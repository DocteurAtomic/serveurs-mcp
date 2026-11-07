"""Checks of the module 2 exercise, run by check.sh: two wire logs against answers.toml.

Three tests. The logs are those the student recorded with tools/wire.sh: logs/wire-insp.*
(MCP Inspector CLI, legacy era) and logs/wire-claude.* (claude -p). The answers are compared
with what the logs contain, not with fixed values: Claude Code may speak another revision on
another machine.
"""

import tomllib
from pathlib import Path

import pytest

from tools.wire_summary import read, summarize

HERE = Path(__file__).resolve().parent
LOGS = HERE.parents[1] / "logs"
CLIENTS = {"inspector": ("insp", "inspector-cli"), "claude": ("claude", "claude-code")}


@pytest.fixture(scope="module")
def answers():
    path = HERE / "answers.toml"
    assert path.exists(), f"write your answers in {path} (see answers.example.toml)"
    return tomllib.loads(path.read_text())


@pytest.fixture(scope="module")
def wires():
    found = {}
    for client, (tag, name) in CLIENTS.items():
        for suffix in ("in", "out"):
            path = LOGS / f"wire-{tag}.{suffix}.jsonl"
            assert path.exists() and path.stat().st_size, f"no log {path}: record it first"
            read(path)  # every line must be a JSON-RPC message
        wire = summarize(tag, LOGS)
        assert wire.client == name, f"logs/wire-{tag}.* was written by {wire.client}, not {name}"
        found[client] = wire
    return found


def test_revision_of_each_client(answers, wires):
    # The Inspector CLI opens in the legacy era unless told otherwise: the exercise asks for it.
    assert wires["inspector"].first_method == "initialize", "record the Inspector in legacy era"
    for client, wire in wires.items():
        assert answers[client]["revision"] == wire.revision, f"{client}: revision"


def test_first_method_of_each_client(answers, wires):
    for client, wire in wires.items():
        assert answers[client]["first_method"] == wire.first_method, f"{client}: first method"


def test_tool_calls_of_each_client(answers, wires):
    for client, wire in wires.items():
        assert wire.tool_calls >= 1, f"{client}: the log holds no tools/call, call a tool"
        assert answers[client]["tool_calls"] == wire.tool_calls, f"{client}: tools/call"
