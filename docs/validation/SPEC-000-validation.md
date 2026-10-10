# SPEC-000 — PEOS Bootstrap — Validation Record

## Context

- Spec: `docs/specifications/SPEC-000-peos-bootstrap.md` (approved,
  commit `ee57bed`)
- Branch: `peos/bootstrap-v1`
- Revision this record was produced against: `ee57bed`
  (`ee57beddbce9536293faeff8c71a326e937a0740`, committed
  2026-10-09T20:59:50-07:00) plus uncommitted PEOS-bootstrap working-tree
  changes (new files under `docs/`, `AGENTS.md`, `ENGINEERING.md`,
  `.github/pull_request_template.md`, and an additive section appended
  to `CLAUDE.md`). Nothing has been committed for this bootstrap work as
  of this record.

## Verification commands and results

All commands run from a clean re-check of the working tree described
above; no simulation, API, or frontend source files were touched
between runs.

### Python tests

```
$ pytest -q
........................................................................ [ 83%]
..............                                                           [100%]
86 passed, 1 warning in 1.97s
```

The one warning is a pre-existing `StarletteDeprecationWarning` from
`fastapi.testclient` (`httpx` vs. `httpx2`), unrelated to this bootstrap.

### Frontend lint

```
$ npm run lint
> frontend@0.1.0 lint
> eslint
```

No output, exit 0 — clean.

### Frontend type checking

```
$ npm run typecheck
> frontend@0.1.0 typecheck
> next typegen && tsc --noEmit
Generating route types...
✓ Types generated successfully
```

Clean, no type errors.

### Frontend production build

```
$ npm run build
> frontend@0.1.0 build
> next build
▲ Next.js 16.3.8 (Turbopack)
✓ Compiled successfully in 464ms
  Running TypeScript ...
  Finished TypeScript in 889ms ...
✓ Generating static pages using 5 workers (4/4) in 200ms

Route (app)
┌ ○ /
└ ○ /_not-found
○  (Static)  prerendered as static content
```

Build succeeded.

### Repository diff review (no accidental product changes)

```
$ git status
  modified:   CLAUDE.md
  (untracked: docs/decisions/, docs/validation/, docs/specifications/TEMPLATE.md,
   docs/architecture/, .github/pull_request_template.md, AGENTS.md,
   ENGINEERING.md, skills-lock.json)

$ git diff --stat
 CLAUDE.md | 29 +++++++++++++++++++++++++++++
 1 file changed, 29 insertions(+)
```

`CLAUDE.md` is the only tracked file touched, and the diff is a pure
addition (29 insertions, 0 deletions) — an appended "Engineering
Workflow (PEOS)" section. No lines of existing `CLAUDE.md` content, and
no simulation (`src/`), API (`backend/`), or frontend (`frontend/`)
source file, were modified.

## Confirmation: no intentional product-behavior change

Verified by the diff above: this bootstrap touched no file under `src/`,
`backend/`, `frontend/` (other than running its own lint/typecheck/build
checks, which modify no source), `scenarios/`, `config/`, or
`.github/workflows/ci.yml`. Simulation physics, FastAPI contracts, and
frontend product behavior were not intentionally changed, and the test
suite confirms no unintentional change either (same 86/86 pass count as
pre-bootstrap).

## Relevant limitations

- This record itself has not been reviewed or accepted by the Human
  Engineering Lead yet — per `ENGINEERING.md`'s Definition of Done, that
  review is still outstanding.
- `skills-lock.json`'s `computedHash` for `design-taste-frontend` does
  not match the sha256 of the on-disk `SKILL.md` it supposedly pins —
  see `docs/decisions/0001-agent-skill-version-control.md` for the
  verified detail. This is a pre-existing condition of the repository,
  not something this bootstrap introduced or can resolve.
- No CI run evidence is included here — these are local verification
  results only, run interactively. A CI run against the actual PR will
  be the reproducible, machine-independent version of this evidence.
