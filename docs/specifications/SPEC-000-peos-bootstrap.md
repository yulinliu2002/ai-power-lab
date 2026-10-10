# SPEC-000 — PEOS Bootstrap

**Status:** Approved  
**Project:** AI Power Lab  
**System:** Personal Engineering OS (PEOS)  
**Version:** 1.0  
**Type:** Engineering Workflow Infrastructure

---

## 1. Purpose

Establish PEOS V1.0 inside AI Power Lab.

PEOS is a lightweight, artifact-driven engineering workflow for using
multiple AI engineering agents while keeping the human engineer in control.

The workflow must improve:

1. engineering traceability,
2. implementation consistency,
3. independent verification,
4. automated quality control,
5. reuse of project context across AI agents.

PEOS must not introduce process for its own sake.

The repository, specifications, tests, and validation evidence are the
shared engineering source of truth.

Chat history is not the engineering source of truth.

---

## 2. Core Workflow

The standard engineering workflow is:

Engineering Question
→ Specification
→ Implementation
→ Local Verification
→ Independent Review
→ Fixes if required
→ Pull Request
→ CI
→ Human Approval
→ Merge
→ Validation Record

The workflow is human-orchestrated in PEOS V1.0.

Agents must not autonomously create agent-to-agent execution loops.

---

## 3. Roles and Authority

### Human Engineering Lead

The human user is the final engineering authority.

Responsibilities:

- define engineering goals,
- approve specifications,
- approve architecture changes,
- resolve specification conflicts,
- review validation evidence,
- authorize merges.

Only the human decides whether an engineering change is accepted.

---

### ChatGPT — Engineering / Systems Partner

Primary responsibilities:

- engineering problem formulation,
- public technical research,
- system architecture,
- physics and controls reasoning,
- specification development,
- acceptance criteria,
- interpretation of validation results.

ChatGPT may help draft specifications.

ChatGPT does not replace reproducible engineering verification.

---

### Claude Code — Implementation Owner

Primary responsibilities:

- implement approved specifications,
- modify repository code,
- integrate frontend/backend systems,
- add or update tests,
- run local verification,
- report changed files and limitations.

Claude must not silently change an approved engineering requirement,
physics assumption, acceptance criterion, or API contract merely to make
an implementation or test pass.

If the specification appears incorrect or contradictory, Claude must stop
and report the conflict.

---

### Codex — Independent Reviewer / Verification Engineer

Primary responsibilities:

- independently review implementation against the approved specification,
- inspect physics and mathematical correctness,
- inspect numerical behavior,
- inspect software architecture,
- identify regression risks,
- evaluate test adequacy,
- identify missing verification evidence.

Default behavior is REVIEW FIRST.

Codex must not silently modify implementation while acting as the
independent reviewer.

Findings should distinguish:

- implementation defect,
- specification ambiguity,
- missing test,
- missing validation evidence,
- architecture concern,
- non-blocking improvement.

---

### GitHub Actions — Automated Quality Gate

CI provides reproducible automated evidence.

CI should progressively cover:

- Python unit tests,
- physics invariant tests,
- simulation regression tests,
- API tests,
- API/model parity tests,
- frontend lint,
- TypeScript type checking,
- frontend production build.

CI passing does not prove that the physical model is correct.

CI failing means the change is not ready to merge.

---

## 4. Source-of-Truth Hierarchy

When engineering artifacts disagree, use this hierarchy:

1. Approved Engineering Specification
2. Approved Architecture / Engineering Decision
3. Explicit Validation Criteria
4. Implementation
5. Automated Tests and Recorded Results
6. Agent conversation history

Conversation history must not override an approved repository artifact.

If an implementation disagrees with an approved specification, do not
silently modify the specification to match the implementation.

Determine which artifact is wrong.

---

## 5. Required Repository Structure

PEOS V1.0 should establish or preserve the following structure:

```text
docs/
├── architecture/
├── specifications/
│   ├── TEMPLATE.md
│   └── SPEC-000-peos-bootstrap.md
├── decisions/
└── validation/

.github/
├── workflows/
└── pull_request_template.md

CLAUDE.md
AGENTS.md
ENGINEERING.md

---

## 6. Engineering Specification Standard

Future engineering features should begin with a lightweight specification
when the change affects physics, architecture, APIs, system behavior, or
other significant engineering behavior.

A specification should contain:

- Engineering Question
- Motivation
- Scope
- Out of Scope
- Model / Technical Basis
- Assumptions
- Requirements
- Acceptance Criteria
- Verification Plan
- Known Limitations

Small maintenance changes and trivial bug fixes do not require unnecessary
specification overhead.

---

## 7. Definition of Done

A significant engineering task is DONE only when:

1. approved requirements are satisfied,
2. implementation is complete,
3. relevant tests exist,
4. existing tests pass,
5. engineering validation is performed where applicable,
6. independent review findings are resolved or explicitly accepted,
7. CI is green,
8. documentation is updated when the change affects architecture,
   model assumptions, interfaces, or user-visible engineering behavior,
9. the human Engineering Lead approves the change.

Agent claims such as "done", "working", or "looks correct" are not
verification evidence.

---

## 8. Verification Philosophy

AI Power Lab should progressively use four verification layers:

### Layer 1 — Unit Tests

Verify individual functions and components.

### Layer 2 — Physics Invariants

Verify physical and mathematical relationships where applicable.

Examples include:

`E_dc = 1/2 C_dc V_dc^2`

and numerical energy-balance consistency within explicitly defined
tolerances.

### Layer 3 — Regression Tests

Verify that established scenarios do not change unexpectedly.

### Layer 4 — Scenario Validation

Verify qualitative and quantitative engineering behavior.

Example:

Increasing C_dc should reduce DC-bus voltage-droop severity for the same
load transient, all else equal.

Increasing SST response time constant should increase transient severity,
all else equal.

AI review is not itself validation evidence.

Evidence should come from reproducible tests, calculations, or explicitly
documented engineering reasoning.

---

## 9. PEOS V1.0 Scope

This bootstrap task includes:

- establish ENGINEERING.md,
- establish or refine CLAUDE.md,
- establish AGENTS.md,
- create the specification template,
- establish architecture / decision / validation documentation locations,
- establish a pull-request template,
- inspect existing CI coverage,
- document the existing CI quality gates,
- determine appropriate treatment of project-local agent skills and
  skills-lock.json,
- preserve all existing AI Power Lab functionality.

---

## 10. Out of Scope

SPEC-000 must NOT:

- change simulation physics,
- change Scenario A behavior,
- change FastAPI contracts,
- change frontend behavior,
- redesign the UI,
- implement Concept 03,
- modify Pixso designs,
- add new simulation scenarios,
- add unnecessary workflow tooling,
- automate agent-to-agent execution,
- merge branches,
- create releases,
- move existing version tags.

---

## 11. Agent Skill Policy

Existing project-local agent tooling must be inspected before deciding
whether it belongs in version control.

In particular:

- inspect `.agents/`,
- inspect `.claude/`,
- inspect `skills-lock.json`,
- identify generated files versus intentional project dependencies,
- avoid committing machine-specific or ephemeral state.

The installed `design-taste-frontend` skill may remain a project-level
design dependency if doing so is reproducible and useful.

No decision should be made solely because a file was generated by an
installation command.

---

## 12. Acceptance Criteria

### AC-001 — Workflow Definition

A concise `ENGINEERING.md` defines:

- PEOS purpose,
- roles,
- standard workflow,
- source-of-truth hierarchy,
- Definition of Done.

### AC-002 — Claude Contract

`CLAUDE.md` gives Claude sufficient project context and explicitly defines
its implementation authority and constraints.

Existing useful Claude instructions must be preserved.

### AC-003 — Independent Review Contract

`AGENTS.md` defines independent review behavior suitable for Codex and
other compatible engineering agents.

### AC-004 — Specification Template

`docs/specifications/TEMPLATE.md` provides a reusable lightweight
engineering specification template.

### AC-005 — Validation Structure

`docs/validation/` documents how engineering validation evidence should
be recorded.

### AC-006 — Decision Structure

`docs/decisions/` provides a lightweight location and format for important
engineering / architecture decisions.

Do not introduce heavyweight ADR bureaucracy.

### AC-007 — Architecture Structure

`docs/architecture/` exists for durable system architecture documentation.

Do not invent architecture documentation merely to populate the directory.

### AC-008 — Pull Request Gate

`.github/pull_request_template.md` asks for:

- specification reference when applicable,
- implementation summary,
- verification performed,
- validation evidence when applicable,
- known limitations,
- reviewer findings status.

### AC-009 — CI Preservation

Existing GitHub Actions behavior remains functional.

Existing Python and frontend quality gates must not be weakened.

### AC-010 — No Product Behavior Change

The bootstrap produces no intentional simulation, API, or frontend behavior
change.

### AC-011 — Agent Skill Decision

The implementation reports and documents the chosen treatment of:

- `.agents/`,
- `.claude/`,
- `skills-lock.json`.

The decision must distinguish reproducible project dependencies from
machine-specific state.

### AC-012 — Verification

Before completion:

- relevant existing Python tests pass,
- frontend lint passes,
- frontend type checking passes,
- frontend production build passes,
- repository diff is reviewed for accidental product changes.

---

## 13. Implementation Constraints

Implementation should be minimal.

Prefer a small number of durable documents over a large process framework.

Do not duplicate the same instructions across multiple files unless the
agent requires local instructions.

Use links between documents where appropriate.

Do not introduce new dependencies unless required.

Do not modify simulation or frontend source code for this task.

---

## 14. Deliverables

Expected deliverables:

- `ENGINEERING.md`
- reviewed / refined `CLAUDE.md`
- `AGENTS.md`
- `docs/specifications/TEMPLATE.md`
- `docs/decisions/README.md`
- `docs/validation/README.md`
- architecture directory if needed
- `.github/pull_request_template.md`
- documented decision for agent-skill files
- verification report

---

## 15. Final Report

The implementation agent must report:

1. files created,
2. files modified,
3. existing instructions preserved,
4. treatment of `.agents/`, `.claude/`, and `skills-lock.json`,
5. tests / checks executed,
6. results,
7. remaining limitations,
8. any specification conflicts discovered.

Do not merge the branch.

Do not create a release.

Do not modify version tags.