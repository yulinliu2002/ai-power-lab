"""AI data-center load model.

V1 Phase 1 represents the AI load purely as an exogenous power demand
P_load(t) -- there is no server- or transistor-level simulation, and
no internal state or dynamics of the load itself.

Governing relationship
-----------------------
P_load(t) = load_fraction(t) * rated_power_w

This is a Category C (arbitrary educational) profile definition, not
a physics-derived relationship -- it exists to exercise the electrical
core (controller, SST, DC bus), not to represent any real workload's
statistics.

Assumptions
-----------
- The load is an ideal power sink: it draws exactly P_load(t) from the
  bus regardless of bus voltage (no current-limiting or constant-
  impedance behavior).
- Load transitions in this step profile are instantaneous steps in
  commanded power, not ramped -- the "finite response time" visible at
  the bus is entirely a consequence of the SST and DC-bus dynamics,
  not a load-side filter.

Limitations
-----------
- No representation of real AI workload burstiness, duty cycling, or
  power-factor/harmonic behavior.
- A step profile is the only load archetype implemented in Phase 1;
  ramps, bursts, and repeating profiles are left to later phases if
  needed.
"""

from __future__ import annotations

from typing import Callable


def step_load_power_w(
    t_s: float,
    rated_power_w: float,
    initial_fraction: float,
    final_fraction: float,
    step_time_s: float,
) -> float:
    """Evaluate a single-step load power profile at time t_s.

    Args:
        t_s: simulation time [s].
        rated_power_w: load rated power [W], used to scale fractions.
        initial_fraction: load fraction [-] before the step (e.g. 0.4).
        final_fraction: load fraction [-] after the step (e.g. 0.8).
        step_time_s: time at which the step occurs [s].

    Returns:
        P_load(t_s) [W].
    """
    fraction = final_fraction if t_s >= step_time_s else initial_fraction
    return fraction * rated_power_w


def make_step_load_profile(
    rated_power_w: float,
    initial_fraction: float,
    final_fraction: float,
    step_time_s: float,
) -> Callable[[float], float]:
    """Build a P_load(t) callable for a single-step load profile.

    Convenience wrapper so scenario code can pass a single function to
    the simulation loop instead of threading the four parameters
    through separately.
    """

    def profile(t_s: float) -> float:
        return step_load_power_w(
            t_s, rated_power_w, initial_fraction, final_fraction, step_time_s
        )

    return profile
