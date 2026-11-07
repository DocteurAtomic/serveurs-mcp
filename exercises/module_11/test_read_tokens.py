"""The check of the module 11 exercise: a token that reads, and a token that also writes.

Run by check.sh. One server is started for the whole run, `pachatraining-mcp --http` on a
free port of 127.0.0.1, with two colleagues whose names and tokens are drawn at random: a
writer in PACHA_TOKENS, a reader in PACHA_READ_TOKENS. Everything goes over HTTP: the
in-memory client sends no Authorization header, so over it the server knows no caller.
Nothing is written to the database: the writer declines the confirmation.
"""

import os
import secrets
import socket
import subprocess
import time
from pathlib import Path

import httpx2
import pytest

ROOT = Path(__file__).resolve().parents[2]
REVISION = "2026-07-28"
WRITER = (f"writer-{secrets.token_hex(3)}", secrets.token_urlsafe(32))
READER = (f"reader-{secrets.token_hex(3)}", secrets.token_urlsafe(32))
META = {
    "io.modelcontextprotocol/protocolVersion": REVISION,
    "io.modelcontextprotocol/clientInfo": {"name": "check_module_11", "version": "1"},
    "io.modelcontextprotocol/clientCapabilities": {"elicitation": {"form": {}}},
}
TOOLS = {"sessions_in_week", "session_detail", "trainer_load", "unpaid_invoices",
         "sessions_to_watch", "cancelled_enrollments", "postpone_session", "cancel_enrollment"}
POSTPONE = {"name": "postpone_session",
            "arguments": {"session_id": 17712, "new_start_date": "2026-11-30",
                          "as_of": "2026-11-16"}}
CANCEL = {"name": "cancel_enrollment",
          "arguments": {"enrollment_id": 150707, "reason": "Trainee moved to another session",
                        "as_of": "2026-11-16"}}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """The server, and the file its stderr goes to."""
    port = free_port()
    log = tmp_path_factory.mktemp("server") / "stderr.log"
    env = {**os.environ, "PACHA_HTTP_PORT": str(port),
           "PACHA_TOKENS": f"{WRITER[0]}:{WRITER[1]}",
           "PACHA_READ_TOKENS": f"{READER[0]}:{READER[1]}"}
    with open(log, "w") as err:
        process = subprocess.Popen(
            ["uv", "--directory", str(ROOT), "run", "--quiet", "pachatraining-mcp", "--http"],
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                    break
                except OSError:
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError(
                            f"pachatraining-mcp --http does not listen on 127.0.0.1:{port}"
                        ) from None
                    time.sleep(0.1)
            yield port, log
        finally:
            process.terminate()
            process.wait(timeout=10)


def post(port: int, method: str, params: dict | None = None, token: str | None = None,
         name: str | None = None) -> httpx2.Response:
    __tracebackhide__ = True  # a failure shows the test, not the token in this frame
    headers = {"MCP-Protocol-Version": REVISION, "Mcp-Method": method,
               "Accept": "application/json, text/event-stream"}
    if name:
        headers["Mcp-Name"] = name
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = {"jsonrpc": "2.0", "id": 1, "method": method,
            "params": {**(params or {}), "_meta": META}}
    return httpx2.post(f"http://127.0.0.1:{port}/mcp", json=body, headers=headers, timeout=30)


def result(port: int, method: str, params: dict, token: str, name: str | None = None) -> dict:
    """The result of one request that must be served: a refusal at the door fails here."""
    __tracebackhide__ = True
    response = post(port, method, params, token, name=name)
    status, text = response.status_code, response.text[:300]
    assert status == 200, f"{method} got {status}: {text}"
    return response.json()["result"]


def call(port: int, tool: dict, token: str) -> dict:
    return result(port, "tools/call", tool, token, name=tool["name"])


def test_both_tokens_open_the_door_and_only_them(server):
    port, _ = server
    for token in (None, secrets.token_urlsafe(32)):
        status = post(port, "server/discover", token=token).status_code
        assert status == 401, "a request without a team token was served"
    for who, token in (WRITER, READER):
        status = post(port, "server/discover", token=token).status_code
        assert status == 200, f"the token of {who} got {status}"


def test_the_reader_reads_and_may_not_write(server):
    port, _ = server
    listed = result(port, "tools/list", {}, READER[1])["tools"]
    assert TOOLS <= {tool["name"] for tool in listed}
    week = call(port, {"name": "sessions_in_week", "arguments": {"monday": "2026-11-16"}},
                READER[1])
    assert week["structuredContent"]["count"] == 36
    for tool in (POSTPONE, CANCEL):
        answer = call(port, tool, READER[1])
        # Refused before the confirmation: no question for a change that cannot be made.
        assert answer.get("resultType") != "input_required", f"{tool['name']} asked the reader"
        assert answer.get("isError") is True, f"{tool['name']} did not refuse the reader"
        assert "Unknown tool" not in answer["content"][0]["text"]


def test_the_writer_is_asked_to_confirm(server):
    port, _ = server
    question = call(port, POSTPONE, WRITER[1])
    assert question["resultType"] == "input_required"
    answers = {key: {"action": "decline"} for key in question["inputRequests"]}
    retry = {**POSTPONE, "inputResponses": answers, "requestState": question["requestState"]}
    answer = call(port, retry, WRITER[1])
    assert answer["structuredContent"]["postponed"] is False


def test_the_log_names_the_colleagues_never_their_tokens(server):
    port, log = server
    post(port, "server/discover", token=READER[1])
    post(port, "server/discover", token=WRITER[1])
    time.sleep(0.5)
    text = log.read_text()
    named = READER[0] in text and WRITER[0] in text
    assert named, "the log does not say who called"
    # The log handler wraps long lines: no piece of 12 characters of a token may appear.
    for _, token in (WRITER, READER):
        assert not any(token[i:i + 12] in text for i in range(len(token) - 11)), \
            "a token, or a piece of one, is in the server's log"
