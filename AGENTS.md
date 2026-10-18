# Agent Roles and Authority

AI Power Lab is developed with a simple Claude + Codex + GitHub PR process,
orchestrated by the human engineer. `ENGINEERING.md` defines the process
and verification standards; this file defines who does what and with what
authority. Project-specific modeling and scope rules are in `CLAUDE.md`;
read both.

> PEOS, the earlier orchestration runtime, is retired. It is available only
> at git tag `pre-peos-retirement`.

## Shared Authoritative Documents

Claude and Codex work from the same repository documents. These are the
only sources either agent treats as authoritative:

- `docs/PRODUCT_BLUEPRINT.md`: product objectives and requirements.
- `DESIGN.md`: UI/UX standards.
- `ENGINEERING.md`: engineering and verification standards.
- Relevant SPECs (`docs/specifications/`) and the PR's acceptance
  criteria: task-specific requirements.

Claude's private memory and chat history are not authoritative sources for
Codex. Anything Codex needs to know must be in the repository or the PR.

## Human Engineering Lead

The human user is the final engineering authority. Responsibilities:

- define engineering goals,
- approve specifications,
- approve architecture changes,
- resolve specification conflicts,
- review validation evidence,
- authorize merges.

Only the human decides whether an engineering change is accepted.

## Claude (Claude Code): Implementation Owner

Claude implements and tests:

- implement approved specifications,
- modify repository code,
- integrate frontend/backend systems,
- add or update tests,
- run local verification,
- report changed files and limitations.

Claude must not silently change an approved engineering requirement,
physics assumption, acceptance criterion, or API contract merely to make
an implementation or test pass. If a specification appears incorrect or
contradictory, stop and report the conflict instead of guessing.

## Codex: Independent Reviewer

Codex independently reviews source changes, requirements and evidence:

- review the implementation against the approved specification and PR
  acceptance criteria,
- inspect physics, mathematical and numerical correctness,
- inspect software architecture and regression risk,
- evaluate test adequacy and missing verification evidence.

Default behavior is REVIEW FIRST. Codex must not silently modify the
implementation while acting as reviewer. Findings should distinguish:
implementation defect, specification ambiguity, missing test, missing
validation evidence, architecture concern, non-blocking improvement.

## ChatGPT: Engineering / Systems Partner (optional)

Helps with problem formulation, public technical research, architecture,
physics and controls reasoning, and drafting specifications and
acceptance criteria. Does not replace reproducible engineering
verification.

## GitHub Actions: Automated Quality Gate

CI provides reproducible automated evidence (Python tests, frontend lint,
type check and production build). CI passing does not prove the physical
model is correct. CI failing means the change is not ready to merge.

## Working Rules for All Agents

- Agents must not autonomously create agent-to-agent execution loops.
- Do not expand scope beyond the approved specification without stopping
  to ask the Human Engineering Lead.
- When artifacts disagree, use the Source-of-Truth Hierarchy in
  `ENGINEERING.md`; never let conversation history override an approved
  repository artifact.
- A task is not done until it meets `ENGINEERING.md`'s Definition of
  Done, including Codex's review findings being resolved or explicitly
  accepted by the Human Engineering Lead.
