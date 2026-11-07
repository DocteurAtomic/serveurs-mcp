"""Put a proxy in front of the HTTP server and record what goes over the wire, both ways.

    uv run python tools/wire_http.py <tag> <port> <server-port>

Listens on 127.0.0.1:<port> and forwards every request to http://127.0.0.1:<server-port>/mcp:
register http://127.0.0.1:<port>/mcp in the host instead of the server, as tools/wire.sh is
registered instead of the stdio command. Writes three files, overwritten at each start:

    logs/wire-<tag>.in.jsonl     the JSON-RPC messages the host posted, one per line
    logs/wire-<tag>.out.jsonl    the JSON-RPC messages the server answered, SSE events unwrapped
    logs/wire-<tag>.http.jsonl   one line per HTTP request: verb, status, the MCP headers

tools/wire_summary.py reads the first two as it reads a stdio log. The third is what only
HTTP has: MCP-Protocol-Version, Mcp-Method, Mcp-Name, and Mcp-Session-Id if a session exists.
Stop it with Ctrl-C.
"""

import json
import sys
from pathlib import Path

import httpx2
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import StreamingResponse
from starlette.routing import Route

LOGS = Path(__file__).resolve().parents[1] / "logs"
MCP_HEADERS = ("mcp-protocol-version", "mcp-method", "mcp-name", "mcp-session-id")
# Set again by the proxy or by uvicorn for the leg they serve.
HOP_HEADERS = {"host", "content-length", "transfer-encoding", "connection", "content-encoding"}


def app(tag: str, server_port: int) -> Starlette:
    LOGS.mkdir(exist_ok=True)
    logs = {kind: open(LOGS / f"wire-{tag}.{kind}.jsonl", "w", buffering=1)
            for kind in ("in", "out", "http")}
    target = f"http://127.0.0.1:{server_port}/mcp"
    # The SDK client's timeouts: a response stream may stay open for minutes.
    client = httpx2.AsyncClient(timeout=httpx2.Timeout(30, read=300))

    async def forward(request: Request) -> StreamingResponse:
        body = await request.body()
        if body.strip():
            logs["in"].write(json.dumps(json.loads(body)) + "\n")
        headers = {k: v for k, v in request.headers.items() if k not in HOP_HEADERS}
        sent = client.build_request(request.method, target, headers=headers, content=body)
        response = await client.send(sent, stream=True)
        logs["http"].write(json.dumps({
            "verb": request.method,
            "status": response.status_code,
            "sent": {h: request.headers[h] for h in MCP_HEADERS if h in request.headers},
            "received": {h: response.headers[h] for h in MCP_HEADERS if h in response.headers},
        }) + "\n")
        kind = response.headers.get("content-type", "")

        async def relay():
            pending = ""
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
                    if kind.startswith("text/event-stream"):
                        pending += chunk.decode()
                        *lines, pending = pending.split("\n")
                        for line in lines:
                            if line.startswith("data:") and line[5:].strip():
                                logs["out"].write(line[5:].strip() + "\n")
                    elif kind.startswith("application/json"):
                        pending += chunk.decode()
                if kind.startswith("application/json") and pending.strip():
                    logs["out"].write(json.dumps(json.loads(pending)) + "\n")
            finally:
                await response.aclose()

        return StreamingResponse(
            relay(), status_code=response.status_code,
            headers={k: v for k, v in response.headers.items() if k not in HOP_HEADERS},
        )

    return Starlette(routes=[Route("/mcp", forward, methods=["GET", "POST", "DELETE"])])


def main() -> None:
    tag, port, server_port = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    uvicorn.run(app(tag, server_port), host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
