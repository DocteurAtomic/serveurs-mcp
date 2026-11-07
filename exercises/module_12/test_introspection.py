"""The check of the module 12 exercise: the server asks Keycloak about each token.

Run by check.sh, against the Keycloak of the lab (uv run python setup/keycloak.py). One server
is started for the whole run, `pachatraining-mcp --http` on a free port of 127.0.0.1, with
PACHA_OAUTH_VERIFY=introspection. The tokens come from Keycloak itself, by the password grant
of pacha-check, a confidential client of the realm kept for the checks: a real client such
as Claude Code signs in through the browser instead. Nothing is written to the database: the
writer's confirmation is never answered.
"""

import os
import socket
import subprocess
import time
from pathlib import Path

import httpx2
import pytest

ROOT = Path(__file__).resolve().parents[2]
REVISION = "2026-07-28"
META = {
    "io.modelcontextprotocol/protocolVersion": REVISION,
    "io.modelcontextprotocol/clientInfo": {"name": "check_module_12", "version": "1"},
    "io.modelcontextprotocol/clientCapabilities": {"elicitation": {"form": {}}},
}
POSTPONE = {"name": "postpone_session",
            "arguments": {"session_id": 17712, "new_start_date": "2026-11-30",
                          "as_of": "2026-11-16"}}


def dotenv() -> dict[str, str]:
    """.env as the server reads it: the real environment wins."""
    values = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return {**values, **{k: v for k, v in os.environ.items() if k in values}}


ENV = dotenv()
ISSUER = (ENV.get("PACHA_OAUTH_ISSUER")
          or f"http://127.0.0.1:{ENV.get('KEYCLOAK_PORT') or 8080}/realms/pachadata")
# The URL the realm writes in the audience of the tokens (compose.yaml, PACHA_MCP_URL).
MCP_URL = ENV.get("PACHA_MCP_URL") or "http://127.0.0.1:8000/mcp"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def keycloak(path: str, **form: str) -> dict:
    __tracebackhide__ = True  # a failure shows the test, not the secrets of this frame
    answer = httpx2.post(f"{ISSUER}/protocol/openid-connect/{path}", data=form, timeout=30)
    assert answer.status_code in (200, 204), f"Keycloak {path}: {answer.status_code}"
    return answer.json() if answer.content else {}


def tokens(user: str, scope: str) -> dict:
    """An access token and its refresh token for a user of the realm, by pacha-check."""
    __tracebackhide__ = True
    return keycloak("token", grant_type="password", client_id="pacha-check",
                    client_secret=ENV["KEYCLOAK_CHECK_SECRET"], username=user,
                    password=ENV[f"KEYCLOAK_{user.upper()}_PASSWORD"], scope=scope)


@pytest.fixture(scope="module")
def realm():
    """Stop the run, and say why, when Keycloak or its secrets are missing."""
    missing = [k for k in ("KEYCLOAK_CHECK_SECRET", "KEYCLOAK_MCP_SECRET",
                           "KEYCLOAK_ALICE_PASSWORD", "KEYCLOAK_CAROL_PASSWORD") if not ENV.get(k)]
    if missing:
        pytest.exit(f"{', '.join(missing)} missing in .env: run uv run python setup/keycloak.py",
                    returncode=3)
    try:
        httpx2.get(f"{ISSUER}/.well-known/openid-configuration", timeout=5).raise_for_status()
    except httpx2.HTTPError as exc:
        pytest.exit(f"Keycloak does not answer at {ISSUER} ({type(exc).__name__}): "
                    "run uv run python setup/keycloak.py", returncode=3)
    return {"alice": tokens("alice", "pacha:read pacha:write"),
            "carol": tokens("carol", "pacha:read pacha:write"),
            "other": tokens("alice", "other:api")}


def server_env(port: int, **extra: str) -> dict:
    return {**os.environ, "PACHA_HTTP_PORT": str(port), "PACHA_OAUTH_ISSUER": ISSUER,
            "PACHA_OAUTH_VERIFY": "introspection", "PACHA_MCP_URL": MCP_URL, **extra}


@pytest.fixture(scope="module")
def server(realm, tmp_path_factory):
    """The server, and the file its stderr goes to."""
    port = free_port()
    log = tmp_path_factory.mktemp("server") / "stderr.log"
    with open(log, "w") as err:
        process = subprocess.Popen(
            ["uv", "--directory", str(ROOT), "run", "--quiet", "pachatraining-mcp", "--http"],
            env=server_env(port), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=err,
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
    __tracebackhide__ = True
    headers = {"MCP-Protocol-Version": REVISION, "Mcp-Method": method,
               "Accept": "application/json, text/event-stream"}
    if name:
        headers["Mcp-Name"] = name
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = {"jsonrpc": "2.0", "id": 1, "method": method,
            "params": {**(params or {}), "_meta": META}}
    return httpx2.post(f"http://127.0.0.1:{port}/mcp", json=body, headers=headers, timeout=30)


def call(port: int, tool: dict, token: str) -> dict:
    __tracebackhide__ = True
    response = post(port, "tools/call", tool, token, name=tool["name"])
    assert response.status_code == 200, f"{tool['name']} got {response.status_code}"
    return response.json()["result"]


def test_the_door_opens_to_the_tokens_of_the_realm_only(realm, server):
    port, _ = server
    assert post(port, "server/discover").status_code == 401
    # The metadata is read where this server listens; the 401 names it at MCP_URL, the
    # address the clients use, which may be another one.
    document = httpx2.get(f"http://127.0.0.1:{port}/.well-known/oauth-protected-resource/mcp",
                          timeout=30).json()
    assert [s.rstrip("/") for s in document["authorization_servers"]] == [ISSUER]
    for who in ("alice", "carol"):
        status = post(port, "server/discover", token=realm[who]["access_token"]).status_code
        assert status == 200, f"the token of {who} got {status}"
    status = post(port, "server/discover", token=realm["other"]["access_token"]).status_code
    assert status == 401, "a token issued for another service was served"


def test_carol_reads_and_alice_is_asked_to_confirm(realm, server):
    port, _ = server
    refused = call(port, POSTPONE, realm["carol"]["access_token"])
    assert refused.get("resultType") != "input_required", "carol was asked to confirm"
    assert refused.get("isError") is True, "carol was not refused"
    asked = call(port, POSTPONE, realm["alice"]["access_token"])
    assert asked.get("resultType") == "input_required", "alice was not asked to confirm"


def test_a_token_of_a_closed_session_is_refused_at_once(server):
    """The difference with the keys: a signed token whose session is over is still valid
    until its expiry for a server that only checks the signature."""
    port, _ = server
    alice = tokens("alice", "pacha:read pacha:write")
    assert post(port, "server/discover", token=alice["access_token"]).status_code == 200
    # Alice signs out: Keycloak ends her session, the access token itself is unchanged.
    keycloak("logout", client_id="pacha-check", client_secret=ENV["KEYCLOAK_CHECK_SECRET"],
             refresh_token=alice["refresh_token"])
    status = post(port, "server/discover", token=alice["access_token"]).status_code
    assert status == 401, f"the token of a closed session got {status}"


def test_without_the_client_secret_it_does_not_start(realm):
    process = subprocess.Popen(
        ["uv", "--directory", str(ROOT), "run", "--quiet", "pachatraining-mcp", "--http"],
        env=server_env(free_port(), KEYCLOAK_MCP_SECRET=""),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    try:
        _, stderr = process.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        # Terminated, not killed: uv passes the signal on to the server it started.
        process.terminate()
        process.communicate(timeout=10)
        pytest.fail("the server started without the secret of pacha-mcp")
    assert process.returncode == 2, f"exit code {process.returncode}"
    assert "KEYCLOAK_MCP_SECRET" in stderr


def test_the_log_names_the_users_never_their_tokens(realm, server):
    port, log = server
    for who in ("alice", "carol"):
        post(port, "server/discover", token=realm[who]["access_token"])
    time.sleep(0.5)
    text = log.read_text()
    assert "from alice" in text and "from carol" in text, "the log does not say who called"
    # The log handler wraps long lines: no piece of 12 characters of a token may appear.
    for who in ("alice", "carol", "other"):
        token = realm[who]["access_token"]
        assert not any(token[i:i + 12] in text for i in range(len(token) - 11)), \
            "a token, or a piece of one, is in the server's log"
