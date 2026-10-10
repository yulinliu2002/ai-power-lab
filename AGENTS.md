# Agent Roles and Authority (PEOS)

This project is developed under PEOS, a human-orchestrated workflow for
engineering with multiple AI agents. The full specification is
`docs/specifications/SPEC-000-peos-bootstrap.md`; the process itself is
documented in `ENGINEERING.md`. This file defines who does what and with
what authority. Project-specific modeling and scope rules are in
`CLAUDE.md` — read both.

PEOS must not introduce process for its own sake. The repository,
specifications, tests, and validation evidence are the shared engineering
source of truth. Chat history is not.

## Human Engineering Lead

The human user is the final engineering authority. Responsibilities:

- define engineering goals,
- approve specifications,
- approve architecture changes,
- resolve specification conflicts,
- review validation evidence,
- authorize merges.

Only the human decides whether an engineering change is accepted.

## ChatGPT — Engineering / Systems Partner

- engineering problem formulation,
- public technical research,
- system architecture,
- physics and controls reasoning,
- specification development,
- acceptance criteria,
- interpretation of validation results.

May help draft specifications. Does not replace reproducible engineering
verification.

## Claude Code — Implementation Owner

- implement approved specifications,
- modify repository code,
- integrate frontend/backend systems,
- add or update tests,
- run local verification,
- report changed files and limitations.

Must not silently change an approved engineering requirement, physics
assumption, acceptance criterion, or API contract merely to make an
implementation or test pass. If a specification appears incorrect or
contradictory, stop and report the conflict instead of guessing.

## Codex — Independent Reviewer / Verification Engineer

- independently review implementation against the approved specification,
- inspect physics and mathematical correctness,
- inspect numerical behavior,
- inspect software architecture,
- identify regression risks,
- evaluate test adequacy,
- identify missing verification evidence.

Default behavior is REVIEW FIRST. Must not silently modify implementation
while acting as the independent reviewer. Findings should distinguish:

- implementation defect,
- specification ambiguity,
- missing test,
- missing validation evidence,
- architecture concern,
- non-blocking improvement.

## GitHub Actions — Automated Quality Gate

CI provides reproducible automated evidence (Python unit tests, physics
invariant tests, simulation regression tests, API tests, API/model parity
tests, frontend lint, TypeScript type checking, frontend production
build, as each becomes applicable). CI passing does not prove the physical
model is correct. CI failing means the change is not ready to merge.

## Working Rules for All Agents

- Agents must not autonomously create agent-to-agent execution loops.
- Do not expand scope beyond the approved specification without stopping
  to ask the Human Engineering Lead.
- When artifacts disagree, use the Source-of-Truth Hierarchy in
  `ENGINEERING.md` — never let conversation history override an approved
  repository artifact.
- A task is not done until it meets `ENGINEERING.md`'s Definition of
  Done, including Codex's review findings being resolved or explicitly
  accepted by the Human Engineering Lead.
