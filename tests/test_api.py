"""Tests for the V2 HTTP API boundary (backend/app.py).

Verifies the API layer is a faithful, lossless translation of the
existing simulation adapter -- it does not re-test the physics itself
(see tests/test_simulation_integration.py and friends for that). The
parity tests are the load-bearing ones here: they prove the API never
becomes a second implementation of the simulation.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
from dashboard.adapters import simulation_adapter as adapter

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_load_step_accepts_default_request() -> None:
    response = client.post("/api/v1/simulations/load-step", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["scenario"] == "load_step"
    assert "timeseries" in body
    assert "thresholds" in body


def test_load_step_response_schema_shape() -> None:
    response = client.post("/api/v1/simulations/load-step", json={"duration_s": 0.3})
    body = response.json()

    assert set(body.keys()) == {"scenario", "thresholds", "events", "timeseries"}
    assert set(body["thresholds"].keys()) == {
        "voltage_reference_v", "rated_power_w", "thermal_derate_start_c", "thermal_trip_c",
    }
    timeseries_fields = {
        "time_s", "v_dc_v", "p_sst_w", "p_load_w", "p_target_w",
        "temperature_c", "derate_factor", "trip_active", "operating_state",
        "grid_voltage_pu", "grid_available",
    }
    assert set(body["timeseries"].keys()) == timeseries_fields

    n = len(body["timeseries"]["time_s"])
    assert n > 0
    for field in timeseries_fields:
        assert len(body["timeseries"][field]) == n

    for event in body["events"]:
        assert set(event.keys()) == {"time_s", "label"}


def test_load_step_rejects_out_of_range_fraction() -> None:
    response = client.post("/api/v1/simulations/load-step", json={"initial_fraction": 1.5})
    assert response.status_code == 422


def test_load_step_rejects_non_positive_duration() -> None:
    response = client.post("/api/v1/simulations/load-step", json={"duration_s": 0.0})
    assert response.status_code == 422


def test_load_step_rejects_wrong_type() -> None:
    response = client.post("/api/v1/simulations/load-step", json={"initial_fraction": "not-a-number"})
    assert response.status_code == 422


def test_load_step_baseline_reproduces_default_adapter_result() -> None:
    """A request with no experiment overrides must still reproduce the
    existing Scenario A baseline exactly (contract check A)."""
    baseline = adapter.run_load_step()
    response = client.post("/api/v1/simulations/load-step", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["timeseries"]["v_dc_v"] == baseline.telemetry.v_dc_v.tolist()
    assert body["timeseries"]["p_sst_w"] == baseline.telemetry.p_sst_w.tolist()


def test_higher_capacitance_reduces_voltage_droop() -> None:
    """Contract check B: more DC-link capacitance must buffer more
    energy per volt, so the same load step produces a shallower
    voltage dip (qualitative direction, not an exact value)."""
    baseline = client.post("/api/v1/simulations/load-step", json={}).json()
    higher_c = client.post(
        "/api/v1/simulations/load-step", json={"capacitance_f": 0.08}
    ).json()

    baseline_min_v = min(baseline["timeseries"]["v_dc_v"])
    higher_c_min_v = min(higher_c["timeseries"]["v_dc_v"])

    assert higher_c_min_v > baseline_min_v


def test_slower_sst_response_worsens_transient() -> None:
    """Contract check C: a slower SST power-response time constant
    must leave the energy deficit open longer, producing a deeper
    voltage dip than baseline (qualitative direction)."""
    baseline = client.post("/api/v1/simulations/load-step", json={}).json()
    slower_sst = client.post(
        "/api/v1/simulations/load-step", json={"time_constant_s": 0.08}
    ).json()

    baseline_min_v = min(baseline["timeseries"]["v_dc_v"])
    slower_min_v = min(slower_sst["timeseries"]["v_dc_v"])

    assert slower_min_v < baseline_min_v


def test_changing_final_load_changes_transient() -> None:
    """Contract check D: a different final AI load level must change
    both the resulting P_load and the resulting transient."""
    baseline = client.post("/api/v1/simulations/load-step", json={}).json()
    bigger_step = client.post(
        "/api/v1/simulations/load-step", json={"final_fraction": 1.0}
    ).json()

    baseline_final_p_load = baseline["timeseries"]["p_load_w"][-1]
    bigger_final_p_load = bigger_step["timeseries"]["p_load_w"][-1]
    assert bigger_final_p_load > baseline_final_p_load

    baseline_min_v = min(baseline["timeseries"]["v_dc_v"])
    bigger_min_v = min(bigger_step["timeseries"]["v_dc_v"])
    assert bigger_min_v < baseline_min_v


def test_load_step_rejects_out_of_range_capacitance() -> None:
    """Contract check E: invalid experiment parameters are rejected
    with a validation error, not silently clipped."""
    too_small = client.post(
        "/api/v1/simulations/load-step", json={"capacitance_f": 0.0001}
    )
    assert too_small.status_code == 422

    too_large = client.post(
        "/api/v1/simulations/load-step", json={"capacitance_f": 10.0}
    )
    assert too_large.status_code == 422


def test_load_step_rejects_out_of_range_time_constant() -> None:
    """Contract check E: same for the SST response-time override."""
    too_small = client.post(
        "/api/v1/simulations/load-step", json={"time_constant_s": 0.0001}
    )
    assert too_small.status_code == 422

    too_large = client.post(
        "/api/v1/simulations/load-step", json={"time_constant_s": 10.0}
    )
    assert too_large.status_code == 422


def test_experiment_parameters_do_not_mutate_shared_config() -> None:
    """Each request must build an isolated Config -- running a custom
    experiment must never leak into a subsequent baseline request."""
    client.post(
        "/api/v1/simulations/load-step",
        json={"capacitance_f": 0.005, "time_constant_s": 0.08, "final_fraction": 1.0},
    )
    baseline_after = client.post("/api/v1/simulations/load-step", json={}).json()
    fresh_baseline = adapter.run_load_step()
    assert baseline_after["timeseries"]["v_dc_v"] == fresh_baseline.telemetry.v_dc_v.tolist()


def test_load_step_parity_with_source_of_truth() -> None:
    """Same parameters through two paths -- the API must reproduce the
    adapter's own result exactly, not a recomputation of it.
    """
    params = dict(
        initial_fraction=0.3, final_fraction=0.75, step_time_s=0.15, duration_s=0.4,
        rated_power_w=250_000.0, voltage_reference_v=780.0,
        capacitance_f=0.03, time_constant_s=0.04,
    )

    direct = adapter.run_load_step(**params)
    direct_telemetry = direct.telemetry

    response = client.post("/api/v1/simulations/load-step", json=params)
    assert response.status_code == 200
    api_timeseries = response.json()["timeseries"]

    assert len(api_timeseries["time_s"]) == len(direct_telemetry.time_s)

    # Exact equality for exactly-representable raw floats/bools/strings
    # straight out of the deterministic engine -- JSON round-tripping a
    # Python float through float() introduces no precision loss here.
    assert api_timeseries["time_s"] == direct_telemetry.time_s.tolist()
    assert api_timeseries["v_dc_v"] == direct_telemetry.v_dc_v.tolist()
    assert api_timeseries["p_sst_w"] == direct_telemetry.p_sst_w.tolist()
    assert api_timeseries["p_load_w"] == direct_telemetry.p_load_w.tolist()
    assert api_timeseries["p_target_w"] == direct_telemetry.p_target_w.tolist()
    assert api_timeseries["temperature_c"] == direct_telemetry.temperature_c.tolist()
    assert api_timeseries["derate_factor"] == direct_telemetry.derate_factor.tolist()
    assert api_timeseries["trip_active"] == direct_telemetry.trip_active.tolist()
    assert api_timeseries["operating_state"] == direct_telemetry.operating_state.tolist()
    assert api_timeseries["grid_voltage_pu"] == direct_telemetry.grid_voltage_pu.tolist()
    assert api_timeseries["grid_available"] == direct_telemetry.grid_available.tolist()

    api_thresholds = response.json()["thresholds"]
    assert api_thresholds["voltage_reference_v"] == direct.config.controller.voltage_reference_v
    assert api_thresholds["rated_power_w"] == direct.config.sst.rated_power_w
    assert api_thresholds["thermal_derate_start_c"] == direct.config.protection.thermal_derate_start_c
    assert api_thresholds["thermal_trip_c"] == direct.config.protection.thermal_trip_c

    api_events = response.json()["events"]
    assert [(e["time_s"], e["label"]) for e in api_events] == direct.events
