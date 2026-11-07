"""The wire log, tested with the SDK client over stdio: the real process, both revisions."""

from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

from tools.wire_summary import summarize

ROOT = Path(__file__).resolve().parents[1]
WIRE = str(ROOT / "tools" / "wire.sh")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("mode", "revision", "first_method"),
    [("auto", "2026-07-28", "server/discover"), ("legacy", "2025-11-25", "initialize")],
)
async def test_wire_log_of_one_start(mode, revision, first_method):
    tag = f"test-{mode}"
    # The client starts tools/wire.sh with PATH and HOME only: the server reads its own .env.
    params = StdioServerParameters(command="bash", args=[WIRE, tag])
    async with Client(params, mode=mode) as client:
        assert client.protocol_version == revision
        result = await client.call_tool("sessions_in_week", {"monday": "2026-11-16"})
    assert result.structured_content["count"] == 36
    wire = summarize(tag, ROOT / "logs")
    assert wire.revision == revision
    assert wire.first_method == first_method
    assert wire.tool_calls == 1
    assert wire.errors == 0
