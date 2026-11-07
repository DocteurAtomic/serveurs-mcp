#!/usr/bin/env bash
# Checks the module 1 exercise: the session_detail tool of the server.
#
#   bash exercises/module_01/check.sh
#
# Run it from anywhere in the project, with the lab started (./setup/install.sh). It calls
# neither a model nor Node: pytest drives the server in memory with the SDK client
# (test_session_detail.py, next to this script). Four tests are expected; any other number,
# more included, means the exercise or the check was changed, and fails.
set -u
EXPECTED=4
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.." || exit 2
out=$(uv run --quiet pytest "$here/test_session_detail.py" -q -p no:cacheprovider 2>&1)
code=$?
printf '%s\n' "$out"
passed=$(printf '%s\n' "$out" | grep -oE '[0-9]+ passed' | tail -n 1 | cut -d' ' -f1)
if [ "$code" -eq 0 ] && [ "${passed:-0}" -eq "$EXPECTED" ]; then
    echo "All $EXPECTED checks passed."
    exit 0
fi
echo "Expected $EXPECTED passed tests, got ${passed:-0} (pytest exit code $code)."
exit 1
