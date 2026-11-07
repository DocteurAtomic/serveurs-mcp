"""Checks of the module 7 exercise: cancel_enrollment, after the user confirms it.

Run by check.sh, which recreates PachadataTraining_m07 first: the first test cancels
enrollment 150706 for good.
"""

import re
from datetime import date
from pathlib import Path

import pytest
from mcp import Client
from mcp.types import ElicitResult

from pachatraining_mcp.server import connect, mcp, write_database

SERVER = Path(__file__).resolve().parents[2] / "src" / "pachatraining_mcp" / "server.py"
ARGS = {"reason": "Trainee moved to another session", "as_of": "2026-11-16"}

pytestmark = pytest.mark.anyio


def enrollment(enrollment_id: int):
    """CancellationDate in Mcp.EnrollmentSummary, and the reason in Mcp.EnrollmentCancellation,
    read in the database the tool writes to."""
    with connect(write_database()) as cn:
        cur = cn.cursor()
        cur.execute("SELECT CancellationDate FROM Mcp.EnrollmentSummary WHERE EnrollmentId = ?",
                    (enrollment_id,))
        cancelled = cur.fetchone()[0]
        cur.execute("SELECT Reason FROM Mcp.EnrollmentCancellation WHERE EnrollmentId = ?",
                    (enrollment_id,))
        row = cur.fetchone()
    return cancelled, row[0] if row else None


def user(action: str, content: dict | None = None):
    questions = []

    async def answer(context, params):
        questions.append(params.message)
        return ElicitResult(action=action, content=content)

    return answer, questions


async def test_cancelled_after_accept():
    assert enrollment(150706) == (None, None), "recreate the copy: ./setup/reset-copy.sh m07"
    answer, questions = user("accept", {"confirm": True})
    async with Client(mcp, elicitation_callback=answer) as c:
        result = await c.call_tool("cancel_enrollment", {"enrollment_id": 150706, **ARGS})
    assert not result.is_error, result.content[0].text
    assert result.structured_content["cancelled"] is True
    assert len(questions) == 1
    assert "Alicia Chanteloup" in questions[0] and "17709" in questions[0], questions[0]
    assert enrollment(150706) == (date(2026, 11, 16), ARGS["reason"])


@pytest.mark.parametrize("action", ["decline", "cancel"])
async def test_nothing_written_without_a_yes(action):
    answer, questions = user(action)
    async with Client(mcp, elicitation_callback=answer) as c:
        result = await c.call_tool("cancel_enrollment", {"enrollment_id": 150707, **ARGS})
    assert not result.is_error, result.content[0].text
    assert result.structured_content["cancelled"] is False
    assert len(questions) == 1
    assert enrollment(150707) == (None, None)


async def test_already_cancelled_without_asking():
    answer, questions = user("accept", {"confirm": True})
    async with Client(mcp, elicitation_callback=answer) as c:
        result = await c.call_tool("cancel_enrollment", {"enrollment_id": 150753, **ARGS})
    assert result.is_error
    assert "already cancelled" in result.content[0].text
    assert questions == [], "the user was asked about an enrollment already cancelled"


async def test_the_tool_says_it_writes_and_writes_through_the_procedure():
    async with Client(mcp) as c:
        tool = next((t for t in (await c.list_tools()).tools if t.name == "cancel_enrollment"), None)
    assert tool is not None, "the server has no cancel_enrollment tool"
    assert tool.annotations is not None and tool.annotations.read_only_hint is False
    assert set(tool.input_schema["properties"]) == {"enrollment_id", "reason", "as_of"}
    statements = re.findall(r"\b(UPDATE|DELETE|INSERT|MERGE)\b", SERVER.read_text())
    assert statements == [], f"the server writes SQL of its own: {statements}"
