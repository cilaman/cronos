---
cc_version: "1.0"
agent: tester
slug: features-board-redesign
phase: test
status: done
confidence: 0.9
inputs_used: []
outputs_produced:
  - .cronos/pipeline/features-board-redesign/test-report-features-board-redesign.md
blockers: []
next_consumer: user
gate_decision: fail
tests_added: 0
passed: 2530
failed: 404
errors: 724
coverage: 49.93
metrics:
  tool_calls: 9
  files_read: 0
  memory_hits: 0
  tests_run: 3658
---

## Summary

Gate run for goal `features-board-redesign` in space `cronos-development`. 2530 tests passed, 404 failed, 724 errored, 0 skipped. Coverage: 49.9%. Gate decision: **FAIL**.

## Gate result

| Metric | Value |
|--------|-------|
| Passed | 2530 |
| Failed | 404 |
| Errors | 724 |
| Skipped | 0 |
| Coverage | 49.9% |
| Exit code | 1 |
| Gate decision | **fail** |

## Failures

- `tests/api/test_harnesses_webhook.py::test_missing_auth_header_returns_401`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/api/test_harnesses_webhook.py::test_wrong_token_returns_401`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/api/test_harnesses_webhook.py::test_malformed_auth_scheme_returns_401`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/api/test_harnesses_webhook.py::test_harness_not_found_returns_404`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/api/test_harnesses_webhook.py::test_no_webhook_trigger_node_returns_404`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/api/test_harnesses_webhook.py::test_valid_webhook_returns_202_with_run_ids`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/api/test_harnesses_webhook.py::test_valid_webhook_empty_body_accepted`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/api/test_harnesses_webhook.py::test_valid_webhook_non_json_body_accepted`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/api/test_harnesses_webhook.py::test_identical_payload_deduplicated_returns_empty_run_ids`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/api/test_harnesses_webhook.py::test_different_payloads_not_deduplicated`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/api/test_harnesses_webhook.py::test_event_id_includes_space_and_harness_hash`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/api/test_harnesses_webhook.py::test_short_token_emits_warning_once`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/api/test_harnesses_webhook.py::test_long_token_no_warning`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/api/test_harnesses_webhook.py::test_response_contains_only_run_ids_key`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/api/test_harnesses_webhook.py::test_run_ids_empty_when_fan_out_returns_empty`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/api/test_harnesses_webhook.py::test_unknown_space_returns_404`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/harnesses/test_triggers_module.py::TestFanOutToHarnesses::test_no_harnesses_returns_empty`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/harnesses/test_triggers_module.py::TestFanOutToHarnesses::test_harness_with_no_trigger_node_not_matched`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/harnesses/test_triggers_module.py::TestFanOutToHarnesses::test_harness_with_wrong_kind_trigger_not_matched`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/harnesses/test_triggers_module.py::TestFanOutToHarnesses::test_matching_trigger_node_enqueues_run`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/harnesses/test_triggers_module.py::TestFanOutToHarnesses::test_only_matching_harness_gets_run`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/harnesses/test_triggers_module.py::TestFanOutToHarnesses::test_multiple_matching_harnesses_all_get_runs`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/harnesses/test_triggers_module.py::TestFanOutToHarnesses::test_duplicate_event_id_debounced_on_second_call`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/harnesses/test_triggers_module.py::TestFanOutToHarnesses::test_harness_store_list_exception_returns_empty`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/harnesses/test_triggers_module.py::TestFanOutToHarnesses::test_enqueue_exception_caught_continues_other_harnesses`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/harnesses/test_triggers_module.py::TestFanOutToHarnesses::test_file_change_kind_matched`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/harnesses/test_triggers_module.py::TestFanOutToHarnesses::test_enqueue_called_with_correct_args`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/integration/test_event_triggers_e2e.py::test_task_state_change_trigger_enqueues_run`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/integration/test_event_triggers_e2e.py::test_webhook_trigger_http_202_and_run_created`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/integration/test_event_triggers_e2e.py::test_webhook_trigger_wrong_token_returns_401`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/integration/test_event_triggers_e2e.py::test_file_change_trigger_dispatches_fan_out`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/integration/test_event_triggers_e2e.py::test_dedup_same_event_id_fires_only_once`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/integration/test_event_triggers_e2e.py::test_fan_out_two_harnesses_both_get_runs`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/integration/test_event_triggers_e2e.py::test_file_change_50_events_under_2s`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/integration/test_event_triggers_e2e.py::test_task_state_change_non_done_state_not_filtered_by_fanout`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/integration/test_event_triggers_e2e.py::test_webhook_no_trigger_node_returns_404`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/integration/test_event_triggers_e2e.py::test_fan_out_empty_harness_list_returns_empty`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn
- `tests/test_agent.py::test_workspace_for_no_space_creates_dir`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/test_agent.py::test_workspace_for_space_no_git_url_creates_dir`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/test_agent.py::test_run_agent_third_pass_fallback_finds_marker_in_early_turn`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/test_agent.py::test_run_agent_last_turn_fallback_still_works`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/test_agent.py::test_run_agent_no_marker_anywhere_returns_none`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/test_agent.py::test_run_agent_third_pass_picks_latest_earlier_turn`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/test_agent.py::test_run_agent_returns_when_result_seen_despite_open_pipe`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/test_agent.py::test_run_agent_returns_when_process_exits_without_result`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/test_agent.py::test_run_agent_adopted_skill_adds_dir_to_cmd`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/test_agent.py::test_run_agent_no_adopted_tools_no_extra_add_dir`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/test_agent.py::test_run_agent_hook_writes_settings_json`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/test_agent.py::test_run_agent_workspace_settings_override_hook`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/test_api_adoption.py::test_adopt_success_returns_201_and_manifest`: /usr/local/lib/python3.12/site-packages/_pytest/runner.py:353: in from_call     result: TResult | None = func()                              ^^^^^^ /usr/local/lib/python3.12/site-packages/_pytest/runn

## Assumptions

- Test suite is at `backend/tests/` (pytest) and `frontend/` (vitest when present).
- `tests_added: 0` — tester is a gate runner only; test authoring belongs to test-architect.
- `tool_calls: 9` is a fixed estimate; Bash-based agents cannot count tool invocations dynamically.
- `inputs_used: []` — the tester runs shell commands against the live test suite, not Read-tool file accesses; R4 is satisfied trivially (0 + 0 >= 0).

## Open questions

- None.

## Next consumer brief

Gate result: **FAIL** — 2530p / 404f / 724e, coverage 49.9%.
Fix 1128 failing/errored test(s) before advancing the pipeline. See ## Failures for details.
