"""End-to-end test of the Phase 1 electrical core (src/simulation.py).

Runs the same load-step scenario as scenarios/load_step.py (40% -> 80%
rated load) over a short duration and checks the physical and
numerical sanity properties called out in the implementation request:
non-negative energy, finite voltage, SST power within limits, and a
qualitatively sensible transient (voltage dips then recovers toward
V_ref after the step).
"""

import math

import numpy as np

from src.config import load_config
from src.load import make_step_load_profile
from src.simulation import run_simulation

CONFIG_PATH = "config/default.yaml"
STEP_TIME_S = 0.2


def _run_load_step_scenario():
    config = load_config(CONFIG_PATH)
    load_fn = make_step_load_profile(
        rated_power_w=config.load.rated_power_w,
        initial_fraction=0.4,
        final_fraction=0.8,
        step_time_s=STEP_TIME_S,
    )
    return config, run_simulation(config, load_fn)


def test_energy_remains_non_negative():
    _, telemetry = _run_load_step_scenario()
    assert np.all(telemetry.e_dc_j >= 0.0)


def test_voltage_remains_finite_and_positive():
    _, telemetry = _run_load_step_scenario()
    assert np.all(np.isfinite(telemetry.v_dc_v))
    assert np.all(telemetry.v_dc_v > 0.0)


def test_sst_power_stays_within_rated_limits():
    config, telemetry = _run_load_step_scenario()
    assert np.all(telemetry.p_sst_w >= config.sst.min_power_w - 1e-6)
    assert np.all(telemetry.p_sst_w <= config.sst.rated_power_w + 1e-6)


def test_load_profile_matches_expected_fractions():
    config, telemetry = _run_load_step_scenario()
    before_step = telemetry.time_s < STEP_TIME_S
    after_step = telemetry.time_s >= STEP_TIME_S

    assert np.allclose(telemetry.p_load_w[before_step], 0.4 * config.load.rated_power_w)
    assert np.allclose(telemetry.p_load_w[after_step], 0.8 * config.load.rated_power_w)


def test_voltage_dips_after_load_step_then_recovers_toward_reference():
    config, telemetry = _run_load_step_scenario()
    v_ref = config.controller.voltage_reference_v

    just_before = telemetry.time_s < STEP_TIME_S
    just_after_window = (telemetry.time_s >= STEP_TIME_S) & (telemetry.time_s < STEP_TIME_S + 0.01)
    final_window = telemetry.time_s >= config.simulation.duration_s - 0.02

    v_before = telemetry.v_dc_v[just_before][-1]
    v_dip = np.min(telemetry.v_dc_v[just_after_window])
    v_final = np.mean(telemetry.v_dc_v[final_window])

    # Voltage should sag measurably below its pre-step value right after the step...
    assert v_dip < v_before
    # ...and recover to close to V_ref by the end of the simulation.
    assert math.isclose(v_final, v_ref, abs_tol=2.0)


def test_sst_power_tracks_toward_new_load_after_step():
    config, telemetry = _run_load_step_scenario()
    final_window = telemetry.time_s >= config.simulation.duration_s - 0.02
    p_sst_final = np.mean(telemetry.p_sst_w[final_window])
    expected_steady_state = 0.8 * config.load.rated_power_w

    assert math.isclose(p_sst_final, expected_steady_state, rel_tol=0.02)
