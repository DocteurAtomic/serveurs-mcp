#!/usr/bin/env bash
# Checks the module 12 exercise: with PACHA_OAUTH_VERIFY=introspection, the server asks
# Keycloak about every token instead of checking its signature with the keys.
#
#   bash exercises/module_12/check.sh
#
# Run it from anywhere in the project, with the lab started (./setup/install.sh) and Keycloak
# started (uv run python setup/keycloak.py). It calls neither a model nor Node, and writes
# nothing to the database. pytest runs test_introspection.py, next to this script, which asks
# Keycloak for tokens itself (client pacha-check, password grant, secrets read from .env),
# starts `pachatraining-mcp --http` on a free port of 127.0.0.1 and talks to it over HTTP.
# Five tests are expected; any other number, more included, means the exercise or the check
# was changed, and fails.
set -u
EXPECTED=5
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.." || exit 2
out=$(uv run --quiet pytest "$here/test_introspection.py" -q -p no:cacheprovider 2>&1)
code=$?
printf '%s\n' "$out"
passed=$(printf '%s\n' "$out" | grep -oE '[0-9]+ passed' | tail -n 1 | cut -d' ' -f1)
if [ "$code" -eq 0 ] && [ "${passed:-0}" -eq "$EXPECTED" ]; then
    echo "All $EXPECTED checks passed."
    exit 0
fi
echo "Expected $EXPECTED passed tests, got ${passed:-0} (pytest exit code $code)."
exit 1
