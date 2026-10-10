# SPEC-001 — PEOS Automation V1

Status: Draft  
Owner: Human Engineering Lead  
Project: AI Power Lab / Personal Engineering Operating System

## 1. Purpose

PEOS Automation V1 reduces the manual coordination required between the Human Engineering Lead, Claude Code, Codex, local verification, Git, and GitHub.

The target user experience is a single entry point such as:

    peos "Implement Scenario A comparative experiment"

PEOS should coordinate the already-established engineering workflow automatically while preserving human authority over important engineering decisions.

Automation must not replace engineering judgment.

---

## 2. Problem

PEOS Bootstrap established the workflow:

Engineering Question
→ Specification
→ Implementation
→ Local Verification
→ Independent Review
→ Remediation
→ Re-review
→ PR
→ CI
→ Human Approval
→ Merge

The workflow works, but currently requires the user to manually:

- launch Claude
- provide implementation instructions
- wait for completion
- exit Claude
- launch Codex
- provide review instructions
- interpret findings
- return to Claude
- provide remediation instructions
- return to Codex for re-review
- inspect Git state
- coordinate the next step

This creates unnecessary coordination overhead.

Automation V1 should remove repetitive coordination without removing human engineering authority.

---

## 3. V1 Goal

Provide one local PEOS entry point that can orchestrate:

Human request
→ Claude implementation
→ local verification
→ Codex independent review
→ Claude remediation when required
→ Codex focused re-review
→ final PEOS report
→ Human Engineering Lead

The workflow stops before merge or release.

---

## 4. Core Principle

PEOS is an orchestrator, not an autonomous engineering authority.

Agents may:

- implement approved specifications
- inspect repository state
- run approved verification
- review implementation
- remediate review findings within approved scope
- generate reports

Agents may not independently approve changes to:

- simulation physics
- control architecture
- protection logic
- system architecture
- engineering assumptions
- specification intent
- release scope

Those decisions require the Human Engineering Lead.

---

## 5. V1 User Interface

Primary target:

    peos "<engineering task>"

Example:

    peos "Implement Scenario A comparative experiment"

The exact implementation mechanism may be a shell command, Python CLI, or equivalent local wrapper.

The interface should remain simple even if internal orchestration becomes more sophisticated later.

---

## 6. Workflow

### Phase 1 — Intake

PEOS receives the user's task.

PEOS identifies the governing approved specification.

If no approved specification exists for a significant engineering change, PEOS must stop and request specification work rather than allowing an implementation agent to invent requirements.

### Phase 2 — Implementation

PEOS invokes Claude Code as the implementation agent.

Claude must:

- read repository instructions
- read the governing specification
- inspect relevant existing implementation
- modify only the approved scope
- run required local verification
- report changes, results, and limitations

### Phase 3 — Independent Review

PEOS invokes Codex as an independent reviewer.

Codex must:

- inspect the actual working tree
- read the governing specification
- review implementation independently
- not modify files
- classify findings by severity
- produce an acceptance-criteria assessment where applicable
- return APPROVE or CHANGES REQUIRED

### Phase 4 — Remediation

If Codex returns CHANGES REQUIRED:

PEOS sends the concrete review findings back to Claude.

Claude may remediate only those findings within the approved specification.

If remediation requires changing specification intent, architecture, physics, controls, protection behavior, or another human-owned engineering decision, PEOS must stop and escalate to the Human Engineering Lead.

### Phase 5 — Re-review

Codex performs a focused review of the remediation.

The workflow must not silently loop indefinitely.

Automation V1 permits at most one automatic remediation cycle.

If Codex still returns CHANGES REQUIRED after that cycle, PEOS stops and reports the unresolved findings to the Human Engineering Lead.

### Phase 6 — Final Report

If Codex returns APPROVE, PEOS produces a concise final report containing:

- task
- governing specification
- files changed
- verification results
- independent review result
- remediation performed, if any
- known limitations
- Git working-tree status
- recommended next human action

PEOS then stops.

---

## 7. Human Gates

Automation V1 must stop for human input when:

1. no approved specification exists for a significant engineering change
2. specification intent is ambiguous or contradictory
3. physics behavior would change
4. control or protection behavior would change
5. architecture requires a new engineering decision
6. review findings cannot be resolved without changing approved scope
7. verification fails and the cause cannot be resolved within approved scope
8. Codex still returns CHANGES REQUIRED after one remediation cycle
9. merge, release, or tag approval is required

---

## 8. Verification

PEOS must execute deterministic verification defined by the repository and governing specification.

For the current AI Power Lab repository this may include:

    python -m pytest -q

and frontend:

    npm run lint
    npm run typecheck
    npm run build

The orchestrator must not treat agent statements such as "tests should pass" as verification evidence.

Verification results must come from executed commands and recorded exit status/output.

---

## 9. Agent Separation

Claude Code is the implementation agent.

Codex is the independent verification/review agent.

The same agent must not act as both implementer and independent reviewer for the same change.

Codex must not modify implementation during independent review.

Claude must not self-approve its implementation.

---

## 10. State and Artifacts

Automation should rely on repository artifacts rather than conversational memory wherever practical.

Relevant artifacts include:

- approved specifications
- ENGINEERING.md
- CLAUDE.md
- AGENTS.md
- architecture decisions
- validation records
- Git diff/status
- test results
- review findings

Agent conversation history is not the source of truth.

---

## 11. Safety and Failure Behavior

PEOS must fail closed.

If an agent command fails, output cannot be interpreted reliably, required files are missing, repository state is unsafe, or the orchestrator cannot determine whether a human gate applies, PEOS must stop.

It must not guess and continue.

The final report must make the failure visible.

---

## 12. Git Behavior

Automation V1 may:

- inspect Git status
- inspect Git diff
- create working artifacts required by the approved task

Automation V1 must not automatically:

- merge branches
- push to remote
- create releases
- create or move tags
- force push
- rewrite history

Commit and PR automation are not required for V1.

---

## 13. Out of Scope

Automation V1 does not include:

- autonomous specification creation and approval
- autonomous architecture decisions
- autonomous physics/model decisions
- autonomous merge
- autonomous release
- autonomous deployment
- unlimited agent-to-agent loops
- cloud orchestration infrastructure
- multi-user workflow
- GUI/dashboard for PEOS
- replacement of GitHub Actions

---

## 14. Observability

PEOS should make orchestration visible.

At minimum, the user should be able to see which phase is running:

    [PEOS] Intake
    [PEOS] Claude implementation
    [PEOS] Local verification
    [PEOS] Codex independent review
    [PEOS] Claude remediation
    [PEOS] Codex re-review
    [PEOS] Complete

Errors and human gates must be clearly distinguished from normal progress.

---

## 15. Acceptance Criteria

### AC-001 — Single Entry Point

A user can start an automation run through one local PEOS command.

### AC-002 — Specification Enforcement

PEOS identifies and supplies the governing specification before implementation begins.

### AC-003 — Claude Implementation

PEOS can invoke Claude Code non-interactively or through an equivalent controlled subprocess and capture its result.

### AC-004 — Deterministic Verification

PEOS executes required repository verification and records whether each command passed or failed.

### AC-005 — Independent Codex Review

PEOS can invoke Codex independently and capture a structured APPROVE or CHANGES REQUIRED result.

### AC-006 — Remediation Routing

Codex findings can be supplied back to Claude for one controlled remediation cycle.

### AC-007 — Re-review

Codex can perform a focused re-review after remediation.

### AC-008 — Loop Bound

Automation cannot enter an unlimited Claude/Codex remediation loop.

### AC-009 — Human Escalation

Human-owned engineering decisions stop automation with a clear explanation.

### AC-010 — Git Safety

Automation does not merge, push, release, tag, force-push, or rewrite Git history.

### AC-011 — Failure Safety

Unexpected command failures or uninterpretable agent output stop the workflow rather than silently continuing.

### AC-012 — Final Report

Every run ends with a human-readable report describing outcome, verification, review status, limitations, and recommended next action.

### AC-013 — Existing Product Preservation

Implementing PEOS Automation V1 must not change AI Power Lab simulation physics, API behavior, Scenario A behavior, or frontend product behavior.

### AC-014 — Existing CI Preservation

Existing GitHub Actions quality gates must remain intact and must not be weakened.

---

## 16. Implementation Constraints

Prefer the smallest maintainable local orchestration solution.

Avoid introducing:

- databases
- message queues
- web servers
- orchestration frameworks
- agent frameworks
- unnecessary dependencies

unless a concrete requirement proves they are necessary.

The first implementation should favor transparent subprocess execution, files, Git, and deterministic command results.

---

## 17. Definition of Done

Automation V1 is complete when:

- AC-001 through AC-014 are satisfied
- the workflow can be demonstrated on a safe repository task
- Claude and Codex remain role-separated
- deterministic verification is executed
- one remediation cycle can be demonstrated or tested
- human gates are enforced
- failure behavior is tested
- existing repository tests remain green
- frontend lint/typecheck/build remain green
- independent review approves the implementation
- CI remains green
- the Human Engineering Lead approves the result

---

## 18. Future Direction

Automation V1 is intentionally conservative.

Future versions may add:

- automatic branch creation
- automatic commits
- PR creation
- CI polling
- richer structured agent protocols
- persistent run state
- resumable workflows
- multiple specialized reviewers
- a unified desktop or web interface

These should only be added after the simpler V1 workflow proves reliable.