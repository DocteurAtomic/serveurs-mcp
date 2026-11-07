"""Start Keycloak, the authorization server of the lab, with the pachadata realm.

    uv run python setup/keycloak.py
    With Podman: COMPOSE="podman compose" uv run python setup/keycloak.py

First fills the Keycloak secrets of .env that are missing or empty with random values: the
password of Keycloak's admin, those of the two accounts of the realm (alice writes, carol
reads), and the secrets of its two confidential clients. They go to .env only, never to a
command line or a committed file; compose hands them to the container, and Keycloak writes
them into the realm it imports. Then starts the keycloak service of compose.yaml (profile
oauth) and waits until the realm answers. Running it again is safe: secrets already drawn
are kept, and so is a running container.

The realm is imported only when the container is created. After a change of the realm file
or of a secret, remove the container (docker rm -f mcpcourse-keycloak) and run this again.
"""

import os
import secrets
import shlex
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
SECRETS = {
    "KEYCLOAK_ADMIN_PASSWORD": "admin of Keycloak (console on http://127.0.0.1:8080/admin)",
    "KEYCLOAK_ALICE_PASSWORD": "alice, who may write (role pacha-writer)",
    "KEYCLOAK_CAROL_PASSWORD": "carol, who only reads",
    "KEYCLOAK_MCP_SECRET": "client pacha-mcp, the MCP server when it introspects a token",
    "KEYCLOAK_CHECK_SECRET": "client pacha-check, the checks that ask for tokens themselves",
}


def fill_secrets() -> tuple[list[str], dict[str, str]]:
    """Draw the secrets .env lacks; return their names, and the values of .env."""
    if not ENV.exists():
        sys.exit("No .env: run ./setup/install.sh first.")
    lines = ENV.read_text().splitlines()
    values = {line.split("=", 1)[0]: line.split("=", 1)[1]
              for line in lines if "=" in line and not line.lstrip().startswith("#")}
    drawn = []
    for name, what in SECRETS.items():
        if values.get(name):
            continue
        value = secrets.token_urlsafe(18)
        drawn.append(name)
        if name in values:
            lines = [f"{name}={value}" if line.startswith(f"{name}=") else line
                     for line in lines]
        else:
            lines += [f"# Keycloak: {what}.", f"{name}={value}"]
    if drawn:
        fd = os.open(ENV, os.O_WRONLY | os.O_TRUNC)
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(lines) + "\n")
    return drawn, values


def main() -> None:
    drawn, values = fill_secrets()
    if drawn:
        print(f"Drew {', '.join(drawn)} in .env.")
    compose = shlex.split(os.environ.get("COMPOSE", "docker compose"))
    subprocess.run([*compose, "--profile", "oauth", "up", "-d", "keycloak"], cwd=ROOT,
                   check=True)
    port = os.environ.get("KEYCLOAK_PORT") or values.get("KEYCLOAK_PORT") or "8080"
    realm = f"http://127.0.0.1:{port}/realms/pachadata"
    print("Waiting for Keycloak", end="", flush=True)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{realm}/.well-known/openid-configuration", timeout=2):
                print(f" ready: {realm}")
                return
        except OSError:
            print(".", end="", flush=True)
            time.sleep(2)
    sys.exit(" not ready after 2 minutes: see the logs of the container mcpcourse-keycloak.")


if __name__ == "__main__":
    main()
