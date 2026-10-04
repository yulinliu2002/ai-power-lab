# AI Power Lab: SST Digital Twin

An educational, system-level digital twin of an SST-powered 800 VDC AI
data-center power architecture.

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
├── config/
│   └── default.yaml           # every engineering parameter, with units
├── src/
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
├── scenarios/
│   ├── plotting.py               # shared matplotlib helpers
│   ├── load_step.py              # Scenario A
│   ├── sustained_high_load.py    # Scenario B
│   ├── thermal_trip.py           # Scenario C
│   ├── grid_sag.py               # Scenario D
│   └── grid_loss.py              # Scenario E
├── tests/                       # one test module per physics/logic module
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
