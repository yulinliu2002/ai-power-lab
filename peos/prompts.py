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
"""

from __future__ import annotations

from peos.codex_agent import Finding

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


def build_implementation_prompt(task: str, spec_path: str) -> str:
    return (
        f"{_GOVERNANCE_READING}\n\n"
        f"{_WORKSPACE_NOTE}\n\n"
        f"Governing specification: {spec_path}\n\n"
        f"Task from the Human Engineering Lead:\n{task}\n\n"
        "Implement only what the governing specification approves. Modify "
        "only the approved scope. Add or update tests for any non-trivial "
        "model or control logic you add or change. If the specification is "
        "incorrect, incomplete, or contradictory, or the task would require "
        "a human-owned engineering decision, do not guess -- stop and "
        "report it via the result contract below instead of proceeding.\n\n"
        f"{_RESULT_CONTRACT}"
    )


def build_review_prompt(task: str, spec_path: str) -> str:
    return (
        f"{_GOVERNANCE_READING}\n\n"
        "You are working in a disposable local clone of the repository "
        "that the implementer used; this is expected. You have no network/"
        "MCP tools in this session and are running in a read-only sandbox "
        "-- any attempt to modify a file will be denied by the sandbox "
        "itself, not merely discouraged.\n\n"
        f"Governing specification: {spec_path}\n\n"
        f"Task that was implemented:\n{task}\n\n"
        "You are the independent reviewer. Inspect the actual working tree "
        "(`git status`, `git diff`, and the changed files) and review the "
        "implementation against the governing specification. Do not modify "
        "any files.\n\n"
        "Classify every finding into exactly one category: "
        "implementation_defect, specification_ambiguity, missing_test, "
        "missing_validation_evidence, architecture_concern, or "
        "non_blocking_improvement. Set requires_human_decision=true for any "
        "finding whose correct fix would change specification intent, "
        "architecture, physics, control, or protection behavior -- these are "
        "human-owned decisions, not something the implementer may remediate "
        "automatically. Produce an acceptance-criteria assessment (or null "
        "if the specification defines none) if it defines numbered "
        "acceptance criteria (AC-NNN).\n\n"
        "Return verdict=APPROVE only if there are no blocking or major "
        "findings, no finding has requires_human_decision=true, and every "
        "acceptance criterion you assessed is met; otherwise "
        "CHANGES_REQUIRED. An APPROVE that contradicts your own findings or "
        "acceptance-criteria assessment will be rejected and treated as a "
        "failure, not an approval."
    )


def build_remediation_prompt(task: str, spec_path: str, findings: tuple[Finding, ...]) -> str:
    findings_text = "\n".join(
        f"- [{f.severity}/{f.category}] {f.description}"
        for f in findings
    ) or "(no findings supplied)"
    return (
        f"{_GOVERNANCE_READING}\n\n"
        f"{_WORKSPACE_NOTE}\n\n"
        f"Governing specification: {spec_path}\n\n"
        f"Original task:\n{task}\n\n"
        "An independent reviewer (Codex) found the following issues with "
        "your implementation. Remediate only these findings, and only "
        "within the approved specification's scope. This is the one "
        "automatic remediation cycle PEOS permits -- if a finding below "
        "actually requires changing specification intent, architecture, "
        "physics, control, or protection behavior, do not attempt a fix; "
        "use the result contract below to say so instead.\n\n"
        f"Findings to address:\n{findings_text}\n\n"
        f"{_RESULT_CONTRACT}"
    )


def build_rereview_prompt(task: str, spec_path: str, prior_findings: tuple[Finding, ...]) -> str:
    findings_text = "\n".join(
        f"- [{f.severity}/{f.category}] {f.description}"
        for f in prior_findings
    ) or "(no prior findings)"
    return (
        f"{_GOVERNANCE_READING}\n\n"
        "You are working in a disposable local clone of the repository "
        "that the implementer used; this is expected. You have no network/"
        "MCP tools in this session and are running in a read-only sandbox "
        "-- any attempt to modify a file will be denied by the sandbox "
        "itself, not merely discouraged.\n\n"
        f"Governing specification: {spec_path}\n\n"
        f"Task that was implemented:\n{task}\n\n"
        "This is a focused re-review after one remediation cycle. Inspect "
        "the current working tree and check specifically whether the "
        "following previously reported findings are now resolved. Do not "
        "modify any files.\n\n"
        f"Findings from the previous review:\n{findings_text}\n\n"
        "Report each prior finding as resolved or still outstanding, plus "
        "any new blocking/major finding introduced by the remediation "
        "itself. Classify findings and set requires_human_decision exactly "
        "as in a normal review. This is the final automatic review cycle: "
        "if findings remain, PEOS will stop and escalate to the Human "
        "Engineering Lead rather than attempting another remediation cycle.\n\n"
        "Return verdict=APPROVE only if there are no remaining blocking or "
        "major findings, no finding has requires_human_decision=true, and "
        "every acceptance criterion you assessed is met; otherwise "
        "CHANGES_REQUIRED. An APPROVE that contradicts your own findings or "
        "acceptance-criteria assessment will be rejected and treated as a "
        "failure, not an approval."
    )
