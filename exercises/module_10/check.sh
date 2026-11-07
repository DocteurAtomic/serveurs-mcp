#!/usr/bin/env bash
# Checks the module 10 exercise: over Streamable HTTP, the server accepts the names the team
# reaches it by (PACHA_HTTP_HOSTS), keeps the names of this machine, and refuses any other.
#
#   bash exercises/module_10/check.sh
#
# Run it from anywhere in the project, with the lab started (./setup/install.sh). It calls
# neither a model nor Node, and writes nothing to the database. pytest runs
# test_team_names.py, next to this script, which starts `pachatraining-mcp --http` itself on
# free ports of 127.0.0.1 (twice: with a team name drawn at random, then without the
# variable) and talks to it over HTTP only: the in-memory client goes through no transport
# and would check nothing here. Four tests are expected; any other number, more included,
# means the exercise or the check was changed, and fails.
set -u
EXPECTED=4
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.." || exit 2
out=$(uv run --quiet pytest "$here/test_team_names.py" -q -p no:cacheprovider 2>&1)
code=$?
printf '%s\n' "$out"
passed=$(printf '%s\n' "$out" | grep -oE '[0-9]+ passed' | tail -n 1 | cut -d' ' -f1)
if [ "$code" -eq 0 ] && [ "${passed:-0}" -eq "$EXPECTED" ]; then
    echo "All $EXPECTED checks passed."
    exit 0
fi
echo "Expected $EXPECTED passed tests, got ${passed:-0} (pytest exit code $code)."
exit 1
