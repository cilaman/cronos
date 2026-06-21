---
cc_version: "1.0"
agent: tester
slug: harness-run-test-harness
phase: test
status: done
confidence: 0.9
inputs_used: []
outputs_produced:
  - .cronos/pipeline/harness-run-test-harness/test-report-harness-run-test-harness.md
blockers: []
next_consumer: user
gate_decision: fail
tests_added: 0
passed: 3920
failed: 20
errors: 0
coverage: 85.07
metrics:
  tool_calls: 9
  files_read: 0
  memory_hits: 0
  tests_run: 3940
---

## Summary

Gate run for goal `harness-run-test-harness` in space `cronos-development`. 3920 tests passed, 20 failed, 0 errored, 0 skipped. Coverage: 85.1%. Gate decision: **FAIL**.

## Gate result

| Metric | Value |
|--------|-------|
| Passed | 3920 |
| Failed | 20 |
| Errors | 0 |
| Skipped | 0 |
| Coverage | 85.1% |
| Exit code | 1 |
| Gate decision | **fail** |

## Failures

- `tests/test_api_plugins.py::test_get_plugins_happy`: tests/test_api_plugins.py:55: in test_get_plugins_happy     resp = await async_client.get("/api/plugins")            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ /usr/local/lib/python3.12/site-packages/http
- `tests/test_api_plugins.py::test_install_plugin_happy`: tests/test_api_plugins.py:91: in test_install_plugin_happy     assert resp.status_code == 200 E   assert 422 == 200 E    +  where 422 = <Response [422 Unprocessable Entity]>.status_code
- `tests/test_api_plugins.py::test_uninstall_plugin_happy`: tests/test_api_plugins.py:140: in test_uninstall_plugin_happy     assert resp.status_code == 200 E   assert 422 == 200 E    +  where 422 = <Response [422 Unprocessable Entity]>.status_code
- `tests/test_api_plugins.py::test_enable_plugin_happy`: tests/test_api_plugins.py:171: in test_enable_plugin_happy     assert resp.status_code == 200 E   assert 422 == 200 E    +  where 422 = <Response [422 Unprocessable Entity]>.status_code
- `tests/test_api_plugins.py::test_disable_plugin_happy`: tests/test_api_plugins.py:202: in test_disable_plugin_happy     assert resp.status_code == 200 E   assert 422 == 200 E    +  where 422 = <Response [422 Unprocessable Entity]>.status_code
- `tests/test_api_plugins.py::test_add_marketplace_happy`: tests/test_api_plugins.py:242: in test_add_marketplace_happy     assert resp.status_code == 200 E   assert 422 == 200 E    +  where 422 = <Response [422 Unprocessable Entity]>.status_code
- `tests/test_api_plugins.py::test_remove_marketplace_happy`: tests/test_api_plugins.py:305: in test_remove_marketplace_happy     assert resp.status_code == 200 E   assert 422 == 200 E    +  where 422 = <Response [422 Unprocessable Entity]>.status_code
- `tests/test_no_pat_in_traces.py::test_committed_traces_contain_no_pat`: tests/test_no_pat_in_traces.py:69: in test_committed_traces_contain_no_pat     assert not offenders, ( E   AssertionError: Secret patterns found in committed trace JSONs: E     .cronos/traces/2026-06-
- `tests/test_plugin_models.py::TestPluginComponent::test_invalid_kind_raises`: tests/test_plugin_models.py:27: in test_invalid_kind_raises     with pytest.raises(Exception):          ^^^^^^^^^^^^^^^^^^^^^^^^ E   Failed: DID NOT RAISE <class 'Exception'>
- `tests/test_plugin_models.py::TestPluginEntry::test_minimal`: tests/test_plugin_models.py:37: in test_minimal     p = PluginEntry(id="myplugin@default", name="myplugin")         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E   pydantic_core._pydantic_core
- `tests/test_plugin_models.py::TestPluginEntry::test_full_fields`: tests/test_plugin_models.py:64: in test_full_fields     p = PluginEntry( E   pydantic_core._pydantic_core.ValidationError: 1 validation error for PluginEntry E   components E     Field required [type=
- `tests/test_plugin_models.py::TestMarketplacePluginEntry::test_minimal`: tests/test_plugin_models.py:90: in test_minimal     e = MarketplacePluginEntry(pluginId="myplugin", name="My Plugin")         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E   pydantic
- `tests/test_plugin_models.py::TestPluginsResponse::test_empty_defaults`: tests/test_plugin_models.py:136: in test_empty_defaults     r = PluginsResponse()         ^^^^^^^^^^^^^^^^^ E   pydantic_core._pydantic_core.ValidationError: 3 validation errors for PluginsResponse E 
- `tests/test_plugin_models.py::TestPluginsResponse::test_with_data`: tests/test_plugin_models.py:142: in test_with_data     plugin = PluginEntry(id="p@m", name="p")              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E   pydantic_core._pydantic_core.ValidationError: 3 validat
- `tests/test_plugin_models.py::TestPluginsResponse::test_serialization_roundtrip`: tests/test_plugin_models.py:152: in test_serialization_roundtrip     installed=[PluginEntry(id="x@y", name="x", enabled=True)],                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E   pydanti
- `tests/test_tools_plugins.py::TestMutationFunctions::test_install_valid_id`: tests/test_tools_plugins.py:304: in test_install_valid_id     empty_response = PluginsResponse()                      ^^^^^^^^^^^^^^^^^ E   pydantic_core._pydantic_core.ValidationError: 3 validation e
- `tests/test_tools_plugins.py::TestMutationFunctions::test_uninstall_valid_id`: tests/test_tools_plugins.py:315: in test_uninstall_valid_id     empty_response = PluginsResponse()                      ^^^^^^^^^^^^^^^^^ E   pydantic_core._pydantic_core.ValidationError: 3 validation
- `tests/test_tools_plugins.py::TestMutationFunctions::test_enable_valid_id`: tests/test_tools_plugins.py:326: in test_enable_valid_id     empty_response = PluginsResponse()                      ^^^^^^^^^^^^^^^^^ E   pydantic_core._pydantic_core.ValidationError: 3 validation er
- `tests/test_tools_plugins.py::TestMutationFunctions::test_disable_valid_id`: tests/test_tools_plugins.py:337: in test_disable_valid_id     empty_response = PluginsResponse()                      ^^^^^^^^^^^^^^^^^ E   pydantic_core._pydantic_core.ValidationError: 3 validation e
- `tests/test_tools_plugins.py::TestMutationLockSerialization::test_concurrent_installs_serialized`: tests/test_tools_plugins.py:392: in test_concurrent_installs_serialized     empty_response = PluginsResponse()                      ^^^^^^^^^^^^^^^^^ E   pydantic_core._pydantic_core.ValidationError: 

## Assumptions

- Test suite is at `backend/tests/` (pytest) and `frontend/` (vitest when present).
- `tests_added: 0` — tester is a gate runner only; test authoring belongs to test-architect.
- `tool_calls: 9` is a fixed estimate; Bash-based agents cannot count tool invocations dynamically.
- `inputs_used: []` — the tester runs shell commands against the live test suite, not Read-tool file accesses; R4 is satisfied trivially (0 + 0 >= 0).

## Open questions

- None.

## Next consumer brief

Gate result: **FAIL** — 3920p / 20f / 0e, coverage 85.1%.
Fix 20 failing/errored test(s) before advancing the pipeline. See ## Failures for details.
