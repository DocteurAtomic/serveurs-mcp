"""The check of the module 10 exercise: the HTTP server accepts the team's names, and only them.

Run by check.sh. Each test starts `pachatraining-mcp --http` itself, on a free port of
127.0.0.1, and talks to it over HTTP: with the SDK client, or with plain requests whose Host
and Origin headers are the ones a proxy or a browser would send. The team's name is drawn
at random for each run, so that only a server that reads PACHA_HTTP_HOSTS accepts it.
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

ROOT = Path(__file__).resolve().parents[2]
REVISION = "2026-07-28"
TEAM = f"mcp-{secrets.token_hex(3)}.pachadata.example"
META = {
    "io.modelcontextprotocol/protocolVersion": REVISION,
    "io.modelcontextprotocol/clientInfo": {"name": "check_module_10", "version": "1"},
    "io.modelcontextprotocol/clientCapabilities": {},
}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def http_server(hosts: str):
    port = free_port()
    process = subprocess.Popen(
        ["uv", "--directory", str(ROOT), "run", "--quiet", "pachatraining-mcp", "--http"],
        env={**os.environ, "PACHA_HTTP_PORT": str(port), "PACHA_HTTP_HOSTS": hosts},
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
                    raise RuntimeError("pachatraining-mcp --http does not listen on "
                                       f"127.0.0.1:{port} (PACHA_HTTP_PORT)") from None
                time.sleep(0.1)
        yield port
    finally:
        process.terminate()
        process.wait(timeout=10)


def discover(port: int, **headers: str) -> int:
    """The status of a modern server/discover sent to 127.0.0.1, with the given headers."""
    sent = {"MCP-Protocol-Version": REVISION, "Mcp-Method": "server/discover",
            "Accept": "application/json, text/event-stream", **headers}
    body = {"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {"_meta": META}}
    return httpx2.post(f"http://127.0.0.1:{port}/mcp", json=body, headers=sent,
                       timeout=30).status_code


@pytest.fixture(scope="module")
def port():
    with http_server(TEAM) as p:
        yield p


def test_the_team_name_is_accepted(port: int):
    assert discover(port, Host=f"{TEAM}:{port}") == 200, f"Host: {TEAM}:{port}"
    assert discover(port, Host=TEAM) == 200, f"Host: {TEAM} (a proxy on port 443 sends no port)"
    assert discover(port, Host=TEAM, Origin=f"https://{TEAM}") == 200, f"Origin: https://{TEAM}"


@pytest.mark.anyio
async def test_the_names_of_this_machine_still_work(port: int):
    assert discover(port, Host=f"localhost:{port}") == 200, f"Host: localhost:{port}"
    async with Client(f"http://127.0.0.1:{port}/mcp") as client:
        assert client.protocol_version == REVISION
        result = await client.call_tool("sessions_in_week", {"monday": "2026-11-16"})
    assert not result.is_error, result.content[0].text
    assert result.structured_content["count"] == 36


def test_other_names_are_refused(port: int):
    assert discover(port, Host="evil.example") == 421, "Host: evil.example"
    assert discover(port, Host=f"{TEAM}.evil.example:{port}") == 421, f"Host: {TEAM}.evil.example"
    assert discover(port, Host=f"127.0.0.1:{port}", Origin="http://evil.example") == 403, \
        "Origin: http://evil.example"


def test_without_the_variable_only_this_machine():
    with http_server("") as p:
        assert discover(p, Host=f"127.0.0.1:{p}") == 200, f"Host: 127.0.0.1:{p}"
        assert discover(p, Host=f"{TEAM}:{p}") == 421, f"Host: {TEAM}:{p}, PACHA_HTTP_HOSTS empty"
        assert discover(p, Host="evil.example") == 421, "Host: evil.example, PACHA_HTTP_HOSTS empty"
