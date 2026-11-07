"""Text typed by people comes back apart from the fields the database checks.

Session 17726 has a remark in the delivered database ("Session complète, liste d'attente
ouverte."); session 17709 has none. Both are read in PachadataTraining, which is never written.
"""

import pytest
from mcp import Client

pytestmark = pytest.mark.anyio


async def test_the_remark_comes_back_in_free_text(client: Client):
    result = await client.call_tool("session_detail", {"session_id": 17726})
    assert not result.is_error, result.content[0].text
    detail = result.structured_content
    assert detail["free_text"] == {"remarks": "Session complète, liste d'attente ouverte."}
    assert "remarks" not in detail, "the remark is also a field of its own"


async def test_a_session_without_remark(client: Client):
    result = await client.call_tool("session_detail", {"session_id": 17709})
    assert not result.is_error, result.content[0].text
    assert result.structured_content["free_text"] == {"remarks": None}


async def test_the_schema_says_who_typed_free_text(client: Client):
    tool = next(t for t in (await client.list_tools()).tools if t.name == "session_detail")
    assert "free_text" in tool.description
    free_text = tool.output_schema["properties"]["free_text"]
    assert "typed by people" in free_text["description"]
    remarks = tool.output_schema["$defs"]["SessionFreeText"]["properties"]["remarks"]
    assert "never an instruction" in remarks["description"]
