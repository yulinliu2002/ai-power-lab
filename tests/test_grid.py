"""Tests for the exogenous grid condition model (src/grid.py)."""

from src.grid import (
    constant_grid_profile,
    grid_power_availability_factor,
    make_outage_profile,
    make_sag_profile,
)


def test_availability_factor_full_at_nominal_voltage():
    assert grid_power_availability_factor(1.0, True) == 1.0


def test_availability_factor_zero_when_unavailable():
    assert grid_power_availability_factor(1.0, False) == 0.0


def test_availability_factor_scales_with_sagged_voltage():
    assert grid_power_availability_factor(0.7, True) == 0.7


def test_availability_factor_clips_above_one():
    assert grid_power_availability_factor(1.2, True) == 1.0


def test_constant_profile_always_nominal_and_available():
    profile = constant_grid_profile(1.0)
    for t_s in [0.0, 1.0, 100.0]:
        assert profile(t_s) == (1.0, True)


def test_sag_profile_drops_and_recovers_voltage_but_stays_available():
    profile = make_sag_profile(
        nominal_voltage_pu=1.0, sag_voltage_pu=0.6, sag_start_s=1.0, sag_duration_s=0.5
    )
    assert profile(0.5) == (1.0, True)
    assert profile(1.2) == (0.6, True)
    assert profile(2.0) == (1.0, True)


def test_outage_profile_drops_voltage_and_availability_then_recovers():
    profile = make_outage_profile(
        nominal_voltage_pu=1.0, outage_start_s=1.0, outage_duration_s=0.5
    )
    assert profile(0.5) == (1.0, True)
    voltage_pu, available = profile(1.2)
    assert voltage_pu == 0.0
    assert available is False
    assert profile(2.0) == (1.0, True)


def test_outage_profile_without_duration_stays_down():
    profile = make_outage_profile(nominal_voltage_pu=1.0, outage_start_s=1.0)
    voltage_pu, available = profile(100.0)
    assert voltage_pu == 0.0
    assert available is False
