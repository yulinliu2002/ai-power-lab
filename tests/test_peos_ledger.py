"""Tests for the Run Ledger (peos/ledger.py, SPEC-004 Requirements 18-20).

AC-11 (secret injection), AC-12/AC-30 (persistence + atomic write), AC-13
(.gitignore + git status), AC-29/AC-33-style symlink containment, AC-31
(retention).
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from peos.ledger import (
    DEFAULT_RETENTION,
    LedgerError,
    LedgerWriter,
    RunLedger,
    cleanup_old_runs,
)


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)


def _make_ledger(run_id, outcome=None, created_at="2024-01-01T00:00:00+00:00", **overrides):
    defaults = dict(
        run_id=run_id, schema_version="1", created_at=created_at, updated_at=created_at,
        max_cycles=3, authoritative_baseline="abc123", governing_spec_identity="spec:hash",
        active_phase="Planning", last_completed_phase="", current_cycle=0, outcome=outcome,
    )
    defaults.update(overrides)
    return RunLedger(**defaults)


# --- AC-11: secret injection across every required injection point ------

@pytest.mark.parametrize("field_name", [
    "authoritative_baseline", "governing_spec_identity", "gate_reason",
])
def test_ledger_never_persists_a_secret_planted_in_a_scalar_field(tmp_path, field_name):
    secret = "sk-liveAbCdEfGhIjKlMnOpQrSt"
    overrides = {field_name: f"value containing {secret} inline"}
    if field_name == "gate_reason":
        overrides["outcome"] = "FAILED"
    ledger = _make_ledger("run1", **overrides)
    writer = LedgerWriter(tmp_path, "run1")
    path = writer.write(ledger)
    text = path.read_text(encoding="utf-8")
    assert secret not in text
    assert "[REDACTED]" in text


@pytest.mark.parametrize("field_name", [
    "sanitized_phase_history", "sanitized_register_state",
    "sanitized_dispute_state", "sanitized_verification_summaries",
])
def test_ledger_never_persists_a_secret_planted_in_a_sequence_field(tmp_path, field_name):
    secret = "sk-liveAbCdEfGhIjKlMnOpQrSt"
    ledger = _make_ledger("run1", **{field_name: (f"line with {secret}",)})
    writer = LedgerWriter(tmp_path, "run1")
    path = writer.write(ledger)
    text = path.read_text(encoding="utf-8")
    assert secret not in text
    assert "[REDACTED]" in text


def test_ledger_never_writes_raw_stdout_or_stderr_fields_at_all():
    """There is no field for them -- RunLedger's allowlist structurally
    excludes raw stdout/stderr, credential values, and environment dumps.
    """
    field_names = {f for f in RunLedger.__dataclass_fields__}
    assert "stdout" not in field_names
    assert "stderr" not in field_names
    assert "raw_stdout" not in field_names
    assert "raw_stderr" not in field_names
    assert "environ" not in field_names
    assert not any("credential" in f or "token" in f for f in field_names)


# --- AC-12/AC-30: persistence, atomicity ---------------------------------

def test_ledger_is_inspectable_on_disk_after_write(tmp_path):
    writer = LedgerWriter(tmp_path, "run1")
    path = writer.write(_make_ledger("run1"))
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_id"] == "run1"
    assert data["active_phase"] == "Planning"


def test_ledger_write_is_atomic_no_temp_file_left_behind(tmp_path):
    writer = LedgerWriter(tmp_path, "run1")
    writer.write(_make_ledger("run1"))
    writer.write(_make_ledger("run1", outcome="APPROVED"))
    leftovers = list(writer.run_dir.glob(".ledger.json.*.tmp"))
    assert leftovers == []


def test_ledger_write_sequence_reflects_most_recently_completed_phase(tmp_path):
    writer = LedgerWriter(tmp_path, "run1")
    writer.write(_make_ledger("run1", active_phase="Planning"))
    writer.write(_make_ledger("run1", active_phase="Claude implementation"))
    data = json.loads((writer.run_dir / "ledger.json").read_text(encoding="utf-8"))
    assert data["active_phase"] == "Claude implementation"


def test_run_directory_reuse_by_a_second_ledger_writer_is_tolerated(tmp_path):
    """SPEC-007: the run directory's *exclusive*-creation guarantee (no
    reuse, no silent overwrite of another run's state) now lives in
    `peos.checkpoint.CheckpointWriter._ensure_dir` -- the checkpoint's
    own first write always happens before the ledger's first write in a
    real run's lifecycle, so it is the one place a genuine `run_id`
    collision is actually caught (see
    tests/test_peos_checkpoint.py::test_run_directory_creation_is_exclusive_no_reuse).
    A second `LedgerWriter` for the same `run_id` tolerantly reuses the
    directory the first one (or a checkpoint writer) already created --
    this is expected, not a regression, since both writers always target
    the same, single run directory for one real run."""
    writer1 = LedgerWriter(tmp_path, "run1")
    writer1.write(_make_ledger("run1"))

    writer2 = LedgerWriter(tmp_path, "run1")
    writer2.write(_make_ledger("run1", active_phase="Planning"))
    data = json.loads((writer2.run_dir / "ledger.json").read_text(encoding="utf-8"))
    assert data["active_phase"] == "Planning"


# --- AC-29-style: filesystem containment ---------------------------------

def test_symlinked_peos_runs_directory_fails_closed(tmp_path):
    real_elsewhere = tmp_path / "elsewhere"
    real_elsewhere.mkdir()
    peos_dir = tmp_path / ".peos"
    peos_dir.mkdir()
    (peos_dir / "runs").symlink_to(real_elsewhere)

    writer = LedgerWriter(tmp_path, "run1")
    with pytest.raises(LedgerError):
        writer.write(_make_ledger("run1"))
    assert list(real_elsewhere.iterdir()) == []


def test_symlinked_peos_directory_itself_fails_closed(tmp_path):
    real_elsewhere = tmp_path / "elsewhere"
    real_elsewhere.mkdir()
    (tmp_path / ".peos").symlink_to(real_elsewhere)

    writer = LedgerWriter(tmp_path, "run1")
    with pytest.raises(LedgerError):
        writer.write(_make_ledger("run1"))


def test_symlinked_run_directory_itself_fails_closed(tmp_path):
    (tmp_path / ".peos" / "runs").mkdir(parents=True)
    real_elsewhere = tmp_path / "elsewhere"
    real_elsewhere.mkdir()
    (tmp_path / ".peos" / "runs" / "run1").symlink_to(real_elsewhere)

    writer = LedgerWriter(tmp_path, "run1")
    with pytest.raises(LedgerError):
        writer.write(_make_ledger("run1"))


# --- AC-13: .gitignore + git status --------------------------------------

def test_dot_peos_runs_is_gitignored_in_this_repository():
    repo_root = Path(__file__).resolve().parent.parent
    gitignore_text = (repo_root / ".gitignore").read_text(encoding="utf-8")
    assert ".peos/runs/" in gitignore_text


def test_completed_run_directory_is_absent_from_git_status(tmp_path):
    _git(["init", "-q"], tmp_path)
    _git(["config", "user.email", "t@example.com"], tmp_path)
    _git(["config", "user.name", "T"], tmp_path)
    (tmp_path / ".gitignore").write_text(".peos/runs/\n", encoding="utf-8")
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    _git(["add", "-A"], tmp_path)
    _git(["commit", "-q", "-m", "init"], tmp_path)

    writer = LedgerWriter(tmp_path, "run1")
    writer.write(_make_ledger("run1", outcome="APPROVED"))

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(tmp_path), capture_output=True, text=True,
    ).stdout
    assert ".peos" not in status


# --- AC-31: retention -----------------------------------------------------

def test_retention_keeps_exactly_twenty_most_recent_and_preserves_active_and_foreign_dirs(tmp_path):
    (tmp_path / ".git").mkdir()
    for i in range(25):
        writer = LedgerWriter(tmp_path, f"old{i}")
        writer.write(_make_ledger(f"old{i}", outcome="FAILED", created_at=f"2024-01-{i + 1:02d}T00:00:00+00:00"))

    # The currently active run (not yet terminal) must survive regardless
    # of age, even if it is the oldest by directory name.
    active_writer = LedgerWriter(tmp_path, "active-run")
    active_writer.write(_make_ledger("active-run", outcome=None, created_at="2020-01-01T00:00:00+00:00"))

    # A foreign (non-PEOS) directory with no valid ledger must never be removed.
    foreign_dir = tmp_path / ".peos" / "runs" / "not-a-peos-run"
    foreign_dir.mkdir(parents=True)
    (foreign_dir / "some_other_file.txt").write_text("hello", encoding="utf-8")

    cleanup_old_runs(tmp_path, active_run_id="active-run", keep=DEFAULT_RETENTION)

    remaining = {p.name for p in (tmp_path / ".peos" / "runs").iterdir()}
    assert "active-run" in remaining
    assert "not-a-peos-run" in remaining
    old_remaining = {name for name in remaining if name.startswith("old")}
    assert len(old_remaining) == DEFAULT_RETENTION
    # The most recent 20 (old5..old24) survive; old0..old4 are removed.
    assert "old24" in old_remaining
    assert "old0" not in old_remaining


def test_retention_never_removes_a_directory_without_a_recognizable_ledger(tmp_path):
    runs_dir = tmp_path / ".peos" / "runs"
    runs_dir.mkdir(parents=True)
    mystery_dir = runs_dir / "mystery"
    mystery_dir.mkdir()
    (mystery_dir / "ledger.json").write_text("not valid json {{{", encoding="utf-8")

    cleanup_old_runs(tmp_path, active_run_id=None, keep=0)
    assert mystery_dir.exists()


# --- SPEC-004 remediation Finding 10: strict terminal-ledger validation --

def test_retention_ignores_a_directory_whose_ledger_outcome_is_an_arbitrary_non_null_string(tmp_path):
    """An outcome that is non-null but not one of the enumerated terminal
    outcomes (APPROVED/HUMAN_GATE/FAILED) must not count as a valid
    terminal run -- arbitrary/forged JSON with *some* non-null `outcome`
    key is not what SPEC-004 means by "terminal".
    """
    runs_dir = tmp_path / ".peos" / "runs"
    runs_dir.mkdir(parents=True)
    forged_dir = runs_dir / "forged"
    forged_dir.mkdir()
    (forged_dir / "ledger.json").write_text(
        json.dumps({
            "run_id": "forged", "schema_version": "1", "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00", "max_cycles": 1,
            "authoritative_baseline": "", "governing_spec_identity": "",
            "active_phase": "", "last_completed_phase": "", "current_cycle": 0,
            "outcome": "DEFINITELY_NOT_A_REAL_OUTCOME",
        }),
        encoding="utf-8",
    )
    cleanup_old_runs(tmp_path, active_run_id=None, keep=0)
    # Never counted as terminal, so never deleted despite keep=0.
    assert forged_dir.exists()


def test_retention_ignores_a_ledger_whose_run_id_does_not_match_its_directory(tmp_path):
    """A ledger claiming a different `run_id` than the directory it was
    found in is not trustworthy as *that* directory's terminal record --
    `LedgerWriter.write()` itself refuses to produce this (it checks
    `ledger.run_id == self._run_id`), so the mismatch is written directly
    here to exercise `cleanup_old_runs`'s own defensive validation.
    """
    run_dir = tmp_path / ".peos" / "runs" / "dir-name"
    run_dir.mkdir(parents=True)
    (run_dir / "ledger.json").write_text(
        json.dumps({
            "run_id": "a-different-run-id", "schema_version": "1",
            "created_at": "2024-01-01T00:00:00+00:00", "updated_at": "2024-01-01T00:00:00+00:00",
            "max_cycles": 1, "authoritative_baseline": "", "governing_spec_identity": "",
            "active_phase": "", "last_completed_phase": "", "current_cycle": 0,
            "outcome": "FAILED",
        }),
        encoding="utf-8",
    )
    cleanup_old_runs(tmp_path, active_run_id=None, keep=0)
    assert run_dir.exists()


def test_retention_reduces_more_than_twenty_valid_terminal_runs_to_the_cap(tmp_path):
    (tmp_path / ".git").mkdir()
    for i in range(23):
        writer = LedgerWriter(tmp_path, f"run{i}")
        writer.write(_make_ledger(f"run{i}", outcome="FAILED", created_at=f"2024-02-{i + 1:02d}T00:00:00+00:00"))

    cleanup_old_runs(tmp_path, active_run_id=None, keep=DEFAULT_RETENTION)
    remaining = {p.name for p in (tmp_path / ".peos" / "runs").iterdir()}
    assert len(remaining) == DEFAULT_RETENTION
    assert "run22" in remaining  # most recent survives
    assert "run0" not in remaining  # oldest is gone


def test_current_run_terminalizing_does_not_leave_the_cap_plus_one_retained(tmp_path):
    """SPEC-004 remediation Finding 10: cleanup run *before* the current
    run starts (as peos/workflow.py does, for hygiene) is not enough on
    its own -- with exactly `keep` pre-existing terminal runs, the
    current run's own eventual terminal ledger would make 21 unless
    retention is also enforced *after* the current run terminalizes.
    This test models that second, post-completion cleanup call directly
    (the one peos/workflow.py's `_write_ledger` now makes on every
    terminal write) rather than only the pre-run one.
    """
    (tmp_path / ".git").mkdir()
    for i in range(DEFAULT_RETENTION):
        writer = LedgerWriter(tmp_path, f"old{i}")
        writer.write(_make_ledger(f"old{i}", outcome="FAILED", created_at=f"2024-03-{i + 1:02d}T00:00:00+00:00"))

    # Pre-run hygiene cleanup (as peos/workflow.py calls it at the top of
    # a run, with the new run's own id excluded since its directory does
    # not exist yet).
    cleanup_old_runs(tmp_path, active_run_id="current-run", keep=DEFAULT_RETENTION)
    assert len(list((tmp_path / ".peos" / "runs").iterdir())) == DEFAULT_RETENTION

    # The current run now terminalizes...
    current_writer = LedgerWriter(tmp_path, "current-run")
    current_writer.write(_make_ledger("current-run", outcome="APPROVED", created_at="2024-04-01T00:00:00+00:00"))
    # ...and peos/workflow.py's `_write_ledger` immediately follows that
    # terminal write with a second cleanup, this time with no run
    # excluded (the just-terminalized run is itself now eligible, and
    # survives purely because it is the most recent by created_at).
    cleanup_old_runs(tmp_path, active_run_id=None, keep=DEFAULT_RETENTION)

    remaining = {p.name for p in (tmp_path / ".peos" / "runs").iterdir()}
    assert len(remaining) == DEFAULT_RETENTION
    assert "current-run" in remaining
    assert "old0" not in remaining


# --- SPEC-004 remediation Finding 3: filesystem containment TOCTOU ------

def test_run_directory_replaced_by_symlink_after_first_write_fails_closed_on_second_write(tmp_path):
    """Case A: the first write succeeds normally; the run directory is
    then replaced by a symlink to an external directory before the
    *second* write. The earlier successful write/`_ensure_dir` call must
    not be treated as lasting proof the directory is still safe --
    `write()` must re-verify and fail closed, and the external target
    must never be touched.
    """
    external = tmp_path / "external"
    external.mkdir()

    writer = LedgerWriter(tmp_path, "run1")
    writer.write(_make_ledger("run1"))
    assert (writer.run_dir / "ledger.json").exists()

    run_dir = writer.run_dir
    shutil.rmtree(run_dir)
    run_dir.symlink_to(external, target_is_directory=True)

    with pytest.raises(LedgerError):
        writer.write(_make_ledger("run1", outcome="APPROVED"))
    assert list(external.iterdir()) == []


def test_cleanup_refuses_when_peos_runs_itself_becomes_a_symlink(tmp_path):
    """Case B: `.peos/runs` itself is a symlink to an external directory
    (e.g. `.peos` recreated as a symlink after being legitimately used
    earlier). Cleanup must refuse outright -- it must never delete
    anything inside that external directory.
    """
    external = tmp_path / "external"
    external.mkdir()
    (external / "evil").mkdir()
    peos_dir = tmp_path / ".peos"
    peos_dir.mkdir()
    (peos_dir / "runs").symlink_to(external, target_is_directory=True)

    cleanup_old_runs(tmp_path, active_run_id=None, keep=0)
    assert (external / "evil").exists()


def test_cleanup_deleting_a_stale_run_directory_does_not_follow_a_nested_symlink(tmp_path):
    """Case C: a symlink appears *inside* a run directory that retention
    legitimately decides to delete. The deletion must remove the
    symlink entry itself, never follow it into the external directory
    it points at.
    """
    external = tmp_path / "external"
    external.mkdir()
    (external / "secret.txt").write_text("keep me", encoding="utf-8")

    writer = LedgerWriter(tmp_path, "old1")
    writer.write(_make_ledger("old1", outcome="FAILED", created_at="2024-01-01T00:00:00+00:00"))
    (writer.run_dir / "nested_link").symlink_to(external, target_is_directory=True)

    cleanup_old_runs(tmp_path, active_run_id=None, keep=0)

    assert not writer.run_dir.exists()
    assert external.exists()
    assert (external / "secret.txt").exists()


# --- F3-A/B/C/D: ancestor-symlink / TOCTOU containment (closure review) --
#
# These exercise the real production entry points (`LedgerWriter.write`,
# `cleanup_old_runs`), covering the gap the earlier Codex closure review
# found in `open_dir_nofollow(absolute_path)`: an ancestor (`.peos` or
# `.peos/runs`) swapped to a symlink, not only the leaf run directory
# itself (already covered above). With the anchored, component-by-
# component walk (`peos.fsguard.traverse_dirs_anchored`), every one of
# these must fail closed without ever creating, writing to, or deleting
# anything inside the external target.

def test_f3a_ancestor_dot_peos_swapped_to_symlink_fails_closed_on_next_write(tmp_path):
    """F3-A: establish a valid ledger hierarchy via one real write, then
    replace the `.peos` ancestor itself (not the run directory) with a
    symlink to an external directory before the next write. The write
    must fail closed, and the external directory must remain untouched
    -- it must never gain a `runs/run1` hierarchy of its own.
    """
    external = tmp_path / "external"
    external.mkdir()

    writer = LedgerWriter(tmp_path, "run1")
    writer.write(_make_ledger("run1"))
    assert (writer.run_dir / "ledger.json").exists()

    shutil.rmtree(tmp_path / ".peos")
    (tmp_path / ".peos").symlink_to(external, target_is_directory=True)

    with pytest.raises(LedgerError):
        writer.write(_make_ledger("run1", outcome="APPROVED"))
    assert list(external.iterdir()) == []


def test_f3b_ancestor_dot_peos_swapped_to_symlink_fails_closed_on_cleanup(tmp_path):
    """F3-B: a real, valid-looking terminal run already exists under the
    authoritative `.peos/runs/old1`. Before cleanup runs, `.peos` itself
    (not just `.peos/runs`) is replaced by a symlink to an external
    directory. Cleanup must refuse outright, touching neither the
    external directory nor (since it can no longer even be reached
    through the swapped `.peos`) the original run directory.
    """
    writer = LedgerWriter(tmp_path, "old1")
    writer.write(_make_ledger("old1", outcome="FAILED", created_at="2024-01-01T00:00:00+00:00"))
    real_peos = tmp_path / ".peos"
    real_peos_backup = tmp_path / ".peos_authoritative_backup"
    real_peos.rename(real_peos_backup)

    external = tmp_path / "external"
    external.mkdir()
    (external / "evil").mkdir()
    real_peos.symlink_to(external, target_is_directory=True)

    cleanup_old_runs(tmp_path, active_run_id=None, keep=0)

    assert (external / "evil").exists()
    assert [p.name for p in external.iterdir()] == ["evil"]
    assert (real_peos_backup / "runs" / "old1" / "ledger.json").exists()


def test_f3c_dot_peos_pre_created_as_symlink_before_any_write_fails_closed_no_external_hierarchy(tmp_path):
    """F3-C: the ledger hierarchy does not exist yet anywhere -- this is
    this `LedgerWriter`'s very first `write()` call, which must create
    `.peos/runs/run1` from scratch. `.peos` is pre-created as a symlink
    to an external directory *before* that first call. Initial directory
    creation must fail closed, and -- the specific regression this
    covers -- it must never create a `runs/run1` hierarchy inside the
    external target on the way to discovering that.
    """
    external = tmp_path / "external"
    external.mkdir()
    (tmp_path / ".peos").symlink_to(external, target_is_directory=True)

    writer = LedgerWriter(tmp_path, "run1")
    with pytest.raises(LedgerError):
        writer.write(_make_ledger("run1"))

    assert list(external.iterdir()) == []
    assert not (external / "runs").exists()


# F3-D (run-directory swap after first write) is exactly
# `test_run_directory_replaced_by_symlink_after_first_write_fails_closed_on_second_write`
# above ("Case A"): kept as-is, no duplicate needed.


# --- SPEC-004 remediation Finding 9: machine hashes survive persistence -

def test_valid_baseline_git_hash_and_spec_hash_survive_ledger_persistence(tmp_path):
    git_hash = "0123456789abcdef0123456789abcdef01234567"
    spec_hash = "a" * 64
    ledger = _make_ledger(
        "run1",
        authoritative_baseline=git_hash,
        governing_spec_identity=f"docs/specifications/SPEC-004-x.md:{spec_hash}",
    )
    writer = LedgerWriter(tmp_path, "run1")
    path = writer.write(ledger)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["authoritative_baseline"] == git_hash
    assert data["governing_spec_identity"] == f"docs/specifications/SPEC-004-x.md:{spec_hash}"
    assert "[REDACTED]" not in data["authoritative_baseline"]
    assert "[REDACTED]" not in data["governing_spec_identity"]


def test_malformed_pseudo_hash_in_an_identity_field_still_gets_redacted(tmp_path):
    pseudo_hash = "g" * 40  # hash-length, but not valid hex
    ledger = _make_ledger("run1", authoritative_baseline=f"value={pseudo_hash}")
    writer = LedgerWriter(tmp_path, "run1")
    path = writer.write(ledger)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert pseudo_hash not in data["authoritative_baseline"]
    assert "[REDACTED]" in data["authoritative_baseline"]
