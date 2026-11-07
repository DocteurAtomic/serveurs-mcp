"""Checks of the module 6 exercise, run by check.sh: sessions_to_watch, paginated by 20 in a
stable order, in memory.

Five tests, on the second half of November and December 2026: 74 sessions PLANNED or OPEN
and less than half full in the lab database, so four pages of 20, 20, 20 and 14.
"""

import pytest
from mcp import Client

from pachatraining_mcp.server import connect, mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp) as c:
        yield c

PERIOD = {"from_date": "2026-11-16", "to_date": "2026-12-31"}

# The query of the README, run here as the server's account: the result the pages must cover.
REFERENCE = """
    SELECT s.SessionId
    FROM Course.Session AS s
    JOIN Course.Course AS c ON c.CourseId = s.CourseId
    WHERE s.StartDate BETWEEN ? AND ?
      AND s.StatusCode IN ('PLANNED', 'OPEN')
      AND (SELECT COUNT(*) FROM Enrollment.Enrollment AS e
           WHERE e.SessionId = s.SessionId AND e.CancellationDate IS NULL) * 2 < c.MaxAttendees
    ORDER BY s.StartDate, s.SessionId"""


async def pages(client: Client, args: dict) -> list[dict]:
    """Every page of one period, following next_cursor; at most 10, to stop a loop."""
    found = []
    args = dict(args)
    for _ in range(10):
        result = await client.call_tool("sessions_to_watch", args)
        assert not result.is_error, result.content[0].text
        found.append(result.structured_content)
        if not found[-1].get("next_cursor"):
            return found
        args["cursor"] = found[-1]["next_cursor"]
    pytest.fail("More than 10 pages: next_cursor never ends")


async def test_a_page_holds_twenty_rows_at_most(client: Client):
    first = (await client.call_tool("sessions_to_watch", PERIOD)).structured_content
    assert first is not None, "sessions_to_watch must return a structured result"
    assert len(first["sessions"]) == 20
    assert first["next_cursor"]
    assert first["total"] == 74


async def test_pages_cover_the_reference_query(client: Client):
    with connect() as cn:
        cur = cn.cursor()
        cur.execute(REFERENCE, (PERIOD["from_date"], PERIOD["to_date"]))
        expected = [r[0] for r in cur.fetchall()]
    got = [s["session_id"] for p in await pages(client, PERIOD) for s in p["sessions"]]
    assert len(expected) == 74
    assert got == expected  # same rows, same order: no duplicate, no gap


async def test_the_last_page_has_no_cursor(client: Client):
    found = await pages(client, PERIOD)
    assert [len(p["sessions"]) for p in found] == [20, 20, 20, 14]
    assert found[-1].get("next_cursor") is None


async def test_a_tampered_cursor_is_refused(client: Client):
    first = (await client.call_tool("sessions_to_watch", PERIOD)).structured_content
    tampered = first["next_cursor"][:-4] + "AAAA"
    result = await client.call_tool("sessions_to_watch", PERIOD | {"cursor": tampered})
    assert result.is_error
    # A message for the model, raised by the tool: not the bare "Error executing tool" of an
    # exception, nor the "Unknown tool" of a server without it.
    assert "cursor" in result.content[0].text.lower(), result.content[0].text


async def test_a_long_period_is_refused(client: Client):
    accepted = await client.call_tool(
        "sessions_to_watch", {"from_date": "2026-11-16", "to_date": "2027-02-16"})
    assert not accepted.is_error, accepted.content[0].text  # 92 days
    refused = await client.call_tool(
        "sessions_to_watch", {"from_date": "2026-11-16", "to_date": "2027-02-17"})
    assert refused.is_error  # 93 days
    assert "92" in refused.content[0].text, refused.content[0].text
