"""
Smoke test: verifies the full lib.gate -> lib.verify call chain.

gate.py imports split_frontmatter and verify from lib.verify. This smoke test
confirms:
1. lib.gate is importable (its lib.verify imports resolve correctly)
2. runGate is callable and produces expected results with correct GateResult shape
3. lib.verify.verify is the function actually used by gate.py internally
   (gate_mod._cc_verify is lib.verify.verify)
4. lib.verify.split_frontmatter is the function actually used by gate.py internally
"""
from __future__ import annotations

import pathlib
import textwrap

import pytest


# ---------------------------------------------------------------------------
# Test 1 — import chain
# ---------------------------------------------------------------------------


def test_gate_importable():
    """lib.gate should be importable; this confirms lib.verify is on sys.path."""
    import lib.gate  # noqa: F401

    assert hasattr(lib.gate, "runGate")
    assert callable(lib.gate.runGate)


def test_gate_imports_from_lib_verify():
    """gate.py's internal verify and split_frontmatter come from lib.verify after I4."""
    import lib.verify
    import lib.gate as gate_mod

    # After I4, gate.py imports:
    #   from lib.verify import split_frontmatter
    #   from lib.verify import verify as _cc_verify
    # Confirm the module-level bindings are identical objects (not just equal).
    assert gate_mod._cc_verify is lib.verify.verify, (
        "gate._cc_verify should be lib.verify.verify after I4 import flip"
    )
    assert gate_mod.split_frontmatter is lib.verify.split_frontmatter, (
        "gate.split_frontmatter should be lib.verify.split_frontmatter after I4 import flip"
    )


# ---------------------------------------------------------------------------
# Test 2 — runGate importable as a named symbol
# ---------------------------------------------------------------------------


def test_rungate_importable_as_named_symbol():
    """runGate should be importable by name from lib.gate."""
    from lib.gate import runGate  # noqa: F401

    assert callable(runGate)


# ---------------------------------------------------------------------------
# Test 3 — runGate returns GateResult with no checks (empty gate)
# ---------------------------------------------------------------------------


def test_rungate_empty_gate_returns_proceed():
    """runGate with zero checks should return decision='proceed'."""
    from lib.gate import runGate, GateResult

    gate: dict = {"id": "smoke-empty", "checks": []}
    result = runGate(gate, [], space=None)

    assert isinstance(result, GateResult)
    assert result.decision == "proceed"
    assert result.errors == []


# ---------------------------------------------------------------------------
# Test 4 — runGate with a valid artifact and a traceability check (no required_ids)
# ---------------------------------------------------------------------------


def test_rungate_traceability_no_required_ids(tmp_path: pathlib.Path):
    """runGate traceability check with no required_ids should return proceed."""
    from lib.gate import runGate, GateResult

    # Create a minimal research-class artifact with YAML frontmatter
    artifact_content = textwrap.dedent("""\
        ---
        cc_version: '1.0'
        agent: pipeline-scout
        slug: smoke-test-rungate
        phase: research
        status: done
        confidence: 0.9
        inputs_used:
          - test-file.py
        outputs_produced:
          - .cronos/pipeline/smoke-test-rungate/scout-report-smoke-test-rungate.md
        blockers: []
        next_consumer: analysis
        metrics:
          tool_calls: 3
          files_read: 2
          memory_hits: 0
        ---

        ## Summary

        Smoke test artifact for SG7 runGate chain validation.

        ## Findings

        - lib.verify is now the canonical verifier.
        - gate.py successfully imports from lib.verify after I4.
    """)

    pipeline_dir = tmp_path / ".cronos" / "pipeline" / "smoke-test-rungate"
    pipeline_dir.mkdir(parents=True)
    artifact_path = pipeline_dir / "scout-report-smoke-test-rungate.md"
    artifact_path.write_text(artifact_content, encoding="utf-8")

    gate: dict = {
        "id": "smoke-traceability",
        "checks": [
            {
                "type": "traceability",
                "artifact_path": str(artifact_path),
                "required_ids": [],
            }
        ],
    }

    result = runGate(gate, [str(artifact_path)], space=str(tmp_path))

    assert isinstance(result, GateResult)
    assert result.decision == "proceed", (
        f"Expected 'proceed', got {result.decision!r}. Errors: {result.errors}"
    )


# ---------------------------------------------------------------------------
# Test 5 — runGate with acceptance check on artifact with no traceability[]
# ---------------------------------------------------------------------------


def test_rungate_acceptance_no_traceability(tmp_path: pathlib.Path):
    """runGate acceptance check on artifact with no traceability[] returns proceed."""
    from lib.gate import runGate, GateResult

    artifact_content = textwrap.dedent("""\
        ---
        cc_version: '1.0'
        agent: pipeline-scout
        slug: smoke-acceptance-test
        phase: research
        status: done
        confidence: 0.85
        inputs_used:
          - some-file.py
        outputs_produced:
          - .cronos/pipeline/smoke-acceptance-test/scout-report-smoke-acceptance-test.md
        blockers: []
        next_consumer: analysis
        metrics:
          tool_calls: 2
          files_read: 1
          memory_hits: 0
        ---

        ## Summary

        Minimal artifact with no traceability block.
    """)

    artifact_path = tmp_path / "scout-report-smoke-acceptance-test.md"
    artifact_path.write_text(artifact_content, encoding="utf-8")

    gate: dict = {
        "id": "smoke-acceptance",
        "checks": [
            {
                "type": "acceptance",
                "artifact_path": str(artifact_path),
            }
        ],
    }

    result = runGate(gate, [str(artifact_path)], space=str(tmp_path))

    assert isinstance(result, GateResult)
    # No traceability[] present → acceptance check returns proceed (advisory pass)
    assert result.decision == "proceed", (
        f"Expected 'proceed', got {result.decision!r}. Errors: {result.errors}"
    )


# ---------------------------------------------------------------------------
# Test 6 — GateResult dataclass structure
# ---------------------------------------------------------------------------


def test_gateresult_structure():
    """GateResult should have decision, errors, evidence and to_dict()."""
    from lib.gate import GateResult

    r = GateResult(decision="proceed", errors=[], evidence={"foo": "bar"})
    assert r.decision == "proceed"
    assert r.errors == []
    assert r.evidence == {"foo": "bar"}

    d = r.to_dict()
    assert d["decision"] == "proceed"
    assert d["errors"] == []
    assert d["evidence"] == {"foo": "bar"}


# ---------------------------------------------------------------------------
# Test 7 — runGate handles unknown check type gracefully (fails, not crashes)
# ---------------------------------------------------------------------------


def test_rungate_unknown_check_type_returns_fail():
    """runGate with an unknown check type should return decision='fail', not raise."""
    from lib.gate import runGate, GateResult

    gate: dict = {
        "id": "smoke-unknown-check",
        "checks": [{"type": "nonexistent_check_type"}],
    }

    result = runGate(gate, [], space=None)

    assert isinstance(result, GateResult)
    assert result.decision == "fail"
    assert any("unknown check type" in e for e in result.errors)
