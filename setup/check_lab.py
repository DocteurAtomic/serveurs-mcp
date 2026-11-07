"""Checks that the lab is the one the course was recorded on. Run: uv run python setup/check_lab.py

Reads .env like the server does (the real environment wins), connects from the host with
mssql-python as pacha_app and as mcp_reader, and compares what it reads with the numbers the
videos show. Exit code 0 when everything matches, 1 otherwise.
"""

import os
import sys
from pathlib import Path

import mssql_python

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def connect(user: str, password: str, database: str = "PachadataTraining"):
    return mssql_python.connect(
        f"Server={os.environ['PACHA_SQL_SERVER']};Database={database};UID={user};"
        f"PWD={password};Encrypt=yes;TrustServerCertificate=yes"
    )


def scalar(cn, query: str, *params):
    cur = cn.cursor()
    cur.execute(query, params)
    return cur.fetchone()[0]


WEEK = "StartDate >= '2026-11-16' AND StartDate < '2026-11-23'"
EXPECTED_AS_PACHA_APP = [
    ("sessions in the week of 16 November 2026",
     f"SELECT COUNT(*) FROM Course.Session WHERE {WEEK}", 36),
    ("same week with <= instead of <",
     "SELECT COUNT(*) FROM Course.Session WHERE StartDate >= '2026-11-16' AND StartDate <= '2026-11-23'", 51),
    ("CONFIRMED that week", f"SELECT COUNT(*) FROM Course.Session WHERE {WEEK} AND StatusCode = 'CONFIRMED'", 27),
    ("OPEN that week", f"SELECT COUNT(*) FROM Course.Session WHERE {WEEK} AND StatusCode = 'OPEN'", 9),
    ("PLANNED that week", f"SELECT COUNT(*) FROM Course.Session WHERE {WEEK} AND StatusCode = 'PLANNED'", 0),
    ("first session of the week",
     f"SELECT TOP (1) SessionId FROM Course.Session WHERE {WEEK} ORDER BY StartDate, SessionId", 17709),
    ("sessions", "SELECT COUNT(*) FROM Course.Session", 19300),
    ("invoices", "SELECT COUNT(*) FROM Enrollment.Invoice", 110737),
    ("invoice lines", "SELECT COUNT(*) FROM Enrollment.InvoiceLine", 250198),
    ("contacts", "SELECT COUNT(*) FROM Contact.Contact", 120140),
    ("last session with a trainer engagement",
     "SELECT CONVERT(char(10), MAX(s.StartDate), 23) FROM Trainer.Engagement AS e "
     "JOIN Course.Session AS s ON s.SessionId = e.SessionId", "2026-10-15"),
    ("database compatibility level",
     "SELECT compatibility_level FROM sys.databases WHERE name = DB_NAME()", 170),
]
EXPECTED_AS_MCP_READER = [
    ("Mcp.SessionSummary, week of 16 November 2026",
     f"SELECT COUNT(*) FROM Mcp.SessionSummary WHERE {WEEK}", 36),
    ("Mcp.SessionDetail, enrolled in 17709",
     "SELECT EnrolledCount FROM Mcp.SessionDetail WHERE SessionId = 17709", 6),
    ("Mcp.SessionStatus", "SELECT COUNT(*) FROM Mcp.SessionStatus", 5),
    ("Mcp.CourseSheet, English sheets", "SELECT COUNT(*) FROM Mcp.CourseSheet WHERE LanguageCode = 'EN'", 514),
    ("Mcp.UnpaidInvoice, due before 2026-10-17",
     "SELECT COUNT(*) FROM Mcp.UnpaidInvoice WHERE DueDate < '2026-10-17'", 4301),
]


def main() -> int:
    load_env()
    failures = 0

    def check(cn, label, query, expected):
        nonlocal failures
        try:
            got = scalar(cn, query)
        except mssql_python.Error as exc:
            got = f"error: {exc}"
        ok = got == expected
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {label}: {got}" + ("" if ok else f" (expected {expected})"))

    with connect("pacha_app", os.environ["PACHA_APP_PASSWORD"]) as cn:
        for label, query, expected in EXPECTED_AS_PACHA_APP:
            check(cn, label, query, expected)
    with connect("mcp_reader", os.environ["MCP_READER_PASSWORD"]) as cn:
        for label, query, expected in EXPECTED_AS_MCP_READER:
            check(cn, label, query, expected)
        try:
            scalar(cn, "SELECT TOP (1) Email FROM Contact.Contact")
            print("FAIL mcp_reader can read Contact.Contact")
            failures += 1
        except mssql_python.Error as exc:
            ok = "229" in str(exc) or "permission was denied" in str(exc)
            failures += not ok
            print(f"{'ok  ' if ok else 'FAIL'} mcp_reader is refused Contact.Contact: {str(exc)[:120]}")
    for copy in ("PachadataTraining_m07", "PachadataTraining_m09"):
        try:
            cn = connect("pacha_app", os.environ["PACHA_APP_PASSWORD"], copy)
        except mssql_python.Error as exc:
            print(f"FAIL {copy}: {str(exc)[:120]} (./setup/reset-copy.sh {copy[-3:]})")
            failures += 1
            continue
        with cn:
            check(cn, f"{copy}, Mcp.SessionSummary", f"SELECT COUNT(*) FROM Mcp.SessionSummary WHERE {WEEK}", 36)
    print("lab ok" if failures == 0 else f"{failures} check(s) failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
