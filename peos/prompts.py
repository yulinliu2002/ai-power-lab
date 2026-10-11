"""Prompt templates for the Claude and Codex subprocess invocations.

Kept in one small module so the actual instructions given to each agent
are easy to read and audit without digging through workflow.py's control
flow. Every prompt reminds the agent to read CLAUDE.md / ENGINEERING.md /
AGENTS.md itself rather than PEOS restating project rules, per SPEC-001
Section 10 ("state should rely on repository artifacts rather than
conversational memory wherever practical").

Both agents operate inside a disposable local Git clone (peos/sandbox.py),
not the authoritative repository -- the prompts say so explicitly so
neither agent is confused by an unfamiliar absolute path or wonders where
the GitHub remote went.

SPEC-004 (PEOS Autonomous Engineering Loop): every one of the four prompt
builders below -- including cycle 0's `build_implementation_prompt`/
`build_review_prompt`, not only the remediation-cycle ones -- takes a
`peos.round_packet.RoundPacket` and renders its full contents into the
prompt text via `render_round_packet_header` (Requirement 17/AC-37).
SPEC-004 remediation Finding 4 (MAJOR): constructing a `RoundPacket`
dataclass is not the same as an agent actually receiving its contents --
each fresh Claude/Codex subprocess invocation is, by SPEC-003's own
design, a brand-new process with no memory of prior calls, so every
element (governing-spec identity, governance/decision identities, cycle/
budget, workspace snapshot identity, latest verification result, the
complete acceptance-criteria set, static-context identities, and -- for
the two remediation-cycle builders -- the Outstanding Findings Register
and any active disputes) must be restated as literal prompt text every
round, never merely held in an orchestrator-side dataclass the agent
never reads and never assumed carried over from "the previous cycle"
(there may have been several). Cycle 0's packet is always empty on the
register/dispute/historical-disposition fields (nothing has happened
yet) -- that emptiness is rendered explicitly by `render_round_packet_
header`/`render_register_for_prompt`, never omitted.
"""

from __future__ import annotations

from peos.round_packet import (
    RoundPacket,
    render_disputes_for_prompt,
    render_register_for_prompt,
    render_round_packet_header,
)

_GOVERNANCE_READING = (
    "Before doing anything else, read CLAUDE.md, ENGINEERING.md, AGENTS.md, "
    "and the governing specification below. Treat the specification as "
    "authoritative."
)

_WORKSPACE_NOTE = (
    "You are working in a disposable local clone of the repository, not "
    "the authoritative one -- this is expected; a human will review your "
    "changes against the authoritative working tree afterward. You have "
    "no shell/Bash tool and no network/MCP tools in this session; only "
    "Read, Edit, Write, Grep, and Glob are available, confined to this "
    "working directory. Do not attempt git commands, package installs, or "
    "any other shell-only operation -- there is no tool to run them with. "
    "PEOS runs all verification (tests, lint, typecheck, build) itself, "
    "independently, after you finish; do not try to run it yourself."
)

_RESULT_CONTRACT = (
    "Your final answer must set:\n"
    "- status: \"COMPLETED\" if you finished the requested work within the "
    "approved specification's scope; \"HUMAN_GATE\" if the task would "
    "require a human-owned engineering decision (physics, control, "
    "protection, or architecture change; a change to specification intent "
    "or an ambiguous/contradictory specification; or any merge/release/tag/"
    "git-history action) and you deliberately stopped short rather than "
    "attempting it; \"FAILED\" if you attempted the task but could not "
    "complete it for any other reason (e.g. you hit an error you could not "
    "resolve within scope).\n"
    "- gate_category: when status is HUMAN_GATE, exactly one of physics, "
    "control, protection, architecture, specification_intent, "
    "ambiguous_specification, git_release_action, other -- explaining "
    "*which* human-owned decision is blocking you; null otherwise.\n"
    "- gate_reason: when status is HUMAN_GATE, a concrete, specific "
    "explanation of the decision that is needed and why you cannot make "
    "it; null otherwise.\n"
    "- summary: always required. A concise account of what you changed "
    "(file by file) or attempted, any verification you ran yourself for "
    "your own iteration (not as proof -- PEOS re-runs verification "
    "independently), and any known limitations."
)

_DISPUTE_INSTRUCTION = (
    "If you have concrete evidence that one of the outstanding findings "
    "listed below is already satisfied, inapplicable, or factually wrong, "
    "you may decline to change code for it -- but only by including a line "
    "of the exact form `DISPUTE[<reference>]: <your evidence>` in your "
    "`summary` field, where `<reference>` is copied exactly from the "
    "finding's reference below (e.g. `DISPUTE[0.2]: ...`). Do not invent a "
    "reference and do not dispute a finding that is not listed as "
    "outstanding below. An unresolved dispute is reviewed by the "
    "independent reviewer next; it does not excuse you from addressing "
    "every other outstanding finding."
)


def build_implementation_prompt(task: str, spec_path: str, round_packet: RoundPacket) -> str:
    return (
        f"{_GOVERNANCE_READING}\n\n"
        f"{_WORKSPACE_NOTE}\n\n"
        f"Governing specification: {spec_path}\n\n"
        f"{render_round_packet_header(round_packet)}\n\n"
        f"Task from the Human Engineering Lead:\n{task}\n\n"
        "Implement only what the governing specification approves. Modify "
        "only the approved scope. Add or update tests for any non-trivial "
        "model or control logic you add or change. If the specification is "
        "incorrect, incomplete, or contradictory, or the task would require "
        "a human-owned engineering decision, do not guess -- stop and "
        "report it via the result contract below instead of proceeding.\n\n"
        f"{_RESULT_CONTRACT}"
    )


def build_review_prompt(task: str, spec_path: str, round_packet: RoundPacket) -> str:
    ac_note = (
        (
            "The governing specification declares these acceptance criteria: "
            f"{', '.join(round_packet.acceptance_criteria_ids)}. Your "
            "acceptance-criteria assessment must cover every one of them by "
            "id -- an assessment that silently omits one is treated as "
            "invalid, not a passing review.\n\n"
        )
        if round_packet.acceptance_criteria_ids else ""
    )
    return (
        f"{_GOVERNANCE_READING}\n\n"
        "You are working in a disposable local clone of the repository "
        "that the implementer used; this is expected. You have no network/"
        "MCP tools in this session and are running in a read-only sandbox "
        "-- any attempt to modify a file will be denied by the sandbox "
        "itself, not merely discouraged.\n\n"
        f"Governing specification: {spec_path}\n\n"
        f"{render_round_packet_header(round_packet)}\n\n"
        f"Task that was implemented:\n{task}\n\n"
        "You are the independent reviewer. Inspect the actual working tree "
        "(`git status`, `git diff`, and the changed files) and review the "
        "implementation against the governing specification. Do not modify "
        "any files.\n\n"
        f"{ac_note}"
        "Classify every finding into exactly one category: "
        "implementation_defect, specification_ambiguity, missing_test, "
        "missing_validation_evidence, architecture_concern, or "
        "non_blocking_improvement. Set requires_human_decision=true for any "
        "finding whose correct fix would change specification intent, "
        "architecture, physics, control, or protection behavior -- these are "
        "human-owned decisions, not something the implementer may remediate "
        "automatically. Produce an acceptance-criteria assessment (or null "
        "if the specification defines none) if it defines numbered "
        "acceptance criteria (AC-NNN). This is the initial review: no "
        "dispute is active and no historical finding exists yet, so set "
        "reviewer_overrules_dispute, addressed_dispute_references, and "
        "historical_finding_dispositions to null.\n\n"
        "Return verdict=APPROVE only if there are no blocking or major "
        "findings, no finding has requires_human_decision=true, and every "
        "acceptance criterion you assessed is met; otherwise "
        "CHANGES_REQUIRED. An APPROVE that contradicts your own findings or "
        "acceptance-criteria assessment will be rejected and treated as a "
        "failure, not an approval."
    )


def build_remediation_prompt(task: str, spec_path: str, round_packet: RoundPacket) -> str:
    register_text = render_register_for_prompt(round_packet)
    return (
        f"{_GOVERNANCE_READING}\n\n"
        f"{_WORKSPACE_NOTE}\n\n"
        f"Governing specification: {spec_path}\n\n"
        f"{render_round_packet_header(round_packet)}\n\n"
        f"Original task:\n{task}\n\n"
        f"This is remediation cycle {round_packet.cycle_number} of up to "
        f"{round_packet.max_cycles} ({round_packet.remaining_budget} cycle(s) "
        "remaining after this one). An independent reviewer (Codex) has "
        "raised the following outstanding findings across this run so far "
        "(a reference like \"0.2\" names the 2nd finding of the initial "
        "review; \"1.1\" names the 1st finding of remediation cycle 1's "
        "closure review). Remediate every one of them within the approved "
        "specification's scope. If a finding actually requires changing "
        "specification intent, architecture, physics, control, or "
        "protection behavior, do not attempt a fix; use the result "
        "contract below to say so instead.\n\n"
        f"Outstanding findings:\n{register_text}\n\n"
        f"{_DISPUTE_INSTRUCTION}\n\n"
        f"{_RESULT_CONTRACT}"
    )


def build_rereview_prompt(task: str, spec_path: str, round_packet: RoundPacket) -> str:
    register_text = render_register_for_prompt(round_packet)
    disputes_text = render_disputes_for_prompt(round_packet)
    ac_note = (
        (
            "The governing specification declares these acceptance criteria: "
            f"{', '.join(round_packet.acceptance_criteria_ids)}. Your "
            "acceptance-criteria assessment must cover every one of them by "
            "id -- an assessment that silently omits one is treated as "
            "invalid, not a passing review.\n\n"
        )
        if round_packet.acceptance_criteria_ids else ""
    )
    dispute_note = (
        (
            "The implementer disputed the following finding(s) with "
            "evidence this cycle. For each one, decide whether you concede "
            "it (the evidence holds) or still consider it a real, unresolved "
            "issue. Set `addressed_dispute_references` to the complete list "
            "of references below (every one, not only the ones you "
            "overrule), and set `reviewer_overrules_dispute=true` if you "
            "still find at least one of them a real issue after considering "
            "the evidence, or `false` if you concede all of them:\n"
            f"{disputes_text}\n\n"
        )
        if round_packet.active_disputes else
        "No dispute is active this cycle: set reviewer_overrules_dispute "
        "and addressed_dispute_references to null.\n\n"
    )
    return (
        f"{_GOVERNANCE_READING}\n\n"
        "You are working in a disposable local clone of the repository "
        "that the implementer used; this is expected. You have no network/"
        "MCP tools in this session and are running in a read-only sandbox "
        "-- any attempt to modify a file will be denied by the sandbox "
        "itself, not merely discouraged.\n\n"
        f"Governing specification: {spec_path}\n\n"
        f"{render_round_packet_header(round_packet)}\n\n"
        f"Task that was implemented:\n{task}\n\n"
        f"This is remediation cycle {round_packet.cycle_number} of up to "
        f"{round_packet.max_cycles}'s closure review "
        f"({round_packet.remaining_budget} cycle(s) remaining after this "
        "one, if you still return CHANGES_REQUIRED). Inspect the current "
        "working tree and check specifically whether every outstanding "
        "finding below is now resolved. Do not modify any files.\n\n"
        f"{ac_note}"
        f"Outstanding findings across this run so far:\n{register_text}\n\n"
        f"{dispute_note}"
        "For every outstanding finding above that you have now verified is "
        "resolved, no longer applicable, or -- while real -- no longer "
        "blocking/major severity, include an entry in "
        "`historical_finding_dispositions` naming its exact reference with "
        "disposition RESOLVED, ACCEPTED_RECLASSIFICATION, or (if it needs a "
        "human-owned decision you cannot make) HUMAN_DECISION_REQUIRED. "
        "Leaving a reference out means it remains outstanding -- that is "
        "the normal, expected case for most findings most cycles, not an "
        "error. Report any new blocking/major finding introduced by the "
        "remediation itself as a normal finding. Classify findings and set "
        "requires_human_decision exactly as in a normal review.\n\n"
        "Return verdict=APPROVE only if there are no remaining blocking or "
        "major findings anywhere in this run's outstanding findings (not "
        "only this cycle's own), no finding has requires_human_decision=true, "
        "no dispute above is left unconceded, and every acceptance "
        "criterion you assessed is met; otherwise CHANGES_REQUIRED. An "
        "APPROVE that contradicts your own findings, dispositions, or "
        "acceptance-criteria assessment will be rejected and treated as a "
        "failure, not an approval."
    )
