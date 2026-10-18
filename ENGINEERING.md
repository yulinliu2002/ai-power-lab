# Engineering Workflow

This project uses a lightweight, artifact-driven Claude + Codex + GitHub PR
process, orchestrated by the human engineer. Agent roles and the shared
authoritative documents are defined in `AGENTS.md`. This file covers the
process and verification standards.

> PEOS, the earlier orchestration runtime, is retired and removed. It is
> available only at git tag `pre-peos-retirement`. Specifications and
> validation records that mention PEOS are historical.

The repository, specifications, tests, and validation evidence are the
shared engineering source of truth. **Chat history is not.**

Before proposing a new specification, prioritizing roadmap work, or evaluating a
scope change, consult `PROJECT_CHARTER.md` for the project's strategic direction
(product and career ROI, maturity progression, anti-feature-creep rule). The
charter defines *why*; this file defines *how*.

## Core Workflow

```
Engineering Question
  -> Specification (significant changes)
  -> Implementation (Claude)
  -> Local Verification
  -> Independent Review (Codex)
  -> Fixes if required
  -> Pull Request
  -> CI
  -> Human Approval
  -> Merge
  -> Validation Record
```

The workflow is human-orchestrated. Agents must not autonomously create
agent-to-agent execution loops.

1. **Specification** — significant changes are written to
   `docs/specifications/SPEC-NNN-<slug>.md` from `TEMPLATE.md` and approved
   by the Human Engineering Lead before implementation starts.
2. **Implementation and local verification** — Claude implements against
   the approved spec only and runs the checks the spec calls for.
3. **Independent review** — Codex reviews the diff, requirements and
   evidence (see `AGENTS.md`).
4. **Pull Request** using `.github/pull_request_template.md`, then **CI**.
   CI passing does not prove the physical model is correct; CI failing
   means the change is not ready to merge.
5. **Human approval and merge.**
6. **Validation Record** — evidence of what was verified, filed in
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

`.github/workflows/ci.yml` runs on every push and pull request:

- **Python job** — the full `pytest` suite (unit, physics-invariant,
  scenario regression, FastAPI endpoint and API/adapter parity tests).
- **Frontend job** — `npm run lint`, `npm run typecheck`, `npm run build`.

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
AGENTS.md      agent roles, authority, and shared authoritative documents
ENGINEERING.md this file
```
