"""Context Recovery (SPEC-004 Requirement 2/Model section -- NEW, purely
deterministic, no agent call).

Runs before Planning and feeds the Delivery Report: a deterministic
listing of the already-approved context that should inform what the
Human Engineering Lead writes next -- every approved specification under
`docs/specifications/`, every decision record under `docs/decisions/`,
and every validation record under `docs/validation/`. This is
deliberately a complete listing, not a relevance-ranked subset (SPEC-001
Section 16: "prefer the smallest maintainable local orchestration
solution" -- a keyword-overlap ranking heuristic already exists for
*selecting* the one governing specification, in `peos/spec.py`; Context
Recovery's job is only to *gather* what already exists, not to guess
which parts of it will matter).

Context Recovery's own output does not depend on Planning (spec
resolution) having succeeded -- it runs and is reflected in the Delivery
Report even on a run that stops at Human Gate #1 (no governing spec),
which is exactly why `peos/workflow.py` runs it before, and independently
of, spec resolution (SPEC-004 AC-5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from peos.spec import list_specs


@dataclass(frozen=True)
class ContextRecoveryResult:
    related_specs: tuple[str, ...] = field(default_factory=tuple)
    related_decisions: tuple[str, ...] = field(default_factory=tuple)
    related_validation_records: tuple[str, ...] = field(default_factory=tuple)


def _list_markdown_files(directory: Path) -> tuple[str, ...]:
    if not directory.is_dir():
        return ()
    return tuple(
        sorted(
            p.name for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() == ".md" and p.name.upper() != "README.MD"
        )
    )


def run_context_recovery(repo_root: Path, specs_dir: Path | None = None) -> ContextRecoveryResult:
    """Deterministically gather already-approved context from the
    repository. No agent call is made; this never invents, authors, or
    ranks content -- it only lists what is already there.
    """
    specs_dir = specs_dir or (repo_root / "docs" / "specifications")
    related_specs = tuple(
        sorted(c.path.name for c in list_specs(specs_dir) if c.status.lower() == "approved")
    )
    related_decisions = _list_markdown_files(repo_root / "docs" / "decisions")
    related_validation_records = _list_markdown_files(repo_root / "docs" / "validation")
    return ContextRecoveryResult(
        related_specs=related_specs,
        related_decisions=related_decisions,
        related_validation_records=related_validation_records,
    )
