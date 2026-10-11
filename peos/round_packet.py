"""Round Packet (SPEC-004 Requirement 17 -- NEW).

Each fresh Claude or Codex subprocess invocation is, by SPEC-003's own
design, a brand-new process with no memory of prior calls -- agent
conversation history is not, and has never been, an authoritative
context channel in PEOS. `build_round_packet` assembles the ten elements
Requirement 17 requires, fresh, from the orchestrator's own live state
(the Outstanding Findings Register, the active-dispute set, the resolved
specification/decisions, the current cycle's verification result, the
staged static-context artifacts) -- never from a prior subprocess's
captured stdout/transcript (SPEC-004 AC-37). `peos/workflow.py` builds one
of these immediately before every Claude/Codex call from remediation
cycle 1 onward (cycle 0 has no register/dispute history yet, so its
prompts remain the simpler SPEC-001 shape).

SPEC-004 remediation Finding 4 (closure review): the identity payload is
completed with two further elements -- governance file identities
(CLAUDE.md/AGENTS.md/ENGINEERING.md) and the authoritative baseline Git
commit SHA -- both sourced from the orchestrator's own frozen/verified
state (`peos.preflight.hash_governance_artifacts` /
`peos.preflight.check_repository_safety`'s `head_commit`), never
recomputed opportunistically from agent-controlled text at prompt-build
time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from peos.findings_register import FindingsRegister, RegisterEntry


@dataclass(frozen=True)
class RegisterEntrySnapshot:
    reference: str
    severity: str
    description: str
    outstanding: bool
    disposition: str | None
    disposition_note: str | None
    human_decision_required_ever: bool

    @classmethod
    def from_entry(cls, entry: RegisterEntry) -> "RegisterEntrySnapshot":
        return cls(
            reference=str(entry.ref), severity=entry.severity, description=entry.description,
            outstanding=entry.outstanding, disposition=entry.disposition,
            disposition_note=entry.disposition_note,
            human_decision_required_ever=entry.human_decision_required_ever,
        )


@dataclass(frozen=True)
class ActiveDispute:
    reference: str
    evidence: str
    raised_in_remediation_cycle: int


@dataclass(frozen=True)
class StaticContextRef:
    declared_path: str
    staged_relative_path: str | None
    content_hash: str


@dataclass(frozen=True)
class RoundPacket:
    # 1. Original human task/intent, unchanged since Planning.
    task: str
    # 2. Governing specification's repository path + content hash.
    spec_relative_path: str
    spec_content_hash: str
    # 3. Applicable decision/governance identities.
    decision_identities: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    # 4. Current cycle number and remaining budget.
    cycle_number: int = 0
    max_cycles: int = 0
    remaining_budget: int = 0
    # 5. Current isolated-workspace snapshot identity.
    workspace_snapshot_identity: str = ""
    # 6. Latest deterministic verification result/evidence.
    verification_passed: bool | None = None
    verification_summary: str = ""
    # 7. Complete Outstanding Findings Register, entering this round.
    register_snapshot: tuple[RegisterEntrySnapshot, ...] = field(default_factory=tuple)
    # 8. Every currently active dispute and its evidence.
    active_disputes: tuple[ActiveDispute, ...] = field(default_factory=tuple)
    # 9. Complete governing acceptance-criteria set.
    acceptance_criteria_ids: tuple[str, ...] = field(default_factory=tuple)
    # 10. Staged static-context artifacts.
    static_context_artifacts: tuple[StaticContextRef, ...] = field(default_factory=tuple)
    # 11. Governance artifact identities (SPEC-004 remediation Finding 4,
    # closure review): CLAUDE.md/AGENTS.md/ENGINEERING.md, each as
    # (repo-relative path, content hash), sourced from the orchestrator's
    # own frozen `peos.preflight.hash_governance_artifacts` baseline --
    # never recomputed from agent-controlled text at prompt-build time.
    governance_identities: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    # 12. Authoritative baseline Git commit SHA (SPEC-004 remediation
    # Finding 4, closure review), sourced from `peos.preflight.
    # check_repository_safety`'s own `head_commit` -- the same value the
    # Run Ledger persists as `authoritative_baseline`.
    baseline_commit: str = ""


def build_round_packet(
    *,
    task: str,
    spec_relative_path: str,
    spec_content_hash: str,
    decision_identities: tuple[tuple[str, str], ...],
    cycle_number: int,
    max_cycles: int,
    workspace_snapshot_identity: str,
    verification_passed: bool | None,
    verification_summary: str,
    register: FindingsRegister,
    active_disputes: tuple[ActiveDispute, ...],
    acceptance_criteria_ids: tuple[str, ...],
    static_context_artifacts: tuple[StaticContextRef, ...],
    governance_identities: tuple[tuple[str, str], ...],
    baseline_commit: str,
) -> RoundPacket:
    return RoundPacket(
        task=task,
        spec_relative_path=spec_relative_path,
        spec_content_hash=spec_content_hash,
        decision_identities=decision_identities,
        cycle_number=cycle_number,
        max_cycles=max_cycles,
        remaining_budget=max(max_cycles - cycle_number, 0),
        workspace_snapshot_identity=workspace_snapshot_identity,
        verification_passed=verification_passed,
        verification_summary=verification_summary,
        register_snapshot=tuple(RegisterEntrySnapshot.from_entry(e) for e in register.all_entries()),
        active_disputes=active_disputes,
        acceptance_criteria_ids=acceptance_criteria_ids,
        static_context_artifacts=static_context_artifacts,
        governance_identities=governance_identities,
        baseline_commit=baseline_commit,
    )


def render_register_for_prompt(packet: RoundPacket) -> str:
    outstanding = [e for e in packet.register_snapshot if e.outstanding]
    if not outstanding:
        return "(no outstanding historical findings)"
    return "\n".join(
        f"- [{e.reference}] [{e.severity}] {e.description}" for e in outstanding
    )


def render_disputes_for_prompt(packet: RoundPacket) -> str:
    if not packet.active_disputes:
        return "(no active disputes)"
    return "\n".join(
        f'- DISPUTE[{d.reference}] (raised in remediation cycle {d.raised_in_remediation_cycle}): {d.evidence}'
        for d in packet.active_disputes
    )


def render_historical_dispositions_for_prompt(packet: RoundPacket) -> str:
    """SPEC-004 remediation Finding 4 (MAJOR): the complete historical
    findings register includes entries a *prior* round already closed
    (RESOLVED/ACCEPTED_RECLASSIFICATION/HUMAN_DECISION_REQUIRED), not
    only the ones still OUTSTANDING -- `render_register_for_prompt`
    above deliberately renders outstanding-only (that is the actionable
    worklist), so this is the separate rendering of closed history every
    Round Packet must also carry (SPEC-004's "complete historical
    findings register and dispositions" element).
    """
    disposed = [e for e in packet.register_snapshot if not e.outstanding]
    if not disposed:
        return "(no historical finding has been dispositioned yet)"
    lines = []
    for e in disposed:
        note = f" -- {e.disposition_note}" if e.disposition_note else ""
        lines.append(f"- [{e.reference}] [{e.severity}] {e.disposition}{note}: {e.description}")
    return "\n".join(lines)


def render_round_packet_header(packet: RoundPacket) -> str:
    """Render every element of `packet` that the register/dispute
    renderers above do not already cover, as literal text any Claude or
    Codex prompt can include (SPEC-004 remediation Finding 4, MAJOR):
    constructing a `RoundPacket` dataclass is not the same as an agent
    actually receiving its contents -- every element must appear in the
    rendered prompt text itself. Used by every prompt builder in
    `peos/prompts.py`, for the initial cycle-0 calls exactly like every
    later remediation/closure-review call -- there is no "cycle 0 is
    simpler" exception to Round Packet delivery, even though cycle 0's
    register/active-dispute/historical-disposition content is always
    empty by construction (explicitly rendered as such below, not
    omitted).
    """
    decisions = ", ".join(f"{path} ({content_hash})" for path, content_hash in packet.decision_identities) or "(none)"
    static_context = ", ".join(
        f"{a.declared_path} ({a.content_hash})" for a in packet.static_context_artifacts
    ) or "(none declared)"
    ac_ids = ", ".join(packet.acceptance_criteria_ids) or "(none declared)"
    governance = ", ".join(
        f"{path} ({content_hash})" for path, content_hash in packet.governance_identities
    ) or "(none)"
    if packet.verification_passed is None:
        verification_line = "(no deterministic verification result yet)"
    else:
        outcome = "PASSED" if packet.verification_passed else "FAILED"
        verification_line = f"{outcome} -- {packet.verification_summary}" if packet.verification_summary else outcome
    return (
        "Orchestrator-authoritative round context (this is ground truth for this round; "
        "do not rely on any prior conversation memory, which does not exist across "
        "separate PEOS subprocess invocations):\n"
        f"- Governing specification: {packet.spec_relative_path} (content hash {packet.spec_content_hash})\n"
        f"- Governance file identities (CLAUDE.md/AGENTS.md/ENGINEERING.md): {governance}\n"
        f"- Authoritative baseline Git commit: {packet.baseline_commit or '(none)'}\n"
        f"- Governance/decision record identities: {decisions}\n"
        f"- Cycle: {packet.cycle_number} of {packet.max_cycles} ({packet.remaining_budget} remediation cycle(s) "
        "remaining after this one)\n"
        f"- Isolated workspace snapshot identity: {packet.workspace_snapshot_identity}\n"
        f"- Latest deterministic verification result: {verification_line}\n"
        f"- Complete governing acceptance-criteria set: {ac_ids}\n"
        f"- Static external-context artifact identities: {static_context}\n"
        f"- Historical finding dispositions so far: {render_historical_dispositions_for_prompt(packet)}"
    )
