"""Checks of the module 3 exercise, run by check.sh: the trainer_load tool, in memory.

Five tests. The expected values are those of the lab database (./setup/install.sh), and the
load of trainer 38 in October 2026 is also read from the database with a query of its own.
"""

import os

import mssql_python
import pytest
from mcp import Client

from pachatraining_mcp.server import mcp

FIELDS = {"trainer_id", "month", "sessions", "days"}


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def trainer_load_tool():
    async with Client(mcp) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert "trainer_load" in tools, "no tool named trainer_load"
    return tools["trainer_load"]


def engagements(trainer_id: int, first: str, after: str) -> tuple[int, float]:
    """The load the tool must return, read without the server (the server read .env)."""
    with mssql_python.connect(
        f"Server={os.environ['PACHA_SQL_SERVER']};"
        f"Database={os.environ.get('PACHA_SQL_DATABASE', 'PachadataTraining')};"
        f"UID={os.environ['PACHA_SQL_USER']};PWD={os.environ['PACHA_SQL_PASSWORD']};"
        "Encrypt=yes;TrustServerCertificate=yes"
    ) as cn:
        cur = cn.cursor()
        cur.execute(
            "SELECT COUNT(*), COALESCE(SUM(e.DayCount), 0) FROM Trainer.Engagement AS e"
            " JOIN Course.Session AS s ON s.SessionId = e.SessionId"
            " WHERE e.TrainerId = ? AND s.StartDate >= ? AND s.StartDate < ?",
            (trainer_id, first, after),
        )
        count, days = cur.fetchone()
        return count, float(days)


@pytest.mark.anyio
async def test_output_schema_names_the_fields():
    tool = await trainer_load_tool()
    assert tool.output_schema, "trainer_load has no outputSchema: return a pydantic model"
    missing = FIELDS - set(tool.output_schema.get("properties", {}))
    assert not missing, f"fields missing from the outputSchema: {sorted(missing)}"


@pytest.mark.anyio
async def test_a_month_13_is_refused_by_the_schema():
    async with Client(mcp) as client:
        result = await client.call_tool("trainer_load", {"trainer_id": 38, "month": "2026-13"})
    assert result.is_error, "2026-13 was accepted"
    # Refused against the input schema, before the function: pydantic says why.
    assert "validation error for trainer_loadArguments" in result.content[0].text, (
        "2026-13 reached the function: month needs a pattern in its Field"
    )


@pytest.mark.anyio
async def test_unknown_trainer_is_an_error_that_names_it():
    async with Client(mcp) as client:
        result = await client.call_tool("trainer_load", {"trainer_id": 999, "month": "2026-10"})
    assert result.is_error, "trainer 999 does not exist, and the tool returned a result"
    text = result.content[0].text
    assert "Unknown tool" not in text, "no tool named trainer_load"
    assert "999" in text, f"the model cannot tell which trainer is missing: {text!r}"


@pytest.mark.anyio
async def test_trainer_38_in_october_2026():
    async with Client(mcp) as client:
        result = await client.call_tool("trainer_load", {"trainer_id": 38, "month": "2026-10"})
    assert not result.is_error, result.content
    load = result.structured_content
    expected = engagements(38, "2026-10-01", "2026-11-01")
    assert expected == (3, 6.0)
    assert (load["sessions"], load["days"]) == expected
    assert load["trainer_id"] == 38
    assert load["month"] == "2026-10"


@pytest.mark.anyio
async def test_every_parameter_is_described():
    tool = await trainer_load_tool()
    assert tool.description and tool.description.strip(), "trainer_load has no description"
    properties = tool.input_schema.get("properties", {})
    assert set(properties) == {"trainer_id", "month"}, f"parameters: {sorted(properties)}"
    for name, prop in properties.items():
        assert prop.get("description"), f"parameter {name} has no description"
