"""Tests for the thermal protection / operating-state machine (src/protection.py)."""

from src.protection import (
    OperatingState,
    ProtectionState,
    compute_derate_factor,
    step_protection,
)

DERATE_START_C = 70.0
TRIP_C = 100.0
TRIP_TIME_S = 2.0
DERATE_MIN = 0.2
DT_S = 0.01


def _step(state, temperature_c, dt_s=DT_S):
    return step_protection(
        state, temperature_c, dt_s, DERATE_START_C, TRIP_C, TRIP_TIME_S, DERATE_MIN
    )


def test_compute_derate_factor_is_one_below_derate_start():
    assert compute_derate_factor(50.0, DERATE_START_C, TRIP_C, DERATE_MIN) == 1.0


def test_compute_derate_factor_is_minimum_at_or_above_trip():
    assert compute_derate_factor(TRIP_C, DERATE_START_C, TRIP_C, DERATE_MIN) == DERATE_MIN
    assert compute_derate_factor(150.0, DERATE_START_C, TRIP_C, DERATE_MIN) == DERATE_MIN


def test_compute_derate_factor_linear_at_midpoint():
    midpoint_c = (DERATE_START_C + TRIP_C) / 2.0
    expected = 1.0 - (1.0 - DERATE_MIN) * 0.5
    assert abs(compute_derate_factor(midpoint_c, DERATE_START_C, TRIP_C, DERATE_MIN) - expected) < 1e-9


def test_normal_operation_stays_running_no_trip():
    state = ProtectionState()
    for _ in range(1000):
        operating_state, derate_factor, trip_active, _ = _step(state, 40.0)
    assert operating_state is OperatingState.RUNNING
    assert derate_factor == 1.0
    assert trip_active is False


def test_entry_into_derated_region():
    state = ProtectionState()
    operating_state, derate_factor, trip_active, _ = _step(state, 85.0)
    assert operating_state is OperatingState.DERATED
    assert 0.0 < derate_factor < 1.0
    assert trip_active is False


def test_trip_after_sustained_overtemperature():
    state = ProtectionState()
    # Hold at trip temperature for longer than TRIP_TIME_S.
    n_steps = int(TRIP_TIME_S / DT_S) + 10
    for _ in range(n_steps):
        operating_state, derate_factor, trip_active, trip_reason = _step(state, 120.0)
    assert operating_state is OperatingState.TRIPPED
    assert derate_factor == 0.0
    assert trip_active is True
    assert trip_reason == "sustained_overtemperature"


def test_no_false_trip_from_short_transient():
    state = ProtectionState()
    # Spike above trip threshold for less than TRIP_TIME_S...
    short_spike_steps = int((TRIP_TIME_S / DT_S) / 2)
    for _ in range(short_spike_steps):
        operating_state, _, trip_active, _ = _step(state, 120.0)
    assert trip_active is False
    assert operating_state is not OperatingState.TRIPPED

    # ...then drop back into the derated region: should not be tripped,
    # and the overtemperature timer should have reset (not accumulated
    # across the gap).
    operating_state, _, trip_active, _ = _step(state, 85.0)
    assert trip_active is False
    assert operating_state is OperatingState.DERATED

    # Re-entering the trip region now needs the FULL debounce time again,
    # not just the remainder -- confirms the timer truly reset.
    for _ in range(short_spike_steps):
        operating_state, _, trip_active, _ = _step(state, 120.0)
    assert trip_active is False
    assert operating_state is not OperatingState.TRIPPED


def test_trip_is_latched_even_after_temperature_recovers():
    state = ProtectionState()
    n_steps = int(TRIP_TIME_S / DT_S) + 10
    for _ in range(n_steps):
        _step(state, 120.0)
    assert state.operating_state is OperatingState.TRIPPED

    # Temperature fully recovers to a cool, safe value...
    operating_state, derate_factor, trip_active, trip_reason = _step(state, 25.0)

    # ...but V1 has no reset mechanism: it stays latched TRIPPED.
    assert operating_state is OperatingState.TRIPPED
    assert derate_factor == 0.0
    assert trip_active is True
    assert trip_reason == "sustained_overtemperature"
