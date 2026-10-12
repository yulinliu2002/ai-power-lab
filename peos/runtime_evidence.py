"""Runtime Evidence (SPEC-006 Section 9, hardening item F; Section 13
hardening item C's four-state AC rollup).

`RuntimeCheck` / `ServiceReadiness` / `RuntimeEvidence` are the
structured, bounded, provenance-rich records SPEC-006 requires. Every
text field is sanitized (`peos.diagnostics.sanitize_human_text`) and
every size bound (evidence.json <= 256 KiB, a service's captured
stdout/stderr tail <= 64 KiB, at most one screenshot per check,
<= 4 MiB per screenshot, <= 10 MiB total screenshots per round) is
enforced at construction time, never left to the caller -- any field a
bound would otherwise exceed is marked `truncated=True`/given a non-null
`omitted_reason`, never silently dropped with no trace (SPEC-006
Resolved Decision 5).

Persistence is cycle-qualified (SPEC-006 Section 9 "Per-cycle identity",
Codex Round 1 Finding 5): every round's evidence lives at its own,
immutable path, `.peos/runs/<run_id>/runtime-evidence/<cycle_label>/`,
never shared or overwritten across rounds. The SHA-256 hash of
`evidence.json` is written to a separate sidecar file
(`evidence.json.sha256`), never embedded as a field inside the JSON it
hashes (Codex Round 1 Finding 6). The staged copy inside the isolated
workspace is read-only by OS permission bits as a convention, not a
tamper-prevention claim -- `reverify_evidence_identity` (hash
re-verification) is the actual tamper-*detection* mechanism this
specification relies on (Codex Round 1 Finding 4).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from peos.diagnostics import redact, sanitize_human_text
from peos.fsguard import assert_no_symlink_components
from peos.runtime_catalog import RUNTIME_CHECK_CATALOG_VERSION

EVIDENCE_SUBDIR = ".peos/runs"
EVIDENCE_DIRNAME = "runtime-evidence"
EVIDENCE_FILENAME = "evidence.json"
EVIDENCE_HASH_FILENAME = "evidence.json.sha256"
SCREENSHOTS_DIRNAME = "screenshots"

# SPEC-006 Resolved Decision 5 bounds.
MAX_EVIDENCE_JSON_BYTES = 256 * 1024
MAX_SERVICE_TAIL_CHARS = 64 * 1024
MAX_SCREENSHOT_BYTES = 4 * 1024 * 1024
MAX_TOTAL_SCREENSHOT_BYTES_PER_ROUND = 10 * 1024 * 1024

VALID_CHECK_STATUSES = ("PASS", "FAIL", "NOT_EXECUTED")

# Codex implementation review Finding 6: `sanitize_human_text` bounds
# each individual *string*, but nothing previously bounded how many
# strings a console/page-error/blocked-request list could hold, or the
# number of keys a `parameters`/`measurements` dict could hold -- a
# pathological page (or a check author) could still blow past the
# per-round 256 KiB evidence.json bound even with the 20-check cap,
# because that cap bounds the number of *checks*, not the number of
# *items inside* one check. Both bounds below are named, fixed, and
# applied at construction time, with truncation always represented in
# `RuntimeCheck.truncated` -- never silently dropped.
MAX_LIST_ITEMS = 20
MAX_DICT_ITEMS = 20


def _bounded_text_list(items) -> tuple[tuple[str, ...], bool]:
    sanitized = [sanitize_human_text(str(i)) for i in items]
    truncated = len(sanitized) > MAX_LIST_ITEMS
    return tuple(sanitized[-MAX_LIST_ITEMS:]), truncated


def _bounded_dict(d: dict) -> tuple[dict, bool]:
    """Sanitize every string value (secret redaction + length bound) and
    cap the number of keys -- `parameters`/`measurements` are agent/
    page-adjacent data, not orchestrator-authored, so neither is trusted
    to be small or secret-free on its own."""
    truncated = len(d) > MAX_DICT_ITEMS
    bounded_items = list(d.items())[:MAX_DICT_ITEMS]
    sanitized = {
        key: (sanitize_human_text(value) if isinstance(value, str) else value)
        for key, value in bounded_items
    }
    return sanitized, truncated


class RuntimeEvidenceError(RuntimeError):
    """Raised when evidence cannot be safely persisted with integrity.
    Callers (`peos/workflow.py`) must treat this as an execution-
    integrity `FAILED`, never a silent follow-through (SPEC-006 Section
    6)."""


def _cycle_label_slug(cycle_label: str) -> str:
    """`"cycle 0"` -> `"cycle-0"`, `"remediation cycle 3"` ->
    `"remediation-cycle-3"` -- a filesystem-safe directory-name slug."""
    return cycle_label.strip().lower().replace(" ", "-")


@dataclass(frozen=True)
class RuntimeCheck:
    check_id: str
    kind: str
    catalog_version: str
    related_ac_ids: tuple[str, ...]
    parameters: dict
    status: str  # "PASS" | "FAIL" | "NOT_EXECUTED"
    action_performed: str
    observation: str
    measurements: dict
    screenshot_path: str | None = None
    screenshot_sha256: str | None = None
    console_errors: tuple[str, ...] = field(default_factory=tuple)
    page_errors: tuple[str, ...] = field(default_factory=tuple)
    blocked_network_requests: tuple[str, ...] = field(default_factory=tuple)
    truncated: bool = False
    omitted_reason: str | None = None
    started_at: str = ""
    finished_at: str = ""

    def __post_init__(self) -> None:
        if self.status not in VALID_CHECK_STATUSES:
            raise ValueError(f"invalid RuntimeCheck.status: {self.status!r}")


def build_runtime_check(
    *,
    check_id: str,
    kind: str,
    related_ac_ids: tuple[str, ...],
    parameters: dict,
    status: str,
    action_performed: str,
    observation: str,
    measurements: dict,
    screenshot_bytes: bytes | None,
    console_errors: tuple[str, ...] = (),
    page_errors: tuple[str, ...] = (),
    blocked_network_requests: tuple[str, ...] = (),
    started_at: str = "",
    finished_at: str = "",
) -> tuple[RuntimeCheck, bytes | None]:
    """Construct a `RuntimeCheck`, applying sanitization and the
    per-check bounds (screenshot size) automatically -- callers
    (`peos/runtime_browser.py`) never hand-manage truncation bookkeeping.
    Returns `(check, screenshot_bytes_to_persist_or_None)`; the caller
    persists the returned bytes (if any) at `check.screenshot_path`.
    """
    truncated = False
    omitted_reason: str | None = None
    screenshot_path: str | None = None
    screenshot_sha256: str | None = None
    screenshot_to_persist: bytes | None = None

    if screenshot_bytes is not None:
        if len(screenshot_bytes) > MAX_SCREENSHOT_BYTES:
            truncated = True
            omitted_reason = (
                f"screenshot exceeded the {MAX_SCREENSHOT_BYTES} byte bound "
                f"({len(screenshot_bytes)} bytes) and was omitted"
            )
        else:
            screenshot_path = f"{SCREENSHOTS_DIRNAME}/{check_id}.png"
            screenshot_sha256 = hashlib.sha256(screenshot_bytes).hexdigest()
            screenshot_to_persist = screenshot_bytes

    console_errors, console_list_truncated = _bounded_text_list(console_errors)
    page_errors, page_list_truncated = _bounded_text_list(page_errors)
    blocked_network_requests, blocked_list_truncated = _bounded_text_list(blocked_network_requests)
    sanitized_parameters, parameters_truncated = _bounded_dict(parameters)
    sanitized_measurements, measurements_truncated = _bounded_dict(measurements)
    truncated = truncated or any((
        console_list_truncated, page_list_truncated, blocked_list_truncated,
        parameters_truncated, measurements_truncated,
    ))

    check = RuntimeCheck(
        check_id=check_id,
        kind=kind,
        catalog_version=RUNTIME_CHECK_CATALOG_VERSION,
        related_ac_ids=tuple(related_ac_ids),
        parameters=sanitized_parameters,
        status=status,
        action_performed=sanitize_human_text(action_performed),
        observation=sanitize_human_text(observation),
        measurements=sanitized_measurements,
        screenshot_path=screenshot_path,
        screenshot_sha256=screenshot_sha256,
        console_errors=console_errors,
        page_errors=page_errors,
        blocked_network_requests=blocked_network_requests,
        truncated=truncated,
        omitted_reason=omitted_reason,
        started_at=started_at,
        finished_at=finished_at,
    )
    return check, screenshot_to_persist


@dataclass(frozen=True)
class ServiceReadiness:
    service: str  # "backend" | "frontend"
    command: tuple[str, ...]
    resolved_port: int
    ready: bool
    waited_seconds: float
    captured_stdout_tail: str = ""
    captured_stderr_tail: str = ""
    truncated: bool = False


def build_service_readiness(
    *, service: str, command: tuple[str, ...], resolved_port: int, ready: bool,
    waited_seconds: float, stdout: str = "", stderr: str = "",
) -> ServiceReadiness:
    """Codex implementation review Finding 6: `sanitize_human_text`
    applies `peos.diagnostics.MAX_DIAGNOSTIC_CHARS` (500 chars), not this
    module's own `MAX_SERVICE_TAIL_CHARS` (64 KiB) -- calling it directly
    silently re-truncated every tail down to 500 characters while
    `truncated` was computed against the wrong (64 KiB) bound, so a
    601-65536-character log was marked `truncated=False` despite having
    already lost everything past character 500. Secret redaction
    (`redact`, no length bound) and this module's own bound are now
    applied, and compared, separately and consistently.
    """
    redacted_stdout = redact(stdout)
    redacted_stderr = redact(stderr)
    truncated = len(redacted_stdout) > MAX_SERVICE_TAIL_CHARS or len(redacted_stderr) > MAX_SERVICE_TAIL_CHARS
    stdout_tail = redacted_stdout[-MAX_SERVICE_TAIL_CHARS:]
    stderr_tail = redacted_stderr[-MAX_SERVICE_TAIL_CHARS:]
    return ServiceReadiness(
        service=service, command=tuple(command), resolved_port=resolved_port, ready=ready,
        waited_seconds=waited_seconds, captured_stdout_tail=stdout_tail,
        captured_stderr_tail=stderr_tail, truncated=truncated,
    )


@dataclass(frozen=True)
class RuntimeEvidence:
    run_id: str
    cycle_label: str
    workspace_snapshot_identity: str
    baseline_commit: str
    catalog_version: str
    playwright_version: str
    browser_version: str
    browser_environment: dict
    service_readiness: tuple[ServiceReadiness, ...] = field(default_factory=tuple)
    checks: tuple[RuntimeCheck, ...] = field(default_factory=tuple)
    execution_integrity_passed: bool = False
    truncated: bool = False
    started_at: str = ""
    finished_at: str = ""

    @property
    def all_checks_passed(self) -> bool:
        return all(c.status == "PASS" for c in self.checks)

    def ac_status(self, ac_id: str) -> str:
        """SPEC-006 Section 13 hardening item C: the four-state rollup
        for one AC ID. Returns `"NOT_APPLICABLE"` if no check names it;
        `"PASS"` only if every mapped check is `"PASS"`; `"FAIL"` if any
        mapped check is `"FAIL"`; otherwise `"NOT_EXECUTED"`.
        """
        mapped = [c for c in self.checks if ac_id in c.related_ac_ids]
        if not mapped:
            return "NOT_APPLICABLE"
        if any(c.status == "FAIL" for c in mapped):
            return "FAIL"
        if all(c.status == "PASS" for c in mapped):
            return "PASS"
        return "NOT_EXECUTED"

    def runtime_evidenced_ac_status(self) -> dict[str, str]:
        """SPEC-006 Section 13/14: the complete per-round rollup mapping,
        domain-restricted to AC IDs at least one check names (an AC with
        no mapped check is NOT_APPLICABLE and is therefore absent from
        this mapping's domain, not merely valued NOT_APPLICABLE within
        it)."""
        ac_ids: set[str] = set()
        for c in self.checks:
            ac_ids.update(c.related_ac_ids)
        return {ac_id: self.ac_status(ac_id) for ac_id in ac_ids}


def _serialize_check(check: RuntimeCheck) -> dict:
    return {
        "check_id": check.check_id,
        "kind": check.kind,
        "catalog_version": check.catalog_version,
        "related_ac_ids": list(check.related_ac_ids),
        "parameters": check.parameters,
        "status": check.status,
        "action_performed": check.action_performed,
        "observation": check.observation,
        "measurements": check.measurements,
        "screenshot_path": check.screenshot_path,
        "screenshot_sha256": check.screenshot_sha256,
        "console_errors": list(check.console_errors),
        "page_errors": list(check.page_errors),
        "blocked_network_requests": list(check.blocked_network_requests),
        "truncated": check.truncated,
        "omitted_reason": check.omitted_reason,
        "started_at": check.started_at,
        "finished_at": check.finished_at,
    }


def _serialize_service_readiness(s: ServiceReadiness) -> dict:
    return {
        "service": s.service,
        "command": list(s.command),
        "resolved_port": s.resolved_port,
        "ready": s.ready,
        "waited_seconds": s.waited_seconds,
        "captured_stdout_tail": s.captured_stdout_tail,
        "captured_stderr_tail": s.captured_stderr_tail,
        "truncated": s.truncated,
    }


def serialize_evidence(evidence: RuntimeEvidence) -> dict:
    """Build the JSON-ready dict explicitly, field by field -- never a
    generic serializer -- matching `peos/ledger.py`'s own discipline for
    the same class of persisted, non-secret orchestrator record."""
    return {
        "run_id": evidence.run_id,
        "cycle_label": evidence.cycle_label,
        "workspace_snapshot_identity": evidence.workspace_snapshot_identity,
        "baseline_commit": evidence.baseline_commit,
        "catalog_version": evidence.catalog_version,
        "playwright_version": evidence.playwright_version,
        "browser_version": evidence.browser_version,
        "browser_environment": evidence.browser_environment,
        "service_readiness": [_serialize_service_readiness(s) for s in evidence.service_readiness],
        "checks": [_serialize_check(c) for c in evidence.checks],
        "execution_integrity_passed": evidence.execution_integrity_passed,
        "truncated": evidence.truncated,
        "started_at": evidence.started_at,
        "finished_at": evidence.finished_at,
    }


@dataclass(frozen=True)
class PersistedEvidence:
    evidence_dir: Path  # <repo_root>/.peos/runs/<run_id>/runtime-evidence/<cycle_label>
    evidence_json_path: Path
    evidence_hash_path: Path
    evidence_json_sha256: str


def persist_evidence(
    repo_root: Path, run_id: str, evidence: RuntimeEvidence, screenshots: dict[str, bytes],
) -> PersistedEvidence:
    """Persist `evidence` under
    `.peos/runs/<run_id>/runtime-evidence/<cycle_label>/` -- exclusive
    per-cycle directory creation (never overwrites an earlier round's
    evidence, SPEC-006 Section 9 "Per-cycle identity"), atomic writes,
    the hash in a separate sidecar file (never embedded in the JSON it
    hashes), symlink rejection at every path component.

    Enforces the package-level screenshot-bytes bound
    (`MAX_TOTAL_SCREENSHOT_BYTES_PER_ROUND`): screenshots are written in
    the order `evidence.checks` lists them, and once the running total
    would exceed the bound, remaining screenshots are skipped (their
    `RuntimeCheck.screenshot_path` is cleared in the persisted JSON, and
    the package-level `truncated` flag is forced true) -- never a
    partial/corrupt image file.
    """
    cycle_slug = _cycle_label_slug(evidence.cycle_label)
    relative_dir = f"{EVIDENCE_DIRNAME}/{cycle_slug}"
    runs_relative = f".peos/runs/{run_id}"

    containment_error = assert_no_symlink_components(repo_root, runs_relative)
    if containment_error is not None:
        raise RuntimeEvidenceError(f"run directory failed a containment check: {containment_error}")

    run_dir = repo_root / runs_relative
    run_dir.mkdir(parents=True, exist_ok=True)

    containment_error = assert_no_symlink_components(run_dir, relative_dir)
    if containment_error is not None:
        raise RuntimeEvidenceError(f"evidence directory failed a containment check: {containment_error}")

    evidence_dir = run_dir / relative_dir
    try:
        evidence_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise RuntimeEvidenceError(
            f"evidence directory already exists -- refusing to overwrite an earlier round's "
            f"evidence: {evidence_dir}"
        ) from exc

    screenshots_dir = evidence_dir / SCREENSHOTS_DIRNAME
    total_screenshot_bytes = 0
    # Codex implementation review Finding 6: roll up every check's and
    # every service's own `truncated` flag into the package-level one --
    # the original draft only ever set this from the caller-supplied
    # `evidence.truncated` and this function's own screenshot-bound
    # overflow, silently losing a per-check/per-service truncation that
    # happened earlier (e.g. in `build_runtime_check`).
    package_truncated = evidence.truncated or any(
        sr.truncated for sr in evidence.service_readiness
    )
    persisted_checks: list[RuntimeCheck] = []
    for check in evidence.checks:
        if check.truncated:
            package_truncated = True
        raw_bytes = screenshots.get(check.check_id)
        if check.screenshot_path is None or raw_bytes is None:
            persisted_checks.append(check)
            continue
        # Codex implementation review Finding 7: `persist_evidence` is a
        # public function `screenshots` could in principle be supplied
        # to directly (bypassing `build_runtime_check`'s own bound/hash
        # computation) -- defense in depth re-validates both the 4 MiB
        # per-screenshot bound and the recorded hash here, independently.
        #
        # `check.screenshot_sha256 is None` is the worker-subprocess
        # path's own documented contract (`_check_from_worker_dict`:
        # "recomputed by persist_evidence from the actual bytes it
        # writes") -- not a caller-supplied hash to validate against, so
        # it must not be treated as a mismatch. Live-run finding: the
        # original code compared `raw_bytes`'s hash to `None` directly,
        # which is always false, silently stripping every
        # worker-subprocess screenshot and force-setting the
        # package-level `truncated` flag on every real run.
        computed_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        hash_matches = check.screenshot_sha256 is None or computed_sha256 == check.screenshot_sha256
        if len(raw_bytes) > MAX_SCREENSHOT_BYTES or not hash_matches:
            package_truncated = True
            reason = (
                "per-screenshot size bound exceeded" if len(raw_bytes) > MAX_SCREENSHOT_BYTES
                else "supplied screenshot bytes did not match the recorded hash"
            )
            persisted_checks.append(
                RuntimeCheck(**{**check.__dict__, "screenshot_path": None, "screenshot_sha256": None,
                                 "truncated": True, "omitted_reason": reason})
            )
            continue
        if total_screenshot_bytes + len(raw_bytes) > MAX_TOTAL_SCREENSHOT_BYTES_PER_ROUND:
            package_truncated = True
            persisted_checks.append(
                RuntimeCheck(**{**check.__dict__, "screenshot_path": None, "screenshot_sha256": None,
                                 "truncated": True,
                                 "omitted_reason": "per-round total screenshot-evidence bound exceeded"})
            )
            continue
        screenshots_dir.mkdir(exist_ok=True)
        dst = evidence_dir / check.screenshot_path
        _atomic_write(dst, raw_bytes)
        total_screenshot_bytes += len(raw_bytes)
        persisted_checks.append(
            check if check.screenshot_sha256 is not None
            else RuntimeCheck(**{**check.__dict__, "screenshot_sha256": computed_sha256})
        )

    final_evidence = RuntimeEvidence(**{**evidence.__dict__, "checks": tuple(persisted_checks),
                                         "truncated": package_truncated})

    payload = serialize_evidence(final_evidence)
    text = json.dumps(payload, indent=2, sort_keys=True)
    if len(text.encode("utf-8")) > MAX_EVIDENCE_JSON_BYTES:
        raise RuntimeEvidenceError(
            f"serialized evidence.json exceeds the {MAX_EVIDENCE_JSON_BYTES}-byte bound "
            f"({len(text.encode('utf-8'))} bytes) even after per-field bounds -- this should "
            "be structurally impossible given MAX_CHECKS_PER_ROUND; failing closed rather "
            "than silently truncating the whole document."
        )

    evidence_json_path = evidence_dir / EVIDENCE_FILENAME
    _atomic_write(evidence_json_path, text.encode("utf-8"))
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    evidence_hash_path = evidence_dir / EVIDENCE_HASH_FILENAME
    _atomic_write(evidence_hash_path, digest.encode("ascii"))

    return PersistedEvidence(
        evidence_dir=evidence_dir, evidence_json_path=evidence_json_path,
        evidence_hash_path=evidence_hash_path, evidence_json_sha256=digest,
    )


def _atomic_write(path: Path, data: bytes) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def staged_evidence_path(workspace_root: Path, cycle_label: str) -> Path:
    """The fixed, documented, cycle-qualified staging path inside the
    isolated workspace -- distinct from the authoritative
    `.peos/runs/<run_id>/...` path (which is never itself duplicated
    into the workspace; only this evidence copy is, per SPEC-006
    Section 9's one deliberate asymmetry from the Run Ledger)."""
    return workspace_root / ".peos" / "runtime-evidence" / _cycle_label_slug(cycle_label)


def stage_evidence_into_workspace(workspace_root: Path, persisted: PersistedEvidence, cycle_label: str) -> Path:
    """Copy the persisted evidence directory into the isolated workspace,
    read-only (OS permission bits, a convention/speed-bump, not a
    tamper-prevention claim -- SPEC-006 Section 9), at a fixed,
    cycle-qualified path so either agent's file tools can inspect it.
    Returns the staged directory's path inside the workspace.
    """
    staged_dir = staged_evidence_path(workspace_root, cycle_label)
    if staged_dir.exists():
        shutil.rmtree(staged_dir)
    shutil.copytree(persisted.evidence_dir, staged_dir)
    for path in staged_dir.rglob("*"):
        if path.is_file():
            os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    os.chmod(staged_dir, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    return staged_dir


@dataclass(frozen=True)
class EvidenceIdentityResult:
    ok: bool
    reason: str | None = None


def reverify_evidence_identity(persisted: PersistedEvidence, staged_dir: Path) -> EvidenceIdentityResult:
    """SPEC-006 Section 9 identity re-verification, mirroring SPEC-004's
    static-context-artifact pattern: before every Claude/Codex invocation
    that consumes this round's staged evidence copy, re-verify the staged
    `evidence.json`'s hash still equals the authoritative copy's recorded
    sidecar hash. A mismatch (the staged copy altered by any means after
    staging) is the tamper-*detection* mechanism this specification
    relies on -- never a silent re-hash, never a Human Gate.
    """
    staged_evidence_path = staged_dir / EVIDENCE_FILENAME
    if not staged_evidence_path.is_file() or staged_evidence_path.is_symlink():
        return EvidenceIdentityResult(False, f"staged evidence.json is missing or not a regular file: {staged_evidence_path}")
    try:
        staged_bytes = staged_evidence_path.read_bytes()
    except OSError as exc:
        return EvidenceIdentityResult(False, f"staged evidence.json could not be read: {exc}")
    staged_hash = hashlib.sha256(staged_bytes).hexdigest()
    if staged_hash != persisted.evidence_json_sha256:
        return EvidenceIdentityResult(
            False,
            f"staged evidence copy no longer matches the authoritative recorded hash "
            f"(expected {persisted.evidence_json_sha256}, found {staged_hash})",
        )
    return EvidenceIdentityResult(True)
