"""Final PEOS report (SPEC-001 Phase 6, AC-012, remediated per Finding 10).

Every run ends with one human-readable report, regardless of whether it
ended in APPROVED, HUMAN_GATE, or FAILED -- SPEC-001 Section 11 requires
failures to be made visible, not just successes. The report always
preserves the resolved governing specification (when one was resolved),
the frozen verification plan, untracked as well as tracked changed
files, the isolated workspace's reconciliation outcome, and any
run-specific limitations -- a failed or human-gated run must be just as
inspectable as an approved one.
"""

from __future__ import annotations

from pathlib import Path

from peos.gitutil import (
    git_current_branch,
    git_diff_name_status,
    git_status_porcelain,
    git_untracked_files,
)
from peos.verification_plan import VerificationPlan
from peos.verify import VerificationReport
from peos.workflow import RunResult

KNOWN_LIMITATIONS = (
    "Governing-specification auto-detection (when --spec is omitted) is a "
    "simple keyword-overlap heuristic over approved specification titles, "
    "not natural-language understanding; pass --spec explicitly for "
    "reliable behavior.",
    "Claude and Codex operate in a disposable local Git clone (the "
    "isolated workspace), never the authoritative repository directly. "
    "Claude runs with `--restricted` and no Bash/shell tool -- verified "
    "against the installed CLI to confine Read/Edit/Write to that "
    "workspace directory and expose no code-execution tool at all -- and "
    "the workspace's Git remotes and push-capable credentials "
    "(SSH agent socket, GitHub tokens, credential helpers) are removed/"
    "stripped before either agent runs. This is not a full OS container: "
    "no filesystem jail or network isolation is applied to Claude/Codex "
    "themselves, so that part of the trust boundary rests on (a) Claude "
    "having no tool capable of reaching outside the workspace directory "
    "and no shell at all, and (b) no push-capable credential being "
    "reachable even if a command somehow ran. Codex additionally runs "
    "under its own `--sandbox read-only` (verified to reject one file "
    "write attempt with a real OS permission error, not a claim about "
    "every property of that mode, e.g. its network policy) plus "
    "`--ignore-user-config`/`--ignore-rules` to skip loading configured "
    "MCP servers and execpolicy rules where the CLI supports it; the "
    "structural backstop that does not depend on characterizing every "
    "property of either agent's sandbox is the before/after content-based "
    "fingerprint of both the authoritative repository and the isolated "
    "workspace around every Codex phase (peos/gitutil.py).",
    "Deterministic verification (pytest / npm run lint|typecheck|build) "
    "executes whatever code is in the workspace at that point, which is "
    "not trusted -- it runs under an OS-enforced macOS Seatbelt "
    "(`sandbox-exec`) profile, verified empirically against this "
    "repository's real test/lint/typecheck/build commands, that denies "
    "all network, denies writing anywhere except the workspace/temp "
    "directories, and denies reading the authoritative repository's "
    "`.git` directory plus a named list of real-$HOME credential paths "
    "(SSH keys, .netrc, gh/aws/docker config). This is macOS-only: on any "
    "other platform, or if `sandbox-exec` is ever removed, PEOS refuses "
    "to run verification unconfined rather than silently weakening the "
    "boundary. It is not a full filesystem jail -- reads of the rest of "
    "the real filesystem outside the denied paths are not blocked, so a "
    "malicious verification script could still read and print an "
    "arbitrary file to stdout (a disclosure risk visible in this report, "
    "not a covert one); what it cannot do is mutate the authoritative "
    "repository, push, or reach the network at all.",
    "Frontend dependencies (`frontend/node_modules`) are copied into the "
    "isolated workspace once, from the authoritative checkout, at "
    "workspace-creation time, because the verification sandbox denies "
    "network (so `npm install` cannot run inside it). Python verification "
    "reuses the orchestrator's own installed interpreter/site-packages by "
    "path instead of duplicating a virtualenv into the workspace. Either "
    "way, dependencies are taken as of run start and never re-installed "
    "or updated by PEOS; if `frontend/node_modules` is missing from the "
    "authoritative checkout, frontend verification fails closed with an "
    "explicit message.",
    "Human-owned-decision detection relies on two independent self-reports "
    "-- Claude's own structured `status=HUMAN_GATE` result and Codex's "
    "`requires_human_decision` per finding -- neither of which PEOS can "
    "independently verify is engineering-correct, only that each is "
    "well-formed and internally consistent (e.g. an APPROVE verdict that "
    "contradicts its own blocking findings, or that has no "
    "acceptance-criteria evidence at all, is rejected as uninterpretable, "
    "not silently accepted).",
    "Governance-artifact mutation detection (CLAUDE.md/AGENTS.md/"
    "ENGINEERING.md and the governing specification, wherever it was "
    "supplied from) is a before/after content hash comparison; it detects "
    "any change to those files' content, not merely semantic rewrites, "
    "and is re-checked after every Claude phase and after every local "
    "verification run, not only once.",
    "The authoritative repository's and the isolated workspace's Git "
    "state are each compared by content-based fingerprint before and "
    "after every Codex review phase to confirm the reviewer made no "
    "change visible to Git, including a further edit to a file that was "
    "already dirty/untracked beforehand; this does not inspect files "
    "ignored by .gitignore.",
    "Commit, PR creation, CI polling, and merge are explicitly out of "
    "scope for V1 (SPEC-001 Section 12/13) and are not performed by this "
    "tool.",
)

_NEXT_ACTION = {
    "APPROVED": (
        "Review the diff and the recorded verification/review results "
        "below, then decide whether to commit and open a PR yourself -- "
        "PEOS does not do this automatically."
    ),
    "HUMAN_GATE": (
        "This run stopped for a human-owned engineering decision. Resolve "
        "the gate reason below (e.g. approve/write a specification, or "
        "make the architecture/physics/control decision), then re-run PEOS "
        "if appropriate."
    ),
    "FAILED": (
        "This run stopped on an unexpected command failure or "
        "uninterpretable agent output. Inspect the failure detail and the "
        "repository state below before re-running."
    ),
}


def _format_verification(reports: tuple[VerificationReport, ...]) -> str:
    if not reports:
        return "(not reached)"
    lines = []
    for i, report in enumerate(reports, start=1):
        label = "Post-implementation" if i == 1 else f"Round {i}"
        lines.append(f"{label}: {'PASS' if report.passed else 'FAIL'}")
        for result in report.results:
            status = "ok" if result.passed else "FAIL"
            lines.append(f"  - {result.name}: {status} (exit {result.returncode})")
            if not result.passed:
                tail = (result.stderr or result.stdout or result.error or "").strip()
                if tail:
                    lines.append(f"    {tail.splitlines()[-1][:300]}")
    return "\n".join(lines)


def _format_verification_plan(plan: VerificationPlan | None) -> str:
    if plan is None or (not plan.steps and not plan.manual_items):
        return "(not resolved)"
    lines = [
        f"- {step.name} (cwd: {step.cwd_relative}, requires: {step.required_input})"
        for step in plan.steps
    ]
    if plan.manual_items:
        lines.append(
            "Manual / observational verification (from the governing specification's "
            "Verification section; not executed by PEOS -- requires human or "
            "implementer evidence, per ENGINEERING.md's governance model):"
        )
        lines.extend(f"  - {item}" for item in plan.manual_items)
    return "\n".join(lines)


def _format_reviews(reviews) -> str:
    if not reviews:
        return "(not reached)"
    lines = []
    for i, review in enumerate(reviews, start=1):
        label = "Initial review" if i == 1 else "Re-review"
        lines.append(f"{label}: {review.verdict or 'UNINTERPRETABLE'}")
        for finding in review.findings:
            flag = " [HUMAN DECISION]" if finding.requires_human_decision else ""
            lines.append(f"  - [{finding.severity}/{finding.category}]{flag} {finding.description}")
        for ac in review.acceptance_criteria:
            # Focused closure review, Finding 3 (remaining disclosure path):
            # render the sanitized `display_id`, never the internal `id`,
            # which Codex controls and which may contain a credential-shaped
            # value -- `peos/codex_agent.py::_validate_acceptance_criteria`
            # is the only producer of this dict and always sets both keys.
            lines.append(f"  - {ac.get('display_id', '?')}: {'met' if ac.get('met') else 'NOT MET'} {ac.get('note', '')}")
    return "\n".join(lines)


def _format_claude_runs(runs) -> str:
    if not runs:
        return "(not reached)"
    lines = []
    for i, run in enumerate(runs, start=1):
        label = "Implementation" if i == 1 else f"Remediation cycle {i - 1}"
        lines.append(f"{label}: status={run.status or 'UNINTERPRETABLE'}")
        if run.summary:
            lines.append(f"  {run.summary}")
    return "\n".join(lines)


def _format_context_recovery(context_recovery) -> str:
    """SPEC-004 Requirement 10/AC-5: Context Recovery's output is shown
    even on a run that never reaches implementation -- this section's
    content comes only from `result.context_recovery`, never from
    whether Planning/implementation succeeded.
    """
    if context_recovery is None:
        return "(not run)"
    lines = []
    for label, items in (
        ("Related approved specifications", context_recovery.related_specs),
        ("Related decision records", context_recovery.related_decisions),
        ("Related validation records", context_recovery.related_validation_records),
    ):
        lines.append(f"{label}: {', '.join(items) if items else '(none found)'}")
    return "\n".join(lines)


def _format_iteration_history(result: RunResult) -> str:
    """SPEC-004 Requirement 10: one cycle-indexed table -- cycle 0 is the
    initial implementation + review; remediation cycle N is the Nth
    remediation + closure review -- including any dispute activity for
    that cycle, read from `result.dispute_log`.
    """
    if not result.claude_runs:
        return "(not reached)"
    lines = []
    for i, claude_run in enumerate(result.claude_runs):
        cycle_label = "Cycle 0 (initial implementation)" if i == 0 else f"Remediation cycle {i}"
        lines.append(f"{cycle_label}:")
        lines.append(f"  Claude: status={claude_run.status or 'UNINTERPRETABLE'}")
        review = result.review_results[i] if i < len(result.review_results) else None
        if review is not None:
            review_label = "Codex initial review" if i == 0 else "Codex closure review"
            lines.append(f"  {review_label}: {review.verdict or 'UNINTERPRETABLE'}")
        cycle_disputes = [
            entry for entry in result.dispute_log
            if f"remediation cycle {i}" in entry and i > 0
        ]
        for entry in cycle_disputes:
            lines.append(f"  {entry}")
    return "\n".join(lines)


def _format_findings_register(register) -> str:
    """SPEC-004 Requirement 10/16: every finding the run's Outstanding
    Findings Register ever held, its PEOS-assigned reference, and its
    final disposition -- with no exceptions (omission from this section
    is itself a reporting defect, not a valid way to say "nothing more
    to report").
    """
    if register is None:
        return "(no reviews completed -- register empty)"
    entries = register.all_entries()
    if not entries:
        return "(no blocking/major findings were ever raised in this run)"
    lines = []
    for entry in entries:
        if entry.outstanding:
            status = "OUTSTANDING"
        else:
            status = entry.disposition or "CLOSED"
        lines.append(f"- [{entry.ref}] [{entry.severity}] {status}: {entry.description}")
        if entry.disposition_note:
            lines.append(f"    note: {entry.disposition_note}")
    return "\n".join(lines)


def _format_unresolved_minor_findings(result: RunResult) -> str:
    """SPEC-004 Requirement 10: an explicit section whenever the run
    reaches APPROVED/HUMAN_GATE with any minor/info finding still
    outstanding in the last review reached, so a non-blocking finding is
    never silently dropped just because it wasn't blocking enough to
    stop the run.
    """
    if result.outcome not in ("APPROVED", "HUMAN_GATE") or not result.review_results:
        return "(none)"
    last_review = result.review_results[-1]
    minors = [f for f in last_review.findings if f.severity in ("minor", "info")]
    if not minors:
        return "(none)"
    return "\n".join(f"- [{f.severity}/{f.category}] {f.description}" for f in minors)


def _format_runtime_verification_history(result: RunResult) -> str:
    """SPEC-006 Section 18 extension point 4: one entry per round whose
    Runtime Verification actually ran (the documented no-op is never
    listed here), showing that round's execution-integrity outcome and
    every declared check's own status -- never only the latest round's.
    """
    history = getattr(result, "runtime_verification_history", ())
    ran_rounds = [o for o in history if o.ran]
    if not ran_rounds:
        return "(no runtime checks declared, or Runtime Verification did not run)"
    lines = []
    for outcome in ran_rounds:
        integrity = "PASSED" if outcome.execution_integrity_passed else "FAILED"
        lines.append(f"Execution integrity: {integrity}")
        if outcome.failure_reason:
            lines.append(f"  reason: {outcome.failure_reason}")
        if outcome.evidence is not None:
            lines.append(f"  cycle: {outcome.evidence.cycle_label}")
            if outcome.persisted is not None:
                lines.append(f"  evidence: {outcome.persisted.evidence_dir} (sha256 {outcome.persisted.evidence_json_sha256})")
            for check in outcome.evidence.checks:
                ac_ids = ", ".join(check.related_ac_ids) or "(none)"
                lines.append(f"  - [{check.check_id}] kind={check.kind} status={check.status} ac={ac_ids}")
    return "\n".join(lines)


def _task_specific_limitations(result: RunResult) -> list[str]:
    items: list[str] = []
    if result.blocked_governance_mutation:
        items.append(
            "This run attempted to modify governance artifact(s) that were "
            f"rejected and NOT applied to the repository: {', '.join(result.blocked_governance_mutation)}."
        )
    for report in result.verification_reports:
        for failure in report.failures:
            if not failure.ran and failure.error:
                items.append(f"Verification step '{failure.name}' could not run: {failure.error}")
    if result.workspace_path:
        items.append(
            f"The isolated workspace used for this run was left in place for "
            f"inspection at: {result.workspace_path} (not automatically deleted)."
        )
    return items


def build_report(result: RunResult, repo_root: Path) -> str:
    spec_label = str(result.spec.path) if result.spec is not None else "(not resolved)"
    status = git_status_porcelain(repo_root)
    diff = git_diff_name_status(repo_root)
    untracked = git_untracked_files(repo_root)
    branch = git_current_branch(repo_root)

    changed_files_text = "\n".join(p for p in (diff, untracked) if p) or "(none)"

    lines = [
        "# PEOS Run Report",
        "",
        f"**Task:** {result.task}",
        f"**Governing specification:** {spec_label}",
        f"**Outcome:** {result.outcome}",
        f"**Max remediation cycles (effective):** {result.max_cycles}",
        f"**Remediation cycles run:** {result.remediation_cycles_run}",
        "",
        "## Phases executed",
        "\n".join(f"- {p.phase}" + (f": {p.detail}" if p.detail else "") for p in result.phases),
        "",
        "## Context recovered",
        _format_context_recovery(result.context_recovery),
        "",
        "## Iteration history",
        _format_iteration_history(result),
        "",
        "## Findings and resolutions (Outstanding Findings Register)",
        _format_findings_register(result.register),
        "",
        "## Unresolved MINOR findings",
        _format_unresolved_minor_findings(result),
        "",
        "## Frozen verification plan",
        _format_verification_plan(result.verification_plan),
        "",
        "## Local verification",
        _format_verification(result.verification_reports),
        "",
        "## Runtime evidence",
        _format_runtime_verification_history(result),
        "",
        "## Claude implementation/remediation",
        _format_claude_runs(result.claude_runs),
        "",
        "## Independent review (Codex)",
        _format_reviews(result.review_results),
        "",
        f"## Remediation performed: {result.remediation_performed}",
        "",
    ]

    if result.gate_reason:
        header = "## Human gate" if result.outcome == "HUMAN_GATE" else "## Failure detail"
        gate_id_line = f" (Gate #{result.gate_id})" if result.gate_id else ""
        lines += [f"{header}{gate_id_line}", result.gate_reason, ""]

    if result.reconciliation is not None:
        lines += [
            "## Isolated workspace reconciliation",
            f"Copied back to {repo_root} for review: {len(result.reconciliation.copied)} file(s)",
            "\n".join(f"  - {p}" for p in result.reconciliation.copied) or "  (none)",
            f"Deleted in {repo_root} to mirror the workspace: {len(result.reconciliation.deleted)} file(s)",
            "\n".join(f"  - {p}" for p in result.reconciliation.deleted) or "  (none)",
            "",
        ]
    if result.reconciliation_error:
        lines += [
            "## Isolated workspace reconciliation FAILED",
            (
                "Reconciling the isolated workspace back onto the authoritative working "
                "tree did not complete; the working tree below may not reflect everything "
                "that happened inside the workspace. This is why the outcome above is not "
                "APPROVED even if Codex approved the implementation (SPEC-001 remediation "
                "Finding 8)."
            ),
            result.reconciliation_error,
            "",
        ]

    task_limitations = _task_specific_limitations(result)
    lines += [
        "## Task-specific limitations",
        "\n".join(f"- {item}" for item in task_limitations) if task_limitations else "(none beyond the general limitations below)",
        "",
        "## Known limitations",
        "\n".join(f"- {item}" for item in KNOWN_LIMITATIONS),
        "",
        "## Git working-tree status",
        f"Branch: {branch}",
        "```",
        status or "(clean)",
        "```",
        "",
        "## Changed files (tracked + untracked)",
        "```",
        changed_files_text,
        "```",
        "",
        "## Recommended next human action",
        _NEXT_ACTION[result.outcome],
        "",
    ]

    return "\n".join(lines)
