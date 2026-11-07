"""The checks of the module 8 exercise: the server reads the views of the Mcp schema only, with
an account that has no right outside it, and no password lives in the code.

Run by check.sh, next to this file, with the lab started and .env on mcp_reader
(uv run python setup/use_account.py mcp_reader).
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import mssql_python
import pytest
from mcp import Client, MCPError

from pachatraining_mcp.server import connect, mcp

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "pachatraining_mcp"
# The suite of modules 1 to 7, exercises included, as module-08-start has it.
SUITE_AT_LEAST = 42

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        yield c


def scalar(query: str, *params):
    with connect() as cn:
        cur = cn.cursor()
        cur.execute(query, params)
        return cur.fetchone()[0]


def test_the_suite_passes_as_mcp_reader():
    assert scalar("SELECT SUSER_SNAME()") == "mcp_reader", (
        "The server does not connect as mcp_reader: "
        "run uv run python setup/use_account.py mcp_reader")
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    summary = run.stdout.strip().splitlines()[-1] if run.stdout.strip() else run.stderr
    passed = re.search(r"(\d+) passed", summary)
    assert run.returncode == 0, run.stdout[-3000:]
    assert passed and int(passed.group(1)) >= SUITE_AT_LEAST, summary
    assert not re.search(r"skipped|deselected|xfail", summary), summary


def test_trainer_month_is_a_view_of_the_mcp_schema():
    assert scalar("SELECT OBJECTPROPERTY(OBJECT_ID(N'Mcp.TrainerMonth'), 'IsView')") == 1, (
        "No view Mcp.TrainerMonth: write it in setup/mcp-schema.sql, then run ./setup/install.sh")
    with connect() as cn:
        cur = cn.cursor()
        cur.execute("SELECT SessionCount, DayCount FROM Mcp.TrainerMonth "
                    "WHERE TrainerId = 38 AND Month = '2026-10'")
        assert [(r[0], float(r[1])) for r in cur.fetchall()] == [(3, 6.0)]


async def test_trainer_load_reads_the_view(client: Client):
    # Trainer 3 exists and has no engagement at all: zero, not "not found".
    idle = await client.call_tool("trainer_load", {"trainer_id": 3, "month": "2026-10"})
    assert not idle.is_error, idle.content[0].text
    assert idle.structured_content == {"trainer_id": 3, "month": "2026-10",
                                       "sessions": 0, "days": 0.0}
    text = (await client.read_resource("pachatraining://trainer/3/month/2026-10")).contents[0].text
    assert "- Sessions: 0\n" in text, text
    missing = await client.call_tool("trainer_load", {"trainer_id": 999, "month": "2026-10"})
    assert missing.is_error
    assert missing.content[0].text == "Error executing tool trainer_load: Trainer 999 not found."
    with pytest.raises(MCPError) as caught:
        await client.read_resource("pachatraining://trainer/999/month/2026-10")
    assert caught.value.error.code == -32602, caught.value.error


# A schema-qualified name after the SQL keywords that read or write an object, once the
# Python imports (from collections.abc import ...) are left out.
SQL_NAME = re.compile(r"\b(?:FROM|JOIN|INTO|UPDATE|EXEC(?:UTE)?)\s+\[?(\w+)\]?\s*\.\s*\[?(\w+)",
                      re.IGNORECASE)
IMPORT = re.compile(r"^\s*(?:from\s+[\w.]+\s+import|import)\b.*$", re.MULTILINE)


def test_the_code_names_only_the_mcp_schema_and_no_password():
    names = set()
    for path in SOURCE.rglob("*.py"):
        code = IMPORT.sub("", path.read_text())
        names |= {(m.group(1), m.group(2)) for m in SQL_NAME.finditer(code)}
    assert len(names) >= 8, f"Too few SQL names found in {SOURCE}: {sorted(names)}"
    outside = sorted(f"{schema}.{name}" for schema, name in names if schema.lower() != "mcp")
    assert outside == [], f"The server names objects outside the Mcp schema: {outside}"
    # Every file git would commit, untracked ones included: .env is ignored and stays out.
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    secrets = {v for k, v in os.environ.items() if k.endswith("PASSWORD") and len(v) >= 8}
    assert secrets, "No password in the environment: is .env there?"
    leaked = sorted(f for f in files if (ROOT / f).is_file()
                    and any(s in (ROOT / f).read_text(errors="ignore") for s in secrets))
    assert leaked == [], f"A password of .env is written in {leaked}"


def test_mcp_reader_has_no_right_outside_the_mcp_schema():
    with connect() as cn:
        cur = cn.cursor()
        # The rights granted to the account itself, and the roles it belongs to.
        cur.execute("""SELECT p.class_desc, p.permission_name,
                              COALESCE(SCHEMA_NAME(CASE WHEN p.class = 3 THEN p.major_id END),
                                       OBJECT_SCHEMA_NAME(p.major_id) + '.' + OBJECT_NAME(p.major_id))
                       FROM sys.database_permissions AS p
                       WHERE p.grantee_principal_id = USER_ID() AND p.state IN ('G', 'W')""")
        granted = sorted((r[0], r[1], r[2]) for r in cur.fetchall())
        cur.execute("SELECT COUNT(*) FROM sys.database_role_members "
                    "WHERE member_principal_id = USER_ID()")
        roles = cur.fetchone()[0]
        # What it can see of tables and views outside Mcp, whoever granted it (public too).
        cur.execute("SELECT COUNT(*) FROM sys.objects WHERE type IN ('U', 'V') "
                    "AND schema_id <> SCHEMA_ID(N'Mcp')")
        visible = cur.fetchone()[0]
    assert granted == [
        ("DATABASE", "CONNECT", None),
        ("OBJECT_OR_COLUMN", "EXECUTE", "Mcp.CancelEnrollment"),
        ("OBJECT_OR_COLUMN", "EXECUTE", "Mcp.PostponeSession"),
        ("SCHEMA", "SELECT", "Mcp"),
    ], granted
    assert roles == 0, "mcp_reader belongs to a database role"
    assert visible == 0, f"mcp_reader sees {visible} tables or views outside the Mcp schema"
    with pytest.raises(mssql_python.DatabaseError, match="SELECT permission was denied"):
        scalar("SELECT COUNT(*) FROM Contact.Contact")
