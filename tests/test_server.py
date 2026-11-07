"""The server, tested in memory with the SDK client: no model, no subprocess."""

import pytest
from mcp import Client

from pachatraining_mcp.server import mcp


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_sessions_in_week():
    async with Client(mcp) as client:
        tools = await client.list_tools()
        # Present, whatever the number of tools: the next tools must not break this test.
        assert "sessions_in_week" in [t.name for t in tools.tools]
        result = await client.call_tool("sessions_in_week", {"monday": "2026-11-16"})
        confirmed = await client.call_tool(
            "sessions_in_week", {"monday": "2026-11-16", "status": "CONFIRMED"}
        )
    assert not result.is_error
    week = result.structured_content
    assert week["monday"] == "2026-11-16"
    assert week["count"] == len(week["sessions"]) == 36
    assert week["sessions"][0]["session_id"] == 17709
    assert not confirmed.is_error
    assert confirmed.structured_content["count"] == 27


@pytest.mark.anyio
async def test_session_detail():
    async with Client(mcp) as client:
        result = await client.call_tool("session_detail", {"session_id": 17709})
        missing = await client.call_tool("session_detail", {"session_id": 99999})
    assert not result.is_error
    assert result.structured_content["course_code"] == "LNX-ADM2"
    assert result.structured_content["enrolled"] == 6
    assert missing.is_error
    # A ToolError: the model reads why. An ordinary exception would only say the call failed.
    text = missing.content[0].text
    assert text == "Error executing tool session_detail: Session 99999 not found."


@pytest.mark.anyio
async def test_arguments_are_checked_before_the_function():
    async with Client(mcp) as client:
        late = await client.call_tool(
            "sessions_in_week", {"monday": "2026-11-16", "status": "LATE"}
        )
        zero = await client.call_tool("session_detail", {"session_id": 0})
    assert late.is_error
    # The validation error of pydantic, sent before the function runs: the model reads it.
    assert "'CANCELED', 'COMPLETED', 'CONFIRMED', 'OPEN' or 'PLANNED'" in late.content[0].text
    assert zero.is_error
    assert "greater than or equal to 1" in zero.content[0].text
