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
        assert not result.is_error
        rows = result.structured_content["result"]
        assert len(rows) == 36
        assert rows[0]["session_id"] == 17709
