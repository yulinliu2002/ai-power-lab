"""Tests for dashboard/adapters/protection_timeline.py (SPEC-008).

Exercises both the four real Scenarios B-E's actual adapter output and
Scenario A's (AC-001), plus small, constructed `Telemetry` fixtures for
the general extraction-algorithm edge cases that none of the real
scenarios' fixed defaults reach: `PROTECTION_TRIP`, the exact-timestep
tie-break, the `DERATED` -> `RUNNING` return case, and repeated
bus-energy excursions (SPEC-008 AC-019).
"""

from __future__ import annotations

import re

import numpy as np
import pytest

from dashboard.adapters import simulation_adapter as adapter
from dashboard.adapters.protection_timeline import (
    RecoveryStatus,
    RideThroughOutcome,
    build_protection_timeline,
)
from src.config import (
    Config,
    ControllerConfig,
    DcBusConfig,
    GridConfig,
    LoadConfig,
    ProtectionConfig,
    SimulationConfig,
    SstConfig,
    ThermalConfig,
)
from src.telemetry import Telemetry


def _make_config(
    *,
    thermal_derate_start_c: float = 70.0,
    thermal_trip_c: float = 100.0,
    thermal_trip_time_s: float = 2.0,
    derate_factor_min: float = 0.5,
    capacitance_f: float = 0.02,
    min_energy_j: float = 1.0,
    voltage_reference_v: float = 800.0,
) -> Config:
    return Config(
        simulation=SimulationConfig(timestep_s=1.0, duration_s=1.0),
        sst=SstConfig(rated_power_w=500_000.0, min_power_w=0.0, efficiency=0.97, time_constant_s=0.02),
        dc_bus=DcBusConfig(
            nominal_voltage_v=800.0,
            capacitance_f=capacitance_f,
            initial_voltage_v=800.0,
            min_energy_j=min_energy_j,
        ),
        controller=ControllerConfig(
            voltage_reference_v=voltage_reference_v,
            kp_w_per_v=2000.0,
            ki_w_per_v_s=1500.0,
            integral_min_v_s=-250.0,
            integral_max_v_s=250.0,
        ),
        load=LoadConfig(rated_power_w=400_000.0),
        thermal=ThermalConfig(
            ambient_temperature_c=25.0,
            initial_temperature_c=25.0,
            thermal_resistance_c_per_w=0.01,
            thermal_capacitance_j_per_c=3000.0,
        ),
        protection=ProtectionConfig(
            thermal_derate_start_c=thermal_derate_start_c,
            thermal_trip_c=thermal_trip_c,
            thermal_trip_time_s=thermal_trip_time_s,
            derate_factor_min=derate_factor_min,
        ),
        grid=GridConfig(nominal_voltage_pu=1.0),
    )


def _make_telemetry(
    *,
    time_s: list[float],
    operating_state: list[str],
    trip_active: list[bool],
    trip_reason: list[str],
    v_dc_v: list[float] | None = None,
    temperature_c: list[float] | None = None,
) -> Telemetry:
    n = len(time_s)
    zeros = np.zeros(n)
    return Telemetry(
        time_s=np.array(time_s, dtype=float),
        grid_voltage_pu=np.ones(n),
        grid_available=np.ones(n, dtype=bool),
        p_load_w=zeros.copy(),
        p_cmd_w=zeros.copy(),
        p_target_w=zeros.copy(),
        p_sst_w=zeros.copy(),
        p_input_w=zeros.copy(),
        p_loss_w=zeros.copy(),
        e_dc_j=zeros.copy(),
        v_dc_v=np.array(v_dc_v if v_dc_v is not None else [800.0] * n, dtype=float),
        voltage_error_v=zeros.copy(),
        controller_integral_v_s=zeros.copy(),
        temperature_c=np.array(temperature_c if temperature_c is not None else [25.0] * n, dtype=float),
        operating_state=np.array(operating_state, dtype=object),
        derate_factor=zeros.copy(),
        trip_active=np.array(trip_active, dtype=bool),
        trip_reason=np.array(trip_reason, dtype=object),
    )


# --------------------------------------------------------------------------
# AC-001 / AC-004 / AC-015: real scenarios
# --------------------------------------------------------------------------


def test_scenario_a_never_reaches_the_numerical_floor() -> None:
    """Establishes, not assumes, Scenario A's RIDE_THROUGH/RECOVERED result."""
    result = adapter.run_load_step()
    timeline = build_protection_timeline(result.telemetry, result.config, result.events)
    assert timeline.outcome is RideThroughOutcome.RIDE_THROUGH
    assert timeline.recovery is RecoveryStatus.RECOVERED


def test_sustained_high_load_rides_through() -> None:
    result = adapter.run_sustained_high_load()
    timeline = build_protection_timeline(result.telemetry, result.config, result.events)
    assert timeline.outcome is RideThroughOutcome.RIDE_THROUGH
    assert timeline.recovery is RecoveryStatus.RECOVERED


def test_grid_sag_collapses_unprotected_and_recovers() -> None:
    result = adapter.run_grid_sag()
    timeline = build_protection_timeline(result.telemetry, result.config, result.events)
    assert timeline.outcome is RideThroughOutcome.BUS_COLLAPSE_UNPROTECTED
    assert timeline.recovery is RecoveryStatus.RECOVERED


def test_grid_loss_collapses_unprotected_and_never_recovers() -> None:
    result = adapter.run_grid_loss()
    timeline = build_protection_timeline(result.telemetry, result.config, result.events)
    assert timeline.outcome is RideThroughOutcome.BUS_COLLAPSE_UNPROTECTED
    assert timeline.recovery is RecoveryStatus.NOT_RECOVERED


def test_thermal_trip_floor_contact_precedes_later_trip_real_chronology() -> None:
    """AC-004: the bus reaches the floor (~14.4s) before TRIPPED latches
    (~46.1s); outcome is BUS_COLLAPSE_UNPROTECTED at the earlier time, and
    the later TRIPPED transition remains fully visible in `events`."""
    result = adapter.run_thermal_trip()
    telemetry = result.telemetry
    # Thermal Trip's own adapter-computed events are protection-derived,
    # not genuine input events (SPEC-008 §11 reconciliation rule).
    timeline = build_protection_timeline(telemetry, result.config, [])

    first_floor_idx = int(np.argmax(telemetry.v_dc_v <= 10.5))
    first_trip_idx = int(np.argmax(telemetry.trip_active))
    floor_time_s = float(telemetry.time_s[first_floor_idx])
    trip_time_s = float(telemetry.time_s[first_trip_idx])
    assert floor_time_s < trip_time_s

    assert timeline.outcome is RideThroughOutcome.BUS_COLLAPSE_UNPROTECTED
    assert timeline.outcome_event_time_s == pytest.approx(floor_time_s)

    tripped_events = [e for e in timeline.events if e.category == "protection_state" and e.label == "TRIPPED"]
    assert len(tripped_events) == 1
    assert tripped_events[0].time_s == pytest.approx(trip_time_s)
    assert "sustained_overtemperature" in tripped_events[0].detail

    segment_states = [s.state for s in timeline.segments]
    assert segment_states == ["RUNNING", "DERATED", "TRIPPED"]


# --------------------------------------------------------------------------
# AC-002: duration invariant
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario_fn,input_events_filtered",
    [
        (adapter.run_load_step, False),
        (adapter.run_sustained_high_load, False),
        (adapter.run_thermal_trip, True),
        (adapter.run_grid_sag, False),
        (adapter.run_grid_loss, False),
    ],
)
def test_segment_durations_sum_to_run_duration(scenario_fn, input_events_filtered: bool) -> None:
    result = scenario_fn()
    input_events = [] if input_events_filtered else result.events
    timeline = build_protection_timeline(result.telemetry, result.config, input_events)
    total = sum(s.duration_s for s in timeline.segments)
    expected = float(result.telemetry.time_s[-1] - result.telemetry.time_s[0])
    assert total == pytest.approx(expected)


# --------------------------------------------------------------------------
# AC-003: config-traceable causes
# --------------------------------------------------------------------------


def test_derated_transition_detail_names_the_exact_config_value() -> None:
    config = _make_config(thermal_derate_start_c=70.0)
    telemetry = _make_telemetry(
        time_s=[0.0, 1.0],
        operating_state=["RUNNING", "DERATED"],
        trip_active=[False, False],
        trip_reason=["", ""],
        temperature_c=[50.0, 75.0],
    )
    timeline = build_protection_timeline(telemetry, config, [])
    derated_events = [e for e in timeline.events if e.label == "DERATED begins"]
    assert len(derated_events) == 1

    match = re.search(r"thermal_derate_start_c \(([\d.eE+-]+) °C\)", derated_events[0].detail)
    assert match is not None
    assert float(match.group(1)) == config.protection.thermal_derate_start_c


def test_running_resumes_transition_detail_names_the_exact_config_value() -> None:
    config = _make_config(thermal_derate_start_c=70.0)
    telemetry = _make_telemetry(
        time_s=[0.0, 1.0, 2.0],
        operating_state=["RUNNING", "DERATED", "RUNNING"],
        trip_active=[False, False, False],
        trip_reason=["", "", ""],
        temperature_c=[50.0, 75.0, 60.0],
    )
    timeline = build_protection_timeline(telemetry, config, [])
    running_events = [e for e in timeline.events if e.label == "RUNNING resumes"]
    assert len(running_events) == 1

    match = re.search(r"thermal_derate_start_c \(([\d.eE+-]+) °C\)", running_events[0].detail)
    assert match is not None
    assert float(match.group(1)) == config.protection.thermal_derate_start_c


def test_tripped_transition_detail_names_the_exact_config_values() -> None:
    config = _make_config(thermal_trip_c=100.0, thermal_trip_time_s=2.0)
    telemetry = _make_telemetry(
        time_s=[0.0, 1.0],
        operating_state=["RUNNING", "TRIPPED"],
        trip_active=[False, True],
        trip_reason=["", "sustained_overtemperature"],
        temperature_c=[50.0, 105.0],
    )
    timeline = build_protection_timeline(telemetry, config, [])
    tripped_events = [e for e in timeline.events if e.label == "TRIPPED"]
    assert len(tripped_events) == 1

    detail = tripped_events[0].detail
    trip_c_match = re.search(r"thermal_trip_c \(([\d.eE+-]+) °C\)", detail)
    trip_time_match = re.search(r"thermal_trip_time_s \(([\d.eE+-]+) s\)", detail)
    assert trip_c_match is not None and trip_time_match is not None
    assert float(trip_c_match.group(1)) == config.protection.thermal_trip_c
    assert float(trip_time_match.group(1)) == config.protection.thermal_trip_time_s


# --------------------------------------------------------------------------
# AC-017: trip_reason field contract
# --------------------------------------------------------------------------


def test_tripped_transition_detail_contains_verbatim_trip_reason() -> None:
    result = adapter.run_thermal_trip()
    timeline = build_protection_timeline(result.telemetry, result.config, [])
    tripped_events = [e for e in timeline.events if e.category == "protection_state" and e.label == "TRIPPED"]
    assert len(tripped_events) == 1

    trip_idx = int(np.argmax(result.telemetry.trip_active))
    expected_reason = str(result.telemetry.trip_reason[trip_idx])
    assert expected_reason in tripped_events[0].detail


# --------------------------------------------------------------------------
# AC-016: input-event reconciliation
# --------------------------------------------------------------------------


def test_thermal_trip_protection_derived_markers_are_not_input_events() -> None:
    result = adapter.run_thermal_trip()
    # Reconciled per SPEC-008 §11: thermal_trip's own adapter events are
    # protection-derived, never passed through as input_events.
    timeline = build_protection_timeline(result.telemetry, result.config, [])
    input_labels = {e.label for e in timeline.events if e.category == "input_event"}
    assert "derating begins" not in input_labels
    assert "TRIPPED" not in input_labels


@pytest.mark.parametrize("scenario_fn", [adapter.run_grid_sag, adapter.run_grid_loss, adapter.run_load_step])
def test_genuine_input_events_pass_through_unchanged(scenario_fn) -> None:
    result = scenario_fn()
    timeline = build_protection_timeline(result.telemetry, result.config, result.events)
    input_labels = [e.label for e in timeline.events if e.category == "input_event"]
    assert input_labels == [label for _, label in result.events]


# --------------------------------------------------------------------------
# AC-018: degenerate input handling
# --------------------------------------------------------------------------


def test_build_protection_timeline_rejects_zero_length_telemetry() -> None:
    config = _make_config()
    telemetry = _make_telemetry(time_s=[], operating_state=[], trip_active=[], trip_reason=[])
    with pytest.raises(ValueError):
        build_protection_timeline(telemetry, config, [])


def test_single_sample_telemetry_produces_one_open_ended_segment() -> None:
    config = _make_config()
    telemetry = _make_telemetry(
        time_s=[3.5], operating_state=["RUNNING"], trip_active=[False], trip_reason=[""]
    )
    timeline = build_protection_timeline(telemetry, config, [])
    assert len(timeline.segments) == 1
    assert timeline.segments[0].is_open_ended is True
    assert timeline.segments[0].duration_s == 0.0
    assert len(timeline.events) == 0
    assert timeline.outcome is RideThroughOutcome.RIDE_THROUGH
    assert timeline.recovery is RecoveryStatus.RECOVERED


# --------------------------------------------------------------------------
# AC-019: constructed extraction fixtures
# --------------------------------------------------------------------------


def test_running_derated_running_derated_tripped_segment_boundaries() -> None:
    """Covers exact segment boundary/adjacency, the DERATED -> RUNNING
    return case, and (since no bus-floor contact occurs) a constructed
    PROTECTION_TRIP fixture -- none of Scenarios A-E's real defaults
    exercise PROTECTION_TRIP (SPEC-008 §0)."""
    config = _make_config()
    telemetry = _make_telemetry(
        time_s=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
        operating_state=["RUNNING", "DERATED", "RUNNING", "DERATED", "TRIPPED", "TRIPPED"],
        trip_active=[False, False, False, False, True, True],
        trip_reason=["", "", "", "", "sustained_overtemperature", "sustained_overtemperature"],
        temperature_c=[50.0, 75.0, 60.0, 80.0, 105.0, 105.0],
        v_dc_v=[800.0] * 6,
    )
    timeline = build_protection_timeline(telemetry, config, [])

    segment_tuples = [(s.state, s.start_time_s, s.end_time_s, s.is_open_ended) for s in timeline.segments]
    assert segment_tuples == [
        ("RUNNING", 0.0, 1.0, False),
        ("DERATED", 1.0, 2.0, False),
        ("RUNNING", 2.0, 3.0, False),
        ("DERATED", 3.0, 4.0, False),
        ("TRIPPED", 4.0, 5.0, True),
    ]
    assert sum(s.duration_s for s in timeline.segments) == pytest.approx(5.0)

    transition_labels = [e.label for e in timeline.events if e.category == "protection_state"]
    assert transition_labels == ["DERATED begins", "RUNNING resumes", "DERATED begins", "TRIPPED"]

    # No bus-floor contact in this fixture -> PROTECTION_TRIP, not BUS_COLLAPSE_UNPROTECTED.
    assert timeline.outcome is RideThroughOutcome.PROTECTION_TRIP
    assert timeline.outcome_event_time_s == pytest.approx(4.0)
    assert timeline.recovery is RecoveryStatus.NOT_APPLICABLE


def test_repeated_bus_energy_excursions_produce_distinct_entry_exit_pairs() -> None:
    """At least two separate floor excursions must each produce their own
    entry/exit pair -- not merged into one, not dropped."""
    config = _make_config(capacitance_f=0.02, min_energy_j=1.0)  # floor_v = 10.0 V
    telemetry = _make_telemetry(
        time_s=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
        operating_state=["RUNNING"] * 8,
        trip_active=[False] * 8,
        trip_reason=[""] * 8,
        v_dc_v=[800.0, 5.0, 800.0, 800.0, 5.0, 5.0, 800.0, 800.0],
    )
    timeline = build_protection_timeline(telemetry, config, [])

    bus_events = [(e.time_s, e.label) for e in timeline.events if e.category == "bus_energy"]
    assert bus_events == [
        (1.0, "bus energy at numerical floor"),
        (2.0, "bus energy recovers"),
        (4.0, "bus energy at numerical floor"),
        (6.0, "bus energy recovers"),
    ]


def test_exact_timestep_tie_breaks_toward_protection_trip() -> None:
    """AC-019's tie-break fixture: trip_active first True at the exact
    same sample as the first bus-floor contact. Tests the documented
    convention (an arbitrary, non-causal tie-break favoring the named
    protection action), not a causal claim (SPEC-008 §9)."""
    config = _make_config(capacitance_f=0.02, min_energy_j=1.0)  # floor_v = 10.0 V
    telemetry = _make_telemetry(
        time_s=[0.0, 1.0, 2.0],
        operating_state=["RUNNING", "TRIPPED", "TRIPPED"],
        trip_active=[False, True, True],
        trip_reason=["", "sustained_overtemperature", "sustained_overtemperature"],
        temperature_c=[50.0, 105.0, 105.0],
        v_dc_v=[800.0, 5.0, 5.0],
    )
    timeline = build_protection_timeline(telemetry, config, [])

    assert timeline.outcome is RideThroughOutcome.PROTECTION_TRIP
    assert timeline.outcome_event_time_s == pytest.approx(1.0)

    # The tie-break is an explicit, arbitrary, non-causal convention
    # (§9) -- the detail text must never claim the trip occurred
    # "before" the floor contact when the two candidate times are
    # exactly equal.
    assert "before" not in timeline.outcome_detail
    assert "tie" in timeline.outcome_detail.lower()
