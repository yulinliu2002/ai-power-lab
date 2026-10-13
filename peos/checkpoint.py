"""RunCheckpoint persistence (SPEC-007 PEOS Durable Run Resume V1).

A new, trusted, orchestrator-owned artifact distinct from the diagnostic
Run Ledger (`peos/ledger.py`): sufficient, on its own, to resume a safely
resumable interrupted run. Written to
`<repo_root>/.peos/runs/<run_id>/checkpoint.json`, a sibling of
`ledger.json` under the same run directory.

Trust boundary (ADR-0004 Decision 8, SPEC-007 "Checkpoint Trust Boundary
(Precise Claim)"): no cryptographic claim. Orchestrator-owned persistence;
structural candidate-workspace exclusion (see `peos/sandbox.py`'s
`candidate/` nesting); atomic persistence (temp file + `fsync` +
`os.rename`, plus an `fsync` of the containing directory so the
directory-entry change itself survives power loss); an explicit
serialization allowlist (this module never calls `dataclasses.asdict`/
`vars`/`__dict__` on the whole checkpoint); bounded fields (every string
field is sanitized via `peos.diagnostics.sanitize_identity_text`, which
preserves genuine hash-shaped substrings while still redacting/bounding
everything else -- the same property `peos/ledger.py` already relies on
for its own identity fields, applied here uniformly since this artifact
is overwhelmingly identity/hash data). This is agent-unforgeable under
the PEOS execution boundary (neither Claude nor Codex has a write path to
`.peos/runs/`), fail-closed under inconsistent state, and explicitly
**not** a defense against an authorized local machine owner with direct
filesystem access.

Filesystem containment mirrors `peos/ledger.py` exactly (anchored,
`dir_fd`-relative traversal via `peos.fsguard` -- never a point-in-time
check followed by a separate absolute-path `open()`), with one
deliberate difference: this writer creates `.peos`/`.peos/runs`/the run
directory *tolerantly* (`peos.fsguard.mkdir_tolerant_anchored`), not
exclusively. Per SPEC-007's design, the checkpoint's own first write
happens *before* the Run Ledger's first write in a run's lifecycle (right
after the shared run lock is acquired, before Planning's own resolution
work begins -- see `peos/resume.py`), so whichever of the two writers
reaches the run directory first creates it; `peos/ledger.py`'s own
`create_dir_exclusive_anchored` call, which still runs moments later at
the first `ledger.write()` call, remains the sole place a genuine
`run_id` collision is still caught and rejected -- this module
deliberately does not duplicate that specific guarantee a second time.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import os
import stat
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from peos.diagnostics import sanitize_identity_text
from peos.fsguard import (
    create_dir_exclusive_anchored,
    mkdir_tolerant_anchored,
    open_repo_root,
    stat_nofollow,
    fsync_dir_fd,
    traverse_dirs_anchored,
    write_all,
)
from peos.round_packet import ActiveDispute, RegisterEntrySnapshot, StaticContextRef

SCHEMA_VERSION = "1"
RUNS_SUBDIR = ".peos/runs"
CHECKPOINT_FILENAME = "checkpoint.json"

PhaseState = Literal["NOT_STARTED", "ENTERED", "COMPLETED"]

# SPEC-007 "Terminal and Non-Terminal State Taxonomy".
Outcome = Literal[
    "APPROVED", "HUMAN_GATE", "FAILED",
    "MAX_CYCLES_REACHED", "PAUSED_RETRYABLE", "ABANDONED",
]
TERMINAL_OUTCOMES = frozenset({"APPROVED", "HUMAN_GATE", "FAILED", "MAX_CYCLES_REACHED", "ABANDONED"})


class CheckpointError(RuntimeError):
    """Raised when the checkpoint cannot be safely written or read.
    Callers must treat a write failure as a reason the run's outcome is
    `FAILED`, never swallowed, never silently skipped -- mirroring
    `peos.ledger.LedgerError`'s own contract."""


@dataclass(frozen=True)
class ReconciliationOperation:
    """SPEC-007 "Reconciliation Crash-Safety" -- one durably-recorded,
    atomically-applied file-level operation. `target_content_hash` is the
    candidate's value to apply (`None` for a delete); `original_content_
    hash` is the authoritative value before reconciliation started
    (`None` if the path did not exist). `applied` is updated, in place,
    as each operation completes."""

    relative_path: str
    action: Literal["write", "delete"]
    target_content_hash: str | None = None
    original_content_hash: str | None = None
    applied: bool = False


@dataclass(frozen=True)
class ServiceProcessIdentity:
    """SPEC-007 "Process Ownership and Orphan Reclamation" (Decision 7).
    `port` is required for backend/frontend; `None` for a browser_worker,
    which binds no service port. `command_argv` is the exact argv passed
    to `Popen`, including any sandbox-exec/wrapper prefix."""

    service_name: str
    pid: int
    pgid: int
    port: int | None
    start_time: str | None
    command_argv: tuple[str, ...]
    owning_run_id: str
    recorded_at: str


@dataclass(frozen=True)
class RuntimeEvidenceRefSnapshot:
    """One round's persisted Runtime Verification evidence reference, as
    recorded durably in the checkpoint's `runtime_evidence_history` --
    sufficient to re-run `peos.runtime_evidence.reverify_evidence_identity`
    against the authoritative, persisted copy after a resume."""

    cycle_label: str
    staged_relative_path: str
    evidence_json_sha256: str
    execution_integrity_passed: bool


@dataclass(frozen=True)
class RunCheckpoint:
    schema_version: str
    run_id: str
    resume_generation: int

    created_at: str
    updated_at: str

    task: str
    authoritative_baseline: str
    governing_spec_relative_path: str
    governing_spec_content_hash: str
    governing_spec_source: str
    governing_spec_original_path: str
    effective_max_cycles: int

    active_phase: str
    active_phase_state: str
    last_safely_completed_phase: str
    current_cycle: int

    workspace_root_relative_path: str
    workspace_home_dir_relative_path: str
    workspace_baseline_commit: str
    current_workspace_snapshot_identity: str
    resume_candidate_workspace_identity: str | None = None
    # SPEC-007 "Resume Preflight" check 15 (Codex closure review,
    # confirmed, major): a content-based fingerprint of `repo_root`
    # itself (`peos.gitutil.repo_state_fingerprint`), captured at
    # PLANNING's own `COMPLETED` write -- the HEAD-commit comparison
    # alone cannot detect an *uncommitted* tracked-file edit (or a new
    # untracked file) made to the authoritative repository during a
    # long pause, which a freshly-rebuilt reconciliation manifest would
    # otherwise silently adopt as "the original" and overwrite without
    # ever flagging it. Empty for a checkpoint that never reached
    # PLANNING's own COMPLETED write.
    authoritative_repo_fingerprint: str = ""

    reconciliation_manifest: tuple[ReconciliationOperation, ...] = field(default_factory=tuple)
    service_process_identities: tuple[ServiceProcessIdentity, ...] = field(default_factory=tuple)

    decision_identities: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    governance_identities: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    static_context_artifacts: tuple[StaticContextRef, ...] = field(default_factory=tuple)
    acceptance_criteria_ids: tuple[str, ...] = field(default_factory=tuple)

    findings_register_entries: tuple[RegisterEntrySnapshot, ...] = field(default_factory=tuple)
    active_disputes: tuple[ActiveDispute, ...] = field(default_factory=tuple)
    dispute_log: tuple[str, ...] = field(default_factory=tuple)

    runtime_evidence_history: tuple[RuntimeEvidenceRefSnapshot, ...] = field(default_factory=tuple)

    codex_review_payload_hashes: tuple[str, ...] = field(default_factory=tuple)
    codex_review_verdict_history: tuple[str, ...] = field(default_factory=tuple)

    pause_reason: str | None = None

    terminal_outcome: str | None = None
    terminal_gate_id: str | None = None
    terminal_gate_reason: str | None = None


_NESTED_DATACLASS_FIELDS = (
    "reconciliation_manifest", "service_process_identities", "static_context_artifacts",
    "findings_register_entries", "active_disputes", "runtime_evidence_history",
)
_SIMPLE_TUPLE_FIELDS = (
    "decision_identities", "governance_identities", "acceptance_criteria_ids",
    "dispute_log", "codex_review_payload_hashes", "codex_review_verdict_history",
)
_ALLOWED_FIELDS = frozenset(f.name for f in dataclasses.fields(RunCheckpoint))


def _sanitize_scalar(value):
    if isinstance(value, str):
        return sanitize_identity_text(value)
    return value


def _sanitize_nested_dict(d: dict) -> dict:
    return {k: _sanitize_scalar(v) if not isinstance(v, (tuple, list)) else [_sanitize_scalar(x) for x in v] for k, v in d.items()}


def serialize_checkpoint(cp: RunCheckpoint) -> dict:
    """Build the JSON-ready dict explicitly, field by field (never
    `dataclasses.asdict`/`vars`/`__dict__` on the whole checkpoint),
    sanitizing every string leaf at the persistence boundary -- mirroring
    `peos.ledger._serialize_ledger`'s own explicit-allowlist discipline.
    """
    out: dict = {}
    for f in dataclasses.fields(RunCheckpoint):
        name = f.name
        value = getattr(cp, name)
        if name in _NESTED_DATACLASS_FIELDS:
            out[name] = [_sanitize_nested_dict(dataclasses.asdict(item)) for item in value]
        elif name == "decision_identities" or name == "governance_identities":
            out[name] = [[sanitize_identity_text(a), sanitize_identity_text(b)] for a, b in value]
        elif name in ("acceptance_criteria_ids", "dispute_log", "codex_review_payload_hashes", "codex_review_verdict_history"):
            out[name] = [sanitize_identity_text(x) for x in value]
        elif isinstance(value, str):
            out[name] = sanitize_identity_text(value)
        elif value is None or isinstance(value, (int, bool)):
            out[name] = value
        else:
            out[name] = value
    return out


def _coerce_nested(field_name: str, raw_list: list) -> tuple:
    cls = {
        "reconciliation_manifest": ReconciliationOperation,
        "service_process_identities": ServiceProcessIdentity,
        "static_context_artifacts": StaticContextRef,
        "findings_register_entries": RegisterEntrySnapshot,
        "active_disputes": ActiveDispute,
        "runtime_evidence_history": RuntimeEvidenceRefSnapshot,
    }[field_name]
    allowed = frozenset(f.name for f in dataclasses.fields(cls))
    out = []
    for item in raw_list:
        if not isinstance(item, dict):
            raise ValueError(f"{field_name} entry is not an object")
        kwargs = {k: v for k, v in item.items() if k in allowed}
        for tf in ("command_argv", "related_ac_ids"):
            if tf in kwargs and isinstance(kwargs[tf], list):
                kwargs[tf] = tuple(kwargs[tf])
        out.append(cls(**kwargs))
    return tuple(out)


def deserialize_checkpoint(data: dict) -> RunCheckpoint:
    """Strictly parse `data` (already `json.loads`-decoded) into a
    `RunCheckpoint`, raising `ValueError`/`TypeError`/`KeyError` on any
    structural problem -- callers (see `load_checkpoint`) must treat any
    such exception as "malformed", never as "equivalent to missing"
    (SPEC-007 AC-014)."""
    if not isinstance(data, dict):
        raise ValueError("checkpoint content is not a JSON object")
    kwargs: dict = {}
    for name in _ALLOWED_FIELDS:
        if name not in data:
            continue
        if name in _NESTED_DATACLASS_FIELDS:
            kwargs[name] = _coerce_nested(name, data[name])
        elif name in ("decision_identities", "governance_identities"):
            kwargs[name] = tuple(tuple(pair) for pair in data[name])
        elif name in _SIMPLE_TUPLE_FIELDS:
            kwargs[name] = tuple(data[name])
        else:
            kwargs[name] = data[name]
    return RunCheckpoint(**kwargs)


class CheckpointWriter:
    """One instance per PEOS run (paired 1:1 with a `peos.ledger.
    LedgerWriter` for the same `run_id`). `write()` may be called many
    times; the run directory is created tolerantly (see module
    docstring) on first use."""

    def __init__(self, repo_root: Path, run_id: str, require_fresh: bool = True):
        """`require_fresh` (default `True`): use *exclusive* run-
        directory creation, catching a genuine `run_id` collision --
        correct for a brand-new task's bootstrap, the overwhelmingly
        common case. A **resumed** run's `CheckpointManager`/
        `CheckpointWriter` (a fresh process instance, same `run_id` as
        an earlier, interrupted attempt) must pass `require_fresh=False`
        to tolerantly reuse its own, already-existing run directory --
        the entire point of resume -- rather than this safety check
        mistaking that legitimate reuse for a collision with an
        unrelated run."""
        self._repo_root = repo_root
        self._run_id = run_id
        self._require_fresh = require_fresh
        self._dir_created = False

    @property
    def run_dir(self) -> Path:
        return self._repo_root / RUNS_SUBDIR / self._run_id

    def _open_repo_root(self) -> int:
        fd = open_repo_root(self._repo_root)
        if fd is None:
            raise CheckpointError(f"repository root is not a safe, real directory: {self._repo_root}")
        return fd

    def _ensure_dir(self) -> None:
        """First use only: create `.peos/runs/<run_id>`. `.peos` and
        `.peos/runs` are created tolerantly; the run directory itself is
        created with *exclusive* semantics
        (`peos.fsguard.create_dir_exclusive_anchored`, `fsync`'d) --
        SPEC-007's checkpoint is the *first* write of a run's lifecycle
        (before `peos.ledger.LedgerWriter`'s own first write), so this is
        the one place a genuine `run_id` collision is caught and
        rejected; `LedgerWriter._ensure_dir` creates the same directory
        tolerantly, deliberately not duplicating this check a second
        time (see `peos/ledger.py`'s own docstring note)."""
        if self._dir_created:
            return
        repo_fd = self._open_repo_root()
        try:
            peos_fd = mkdir_tolerant_anchored(repo_fd, ".peos")
        finally:
            os.close(repo_fd)
        if peos_fd is None:
            raise CheckpointError(f"could not safely create/open .peos anchored at the repository root: {self._repo_root / '.peos'}")
        try:
            runs_fd = mkdir_tolerant_anchored(peos_fd, "runs")
        finally:
            os.close(peos_fd)
        if runs_fd is None:
            raise CheckpointError(f"could not safely create/open {RUNS_SUBDIR} anchored at the repository root: {self._repo_root / RUNS_SUBDIR}")
        try:
            if self._require_fresh:
                try:
                    run_fd = create_dir_exclusive_anchored(runs_fd, self._run_id)
                except FileExistsError as exc:
                    raise CheckpointError(
                        f"run directory already exists -- refusing to reuse another run's state: {self.run_dir}"
                    ) from exc
                except OSError as exc:
                    raise CheckpointError(f"could not create run directory {self.run_dir}: {exc}") from exc
                try:
                    fsync_dir_fd(runs_fd)
                except OSError as exc:
                    os.close(run_fd)
                    raise CheckpointError(f"run-directory-entry fsync failed for {self.run_dir}: {exc}") from exc
            else:
                run_fd = mkdir_tolerant_anchored(runs_fd, self._run_id)
                if run_fd is None:
                    raise CheckpointError(f"could not safely create/open run directory {self.run_dir}")
            os.close(run_fd)
        finally:
            os.close(runs_fd)
        self._dir_created = True

    def _open_run_dir_safely(self) -> int:
        repo_fd = self._open_repo_root()
        try:
            fd = traverse_dirs_anchored(repo_fd, f"{RUNS_SUBDIR}/{self._run_id}", create=False)
        finally:
            os.close(repo_fd)
        if fd is None:
            raise CheckpointError(
                f"checkpoint run directory is not a safe, real directory (missing, or an ancestor or the "
                f"directory itself replaced by a symlink, since it was created): {self.run_dir}"
            )
        return fd

    def write(self, checkpoint: RunCheckpoint) -> Path:
        if checkpoint.run_id != self._run_id:
            raise CheckpointError("RunCheckpoint.run_id does not match this CheckpointWriter's run_id")
        self._ensure_dir()
        run_fd = self._open_run_dir_safely()
        try:
            payload = serialize_checkpoint(checkpoint)
            text = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            tmp_name = f".{CHECKPOINT_FILENAME}.{uuid.uuid4().hex}.tmp"
            try:
                tmp_fd = os.open(tmp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=run_fd)
            except OSError as exc:
                raise CheckpointError(f"checkpoint temp-file create failed in {self.run_dir}: {exc}") from exc
            try:
                write_all(tmp_fd, text)
                os.fsync(tmp_fd)
            finally:
                os.close(tmp_fd)
            try:
                os.rename(tmp_name, CHECKPOINT_FILENAME, src_dir_fd=run_fd, dst_dir_fd=run_fd)
            except OSError as exc:
                try:
                    os.unlink(tmp_name, dir_fd=run_fd)
                except OSError:
                    pass
                raise CheckpointError(f"checkpoint atomic rename failed in {self.run_dir}: {exc}") from exc
            try:
                fsync_dir_fd(run_fd)
            except OSError as exc:
                raise CheckpointError(f"checkpoint directory-entry fsync failed in {self.run_dir}: {exc}") from exc
        finally:
            os.close(run_fd)
        return self.run_dir / CHECKPOINT_FILENAME


def load_checkpoint(repo_root: Path, run_id: str) -> tuple[RunCheckpoint | None, str | None]:
    """Read `<repo_root>/.peos/runs/<run_id>/checkpoint.json`.

    Returns `(checkpoint, None)` on success, `(None, None)` if the run
    directory or the checkpoint file genuinely does not exist (the
    PLANNING-bootstrap-gap case this module's callers must distinguish
    from corruption -- SPEC-007 AC-062), or `(None, error_message)` if
    the file exists but cannot be safely read/parsed (SPEC-007 AC-014 --
    always `FAILED`, never treated as equivalent to "missing"). Uses the
    same anchored, `dir_fd`-relative traversal as every other read in
    this codebase (`peos.fsguard`) -- never a point-in-time check
    followed by a separate absolute-path `open()`.
    """
    repo_fd = open_repo_root(repo_root)
    if repo_fd is None:
        return None, f"repository root is not a safe, real directory: {repo_root}"
    try:
        runs_fd = traverse_dirs_anchored(repo_fd, RUNS_SUBDIR, create=False)
    finally:
        os.close(repo_fd)
    if runs_fd is None:
        return None, None
    try:
        run_entry = stat_nofollow(runs_fd, run_id)
        if run_entry is None or not stat.S_ISDIR(run_entry.st_mode):
            return None, None
        run_fd = os.open(run_id, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_NOFOLLOW, dir_fd=runs_fd)
    except OSError:
        return None, None
    finally:
        os.close(runs_fd)
    try:
        file_entry = stat_nofollow(run_fd, CHECKPOINT_FILENAME)
        if file_entry is None:
            return None, None
        if not stat.S_ISREG(file_entry.st_mode):
            return None, f"checkpoint.json is not a regular file: {run_id}"
        try:
            file_fd = os.open(CHECKPOINT_FILENAME, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=run_fd)
        except OSError as exc:
            return None, f"checkpoint.json could not be opened: {exc}"
        try:
            with os.fdopen(file_fd, "rb") as fh:
                raw = fh.read()
        except OSError as exc:
            return None, f"checkpoint.json could not be read: {exc}"
    finally:
        os.close(run_fd)

    try:
        data = json.loads(raw.decode("utf-8"))
        checkpoint = deserialize_checkpoint(data)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        return None, f"checkpoint.json is malformed/corrupted: {exc}"
    if checkpoint.schema_version != SCHEMA_VERSION:
        return None, f"checkpoint.json has an unrecognized schema_version: {checkpoint.schema_version!r}"
    if checkpoint.run_id != run_id:
        return None, f"checkpoint.json's own run_id ({checkpoint.run_id!r}) does not match its directory ({run_id!r})"
    return checkpoint, None


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class CheckpointManager:
    """Accumulates one run's `RunCheckpoint` fields in memory and
    persists the *complete* checkpoint via `CheckpointWriter` on every
    `enter`/`complete`/`terminal` call -- SPEC-007's "single atomic
    transaction" requirement (a phase's `COMPLETED` write always
    includes every durable consequence of that phase's result, never a
    status flag written separately from what it depends on). One
    instance per run, paired 1:1 with a `peos.ledger.LedgerWriter` for
    the same `run_id`.
    """

    def __init__(self, repo_root: Path, run_id: str, writer: CheckpointWriter | None = None, require_fresh: bool = True):
        self._writer = writer or CheckpointWriter(repo_root, run_id, require_fresh=require_fresh)
        now = _now()
        self._fields: dict = dict(
            schema_version=SCHEMA_VERSION, run_id=run_id, resume_generation=0,
            created_at=now, updated_at=now,
            task="", authoritative_baseline="", governing_spec_relative_path="",
            governing_spec_content_hash="", governing_spec_source="auto_detected",
            governing_spec_original_path="", effective_max_cycles=1,
            active_phase="", active_phase_state="NOT_STARTED", last_safely_completed_phase="",
            current_cycle=0,
            workspace_root_relative_path="", workspace_home_dir_relative_path="",
            workspace_baseline_commit="", current_workspace_snapshot_identity="",
            resume_candidate_workspace_identity=None, authoritative_repo_fingerprint="",
            reconciliation_manifest=(), service_process_identities=(),
            decision_identities=(), governance_identities=(), static_context_artifacts=(),
            acceptance_criteria_ids=(),
            findings_register_entries=(), active_disputes=(), dispute_log=(),
            runtime_evidence_history=(),
            codex_review_payload_hashes=(), codex_review_verdict_history=(),
            pause_reason=None, terminal_outcome=None, terminal_gate_id=None, terminal_gate_reason=None,
        )

    @property
    def run_dir(self) -> Path:
        return self._writer.run_dir

    @property
    def current(self) -> RunCheckpoint:
        return RunCheckpoint(**self._fields)

    def load_resume_generation(self, resume_generation: int) -> None:
        """Set once, immediately after a resumed run's preflight succeeds
        -- every subsequent write in this resumed execution carries the
        incremented generation, distinguishing this attempt's writes from
        the pre-interruption attempt's in any audit trail."""
        self._fields["resume_generation"] = resume_generation

    def seed_from(self, checkpoint: RunCheckpoint) -> None:
        """Adopt an existing (resumed) checkpoint's fields as this
        manager's starting state, so a resumed run's subsequent
        `enter`/`complete` calls build on exactly what was durably
        recorded before the interruption, never a fresh, empty start."""
        self._fields = dataclasses.asdict(checkpoint)
        # dataclasses.asdict recurses into nested dataclasses as plain
        # dicts; reconstruct them as the real nested dataclass instances
        # `serialize_checkpoint`/`CheckpointWriter.write` expect.
        for name in _NESTED_DATACLASS_FIELDS:
            self._fields[name] = _coerce_nested(name, self._fields[name])
        self._fields["decision_identities"] = tuple(tuple(p) for p in self._fields["decision_identities"])
        self._fields["governance_identities"] = tuple(tuple(p) for p in self._fields["governance_identities"])
        for name in _SIMPLE_TUPLE_FIELDS:
            self._fields[name] = tuple(self._fields[name])

    def _persist(self) -> RunCheckpoint:
        self._fields["updated_at"] = _now()
        cp = RunCheckpoint(**self._fields)
        self._writer.write(cp)
        return cp

    def enter(self, phase: str, **extra) -> RunCheckpoint:
        self._fields.update(extra)
        self._fields["active_phase"] = phase
        self._fields["active_phase_state"] = "ENTERED"
        return self._persist()

    def complete(self, phase: str, **extra) -> RunCheckpoint:
        self._fields.update(extra)
        self._fields["active_phase"] = phase
        self._fields["active_phase_state"] = "COMPLETED"
        self._fields["last_safely_completed_phase"] = phase
        return self._persist()

    def terminal(
        self, outcome: str, gate_id: str | None = None, gate_reason: str | None = None,
        pause_reason: str | None = None, **extra,
    ) -> RunCheckpoint:
        # SPEC-007 "Durable Phase-State Semantics": `TERMINAL_DECISION`
        # is itself a phase in the table (`COMPLETED` write: "the
        # terminal outcome, gate ID, gate reason") -- Codex
        # implementation review (confirmed, major): an earlier revision
        # set the `terminal_*` fields without ever recording the phase
        # transition itself, leaving `active_phase`/`active_phase_state`
        # stuck at whatever phase preceded it.
        self._fields.update(extra)
        self._fields["active_phase"] = "TERMINAL_DECISION"
        self._fields["active_phase_state"] = "COMPLETED"
        self._fields["last_safely_completed_phase"] = "TERMINAL_DECISION"
        self._fields["terminal_outcome"] = outcome
        self._fields["terminal_gate_id"] = gate_id
        self._fields["terminal_gate_reason"] = gate_reason
        if pause_reason is not None:
            self._fields["pause_reason"] = pause_reason
        return self._persist()
