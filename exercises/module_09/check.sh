#!/usr/bin/env bash
# Checks the module 9 exercise: cancelled_enrollments returns the reason of a cancellation,
# typed by people, in a free_text object of its own.
#
#   bash exercises/module_09/check.sh                  with Docker
#   ENGINE=podman bash exercises/module_09/check.sh    with Podman
#
# Run it from anywhere in the project, with the lab started (./setup/install.sh) and .env on
# mcp_reader. It first recreates PachadataTraining_m09 (./setup/reset-copy.sh m09, a few
# seconds), since the checks cancel an enrollment for good with a reason written as an
# attack; the reference database is never written. Then pytest drives the server in memory
# with the SDK client (test_free_text_of_cancellations.py, next to this script): no model, no
# Node. Four tests are expected; any other number, more included, means the exercise or the
# check was changed, and fails.
set -u
EXPECTED=4
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.." || exit 2
if ! ./setup/reset-copy.sh m09 > /dev/null; then
    echo "Could not recreate PachadataTraining_m09: is the lab started? (ENGINE=podman with Podman)"
    exit 2
fi
out=$(uv run --quiet pytest "$here/test_free_text_of_cancellations.py" -q -p no:cacheprovider 2>&1)
code=$?
printf '%s\n' "$out"
passed=$(printf '%s\n' "$out" | grep -oE '[0-9]+ passed' | tail -n 1 | cut -d' ' -f1)
if [ "$code" -eq 0 ] && [ "${passed:-0}" -eq "$EXPECTED" ]; then
    echo "All $EXPECTED checks passed."
    exit 0
fi
echo "Expected $EXPECTED passed tests, got ${passed:-0} (pytest exit code $code)."
exit 1
