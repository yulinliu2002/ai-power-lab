# AI Power Lab

A system-level simulation and visualization platform for learning how
an SST-powered 800 VDC AI data-center power architecture behaves,
end-to-end -- electrically, thermally, and under protection logic. It
is best described as an **educational digital-twin framework**: it is
not calibrated to any specific commercial SST, and makes no claim to
hardware-design-validation fidelity.

## V1.1: Platform Overview

V1.0 (tagged `v1.0.0`) delivered the validated simulation engine. V1.1
wraps that engine in an interactive Streamlit dashboard -- the engine
and physics are unchanged; see "What Is Currently Modeled" below.

**What AI Power Lab is.** An interactive platform connecting theory
(the Learn section), system architecture/simulation (this project's own
SST + 800 VDC bus + AI load model), and real industry development
(curated, sourced public records) for solid-state-transformer-powered,
800 VDC AI data-center power.

**Why SST + 800 VDC matter.** Public industry sources (NVIDIA, the Open
Compute Project) describe an industry shift toward centralized power
conversion and 800 VDC distribution for high-density AI racks, aimed at
reducing the number of conversion stages between the grid and the
compute load. See the **AI Data Center** and **Industry** dashboard
pages for sourced detail -- this project does not invent or claim any
performance numbers beyond what's attributed to a public source there.

**What can be demonstrated.**
- The five V1 scenarios (A-E below), run interactively with
  user-adjustable parameters (load levels, timing, SST rating, voltage
  reference) and live Plotly plots, instead of only static
  pre-generated PNGs.
- The full causal chain for the flagship **AI Load Step** demo: load
  increase &rarr; power deficit &rarr; bus energy/voltage sag &rarr; PI
  controller response &rarr; SST power recovery &rarr; bus recovery.
- A **Learn** section connecting each Level 1-3 topic directly to the
  demo that exercises it ("Try it in Simulator").
- A curated, sourced **Industry Intelligence** knowledge base
  distinguishing commercial products, industry architecture/standards
  work, and research.

**How to run the dashboard:**
```bash
source .venv/bin/activate      # or create one -- see "Running the Project" below
pip install -r requirements.txt
streamlit run app.py
```

**What is currently modeled** vs. **what is not** is unchanged from
V1.0 and detailed fully below (Modeling Scope, Limitations) -- the
dashboard adds no new physics. In particular: average-value SST only
(no switching/semiconductor/PWM/MFT physics), thermal-only protection
(no voltage protection), and no AC power flow.

**What the Learning Platform contains:** four priority levels -- Level
1 System Architecture + Controls (power flow, energy balance, DC bus,
dynamic load, voltage regulation, PI control, transient response),
Level 2 SST Power-Electronics Architecture (conceptual only -- AFE, DC
link, isolated DC/DC, MFT, modular conversion -- explicitly NOT
simulated), Level 3 System Behavior (efficiency/loss, thermal dynamics,
derating, protection, grid sag, grid loss -- mapped directly onto
existing modules), and Level 4 Future Deep Dives (roadmap placeholders
only: SiC/GaN, switching/modulation, MFT electromagnetics, EMI,
detailed semiconductor loss, detailed control loops).

**What Industry Intelligence does:** reads a curated, local YAML
knowledge base (`data/industry/*.yaml`) -- no scraping, no live
browsing from the app. Every record is either `status: verified` (with
a real public source) or `status: sample` (an explicit placeholder,
never confused for a verified record), and every record carries a
`maturity` label (`commercial_product` / `architecture_standard` /
`research`) so the UI always visually separates the three. Initial
seeds: NVIDIA's public 800 VDC architecture description, the Open
Compute Project's 800 VDC/LVDC standardization work (including "SST
Specification v0.3"), and Eaton's publicly listed medium-voltage SST
product (15 kV class, 2 MW, >97% efficiency at 800 VDC output,
liquid-cooled).

**Roadmap (not implemented in V1.1):** an Architecture Comparison
Simulator (traditional vs. emerging AI data-center power architecture);
deeper Level 2/4 content; load- and temperature-dependent SST
efficiency; a real weekly industry-update cadence (curated by hand,
still no scraping); DC-bus over/undervoltage protection. See "Future
Work" at the end of this document for the full V1.0-era list, which
remains valid.

## Purpose

This project is a learning tool: a simplified, system-level model, not
a calibrated model of any specific commercial SST and not a product
design. It exists to demonstrate, with simple and fully interpretable
physics, how an AI data center's power chain actually behaves
end-to-end:

> AI workload changes → DC power demand changes → DC-link stored
> energy changes → 800 VDC bus voltage responds → a PI controller
> changes the SST power command → SST power responds with finite
> dynamics → conversion losses generate heat → a thermal state evolves
> → protection can derate or trip the SST → power availability changes
> → the DC bus responds naturally through energy balance.

Every model here is a deliberately simplified, lumped-parameter,
first-principles representation. Nothing in this repository is
derived from, or intended to represent, any real commercial SST,
proprietary control algorithm, or manufacturer specification.

## System Architecture

```
Grid ──────────────────────────┐
 (grid_voltage_pu,              │ grid_power_availability_factor
  grid_available)               ▼
                         ┌───────────────┐        P_sst       ┌─────────────┐      P_load     ┌──────────┐
  P_target  ────────────▶│      SST      │───────────────────▶│   800 VDC   │◀────────────────│  AI Load │
  (saturated by           │ (1st-order    │                    │     Bus     │                 │  (power  │
   derate_factor &        │  power lag)   │                    │ (E_dc state)│                 │   sink)  │
   grid availability)     └───────┬───────┘                    └──────┬──────┘                 └──────────┘
                                  │ P_loss = P_in - P_sst               │ V_dc
                                  ▼                                     │
                          ┌───────────────┐                            │
                          │ Thermal Model │                            │
                          │ (lumped RC)   │                            │
                          └───────┬───────┘                            │
                                  │ T                                  │
                                  ▼                                     │
                          ┌───────────────┐    derate_factor,          │
                          │  Protection / │    operating_state         │
                          │ State Machine │───────────────────┐        │
                          └───────────────┘                   │        │
                                                               ▼        ▼
                                                        ┌─────────────────────┐
                                                        │   PI Controller     │◀── V_ref
                                                        │ P_cmd = P_ff + Kp*e │
                                                        │        + Ki*∫e dt   │
                                                        └─────────────────────┘
```

Power/energy flows left-to-right (Grid → SST → Bus → Load). Feedback
flows right-to-left: `V_dc` drives the PI controller, which commands
`P_target` into the SST; `P_loss` drives the thermal model, which
drives protection, which limits how much power the SST is ever allowed
to attempt.

## Core Equations

**DC bus (physics-derived):**
```
E_dc = 0.5 * C_dc * V_dc^2
dE_dc/dt = P_sst - P_load
V_dc = sqrt(2 * E_dc / C_dc)
```
Energy, not voltage, is the integrated state — `dV_dc/dt` has a
`1/V_dc` singularity near zero that the energy form avoids entirely.

**SST (engineering modeling assumption — average-value, not switching):**
```
dP_sst/dt = (P_target - P_sst) / tau_sst
P_in = P_sst / efficiency
P_loss = P_in - P_sst
```
`P_sst` is **output-referenced**: the power delivered to the DC bus,
not drawn from the grid.

**Thermal (lumped single-node model):**
```
C_th * dT/dt = P_loss - (T - T_ambient) / R_th
T_ss = T_ambient + R_th * P_loss        (steady-state, dT/dt = 0)
```
`T` is a generic aggregate SST temperature, not a junction, case, or
heatsink temperature of any real device.

**PI voltage controller with load feedforward:**
```
e = V_ref - V_dc
P_cmd = P_load + Kp * e + Ki * ∫e dt
```
`Kp` has units of W/V; `Ki` has units of W/(V·s); the integrator state
is carried in V·s. Saturation and simple conditional-integration
anti-windup are applied (see `src/controller.py`).

## Modeling Scope

- **Average-value SST model only** — no switching-level semiconductor
  simulation, no PWM, no individual device behavior.
- **No proprietary commercial SST data** of any kind.
- **Illustrative educational parameters throughout** — every number in
  `config/default.yaml` that isn't a textbook physical relationship is
  explicitly labeled as such (see Modeling Assumption Categories below).
- **System-level behavior, not hardware design validation.** This
  project demonstrates *how the pieces interact*, not whether any
  particular SST design is sound.

## Modeling Assumption Categories & Key Design Decisions

Every non-trivial parameter or relationship in this project falls into
one of three categories, labeled as such in `config/default.yaml` and
in module docstrings:

- **A — Physics-derived.** A direct consequence of a governing physical
  law, not a choice (e.g. `E = 0.5*C*V^2`, `dE/dt = P_in - P_out`, the
  thermal energy balance).
- **B — Engineering modeling assumption.** A deliberate simplification
  of real behavior — standard practice for a system-level model, but
  not itself derived from first principles (e.g. the average-value SST
  response, constant efficiency, the linear grid-availability and
  thermal-derate relationships).
- **C — Arbitrary educational parameter.** A specific numeric value
  chosen for this demo (ratings, gains, thermal constants, protection
  thresholds) with no claim to represent any real commercial product.

A handful of design decisions in this codebase are non-obvious enough
to be worth stating once, here, rather than scattering the reasoning
across comments:

1. **The DC bus integrates stored energy, not voltage.**
   `dV_dc/dt = (P_sst - P_load) / (C_dc * V_dc)` has a `1/V_dc`
   singularity near zero. Integrating `E_dc` and recovering
   `V_dc = sqrt(2*E_dc/C_dc)` avoids that singularity entirely — see
   `src/dc_bus.py`.
2. **`P_sst` is defined as bus-side (output) delivered power**, not
   grid-side input power. This keeps the DC-bus balance
   (`dE/dt = P_sst - P_load`) free of any embedded efficiency term;
   efficiency enters exactly once, in `P_in = P_sst / efficiency`.
3. **Protection only ever limits power availability — it never edits
   `V_dc` or `E_dc` directly.** `derate_factor` and grid availability
   scale `P_available_max`, which saturates the controller's command;
   the bus always evolves solely through `dE_dc/dt = P_sst - P_load`.
   Enforced by `tests/test_thermal_protection_simulation.py::
   test_protection_affects_plant_only_through_power_availability`.
4. **PI gains (`Kp=2000 W/V`, `Ki=1500 W/(V*s)`) came from a small
   empirical sweep, not formal loop-shaping.** A loop-shaped design
   that ignored the SST's 20 ms lag put closed-loop bandwidth too close
   to that lag and rang continuously once the lag was included; these
   gains settle within 1-2 cycles instead. A fully non-oscillatory
   design was not pursued — it needs gains an order of magnitude lower
   and pushes settling out several hundred ms, which is over-tuned for
   this project's purposes.
5. **Timestep is chosen per scenario from the fastest relevant
   dynamic, not fixed globally.** Electrical scenarios use
   `dt=1e-4 s` (<< `tau_sst=20 ms`). Long thermal scenarios (B, C) use
   `dt=1e-3 s` for speed. `dt=1e-2 s` was tested directly and found to
   destabilize the closed-loop PI+SST+bus interaction into a sustained
   limit cycle — despite the thermal time constant being 1500x slower,
   it is the fast electrical loop that sets the stability limit.
6. **`protection.derate_factor_min=0.5` was chosen by direct
   simulation**, so that a sustained load below the derated-floor cap
   self-stabilizes safely (Scenario B), while a load that saturates
   against that cap converges to a steady-state loss that keeps
   temperature at/above the trip threshold indefinitely, guaranteeing a
   genuine trip rather than a last-second self-rescue (Scenario C). A
   lower value (e.g. 0.2) cools enough to self-stabilize under any
   sustained load, demonstrating only derating and never a trip.
7. **Protection scope is deliberately limited to sustained
   overtemperature detection** (one lumped temperature driving
   RUNNING/DERATED/TRIPPED). DC-bus over/undervoltage protection was
   considered and intentionally left out of V1 to keep the state
   machine small; see Limitations and Future Work.

## Scenarios

| Scenario | File | What it shows |
|---|---|---|
| **A — AI load step** | `scenarios/load_step.py` | 40% → 80% rated load step from a proper steady-state start: bus sag, PI controller response, SST power response with finite dynamics, bus recovery. The core electrical-transient demo. |
| **B — Sustained high load** | `scenarios/sustained_high_load.py` | A constant 200 kW demand (below the derated-floor cap) held for 200 s: electrical loading → conversion loss → gradual temperature rise → mild derating that safely self-stabilizes, with the load always fully met. |
| **C — Thermal derating / trip** | `scenarios/thermal_trip.py` | A constant 450 kW overload held for 90 s: thermal accumulation → derating → the now-reduced SST power can no longer meet demand → the DC bus sags *through the existing energy balance, never forced* → sustained overtemperature → TRIPPED. |
| **D — Grid sag** | `scenarios/grid_sag.py` | A 0.5 p.u. grid voltage sag for 200 ms: reduced SST available power → bus droop → clean recovery once the grid returns to nominal. |
| **E — Grid loss** | `scenarios/grid_loss.py` | The grid becomes unavailable and stays down: SST target power is driven to zero, SST power decays per its existing first-order dynamics, and the bus discharges per the existing energy balance. |

Scenarios only ever change *external* inputs (load demand, grid
condition) — they never reach into internal physical states directly.

## Results

Running each scenario (see **Running the Project** below) regenerates
its plots under `results/`. Headline numbers from this project's own
validation run:

- **Scenario A:** voltage dips to ~714 V and recovers to ~801 V within
  roughly 100 ms of the load step, with SST power visibly lagging the
  commanded target.
- **Scenario B:** temperature rises smoothly from 25°C to ~86.8°C
  (derated to ~72% of rated power) over ~150 s and stays there — no
  trip, no voltage deviation, load always fully met.
- **Scenario C:** ~11 s of healthy operation, then derating begins;
  once the derated cap drops below the 450 kW demand the bus collapses
  within seconds (via `dE_dc/dt = P_sst - P_load`, not a forced
  voltage); temperature continues past the 100°C trip threshold and
  the system latches TRIPPED at ~46 s.
- **Scenario D:** the bus droops sharply during the 200 ms sag (and
  briefly touches the numerical energy floor — see Limitations) but
  recovers cleanly to ~800 V within ~0.3 s of the grid returning.
- **Scenario E:** the bus collapses to the numerical floor within
  ~40 ms of losing the grid, tracking the SST's own decay dynamics.

## Repository Structure

```
ai-power-lab/
├── README.md
├── CLAUDE.md                 # permanent project rules
├── requirements.txt
├── conftest.py                # lets tests/scenarios import `src` as a package
├── app.py                      # Streamlit entry point -- streamlit run app.py
├── config/
│   └── default.yaml           # every engineering parameter, with units
├── src/                        # the V1 simulation engine (unchanged by V1.1)
│   ├── config.py               # YAML -> validated, typed dataclasses
│   ├── grid.py                 # exogenous grid_voltage_pu / grid_available model
│   ├── load.py                 # AI load power profile (step function)
│   ├── sst.py                  # average-value SST power + loss model
│   ├── dc_bus.py                # DC-link energy-state model
│   ├── controller.py            # PI voltage controller + feedforward
│   ├── thermal.py               # lumped single-node thermal model
│   ├── protection.py            # RUNNING / DERATED / TRIPPED state machine
│   ├── telemetry.py             # Telemetry container + CSV export
│   └── simulation.py            # the full per-step update loop
├── scenarios/                   # the five V1 scenarios (static matplotlib + CSV)
│   ├── plotting.py               # shared matplotlib helpers
│   ├── load_step.py              # Scenario A
│   ├── sustained_high_load.py    # Scenario B
│   ├── thermal_trip.py           # Scenario C
│   ├── grid_sag.py               # Scenario D
│   └── grid_loss.py              # Scenario E
├── dashboard/                    # V1.1 Streamlit platform
│   ├── adapters/                  # thin bridge from src/scenarios to the UI -- no physics here
│   │   ├── simulation_adapter.py   # parameterized wrappers around src.simulation.run_simulation
│   │   ├── content_loader.py       # loads + validates content/learn/*.yaml
│   │   └── industry_data.py        # loads + validates data/industry/*.yaml
│   ├── components/                # reusable chart/diagram/metric widgets
│   │   ├── palette.py               # validated chart color palette
│   │   ├── plots.py                 # interactive Plotly versions of scenarios/plotting.py
│   │   ├── diagram.py               # reusable flow-diagram renderer
│   │   └── metrics.py               # summary-metric + state-badge display helpers
│   └── pages/                     # the five dashboard sections
│       ├── overview.py
│       ├── simulator.py
│       ├── learn.py
│       ├── ai_datacenter.py
│       └── industry.py
├── content/learn/                 # Learn-section topics (YAML, by priority level)
│   ├── level1_system.yaml
│   ├── level2_sst_architecture.yaml
│   ├── level3_system_behavior.yaml
│   └── level4_future.yaml
├── data/industry/                 # curated, sourced public industry-intelligence records
│   ├── companies.yaml
│   ├── products.yaml
│   ├── standards.yaml
│   ├── developments.yaml
│   ├── research.yaml
│   └── weekly_updates.yaml
├── tests/                       # one test module per physics/logic module, plus dashboard/content/industry-data tests
└── results/                      # generated plots and CSV telemetry (gitignored data, not code)
```

## Running the Project

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the test suite
python -m pytest -q

# Run any scenario (generates plots + a CSV under results/)
python -m scenarios.load_step
python -m scenarios.sustained_high_load
python -m scenarios.thermal_trip
python -m scenarios.grid_sag
python -m scenarios.grid_loss

# Launch the interactive dashboard (V1.1)
streamlit run app.py
```

## Limitations

- **Average-value converter model.** No switching ripple, inrush
  current, or sub-time-constant electrical behavior is represented.
- **Constant efficiency.** Real converters have load- and
  temperature-dependent efficiency curves; V1 uses one fixed number.
- **Lumped single-node thermal model.** One temperature, one time
  constant — no junction/case/heatsink distinction, and not a
  prediction of any real device's survival margins.
- **Simplified grid interaction.** `grid_voltage_pu` is a scalar
  per-unit signal with a linear, illustrative relationship to
  available SST power — no AC waveform, power factor, or real
  ride-through behavior.
- **Educational protection thresholds.** All derate/trip thresholds,
  debounce times, and the derate curve shape are illustrative
  (Category C) choices, not derived from any standard or product.
- **Small illustrative DC-link capacitance.** Chosen to keep Phase 1's
  electrical transients visible on human timescales; a side effect is
  that any sustained power deficit longer than roughly 100 ms fully
  drains the bus to the numerical energy floor (`min_energy_j` in
  `src/dc_bus.py`) rather than settling at some intermediate sagged
  voltage. Scenarios D and E both touch this floor briefly — it is
  called out explicitly where it appears and should never be read as
  a physically meaningful near-zero voltage.
- **No automatic trip reset.** `TRIPPED` latches for the rest of a
  scenario; V1 has no reset/restart logic.

## Future Work (not implemented — possible V2 directions)

- Load- and temperature-dependent efficiency curve instead of a
  constant.
- Multi-node thermal model (junction–case–ambient).
- More realistic AI load telemetry (bursty, duty-cycled workloads).
- Improved grid interaction (ride-through curves, reactive power).
- A lightweight dashboard for interactive scenario exploration.
- A hardware-in-the-loop concept for controller validation.
- Comparison of alternative controller designs (e.g. feedback
  linearization, model predictive control) against this PI baseline.

None of the above is implemented in V1.
