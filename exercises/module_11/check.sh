#!/usr/bin/env bash
# Checks the module 11 exercise: over Streamable HTTP, a token of PACHA_READ_TOKENS reads
# but may not write, and a token of PACHA_TOKENS may also write.
#
#   bash exercises/module_11/check.sh
#
# Run it from anywhere in the project, with the lab started (./setup/install.sh). It calls
# neither a model nor Node, and writes nothing to the database. pytest runs
# test_read_tokens.py, next to this script, which starts `pachatraining-mcp --http` itself on
# a free port of 127.0.0.1, with a reader and a writer whose names and tokens it draws at
# random, and talks to it over HTTP only: the in-memory client sends no token, so over it the
# server would know no caller. Four tests are expected; any other number, more included,
# means the exercise or the check was changed, and fails.
set -u
EXPECTED=4
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.." || exit 2
out=$(uv run --quiet pytest "$here/test_read_tokens.py" -q -p no:cacheprovider 2>&1)
code=$?
printf '%s\n' "$out"
passed=$(printf '%s\n' "$out" | grep -oE '[0-9]+ passed' | tail -n 1 | cut -d' ' -f1)
if [ "$code" -eq 0 ] && [ "${passed:-0}" -eq "$EXPECTED" ]; then
    echo "All $EXPECTED checks passed."
    exit 0
fi
echo "Expected $EXPECTED passed tests, got ${passed:-0} (pytest exit code $code)."
exit 1
