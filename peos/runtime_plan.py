"""Runtime Plan (SPEC-006 Section 8 step 1, Section 10 "Declaration
convention", Section 13 "Explicit Applicability and AC Mapping").

Planning deterministically parses the resolved governing specification's
own text for a conventionally-marked `### Runtime Verification`
subsection -- the same "an isolated run of indented lines under a
recognized heading is a literal, never-AI-interpreted declaration"
convention `peos/verification_plan.py` already uses for spec-declared
verification commands, and `peos/static_context.py` uses for Design
Context artifacts.

Each declaration line has the fixed shape:

    runtime: <kind> key=value key="quoted value" ac=AC-001 ac=AC-002

-- one line per declared check, a `kind` token from
`peos.runtime_catalog.CHECK_KINDS`, that kind's own typed parameters as
named key=value pairs, and at least one `ac=` value naming an
acceptance-criteria ID the check is evidence for. Runtime applicability
is therefore explicit and deterministic -- never inferred heuristically
by an LLM (SPEC-006 hardening item C).

A line naming a `kind` outside the fixed catalog, omitting a required
parameter for its kind, naming an `ac=` value the specification does not
itself declare, or a Runtime Plan declaring more than
`peos.runtime_catalog.MAX_CHECKS_PER_ROUND` checks, is never silently
dropped or silently ignored -- `RuntimePlan.gate_reason` is set, and
`peos/workflow.py` must route this to Human Gate #12 (SPEC-006 Section
15), before any workspace runtime service is ever started.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from peos.runtime_catalog import (
    CHECK_KINDS,
    MAX_CHECKS_PER_ROUND,
    PARAM_CLASSES,
    REQUIRED_FIELDS,
    VIEWPORT_PRESETS,
    CheckParams,
    ExperimentRunParams,
    PageLoadParams,
    ViewportOverflowParams,
)

_HEADING_RE = re.compile(r"^#{1,6}\s")
_RUNTIME_VERIFICATION_HEADING_RE = re.compile(
    r"^#{1,6}\s*[\d.]*\s*Runtime Verification\b", re.IGNORECASE
)
_DECLARATION_LINE_RE = re.compile(r"^\s*runtime:\s*(\S+)\s*(.*)$")
_KV_RE = re.compile(r'(\w+)=(?:"([^"]*)"|(\S+))')


def _is_indented_line(line: str) -> bool:
    return line.startswith("    ") or line.startswith("\t")


@dataclass(frozen=True)
class RawDeclaration:
    kind: str
    raw_kv: tuple[tuple[str, str], ...]  # order-preserving, duplicates allowed (ac=)
    raw_line: str


def _parse_kv_pairs(rest: str) -> tuple[tuple[str, str], ...]:
    pairs = []
    for match in _KV_RE.finditer(rest):
        key = match.group(1)
        value = match.group(2) if match.group(2) is not None else match.group(3)
        pairs.append((key, value))
    return tuple(pairs)


def parse_runtime_verification_declarations(spec_text: str) -> tuple[RawDeclaration, ...]:
    """Extract literal `runtime: ...` declaration lines from the governing
    specification's `### Runtime Verification` section(s). Deterministic
    text parsing only -- never AI-interpreted. Only a line that is part
    of an isolated run of indented lines (preceded by a blank line, the
    section heading, or another such line -- the same CommonMark-style
    code-block isolation `peos/verification_plan.py` already applies) is
    ever treated as a declaration; a wrapped continuation line of
    ordinary prose that merely happens to land at column >=4 is not.
    Order-preserving; declarations are NOT de-duplicated (two identical
    lines declare two checks, which the MAX_CHECKS_PER_ROUND bound still
    counts against).
    """
    declarations: list[RawDeclaration] = []
    in_section = False
    prev_blank = True
    in_code_block = False
    for line in spec_text.splitlines():
        if _HEADING_RE.match(line):
            in_section = bool(_RUNTIME_VERIFICATION_HEADING_RE.match(line))
            prev_blank = True
            in_code_block = False
            continue
        if not in_section:
            continue
        if not line.strip():
            prev_blank = True
            in_code_block = False
            continue
        if _is_indented_line(line) and (prev_blank or in_code_block):
            stripped = line.strip()
            match = _DECLARATION_LINE_RE.match(stripped)
            if match is not None:
                kind, rest = match.group(1), match.group(2)
                declarations.append(
                    RawDeclaration(kind=kind, raw_kv=_parse_kv_pairs(rest), raw_line=stripped)
                )
            in_code_block = True
        else:
            in_code_block = False
        prev_blank = False
    return tuple(declarations)


@dataclass(frozen=True)
class RuntimeCheckDeclaration:
    declaration_index: int
    kind: str
    params: CheckParams
    related_ac_ids: tuple[str, ...]


@dataclass(frozen=True)
class RuntimePlan:
    declarations: tuple[RuntimeCheckDeclaration, ...] = field(default_factory=tuple)
    # Non-None -> Human Gate #12 (SPEC-006 Section 15). Never a FAILED --
    # a decision-bearing specification defect is a human-owned scope
    # question, not a containment/safety violation.
    gate_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.gate_reason is None


def _build_params(kind: str, raw_kv: tuple[tuple[str, str], ...], raw_line: str) -> tuple[CheckParams | None, str | None]:
    """Returns `(params, None)` on success or `(None, reason)` on a
    decision-bearing declaration defect (Human Gate #12)."""
    raw: dict[str, str] = {}
    for key, value in raw_kv:
        if key == "ac":
            continue
        if key in raw:
            return None, f"parameter {key!r} declared more than once in: {raw_line!r}"
        raw[key] = value

    missing = [f for f in REQUIRED_FIELDS[kind] if f not in raw]
    if missing:
        return None, f"declaration missing required parameter(s) {missing} for kind {kind!r}: {raw_line!r}"

    if kind == "page_load":
        landmarks = tuple(s.strip() for s in raw.get("landmarks", "").split(",") if s.strip())
        return PageLoadParams(path=raw.get("path", "/"), landmarks=landmarks), None

    if kind == "experiment_run":
        try:
            final_fraction = float(raw["final_fraction"])
        except ValueError:
            return None, f"final_fraction is not a valid number in: {raw_line!r}"
        kwargs = {"final_fraction": final_fraction, "selector": raw["selector"]}
        # control_selector/submit_selector are optional overrides -- a
        # real frontend with no stable `data-testid` hooks (live-run
        # finding against this repository's own `ExperimentPanel.tsx`)
        # must declare its own, since the catalog's generic-HTML-form
        # defaults will not match it.
        if "control_selector" in raw:
            kwargs["control_selector"] = raw["control_selector"]
        if "submit_selector" in raw:
            kwargs["submit_selector"] = raw["submit_selector"]
        if "expand_selector" in raw:
            kwargs["expand_selector"] = raw["expand_selector"]
        return ExperimentRunParams(**kwargs), None

    if kind == "viewport_overflow":
        viewport = raw.get("viewport")
        width = raw.get("width")
        height = raw.get("height")
        if viewport is not None and (width is not None or height is not None):
            return None, (
                f"viewport_overflow may declare 'viewport' OR 'width'+'height', not both: {raw_line!r}"
            )
        if viewport is not None:
            if viewport not in VIEWPORT_PRESETS:
                return None, (
                    f"unrecognized viewport preset {viewport!r} (known: "
                    f"{sorted(VIEWPORT_PRESETS)}) in: {raw_line!r}"
                )
            return ViewportOverflowParams(viewport=viewport), None
        if width is not None and height is not None:
            try:
                return ViewportOverflowParams(width=int(width), height=int(height)), None
            except ValueError:
                return None, f"width/height are not valid integers in: {raw_line!r}"
        return None, (
            f"viewport_overflow requires either 'viewport' or both 'width' and 'height': {raw_line!r}"
        )

    return None, f"unhandled kind {kind!r} (internal)"  # pragma: no cover -- kind already validated by caller


def build_runtime_plan(spec_text: str, acceptance_criteria_ids: tuple[str, ...]) -> RuntimePlan:
    """Resolve the Runtime Plan for the governing specification's current
    text (SPEC-006 Section 8 step 1). `acceptance_criteria_ids` is the
    specification's own complete, numbered AC set
    (`peos.plan.parse_acceptance_criteria_ids`) -- every declared `ac=`
    value must be one of these.
    """
    raw_declarations = parse_runtime_verification_declarations(spec_text)
    if not raw_declarations:
        return RuntimePlan()

    if len(raw_declarations) > MAX_CHECKS_PER_ROUND:
        return RuntimePlan(
            gate_reason=(
                f"governing specification declares {len(raw_declarations)} Runtime "
                f"Verification checks, exceeding the fixed per-round bound of "
                f"{MAX_CHECKS_PER_ROUND} (SPEC-006 Section 9/12)."
            )
        )

    declared_ac_set = frozenset(acceptance_criteria_ids)
    declarations: list[RuntimeCheckDeclaration] = []
    for index, raw in enumerate(raw_declarations):
        if raw.kind not in CHECK_KINDS:
            return RuntimePlan(
                gate_reason=(
                    f"declared runtime-check kind {raw.kind!r} is outside the fixed V1 "
                    f"catalog ({sorted(CHECK_KINDS)}) in: {raw.raw_line!r}"
                )
            )

        ac_ids = tuple(v for k, v in raw.raw_kv if k == "ac")
        if not ac_ids:
            return RuntimePlan(
                gate_reason=f"declaration names no 'ac=' acceptance-criteria reference: {raw.raw_line!r}"
            )
        orphaned = [ac for ac in ac_ids if ac not in declared_ac_set]
        if orphaned:
            return RuntimePlan(
                gate_reason=(
                    f"declaration names ac= value(s) {orphaned} not in the specification's own "
                    f"numbered acceptance-criteria set {sorted(declared_ac_set)}: {raw.raw_line!r}"
                )
            )

        params, reason = _build_params(raw.kind, raw.raw_kv, raw.raw_line)
        if reason is not None:
            return RuntimePlan(gate_reason=reason)

        declarations.append(
            RuntimeCheckDeclaration(
                declaration_index=index, kind=raw.kind, params=params, related_ac_ids=ac_ids,
            )
        )

    return RuntimePlan(declarations=tuple(declarations))


def runtime_evidenced_ac_ids(plan: RuntimePlan) -> frozenset[str]:
    """Every AC ID at least one declared check names (SPEC-006 Section
    13) -- the domain of `runtime_evidenced_ac_status`."""
    ids: set[str] = set()
    for decl in plan.declarations:
        ids.update(decl.related_ac_ids)
    return frozenset(ids)
