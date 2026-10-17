# AI Power Lab 2.0 — Product Blueprint

**Status:** Approved product direction; repository integration pending.
**Source:** Product direction decided by the Human Engineering Lead (with ChatGPT) and
codified here. This document records the decision; it does not reopen it.
**Last verified against the repository:** branch `refactor/ai-power-lab-2`, HEAD `71e589d`,
including uncommitted frontend work (`/`, `/system-map`, `/sandbox`).

---

## 1. Mission

AI Power Lab is a learning-first engineering platform for understanding, evaluating, and
explaining AI data-center electrical power infrastructure.

It develops systems-level reasoning and architecture judgment, not merely simulator
operation or familiarity with engineering terminology.

The Advanced Sandbox is a supporting engineering-experiment environment. It is not the
central product experience.

## 2. Audience

- **Primary:** the Human Engineering Lead, an equipment/controls engineer building toward
  Systems Engineering and Systems Architecture roles in AI data-center power infrastructure.
- **Secondary:** any engineer or technical reader who wants to understand how an AI data
  center is powered and how to reason about its architecture choices.
- Assumed background: engineering literacy. No device-level power-electronics expertise is
  assumed or required.

## 3. Product Areas and Learning Stages

These are two different things and are deliberately kept separate. *Approved architectural
decision.*

### 3.1 Four user-facing product areas

What the user can navigate to:

| Product area | Role |
|---|---|
| **System Map** | Where the learner builds an understanding of the grid-to-rack power chain. |
| **Architecture Choices** | Where the learner evaluates alternative architectures. |
| **Learn by Example** | Where the learner sees scenarios, system responses, and failure cases explained. |
| **Industry & Career** | A product destination *and* cross-cutting context: engineering roles, system integration, standards, industry developments. It also informs the other three areas. |

The **Advanced Sandbox** remains a supporting tool, not a fifth area of equal standing.

### 3.2 Five learning stages

The pedagogical methodology — what a learner develops, regardless of which page they are on:

| # | Stage | Learner outcome |
|---|---|---|
| 1 | **Requirements** | Understand AI workload power demands, dynamic behavior, reliability requirements, and design constraints. |
| 2 | **System Understanding** | Trace grid-to-rack power delivery, conversion stages, storage, protection, cooling, and monitoring interfaces. |
| 3 | **Architecture Evaluation** | Compare conventional AC, transitional 800 VDC, and conceptual SST-based architectures: assumptions, benefits, limitations, trade-offs. |
| 4 | **Scenario-Based Explanation** | Use scenarios, system responses, and failure cases to connect physical behavior with engineering consequences. |
| 5 | **Engineering Judgment** | Compare alternatives, explain trade-offs, formulate requirements, and identify validation needs. |

### 3.3 How they relate

| Product area | Primarily serves stage |
|---|---|
| System Map | 2 — System Understanding |
| Architecture Choices | 3 — Architecture Evaluation |
| Learn by Example | 4 — Scenario-Based Explanation |
| Industry & Career | Context across all stages |

**Requirements and Engineering Judgment do not require separate pages or navigation items.**
They are taught *through* the four areas: requirements appear as the constraints and drivers
that explain each system element and architecture trade-off; judgment is exercised wherever the
learner compares alternatives, explains a trade-off, or identifies what would need validating.

### 3.4 Learning sequence vs. engineering workflow

The five stages are a **pedagogical sequence**, ordered to build understanding. They are not
the order in which real engineering is done.

Real systems engineering is iterative:

> Requirements → Functional Architecture → Physical Architecture → Interface Definition →
> Trade Study → Verification

Requirements are defined and revisited throughout that cycle, including *before* any trade
study. Nothing in this Blueprint implies that requirements are first defined after a trade
study, or that a learner's path through the stages is a design process.

The progression **Observe → Explain → Compare → Trade Study → Requirements → Architecture**
is a *capability-maturity* concept: how deep the platform's reasoning support becomes over
time. It is not a mandatory chronological design process.

## 4. Narrative Standards (Content Quality Contract)

Every major topic must answer:

1. **What is it?**
2. **Why does it matter?**
3. **How does it connect to the larger system?**
4. **What are the constraints and trade-offs?**
5. **What engineering decision does this knowledge inform?**

Do not accumulate jargon without building causal understanding. A term introduced without a
cause-and-effect link to the rest of the system is a defect, not content.

## 5. Engineering Integrity Rules

### 5.1 Evidence categories

Content draws on four kinds of material. Keep them distinct.

| Category | What it is | Handling |
|---|---|---|
| **Publicly sourced facts and inputs** | Established principles, standards, datasheet or published values, attributed public statements. | Cite the public source where a specific figure or claim is used. |
| **Illustrative assumptions** | Parameter values and topologies chosen for teaching (ratings, gains, time constants, thresholds). | Label as educational assumptions. They are not data. |
| **Model-calculated outputs** | Results the simulation computes from its assumptions. | Present as calculated from stated model assumptions. They are not themselves assumptions, and they are not verified performance of any commercial equipment. |
| **Emerging architectures and uncertain industry claims** | Architectures not yet widely deployed; adoption, timing, or performance claims. | Mark as emerging or uncertain. Attribute, or omit. Unverified records stay marked `sample`. |

**Labeling granularity.** Apply evidence labels at the section, case, figure, or table level,
and wherever a claim could otherwise be misread. Labeling every sentence is neither required
nor desirable.

### 5.2 Rules

1. **SST is not mandatory for 800 VDC.** An 800 VDC bus can be fed by other conversion
   approaches. SST is one candidate technology for the MV-to-DC stage.
2. **Conceptual blocks are not literal converters.** A block such as "SST" or "AI Compute"
   in a diagram is a functional abstraction (internally multi-stage; not a single physical
   converter; not a literal rack). Say so wherever it appears.
3. **No unsupported vendor or adoption claims.** Performance figures and adoption statements
   must be attributed to a named public source or omitted.
4. **Public information only.** No employer-confidential or proprietary information
   (`CLAUDE.md` Integrity Rules remain authoritative).
5. **Conceptual diagrams are labeled** as illustrative and never styled as live readouts
   (see `DESIGN.md`).

## 6. Product ROI and Career ROI

**Gate:** every proposed feature, page, or specification must state how it satisfies *both*.
Passing only one, or neither, means defer or reject. Visual polish, technical interest, and
ease of implementation do not count as ROI.

**Product ROI.** Does it improve a learner's ability to understand, compare, and explain
real-world AI data-center power architectures? Capability maturity runs Observe → Explain →
Compare → Trade Study → Requirements → Architecture (see 3.4: a maturity concept, not a
design sequence).

**Career ROI.** Does it develop or demonstrate a transferable competency in:
Systems Engineering / Architecture; AI data-center power distribution; power-conversion
architecture; controls and integration; protection and reliability; system validation;
technical trade studies?

## 7. Current vs. Planned Capabilities

Verified from the working tree on the date above.

| Capability | State | Where |
|---|---|---|
| Learning-first home page | Implemented (uncommitted) | `/` |
| System Map: 10 infrastructure categories × 3 architectures, plus the simulated slice | Implemented (uncommitted) | `/system-map` |
| Advanced Sandbox: five scenarios, telemetry, protection timeline/coordination, scenario comparison, sensitivity study | Implemented | `/sandbox` |
| Validated simulation engine (grid → SST → 800 VDC bus → AI load; PI control, thermal, protection) | Implemented, preserved | `src/`, `scenarios/`, `backend/` |
| Industry knowledge base (sourced, verified/sample flagged) | Data and Streamlit page only; **no Next.js route or API** | `data/industry/`, `dashboard/pages/industry.py` |
| Learn content (4 levels, YAML) | Streamlit only | `content/learn/` |
| Architecture Choices as a dedicated area | **Not implemented** (nav entry disabled; comparison exists only inside System Map) | — |
| Learn by Example as guided explanations | **Not implemented** (scenarios exist only inside the Sandbox) | — |
| Requirements and Engineering Judgment content | **Not implemented as content**; by decision they will live inside the four areas, not on their own pages | — |
| Streamlit dashboard | Legacy; reference/maintenance only | `dashboard/`, `app.py` |
| PEOS | Maintenance Mode | `peos/`, `bin/peos` |

## 8. Scope Boundaries

**Preserve:** the validated Python simulation engine and the existing Next.js interface.

**Maintenance only:** PEOS (no new orchestration capability); legacy Streamlit (reference
and maintenance until an explicit retirement decision).

**Not in scope:** research-grade or switching-level simulation; device-level SiC/GaN
models; machine learning; cloud infrastructure; paid APIs; Docker/Kubernetes; any added
framework not clearly necessary (`CLAUDE.md` Out of Scope list is unchanged).

**Avoid:** feature accumulation, redundant documentation, excessive tests, and premature
architecture complexity. Prefer deleting complexity to adding it.

## 9. Content-Evaluation Rubric

**Optional review guidance.** It helps judge whether a page teaches a coherent engineering
concept and contributes to an engineering decision. It is not a CI gate, not a deletion
trigger, and not a required process step. It adds no approvals, automation, or documentation.

**Two kinds of content.**
- **Core lessons** must build engineering judgment; criteria 1–6 should be clearly met.
- **Supporting reference content** (for example a glossary-style or category-description
  section) may serve a narrower educational purpose. It need not meet criterion 5 on its own,
  but should not contradict the lessons it supports.

| # | Criterion |
|---|---|
| 1 | **Concept:** teaches one coherent engineering concept, not a collection of terms. |
| 2 | **What / why:** answers *what is it* and *why does it matter*. |
| 3 | **System link:** shows how it connects to the larger system and its interfaces. |
| 4 | **Trade-offs:** states constraints and trade-offs, not only benefits. |
| 5 | **Decision:** names the engineering decision the knowledge informs. |
| 6 | **Causality:** builds cause-and-effect, with no unexplained jargon. |
| 7 | **Evidence labeling:** distinguishes sourced facts, illustrative assumptions, model outputs, and emerging or uncertain claims (Section 5.1). |
| 8 | **Integrity:** no unsupported vendor/adoption claims; sources attributed. |
| 9 | **ROI:** can name its Product ROI and Career ROI contribution. |

A simple met / partly met / not met judgment is enough. Numerical scoring, if used at all,
is a reviewer's private aid; nothing in the repository depends on it.

## 10. Documentation Authority

| Document | Responsibility |
|---|---|
| `PROJECT_CHARTER.md` | Mission, scope, and project boundaries. |
| `docs/PRODUCT_BLUEPRINT.md` (this file) | Learning architecture, narrative, and content-quality principles. |
| `DESIGN.md` | Visual and interaction design. |
| `README.md` | The current repository and setup. Describes what is, not what should be. |
| `docs/specifications/` (SPECs) | Bounded technical implementation. |
| `CLAUDE.md`, `AGENTS.md`, `ENGINEERING.md` | Execution and engineering-workflow rules (modeling, scope, integrity, roles, process). |

A document may not silently contradict another on that other's subject; report the conflict
instead. Conversation history never overrides a repository artifact.

Until integration is complete, these documents may not yet reflect this Blueprint. That is
tracked in Section 11, not corrected here.

## 11. Decisions and Contradictions

### 11.1 Approved decisions awaiting propagation

The decision is made. The listed documents or code have not yet caught up. Propagation is
separate work, not reopened here.

| Decision | Not yet reflected in |
|---|---|
| Four product areas, five learning stages (Section 3). Requirements and Engineering Judgment need no pages or nav items. | Home page and nav (four-area framing is correct, but copy and any "stage" language should be checked); `docs/reboot/REBOOT_ARCHITECTURE.md`; `README.md` |
| Industry & Career is both a destination and cross-cutting context. | Home page and nav treat it only as a planned fourth card. No Next.js route yet. |
| Learning sequence is pedagogical, distinct from the iterative engineering workflow. | Wherever the Observe → … → Architecture ladder is presented as a chronological process (`PROJECT_CHARTER.md` §5–§6 should be read as capability maturity). |
| Evidence categories and section-level labeling (Section 5.1). | System Map and Sandbox copy; not yet audited against it. |
| Document responsibilities (Section 10). | `PROJECT_CHARTER.md` §9 hierarchy; `ENGINEERING.md` charter pointer. |
| Rubric is optional guidance, not a gate. | Nothing to change; recorded so it is not later turned into one. |
| Streamlit is legacy reference/maintenance; PEOS is Maintenance Mode. | `README.md` still presents Streamlit as the platform. `DESIGN.md` (uncommitted edit) already names Next.js as the reference. |
| Stale statements to correct when each document is next edited. | `README.md` (Streamlit-only); `PROJECT_CHARTER.md` §11 (SPEC-010 "not implemented"). |

### 11.2 Genuine unresolved decisions

These need a human decision. Not decided by this Blueprint.

1. **Charter mission wording.** `PROJECT_CHARTER.md` §1 and `CLAUDE.md` Purpose describe an
   "educational digital twin." Section 1 states a learning-first mission. The charter owns
   mission and scope, so whether and how the charter text is amended is open.
2. **Audience wording.** The home page and `docs/reboot/` say "executive-level" or "personal,
   career-oriented" understanding. Section 2 and 1 say systems-level reasoning and
   architecture judgment. Which phrasing the product uses publicly is open.
3. **Streamlit retirement.** No retirement decision or date exists.
4. **Status of `docs/reboot/` and uncommitted work.** `docs/reboot/` (untracked) predates this
   Blueprint and proposes a different mission statement and navigation target. Whether it is
   superseded, committed as history, or revised is open.
5. **System Map architecture naming.** The approved comparison is conventional AC,
   transitional 800 VDC, and conceptual SST-based. The three System Map views are labeled
   `conventional-ac` and two others; whether their labels and framing match this naming has
   not been confirmed.
