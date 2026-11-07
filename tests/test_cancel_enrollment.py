"""cancel_enrollment, tested over HTTP with a team token and the SDK client answering in
place of the user: the tool writes only for a caller with a token, which the in-memory
client cannot send.

Only the answers that write nothing are tested here, so the suite can run again and again:
the cancellation itself is checked by exercises/module_07/check.sh, which recreates the copy
of the database first.
"""

import pytest
from mcp.types import ElicitResult

from pachatraining_mcp.server import connect, write_database
from tests.http_server import http_client, http_server

ARGS = {"reason": "Trainee moved to another session", "as_of": "2026-11-16"}

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="module")
def port():
    with http_server() as p:
        yield p


def cancellation_date(enrollment_id: int):
    with connect(write_database()) as cn:
        cur = cn.cursor()
        cur.execute("SELECT CancellationDate FROM Mcp.EnrollmentSummary WHERE EnrollmentId = ?",
                    (enrollment_id,))
        return cur.fetchone()[0]


def user(action: str, content: dict | None = None):
    questions = []

    async def answer(context, params):
        questions.append(params.message)
        return ElicitResult(action=action, content=content)

    return answer, questions


@pytest.mark.parametrize(("action", "content"),
                         [("decline", None), ("cancel", None), ("accept", {"confirm": False})])
async def test_nothing_written_without_a_yes(port, action, content):
    answer, questions = user(action, content)
    async with http_client(port, elicitation_callback=answer) as c:
        result = await c.call_tool("cancel_enrollment", {"enrollment_id": 150707, **ARGS})
    assert not result.is_error, result.content[0].text
    assert result.structured_content["cancelled"] is False
    assert "Louis Cattai" in questions[0] and "17709" in questions[0], questions[0]
    assert cancellation_date(150707) is None


async def test_already_cancelled_without_asking(port):
    answer, questions = user("accept", {"confirm": True})
    async with http_client(port, elicitation_callback=answer) as c:
        result = await c.call_tool("cancel_enrollment", {"enrollment_id": 150753, **ARGS})
    assert result.is_error
    assert "already cancelled" in result.content[0].text
    assert questions == []
