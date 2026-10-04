"""800 VDC bus model using stored capacitor energy as the integrated state.

Governing equations
--------------------
Capacitor stored energy:
    E_dc = 0.5 * C_dc * V_dc^2                         [J]

Power balance (energy form, physics-derived):
    dE_dc/dt = P_sst - P_load                          [W]

Voltage is recovered algebraically from the integrated energy:
    V_dc = sqrt(2 * E_dc / C_dc)                        [V]

Why integrate energy instead of voltage
----------------------------------------
The equivalent voltage-form ODE,
    dV_dc/dt = (P_sst - P_load) / (C_dc * V_dc),
has a 1/V_dc singularity: as V_dc -> 0 the derivative diverges, which
is both numerically unstable and nonphysical. Integrating E_dc avoids
this entirely -- dE_dc/dt is a plain power balance with no division by
a state variable -- and V_dc is then recovered from a simple, always
well-defined square root.

Numerical floor
----------------
min_energy_j is a NUMERICAL SAFETY NET, not a physical limit. It
exists only to keep the explicit-Euler integrator from producing a
negative E_dc (and therefore an imaginary voltage) if a single step
would otherwise overshoot past zero stored energy. In a properly
configured system this floor should never be reached in practice --
protection logic (added in a later phase) is expected to trip the
SST at a much higher undervoltage threshold, long before stored
energy approaches zero.

Assumptions
-----------
- The DC bus is represented as a single lumped capacitance -- no
  cabling impedance, no distributed capacitance, no AC ripple.
- P_sst and P_load are both bus-referenced (power entering/leaving the
  capacitor node), consistent with the SST's output-referenced
  convention (see sst.py).

Limitations
-----------
- Cannot represent voltage ripple, transient current sharing between
  multiple sources/loads, or any sub-timestep electrical dynamics.
- The energy floor is a numerical artifact; if it is ever hit during a
  simulation run, that indicates a configuration or protection-timing
  issue, not a normal operating mode.
"""

from __future__ import annotations

import math


def energy_from_voltage(v_dc_v: float, capacitance_f: float) -> float:
    """Compute stored capacitor energy from voltage: E = 0.5 * C * V^2.

    Used only for initialization (converting a configured initial
    voltage into the integrated energy state).
    """
    return 0.5 * capacitance_f * v_dc_v**2


def voltage_from_energy(e_dc_j: float, capacitance_f: float) -> float:
    """Recover bus voltage from stored energy: V = sqrt(2E / C).

    Args:
        e_dc_j: stored capacitor energy [J]. Must be non-negative.
        capacitance_f: DC-link capacitance [F].

    Returns:
        Bus voltage [V].
    """
    return math.sqrt(2.0 * e_dc_j / capacitance_f)


def step_dc_bus_energy(
    e_dc_j: float,
    p_sst_w: float,
    p_load_w: float,
    dt_s: float,
    min_energy_j: float,
) -> float:
    """Advance stored DC-bus energy by one explicit-Euler step.

    Implements: E_dc[k+1] = E_dc[k] + dt * (P_sst[k] - P_load[k]),
    clamped below at min_energy_j (see module docstring).

    Args:
        e_dc_j: current stored energy [J].
        p_sst_w: power delivered to the bus by the SST [W].
        p_load_w: power drawn from the bus by the AI load [W].
        dt_s: integration timestep [s].
        min_energy_j: numerical floor on stored energy [J].

    Returns:
        Updated stored energy [J], floored at min_energy_j.
    """
    d_e_dt = p_sst_w - p_load_w
    e_next = e_dc_j + dt_s * d_e_dt
    return max(e_next, min_energy_j)
