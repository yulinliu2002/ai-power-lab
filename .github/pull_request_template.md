<!--
PEOS pull request template. See ENGINEERING.md and AGENTS.md for the full
workflow this maps to.
-->

## Specification

- Spec: <!-- e.g. docs/specifications/SPEC-003-xyz.md -->
- Summary of what this PR implements:

## Changes

- Files created:
- Files modified:
- Out-of-scope items explicitly NOT touched (physics, product behavior,
  API contracts) unless this PR's spec says otherwise:

## Local Verification

<!-- Exact commands run and their result, per the spec's Verification
section (or docs/specifications/TEMPLATE.md if the spec predates one). -->

- [ ] `pytest -q` passes
- [ ] Frontend lint / typecheck / build passes (if frontend touched)
- [ ] Verification commands from the spec:

## Independent Review (Codex)

- [ ] Implementation matches the approved specification
- [ ] Physics / mathematical correctness checked (if applicable)
- [ ] No silent change to an approved requirement, physics assumption,
      acceptance criterion, or API contract
- [ ] Test adequacy checked
- [ ] Findings categorized (defect / spec ambiguity / missing test /
      missing validation evidence / architecture concern / non-blocking)

## Reviewer Findings Disposition

<!-- One row per Codex finding. A PR is not Done (see ENGINEERING.md's
Definition of Done) until every finding below is either fixed or
explicitly accepted by the Human Engineering Lead — "looks fine" from an
agent is not a disposition. -->

| Finding | Severity | Disposition (resolved / explicitly accepted) | Reference (commit, comment, or decision record) |
| --- | --- | --- | --- |
|  |  |  |  |

## Specification Conflicts / Limitations

<!-- Anything where the spec was ambiguous, incomplete, or contradicted
the implementation. Do not silently resolve these by editing the spec. -->

## Human Approval

- [ ] Reviewed by Human Engineering Lead
- [ ] Validation record added to `docs/validation/` (if applicable)
