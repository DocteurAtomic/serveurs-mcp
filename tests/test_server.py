"""The server, tested in memory with the SDK client: no model, no subprocess."""

from datetime import date

import pytest
from mcp import Client

pytestmark = pytest.mark.anyio


async def test_sessions_in_week(client: Client):
    tools = await client.list_tools()
    # Present, whatever the number of tools: the next tools must not break this test.
    assert "sessions_in_week" in [t.name for t in tools.tools]
    result = await client.call_tool("sessions_in_week", {"monday": "2026-11-16"})
    confirmed = await client.call_tool(
        "sessions_in_week", {"monday": "2026-11-16", "status": "CONFIRMED"}
    )
    assert not result.is_error, result.content[0].text
    week = result.structured_content
    assert week["monday"] == "2026-11-16"
    assert week["count"] == len(week["sessions"]) == 36
    assert week["sessions"][0]["session_id"] == 17709
    assert not confirmed.is_error, confirmed.content[0].text
    assert confirmed.structured_content["count"] == 27


async def test_a_week_ends_on_sunday(client: Client):
    result = await client.call_tool("sessions_in_week", {"monday": "2026-11-16"})
    assert not result.is_error, result.content[0].text
    starts = {date.fromisoformat(s["start_date"]) for s in result.structured_content["sessions"]}
    # True of any week, whatever the data: no session before the Monday or after the Sunday.
    assert min(starts) >= date(2026, 11, 16)
    assert max(starts) <= date(2026, 11, 22)


async def test_session_detail(client: Client):
    result = await client.call_tool("session_detail", {"session_id": 17709})
    missing = await client.call_tool("session_detail", {"session_id": 99999})
    assert not result.is_error, result.content[0].text
    assert result.structured_content["course_code"] == "LNX-ADM2"
    assert result.structured_content["enrolled"] == 6
    assert missing.is_error
    # A ToolError: the model reads why. An ordinary exception would only say the call failed.
    text = missing.content[0].text
    assert text == "Error executing tool session_detail: Session 99999 not found."


async def test_arguments_are_checked_before_the_function(client: Client):
    late = await client.call_tool("sessions_in_week", {"monday": "2026-11-16", "status": "LATE"})
    zero = await client.call_tool("session_detail", {"session_id": 0})
    assert late.is_error
    # The validation error of pydantic, sent before the function runs: the model reads it.
    assert "'CANCELED', 'COMPLETED', 'CONFIRMED', 'OPEN' or 'PLANNED'" in late.content[0].text
    assert zero.is_error
    assert "greater than or equal to 1" in zero.content[0].text


async def test_trainer_load(client: Client):
    result = await client.call_tool("trainer_load", {"trainer_id": 38, "month": "2026-10"})
    missing = await client.call_tool("trainer_load", {"trainer_id": 999, "month": "2026-10"})
    assert not result.is_error, result.content[0].text
    assert result.structured_content == {
        "trainer_id": 38, "month": "2026-10", "sessions": 3, "days": 6.0,
    }
    assert missing.is_error
    assert missing.content[0].text == "Error executing tool trainer_load: Trainer 999 not found."
