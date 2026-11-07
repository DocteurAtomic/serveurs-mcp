"""What the tests over HTTP share: a real `pachatraining-mcp --http`, team tokens, a client.

The in-memory client goes through no transport, so it sends no Authorization header: over it
the server sees no caller at all. The tests that need a caller, the tools that write among
them, talk to a real process on a free port of 127.0.0.1, with tokens drawn for the run and
passed through the environment, never written to a file.
"""

import os
import secrets
import socket
import subprocess
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
REVISION = "2026-07-28"
META = {
    "io.modelcontextprotocol/protocolVersion": REVISION,
    "io.modelcontextprotocol/clientInfo": {"name": "tests", "version": "1"},
    "io.modelcontextprotocol/clientCapabilities": {"elicitation": {"form": {}}},
}
# Drawn once per run: the tokens of two colleagues.
TOKENS = {"alice": secrets.token_urlsafe(32), "bob": secrets.token_urlsafe(32)}
PACHA_TOKENS = ",".join(f"{name}:{token}" for name, token in TOKENS.items())


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(port: int, process: subprocess.Popen, what: str) -> None:
    deadline = time.monotonic() + 30
    while True:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            return
        except OSError:
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError(f"{what} does not listen on 127.0.0.1:{port}") from None
            time.sleep(0.1)


@contextmanager
def http_server(stderr: Path | None = None, **env: str):
    """Start pachatraining-mcp --http with the tokens of TOKENS on a free port, wait until it
    listens, stop it after. With stderr, the server's log goes to that file."""
    port = free_port()
    log = open(stderr, "w") if stderr else subprocess.DEVNULL
    process = subprocess.Popen(
        ["uv", "--directory", str(ROOT), "run", "--quiet", "pachatraining-mcp", "--http"],
        env={**os.environ, "PACHA_HTTP_PORT": str(port), "PACHA_TOKENS": PACHA_TOKENS, **env},
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log,
    )
    try:
        wait_for(port, process, "pachatraining-mcp --http")
        yield port
    finally:
        process.terminate()
        process.wait(timeout=10)
        if stderr:
            log.close()


def post(port: int, method: str, params: dict | None = None, name: str | None = None,
         token: str | None = TOKENS["alice"], **headers: str) -> httpx2.Response:
    """One modern request, with the headers the 2026-07-28 revision asks for, and the token
    of alice unless another one, or None, is given."""
    sent = {"MCP-Protocol-Version": REVISION, "Mcp-Method": method,
            "Accept": "application/json, text/event-stream"}
    if name:
        sent["Mcp-Name"] = name
    if token:
        sent["Authorization"] = f"Bearer {token}"
    sent.update({k.replace("_", "-"): v for k, v in headers.items()})
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": {**(params or {}), "_meta": META}}
    return httpx2.post(f"http://127.0.0.1:{port}/mcp", json=body, headers=sent, timeout=30)


@asynccontextmanager
async def http_client(port: int, token: str | None = TOKENS["alice"], **client_options):
    """The SDK client over HTTP, sending the token: the header lives on the httpx2 client
    given to the transport (streamable_http_client takes no headers= of its own)."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx2.AsyncClient(headers=headers,
                                  timeout=httpx2.Timeout(30.0, read=300.0)) as http:
        transport = streamable_http_client(f"http://127.0.0.1:{port}/mcp", http_client=http)
        async with Client(transport, **client_options) as client:
            yield client
