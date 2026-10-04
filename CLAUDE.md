# AI Power Lab

An educational, system-level digital twin of an SST-powered 800 VDC AI data center.

This file defines the permanent rules for working in this repository. These rules apply to every change, every subsystem, and every future conversation. Follow them without needing to be reminded.

## Purpose

The primary goal of this project is **engineering learning**, not maximum software complexity. Every design decision should favor physical understanding and interpretability over sophistication, abstraction, or feature count. If a simpler model teaches the same lesson, prefer it.

The user must be able to **personally explain every major subsystem** in this repository. Do not introduce code, models, or abstractions that would prevent that.

## Modeling Rules

- Use **simple, physically interpretable models**. Prefer lumped-parameter, first-principles formulations over black-box or high-fidelity models.
- **Every major model must document**:
  - Its **governing equation(s)**
  - The **units** of every input, state, and output
  - The **assumptions** it relies on (steady-state vs. dynamic, linearization, idealizations, neglected effects)
  - Its **limitations** (regime of validity, what it cannot represent)
- Use **SI units internally** throughout the codebase. Any unit conversion must happen at I/O boundaries (config loading, telemetry display) and be explicit.
- **Engineering parameters belong in config files**, not hardcoded in source. This includes ratings, gains, time constants, thermal properties, bus voltages, trip thresholds, and fault parameters.
- Before implementing a new engineering subsystem, **explain the physics and governing equations first** in prose or a short design note, and get alignment. Do not jump into code.

## V1 Scope

V1 covers the end-to-end chain:

**Grid → simplified SST → 800 VDC bus → dynamic AI load**

Including:
- PI control loops
- Thermal behavior (lumped thermal models)
- Protection logic
- Fault scenarios
- Telemetry
- Visualization

Anything outside this chain is out of scope for V1.

## Out of Scope (do not add without explicit approval)

- Switching-level semiconductor simulation
- Detailed SiC / GaN device models
- Machine learning of any kind
- Cloud infrastructure
- Paid APIs
- Docker
- Kubernetes
- Any additional framework, library, or abstraction layer that is not clearly necessary

Do not expand project scope automatically. If a task seems to require something out of scope, stop and ask.

## Code Style

- **Python** with type hints and docstrings.
- **Small modules** with clear single responsibilities.
- **Tests** for every non-trivial model and control loop.
- Readability over cleverness. A junior engineer should be able to read and understand each module.
- No premature abstractions, no speculative generality, no frameworks "just in case."

## Integrity Rules

- **Never request or use proprietary information** from Amperesand or any current/former employer.
- Use **only public engineering principles** (textbooks, published papers, standards, open datasheets).
- Any numerical values, topologies, or assumptions that are not from a public source must be **clearly labeled as educational assumptions**.

## Working Agreement

- Do not expand scope on your own initiative.
- When in doubt about whether something fits the rules above, ask before implementing.
- Prefer deleting complexity over adding it.
- If a proposed change would make a subsystem harder for the user to personally explain, flag it.
