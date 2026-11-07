#!/usr/bin/env bash
# Checks the module 4 exercise: tests/test_stdio.py, the server started over stdio as a host
# starts it.
#
#   bash exercises/module_04/check.sh
#
# Run it from anywhere in the project, with the lab started (./setup/install.sh). It calls
# neither a model nor Node. Two runs of pytest on tests/test_stdio.py:
#   1. as is: three tests are expected to pass; any other number, more included, fails;
#   2. with .env moved aside and its PACHA_SQL_* variables exported in this shell instead: a
#      server started over stdio with the client's default environment no longer reaches the
#      database, so all three tests must fail. A test that still passes did not start the
#      server that way (it ran it in memory, or handed it the shell's environment), or does
#      not look at the result.
# .env is put back when the script ends, whatever happens.
set -u
EXPECTED=3
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
cd "$root" || exit 2
suite=tests/test_stdio.py
aside=.env.module-04-check

if [ -e "$aside" ]; then
    if [ -e .env ]; then
        echo "$aside exists next to .env: compare them, keep one as .env, delete the other."
        exit 2
    fi
    mv "$aside" .env && echo "Put back .env from $aside (an earlier run was interrupted)."
fi
if [ ! -f "$suite" ]; then
    echo "No $suite: write it first (see exercises/module_04/README.md)."
    exit 1
fi
if [ ! -f .env ]; then
    echo "No .env at the root of the project: run ./setup/install.sh."
    exit 2
fi

count() { printf '%s\n' "$1" | grep -oE "[0-9]+ $2" | tail -n 1 | cut -d' ' -f1; }

echo "== 1. $suite, as is"
out=$(uv run --quiet pytest "$suite" -q -p no:cacheprovider 2>&1)
code=$?
printf '%s\n' "$out"
passed=$(count "$out" passed)
if [ "$code" -ne 0 ] || [ "${passed:-0}" -ne "$EXPECTED" ]; then
    echo "Expected $EXPECTED passed tests, got ${passed:-0} (pytest exit code $code)."
    exit 1
fi

echo "== 2. $suite, .env moved aside, its PACHA_SQL_* variables in the shell only"
mv .env "$aside" || exit 2
trap 'mv -f "$aside" .env' EXIT
trap 'exit 130' INT TERM HUP
out=$(
    while IFS="=" read -r key value || [ -n "$key" ]; do
        case $key in PACHA_SQL_*) export "$key=$value" ;; esac
    done < "$aside"
    uv run --quiet pytest "$suite" -q -p no:cacheprovider 2>&1
)
code=$?
printf '%s\n' "$out" | grep -E '^(FAILED|ERROR)|[0-9]+ (passed|failed|skipped|error)'
passed=$(count "$out" passed)
if [ "${passed:-0}" -gt 0 ] || [ "$code" -eq 0 ]; then
    echo "${passed:-0} test(s) passed while the server had no .env (pytest exit code $code)."
    echo "The SDK client and the Inspector start a stdio server with almost no environment."
    echo "Start it over stdio without env=os.environ, and check the values of each result,"
    echo "not only that there is one."
    exit 1
fi
echo "All $EXPECTED checks passed, and all of them fail when the server cannot connect."
exit 0
