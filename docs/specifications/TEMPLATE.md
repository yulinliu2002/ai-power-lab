# SPEC-NNN — \<Title\>

**Status:** Draft
**Project:** AI Power Lab
**System:** \<subsystem or workflow this spec covers\>
**Version:** 0.1
**Type:** \<Engineering Model | Software Component | Workflow Infrastructure\>

---

Small maintenance changes and trivial bug fixes do not need this template
(see `ENGINEERING.md`'s "Engineering Specification Standard" section).
Use it when the change affects physics, architecture, APIs, or other
significant engineering behavior.

## Engineering Question

What question or problem is this specification answering?

## Motivation

Why this matters now — the goal, constraint, or gap driving the change.

## Scope

What this specification covers.

## Out of Scope

What this specification explicitly does not cover. If anything here
conflicts with `CLAUDE.md`'s "Out of Scope" list, stop and resolve that
conflict before writing the rest of the spec.

## Model / Technical Basis

For an engineering model: governing equation(s), with the physical
meaning of every term. For a non-physics change: the technical approach.

## Assumptions

Units of every input, state, and output. Steady-state vs. dynamic,
linearization, idealizations, and other neglected effects the model or
implementation relies on.

## Requirements

Concrete functional requirements the implementation must satisfy.

## Acceptance Criteria

Checkable conditions that must hold for this spec to be considered
implemented. Prefer statements a test or verification command can confirm
directly.

- [ ] ...

## Verification Plan

The exact commands or checks an implementer and an independent reviewer
run to confirm the acceptance criteria are met (e.g. `pytest -q`, a named
test file, a specific manual check). Map each criterion to one of the
four verification layers in `ENGINEERING.md`'s "Verification Philosophy"
section where applicable (unit test, physics invariant, regression,
scenario validation).

## Known Limitations

What this spec does not cover, known idealizations, and the regime
outside which it is not valid. Include unresolved questions that need the
Human Engineering Lead's decision.
