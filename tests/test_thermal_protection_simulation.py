"""End-to-end test of the thermal + protection coupling inside run_simulation.

Verifies the causal chain described in src/simulation.py's module
docstring: electrical load -> SST power -> loss -> temperature ->
protection -> available power -> electrical response. Uses a coarser
(but still stable -- see scenarios/sustained_high_load.py for why
dt=0.001s is safe while dt=0.01s is not) timestep so these long-duration
thermal runs stay fast.
"""

import dataclasses

import numpy as np

from src.config import load_config
from src.protection import OperatingState
from src.simulation import run_simulation

CONFIG_PATH = "config/default.yaml"


def _constant_load(p_w):
    def fn(t_s):
        return p_w

    return fn


def _thermal_config(duration_s, derate_factor_min=0.5):
    config = load_config(CONFIG_PATH)
    return dataclasses.replace(
        config,
        protection=dataclasses.replace(config.protection, derate_factor_min=derate_factor_min),
        simulation=dataclasses.replace(config.simulation, timestep_s=0.001, duration_s=duration_s),
    )


def test_short_scenario_a_duration_never_leaves_running():
    # Phase 1's load-step scenario (duration ~0.6 s) is far shorter than the
    # 30 s thermal time constant: protection must never engage.
    config = load_config(CONFIG_PATH)
    telemetry = run_simulation(config, _constant_load(0.8 * config.load.rated_power_w))
    assert np.all(telemetry.operating_state == OperatingState.RUNNING.value)
    assert np.all(telemetry.derate_factor == 1.0)
    assert np.all(~telemetry.trip_active)


def test_moderate_sustained_load_derates_but_never_trips():
    cfg = _thermal_config(duration_s=200.0)
    # 200 kW: below rated_power_w * derate_factor_min (250 kW), so it never
    # saturates against the derated cap and should self-stabilize safely.
    telemetry = run_simulation(cfg, _constant_load(200_000.0))

    assert np.all(~telemetry.trip_active)
    assert OperatingState.DERATED.value in telemetry.operating_state
    final_window = telemetry.time_s >= cfg.simulation.duration_s - 5.0
    # No sustained deficit: the SST should be meeting the full 200 kW demand.
    assert np.mean(telemetry.p_sst_w[final_window]) > 195_000.0
    assert np.mean(telemetry.v_dc_v[final_window]) > 795.0


def test_severe_sustained_load_derates_then_trips():
    cfg = _thermal_config(duration_s=90.0)
    telemetry = run_simulation(
        cfg,
        _constant_load(450_000.0),
        initial_p_sst_w=450_000.0,
        initial_integral_error_v_s=0.0,
    )

    assert OperatingState.DERATED.value in telemetry.operating_state
    assert OperatingState.TRIPPED.value in telemetry.operating_state
    assert np.any(telemetry.trip_active)

    trip_idx = np.argmax(telemetry.trip_active)
    # Once latched, SST power is forced toward zero by the existing SST
    # dynamic model (derate_factor -> 0 -> P_target -> 0 -> first-order decay).
    assert telemetry.p_sst_w[-1] < 1000.0
    assert telemetry.derate_factor[trip_idx] == 0.0


def test_protection_affects_plant_only_through_power_availability():
    """Protection must never touch V_dc/E_dc directly -- only P_available_max."""
    cfg = _thermal_config(duration_s=90.0)
    telemetry = run_simulation(
        cfg,
        _constant_load(450_000.0),
        initial_p_sst_w=450_000.0,
        initial_integral_error_v_s=0.0,
    )
    rated_power_w = cfg.sst.rated_power_w
    # P_target must never exceed what the current derate_factor allows,
    # confirming the only channel of influence is the saturation limit.
    allowed_max = rated_power_w * telemetry.derate_factor
    assert np.all(telemetry.p_target_w <= allowed_max + 1.0)
    # Energy and voltage remain governed purely by dE/dt = P_sst - P_load;
    # no NaNs or negative energy from the protection coupling.
    assert np.all(telemetry.e_dc_j >= 0.0)
    assert np.all(np.isfinite(telemetry.v_dc_v))
