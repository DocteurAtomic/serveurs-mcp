"""Summarize a wire log written by tools/wire.sh: the messages, the protocol revision, the calls.

    uv run python tools/wire_summary.py <tag>        reads logs/wire-<tag>.in.jsonl and .out.jsonl

Every line is parsed with the SDK's JSON-RPC types: a line that is not a JSON-RPC message
stops the summary, since it means something other than the protocol went over the wire.
"""

import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from mcp.types import JSONRPCError, JSONRPCNotification, JSONRPCRequest, jsonrpc_message_adapter

LOGS = Path(__file__).resolve().parents[1] / "logs"
VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_KEY = "io.modelcontextprotocol/clientInfo"


@dataclass
class Wire:
    """What one start of the server received and sent."""

    methods: list[str] = field(default_factory=list)  # host to server, in order
    revision: str | None = None  # negotiated by initialize, or declared in each request's _meta
    client: str | None = None  # the client's name, as it introduces itself
    errors: int = 0  # error responses sent by the server

    @property
    def first_method(self) -> str | None:
        return self.methods[0] if self.methods else None

    @property
    def tool_calls(self) -> int:
        return self.methods.count("tools/call")


def read(path: Path) -> list:
    return [jsonrpc_message_adapter.validate_json(line)
            for line in path.read_text().splitlines() if line.strip()]


def summarize(tag: str, logs: Path = LOGS) -> Wire:
    wire = Wire()
    initialize_ids = set()
    for message in read(logs / f"wire-{tag}.in.jsonl"):
        if not isinstance(message, (JSONRPCRequest, JSONRPCNotification)):
            continue  # a response from the host, to a request of the server
        wire.methods.append(message.method)
        params = message.params or {}
        meta = params.get("_meta") or {}
        if message.method == "initialize":
            initialize_ids.add(message.id)
            wire.client = wire.client or params.get("clientInfo", {}).get("name")
        else:
            wire.client = wire.client or meta.get(CLIENT_KEY, {}).get("name")
        if VERSION_KEY in meta and wire.revision is None:
            wire.revision = meta[VERSION_KEY]
    for message in read(logs / f"wire-{tag}.out.jsonl"):
        if isinstance(message, JSONRPCError):
            wire.errors += 1
        elif getattr(message, "id", None) in initialize_ids:
            wire.revision = message.result.get("protocolVersion")  # the handshake decides
    return wire


def main() -> None:
    for tag in sys.argv[1:] or ["run"]:
        wire = summarize(tag)
        print(f"wire-{tag}: client {wire.client}, revision {wire.revision}, "
              f"first method {wire.first_method}, {wire.tool_calls} tools/call, "
              f"{wire.errors} error responses")
        for method, count in Counter(wire.methods).items():
            print(f"  {count:3}  {method}")


if __name__ == "__main__":
    main()
