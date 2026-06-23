---
cc_version: "1.0"
agent: tester
slug: gui-modal-loading
phase: test
status: done
confidence: 0.9
inputs_used: []
outputs_produced:
  - .cronos/pipeline/gui-modal-loading/test-report-gui-modal-loading.md
blockers: []
next_consumer: user
gate_decision: fail
tests_added: 0
passed: 2813
failed: 663
errors: 836
coverage: 50.48
metrics:
  tool_calls: 9
  files_read: 0
  memory_hits: 0
  tests_run: 4312
---

## Summary

Gate run for goal `gui-modal-loading` in space `cronos-development`. 2813 tests passed, 663 failed, 836 errored, 0 skipped. Coverage: 50.5%. Gate decision: **FAIL**.

## Gate result

| Metric | Value |
|--------|-------|
| Passed | 2813 |
| Failed | 663 |
| Errors | 836 |
| Skipped | 0 |
| Coverage | 50.5% |
| Exit code | 1 |
| Gate decision | **fail** |

## Failures

- `tests/api/test_features_board.py::test_get_feature_board_empty`: tests/api/test_features_board.py:126: in test_get_feature_board_empty     assert response.status_code == 200, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 == 200 E    +  
- `tests/api/test_features_board.py::test_items_routed_to_correct_lanes`: tests/api/test_features_board.py:190: in test_items_routed_to_correct_lanes     assert response.status_code == 200, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 == 200 E 
- `tests/api/test_features_board.py::test_multiple_items_in_same_lane`: tests/api/test_features_board.py:232: in test_multiple_items_in_same_lane     assert response.status_code == 200 E   assert 401 == 200 E    +  where 401 = <Response [401 Unauthorized]>.status_code
- `tests/api/test_features_board.py::test_feature_board_called_with_space_id`: tests/api/test_features_board.py:257: in test_feature_board_called_with_space_id     mock_store.feature_board.assert_called_once_with("my-space") /usr/local/lib/python3.12/unittest/mock.py:960: in ass
- `tests/api/test_features_board.py::test_feature_items_absent_from_tasks_board`: tests/api/test_features_board.py:304: in test_feature_items_absent_from_tasks_board     assert feat_resp.status_code == 200 E   assert 401 == 200 E    +  where 401 = <Response [401 Unauthorized]>.stat
- `tests/api/test_features_board.py::test_mirror_not_called_on_get`: tests/api/test_features_board.py:346: in test_mirror_not_called_on_get     assert response.status_code == 200 E   assert 401 == 200 E    +  where 401 = <Response [401 Unauthorized]>.status_code
- `tests/api/test_features_board.py::test_404_when_space_missing`: tests/api/test_features_board.py:372: in test_404_when_space_missing     assert response.status_code == 404, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 == 404 E    +  w
- `tests/api/test_features_board.py::test_422_when_space_id_empty`: tests/api/test_features_board.py:395: in test_422_when_space_id_empty     assert response.status_code == 422, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 == 422 E    +  
- `tests/api/test_features_board.py::test_response_has_five_lanes`: tests/api/test_features_board.py:428: in test_response_has_five_lanes     assert response.status_code == 200 E   assert 401 == 200 E    +  where 401 = <Response [401 Unauthorized]>.status_code
- `tests/api/test_features_board.py::test_lane_items_contain_task_summary_fields`: tests/api/test_features_board.py:463: in test_lane_items_contain_task_summary_fields     assert response.status_code == 200 E   assert 401 == 200 E    +  where 401 = <Response [401 Unauthorized]>.stat
- `tests/api/test_features_board.py::test_lane_items_contain_realizing_count`: tests/api/test_features_board.py:503: in test_lane_items_contain_realizing_count     assert response.status_code == 200 E   assert 401 == 200 E    +  where 401 = <Response [401 Unauthorized]>.status_c
- `tests/api/test_features_board.py::test_lane_items_default_realizing_count_zero`: tests/api/test_features_board.py:533: in test_lane_items_default_realizing_count_zero     assert response.status_code == 200 E   assert 401 == 200 E    +  where 401 = <Response [401 Unauthorized]>.sta
- `tests/api/test_features_create.py::test_create_feature_success_201`: tests/api/test_features_create.py:148: in test_create_feature_success_201     assert response.status_code == 201, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 == 201 E   
- `tests/api/test_features_create.py::test_create_feature_key_format_feat`: tests/api/test_features_create.py:169: in test_create_feature_key_format_feat     assert response.status_code == 201 E   assert 401 == 201 E    +  where 401 = <Response [401 Unauthorized]>.status_code
- `tests/api/test_features_create.py::test_create_fix_key_format`: tests/api/test_features_create.py:192: in test_create_fix_key_format     assert response.status_code == 201 E   assert 401 == 201 E    +  where 401 = <Response [401 Unauthorized]>.status_code
- `tests/api/test_features_create.py::test_mirror_called_once_on_success`: tests/api/test_features_create.py:217: in test_mirror_called_once_on_success     assert response.status_code == 201 E   assert 401 == 201 E    +  where 401 = <Response [401 Unauthorized]>.status_code
- `tests/api/test_features_create.py::test_mirror_not_called_on_400_no_git`: tests/api/test_features_create.py:241: in test_mirror_not_called_on_400_no_git     assert response.status_code == 400 E   assert 401 == 400 E    +  where 401 = <Response [401 Unauthorized]>.status_cod
- `tests/api/test_features_create.py::test_mirror_not_called_on_404_missing_space`: tests/api/test_features_create.py:262: in test_mirror_not_called_on_404_missing_space     assert response.status_code == 404 E   assert 401 == 404 E    +  where 401 = <Response [401 Unauthorized]>.sta
- `tests/api/test_features_create.py::test_400_when_no_git_repo_url`: tests/api/test_features_create.py:282: in test_400_when_no_git_repo_url     assert response.status_code == 400 E   assert 401 == 400 E    +  where 401 = <Response [401 Unauthorized]>.status_code
- `tests/api/test_features_create.py::test_404_when_space_missing`: tests/api/test_features_create.py:302: in test_404_when_space_missing     assert response.status_code == 404 E   assert 401 == 404 E    +  where 401 = <Response [401 Unauthorized]>.status_code
- `tests/api/test_features_create.py::test_invalid_type_returns_422`: tests/api/test_features_create.py:319: in test_invalid_type_returns_422     assert response.status_code == 422 E   assert 401 == 422 E    +  where 401 = <Response [401 Unauthorized]>.status_code
- `tests/api/test_features_create.py::test_priority_out_of_range_returns_422`: tests/api/test_features_create.py:331: in test_priority_out_of_range_returns_422     assert response.status_code == 422 E   assert 401 == 422 E    +  where 401 = <Response [401 Unauthorized]>.status_c
- `tests/api/test_features_create.py::test_missing_title_returns_422`: tests/api/test_features_create.py:343: in test_missing_title_returns_422     assert response.status_code == 422 E   assert 401 == 422 E    +  where 401 = <Response [401 Unauthorized]>.status_code
- `tests/api/test_features_create.py::test_response_contains_feature_fields`: tests/api/test_features_create.py:363: in test_response_contains_feature_fields     assert response.status_code == 201 E   assert 401 == 201 E    +  where 401 = <Response [401 Unauthorized]>.status_co
- `tests/api/test_features_create.py::test_response_realizing_items_empty_on_create`: tests/api/test_features_create.py:388: in test_response_realizing_items_empty_on_create     assert response.status_code == 201 E   assert 401 == 201 E    +  where 401 = <Response [401 Unauthorized]>.s
- `tests/api/test_features_create.py::test_storage_error_returns_400`: tests/api/test_features_create.py:427: in test_storage_error_returns_400     assert response.status_code == 400 E   assert 401 == 400 E    +  where 401 = <Response [401 Unauthorized]>.status_code
- `tests/api/test_features_create.py::test_unknown_space_on_create_returns_404`: tests/api/test_features_create.py:452: in test_unknown_space_on_create_returns_404     assert response.status_code == 404 E   assert 401 == 404 E    +  where 401 = <Response [401 Unauthorized]>.status
- `tests/api/test_features_create.py::test_storage_error_on_create_includes_message`: tests/api/test_features_create.py:472: in test_storage_error_on_create_includes_message     assert response.status_code == 400 E   assert 401 == 400 E    +  where 401 = <Response [401 Unauthorized]>.s
- `tests/api/test_features_create.py::test_log_mirror_error_callback_logs_on_exception`: async def functions are not natively supported. You need to install a suitable plugin for your async framework, for example:   - anyio   - pytest-asyncio   - pytest-tornasync   - pytest-trio   - pytes
- `tests/api/test_features_create.py::test_brief_passed_to_store_create`: tests/api/test_features_create.py:552: in test_brief_passed_to_store_create     assert response.status_code == 201 E   assert 401 == 201 E    +  where 401 = <Response [401 Unauthorized]>.status_code
- `tests/api/test_features_delete.py::test_delete_feature_returns_501`: tests/api/test_features_delete.py:48: in test_delete_feature_returns_501     assert response.status_code == 501 E   assert 401 == 501 E    +  where 401 = <Response [401 Unauthorized]>.status_code
- `tests/api/test_features_delete.py::test_delete_feature_501_for_any_id`: tests/api/test_features_delete.py:61: in test_delete_feature_501_for_any_id     assert response.status_code == 501, f"Expected 501 for id={feat_id!r}, got {response.status_code}" E   AssertionError: E
- `tests/api/test_features_edit.py::test_patch_feature_title_and_brief_success`: tests/api/test_features_edit.py:151: in test_patch_feature_title_and_brief_success     assert response.status_code == 200, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 ==
- `tests/api/test_features_edit.py::test_patch_feature_title_only`: tests/api/test_features_edit.py:175: in test_patch_feature_title_only     assert response.status_code == 200, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 == 200 E    +  
- `tests/api/test_features_edit.py::test_patch_feature_brief_only`: tests/api/test_features_edit.py:196: in test_patch_feature_brief_only     assert response.status_code == 200, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 == 200 E    +  
- `tests/api/test_features_edit.py::test_patch_feature_key_unchanged`: tests/api/test_features_edit.py:212: in test_patch_feature_key_unchanged     assert response.status_code == 200, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 == 200 E    
- `tests/api/test_features_edit.py::test_patch_feature_updated_at_bumped`: tests/api/test_features_edit.py:235: in test_patch_feature_updated_at_bumped     assert response.status_code == 200, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 == 200 E
- `tests/api/test_features_edit.py::test_patch_feature_mirror_reason_is_edit`: tests/api/test_features_edit.py:256: in test_patch_feature_mirror_reason_is_edit     assert response.status_code == 200, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 == 2
- `tests/api/test_features_edit.py::test_patch_fix_type_succeeds`: tests/api/test_features_edit.py:281: in test_patch_fix_type_succeeds     assert response.status_code == 200, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 == 200 E    +  w
- `tests/api/test_features_edit.py::test_patch_feature_not_found_returns_404`: tests/api/test_features_edit.py:308: in test_patch_feature_not_found_returns_404     assert response.status_code == 404, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 == 4
- `tests/api/test_features_edit.py::test_patch_wrong_type_returns_404`: tests/api/test_features_edit.py:341: in test_patch_wrong_type_returns_404     assert response.status_code == 404, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 == 404 E   
- `tests/api/test_features_edit.py::test_patch_feature_task_not_found_from_update_returns_404`: tests/api/test_features_edit.py:365: in test_patch_feature_task_not_found_from_update_returns_404     assert response.status_code == 404, response.text E   AssertionError: {"detail":"Unauthorized"} E 
- `tests/api/test_features_edit.py::test_patch_feature_space_not_found_returns_404`: tests/api/test_features_edit.py:395: in test_patch_feature_space_not_found_returns_404     assert response.status_code == 404, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 40
- `tests/api/test_features_edit.py::test_patch_feature_storage_error_from_update_returns_400`: tests/api/test_features_edit.py:426: in test_patch_feature_storage_error_from_update_returns_400     assert response.status_code == 400, response.text E   AssertionError: {"detail":"Unauthorized"} E  
- `tests/api/test_features_edit.py::test_patch_feature_empty_body_succeeds`: tests/api/test_features_edit.py:474: in test_patch_feature_empty_body_succeeds     assert response.status_code == 200, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 == 200
- `tests/api/test_features_edit.py::test_patch_feature_response_has_realizing_items`: tests/api/test_features_edit.py:490: in test_patch_feature_response_has_realizing_items     assert response.status_code == 200, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 4
- `tests/api/test_features_process.py::test_process_feature_success_200`: tests/api/test_features_process.py:134: in test_process_feature_success_200     assert response.status_code == 200, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 401 == 200 E 
- `tests/api/test_features_process.py::test_process_feature_response_is_feature_read`: tests/api/test_features_process.py:158: in test_process_feature_response_is_feature_read     assert response.status_code == 200, response.text E   AssertionError: {"detail":"Unauthorized"} E   assert 
- `tests/api/test_features_process.py::test_process_feature_transition_called_with_processing_state`: tests/api/test_features_process.py:184: in test_process_feature_transition_called_with_processing_state     assert response.status_code == 200, response.text E   AssertionError: {"detail":"Unauthorize
- `tests/api/test_features_process.py::test_process_feature_transition_called_with_user_transitions`: tests/api/test_features_process.py:215: in test_process_feature_transition_called_with_user_transitions     assert response.status_code == 200, response.text E   AssertionError: {"detail":"Unauthorize

## Assumptions

- Test suite is at `backend/tests/` (pytest) and `frontend/` (vitest when present).
- `tests_added: 0` — tester is a gate runner only; test authoring belongs to test-architect.
- `tool_calls: 9` is a fixed estimate; Bash-based agents cannot count tool invocations dynamically.
- `inputs_used: []` — the tester runs shell commands against the live test suite, not Read-tool file accesses; R4 is satisfied trivially (0 + 0 >= 0).

## Open questions

- None.

## Next consumer brief

Gate result: **FAIL** — 2813p / 663f / 836e, coverage 50.5%.
Fix 1499 failing/errored test(s) before advancing the pipeline. See ## Failures for details.
