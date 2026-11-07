#!/usr/bin/env bash
# Checks the module 8 exercise: the server reads the views of the Mcp schema only, as
# mcp_reader, and Mcp.TrainerMonth serves trainer_load and the trainer resource template.
#
#   bash exercises/module_08/check.sh
#
# Run it from anywhere in the project, with the lab started, .env on mcp_reader
# (uv run python setup/use_account.py mcp_reader), and Mcp.TrainerMonth created by
# ./setup/install.sh from setup/mcp-schema.sql. pytest drives the server in memory with the
# SDK client (test_least_privilege.py, next to this script), and its first check runs the
# whole suite of tests/ again under mcp_reader: no model, no Node, a few seconds. Five tests
# are expected; any other number, more included, means the exercise or the check was changed,
# and fails.
set -u
EXPECTED=5
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.." || exit 2
out=$(uv run --quiet pytest "$here/test_least_privilege.py" -q -p no:cacheprovider 2>&1)
code=$?
printf '%s\n' "$out"
passed=$(printf '%s\n' "$out" | grep -oE '[0-9]+ passed' | tail -n 1 | cut -d' ' -f1)
if [ "$code" -eq 0 ] && [ "${passed:-0}" -eq "$EXPECTED" ]; then
    echo "All $EXPECTED checks passed."
    exit 0
fi
echo "Expected $EXPECTED passed tests, got ${passed:-0} (pytest exit code $code)."
exit 1
