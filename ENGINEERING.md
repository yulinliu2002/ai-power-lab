# Engineering Workflow (PEOS)

This project uses PEOS — a lightweight, artifact-driven workflow for
engineering with multiple AI agents while keeping the human engineer in
control. The full specification is
`docs/specifications/SPEC-000-peos-bootstrap.md`. Agent roles and
authority are defined in `AGENTS.md`. This file covers the process itself.

The repository, specifications, tests, and validation evidence are the
shared engineering source of truth. **Chat history is not.**

## Purpose

PEOS must improve engineering traceability, implementation consistency,
independent verification, automated quality control, and reuse of
project context across AI agents — without introducing process for its
own sake. If a lighter-weight artifact teaches/enforces the same thing,
prefer it.

## Roles

Five parties participate: the **Human Engineering Lead** (final
authority — approves specs, architecture, and merges), **ChatGPT**
(engineering/systems partner — problem formulation, specs, physics
reasoning), **Claude Code** (implementation owner), **Codex** (independent
reviewer — review-first, never silently modifies implementation), and
**GitHub Actions** (automated quality gate — CI passing is not proof the
physical model is correct). Full responsibilities and constraints for
each are defined in `AGENTS.md`; this list is a pointer, not a
duplicate.

## Core Workflow

```
Engineering Question
  -> Specification
  -> Implementation
  -> Local Verification
  -> Independent Review
  -> Fixes if required
  -> Pull Request
  -> CI
  -> Human Approval
  -> Merge
  -> Validation Record
```

The workflow is human-orchestrated. Agents must not autonomously create
agent-to-agent execution loops.

1. **Engineering Question** — a problem or goal is stated.
2. **Specification** — written to `docs/specifications/SPEC-NNN-<slug>.md`
   using `docs/specifications/TEMPLATE.md`, and approved by the Human
   Engineering Lead before implementation starts.
3. **Implementation** — against the approved spec only.
4. **Local Verification** — run the commands/checks the spec's
   Verification section calls for.
5. **Independent Review** — a reviewer distinct from the implementer
   checks the work against the spec (see `AGENTS.md`).
6. **Fixes if required**, then a **Pull Request** using
   `.github/pull_request_template.md`.
7. **CI** — automated, reproducible evidence. CI passing does not prove
   the physical model is correct; CI failing means the change is not
   ready to merge.
8. **Human Approval** and **Merge**.
9. **Validation Record** — evidence of what was verified, filed in
   `docs/validation/`.

## Source-of-Truth Hierarchy

When engineering artifacts disagree, resolve using this order:

1. Approved Engineering Specification
2. Approved Architecture / Engineering Decision (`docs/decisions/`)
3. Explicit Validation Criteria
4. Implementation
5. Automated Tests and Recorded Results
6. Agent conversation history

Conversation history must never override an approved repository artifact.
If an implementation disagrees with an approved specification, do not
silently edit the specification to match the implementation — determine
which artifact is wrong and say so.

## Engineering Specification Standard

Significant changes (physics, architecture, APIs, or other significant
engineering behavior) start with a specification written from
`docs/specifications/TEMPLATE.md`. A specification should contain an
Engineering Question, Motivation, Scope, Out of Scope, Model / Technical
Basis, Assumptions, Requirements, Acceptance Criteria, a Verification
Plan, and Known Limitations. Small maintenance changes and trivial bug
fixes do not need this overhead.

## Definition of Done

A significant engineering task is done only when:

1. approved requirements are satisfied,
2. implementation is complete,
3. relevant tests exist,
4. existing tests pass,
5. engineering validation is performed where applicable,
6. independent review findings are resolved or explicitly accepted,
7. CI is green,
8. documentation is updated when the change affects architecture, model
   assumptions, interfaces, or user-visible engineering behavior,
9. the Human Engineering Lead approves the change.

Agent claims such as "done," "working," or "looks correct" are not
verification evidence.

## Verification Philosophy

Four layers, used progressively as applicable rather than all-or-nothing:

1. **Unit tests** — individual functions and components.
2. **Physics invariants** — physical/mathematical relationships, e.g.
   `E_dc = 1/2 C_dc V_dc^2`, checked within explicit tolerances
   (`tests/test_dc_bus.py`).
3. **Regression tests** — established scenarios don't change
   unexpectedly (`tests/test_grid_scenarios.py`,
   `tests/test_thermal_protection_simulation.py`).
4. **Scenario validation** — qualitative/quantitative engineering
   behavior, e.g. increasing `C_dc` should reduce voltage-droop severity
   for the same load transient; increasing SST response time constant
   should increase transient severity (`tests/test_api.py`).

AI review is not itself validation evidence. Evidence comes from
reproducible tests, calculations, or explicitly documented engineering
reasoning, recorded in `docs/validation/`.

## Current CI Coverage

`.github/workflows/ci.yml` today runs, on every push and pull request:

- **Python job** — the full `pytest` suite in one run, which already
  spans unit tests, DC-bus physics-invariant tests (`test_dc_bus.py`),
  scenario regression tests (`test_grid_scenarios.py`,
  `test_thermal_protection_simulation.py`), FastAPI endpoint tests, and
  API/simulation-adapter parity tests (`test_api.py`) — i.e. layers 1-4
  above and the "API tests" / "API/model parity tests" gates from
  `AGENTS.md`'s GitHub Actions role.
- **Frontend job** — `npm run lint`, `npm run typecheck`, `npm run build`.

Not yet separate CI jobs (tracked as future work, not added by this
bootstrap): dedicated physics-invariant/regression jobs split out from
the single Python job. The coverage exists today inside that one job.

## Repository Map

```
docs/
├── architecture/      design notes: how subsystems are decomposed
├── specifications/    SPEC-NNN documents (TEMPLATE.md to start one)
├── decisions/         short records of specific engineering decisions
└── validation/        evidence that a spec's acceptance criteria were met

.github/
├── workflows/              CI (automated quality gate)
└── pull_request_template.md

CLAUDE.md      AI Power Lab's modeling/scope rules for Claude Code
AGENTS.md      PEOS roles, authority, and agent working rules
ENGINEERING.md this file
```
