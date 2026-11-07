"""cancelled_enrollments, read in the reference database: nothing here writes.

The reason written as an attack is checked by exercises/module_09/check.sh, which recreates
PachadataTraining_m09 and cancels an enrollment there.
"""

import pytest
from mcp import Client

pytestmark = pytest.mark.anyio


async def test_a_cancellation_without_reason(client: Client):
    result = await client.call_tool("cancelled_enrollments", {"session_id": 17719})
    assert not result.is_error, result.content[0].text
    assert result.structured_content["cancellations"] == [{
        "enrollment_id": 150753, "trainee": "Samuel Duchadeau",
        "cancelled_on": "2026-10-07", "free_text": {"reason": None},
    }]


async def test_a_session_without_cancellation(client: Client):
    result = await client.call_tool("cancelled_enrollments", {"session_id": 17710})
    assert not result.is_error, result.content[0].text
    assert result.structured_content == {"session_id": 17710, "count": 0, "cancellations": []}


async def test_free_text_is_described(client: Client):
    tool = next(t for t in (await client.list_tools()).tools if t.name == "cancelled_enrollments")
    assert tool.annotations.read_only_hint is True
    row = tool.output_schema["$defs"]["CancelledEnrollment"]
    assert "typed by people" in row["properties"]["free_text"]["description"]
