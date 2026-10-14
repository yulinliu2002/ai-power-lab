"""Tests for dashboard/adapters/scenario_comparison.py (SPEC-010).

Exercises `build_stress_profile` against all five real fixed scenarios
(AC-039/AC-040/AC-041), plus one constructed fixture for the one
`dominant_stress` branch no real scenario preset reaches
(`THERMAL_PROTECTION_TRIP`, AC-042), reusing the existing
`_make_config`/`_make_telemetry` fixture-construction pattern from
`tests/test_protection_timeline.py`.
"""

from __future__ import annotations

import numpy as np
import pytest

from dashboard.adapters import simulation_adapter as adapter
from dashboard.adapters.protection_timeline import build_protection_timeline
from dashboard.adapters.scenario_comparison import (
    DominantStress,
    build_stress_profile,
)
from src.dc_bus import energy_from_voltage
from tests.test_protection_timeline import _make_config, _make_telemetry

_SCENARIOS = [
    ("load_step", adapter.run_load_step, False),
    ("sustained_high_load", adapter.run_sustained_high_load, False),
    ("thermal_trip", adapter.run_thermal_trip, True),
    ("grid_sag", adapter.run_grid_sag, False),
    ("grid_loss", adapter.run_grid_loss, False),
]


def _build(scenario_fn, input_events_filtered: bool):
    result = scenario_fn()
    input_events = [] if input_events_filtered else result.events
    timeline = build_protection_timeline(result.telemetry, result.config, input_events)
    profile = build_stress_profile(result.telemetry, result.config, timeline)
    return result, timeline, profile


# --------------------------------------------------------------------------
# AC-039: StressProfile correctness, real scenarios, direct computation
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name,scenario_fn,input_events_filtered", _SCENARIOS)
def test_stress_profile_matches_direct_computation(name, scenario_fn, input_events_filtered) -> None:
    result, _, profile = _build(scenario_fn, input_events_filtered)
    t = result.telemetry
    v_ref = result.config.controller.voltage_reference_v

    assert profile.min_v_dc_v == pytest.approx(float(t.v_dc_v.min()))
    assert profile.max_v_dc_v == pytest.approx(float(t.v_dc_v.max()))
    assert profile.max_voltage_deviation_v == pytest.approx(float(np.abs(t.v_dc_v - v_ref).max()))
    assert profile.max_voltage_deviation_percent == pytest.approx(
        profile.max_voltage_deviation_v / v_ref * 100.0
    )
    assert profile.peak_power_deficit_w == pytest.approx(
        float(np.maximum(t.p_load_w - t.p_sst_w, 0.0).max())
    )
    assert profile.max_temperature_c == pytest.approx(float(t.temperature_c.max()))
    assert profile.grid_ever_unavailable == bool((~t.grid_available).any())
    assert profile.min_grid_voltage_pu == pytest.approx(float(t.grid_voltage_pu.min()))


# --------------------------------------------------------------------------
# AC-040: energy-excursion correctness + cross-check invariant
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name,scenario_fn,input_events_filtered", _SCENARIOS)
def test_energy_excursion_sourced_from_e_dc_j(name, scenario_fn, input_events_filtered) -> None:
    """`dc_link_energy_excursion_j` must equal
    `max(0, energy_from_voltage(V_ref, C) - min(telemetry.e_dc_j))` --
    the authoritative, `e_dc_j`-based value -- within 1e-6 J."""
    result, _, profile = _build(scenario_fn, input_events_filtered)
    t = result.telemetry
    config = result.config

    expected = max(
        0.0,
        energy_from_voltage(config.controller.voltage_reference_v, config.dc_bus.capacitance_f)
        - float(t.e_dc_j.min()),
    )
    assert profile.dc_link_energy_excursion_j == pytest.approx(expected, abs=1e-6)


@pytest.mark.parametrize("name,scenario_fn,input_events_filtered", _SCENARIOS)
def test_energy_excursion_cross_check_invariant(name, scenario_fn, input_events_filtered) -> None:
    """The closed-form voltage-energy cross-check must agree with the
    primary `e_dc_j`-based value to within 1e-9 J (SPEC-010 AC-040) --
    a larger disagreement would mean `e_dc_j`/`v_dc_v` are out of sync."""
    result, _, profile = _build(scenario_fn, input_events_filtered)
    config = result.config
    v_ref = config.controller.voltage_reference_v
    capacitance_f = config.dc_bus.capacitance_f

    cross_check = max(0.0, 0.5 * capacitance_f * (v_ref**2 - profile.min_v_dc_v**2))
    assert profile.dc_link_energy_excursion_j == pytest.approx(cross_check, abs=1e-9)


def test_energy_excursion_clamps_at_zero_when_min_energy_exceeds_nominal() -> None:
    """A constructed fixture where `min(e_dc_j) > energy_from_voltage(V_ref, C)`
    must return exactly 0.0, never a negative value."""
    config = _make_config(voltage_reference_v=800.0, capacitance_f=0.02, min_energy_j=1.0)
    telemetry = _make_telemetry(
        time_s=[0.0, 1.0],
        operating_state=["RUNNING", "RUNNING"],
        trip_active=[False, False],
        trip_reason=["", ""],
        v_dc_v=[850.0, 850.0],
    )
    telemetry.e_dc_j[:] = energy_from_voltage(850.0, 0.02)
    timeline = build_protection_timeline(telemetry, config, [])
    profile = build_stress_profile(telemetry, config, timeline)
    assert profile.dc_link_energy_excursion_j == 0.0


# --------------------------------------------------------------------------
# AC-041: protection_states_reached correctness
# --------------------------------------------------------------------------


_EXPECTED_STATES_REACHED = {
    "load_step": ("RUNNING",),
    "sustained_high_load": ("RUNNING", "DERATED"),
    "thermal_trip": ("RUNNING", "DERATED", "TRIPPED"),
    "grid_sag": ("RUNNING",),
    "grid_loss": ("RUNNING",),
}


@pytest.mark.parametrize("name,scenario_fn,input_events_filtered", _SCENARIOS)
def test_protection_states_reached(name, scenario_fn, input_events_filtered) -> None:
    _, _, profile = _build(scenario_fn, input_events_filtered)
    assert profile.protection_states_reached == _EXPECTED_STATES_REACHED[name]


# --------------------------------------------------------------------------
# AC-042: dominant_stress taxonomy, real scenarios + constructed fixture
# --------------------------------------------------------------------------


_EXPECTED_DOMINANT_STRESS = {
    "load_step": DominantStress.TRANSIENT_POWER_IMBALANCE,
    "sustained_high_load": DominantStress.SUSTAINED_THERMAL_DERATING,
    "thermal_trip": DominantStress.DC_BUS_VIABILITY_LOSS,
    "grid_sag": DominantStress.DC_BUS_VIABILITY_LOSS,
    "grid_loss": DominantStress.DC_BUS_VIABILITY_LOSS,
}


@pytest.mark.parametrize("name,scenario_fn,input_events_filtered", _SCENARIOS)
def test_dominant_stress_real_scenarios(name, scenario_fn, input_events_filtered) -> None:
    _, _, profile = _build(scenario_fn, input_events_filtered)
    assert profile.dominant_stress is _EXPECTED_DOMINANT_STRESS[name]


def test_dominant_stress_protection_trip_fixture() -> None:
    """The one branch no real scenario preset reaches (SPEC-010 AC-042) --
    reuses the PROTECTION_TRIP fixture pattern from
    tests/test_protection_timeline.py. No bus-floor contact at all in
    this fixture -- `dominant_stress_detail` must say the floor was
    never reached, never "before" (there is nothing to be before)."""
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
    profile = build_stress_profile(telemetry, config, timeline)
    assert profile.dominant_stress is DominantStress.THERMAL_PROTECTION_TRIP
    assert "PROTECTION_TRIP" in profile.dominant_stress_detail
    assert "never reached" in profile.dominant_stress_detail
    assert "before" not in profile.dominant_stress_detail


def test_dominant_stress_protection_trip_detail_with_later_floor_contact() -> None:
    """A `PROTECTION_TRIP` fixture where the bus floor is reached strictly
    *after* the trip (Codex Round 1 implementation-review finding) --
    `dominant_stress_detail` must correctly say "before", since the trip
    genuinely did precede the later floor contact here."""
    config = _make_config(capacitance_f=0.02, min_energy_j=1.0)  # floor_v = 10.0 V
    telemetry = _make_telemetry(
        time_s=[0.0, 1.0, 2.0],
        operating_state=["RUNNING", "TRIPPED", "TRIPPED"],
        trip_active=[False, True, True],
        trip_reason=["", "sustained_overtemperature", "sustained_overtemperature"],
        temperature_c=[50.0, 105.0, 105.0],
        v_dc_v=[800.0, 800.0, 5.0],
    )
    timeline = build_protection_timeline(telemetry, config, [])
    profile = build_stress_profile(telemetry, config, timeline)
    assert profile.dominant_stress is DominantStress.THERMAL_PROTECTION_TRIP
    assert "before" in profile.dominant_stress_detail


def test_dominant_stress_protection_trip_detail_exact_timestep_tie() -> None:
    """The exact-timestep tie fixture (reused from
    tests/test_protection_timeline.py::test_exact_timestep_tie_breaks_toward_protection_trip,
    SPEC-010 Codex Round 1 implementation-review MAJOR finding): trip and
    bus-floor contact at the exact same sample. `dominant_stress_detail`
    must state the tie, never claim the trip occurred "before" the floor
    contact."""
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
    profile = build_stress_profile(telemetry, config, timeline)
    assert profile.dominant_stress is DominantStress.THERMAL_PROTECTION_TRIP
    assert "before" not in profile.dominant_stress_detail
    assert "tie" in profile.dominant_stress_detail.lower()
