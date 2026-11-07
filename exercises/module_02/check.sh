#!/usr/bin/env bash
# Checks the module 2 exercise: what two clients sent to the server.
#
#   bash exercises/module_02/check.sh
#
# Run it from anywhere in the project, after recording the two logs the README asks for
# (logs/wire-insp.* with the Inspector CLI, logs/wire-claude.* with claude -p) and writing
# answers.toml next to this script. It calls neither a model nor Node: pytest reads the logs
# with the SDK's JSON-RPC types and compares them with the answers (test_wire_answers.py).
# Three tests are expected; any other number, more included, means the exercise or the check
# was changed, and fails.
set -u
EXPECTED=3
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.." || exit 2
out=$(uv run --quiet pytest "$here/test_wire_answers.py" -q -p no:cacheprovider 2>&1)
code=$?
printf '%s\n' "$out"
passed=$(printf '%s\n' "$out" | grep -oE '[0-9]+ passed' | tail -n 1 | cut -d' ' -f1)
if [ "$code" -eq 0 ] && [ "${passed:-0}" -eq "$EXPECTED" ]; then
    echo "All $EXPECTED checks passed."
    exit 0
fi
echo "Expected $EXPECTED passed tests, got ${passed:-0} (pytest exit code $code)."
exit 1
