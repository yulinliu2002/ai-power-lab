"""Tests for dashboard/adapters/simulation_adapter.py.

Verifies the dashboard adapter layer produces finite, sane telemetry
for each interactive demo and never diverges from the underlying
engine's own guarantees -- it does not re-test the physics itself (see
tests/test_simulation_integration.py and friends for that).
"""

from __future__ import annotations

import numpy as np

from dashboard.adapters import simulation_adapter as adapter

TELEMETRY_FIELDS_TO_CHECK = ("v_dc_v", "p_sst_w", "p_load_w", "temperature_c", "derate_factor")


def _assert_finite_telemetry(result: adapter.ScenarioResult) -> None:
    for name in TELEMETRY_FIELDS_TO_CHECK:
        values = getattr(result.telemetry, name)
        assert np.all(np.isfinite(values)), f"{name} contains non-finite values"
        assert len(values) > 0


def test_run_load_step_default_params():
    result = adapter.run_load_step(duration_s=0.3)
    _assert_finite_telemetry(result)
    assert result.telemetry.v_dc_v[0] > 0
    assert result.events


def test_run_load_step_respects_overrides():
    result = adapter.run_load_step(
        duration_s=0.3, rated_power_w=300_000.0, voltage_reference_v=750.0
    )
    assert result.config.sst.rated_power_w == 300_000.0
    assert result.config.controller.voltage_reference_v == 750.0
    _assert_finite_telemetry(result)


def test_run_sustained_high_load_short_duration():
    result = adapter.run_sustained_high_load(load_w=200_000.0, duration_s=2.0)
    _assert_finite_telemetry(result)


def test_run_thermal_trip_short_duration():
    result = adapter.run_thermal_trip(overload_w=450_000.0, duration_s=2.0)
    _assert_finite_telemetry(result)


def test_run_grid_sag():
    result = adapter.run_grid_sag(duration_s=1.0)
    _assert_finite_telemetry(result)
    assert len(result.events) == 2


def test_run_grid_loss():
    result = adapter.run_grid_loss(duration_s=0.3)
    _assert_finite_telemetry(result)
    assert len(result.events) == 1


def test_summary_metrics_shape():
    result = adapter.run_load_step(duration_s=0.3)
    metrics = adapter.summary_metrics(result)
    expected_keys = {
        "min_vdc_v",
        "max_vdc_v",
        "peak_sst_power_w",
        "max_temperature_c",
        "final_operating_state",
    }
    assert set(metrics.keys()) == expected_keys
    assert metrics["final_operating_state"] in {"RUNNING", "DERATED", "TRIPPED"}


def test_scenario_keys_cover_all_adapter_functions():
    assert adapter.SCENARIO_KEYS == {
        "load_step",
        "sustained_high_load",
        "thermal_trip",
        "grid_sag",
        "grid_loss",
    }
