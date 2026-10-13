"""Run Ledger (SPEC-004 Requirements 3, 18, 19, 20 -- NEW).

A small, non-secret, JSON diagnostic record `peos/workflow.py` writes to
`<repo_root>/.peos/runs/<run_id>/ledger.json` after every phase
transition (the same places that already call `log(...)`), sufficient
for a human (or a future PEOS session) to read exactly what happened and
why a run stopped, from disk, without chat history (Tier 1
Resumability). It is diagnostic only: it cannot authorize execution,
establish engineering acceptance, or override repository/spec state, and
it is not a resume checkpoint (Tier 2 is explicitly deferred).

Serialization security (Requirement 18): `RunLedger` is a frozen
dataclass built through an explicit field allowlist; `write()` never
calls a generic serializer (`dataclasses.asdict`, `vars()`, `__dict__`)
on an arbitrary result object, and never writes a field not named in
`RunLedger`. Every text field is passed through
`peos.diagnostics.sanitize_human_text` (redact + bound) at the point this
module builds the JSON payload -- not merely at display time -- and raw
`stdout`/`stderr`, environment dumps, credential values/files, and
arbitrary configuration blobs are never accepted as ledger fields at all
(there is no field for them).

Filesystem containment (Requirement 19, hardened by remediation Finding
3): every directory this module creates, opens, or deletes is reached
through `peos.fsguard`'s anchored, component-by-component traversal
(`open_repo_root` + `traverse_dirs_anchored` + `create_dir_exclusive_
anchored`) -- never a point-in-time containment check followed by a
*separate* `open(absolute_path)`, which leaves a TOCTOU window between
the two. `repo_root` is resolved to a trusted directory file descriptor
exactly once per call; `.peos`, `.peos/runs`, and the run directory are
each then opened `O_NOFOLLOW` relative to the specific already-open
parent fd the previous step returned, so a symlink swapped into any
ancestor after that step cannot redirect anything that follows it. A
violation at any step is a `LedgerError`, which `peos/workflow.py` must
turn into a visible `FAILED` outcome, never a silent follow-through. Run
directories are created with exclusive creation semantics
(`create_dir_exclusive_anchored`, anchored to the already-open
`.peos/runs` fd, on first use of a given `LedgerWriter`): no reuse, no
silent overwrite of another run's state. File writes are atomic (temp
file + `os.replace`, both issued `dir_fd=`-relative to the run
directory's own just-opened fd).

Identity/retention (Requirement 20): every ledger carries schema version,
run ID, timestamps, baseline/governing-spec identity, effective
`max_cycles`, phase/cycle state, and sanitized finding/dispute/
verification summaries. `cleanup_old_runs` retains the most recent 20
completed/failed run directories, cleaning up only PEOS-owned, inactive
run directories (identified by a valid ledger with a terminal
`outcome`) and never a directory lacking a recognizable PEOS ledger or
belonging to the currently active run, regardless of its age.
"""

from __future__ import annotations

import dataclasses
import json
import os
import stat
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from peos.diagnostics import sanitize_human_text, sanitize_identity_text
from peos.fsguard import (
    fsync_dir_fd,
    mkdir_tolerant_anchored,
    open_repo_root,
    remove_tree_dir_fd,
    stat_nofollow,
    traverse_dirs_anchored,
    write_all,
)

SCHEMA_VERSION = "1"
RUNS_SUBDIR = ".peos/runs"
LEDGER_FILENAME = "ledger.json"
DEFAULT_RETENTION = 20

# SPEC-004 Requirement 20/Finding 10: the only outcomes a *valid* terminal
# ledger may carry. Kept here (not imported from peos/workflow.py's
# `Outcome` Literal) to avoid a ledger -> workflow import cycle -- this
# module must stay importable standalone. SPEC-007 Decision 9/"Terminal
# and Non-Terminal State Taxonomy" additively extends this with
# `MAX_CYCLES_REACHED` and `ABANDONED` -- both genuinely terminal and
# safely eligible for this ledger's own retention sweep, unlike the new
# `PAUSED_RETRYABLE` outcome (non-terminal, never written to this field
# at all -- see `peos/checkpoint.py`'s `RunCheckpoint.terminal_outcome`).
_VALID_TERMINAL_OUTCOMES = frozenset({"APPROVED", "HUMAN_GATE", "FAILED", "MAX_CYCLES_REACHED", "ABANDONED"})


class LedgerError(RuntimeError):
    """Raised when the Run Ledger cannot be safely written. Callers must
    treat this as a reason the run's outcome is `FAILED` -- never
    swallowed, never silently skipped (SPEC-004 Requirement 20)."""


@dataclass(frozen=True)
class RunLedger:
    """The *complete* list of fields SPEC-004 permits in the Run Ledger.
    `write()` never writes a field not named here."""

    run_id: str
    schema_version: str
    created_at: str
    updated_at: str
    max_cycles: int
    authoritative_baseline: str
    governing_spec_identity: str
    active_phase: str
    last_completed_phase: str
    current_cycle: int
    sanitized_phase_history: tuple[str, ...] = field(default_factory=tuple)
    sanitized_register_state: tuple[str, ...] = field(default_factory=tuple)
    sanitized_dispute_state: tuple[str, ...] = field(default_factory=tuple)
    sanitized_verification_summaries: tuple[str, ...] = field(default_factory=tuple)
    outcome: str | None = None
    gate_id: str | None = None
    gate_reason: str | None = None


_ALLOWED_FIELDS = frozenset(f.name for f in dataclasses.fields(RunLedger))


def _serialize_ledger(ledger: RunLedger) -> dict:
    """Build the JSON-ready dict explicitly, field by field (never
    `dataclasses.asdict`/`vars`/`__dict__`), sanitizing and bounding
    every text field/sequence-of-text field at the persistence boundary.
    """
    return {
        "run_id": sanitize_human_text(ledger.run_id),
        "schema_version": sanitize_human_text(ledger.schema_version),
        "created_at": sanitize_human_text(ledger.created_at),
        "updated_at": sanitize_human_text(ledger.updated_at),
        "max_cycles": int(ledger.max_cycles),
        "authoritative_baseline": sanitize_identity_text(ledger.authoritative_baseline),
        "governing_spec_identity": sanitize_identity_text(ledger.governing_spec_identity),
        "active_phase": sanitize_human_text(ledger.active_phase),
        "last_completed_phase": sanitize_human_text(ledger.last_completed_phase),
        "current_cycle": int(ledger.current_cycle),
        "sanitized_phase_history": [sanitize_human_text(x) for x in ledger.sanitized_phase_history],
        "sanitized_register_state": [sanitize_human_text(x) for x in ledger.sanitized_register_state],
        "sanitized_dispute_state": [sanitize_human_text(x) for x in ledger.sanitized_dispute_state],
        "sanitized_verification_summaries": [
            sanitize_human_text(x) for x in ledger.sanitized_verification_summaries
        ],
        "outcome": sanitize_human_text(ledger.outcome) if ledger.outcome is not None else None,
        "gate_id": sanitize_human_text(ledger.gate_id) if ledger.gate_id is not None else None,
        "gate_reason": sanitize_human_text(ledger.gate_reason) if ledger.gate_reason is not None else None,
    }


class LedgerWriter:
    """One instance per PEOS run. `write()` may be called many times
    (once after every phase transition); only the first call creates the
    run directory (exclusive creation -- SPEC-004 Requirement 19).

    Filesystem containment TOCTOU (SPEC-004 remediation Finding 3): the
    first successful `write()` is not treated as lasting proof that
    `run_dir` stays a safe, real directory for the rest of the run -- a
    symlink swapped in after that first write (replacing the run
    directory itself, or an ancestor of it) must not let a *later*
    `write()` silently follow it outside the repository. Every `write()`
    therefore re-opens `repo_root` as a trusted anchor and walks down to
    `run_dir` fresh, component-by-component
    (`peos.fsguard.traverse_dirs_anchored`) -- never a point-in-time
    containment check followed by a separate `open(absolute_path)`.
    Every subsequent filesystem operation for that call (creating the
    temp file, the atomic rename) is then issued with `dir_fd=` against
    the run directory's own just-opened, verified descriptor rather than
    by re-resolving `run_dir`'s path string, so a symlink introduced at
    `.peos`, `.peos/runs`, or the run directory itself -- at any point,
    before or during this call -- cannot redirect the write.
    """

    def __init__(self, repo_root: Path, run_id: str):
        self._repo_root = repo_root
        self._run_id = run_id
        self._dir_created = False

    @property
    def run_dir(self) -> Path:
        return self._repo_root / RUNS_SUBDIR / self._run_id

    def _open_repo_root(self) -> int:
        fd = open_repo_root(self._repo_root)
        if fd is None:
            raise LedgerError(f"repository root is not a safe, real directory: {self._repo_root}")
        return fd

    def _ensure_dir(self) -> None:
        """First use only: create `.peos/runs/<run_id>` with every
        directory in the chain opened or created relative to the
        already-open parent fd the previous step returned (SPEC-004
        remediation Finding 3) -- `.peos`, `.peos/runs`, and (as of
        SPEC-007) the run directory itself are all created *tolerantly*
        (`exist_ok`-equivalent). Because `mkdir` and the verifying `open`
        that follows it are both issued against the same already-open
        parent fd, there is no window between them for a symlink swapped
        into `name` to be followed instead.

        SPEC-007 note: the run directory's *exclusive*-creation
        guarantee (no reuse, no silent overwrite of another run's state)
        now lives in `peos.checkpoint.CheckpointWriter._ensure_dir`
        instead -- the checkpoint's own first write happens before this
        ledger's first write in every run's lifecycle (right after lock
        acquisition, before Planning), so it is the one place a genuine
        `run_id` collision is actually caught; duplicating that check
        here a second time would only ever fail *because* the checkpoint
        writer already (correctly) created this same directory moments
        earlier, which is not a collision at all.
        """
        if self._dir_created:
            return
        repo_fd = self._open_repo_root()
        try:
            runs_fd = traverse_dirs_anchored(repo_fd, RUNS_SUBDIR, create=True)
        finally:
            os.close(repo_fd)
        if runs_fd is None:
            raise LedgerError(
                f"could not safely create/open {RUNS_SUBDIR} anchored at the repository root "
                f"(an ancestor is a symlink, or not a directory): {self._repo_root / RUNS_SUBDIR}"
            )
        try:
            run_fd = mkdir_tolerant_anchored(runs_fd, self._run_id)
            if run_fd is None:
                raise LedgerError(f"could not safely create/open run directory {self.run_dir}")
            os.close(run_fd)
        finally:
            os.close(runs_fd)
        self._dir_created = True

    def _open_run_dir_safely(self) -> int:
        """Fresh, anchored walk from `repo_root` down to `run_dir`
        (`.peos` -> `.peos/runs` -> the run directory), never reusing any
        fd from `_ensure_dir`'s first call and never resolving `run_dir`
        as a standalone absolute path -- the anchor every write operation
        in this call then uses. Raises `LedgerError` (never returns an
        unsafe fd) on any violation at any step, including a symlink
        introduced at `.peos` or `.peos/runs` (not only the run directory
        itself) since this run's directory was first created.
        """
        repo_fd = self._open_repo_root()
        try:
            fd = traverse_dirs_anchored(repo_fd, f"{RUNS_SUBDIR}/{self._run_id}", create=False)
        finally:
            os.close(repo_fd)
        if fd is None:
            raise LedgerError(
                f"ledger run directory is not a safe, real directory (missing, or an ancestor or "
                f"the directory itself replaced by a symlink, since it was created): {self.run_dir}"
            )
        return fd

    def write(self, ledger: RunLedger) -> Path:
        if ledger.run_id != self._run_id:
            raise LedgerError("RunLedger.run_id does not match this LedgerWriter's run_id")
        self._ensure_dir()
        run_fd = self._open_run_dir_safely()
        try:
            payload = _serialize_ledger(ledger)
            text = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            tmp_name = f".{LEDGER_FILENAME}.{uuid.uuid4().hex}.tmp"
            try:
                tmp_fd = os.open(tmp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=run_fd)
            except OSError as exc:
                raise LedgerError(f"ledger temp-file create failed in {self.run_dir}: {exc}") from exc
            try:
                write_all(tmp_fd, text)
                os.fsync(tmp_fd)
            finally:
                os.close(tmp_fd)
            try:
                os.rename(tmp_name, LEDGER_FILENAME, src_dir_fd=run_fd, dst_dir_fd=run_fd)
            except OSError as exc:
                try:
                    os.unlink(tmp_name, dir_fd=run_fd)
                except OSError:
                    pass
                raise LedgerError(f"ledger atomic rename failed in {self.run_dir}: {exc}") from exc
            # SPEC-007 Decision 8 extension: the rename above changes
            # `run_fd`'s own directory *entry* for LEDGER_FILENAME (its
            # first-ever creation, or a replacement of the previous
            # write) -- fsyncing the already-fsync'd temp file's content
            # says nothing about that entry's own durability. Applied
            # unconditionally (not only on first creation): a rename is
            # always a directory-entry change, even when replacing an
            # existing name.
            try:
                fsync_dir_fd(run_fd)
            except OSError as exc:
                raise LedgerError(f"ledger directory-entry fsync failed in {self.run_dir}: {exc}") from exc
        finally:
            os.close(run_fd)
        return self.run_dir / LEDGER_FILENAME


def _parse_ledger_bytes(raw: bytes) -> RunLedger | None:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        kwargs = {k: data[k] for k in _ALLOWED_FIELDS if k in data}
        for seq_field in (
            "sanitized_phase_history", "sanitized_register_state",
            "sanitized_dispute_state", "sanitized_verification_summaries",
        ):
            if seq_field in kwargs:
                kwargs[seq_field] = tuple(kwargs[seq_field])
        return RunLedger(**kwargs)
    except (TypeError, KeyError):
        return None


def _is_valid_terminal_ledger(ledger: RunLedger | None, expected_run_id: str) -> bool:
    """SPEC-004 remediation Finding 10: a run directory counts toward
    retention's terminal-run pool only when its ledger is a recognizable,
    schema-valid PEOS ledger whose own `run_id` matches the directory it
    was read from and whose `outcome` is one of the enumerated terminal
    outcomes -- never merely "parsed as JSON with a non-null `outcome`
    key", which arbitrary/forged JSON could satisfy trivially.
    """
    if ledger is None:
        return False
    if ledger.schema_version != SCHEMA_VERSION:
        return False
    if ledger.run_id != expected_run_id:
        return False
    return ledger.outcome in _VALID_TERMINAL_OUTCOMES


def _open_file_nofollow(parent_fd: int, name: str, flags: int = os.O_RDONLY) -> int | None:
    try:
        return os.open(name, flags | os.O_NOFOLLOW, dir_fd=parent_fd)
    except OSError:
        return None


def _read_ledger_via_dir_fd(runs_fd: int, name: str) -> RunLedger | None:
    """Read `<name>/ledger.json` using only `dir_fd`-relative syscalls
    anchored at the already-opened, verified-safe `runs_fd` (SPEC-004
    remediation Finding 3) -- never a fresh path-string lookup from
    `repo_root`, which a symlink introduced after `runs_fd` was opened
    could otherwise redirect. Returns `None` (never raises) for anything
    that is not, right now, a real directory containing a real regular
    `ledger.json` file with valid JSON content.
    """
    entry_stat = stat_nofollow(runs_fd, name)
    if entry_stat is None or not stat.S_ISDIR(entry_stat.st_mode):
        return None
    run_fd = _open_file_nofollow(runs_fd, name, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    if run_fd is None:
        return None
    try:
        file_stat = stat_nofollow(run_fd, LEDGER_FILENAME)
        if file_stat is None or not stat.S_ISREG(file_stat.st_mode):
            return None
        file_fd = _open_file_nofollow(run_fd, LEDGER_FILENAME)
        if file_fd is None:
            return None
        try:
            with os.fdopen(file_fd, "rb") as f:
                raw = f.read()
        except OSError:
            return None
    finally:
        os.close(run_fd)
    return _parse_ledger_bytes(raw)


def cleanup_old_runs(repo_root: Path, active_run_id: str | None, keep: int = DEFAULT_RETENTION) -> None:
    """Retain the most recent `keep` valid-terminal (SPEC-004 remediation
    Finding 10) PEOS-owned run directories under `.peos/runs/`; delete
    older ones. Never touches a directory lacking a recognizable, valid
    PEOS ledger, and never touches `active_run_id`'s directory, regardless
    of age.

    Filesystem containment TOCTOU (SPEC-004 remediation Finding 3): the
    handle on `.peos/runs` itself is obtained by an anchored,
    component-by-component walk from a freshly-opened `repo_root`
    descriptor (`peos.fsguard.open_repo_root` + `traverse_dirs_anchored`)
    -- never a point-in-time containment check followed by a separate
    `open(absolute_path)` -- and both the traversal (reading each
    candidate's ledger) and the deletion of a stale run directory are
    then performed entirely through `dir_fd`-relative syscalls anchored
    at that one handle. A symlink introduced at `.peos`, `.peos/runs`, or
    any individual run directory, at any point before or during this
    call, cannot redirect a read or, worse, a deletion outside the
    repository.
    """
    repo_fd = open_repo_root(repo_root)
    if repo_fd is None:
        return
    try:
        runs_fd = traverse_dirs_anchored(repo_fd, RUNS_SUBDIR, create=False)
    finally:
        os.close(repo_fd)
    if runs_fd is None:
        return

    try:
        terminal: list[tuple[str, str]] = []
        for name in os.listdir(runs_fd):
            if name == active_run_id:
                continue
            entry_stat = stat_nofollow(runs_fd, name)
            if entry_stat is None or not stat.S_ISDIR(entry_stat.st_mode):
                continue
            ledger = _read_ledger_via_dir_fd(runs_fd, name)
            if not _is_valid_terminal_ledger(ledger, expected_run_id=name):
                continue
            terminal.append((ledger.created_at, name))

        terminal.sort(key=lambda pair: pair[0], reverse=True)
        for _, stale_name in terminal[keep:]:
            try:
                remove_tree_dir_fd(runs_fd, stale_name)
            except OSError:
                pass
    finally:
        os.close(runs_fd)
