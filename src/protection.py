"""Thermal protection / operating-state machine.

Scope
-----
V1 protection is driven by the single lumped SST temperature from
src/thermal.py. It is intentionally small: three states, one trip
cause. Bus-voltage and grid-availability protection are NOT
implemented here -- V1 deliberately limits protection scope rather
than building a general relay model (see README "Key Design
Decisions" #7).

States
------
    RUNNING  -- temperature below the derating threshold; full rated
                power available (derate_factor = 1.0).
    DERATED  -- temperature between the derating and trip thresholds;
                available power is linearly reduced.
    TRIPPED  -- temperature has stayed at/above the trip threshold for
                at least thermal_trip_time_s; SST output is forced to
                zero (derate_factor = 0.0). TRIPPED is LATCHED: V1 has
                no automatic reset. This is a deliberate simplification
                (Category B) -- see Limitations.

Derating relationship (Category B: engineering modeling assumption)
---------------------------------------------------------------------
For T in [thermal_derate_start_c, thermal_trip_c], derate_factor drops
linearly from 1.0 to derate_factor_min:

    derate_factor(T) = 1 - (1 - derate_factor_min) *
                           (T - derate_start_c) / (trip_c - derate_start_c)

P_available_max = rated_power_w * derate_factor

This linear relationship is an illustrative educational choice, not a
manufacturer derating curve.

Debounce / latching (Category C: illustrative educational parameters)
-----------------------------------------------------------------------
A single sample at or above thermal_trip_c does not immediately trip.
An internal timer accumulates time spent at/above thermal_trip_c; only
once that timer reaches thermal_trip_time_s does the state latch to
TRIPPED. The timer resets to zero whenever T drops back below
thermal_trip_c (so only a SUSTAINED overtemperature condition can
trip it).

Limitations
-----------
- No reset mechanism: once TRIPPED, the state stays TRIPPED for the
  rest of the scenario. A real protection system would have an
  operator- or logic-driven reset; V1 omits this because no scenario
  requires recovering from a trip mid-run, and adding reset logic
  without a scenario to exercise it would be speculative generality.
- Only one trip cause (sustained overtemperature). DC bus over/under-
  voltage protection is a reasonable future addition (see README
  Future Work) but is intentionally out of scope here.
- Debounce uses a simple elapsed-time accumulator, not a realistic
  relay/contactor model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OperatingState(Enum):
    RUNNING = "RUNNING"
    DERATED = "DERATED"
    TRIPPED = "TRIPPED"


@dataclass
class ProtectionState:
    """Mutable protection state carried between simulation steps."""

    operating_state: OperatingState = OperatingState.RUNNING
    derate_factor: float = 1.0
    trip_active: bool = False
    trip_reason: str = ""
    _overtemperature_timer_s: float = 0.0


def compute_derate_factor(
    temperature_c: float,
    thermal_derate_start_c: float,
    thermal_trip_c: float,
    derate_factor_min: float,
) -> float:
    """Linear derate factor in [derate_factor_min, 1.0] from temperature.

    Returns 1.0 below thermal_derate_start_c, derate_factor_min at or
    above thermal_trip_c, and a linear ramp between the two.
    """
    if temperature_c <= thermal_derate_start_c:
        return 1.0
    if temperature_c >= thermal_trip_c:
        return derate_factor_min
    span_c = thermal_trip_c - thermal_derate_start_c
    fraction = (temperature_c - thermal_derate_start_c) / span_c
    return 1.0 - (1.0 - derate_factor_min) * fraction


def step_protection(
    state: ProtectionState,
    temperature_c: float,
    dt_s: float,
    thermal_derate_start_c: float,
    thermal_trip_c: float,
    thermal_trip_time_s: float,
    derate_factor_min: float,
) -> tuple[OperatingState, float, bool, str]:
    """Advance the protection state machine by one step.

    Args:
        state: protection state; mutated in place.
        temperature_c: representative SST temperature for this step [degC]
            (the freshly-integrated value -- see src/simulation.py for why
            protection is evaluated after thermal integration).
        dt_s: integration timestep [s].
        thermal_derate_start_c: temperature at which derating begins [degC].
        thermal_trip_c: temperature at/above which the trip timer runs [degC].
        thermal_trip_time_s: required sustained duration above
            thermal_trip_c before latching TRIPPED [s].
        derate_factor_min: derate factor at/above thermal_trip_c, before
            a trip latches [-], in [0, 1].

    Returns:
        (operating_state, derate_factor, trip_active, trip_reason).
    """
    if state.operating_state is OperatingState.TRIPPED:
        # Latched: no reset mechanism in V1 (see module docstring).
        return (
            state.operating_state,
            state.derate_factor,
            state.trip_active,
            state.trip_reason,
        )

    if temperature_c >= thermal_trip_c:
        state._overtemperature_timer_s += dt_s
    else:
        state._overtemperature_timer_s = 0.0

    if state._overtemperature_timer_s >= thermal_trip_time_s:
        state.operating_state = OperatingState.TRIPPED
        state.derate_factor = 0.0
        state.trip_active = True
        state.trip_reason = "sustained_overtemperature"
        return (
            state.operating_state,
            state.derate_factor,
            state.trip_active,
            state.trip_reason,
        )

    state.derate_factor = compute_derate_factor(
        temperature_c, thermal_derate_start_c, thermal_trip_c, derate_factor_min
    )
    state.operating_state = (
        OperatingState.DERATED
        if temperature_c > thermal_derate_start_c
        else OperatingState.RUNNING
    )
    state.trip_active = False
    state.trip_reason = ""

    return state.operating_state, state.derate_factor, state.trip_active, state.trip_reason
