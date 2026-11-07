"""The pachatraining MCP server: what PachaData's teams ask of the training database."""

import os
from datetime import date, timedelta
from pathlib import Path

import mssql_python
from mcp.server import MCPServer
from pydantic import BaseModel

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
mcp = MCPServer("pachatraining")


def connect() -> mssql_python.Connection:
    """Open a connection with the account of .env (pacha_app), never sa."""
    return mssql_python.connect(
        f"Server={os.environ['PACHA_SQL_SERVER']};"
        f"Database={os.environ.get('PACHA_SQL_DATABASE', 'PachadataTraining')};"
        f"UID={os.environ['PACHA_SQL_USER']};PWD={os.environ['PACHA_SQL_PASSWORD']};"
        "Encrypt=yes;TrustServerCertificate=yes"
    )


class SessionRow(BaseModel):
    session_id: int
    start_date: date
    course_code: str
    title: str | None
    status: str


@mcp.tool()
def sessions_in_week(monday: date) -> list[SessionRow]:
    """List the training sessions that start in the week beginning on `monday` (ISO date)."""
    with connect() as cn:
        cur = cn.cursor()
        cur.execute(
            """SELECT s.SessionId, s.StartDate, c.Code, cl.Title, s.StatusCode
               FROM Course.Session AS s
               JOIN Course.Course AS c ON c.CourseId = s.CourseId
               LEFT JOIN Course.CourseLanguage AS cl
                      ON cl.CourseId = s.CourseId AND cl.LanguageCode = 'EN'
               WHERE s.StartDate >= ? AND s.StartDate < ?
               ORDER BY s.StartDate, s.SessionId""",
            (monday, monday + timedelta(days=7)),
        )
        return [
            SessionRow(session_id=r[0], start_date=r[1], course_code=r[2],
                       title=r[3], status=r[4].strip())
            for r in cur.fetchall()
        ]


def main() -> None:
    mcp.run()
