#!/usr/bin/env bash
# Checks the module 13 exercise: the image of the server, its container, its /health route,
# and the CI of your repository.
#
#   bash exercises/module_13/check.sh                 with Docker
#   ENGINE=podman bash exercises/module_13/check.sh   with Podman
#
# Run it from anywhere in the project, with the lab started (./setup/install.sh), after you
# committed and pushed your work and the CI of your repository finished. It calls neither a
# model nor Node, and writes nothing to the database. pytest runs test_container.py, next to
# this script, which builds the image, starts two containers on the network of the lab with
# their port published on 127.0.0.1, removes them, and asks gh for the last workflow run of
# your commit. Five tests are expected; any other number, more included, means the exercise
# or the check was changed, and fails.
set -u
EXPECTED=5
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.." || exit 2
out=$(uv run --quiet pytest "$here/test_container.py" -q -p no:cacheprovider 2>&1)
code=$?
printf '%s\n' "$out"
passed=$(printf '%s\n' "$out" | grep -oE '[0-9]+ passed' | tail -n 1 | cut -d' ' -f1)
if [ "$code" -eq 0 ] && [ "${passed:-0}" -eq "$EXPECTED" ]; then
    echo "All $EXPECTED checks passed."
    exit 0
fi
echo "Expected $EXPECTED passed tests, got ${passed:-0} (pytest exit code $code)."
exit 1
