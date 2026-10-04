"""End-to-end tests for the grid-sag and grid-loss scenarios (D and E).

Mirrors the pattern in tests/test_thermal_protection_simulation.py:
exercise run_simulation with a real grid-disturbance profile and verify
meaningful engineering behavior (droop/recovery, collapse, and the
"protection/availability only limits power, never forces voltage"
invariant), not just that individual src/grid.py helper functions
return the right numbers in isolation.
"""

import dataclasses

import numpy as np

from src.config import load_config
from src.grid import make_outage_profile, make_sag_profile
from src.simulation import run_simulation

CONFIG_PATH = "config/default.yaml"
LOAD_W = 300_000.0


def _constant_load(p_w):
    def fn(t_s):
        return p_w

    return fn


def test_grid_sag_causes_droop_then_full_recovery():
    config = load_config(CONFIG_PATH)
    config = dataclasses.replace(
        config, simulation=dataclasses.replace(config.simulation, duration_s=1.2)
    )
    sag_start_s, sag_duration_s = 0.3, 0.2
    grid_fn = make_sag_profile(
        nominal_voltage_pu=config.grid.nominal_voltage_pu,
        sag_voltage_pu=0.5,
        sag_start_s=sag_start_s,
        sag_duration_s=sag_duration_s,
    )

    telemetry = run_simulation(
        config, _constant_load(LOAD_W), grid_fn=grid_fn,
        initial_p_sst_w=LOAD_W, initial_integral_error_v_s=0.0,
    )

    before_sag = telemetry.time_s < sag_start_s
    during_sag = (telemetry.time_s >= sag_start_s) & (telemetry.time_s < sag_start_s + sag_duration_s)
    after_recovery = telemetry.time_s >= sag_start_s + sag_duration_s + 0.2

    # Healthy baseline before the disturbance.
    assert np.all(telemetry.v_dc_v[before_sag] > 795.0)
    # A measurable droop during the sag: 250 kW available cap < 300 kW demand.
    assert telemetry.v_dc_v[during_sag].min() < 750.0
    # Clean recovery once the grid returns to nominal -- governed purely by
    # dE_dc/dt = P_sst - P_load, not forced.
    assert telemetry.v_dc_v[after_recovery][-1] > 795.0


def test_grid_sag_limits_power_availability_not_voltage_directly():
    """Grid availability must act only through the power ceiling, like
    thermal protection does -- never by editing V_dc/E_dc directly."""
    config = load_config(CONFIG_PATH)
    grid_fn = make_sag_profile(
        nominal_voltage_pu=config.grid.nominal_voltage_pu,
        sag_voltage_pu=0.5, sag_start_s=0.3, sag_duration_s=0.2,
    )
    telemetry = run_simulation(
        config, _constant_load(LOAD_W), grid_fn=grid_fn,
        initial_p_sst_w=LOAD_W, initial_integral_error_v_s=0.0,
    )
    allowed_max = config.sst.rated_power_w * np.minimum(telemetry.grid_voltage_pu, 1.0)
    assert np.all(telemetry.p_target_w <= allowed_max + 1.0)
    assert np.all(telemetry.e_dc_j >= 0.0)
    assert np.all(np.isfinite(telemetry.v_dc_v))


def test_grid_loss_forces_target_to_zero_and_bus_discharges():
    config = load_config(CONFIG_PATH)
    outage_start_s = 0.2
    grid_fn = make_outage_profile(
        nominal_voltage_pu=config.grid.nominal_voltage_pu,
        outage_start_s=outage_start_s,
        outage_duration_s=None,
    )

    telemetry = run_simulation(
        config, _constant_load(LOAD_W), grid_fn=grid_fn,
        initial_p_sst_w=LOAD_W, initial_integral_error_v_s=0.0,
    )

    before_loss = telemetry.time_s < outage_start_s
    after_loss = telemetry.time_s >= outage_start_s

    # Healthy baseline before the outage.
    assert np.all(telemetry.v_dc_v[before_loss] > 795.0)
    # Once the grid is lost, availability drives the target to zero --
    # via the existing saturation logic, no special-case shutdown.
    assert np.all(telemetry.p_target_w[after_loss] == 0.0)
    # SST power decays toward zero per its own existing first-order dynamics.
    assert telemetry.p_sst_w[-1] < telemetry.p_sst_w[after_loss][0]
    assert telemetry.p_sst_w[-1] < 1000.0
    # The bus discharges monotonically (never recharges once supply is gone)
    # and never goes negative -- governed by dE_dc/dt = P_sst - P_load alone.
    e_after = telemetry.e_dc_j[after_loss]
    assert np.all(np.diff(e_after) <= 1e-6)
    assert np.all(telemetry.e_dc_j >= 0.0)
    assert np.all(np.isfinite(telemetry.v_dc_v))
