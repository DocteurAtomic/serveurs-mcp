#!/usr/bin/env bash
# Start the server over stdio and record what goes over the wire, in both directions.
#
#   tools/wire.sh <tag>          register this command in the host instead of the server's
#
# Writes logs/wire-<tag>.in.jsonl (host to server), logs/wire-<tag>.out.jsonl (server to host)
# and logs/wire-<tag>.err (the server's stderr). The three files are overwritten at each start:
# a log holds the last start of the server only. Nothing else may write to stdout.
tag=${1:-run}
root=$(cd "$(dirname "$0")/.." && pwd)
log=$root/logs/wire-$tag
mkdir -p "$root/logs"
tee "$log.in.jsonl" \
    | uv --directory "$root" run --quiet pachatraining-mcp 2>"$log.err" \
    | tee "$log.out.jsonl"
