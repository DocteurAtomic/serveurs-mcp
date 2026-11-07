"""The tool that writes, tested over HTTP with a team token and the SDK client answering in
place of the user.

The tool writes only for a caller with a token, and the in-memory client sends none: these
tests talk to a real `pachatraining-mcp --http`, as alice. It writes to the copy of
write_database() (PachadataTraining_m07 in the lab), never to the reference database, and
each test leaves session 17712 as it found it.
"""

import json
import subprocess
from datetime import date

import pytest
from mcp.types import ElicitResult

from pachatraining_mcp.server import connect, write_database
from tests.http_server import ROOT, free_port, http_client, http_server, wait_for
SESSION = 17712  # MY80-ADM, CONFIRMED, starts on 2026-11-16 in the delivered backup
POSTPONE = {"session_id": SESSION, "new_start_date": "2026-11-30", "as_of": "2026-11-16"}

pytestmark = pytest.mark.anyio


def start_date(session_id: int = SESSION) -> date:
    """Read in the database the tool writes to, through a view of the Mcp schema."""
    with connect(write_database()) as cn:
        cur = cn.cursor()
        cur.execute("SELECT StartDate FROM Mcp.SessionDetail WHERE SessionId = ?", (session_id,))
        return cur.fetchone()[0]


def user(action: str, content: dict | None = None):
    """An elicitation callback that answers like a user would, and keeps the questions."""
    questions = []

    async def answer(context, params):
        questions.append(params)
        return ElicitResult(action=action, content=content)

    return answer, questions


@pytest.fixture(scope="module")
def port():
    with http_server() as p:
        yield p


@pytest.fixture
async def session_as_delivered(port):
    """Session 17712 starts on 2026-11-16 before the test, and again after it, even when the
    test fails halfway."""
    assert start_date() == date(2026, 11, 16), (
        f"Session {SESSION} was left moved in {write_database()}: "
        "recreate the copy with ./setup/reset-copy.sh m07")
    yield
    if start_date() != date(2026, 11, 16):
        back, _ = user("accept", {"confirm": True})
        async with http_client(port, elicitation_callback=back) as c:
            await c.call_tool("postpone_session", {**POSTPONE, "new_start_date": "2026-11-16"})


async def test_postponed_after_accept(port, session_as_delivered):
    answer, questions = user("accept", {"confirm": True})
    async with http_client(port, elicitation_callback=answer) as c:
        result = await c.call_tool("postpone_session", POSTPONE)
        assert not result.is_error, result.content[0].text
        assert result.structured_content["postponed"] is True
        assert start_date() == date(2026, 11, 30)
        back = await c.call_tool("postpone_session", {**POSTPONE, "new_start_date": "2026-11-16"})
        assert not back.is_error, back.content[0].text
    assert len(questions) == 2
    assert start_date() == date(2026, 11, 16)


@pytest.mark.parametrize(("action", "content"),
                         [("decline", None), ("cancel", None), ("accept", {"confirm": False})])
async def test_nothing_written_without_a_yes(port, session_as_delivered, action, content):
    answer, questions = user(action, content)
    async with http_client(port, elicitation_callback=answer) as c:
        result = await c.call_tool("postpone_session", POSTPONE)
    # Not an error: the tool runs and answers the model, which can tell the user.
    assert not result.is_error, result.content[0].text
    assert result.structured_content["postponed"] is False
    assert result.structured_content["start_date"] == "2026-11-16"
    assert len(questions) == 1
    assert start_date() == date(2026, 11, 16)


async def test_the_question_names_the_session_and_the_dates(port, session_as_delivered):
    answer, questions = user("decline")
    async with http_client(port, elicitation_callback=answer) as c:
        await c.call_tool("postpone_session", POSTPONE)
        tool = next(t for t in (await c.list_tools()).tools if t.name == "postpone_session")
    asked = questions[0]
    for part in (str(SESSION), "MY80-ADM", "2026-11-16", "2026-11-30"):
        assert part in asked.message
    assert asked.requested_schema["properties"]["confirm"]["type"] == "boolean"
    # The answer comes from the user, never from the model: it is not a tool argument.
    assert "confirm" not in tool.input_schema["properties"]
    assert tool.annotations.read_only_hint is False


async def test_refusals_reach_the_model(port, session_as_delivered):
    answer, questions = user("accept", {"confirm": True})
    async with http_client(port, elicitation_callback=answer) as c:
        before = await c.call_tool("postpone_session", {**POSTPONE, "new_start_date": "2026-11-02"})
        missing = await c.call_tool("postpone_session", {**POSTPONE, "session_id": 99999})
    assert before.is_error
    # The text of the procedure's THROW, without the prefixes of the driver.
    assert before.content[0].text == (
        "Error executing tool postpone_session: Not postponed: "
        "The new date 2026-11-02 is before 2026-11-16.")
    assert missing.is_error
    assert "Session 99999 not found." in missing.content[0].text
    # One question only, for the first call: no one is asked about a session that is not there.
    assert len(questions) == 1
    assert start_date() == date(2026, 11, 16)


async def test_the_question_travels_in_the_result(port, session_as_delivered):
    """Through tools/wire_http.py: at 2026-07-28 the server returns the question, and the
    client calls the tool again with the answer. Nothing goes from the server to the client
    but responses."""
    answer, _ = user("decline")
    proxy_port = free_port()
    proxy = subprocess.Popen(
        ["uv", "--directory", str(ROOT), "run", "--quiet", "python", "tools/wire_http.py",
         "test-postpone", str(proxy_port), str(port)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        wait_for(proxy_port, proxy, "tools/wire_http.py")
        async with http_client(proxy_port, elicitation_callback=answer) as c:
            result = await c.call_tool("postpone_session", POSTPONE)
    finally:
        proxy.terminate()
        proxy.wait(timeout=10)
    assert result.structured_content["postponed"] is False
    sent = [json.loads(line) for line in (ROOT / "logs/wire-test-postpone.in.jsonl").open()]
    received = [json.loads(line) for line in (ROOT / "logs/wire-test-postpone.out.jsonl").open()]
    calls = [m for m in sent if m.get("method") == "tools/call"]
    assert len(calls) == 2
    first = next(m for m in received if m.get("id") == calls[0]["id"])["result"]
    assert first["resultType"] == "input_required"
    (request,) = first["inputRequests"].values()
    assert request["method"] == "elicitation/create"
    assert calls[1]["params"]["requestState"] == first["requestState"]
    assert list(calls[1]["params"]["inputResponses"].values()) == [{"action": "decline"}]
    # Every message from the server answers a request of the client.
    assert all("method" not in m for m in received)
