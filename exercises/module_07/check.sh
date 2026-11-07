#!/usr/bin/env bash
# Checks the module 7 exercise: cancel_enrollment, which writes after the user confirms it.
#
#   bash exercises/module_07/check.sh                  with Docker
#   ENGINE=podman bash exercises/module_07/check.sh    with Podman
#
# Run it from anywhere in the project, with the lab started (./setup/install.sh). It first
# recreates PachadataTraining_m07 (./setup/reset-copy.sh m07, a few seconds), since one check
# cancels an enrollment for good; the reference database is never written. Then pytest drives
# the server in memory with the SDK client, which answers the confirmation in place of the
# user (test_cancel_enrollment.py, next to this script): no model, no Node. Five tests are
# expected; any other number, more included, means the exercise or the check was changed,
# and fails.
set -u
EXPECTED=5
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.." || exit 2
if ! ./setup/reset-copy.sh m07 > /dev/null; then
    echo "Could not recreate PachadataTraining_m07: is the lab started? (ENGINE=podman with Podman)"
    exit 2
fi
out=$(uv run --quiet pytest "$here/test_cancel_enrollment.py" -q -p no:cacheprovider 2>&1)
code=$?
printf '%s\n' "$out"
passed=$(printf '%s\n' "$out" | grep -oE '[0-9]+ passed' | tail -n 1 | cut -d' ' -f1)
if [ "$code" -eq 0 ] && [ "${passed:-0}" -eq "$EXPECTED" ]; then
    echo "All $EXPECTED checks passed."
    exit 0
fi
echo "Expected $EXPECTED passed tests, got ${passed:-0} (pytest exit code $code)."
exit 1
