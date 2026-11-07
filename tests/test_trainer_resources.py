"""The month of a trainer, as a resource template and as a prompt, tested in memory.

The checks of the module 5 exercise, on the fixtures of conftest.py. The load of trainer 38
in October 2026 is the one of the module 3 exercise: 3 sessions and 6.0 days in
Trainer.Engagement of the lab database.
"""

import pytest
from mcp import Client, MCPError

TEMPLATE = "pachatraining://trainer/{trainer_id}/month/{month}"

pytestmark = pytest.mark.anyio


async def test_the_template_is_listed_as_a_template(client: Client):
    templates = (await client.list_resource_templates()).resource_templates
    assert TEMPLATE in [t.uri_template for t in templates], f"no template {TEMPLATE}"
    resources = (await client.list_resources()).resources
    assert not [r for r in resources if "trainer" in str(r.uri)], "a trainer resource is listed"


async def test_the_month_of_trainer_38(client: Client):
    uri = "pachatraining://trainer/38/month/2026-10"
    contents = (await client.read_resource(uri)).contents
    assert len(contents) == 1
    assert str(contents[0].uri) == uri
    assert contents[0].mime_type == "text/markdown"
    text = contents[0].text
    assert text.startswith("# Trainer 38, 2026-10"), text
    assert "- Sessions: 3\n" in text and "- Days billed: 6.0\n" in text, text


async def test_an_unknown_trainer_is_invalid_params(client: Client):
    with pytest.raises(MCPError) as caught:
        await client.read_resource("pachatraining://trainer/999/month/2026-10")
    error = caught.value.error
    # A server without the template answers -32602 too, with "Unknown resource": the message
    # must come from the function, which ran and found no trainer 999.
    assert not error.message.startswith("Unknown resource"), error
    # -32602 only when the function raises ResourceNotFoundError; anything else is -32603.
    assert error.code == -32602, error
    assert "999" in error.message, error


async def test_the_prompt_takes_two_required_arguments(client: Client):
    prompts = {p.name: p for p in (await client.list_prompts()).prompts}
    assert "trainer_review" in prompts, "no prompt named trainer_review"
    arguments = {a.name: a.required for a in prompts["trainer_review"].arguments or []}
    assert arguments == {"trainer_id": True, "month": True}


async def test_the_prompt_names_the_trainer_and_the_month(client: Client):
    result = await client.get_prompt("trainer_review", {"trainer_id": "38", "month": "2026-10"})
    assert [m.role for m in result.messages] == ["user"]
    text = result.messages[0].content.text
    assert "38" in text and "2026-10" in text and "trainer_load" in text, text
