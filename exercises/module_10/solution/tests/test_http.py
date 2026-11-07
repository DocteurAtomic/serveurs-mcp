"""The server over Streamable HTTP, started as the team starts it: pachatraining-mcp --http.

Each test talks to a real process on a free port of 127.0.0.1, with the SDK client or with
plain HTTP requests: the in-memory client goes through no transport, so it cannot tell
whether the server checks a Host header or seals a confirmation with a shared key.
"""

import os
import secrets
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

import httpx2
import pytest
from mcp import Client

from tools.wire_summary import summarize

ROOT = Path(__file__).resolve().parents[1]
REVISION = "2026-07-28"
META = {
    "io.modelcontextprotocol/protocolVersion": REVISION,
    "io.modelcontextprotocol/clientInfo": {"name": "test_http", "version": "1"},
    "io.modelcontextprotocol/clientCapabilities": {"elicitation": {"form": {}}},
}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def http_server(**env: str):
    """Start pachatraining-mcp --http on a free port, wait until it listens, stop it after."""
    port = free_port()
    process = subprocess.Popen(
        ["uv", "--directory", str(ROOT), "run", "--quiet", "pachatraining-mcp", "--http"],
        env={**os.environ, "PACHA_HTTP_PORT": str(port), **env},
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("pachatraining-mcp --http does not listen") from None
                time.sleep(0.1)
        yield port
    finally:
        process.terminate()
        process.wait(timeout=10)


def post(port: int, method: str, params: dict | None = None, name: str | None = None,
         **headers: str) -> httpx2.Response:
    """One modern request, with the headers the 2026-07-28 revision asks for."""
    sent = {"MCP-Protocol-Version": REVISION, "Mcp-Method": method,
            "Accept": "application/json, text/event-stream"}
    if name:
        sent["Mcp-Name"] = name
    sent.update({k.replace("_", "-"): v for k, v in headers.items()})
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": {**(params or {}), "_meta": META}}
    return httpx2.post(f"http://127.0.0.1:{port}/mcp", json=body, headers=sent, timeout=30)


@pytest.fixture(scope="module")
def port():
    with http_server() as p:
        yield p


@pytest.mark.anyio
async def test_tools_over_http(port: int):
    async with Client(f"http://127.0.0.1:{port}/mcp") as client:
        assert client.protocol_version == REVISION
        result = await client.call_tool("sessions_in_week", {"monday": "2026-11-16"})
    assert not result.is_error, result.content[0].text
    assert result.structured_content["count"] == 36


def test_only_the_names_of_this_machine(port: int):
    assert post(port, "server/discover", Host=f"localhost:{port}").status_code == 200
    refused = post(port, "server/discover", Host="evil.example")
    assert (refused.status_code, refused.text) == (421, "Invalid Host header")
    refused = post(port, "server/discover", Origin="http://evil.example")
    assert (refused.status_code, refused.text) == (403, "Invalid Origin header")


@pytest.mark.anyio
async def test_wire_log_over_http(port: int):
    """tools/wire_http.py between the client and the server, as in front of Claude Code."""
    proxy_port = free_port()
    proxy = subprocess.Popen(
        ["uv", "--directory", str(ROOT), "run", "--quiet", "python", "tools/wire_http.py",
         "test-http", str(proxy_port), str(port)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                socket.create_connection(("127.0.0.1", proxy_port), timeout=0.2).close()
                break
            except OSError:
                if proxy.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("tools/wire_http.py does not listen") from None
                time.sleep(0.1)
        async with Client(f"http://127.0.0.1:{proxy_port}/mcp") as client:
            result = await client.call_tool("sessions_in_week", {"monday": "2026-11-16"})
        assert result.structured_content["count"] == 36
    finally:
        proxy.terminate()
        proxy.wait(timeout=10)
    wire = summarize("test-http", ROOT / "logs")
    assert (wire.revision, wire.first_method, wire.tool_calls, wire.errors) == (
        REVISION, "server/discover", 1, 0)
    sessions = [line for line in (ROOT / "logs" / "wire-test-http.http.jsonl").read_text()
                .splitlines() if "mcp-session-id" in line]
    assert sessions == [], "a modern request got a session"


POSTPONE = {"name": "postpone_session",
            "arguments": {"session_id": 17712, "new_start_date": "2026-11-30",
                          "as_of": "2026-11-16"}}


def confirm_across_a_restart(**env: str) -> httpx2.Response:
    """Round 1 on one process, round 2 on another: the user declines, so nothing is written."""
    with http_server(**env) as first:
        question = post(first, "tools/call", POSTPONE, name="postpone_session").json()["result"]
    assert question["resultType"] == "input_required"
    answers = {key: {"action": "decline"} for key in question["inputRequests"]}
    retry = {**POSTPONE, "inputResponses": answers, "requestState": question["requestState"]}
    with http_server(**env) as second:
        return post(second, "tools/call", retry, name="postpone_session")


def test_confirmation_needs_a_shared_key():
    # An empty key is no key, whatever .env says: the SDK draws one per process.
    refused = confirm_across_a_restart(PACHA_REQUEST_STATE_KEY="")
    assert refused.status_code == 400
    assert refused.json()["error"]["message"] == "Invalid or expired requestState"
    answered = confirm_across_a_restart(PACHA_REQUEST_STATE_KEY=secrets.token_hex(32))
    assert answered.status_code == 200
    result = answered.json()["result"]["structuredContent"]
    assert result["postponed"] is False
    assert result["message"].startswith("The user declined")


def test_the_team_names():
    with http_server(PACHA_HTTP_HOSTS="mcp.pachadata.example") as p:
        assert post(p, "server/discover", Host="mcp.pachadata.example").status_code == 200
        assert post(p, "server/discover", Host=f"127.0.0.1:{p}").status_code == 200
        assert post(p, "server/discover", Host="evil.example").status_code == 421
