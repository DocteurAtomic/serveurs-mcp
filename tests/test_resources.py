"""Resources, the resource template, the prompt and the completions, tested in memory."""

import pytest
from mcp import Client, MCPError
from mcp.types import PromptReference, ResourceTemplateReference

pytestmark = pytest.mark.anyio

COURSE = ResourceTemplateReference(uri="pachatraining://course/{code}")


async def test_session_statuses(client: Client):
    listed = (await client.list_resources()).resources
    assert "pachatraining://session-statuses" in [str(r.uri) for r in listed]
    contents = (await client.read_resource("pachatraining://session-statuses")).contents
    assert len(contents) == 1
    assert contents[0].mime_type == "text/markdown"
    for status in ("CANCELED", "COMPLETED", "CONFIRMED", "OPEN", "PLANNED"):
        assert f"`{status}`" in contents[0].text


async def test_course_sheet(client: Client):
    templates = (await client.list_resource_templates()).resource_templates
    assert "pachatraining://course/{code}" in [t.uri_template for t in templates]
    # A template is not a resource: it has no address until the client fills it in.
    assert not [r for r in (await client.list_resources()).resources if "course" in str(r.uri)]
    contents = (await client.read_resource("pachatraining://course/LNX-ADM2")).contents
    assert contents[0].mime_type == "text/markdown"
    assert contents[0].text.startswith("# LNX-ADM2: Linux: system administration with systemd")
    assert "- Duration: 4 days" in contents[0].text


async def test_unknown_course(client: Client):
    with pytest.raises(MCPError) as caught:
        await client.read_resource("pachatraining://course/XXX-NONE")
    # -32602 because the function raises ResourceNotFoundError; any other exception is -32603.
    assert caught.value.error.code == -32602
    assert caught.value.error.message == "No course with code XXX-NONE."


async def test_review_week(client: Client):
    prompts = {p.name: p for p in (await client.list_prompts()).prompts}
    assert [(a.name, a.required) for a in prompts["review_week"].arguments] == [("monday", True)]
    result = await client.get_prompt("review_week", {"monday": "2026-11-16"})
    assert [m.role for m in result.messages] == ["user"]
    text = result.messages[0].content.text
    assert "2026-11-16" in text and "sessions_in_week" in text


async def test_completions(client: Client):
    assert client.server_capabilities.completions is not None
    pg1 = (await client.complete(COURSE, {"name": "code", "value": "pg1"})).completion
    assert pg1.values and all(v.startswith("PG1") for v in pg1.values)
    every = (await client.complete(COURSE, {"name": "code", "value": ""})).completion
    # 514 courses, and a response holds 100 values at most.
    assert (len(every.values), every.total, every.has_more) == (100, 514, True)
    week = PromptReference(name="review_week")
    november = (await client.complete(week, {"name": "monday", "value": "2026-11"})).completion
    assert november.values == [
        "2026-11-02", "2026-11-09", "2026-11-16", "2026-11-23", "2026-11-30",
    ]
