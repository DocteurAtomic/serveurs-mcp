"""The pachatraining MCP server: what PachaData's teams ask of the training database."""

import base64
import json
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Literal

import anyio.to_thread
import mssql_python
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError, ToolError
from mcp.types import (
    Completion,
    CompletionArgument,
    CompletionContext,
    PromptReference,
    ResourceTemplateReference,
    ToolAnnotations,
)
from pydantic import BaseModel, Field

# The .env at the root of the project, wherever the host starts the server from.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def load_env(path: Path = ENV_FILE) -> None:
    """Read KEY=VALUE lines from .env. The real environment wins; a missing file is fine."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


load_env()

# The SDK runs a plain def handler in a thread, 40 at most at once (anyio's default limiter).
# A full pool refuses a connection instead of waiting for one, so it is never smaller.
POOL_SIZE = 40


@asynccontextmanager
async def lifespan(server: MCPServer) -> AsyncIterator[None]:
    """Size the connection pool before the first connection: once the pool is on, pooling()
    returns without changing anything. Connections are not opened here: each call takes its
    own, since a connection serves one command at a time (mssql_python.threadsafety is 1)."""
    mssql_python.pooling(max_size=POOL_SIZE, idle_timeout=600)
    yield


mcp = MCPServer("pachatraining", lifespan=lifespan)

# Every tool of this server only reads, and only reads the training database.
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


def connect() -> mssql_python.Connection:
    """Open a connection with the account of .env (pacha_app), never sa. Use it in a with
    block: leaving the block hands the connection back to the pool."""
    return mssql_python.connect(
        f"Server={os.environ['PACHA_SQL_SERVER']};"
        f"Database={os.environ.get('PACHA_SQL_DATABASE', 'PachadataTraining')};"
        f"UID={os.environ['PACHA_SQL_USER']};PWD={os.environ['PACHA_SQL_PASSWORD']};"
        "Encrypt=yes;TrustServerCertificate=yes"
    )


# The five rows of Course.SessionStatus.
Status = Literal["CANCELED", "COMPLETED", "CONFIRMED", "OPEN", "PLANNED"]


class SessionRow(BaseModel):
    session_id: int
    start_date: date
    course_code: str
    title: str | None
    status: Status


class WeekPlan(BaseModel):
    monday: date
    count: Annotated[int, Field(description="Number of sessions in `sessions`.")]
    sessions: list[SessionRow]


@mcp.tool(title="Sessions of a week", annotations=READ_ONLY)
def sessions_in_week(
    monday: Annotated[date, Field(description="Monday of the week, as an ISO date (2026-11-16).")],
    status: Annotated[
        Status | None,
        Field(description="Keep only the sessions in this status; all statuses if omitted."),
    ] = None,
) -> WeekPlan:
    """List the training sessions that start from `monday` to the next Sunday, one row per
    session: id, start date, course code, English title, status.

    Use it to find sessions by date. It does not count enrollments: for one session whose id
    you know, call `session_detail`.
    """
    with connect() as cn:
        cur = cn.cursor()
        cur.execute(
            """SELECT s.SessionId, s.StartDate, c.Code, cl.Title, s.StatusCode
               FROM Course.Session AS s
               JOIN Course.Course AS c ON c.CourseId = s.CourseId
               LEFT JOIN Course.CourseLanguage AS cl
                      ON cl.CourseId = s.CourseId AND cl.LanguageCode = 'EN'
               WHERE s.StartDate >= ? AND s.StartDate < ?
                 AND (? IS NULL OR s.StatusCode = ?)
               ORDER BY s.StartDate, s.SessionId""",
            (monday, monday + timedelta(days=7), status, status),
        )
        rows = [
            SessionRow(session_id=r[0], start_date=r[1], course_code=r[2],
                       title=r[3], status=r[4].strip())
            for r in cur.fetchall()
        ]
    return WeekPlan(monday=monday, count=len(rows), sessions=rows)


class SessionDetail(BaseModel):
    session_id: int
    course_code: str
    title: str | None
    start_date: date
    status: Status
    enrolled: Annotated[int, Field(description="Enrollments that are not cancelled.")]


@mcp.tool(title="Detail of a session", annotations=READ_ONLY)
def session_detail(
    session_id: Annotated[
        int, Field(ge=1, description="Id of the session, as listed by sessions_in_week.")
    ],
) -> SessionDetail:
    """Describe one training session whose id you know: course code, English title, start
    date, status, and the number of trainees enrolled (cancelled enrollments not counted).

    To find a session by date, call `sessions_in_week` first.
    """
    with connect() as cn:
        cur = cn.cursor()
        cur.execute(
            """SELECT s.SessionId, c.Code, cl.Title, s.StartDate, s.StatusCode,
                      (SELECT COUNT(*) FROM Enrollment.Enrollment AS e
                       WHERE e.SessionId = s.SessionId AND e.CancellationDate IS NULL)
               FROM Course.Session AS s
               JOIN Course.Course AS c ON c.CourseId = s.CourseId
               LEFT JOIN Course.CourseLanguage AS cl
                      ON cl.CourseId = s.CourseId AND cl.LanguageCode = 'EN'
               WHERE s.SessionId = ?""",
            (session_id,),
        )
        r = cur.fetchone()
    if r is None:
        # A ToolError reaches the model with its message; any other exception would not.
        raise ToolError(f"Session {session_id} not found.")
    return SessionDetail(session_id=r[0], course_code=r[1], title=r[2], start_date=r[3],
                         status=r[4].strip(), enrolled=r[5])


class TrainerLoad(BaseModel):
    trainer_id: int
    month: str
    sessions: Annotated[
        int, Field(description="Engagements of the trainer in sessions starting that month.")
    ]
    days: Annotated[float, Field(description="Days billed by the trainer for those sessions.")]


@mcp.tool(title="Load of a trainer", annotations=READ_ONLY)
def trainer_load(
    trainer_id: Annotated[int, Field(ge=1, description="Id of the trainer (Trainer.Trainer).")],
    month: Annotated[
        str,
        Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Month, as YYYY-MM (2026-10)."),
    ],
) -> TrainerLoad:
    """Count the sessions a trainer is engaged for in one month, and the days billed for them,
    from the trainer engagements (Trainer.Engagement). A session belongs to the month it
    starts in.

    Engagements are recorded up to mid-October 2026: a later month returns zero.
    """
    first = date(int(month[:4]), int(month[5:]), 1)
    after = date(first.year + first.month // 12, first.month % 12 + 1, 1)
    with connect() as cn:
        cur = cn.cursor()
        cur.execute("SELECT 1 FROM Trainer.Trainer WHERE TrainerId = ?", (trainer_id,))
        if cur.fetchone() is None:
            raise ToolError(f"Trainer {trainer_id} not found.")
        cur.execute(
            """SELECT COUNT(*), COALESCE(SUM(e.DayCount), 0)
               FROM Trainer.Engagement AS e
               JOIN Course.Session AS s ON s.SessionId = e.SessionId
               WHERE e.TrainerId = ? AND s.StartDate >= ? AND s.StartDate < ?""",
            (trainer_id, first, after),
        )
        count, days = cur.fetchone()
    return TrainerLoad(trainer_id=trainer_id, month=month, sessions=count, days=float(days))


@mcp.resource("pachatraining://session-statuses", title="Session statuses",
              mime_type="text/markdown")
def session_statuses() -> str:
    """The five statuses a training session can be in (Course.SessionStatus), with their labels."""
    with connect() as cn:
        cur = cn.cursor()
        cur.execute("SELECT StatusCode, Label FROM Course.SessionStatus ORDER BY StatusCode")
        rows = cur.fetchall()
    return "# Session statuses\n\n" + "\n".join(f"- `{r[0].strip()}`: {r[1]}" for r in rows) + "\n"


@mcp.resource("pachatraining://course/{code}", title="Course sheet", mime_type="text/markdown")
def course_sheet(code: str) -> str:
    """The sheet of one course, by its code (LNX-ADM2): English title, summary, audience,
    prerequisites, objectives, duration and size of a session."""
    with connect() as cn:
        cur = cn.cursor()
        cur.execute(
            """SELECT c.Code, cl.Title, cl.Subtitle, cl.Summary, cl.TargetAudience,
                      cl.Prerequisites, cl.Objectives, c.Duration, c.MaxAttendees,
                      c.CancellationDate
               FROM Course.Course AS c
               LEFT JOIN Course.CourseLanguage AS cl
                      ON cl.CourseId = c.CourseId AND cl.LanguageCode = 'EN'
               WHERE c.Code = ?""",
            (code,),
        )
        r = cur.fetchone()
    if r is None:
        # The client receives -32602 with this message; any other exception would be -32603.
        raise ResourceNotFoundError(f"No course with code {code}.")
    lines = [f"# {r[0]}: {r[1]}", ""]
    if r[2]:
        lines += [f"*{r[2]}*", ""]
    lines += [r[3] or "", "",
              f"- Duration: {r[7]} days", f"- Trainees per session: at most {r[8]}",
              f"- Audience: {r[4]}", f"- Prerequisites: {r[5]}"]
    if r[9]:
        lines += [f"- Cancellation date: {r[9]:%Y-%m-%d}"]
    lines += ["", "## Objectives", ""]
    lines += [f"- {o.strip()}" for o in (r[6] or "").split(";") if o.strip()]
    return "\n".join(lines) + "\n"


@mcp.prompt(title="Review of a week")
def review_week(
    monday: Annotated[str, Field(description="Monday of the week, as an ISO date (2026-11-16).")],
) -> str:
    """Review the training sessions of one week the way the planning team does it."""
    return (
        f"Review the training week that starts on Monday {monday}.\n\n"
        f"1. Call the sessions_in_week tool once, with monday={monday}.\n"
        "2. Give the number of sessions by status.\n"
        "3. List the sessions that are not CONFIRMED yet, by start date, with their id and"
        " course code.\n"
        "4. End with one sentence on what the planning team should check first.\n\n"
        "Rely on the tool result only, and write the review in French."
    )


def course_codes(prefix: str) -> tuple[list[str], int]:
    """The course codes that start with prefix, at most 100, and how many there are."""
    with connect() as cn:
        cur = cn.cursor()
        cur.execute("SELECT Code FROM Course.Course ORDER BY Code")
        codes = [r[0] for r in cur.fetchall() if r[0].startswith(prefix.upper())]
    return codes[:100], len(codes)


def mondays(prefix: str) -> tuple[list[str], int]:
    """The Mondays of the weeks that have sessions, written as ISO dates that start with prefix."""
    with connect() as cn:
        cur = cn.cursor()
        # 1900-01-01 was a Monday: the number of days since then, modulo 7, goes back to it.
        cur.execute(
            """SELECT DISTINCT CONVERT(char(10), DATEADD(day,
                      -(DATEDIFF(day, '19000101', StartDate) % 7), StartDate), 23) AS m
               FROM Course.Session
               ORDER BY m"""
        )
        days = [r[0] for r in cur.fetchall() if r[0].startswith(prefix)]
    return days[:100], len(days)


@mcp.completion()
async def complete(
    ref: PromptReference | ResourceTemplateReference,
    argument: CompletionArgument,
    context: CompletionContext | None,
) -> Completion | None:
    """Suggest course codes for the course sheet, and Mondays for the review of a week."""
    # The handler is async and the driver is not: a query run here directly would hold the
    # event loop, and every other request with it, until it returns.
    if isinstance(ref, ResourceTemplateReference) and argument.name == "code":
        values, total = await anyio.to_thread.run_sync(course_codes, argument.value)
    elif isinstance(ref, PromptReference) and argument.name == "monday":
        values, total = await anyio.to_thread.run_sync(mondays, argument.value)
    else:
        return None
    # A response holds 100 values at most: total and has_more say what was left out.
    return Completion(values=values, total=total, has_more=total > len(values))


@mcp.resource("pachatraining://trainer/{trainer_id}/month/{month}", title="Load of a trainer",
              mime_type="text/markdown")
def trainer_month(trainer_id: int, month: str) -> str:
    """The load of one trainer in one month (YYYY-MM): sessions engaged for, and days billed."""
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ResourceNotFoundError(f"Month {month} is not written as YYYY-MM.")
    try:
        load = trainer_load(trainer_id, month)
    except ToolError as exc:
        # A ToolError is meant for a tool result: out of a resource it would reach the client
        # as -32603, with a message that names only the URI.
        raise ResourceNotFoundError(str(exc)) from exc
    return (f"# Trainer {trainer_id}, {month}\n\n"
            f"- Sessions: {load.sessions}\n- Days billed: {load.days}\n")


@mcp.prompt(title="Review of a trainer's month")
def trainer_review(
    trainer_id: Annotated[str, Field(description="Id of the trainer (Trainer.Trainer).")],
    month: Annotated[str, Field(description="Month, as YYYY-MM (2026-10).")],
) -> str:
    """Review the load of one trainer in one month the way the planning team does it."""
    return (
        f"Review the load of trainer {trainer_id} in {month}.\n\n"
        f"1. Call the trainer_load tool once, with trainer_id={trainer_id} and month={month}.\n"
        "2. Give the number of sessions and the days billed.\n"
        "3. Say in one sentence whether the load looks light, normal or heavy for one month.\n\n"
        "Rely on the tool result only, and write the review in French."
    )


PAGE_SIZE = 50


class UnpaidInvoice(BaseModel):
    invoice_code: str
    due_date: date
    client: Annotated[str, Field(description="Company name, or the trainee's name.")]
    amount_due: Annotated[float, Field(description="Gross amount minus the payments, in euros.")]


class UnpaidPage(BaseModel):
    as_of: date
    days: int
    total: Annotated[int, Field(description="Unpaid invoices over all pages, not this one.")]
    total_due: Annotated[float, Field(description="Amount due over all pages, in euros.")]
    invoices: list[UnpaidInvoice]
    next_cursor: Annotated[
        str | None,
        Field(description="Pass it back as cursor for the next page; absent on the last page."),
    ] = None


class _Position(BaseModel):
    """What a cursor holds: the arguments of the first call, and the last row sent."""
    as_of: date
    days: int
    due_date: date
    invoice_code: str


def _encode(position: _Position) -> str:
    return base64.urlsafe_b64encode(position.model_dump_json().encode()).decode()


def _decode(cursor: str, as_of: date, days: int) -> _Position:
    try:
        position = _Position.model_validate_json(base64.urlsafe_b64decode(cursor.encode()))
    except ValueError:
        raise ToolError("Invalid cursor: pass back the next_cursor of the previous page as is.")
    if (position.as_of, position.days) != (as_of, days):
        raise ToolError("This cursor belongs to another as_of or days: start again without it.")
    return position


# Invoices only (DocumentType 'I'; 'A' is a credit note), whose payments do not cover the gross
# amount, due before the cut-off date. Payments are summed whatever their date.
UNPAID = """
    FROM Enrollment.Invoice AS i
    LEFT JOIN (SELECT InvoiceCode, SUM(Amount) AS Paid
               FROM Enrollment.Payment GROUP BY InvoiceCode) AS p
           ON p.InvoiceCode = i.InvoiceCode
    LEFT JOIN Contact.Company AS co ON co.CompanyId = i.CompanyId
    LEFT JOIN Contact.Contact AS ct ON ct.ContactId = i.ContactId
    WHERE i.DocumentType = 'I' AND i.GrossAmount > ISNULL(p.Paid, 0) AND i.DueDate < ?"""


@mcp.tool(title="Unpaid invoices", annotations=READ_ONLY)
def unpaid_invoices(
    as_of: Annotated[date, Field(description="Date the debts are counted at, as an ISO date.")],
    days: Annotated[
        int, Field(ge=0, le=3650, description="Days past the due date; 30 by default.")
    ] = 30,
    cursor: Annotated[
        str | None, Field(description="next_cursor of the previous page; omit for the first.")
    ] = None,
) -> UnpaidPage:
    """List the invoices still unpaid more than `days` days after their due date, at `as_of`,
    oldest due date first, 50 per page. `total` and `total_due` cover all pages: when
    `next_cursor` is present, call again with it to get the next page.
    """
    cutoff = as_of - timedelta(days=days)
    after = _decode(cursor, as_of, days) if cursor else None
    with connect() as cn:
        cur = cn.cursor()
        cur.execute(f"SELECT COUNT(*), SUM(i.GrossAmount - ISNULL(p.Paid, 0)) {UNPAID}", (cutoff,))
        total, total_due = cur.fetchone()
        # One row more than a page says whether there is a next one. The order is unique
        # (InvoiceCode breaks the ties of DueDate), so the pages never overlap nor skip a row.
        cur.execute(
            f"""SELECT TOP (?) i.InvoiceCode, i.DueDate,
                       COALESCE(co.Name, CONCAT(ct.FirstName, ' ', ct.LastName)),
                       i.GrossAmount - ISNULL(p.Paid, 0)
                {UNPAID}
                  AND (? IS NULL OR i.DueDate > ? OR (i.DueDate = ? AND i.InvoiceCode > ?))
                ORDER BY i.DueDate, i.InvoiceCode""",
            (PAGE_SIZE + 1, cutoff,
             after and after.due_date, after and after.due_date, after and after.due_date,
             after and after.invoice_code),
        )
        rows = cur.fetchall()
    invoices = [UnpaidInvoice(invoice_code=r[0], due_date=r[1], client=r[2],
                              amount_due=float(r[3]))
                for r in rows[:PAGE_SIZE]]
    next_cursor = None
    if len(rows) > PAGE_SIZE:
        last = invoices[-1]
        next_cursor = _encode(_Position(as_of=as_of, days=days, due_date=last.due_date,
                                        invoice_code=last.invoice_code))
    return UnpaidPage(as_of=as_of, days=days, total=total, total_due=float(total_due or 0),
                      invoices=invoices, next_cursor=next_cursor)


def main() -> None:
    mcp.run()
