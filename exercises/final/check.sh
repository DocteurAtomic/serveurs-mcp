#!/usr/bin/env bash
# The final check of the course: one test of the suite for each behaviour the course
# promised, from the first tool to the image, run together, then a summary.
#
#   PACHA_IMAGE=pachatraining-mcp bash exercises/final/check.sh                  with Docker
#   PACHA_IMAGE=pachatraining-mcp ENGINE=podman bash exercises/final/check.sh    with Podman
#
# Run it with the lab started (./setup/install.sh) and the image built
# (docker build -t pachatraining-mcp .). It calls neither a model nor Node; the tests that
# write do it on PachadataTraining_m07, as in module 7. Every test listed below must pass:
# a skipped one (the image test without PACHA_IMAGE) fails the check.
set -u
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.." || exit 2
# module | promise | test
checks=(
  "1|a tool answers with structured content|tests/test_server.py::test_sessions_in_week"
  "4|the server runs over stdio, as a host starts it|tests/test_stdio.py::test_sessions_in_week_over_stdio"
  "2|the wire log of a 2026-07-28 start|tests/test_wire.py::test_wire_log_of_one_start[auto-2026-07-28-server/discover]"
  "2|the same server serves a 2025-11-25 client|tests/test_wire.py::test_wire_log_of_one_start[legacy-2025-11-25-initialize]"
  "3|arguments checked before the function runs|tests/test_server.py::test_arguments_are_checked_before_the_function"
  "3|every tool and parameter described for the model|tests/test_descriptions.py::test_every_tool_and_every_parameter_is_described"
  "5|a resource template, listed as a template|tests/test_trainer_resources.py::test_the_template_is_listed_as_a_template"
  "5|a prompt with its arguments|tests/test_trainer_resources.py::test_the_prompt_names_the_trainer_and_the_month"
  "6|calls at the same time, one connection each|tests/test_database.py::test_simultaneous_calls"
  "6|bounded pages that cover the whole result|tests/test_sessions_to_watch.py::test_pages_cover_the_reference_query"
  "7|nothing written without a yes|tests/test_postpone.py::test_nothing_written_without_a_yes[decline-None]"
  "7|written by the procedure after a yes|tests/test_postpone.py::test_postponed_after_accept"
  "8|the account of the server reads the Mcp schema only|tests/test_least_privilege.py::test_mcp_reader_has_no_right_outside_the_mcp_schema"
  "9|text typed by people comes back as data|tests/test_free_text.py::test_the_remark_comes_back_in_free_text"
  "10|Streamable HTTP for the names of this machine only|tests/test_http.py::test_only_the_names_of_this_machine"
  "11|no token, no answer; a reader does not write|tests/test_auth.py::test_a_reader_may_read_and_not_write"
  "12|a token issued for another service is refused|tests/test_oauth.py::test_a_token_not_for_this_server_gets_401"
  "13|the Host check stays on off 127.0.0.1|tests/test_listen.py::test_host_check_off_the_loopback_address"
  "13|the image serves the tools|tests/test_image.py::test_stdio_in_the_image"
)
ids=()
for c in "${checks[@]}"; do ids+=("${c##*|}"); done
out=$(uv run --quiet pytest -v -p no:cacheprovider "${ids[@]}" 2>&1)
code=$?
failed=0
echo "Module  Result  Promise"
for c in "${checks[@]}"; do
    module=${c%%|*}; rest=${c#*|}; promise=${rest%%|*}; id=${rest#*|}
    if grep -qF -- "$id PASSED" <<<"$out"; then result=ok; else result=NOT; failed=$((failed + 1)); fi
    printf '%6s  %-6s  %s\n' "$module" "$result" "$promise"
done
total=${#checks[@]}
if [ "$code" -eq 0 ] && [ "$failed" -eq 0 ]; then
    echo "All $total promises kept."
    exit 0
fi
printf '%s\n' "$out" | tail -n 30
echo "$failed of $total promises not kept (pytest exit code $code)."
exit 1
