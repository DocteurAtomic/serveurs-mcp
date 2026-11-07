"""Tokens of an authorization server, checked by the server with the issuer's public keys.

No Keycloak here: the tests play the authorization server. They draw an RSA key for the run,
publish its public half (a JWKS) on a free port of 127.0.0.1, at the path where Keycloak
publishes the keys of a realm, and sign the tokens themselves, as Keycloak would: issuer,
audience, expiry, scopes, user name. The server is started with PACHA_OAUTH_ISSUER pointing
there, and only what it does with a token is tested. That the real Keycloak of the lab issues
such tokens is the business of the exercise of module 12, which talks to it.
"""

import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from tests.http_server import TOKENS, free_port, http_server, post

POSTPONE = {"name": "postpone_session",
            "arguments": {"session_id": 17712, "new_start_date": "2026-11-30",
                          "as_of": "2026-11-16"}}


def new_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class Issuer:
    """A stand-in for a Keycloak realm: one signing key, its JWKS over HTTP, and tokens."""

    def __init__(self):
        self.key, self.kid = new_key(), secrets.token_hex(8)
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}/realms/test"
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        keys = json.dumps({"keys": [{**jwk, "kid": self.kid, "use": "sig", "alg": "RS256"}]})

        class Keys(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/realms/test/protocol/openid-connect/certs":
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(keys.encode())

            def log_message(self, *args):
                pass

        self.http = ThreadingHTTPServer(("127.0.0.1", self.port), Keys)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def token(self, user: str, scope: str, audience: str, *, key=None, issuer: str | None = None,
              lifetime: int = 300) -> str:
        now = int(time.time())
        claims = {"iss": issuer or self.url, "sub": f"id-{user}", "aud": [audience, "account"],
                  "azp": "https://claude.ai/oauth/claude-code-client-metadata",
                  "preferred_username": user, "scope": scope,
                  "iat": now, "exp": now + lifetime}
        return jwt.encode(claims, key or self.key, algorithm="RS256", headers={"kid": self.kid})


@pytest.fixture(scope="module")
def issuer():
    realm = Issuer()
    yield realm
    realm.http.shutdown()


@pytest.fixture(scope="module")
def server(issuer, tmp_path_factory):
    """The server trusting the issuer, its URL, and the file its stderr goes to."""
    log = tmp_path_factory.mktemp("oauth") / "stderr.log"
    with http_server(stderr=log, PACHA_OAUTH_ISSUER=issuer.url) as port:
        yield port, f"http://127.0.0.1:{port}/mcp", log


def test_the_metadata_sends_clients_to_the_issuer(issuer, server):
    port, url, _ = server
    refused = post(port, "server/discover", token=None)
    assert refused.status_code == 401
    metadata = f"http://127.0.0.1:{port}/.well-known/oauth-protected-resource/mcp"
    assert f'resource_metadata="{metadata}"' in refused.headers["www-authenticate"]
    document = httpx2.get(metadata, timeout=30).json()
    assert document["resource"] == url
    assert [s.rstrip("/") for s in document["authorization_servers"]] == [issuer.url]
    # With an authorization server, the team tokens of module 11 no longer open the door.
    assert post(port, "server/discover", token=TOKENS["alice"]).status_code == 401


def test_a_token_not_for_this_server_gets_401(issuer, server):
    port, url, _ = server
    refused = {
        "another audience": issuer.token("alice", "pacha:read", "http://127.0.0.1:8001/other"),
        "another key": issuer.token("alice", "pacha:read", url, key=new_key()),
        "another issuer": issuer.token("alice", "pacha:read", url,
                                       issuer=f"http://127.0.0.1:{issuer.port}/realms/master"),
        "expired": issuer.token("alice", "pacha:read", url, lifetime=-60),
        "not a JWT": secrets.token_urlsafe(32),
    }
    for case, token in refused.items():
        assert post(port, "server/discover", token=token).status_code == 401, case
    assert post(port, "server/discover",
                token=issuer.token("alice", "pacha:read", url)).status_code == 200


def test_a_token_without_pacha_read_gets_403(issuer, server):
    port, url, _ = server
    answer = post(port, "server/discover", token=issuer.token("alice", "profile", url))
    assert answer.status_code == 403
    assert answer.json()["error"] == "insufficient_scope"


def test_the_scope_in_the_token_decides_who_writes(issuer, server):
    port, url, _ = server
    reader = issuer.token("carol", "profile pacha:read", url)
    writer = issuer.token("alice", "profile pacha:read pacha:write", url)
    refused = post(port, "tools/call", POSTPONE, name="postpone_session", token=reader)
    asked = post(port, "tools/call", POSTPONE, name="postpone_session", token=writer)
    refused, asked = refused.json()["result"], asked.json()["result"]
    # Refused before the confirmation: no question for a change that cannot be made.
    assert refused.get("resultType") != "input_required" and refused["isError"] is True
    assert "carol may only read" in refused["content"][0]["text"]
    assert asked["resultType"] == "input_required"


def test_the_log_names_the_user_never_the_token(issuer, server):
    port, url, log = server
    tokens = [issuer.token("alice", "pacha:read pacha:write", url),
              issuer.token("carol", "pacha:read", "http://127.0.0.1:8001/other")]
    for token in tokens:
        post(port, "server/discover", token=token)
    time.sleep(0.5)
    text = log.read_text()
    # The log handler wraps long lines at 80 columns: short phrases only.
    assert "HTTP request from alice" in text
    assert "InvalidAudienceError" in text
    # A token cut in two by the wrapping would escape a plain search: no piece of 12
    # characters of a token may appear.
    for token in tokens:
        assert not any(token[i:i + 12] in text for i in range(len(token) - 11))
