"""Governing-specification resolution (SPEC-001 Phase 1 -- Intake, AC-002).

PEOS must identify the single approved specification that governs an
implementation task before any implementation agent is invoked. This
module implements that lookup deterministically from repository files --
no agent call is involved in choosing the governing spec.

Matching is a simple case-insensitive keyword-overlap score between the
task text and each candidate specification's title/filename. This is a
deliberately simple heuristic (SPEC-001 Section 16: "prefer the smallest
maintainable local orchestration solution"); it is not natural-language
understanding, and callers should pass an explicit `--spec` path when the
heuristic is not expected to be reliable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_SPEC_FILENAME_RE = re.compile(r"^SPEC-\d+.*\.md$", re.IGNORECASE)
_STATUS_RE = re.compile(r"^\s*\*{0,2}Status:\*{0,2}\s*(\S+)", re.MULTILINE)
_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with",
    "implement", "implementing", "add", "adding", "fix", "fixing",
    "update", "updating", "create", "creating", "spec", "specification",
}


@dataclass(frozen=True)
class SpecCandidate:
    path: Path
    title: str
    status: str


@dataclass(frozen=True)
class SpecResolution:
    """Result of resolving a governing specification for a task.

    Exactly one of `spec` or `gate_reason` is set. `gate_reason` means
    Phase 1 (Intake) must stop and escalate to the Human Engineering Lead
    (SPEC-001 Human Gates #1/#2) rather than proceeding to implementation.
    """

    spec: SpecCandidate | None = None
    gate_reason: str | None = None
    candidates_considered: tuple[SpecCandidate, ...] = field(default_factory=tuple)


def _tokens(text: str) -> set[str]:
    return {
        t for t in _TOKEN_RE.findall(text.lower())
        if len(t) > 2 and t not in _STOPWORDS
    }


def _read_candidate(path: Path) -> SpecCandidate:
    text = path.read_text(encoding="utf-8", errors="replace")
    title_match = _TITLE_RE.search(text)
    status_match = _STATUS_RE.search(text)
    title = title_match.group(1) if title_match else path.stem
    status = status_match.group(1) if status_match else "UNKNOWN"
    return SpecCandidate(path=path, title=title, status=status)


def list_specs(specs_dir: Path) -> list[SpecCandidate]:
    """List all SPEC-NNN-*.md files under `specs_dir` (TEMPLATE.md excluded)."""
    if not specs_dir.exists():
        return []
    candidates = [
        _read_candidate(p)
        for p in sorted(specs_dir.iterdir())
        if p.is_file() and _SPEC_FILENAME_RE.match(p.name)
    ]
    return candidates


def resolve_governing_spec(
    task: str,
    specs_dir: Path,
    explicit_spec: Path | None = None,
) -> SpecResolution:
    """Resolve the single governing specification for `task`.

    If `explicit_spec` is given, it is used directly and must have
    Status: Approved. Otherwise, candidates are drawn from `specs_dir`
    filtered to Status: Approved, scored by keyword overlap against
    `task`, and a resolution is only returned when exactly one candidate
    has the (positive) maximum score.
    """
    if explicit_spec is not None:
        if not explicit_spec.exists():
            return SpecResolution(
                gate_reason=f"--spec path does not exist: {explicit_spec}"
            )
        candidate = _read_candidate(explicit_spec)
        if candidate.status.lower() != "approved":
            return SpecResolution(
                gate_reason=(
                    f"Specification {explicit_spec} has Status: "
                    f"{candidate.status!r}, not Approved. PEOS requires an "
                    "Approved specification before implementation begins "
                    "(SPEC-001 Human Gate #1)."
                ),
                candidates_considered=(candidate,),
            )
        return SpecResolution(spec=candidate, candidates_considered=(candidate,))

    all_candidates = list_specs(specs_dir)
    approved = [c for c in all_candidates if c.status.lower() == "approved"]
    if not approved:
        return SpecResolution(
            gate_reason=(
                "No approved specification was found under "
                f"{specs_dir}. PEOS does not allow an implementation agent "
                "to invent requirements (SPEC-001 Human Gate #1); write and "
                "approve a specification first, or pass --spec explicitly."
            ),
            candidates_considered=tuple(all_candidates),
        )

    task_tokens = _tokens(task)
    scored = [
        (c, len(task_tokens & _tokens(f"{c.title} {c.path.stem}")))
        for c in approved
    ]
    best_score = max(score for _, score in scored)
    if best_score == 0:
        return SpecResolution(
            gate_reason=(
                "Could not identify a governing specification for this task "
                "from task text alone (no keyword overlap with any approved "
                "specification title). Pass --spec explicitly "
                "(SPEC-001 Human Gate #1/#2)."
            ),
            candidates_considered=tuple(approved),
        )

    top = [c for c, score in scored if score == best_score]
    if len(top) > 1:
        names = ", ".join(str(c.path) for c in top)
        return SpecResolution(
            gate_reason=(
                "Specification identification is ambiguous: multiple "
                f"approved specifications match equally well ({names}). "
                "Pass --spec explicitly (SPEC-001 Human Gate #2)."
            ),
            candidates_considered=tuple(approved),
        )

    return SpecResolution(spec=top[0], candidates_considered=tuple(approved))
