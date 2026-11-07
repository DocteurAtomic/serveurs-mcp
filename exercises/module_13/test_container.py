"""The checks of the module 13 exercise: the image of the server, its container, and the CI.

The image is built from the Dockerfile of the project, then started as compose starts the mcp
service, but by the engine directly: on the network of the lab's SQL Server container, with
the port published on 127.0.0.1 only, and the settings and a token drawn for the run passed
through the environment (names only on the command line). ENGINE is docker by default, podman
otherwise; GH is the gh command (the tests of the check itself replace it).
"""

import json
import os
import secrets
import shlex
import socket
import subprocess
import tarfile
import time
from pathlib import Path

import httpx2
import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGINE = os.environ.get("ENGINE", "docker")
IMAGE = "pachatraining-mcp:exercise-13"
SQL_CONTAINER = "mcpcourse"
REVISION = "2026-07-28"
META = {
    "io.modelcontextprotocol/protocolVersion": REVISION,
    "io.modelcontextprotocol/clientInfo": {"name": "check-13", "version": "1"},
    "io.modelcontextprotocol/clientCapabilities": {},
}
TOKEN = secrets.token_urlsafe(32)


def env_file() -> dict[str, str]:
    """The values of .env: the passwords install.sh drew, the tokens, the secrets."""
    values = {}
    for line in (ROOT / ".env").read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.lstrip().startswith("#"):
            values[key.strip()] = value.strip()
    return values


ENV = env_file()


def engine(*args: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([ENGINE, *args], capture_output=True, **kw)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def image():
    """Build the image of the project, as `docker build -t pachatraining-mcp .` does."""
    built = engine("build", "-t", IMAGE, str(ROOT), text=True)
    assert built.returncode == 0, f"the image does not build:\n{built.stderr[-2000:]}"
    yield IMAGE
    engine("rmi", "-f", IMAGE)


def lab_network() -> str:
    """The network compose gave the lab: the one the SQL Server container is on."""
    found = engine("inspect", SQL_CONTAINER, "--format", "{{json .NetworkSettings.Networks}}",
                   text=True)
    assert found.returncode == 0, f"no {SQL_CONTAINER} container: run ./setup/install.sh"
    return next(iter(json.loads(found.stdout)))


def run(image: str, **env: str) -> tuple[str, int]:
    """Start the image detached, like the mcp service of compose.yaml; return its name and
    the port of 127.0.0.1 it is published on."""
    port = free_port()
    name = f"pachatraining-check-{secrets.token_hex(4)}"
    passed = {"PACHA_SQL_SERVER": "sql,1433",
              "PACHA_SQL_DATABASE": ENV.get("PACHA_SQL_DATABASE", "PachadataTraining"),
              "PACHA_SQL_USER": ENV["PACHA_SQL_USER"],
              "PACHA_SQL_PASSWORD": ENV["PACHA_SQL_PASSWORD"],
              "PACHA_TOKENS": f"check:{TOKEN}",
              "PACHA_MCP_URL": f"http://127.0.0.1:{port}/mcp", **env}
    args = ["run", "-d", "--name", name, "--network", lab_network(),
            "-p", f"127.0.0.1:{port}:8000"]
    for key in passed:
        args += ["-e", key]
    started = subprocess.run([ENGINE, *args, image], capture_output=True, text=True,
                             env={**os.environ, **passed})
    assert started.returncode == 0, started.stderr
    return name, port


def stop(name: str) -> None:
    engine("rm", "-f", name)


def wait(port: int, name: str, seconds: float = 30) -> None:
    """Until the container answers HTTP on its published port."""
    deadline = time.monotonic() + seconds
    while True:
        try:
            httpx2.get(f"http://127.0.0.1:{port}/", timeout=1)
            return
        except httpx2.TransportError:
            if time.monotonic() > deadline:
                logs = engine("logs", name, text=True)
                raise AssertionError(f"the container does not answer on 127.0.0.1:{port}:\n"
                                     f"{(logs.stdout + logs.stderr)[-1500:]}") from None
            time.sleep(0.3)


@pytest.fixture(scope="module")
def server(image):
    name, port = run(image)
    try:
        wait(port, name)
        yield port
    finally:
        stop(name)


def post(port: int, method: str, token: str | None = TOKEN, **headers: str) -> httpx2.Response:
    sent = {"MCP-Protocol-Version": REVISION, "Mcp-Method": method,
            "Accept": "application/json, text/event-stream"}
    if token:
        sent["Authorization"] = f"Bearer {token}"
    sent.update(headers)
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": {"_meta": META}}
    return httpx2.post(f"http://127.0.0.1:{port}/mcp", json=body, headers=sent, timeout=30)


def test_the_container_answers(image, server):
    user = json.loads(engine("image", "inspect", image, text=True).stdout)[0]["Config"]
    assert user.get("User") not in (None, "", "0", "root"), "the server runs as root"
    assert post(server, "server/discover", token=None).status_code == 401
    found = post(server, "server/discover")
    assert found.status_code == 200, found.text[:300]
    assert REVISION in found.json()["result"]["supportedVersions"]


def test_foreign_host_refused(server):
    refused = post(server, "server/discover", Host="evil.example")
    assert (refused.status_code, refused.text) == (421, "Invalid Host header")
    refused = post(server, "server/discover", Origin="http://evil.example")
    assert (refused.status_code, refused.text) == (403, "Invalid Origin header")


def test_health(image, server):
    up = httpx2.get(f"http://127.0.0.1:{server}/health", timeout=10)
    assert up.status_code == 200, f"/health: {up.status_code} {up.text[:200]}"
    assert up.json() == {"status": "ok"}
    # Another container whose base does not answer: nothing listens on port 1 of sql.
    name, port = run(image, PACHA_SQL_SERVER="sql,1")
    try:
        wait(port, name)
        start = time.monotonic()
        down = httpx2.get(f"http://127.0.0.1:{port}/health", timeout=30)
        took = time.monotonic() - start
    finally:
        stop(name)
    assert down.status_code == 503, f"{down.status_code} {down.text[:300]}"
    assert took < 10, f"the health check took {took:.1f} s to say the base is down"
    said = down.text
    for secret in ("sql,1", "mcp_reader", ENV["PACHA_SQL_USER"], ENV["PACHA_SQL_PASSWORD"]):
        assert secret not in said, f"/health tells a stranger {secret[:3]}..."


def pieces(value: str) -> set[str]:
    """Pieces of 12 characters that cover the value: one of them is enough to find it, even
    when the value is cut, quoted or written inside a connection string."""
    return {value[i:i + 12] for i in range(0, len(value) - 11, 12)} | {value[-12:]}


def test_no_secret_in_the_image(image):
    secrets_of_env = {k: v for k, v in ENV.items() if len(v) >= 12 and k not in (
        "PACHA_SQL_SERVER", "PACHA_SQL_DATABASE", "PACHA_SQL_WRITE_DATABASE", "PACHA_MCP_URL",
        "PACHA_OAUTH_ISSUER", "PACHA_HTTP_HOSTS")}
    assert secrets_of_env, ".env holds no password: run ./setup/install.sh first"
    created = engine("create", image, text=True)
    assert created.returncode == 0, created.stderr
    container = created.stdout.strip()
    try:
        filesystem = engine("export", container).stdout
    finally:
        engine("rm", "-f", container)
    history = engine("history", "--no-trunc", "--format", "{{.CreatedBy}}", image).stdout
    config = engine("image", "inspect", image).stdout
    with tarfile.open(fileobj=__import__("io").BytesIO(filesystem)) as tar:
        names = [m.name for m in tar.getmembers()]
    assert not [n for n in names if Path(n).name == ".env"], "a .env file is in the image"
    found = [f"{key} in {where}" for key, value in secrets_of_env.items()
             for where, blob in (("the files", filesystem), ("the history", history),
                                 ("the configuration", config))
             if any(piece.encode() in blob for piece in pieces(value))]
    assert not found, "values of .env in the image: " + ", ".join(found)


def test_the_last_workflow_is_green():
    git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True,
                                    text=True, check=True).stdout.strip()
    head = git("rev-parse", "HEAD")
    assert not git("status", "--porcelain", "--untracked-files=no"), (
        "commit and push your changes: the CI checks what was pushed")
    gh = shlex.split(os.environ.get("GH", "gh"))
    listed = subprocess.run([*gh, "run", "list", "--commit", head, "--limit", "1", "--json",
                             "status,conclusion,headSha,workflowName,url"],
                            capture_output=True, text=True, cwd=ROOT)
    assert listed.returncode == 0, f"gh run list failed: {listed.stderr.strip()}"
    runs = json.loads(listed.stdout)
    assert runs, f"no workflow run for {head[:7]}: push it, and wait for the CI"
    last = runs[0]
    assert last["headSha"] == head
    assert (last["status"], last["conclusion"]) == ("completed", "success"), (
        f"{last['workflowName']} is {last['status']} {last['conclusion']}: {last['url']}")
