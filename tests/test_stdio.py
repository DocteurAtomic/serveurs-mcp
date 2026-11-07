"""The server as a host starts it: the command given to `claude mcp add`, over stdio."""

from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]

# The same command as `claude mcp add pachatraining -- uv --directory <repo> run pachatraining-mcp`.
# No env=: the SDK gives the process HOME, LOGNAME, PATH, SHELL, TERM and USER only, as a host
# would, and the server must find its connection in its own .env.
SERVER = StdioServerParameters(
    command="uv", args=["--directory", str(ROOT), "run", "--quiet", "pachatraining-mcp"]
)

pytestmark = pytest.mark.anyio


@pytest.fixture
async def stdio():
    """A real process for each test, started and stopped by the client."""
    async with Client(SERVER) as client:
        yield client


async def test_sessions_in_week_over_stdio(stdio: Client):
    result = await stdio.call_tool("sessions_in_week", {"monday": "2026-11-16"})
    assert not result.is_error, result.content[0].text
    assert result.structured_content["count"] == 36
    assert result.structured_content["sessions"][0]["session_id"] == 17709


async def test_session_detail_over_stdio(stdio: Client):
    result = await stdio.call_tool("session_detail", {"session_id": 17709})
    assert not result.is_error, result.content[0].text
    assert result.structured_content["course_code"] == "LNX-ADM2"
    assert result.structured_content["enrolled"] == 6


async def test_trainer_load_over_stdio(stdio: Client):
    result = await stdio.call_tool("trainer_load", {"trainer_id": 38, "month": "2026-10"})
    assert not result.is_error, result.content[0].text
    assert result.structured_content == {
        "trainer_id": 38, "month": "2026-10", "sessions": 3, "days": 6.0,
    }
