"""Grid condition model: exogenous grid_voltage_pu / grid_available signal.

V1 scope
--------
The grid is NOT modeled as an AC power-flow or electromagnetic system.
It is a simple exogenous signal pair -- grid_voltage_pu [-] and
grid_available [bool] -- that scenarios drive over time. The grid
exists here to support disturbance/protection scenarios, not to model
power flow. There is no internal state or dynamics here; grid
condition profiles are pure functions of time.

Grid -> available SST power relationship (Category B: engineering
modeling assumption)
---------------------------------------------------------------------
V1 uses the simplest physically-motivated relationship: available SST
power scales linearly with per-unit grid voltage, and drops to zero
whenever the grid is unavailable:

    availability_factor = 0.0                  if not grid_available
    availability_factor = clip(voltage_pu, 0, 1)  otherwise

This says, in effect, "a sagging grid can only source power in
proportion to its voltage" -- a reasonable first-order assumption, but
not a real converter's actual low-voltage-ride-through behavior, which
depends on topology and control design. It is explicitly NOT derived
from any commercial SST specification.

P_available_max = rated_power_w * derate_factor * availability_factor

combines this grid-availability limit with the thermal derate factor
from src/protection.py; see src/simulation.py for where the two are
multiplied together.

Limitations
-----------
- No fault ride-through dynamics, no reactive power/power-factor
  behavior, no three-phase imbalance -- grid_voltage_pu is a single
  scalar per-unit quantity.
- The linear availability relationship is illustrative; real SSTs may
  sustain full power well into a voltage sag (via increased current)
  up to a device current limit, which this model does not represent.
"""

from __future__ import annotations

from typing import Callable


def grid_power_availability_factor(grid_voltage_pu: float, grid_available: bool) -> float:
    """Fraction of rated SST power the grid can support right now.

    See module docstring for the governing assumption.
    """
    if not grid_available:
        return 0.0
    return max(0.0, min(grid_voltage_pu, 1.0))


def constant_grid_profile(nominal_voltage_pu: float = 1.0) -> Callable[[float], tuple[float, bool]]:
    """Grid profile with no disturbance: always nominal and available."""

    def profile(t_s: float) -> tuple[float, bool]:
        return nominal_voltage_pu, True

    return profile


def make_sag_profile(
    nominal_voltage_pu: float,
    sag_voltage_pu: float,
    sag_start_s: float,
    sag_duration_s: float,
) -> Callable[[float], tuple[float, bool]]:
    """Grid profile: nominal voltage, a temporary sag, then recovery.

    The grid remains available (grid_available = True) throughout --
    this represents a voltage sag, not an outage.

    Args:
        nominal_voltage_pu: voltage outside the sag window [-].
        sag_voltage_pu: voltage during the sag window [-].
        sag_start_s: time the sag begins [s].
        sag_duration_s: how long the sag lasts [s].
    """

    def profile(t_s: float) -> tuple[float, bool]:
        in_sag = sag_start_s <= t_s < sag_start_s + sag_duration_s
        voltage_pu = sag_voltage_pu if in_sag else nominal_voltage_pu
        return voltage_pu, True

    return profile


def make_outage_profile(
    nominal_voltage_pu: float,
    outage_start_s: float,
    outage_duration_s: float | None = None,
) -> Callable[[float], tuple[float, bool]]:
    """Grid profile: nominal, then an outage (voltage collapses, unavailable).

    Args:
        nominal_voltage_pu: voltage before the outage (and after
            recovery, if outage_duration_s is given) [-].
        outage_start_s: time the outage begins [s].
        outage_duration_s: outage duration [s]. If None, the grid stays
            down for the rest of the simulation.
    """

    def profile(t_s: float) -> tuple[float, bool]:
        in_outage = t_s >= outage_start_s and (
            outage_duration_s is None or t_s < outage_start_s + outage_duration_s
        )
        if in_outage:
            return 0.0, False
        return nominal_voltage_pu, True

    return profile
