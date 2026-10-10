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