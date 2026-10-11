"""Static External Context (SPEC-004 Requirement 21, generalizing the
original Pixso-specific "Requirement 12").

Planning (`peos/plan.py`) deterministically parses the resolved governing
specification's own text for a conventionally-marked `## Design Context`
/ `### Design Context` section -- the same "indented line under a
recognized heading" authoring convention `peos/verification_plan.py`
already uses for spec-declared verification commands -- whose indented
lines each name one required static artifact, as a path relative to the
repository root (e.g. a Pixso export already committed to the
repository, a reference image path).

This module resolves and validates each declared artifact:

- Containment first (fails closed, never a Human Gate): a declared path
  that resolves outside the repository root, or through a symlink at any
  path component, is a containment/safety violation
  (`peos/fsguard.py::assert_no_symlink_components`) -- `FAILED`, never a
  silent read.
- Existence/type second (Human Gate #11): a path that resolves safely but
  is missing, or is not a regular, readable file, stops Planning at
  `HUMAN_GATE` #11 -- before any workspace is created or either agent is
  invoked.
- A resolved artifact gets a deterministic content identity (SHA-256 of
  its bytes), computed once, at Planning.

Identity re-verification (`reverify_identity`) is a separate, later-round
check: the content identity recorded at Planning is the artifact's fixed
identity for the remainder of the run; any drift (content, containment,
file type/readability, or a staged-copy mismatch) fails the run closed,
immediately, before the next agent invocation that would have consumed
it -- never a silent re-hash, never a Delivery Report note, never a
`HUMAN_GATE` (SPEC-004 AC-39, Known Limitations).

Staged-copy structural check (SPEC-004 remediation Finding 5): a matching
content hash is never, on its own, treated as proof the staged copy is
safe -- the staged path is first checked structurally (no symlink at any
component, including the final file itself, via
`peos.fsguard.assert_no_symlink_components` against the workspace root)
*before* its bytes are ever hashed. A staged file replaced by a symlink
pointing at a byte-for-byte-identical authoritative file is rejected on
that structural check alone; its matching bytes are never reached.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from peos.fsguard import assert_no_symlink_components

_HEADING_RE = re.compile(r"^#{1,6}\s")
_DESIGN_CONTEXT_HEADING_RE = re.compile(r"^#{1,6}\s*[\d.]*\s*Design Context\b", re.IGNORECASE)


def parse_static_context_declaration(spec_text: str) -> tuple[str, ...]:
    """Extract declared, repository-relative artifact paths from the
    governing specification's `## Design Context` / `### Design Context`
    section(s). Deterministic text parsing only; never AI-interpreted.
    Order-preserving, de-duplicated. Returns an empty tuple when no such
    section is present -- the normal case for most specifications.
    """
    declared: list[str] = []
    in_section = False
    for line in spec_text.splitlines():
        if _HEADING_RE.match(line):
            in_section = bool(_DESIGN_CONTEXT_HEADING_RE.match(line))
            continue
        if not in_section:
            continue
        if line.startswith("    ") or line.startswith("\t"):
            stripped = line.strip().strip("`")
            if stripped:
                declared.append(stripped)
    seen: set[str] = set()
    unique: list[str] = []
    for d in declared:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return tuple(unique)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class StaticContextArtifact:
    declared_path: str
    resolved_path: Path
    content_hash: str
    staged_relative_path: str | None = None


@dataclass(frozen=True)
class StaticContextResolution:
    declared: tuple[str, ...] = field(default_factory=tuple)
    artifacts: tuple[StaticContextArtifact, ...] = field(default_factory=tuple)
    gate_reason: str | None = None
    fail_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.gate_reason is None and self.fail_reason is None


def resolve_static_context(repo_root: Path, spec_text: str) -> StaticContextResolution:
    """Resolve every artifact declared in `spec_text`'s Design Context
    section against `repo_root`. Containment violations fail closed
    first (`fail_reason`); a missing/wrong-type artifact gates to Human
    Gate #11 (`gate_reason`) instead, and only once containment is
    already established -- so an escape is never mistaken for "just
    missing".
    """
    declared = parse_static_context_declaration(spec_text)
    if not declared:
        return StaticContextResolution()

    artifacts: list[StaticContextArtifact] = []
    for rel in declared:
        containment_error = assert_no_symlink_components(repo_root, rel)
        if containment_error is not None:
            return StaticContextResolution(
                declared=declared,
                fail_reason=(
                    f"Static external-context artifact declared by the governing "
                    f"specification failed a containment/safety check: {containment_error}"
                ),
            )
        resolved = (repo_root / rel)
        if not resolved.is_file() or resolved.is_symlink():
            return StaticContextResolution(
                declared=declared,
                gate_reason=(
                    "Static external-context artifact declared by the governing "
                    f"specification does not resolve to a present, regular, "
                    f"repository-resident file: {rel}"
                ),
            )
        artifacts.append(
            StaticContextArtifact(declared_path=rel, resolved_path=resolved, content_hash=_sha256_file(resolved))
        )
    return StaticContextResolution(declared=declared, artifacts=tuple(artifacts))


def stage_into_workspace(workspace_root: Path, artifact: StaticContextArtifact, repo_root: Path) -> StaticContextArtifact:
    """Copy a resolved artifact into the isolated workspace at the same
    repository-relative path, so either agent's ordinary file tools can
    read it (unlike the Run Ledger, which is never staged -- see
    peos/ledger.py). Returns a new `StaticContextArtifact` recording the
    staged relative path.
    """
    rel = Path(artifact.declared_path)
    dst = workspace_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artifact.resolved_path, dst)
    return StaticContextArtifact(
        declared_path=artifact.declared_path,
        resolved_path=artifact.resolved_path,
        content_hash=artifact.content_hash,
        staged_relative_path=rel.as_posix(),
    )


@dataclass(frozen=True)
class IdentityDriftResult:
    ok: bool
    reason: str | None = None


def reverify_identity(artifact: StaticContextArtifact, repo_root: Path, workspace_root: Path) -> IdentityDriftResult:
    """Re-verify, in order, before every subsequent agent invocation that
    consumes `artifact` (SPEC-004 AC-39):

    1. containment still holds (no symlink introduced since Planning);
    2. the file still exists and is still a regular, readable file;
    3. its current content hash still equals the identity recorded at
       Planning;
    4. the staged copy in the isolated workspace still matches that same
       identity.

    Any failure fails the run closed -- this never recomputes/adopts a
    new identity itself; the caller (peos/workflow.py) is responsible for
    stopping before the next invocation.
    """
    containment_error = assert_no_symlink_components(repo_root, artifact.declared_path)
    if containment_error is not None:
        return IdentityDriftResult(False, f"containment check failed on re-verification: {containment_error}")

    if not artifact.resolved_path.is_file() or artifact.resolved_path.is_symlink():
        return IdentityDriftResult(
            False, f"artifact is no longer a present, regular file: {artifact.resolved_path}",
        )

    try:
        current_hash = _sha256_file(artifact.resolved_path)
    except OSError as exc:
        return IdentityDriftResult(False, f"artifact could not be read for re-verification: {exc}")

    if current_hash != artifact.content_hash:
        return IdentityDriftResult(
            False,
            f"artifact content identity drifted since Planning for {artifact.declared_path} "
            f"(expected {artifact.content_hash}, found {current_hash})",
        )

    if artifact.staged_relative_path is not None:
        # SPEC-004 remediation Finding 5 (MAJOR): a matching content hash
        # is not sufficient on its own -- the staged copy must also be
        # structurally safe: no symlink at any path component (including
        # the final file itself), and contained within `workspace_root`.
        # Checked *before* any hash comparison, so a staged path replaced
        # by a symlink pointing at a byte-for-byte-identical authoritative
        # file is rejected on structure alone, never "resolved and found
        # to match". This mirrors the authoritative-source check above
        # (which already rejects `artifact.resolved_path.is_symlink()`)
        # for the staged copy specifically.
        staged_containment_error = assert_no_symlink_components(workspace_root, artifact.staged_relative_path)
        if staged_containment_error is not None:
            return IdentityDriftResult(
                False,
                f"staged copy failed a structural containment/symlink check: {staged_containment_error}",
            )
        staged_path = workspace_root / artifact.staged_relative_path
        if not staged_path.is_file() or staged_path.is_symlink():
            return IdentityDriftResult(
                False, f"staged copy is missing or is not a regular file: {staged_path}",
            )
        try:
            staged_hash = _sha256_file(staged_path)
        except OSError as exc:
            return IdentityDriftResult(False, f"staged copy could not be read for re-verification: {exc}")
        if staged_hash != artifact.content_hash:
            return IdentityDriftResult(
                False, f"staged workspace copy no longer matches the pinned identity: {staged_path}",
            )

    return IdentityDriftResult(True)
