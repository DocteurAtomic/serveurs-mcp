"""Who calls the server: a team token over HTTP, nobody over stdio and in memory.

Over HTTP the SDK asks TeamTokens about the bearer token of every request, and answers 401
before any JSON-RPC is read when the token is missing or unknown. Over stdio and in memory
there is no Authorization header at all: get_access_token() is None, and the tools that
write refuse before anything is read or asked.
"""

import os
import secrets
import subprocess
from datetime import date

import httpx2
import pytest
from mcp import Client
from mcp.types import ElicitResult

from pachatraining_mcp.server import connect, mcp, write_database
from tests.http_server import ROOT, TOKENS, http_server, post

POSTPONE = {"session_id": 17712, "new_start_date": "2026-11-30", "as_of": "2026-11-16"}
CANCEL = {"enrollment_id": 150707, "reason": "Trainee moved to another session",
          "as_of": "2026-11-16"}


def test_a_known_token_or_401():
    with http_server() as port:
        for token in (None, "not-a-team-token"):
            refused = post(port, "server/discover", token=token)
            assert refused.status_code == 401
            assert refused.json()["error"] == "invalid_token"
            metadata = f"http://127.0.0.1:{port}/.well-known/oauth-protected-resource/mcp"
            assert f'resource_metadata="{metadata}"' in refused.headers["www-authenticate"]
        assert post(port, "server/discover", token=TOKENS["bob"]).status_code == 200
        # RFC 9728: the resource the tokens are for, the URL clients connect to.
        document = httpx2.get(metadata, timeout=30).json()
    assert document["resource"] == f"http://127.0.0.1:{port}/mcp"


def test_the_log_names_the_caller_never_the_token(tmp_path):
    log = tmp_path / "server.log"
    with http_server(stderr=log) as port:
        post(port, "server/discover", token=TOKENS["alice"])
        post(port, "server/discover", token=TOKENS["bob"])
        post(port, "server/discover", token="not-a-team-token")
    text = log.read_text()
    assert "HTTP request from alice" in text and "HTTP request from bob" in text
    assert "unknown token" in text
    # The log handler wraps long lines: a token cut in two would escape a plain search, so
    # no piece of 12 characters of a token may appear.
    for token in (*TOKENS.values(), "not-a-team-token"):
        assert not any(token[i:i + 12] in text for i in range(len(token) - 11))


@pytest.mark.anyio
async def test_no_token_no_write():
    """In memory, as over stdio, the server knows no caller: both tools refuse, and the user
    is never asked to confirm a change that would be refused anyway."""
    questions = []

    async def answer(context, params):
        questions.append(params.message)
        return ElicitResult(action="accept", content={"confirm": True})

    async with Client(mcp, elicitation_callback=answer) as c:
        postponed = await c.call_tool("postpone_session", POSTPONE)
        cancelled = await c.call_tool("cancel_enrollment", CANCEL)
    for result in (postponed, cancelled):
        assert result.is_error
        assert "only for a caller with a token" in result.content[0].text
    assert questions == []
    with connect(write_database()) as cn:
        cur = cn.cursor()
        cur.execute("SELECT StartDate FROM Mcp.SessionDetail WHERE SessionId = 17712")
        assert cur.fetchone()[0] == date(2026, 11, 16)


def test_http_without_tokens_does_not_start():
    done = subprocess.run(
        ["uv", "--directory", str(ROOT), "run", "--quiet", "pachatraining-mcp", "--http"],
        env={**os.environ, "PACHA_TOKENS": "", "PACHA_OAUTH_ISSUER": "", "PACHA_HTTP_PORT": "1"},
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 2
    assert "PACHA_TOKENS is empty" in done.stderr


def test_a_confirmation_belongs_to_its_caller():
    """The SDK seals the requestState with the caller of round 1: bob cannot answer the
    question alice was asked."""
    call = {"name": "postpone_session", "arguments": POSTPONE}
    with http_server() as port:
        question = post(port, "tools/call", call, name="postpone_session").json()["result"]
        assert question["resultType"] == "input_required"
        answers = {key: {"action": "decline"} for key in question["inputRequests"]}
        retry = {**call, "inputResponses": answers, "requestState": question["requestState"]}
        by_bob = post(port, "tools/call", retry, name="postpone_session", token=TOKENS["bob"])
        by_alice = post(port, "tools/call", retry, name="postpone_session")
    assert by_bob.status_code == 400
    assert by_bob.json()["error"]["message"] == "Invalid or expired requestState"
    assert by_alice.json()["result"]["structuredContent"]["message"].startswith(
        "The user declined")


def test_a_reader_may_read_and_not_write():
    """A token of PACHA_READ_TOKENS: the tools that read answer it, the tools that write
    refuse it before the confirmation."""
    reader = secrets.token_urlsafe(32)
    with http_server(PACHA_READ_TOKENS=f"carol:{reader}") as port:
        week = post(port, "tools/call", {"name": "sessions_in_week",
                                         "arguments": {"monday": "2026-11-16"}},
                    name="sessions_in_week", token=reader).json()["result"]
        refused = post(port, "tools/call", {"name": "postpone_session", "arguments": POSTPONE},
                       name="postpone_session", token=reader).json()["result"]
        asked = post(port, "tools/call", {"name": "postpone_session", "arguments": POSTPONE},
                     name="postpone_session").json()["result"]
    assert week["structuredContent"]["count"] == 36
    assert refused.get("resultType") != "input_required" and refused["isError"] is True
    assert "carol may only read" in refused["content"][0]["text"]
    assert asked["resultType"] == "input_required"
