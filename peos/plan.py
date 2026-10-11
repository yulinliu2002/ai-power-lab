"""Planning (SPEC-004 Requirement 2 -- extends SPEC-001 Phase 1/"Intake").

`build_plan` wraps `peos.spec.resolve_governing_spec` (unchanged: Human
Gates #1/#2 are unchanged, and this still only *selects* among already-
approved specifications -- Planning never authors or invents a
requirement) and deterministically extracts two more things already
implicit in an approved spec's text, using the same "parse a
conventionally-marked section of the spec's own Markdown" approach
`peos/verification_plan.py` already uses for spec-declared verification
commands:

- an optional `max_cycles` override (a conventionally-marked
  `Max Cycles Override: N` line anywhere in the spec text; absent or
  invalid is simply "no override", never an error -- the CLI `--max-
  cycles` flag, not this, is where an out-of-range value is a hard input
  failure, per SPEC-004 Requirement 6/AC-4);
- a Static External Context declaration (`peos/static_context.py`, if the
  spec declares one).

Only reached once a governing specification has actually resolved --
Planning still only fails via Human Gates #1/#2 (no/ambiguous spec) and
#11 (unresolvable static context), never a guessed extension of either.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from peos.spec import SpecResolution, resolve_governing_spec
from peos.static_context import StaticContextResolution, resolve_static_context

_MAX_CYCLES_OVERRIDE_RE = re.compile(r"(?im)^\s*\*{0,2}Max Cycles Override\*{0,2}\s*:\s*(\d+)\s*$")

# Round Packet element 9 (peos/round_packet.py): the complete governing
# acceptance-criteria set, parsed from the resolved specification's own
# `## Acceptance Criteria` text using the two conventions already present
# in this repository's own specifications: a per-AC sub-heading (SPEC-001:
# "### AC-001 -- Title") and a bolded bullet (SPEC-003/SPEC-004:
# "- [ ] **AC-1** ..."). Deterministic text parsing only, same spirit as
# `peos/verification_plan.py`'s spec-declared-command convention -- not
# natural-language understanding, and not claimed to be exhaustive over
# every way a specification could number its acceptance criteria.
_AC_HEADING_RE = re.compile(r"^#{1,6}\s+(AC-\d+[a-z]?)\b")
_AC_BULLET_RE = re.compile(r"^\s*-\s*\[.\]\s*\*{0,2}(AC-\d+[a-z]?)\*{0,2}\b")

MIN_MAX_CYCLES = 1
MAX_MAX_CYCLES = 5

PlanSpecResolver = Callable[[str, Path, "Path | None"], SpecResolution]


@dataclass(frozen=True)
class PlanArtifact:
    resolution: SpecResolution
    max_cycles_override: int | None = None
    static_context: StaticContextResolution = field(default_factory=StaticContextResolution)
    acceptance_criteria_ids: tuple[str, ...] = field(default_factory=tuple)
    # SPEC-004 remediation Finding 1 (BLOCKER): the SHA-256 content hash of
    # the *exact bytes* this Planning pass actually parsed
    # (`resolution.spec.path`), computed here and never recomputed later.
    # `peos/workflow.py` treats this as the governing specification's one
    # fixed identity for the remainder of the run -- never re-derived from
    # whatever happens to be on disk after the isolated workspace is
    # created, and never silently refreshed on drift. Empty when no spec
    # resolved (`resolution.spec is None`).
    governing_spec_content_hash: str = ""


def parse_acceptance_criteria_ids(spec_text: str) -> tuple[str, ...]:
    """Extract every distinct declared AC identifier from `spec_text`,
    order-preserving, de-duplicated. Returns an empty tuple for a
    specification that declares no numbered acceptance criteria (not an
    error -- Codex's own acceptance-criteria assessment already permits
    `null` for exactly this case)."""
    ids: list[str] = []
    seen: set[str] = set()
    for line in spec_text.splitlines():
        match = _AC_HEADING_RE.match(line) or _AC_BULLET_RE.match(line)
        if match is None:
            continue
        ac_id = match.group(1)
        if ac_id not in seen:
            seen.add(ac_id)
            ids.append(ac_id)
    return tuple(ids)


def parse_max_cycles_override(spec_text: str) -> int | None:
    """Deterministic text parsing only. An absent, malformed, or
    out-of-range (`[1, 5]`) declared value is simply treated as "no
    override" -- Planning never fails a run over a spec-declared
    override; only the CLI flag's own validation (`peos/cli.py`) is a
    hard input-error path (SPEC-004 Requirement 6).
    """
    match = _MAX_CYCLES_OVERRIDE_RE.search(spec_text)
    if match is None:
        return None
    value = int(match.group(1))
    if MIN_MAX_CYCLES <= value <= MAX_MAX_CYCLES:
        return value
    return None


def build_plan(
    task: str,
    specs_dir: Path,
    explicit_spec: Path | None,
    repo_root: Path,
    spec_resolver: PlanSpecResolver = resolve_governing_spec,
) -> PlanArtifact:
    resolution = spec_resolver(task, specs_dir, explicit_spec)
    if resolution.spec is None:
        return PlanArtifact(resolution=resolution)

    # SPEC-004 remediation Finding 1 (BLOCKER): hash the *exact same bytes*
    # that are about to be decoded and parsed below -- one read, one set
    # of bytes, shared by the identity hash and the parsed representation,
    # so the two can never refer to different content even in principle.
    spec_bytes = resolution.spec.path.read_bytes()
    governing_spec_content_hash = hashlib.sha256(spec_bytes).hexdigest()
    spec_text = spec_bytes.decode("utf-8", errors="replace")
    max_cycles_override = parse_max_cycles_override(spec_text)
    static_context = resolve_static_context(repo_root, spec_text)
    acceptance_criteria_ids = parse_acceptance_criteria_ids(spec_text)
    return PlanArtifact(
        resolution=resolution, max_cycles_override=max_cycles_override, static_context=static_context,
        acceptance_criteria_ids=acceptance_criteria_ids,
        governing_spec_content_hash=governing_spec_content_hash,
    )
