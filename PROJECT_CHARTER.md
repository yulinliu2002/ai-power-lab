# AI Power Lab — Project Charter

This is a project-governance document. It defines **why** AI Power Lab exists and the
long-term strategic direction of the project. It does not define how work is executed
(`ENGINEERING.md`), who has what authority (`AGENTS.md`), or modeling/scope rules
(`CLAUDE.md`) — read all three alongside this charter.

The Human Engineering Lead remains the final authority on every decision. This charter
provides strategic context for roadmap, architecture, and scope decisions; it does not
override an explicit Human Engineering Lead decision.

## 1. Mission

AI Power Lab is an educational, system-level digital twin of an SST-powered 800 VDC
AI data-center power chain (grid → SST → 800 VDC bus → dynamic AI compute load).

It is **not** primarily:

- a dashboard,
- a UI showcase,
- a collection of unrelated simulations,
- a feature-count exercise,
- a generic portfolio demo.

Its mission is to build and demonstrate credible **system-level reasoning** about
AI data-center electrical infrastructure — the interaction of power conversion,
controls, stored energy/buffering, transient response, thermal behavior, protection,
reliability, system integration, requirements, and verification.

The project must remain educational and public-knowledge-only. No employer-proprietary,
confidential, internal, or non-public information may be used (see `CLAUDE.md`'s
Integrity Rules, which remain authoritative on this point).

## 2. Dual Purpose

AI Power Lab serves two simultaneous strategic purposes. Every major roadmap decision
and product specification should be evaluated against both.

### 2.1 Product Purpose

Evolve into a credible educational systems-engineering and architecture environment
for AI data-center power infrastructure.

### 2.2 Career-Development Purpose

Deliberately develop and demonstrate the systems-engineering knowledge required for
the Human Engineering Lead's intended career progression:

```
Equipment / Controls Engineering
  -> Systems Engineering
  -> Senior Systems Engineering
  -> Systems Architecture / Technical Leadership
```

with particular relevance to AI data-center power infrastructure.

## 3. Dual ROI Gate

Every future product specification and major roadmap proposal must explicitly evaluate
two gates:

- **Product ROI** — "Does this materially advance AI Power Lab toward a credible AI
  data-center power-infrastructure systems-engineering / architecture tool?"
- **Career ROI** — "Does this materially develop or demonstrate knowledge relevant to
  the Human Engineering Lead's transition toward Systems Engineering / Architecture
  and AI power infrastructure?"

A proposal that is weak against **both** gates should normally be deferred or rejected.
Passing only because something is visually impressive, technically interesting, easy to
implement, or increases feature count is not sufficient on its own.

This gate is strategic framing for roadmap and specification proposals. It does not
impose a new approval step beyond the Core Workflow already defined in `ENGINEERING.md`,
and it does not require every small implementation task to restate it.

## 4. Career-Learning Priorities

These are **strategic priorities for what the project should deliberately create
opportunities to learn and demonstrate** — not technical requirements that every
feature must satisfy, and not a constraint on implementation technique.

**P0 — Highest priority**

1. Systems architecture & controls (subsystem boundaries, interfaces, control
   authority, dynamic interactions, requirement allocation, cross-domain behavior,
   limiting constraints).
2. SST / power-electronics architecture at the system level (conversion stages,
   source/load interaction, converter response, DC-link behavior, control structure,
   energy buffering, architecture trade-offs).
3. AI data-center power architecture (utility/MV distribution, power conversion, DC
   distribution, 800 VDC concepts, downstream conversion, AI rack/load behavior,
   dynamic workload impact, power-delivery architecture).

**P1 — High priority**

4. Thermal / protection / reliability.
5. Controls / SCADA / industrial integration.
6. Commissioning / FAT / SAT / sequence-of-operation / system validation.

**P2 — Important supporting knowledge**

7. Requirements engineering.
8. Relevant industry standards.
9. Real-world system-architecture patterns.
10. Verification and validation methodology.

**Lower priority unless a specific architecture question requires it:** detailed
semiconductor device physics, switching-level SiC/GaN device modeling, and
device-level optimization that does not materially improve system-level reasoning.
These are not prohibited (and remain explicitly Out of Scope per `CLAUDE.md` unless
that scope is revisited) — they are simply lower ROI for the current objective unless
a future architecture question requires them.

## 5. Product Maturity Direction

The intended maturity progression:

```
OBSERVE -> EXPLAIN -> COMPARE -> TRADE STUDY -> REQUIREMENTS -> ARCHITECTURE
```

- **OBSERVE** — measure and visualize trustworthy model behavior.
- **EXPLAIN** — explain why the system behaved as it did.
- **COMPARE** — compare disturbances, scenarios, and system responses.
- **TRADE STUDY** — vary legitimate design parameters and reason about competing
  effects.
- **REQUIREMENTS** — express target behavior, constraints, margins, and verification
  criteria.
- **ARCHITECTURE** — reason about how system structure and parameter choices satisfy
  defined requirements and constraints.

The project must not remain indefinitely in dashboard/visualization/scenario-display
work. As of this charter, the repository has progressed through significant parts of
OBSERVE, EXPLAIN, and COMPARE (protection timeline, protection coordination, and an
approved scenario-comparison architecture in SPEC-010). After SPEC-010 is implemented,
roadmap selection should increasingly favor design-space reasoning, parameter
sensitivity with engineering meaning, architecture trade studies, requirements,
constraint analysis, subsystem interactions, limiting factors, and verification against
requirements — over additional dashboard-only features.

## 6. Systems-Engineering Question Ladder

The project should increasingly progress from answering "what happened?" toward:

- Why did it happen?
- What subsystem or constraint became limiting?
- What physical quantity dominated the response?
- What changes if a design parameter changes?
- What improves? What gets worse?
- Where does the stress move elsewhere in the system?
- What requirement is driving the design?
- What architecture best satisfies the defined requirements and constraints?

This ladder should influence roadmap selection, favoring specifications that move work
further down the ladder over ones that repeat earlier rungs.

## 7. Trade-Study Principle

Future design-space exploration must avoid arbitrary optimization. Illustrative
principles the project should eventually be able to reason about include (these are
illustrative, not approved quantitative models):

- DC-link capacitance increases → stored energy increases → transient voltage support
  may improve → but size/cost/stored fault energy may increase.
- Converter response becomes faster → DC-bus transient performance may improve → but
  control/converter demands may increase.

A trade study must use physically defensible parameters and clearly defined
assumptions, consistent with `CLAUDE.md`'s Modeling Rules. Do not introduce fake
precision, arbitrary weighted scores, or unsupported optimization objectives.

## 8. Anti-Feature-Creep Rule

A feature must not be prioritized merely because it looks impressive, adds another
dashboard/card/plot, adds another scenario without a systems-engineering reason,
increases feature count, is technically interesting, or is convenient for an agent to
implement.

A future specification should have a clear systems-engineering purpose and meaningful
Product ROI and/or Career ROI (§3). Where possible, the specification should explicitly
state what systems-engineering capability or knowledge gap it advances.

This rule is a prioritization lens for roadmap decisions and specification authors — it
is not an additional review gate on top of `ENGINEERING.md`'s Core Workflow, and it does
not apply to implementation-level technical choices within an already-approved
specification.

## 9. Relationship Between Governance Artifacts

```
PROJECT_CHARTER.md                 (this file — WHY, strategic direction)
    |
ENGINEERING.md / AGENTS.md         (HOW work is executed, reviewed, verified, approved)
    |
CLAUDE.md                          (modeling rules, V1 scope, out-of-scope boundaries)
    |
Accepted product specification     (WHAT capability is being delivered)
    |
Implementation
    |
Verification / evidence (docs/validation/)
```

This hierarchy describes strategic precedence (why a direction is chosen), not the
engineering-artifact conflict rule. `ENGINEERING.md`'s Source-of-Truth Hierarchy — which
ranks an approved specification above architecture decisions, validation criteria,
implementation, tests, and conversation history — continues to govern disagreements
between engineering artifacts (spec vs. implementation, spec vs. test, etc.) and operates
*within* the strategic direction this charter and `ENGINEERING.md`/`AGENTS.md`/`CLAUDE.md`
set. The two hierarchies answer different questions and do not override one another.

No lower-level artifact should silently contradict this charter's strategic direction.
If such a conflict is found, report it rather than silently resolving it — conversation
history and agent judgment never override an approved repository artifact, and an
explicit Human Engineering Lead decision is always authoritative over this charter.

## 10. When to Consult This Charter

Claude, Codex, and ChatGPT (per the PEOS roles in `AGENTS.md`) should consult this
charter when:

- proposing a new product specification,
- prioritizing roadmap work,
- deciding between candidate features,
- evaluating scope expansion,
- making system-architecture recommendations,
- deciding whether technically interesting work is strategically worthwhile,
- performing roadmap reviews.

This charter does not create ceremony for small implementation details — it is
strategic context for roadmap, architecture, and major scope decisions, not a checklist
for routine engineering work already governed by `ENGINEERING.md` and `AGENTS.md`.

## 11. Current Roadmap Context (informational, not normative)

As of this charter's drafting, SPEC-010 (Scenario Comparison & System Stress Analysis)
is Architecture Approved but **not implemented**. It is a presentation/derived-data
layer over existing scenario and Protection Timeline data (no new engineering model,
no change to `src/`). After SPEC-010 is implemented, future roadmap planning should
increasingly investigate TRADE STUDY / REQUIREMENTS / ARCHITECTURE capabilities (§5)
rather than defaulting to additional dashboard features. This section records roadmap
state at drafting time and will go stale — treat `docs/specifications/` as the
authoritative current roadmap status, not this section.
