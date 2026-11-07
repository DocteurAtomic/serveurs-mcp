"""The server listening on another address than 127.0.0.1, as it does in its container.

In the image, PACHA_HTTP_LISTEN=0.0.0.0: the server must listen on every interface of the
container for the published port to reach it. The SDK only turns its Host check on by itself
for 127.0.0.1 and localhost, so on any other address every Host would pass. The test listens
on 127.0.0.2, another address of the loopback, which the SDK treats like 0.0.0.0 and which
stays on this machine.
"""

import os
import socket
import subprocess
import time

import httpx2

from tests.http_server import META, PACHA_TOKENS, REVISION, ROOT, TOKENS, free_port

ADDRESS = "127.0.0.2"


def discover(port: int, host: str) -> httpx2.Response:
    """server/discover sent to 127.0.0.2, with the Host header a client would send."""
    headers = {"MCP-Protocol-Version": REVISION, "Mcp-Method": "server/discover",
               "Accept": "application/json, text/event-stream", "Host": host,
               "Authorization": f"Bearer {TOKENS['alice']}"}
    body = {"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {"_meta": META}}
    return httpx2.post(f"http://{ADDRESS}:{port}/mcp", json=body, headers=headers, timeout=30)


def test_host_check_off_the_loopback_address():
    port = free_port()
    process = subprocess.Popen(
        ["uv", "--directory", str(ROOT), "run", "--quiet", "pachatraining-mcp", "--http"],
        env={**os.environ, "PACHA_HTTP_LISTEN": ADDRESS, "PACHA_HTTP_PORT": str(port),
             "PACHA_TOKENS": PACHA_TOKENS, "PACHA_OAUTH_ISSUER": "", "PACHA_MCP_URL": "",
             "PACHA_HTTP_HOSTS": ""},
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                socket.create_connection((ADDRESS, port), timeout=0.2).close()
                break
            except OSError:
                assert process.poll() is None and time.monotonic() < deadline, (
                    f"pachatraining-mcp --http does not listen on {ADDRESS}:{port}")
                time.sleep(0.1)
        # A published port: the client names 127.0.0.1 and the port of the host.
        assert discover(port, "127.0.0.1:18000").status_code == 200
        refused = discover(port, "evil.example")
        assert (refused.status_code, refused.text) == (421, "Invalid Host header")
    finally:
        process.terminate()
        process.wait(timeout=10)
