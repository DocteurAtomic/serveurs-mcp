"""The image of the server, built from the Dockerfile, as the CI builds it.

Skipped unless PACHA_IMAGE names the image (`docker build -t pachatraining-mcp .`, then
PACHA_IMAGE=pachatraining-mcp). The CI sets it and counts the passed tests, so a skip there
fails the run. ENGINE is docker by default, podman otherwise (ENGINE=podman).

The container is started over stdio, as `claude mcp add pachatraining -- docker run -i ...`
would: --network host lets it reach SQL Server on 127.0.0.1,14733 as the tests do, and listens
on nothing. The connection settings go through the environment, by name only on the command
line: their values never appear in the list of processes.
"""

import json
import os
import subprocess

import pytest
from mcp import Client, StdioServerParameters

IMAGE = os.environ.get("PACHA_IMAGE", "")
ENGINE = os.environ.get("ENGINE", "docker")
# What the server reads to reach the base, from the environment or from .env (conftest.py
# imports the server, which loads .env first).
PASSED = ["PACHA_SQL_SERVER", "PACHA_SQL_DATABASE", "PACHA_SQL_USER", "PACHA_SQL_PASSWORD"]

pytestmark = pytest.mark.skipif(not IMAGE, reason="PACHA_IMAGE is not set")


@pytest.mark.anyio
async def test_stdio_in_the_image():
    args = ["run", "-i", "--rm", "--network", "host"]
    for name in PASSED:
        args += ["-e", name]
    server = StdioServerParameters(command=ENGINE, args=[*args, IMAGE, "pachatraining-mcp"],
                                   env=dict(os.environ))
    async with Client(server) as client:
        assert client.protocol_version == "2026-07-28"
        result = await client.call_tool("sessions_in_week", {"monday": "2026-11-16"})
    assert not result.is_error, result.content[0].text
    assert result.structured_content["count"] == 36


def test_image_runs_as_a_plain_user():
    config = json.loads(subprocess.run([ENGINE, "image", "inspect", IMAGE], check=True,
                                       capture_output=True, text=True).stdout)[0]["Config"]
    assert config.get("User") not in (None, "", "0", "root"), "the server would run as root"
    assert config["Env"].count("PACHA_HTTP_LISTEN=0.0.0.0") == 1
