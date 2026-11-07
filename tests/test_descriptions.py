"""What the model reads of each tool, checked without a model: the tools/list of the server."""

import pytest
from mcp import Client


@pytest.mark.anyio
async def test_every_tool_and_every_parameter_is_described(client: Client):
    tools = (await client.list_tools()).tools
    assert tools, "the server lists no tool"
    for tool in tools:
        assert tool.description and tool.description.strip(), f"{tool.name} has no description"
        assert tool.title, f"{tool.name} has no title"
        for name, prop in tool.input_schema.get("properties", {}).items():
            assert prop.get("description"), f"{tool.name}: parameter {name} has no description"
