"""Tests for the DC bus energy-state model (src/dc_bus.py)."""

import math

from src.dc_bus import energy_from_voltage, step_dc_bus_energy, voltage_from_energy


def test_energy_voltage_round_trip():
    v_dc_v = 800.0
    c_dc_f = 0.02

    e_dc_j = energy_from_voltage(v_dc_v, c_dc_f)
    v_recovered_v = voltage_from_energy(e_dc_j, c_dc_f)

    assert math.isclose(v_recovered_v, v_dc_v, rel_tol=1e-9)


def test_energy_matches_textbook_formula():
    # E = 0.5 * C * V^2
    v_dc_v = 800.0
    c_dc_f = 0.02
    expected_j = 0.5 * c_dc_f * v_dc_v**2

    assert math.isclose(energy_from_voltage(v_dc_v, c_dc_f), expected_j, rel_tol=1e-9)


def test_bus_energy_increases_when_sst_exceeds_load():
    e_dc_j = 6400.0  # corresponds to 800V at C=0.02F
    e_next_j = step_dc_bus_energy(
        e_dc_j, p_sst_w=200_000.0, p_load_w=100_000.0, dt_s=1e-4, min_energy_j=1.0
    )
    assert e_next_j > e_dc_j


def test_bus_energy_decreases_when_load_exceeds_sst():
    e_dc_j = 6400.0
    e_next_j = step_dc_bus_energy(
        e_dc_j, p_sst_w=100_000.0, p_load_w=200_000.0, dt_s=1e-4, min_energy_j=1.0
    )
    assert e_next_j < e_dc_j


def test_bus_energy_never_goes_below_floor():
    e_dc_j = 2.0
    min_energy_j = 1.0
    # A huge load pulse over one step would otherwise drive energy deeply negative.
    e_next_j = step_dc_bus_energy(
        e_dc_j, p_sst_w=0.0, p_load_w=1e9, dt_s=1e-2, min_energy_j=min_energy_j
    )
    assert e_next_j == min_energy_j


def test_voltage_from_energy_is_finite_at_floor():
    v_dc_v = voltage_from_energy(1.0, 0.02)
    assert math.isfinite(v_dc_v)
    assert v_dc_v > 0.0
