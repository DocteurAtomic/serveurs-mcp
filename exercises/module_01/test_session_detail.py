"""Checks of the module 1 exercise, run by check.sh: the session_detail tool, in memory.

Four tests. The expected values are those of the lab database (./setup/install.sh), and the
enrollment counts are also read from the database with a query of their own.
"""

import os

import mssql_python
import pytest
from mcp import Client

from pachatraining_mcp.server import mcp


@pytest.fixture
def anyio_backend():
    return "asyncio"


def active_enrollments(session_id: int) -> int:
    """The count the tool must return, read without the server (the server read .env)."""
    with mssql_python.connect(
        f"Server={os.environ['PACHA_SQL_SERVER']};"
        f"Database={os.environ.get('PACHA_SQL_DATABASE', 'PachadataTraining')};"
        f"UID={os.environ['PACHA_SQL_USER']};PWD={os.environ['PACHA_SQL_PASSWORD']};"
        "Encrypt=yes;TrustServerCertificate=yes"
    ) as cn:
        cur = cn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM Enrollment.Enrollment"
            " WHERE SessionId = ? AND CancellationDate IS NULL",
            (session_id,),
        )
        return cur.fetchone()[0]


@pytest.mark.anyio
async def test_session_detail_is_listed_with_an_integer_session_id():
    async with Client(mcp) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert "session_detail" in tools, "no tool named session_detail"
    schema = tools["session_detail"].input_schema
    assert "session_id" in schema.get("required", []), "session_id must be required"
    assert schema["properties"]["session_id"]["type"] == "integer"


@pytest.mark.anyio
async def test_session_17709_and_its_active_enrollments():
    async with Client(mcp) as client:
        first = await client.call_tool("session_detail", {"session_id": 17709})
        # 17719 has 4 enrollments, one of them cancelled.
        second = await client.call_tool("session_detail", {"session_id": 17719})
    assert not first.is_error, first.content
    detail = first.structured_content
    assert detail["course_code"] == "LNX-ADM2"
    assert detail["title"] == "Linux: system administration with systemd"
    assert detail["start_date"] == "2026-11-16"
    assert detail["status"] == "CONFIRMED"
    assert detail["enrolled"] == active_enrollments(17709) == 6
    assert not second.is_error, second.content
    assert second.structured_content["enrolled"] == active_enrollments(17719) == 3


@pytest.mark.anyio
async def test_unknown_session_is_an_error():
    async with Client(mcp) as client:
        result = await client.call_tool("session_detail", {"session_id": 99999})
    assert result.is_error
    # An error from the tool itself, not the one a server without the tool returns.
    assert "Unknown tool" not in result.content[0].text, "no tool named session_detail"


@pytest.mark.anyio
async def test_sessions_in_week_still_answers():
    async with Client(mcp) as client:
        result = await client.call_tool("sessions_in_week", {"monday": "2026-11-16"})
    assert not result.is_error
    rows = result.structured_content["result"]
    assert len(rows) == 36
    assert rows[0]["session_id"] == 17709
