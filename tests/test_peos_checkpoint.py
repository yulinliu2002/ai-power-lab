"""Tests for peos/checkpoint.py (SPEC-007 PEOS Durable Run Resume V1)."""

from __future__ import annotations

import json

import pytest

from peos.checkpoint import (
    CheckpointError,
    CheckpointManager,
    CheckpointWriter,
    RunCheckpoint,
    load_checkpoint,
)


def test_write_then_load_round_trips_every_field(tmp_path):
    writer = CheckpointWriter(tmp_path, "run1")
    cp = RunCheckpoint(
        schema_version="1", run_id="run1", resume_generation=0,
        created_at="t0", updated_at="t0", task="do the thing",
        authoritative_baseline="deadbeef", governing_spec_relative_path="docs/specifications/SPEC-001.md",
        governing_spec_content_hash="a" * 64, governing_spec_source="auto_detected",
        governing_spec_original_path="", effective_max_cycles=3,
        active_phase="PLANNING", active_phase_state="ENTERED", last_safely_completed_phase="",
        current_cycle=0,
        workspace_root_relative_path=".peos/runs/run1/candidate/workspace",
        workspace_home_dir_relative_path=".peos/runs/run1/candidate/home",
        workspace_baseline_commit="cafebabe", current_workspace_snapshot_identity="x" * 10,
        acceptance_criteria_ids=("AC-001", "AC-002"),
    )
    writer.write(cp)

    loaded, error = load_checkpoint(tmp_path, "run1")
    assert error is None
    assert loaded == cp


def test_run_directory_creation_is_exclusive_no_reuse(tmp_path):
    """SPEC-007: the checkpoint writer -- not the ledger writer -- is now
    the one place a genuine `run_id` collision is caught and rejected
    (its first write always happens first in a real run's lifecycle)."""
    writer1 = CheckpointWriter(tmp_path, "run1")
    writer1.write(RunCheckpoint(
        schema_version="1", run_id="run1", resume_generation=0, created_at="t0", updated_at="t0",
        task="", authoritative_baseline="", governing_spec_relative_path="", governing_spec_content_hash="",
        governing_spec_source="auto_detected", governing_spec_original_path="", effective_max_cycles=1,
        active_phase="PLANNING", active_phase_state="ENTERED", last_safely_completed_phase="",
        current_cycle=0, workspace_root_relative_path="", workspace_home_dir_relative_path="",
        workspace_baseline_commit="", current_workspace_snapshot_identity="",
    ))

    writer2 = CheckpointWriter(tmp_path, "run1")
    with pytest.raises(CheckpointError):
        writer2.write(RunCheckpoint(
            schema_version="1", run_id="run1", resume_generation=0, created_at="t0", updated_at="t0",
            task="", authoritative_baseline="", governing_spec_relative_path="", governing_spec_content_hash="",
            governing_spec_source="auto_detected", governing_spec_original_path="", effective_max_cycles=1,
            active_phase="PLANNING", active_phase_state="ENTERED", last_safely_completed_phase="",
            current_cycle=0, workspace_root_relative_path="", workspace_home_dir_relative_path="",
            workspace_baseline_commit="", current_workspace_snapshot_identity="",
        ))


def test_load_checkpoint_returns_none_none_when_genuinely_missing(tmp_path):
    checkpoint, error = load_checkpoint(tmp_path, "no-such-run")
    assert checkpoint is None
    assert error is None


def test_load_checkpoint_rejects_hand_edited_corruption_distinctly_from_missing(tmp_path):
    """SPEC-007 AC-014: a corrupted checkpoint.json must be rejected
    (non-None error), never silently treated the same as "missing"."""
    writer = CheckpointWriter(tmp_path, "run1")
    writer.write(RunCheckpoint(
        schema_version="1", run_id="run1", resume_generation=0, created_at="t0", updated_at="t0",
        task="", authoritative_baseline="", governing_spec_relative_path="", governing_spec_content_hash="",
        governing_spec_source="auto_detected", governing_spec_original_path="", effective_max_cycles=1,
        active_phase="PLANNING", active_phase_state="ENTERED", last_safely_completed_phase="",
        current_cycle=0, workspace_root_relative_path="", workspace_home_dir_relative_path="",
        workspace_baseline_commit="", current_workspace_snapshot_identity="",
    ))
    checkpoint_path = tmp_path / ".peos" / "runs" / "run1" / "checkpoint.json"
    checkpoint_path.write_text("{not valid json", encoding="utf-8")

    checkpoint, error = load_checkpoint(tmp_path, "run1")
    assert checkpoint is None
    assert error is not None


def test_load_checkpoint_rejects_mismatched_schema_version(tmp_path):
    writer = CheckpointWriter(tmp_path, "run1")
    cp = RunCheckpoint(
        schema_version="1", run_id="run1", resume_generation=0, created_at="t0", updated_at="t0",
        task="", authoritative_baseline="", governing_spec_relative_path="", governing_spec_content_hash="",
        governing_spec_source="auto_detected", governing_spec_original_path="", effective_max_cycles=1,
        active_phase="PLANNING", active_phase_state="ENTERED", last_safely_completed_phase="",
        current_cycle=0, workspace_root_relative_path="", workspace_home_dir_relative_path="",
        workspace_baseline_commit="", current_workspace_snapshot_identity="",
    )
    writer.write(cp)
    checkpoint_path = tmp_path / ".peos" / "runs" / "run1" / "checkpoint.json"
    data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    data["schema_version"] = "999"
    checkpoint_path.write_text(json.dumps(data), encoding="utf-8")

    checkpoint, error = load_checkpoint(tmp_path, "run1")
    assert checkpoint is None
    assert error is not None


def test_serialize_never_uses_dataclasses_asdict_on_the_whole_checkpoint():
    """SPEC-007 Decision 8. Codex implementation review (confirmed,
    minor): an earlier revision of this test only compared the
    allowlist against the dataclass's own field list, which is trivially
    true by construction and can never detect bypassed sanitization or
    a whole-checkpoint `asdict`/`vars`/`__dict__` call. Replaced with a
    real mechanism check: a secret-shaped, over-length string placed in
    a free-text field must come back redacted and bounded in the
    *serialized* output, proving `serialize_checkpoint` actually routes
    every string field through `sanitize_identity_text` rather than
    passing it through unchanged (which a generic `asdict`/`vars` call
    would do)."""
    import dataclasses

    from peos.checkpoint import _ALLOWED_FIELDS, serialize_checkpoint
    from peos.diagnostics import MAX_DIAGNOSTIC_CHARS

    assert _ALLOWED_FIELDS == frozenset(f.name for f in dataclasses.fields(RunCheckpoint))

    secret_like = "sk-" + "a" * 60  # matches diagnostics.py's own secret-token pattern
    cp = RunCheckpoint(
        schema_version="1", run_id="run1", resume_generation=0, created_at="t0", updated_at="t0",
        task=f"do the thing with {secret_like} embedded", authoritative_baseline="", governing_spec_relative_path="",
        governing_spec_content_hash="", governing_spec_source="auto_detected", governing_spec_original_path="",
        effective_max_cycles=1, active_phase="PLANNING", active_phase_state="ENTERED",
        last_safely_completed_phase="", current_cycle=0, workspace_root_relative_path="",
        workspace_home_dir_relative_path="", workspace_baseline_commit="", current_workspace_snapshot_identity="",
        terminal_gate_reason="x" * (MAX_DIAGNOSTIC_CHARS + 500),
    )
    payload = serialize_checkpoint(cp)
    assert secret_like not in payload["task"]
    assert "[REDACTED]" in payload["task"]
    assert len(payload["terminal_gate_reason"]) <= MAX_DIAGNOSTIC_CHARS


def test_checkpoint_manager_enter_then_complete_persists_full_state(tmp_path):
    manager = CheckpointManager(tmp_path, "run1")
    manager.enter("PLANNING", task="implement X", governing_spec_source="auto_detected", governing_spec_original_path="")
    loaded, error = load_checkpoint(tmp_path, "run1")
    assert error is None
    assert loaded.active_phase == "PLANNING"
    assert loaded.active_phase_state == "ENTERED"
    assert loaded.last_safely_completed_phase == ""
    assert loaded.task == "implement X"

    manager.complete("PLANNING", effective_max_cycles=3)
    loaded2, error2 = load_checkpoint(tmp_path, "run1")
    assert error2 is None
    assert loaded2.active_phase_state == "COMPLETED"
    assert loaded2.last_safely_completed_phase == "PLANNING"
    assert loaded2.effective_max_cycles == 3
    # Prior fields are preserved, not reset, by the accumulating manager.
    assert loaded2.task == "implement X"


def test_checkpoint_manager_terminal_sets_outcome_and_gate_fields(tmp_path):
    manager = CheckpointManager(tmp_path, "run1")
    manager.enter("PLANNING", task="t")
    manager.terminal("HUMAN_GATE", gate_id="6", gate_reason="needs a human")
    loaded, _ = load_checkpoint(tmp_path, "run1")
    assert loaded.terminal_outcome == "HUMAN_GATE"
    assert loaded.terminal_gate_id == "6"
    assert loaded.terminal_gate_reason == "needs a human"


def test_checkpoint_manager_seed_from_restores_nested_dataclasses(tmp_path):
    from peos.checkpoint import ReconciliationOperation

    manager = CheckpointManager(tmp_path, "run1")
    manager.enter("PLANNING", task="t")
    manager.complete(
        "PLANNING",
        reconciliation_manifest=(ReconciliationOperation(relative_path="a.py", action="write", target_content_hash="h1"),),
        decision_identities=(("docs/decisions/0001.md", "h2"),),
    )
    checkpoint = manager.current

    manager2 = CheckpointManager(tmp_path, "run1", require_fresh=False)
    manager2.seed_from(checkpoint)
    assert manager2.current.reconciliation_manifest == checkpoint.reconciliation_manifest
    assert manager2.current.decision_identities == checkpoint.decision_identities
    # Further writes build on the seeded state, not a fresh empty one.
    manager2.enter("CLAUDE_IMPLEMENTATION")
    reloaded, _ = load_checkpoint(tmp_path, "run1")
    assert reloaded.reconciliation_manifest == checkpoint.reconciliation_manifest
    assert reloaded.active_phase == "CLAUDE_IMPLEMENTATION"
