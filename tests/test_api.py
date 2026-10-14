"""Tests for the V2 HTTP API boundary (backend/app.py).

Verifies the API layer is a faithful, lossless translation of the
existing simulation adapter -- it does not re-test the physics itself
(see tests/test_simulation_integration.py and friends for that). The
parity tests are the load-bearing ones here: they prove the API never
becomes a second implementation of the simulation.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from dashboard.adapters import simulation_adapter as adapter
from dashboard.adapters.protection_timeline import build_protection_timeline

client = TestClient(app)


def _timeline_to_dict(timeline) -> dict:
    """JSON-shaped dict matching `ProtectionTimelineModel`'s serialization,
    for direct comparison against a response body's `protection_timeline`.
    """
    return {
        "segments": [
            {
                "state": s.state,
                "start_time_s": s.start_time_s,
                "end_time_s": s.end_time_s,
                "duration_s": s.duration_s,
                "is_open_ended": s.is_open_ended,
            }
            for s in timeline.segments
        ],
        "events": [
            {"time_s": e.time_s, "category": e.category, "label": e.label, "cause": e.cause, "detail": e.detail}
            for e in timeline.events
        ],
        "outcome": timeline.outcome.value,
        "outcome_event_time_s": timeline.outcome_event_time_s,
        "outcome_label": timeline.outcome_label,
        "outcome_detail": timeline.outcome_detail,
        "recovery": timeline.recovery.value,
        "recovery_label": timeline.recovery_label,
        "trip_event_time_s": timeline.trip_event_time_s,
        "bus_collapse_event_time_s": timeline.bus_collapse_event_time_s,
        "coordination": {
            "result": timeline.coordination.result.value,
            "result_label": timeline.coordination.result_label,
            "result_detail": timeline.coordination.result_detail,
            "derating_preceded_terminal_event": timeline.coordination.derating_preceded_terminal_event,
            "separations": [
                {
                    "label": sep.label,
                    "from_time_s": sep.from_time_s,
                    "to_time_s": sep.to_time_s,
                    "duration_s": sep.duration_s,
                }
                for sep in timeline.coordination.separations
            ],
        },
        "coverage": [
            {"function": c.function, "modeled": c.modeled, "detail": c.detail}
            for c in timeline.coverage
        ],
    }


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

    assert set(body.keys()) == {"scenario", "thresholds", "events", "timeseries", "protection_timeline"}
    assert set(body["thresholds"].keys()) == {
        "voltage_reference_v", "rated_power_w", "thermal_derate_start_c", "thermal_trip_c",
        "capacitance_f",
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


def test_thresholds_echo_the_capacitance_actually_used() -> None:
    """The frontend computes an energy figure from thresholds.capacitance_f
    (see lib/transientMetrics.ts) -- it must reflect the override actually
    applied to the run, not always the config/default.yaml value."""
    baseline = client.post("/api/v1/simulations/load-step", json={}).json()
    assert baseline["thresholds"]["capacitance_f"] == 0.02

    overridden = client.post(
        "/api/v1/simulations/load-step", json={"capacitance_f": 0.05}
    ).json()
    assert overridden["thresholds"]["capacitance_f"] == 0.05


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
    assert api_thresholds["capacitance_f"] == direct.config.dc_bus.capacitance_f

    api_events = response.json()["events"]
    assert [(e["time_s"], e["label"]) for e in api_events] == direct.events


def test_load_step_protection_timeline_matches_direct_build() -> None:
    """AC-006/AC-007 parity: LoadStepResponse's additive `protection_timeline`
    must be identical to calling `build_protection_timeline` directly on
    the same adapter call's result."""
    direct = adapter.run_load_step()
    expected = _timeline_to_dict(build_protection_timeline(direct.telemetry, direct.config, direct.events))

    response = client.post("/api/v1/simulations/load-step", json={})
    assert response.json()["protection_timeline"] == expected


# --------------------------------------------------------------------------
# GET /api/v1/simulations/protection-scenarios/{scenario} (SPEC-008)
# --------------------------------------------------------------------------

_PROTECTION_SCENARIOS = ["sustained_high_load", "thermal_trip", "grid_sag", "grid_loss"]


def test_protection_scenario_accepts_every_valid_name() -> None:
    for scenario in _PROTECTION_SCENARIOS:
        response = client.get(f"/api/v1/simulations/protection-scenarios/{scenario}")
        assert response.status_code == 200, scenario
        body = response.json()
        assert body["scenario"] == scenario
        assert "protection_timeline" in body
        assert "thresholds" in body


def test_protection_scenario_rejects_invalid_name() -> None:
    response = client.get("/api/v1/simulations/protection-scenarios/not_a_real_scenario")
    assert response.status_code == 422


def test_protection_scenario_response_schema_shape() -> None:
    response = client.get("/api/v1/simulations/protection-scenarios/grid_sag")
    body = response.json()

    assert set(body.keys()) == {"scenario", "thresholds", "events", "timeseries", "protection_timeline"}
    assert set(body["thresholds"].keys()) == {
        "voltage_reference_v", "rated_power_w", "thermal_derate_start_c", "thermal_trip_c",
        "capacitance_f", "thermal_trip_time_s", "derate_factor_min", "floor_voltage_v",
    }
    assert set(body["protection_timeline"].keys()) == {
        "segments", "events", "outcome", "outcome_event_time_s", "outcome_label", "outcome_detail",
        "recovery", "recovery_label", "trip_event_time_s", "bus_collapse_event_time_s",
        "coordination", "coverage",
    }


@pytest.mark.parametrize(
    "scenario,adapter_fn",
    [
        ("sustained_high_load", adapter.run_sustained_high_load),
        ("thermal_trip", adapter.run_thermal_trip),
        ("grid_sag", adapter.run_grid_sag),
        ("grid_loss", adapter.run_grid_loss),
    ],
)
def test_protection_scenario_thresholds_echo_the_config_actually_used(scenario, adapter_fn) -> None:
    direct = adapter_fn()
    response = client.get(f"/api/v1/simulations/protection-scenarios/{scenario}")
    thresholds = response.json()["thresholds"]

    assert thresholds["voltage_reference_v"] == direct.config.controller.voltage_reference_v
    assert thresholds["rated_power_w"] == direct.config.sst.rated_power_w
    assert thresholds["thermal_derate_start_c"] == direct.config.protection.thermal_derate_start_c
    assert thresholds["thermal_trip_c"] == direct.config.protection.thermal_trip_c
    assert thresholds["capacitance_f"] == direct.config.dc_bus.capacitance_f
    assert thresholds["thermal_trip_time_s"] == direct.config.protection.thermal_trip_time_s
    assert thresholds["derate_factor_min"] == direct.config.protection.derate_factor_min


@pytest.mark.parametrize(
    "scenario,adapter_fn,reconciled_input_events",
    [
        ("sustained_high_load", adapter.run_sustained_high_load, None),
        ("thermal_trip", adapter.run_thermal_trip, []),
        ("grid_sag", adapter.run_grid_sag, None),
        ("grid_loss", adapter.run_grid_loss, None),
    ],
)
def test_protection_scenario_timeline_matches_direct_build(
    scenario, adapter_fn, reconciled_input_events
) -> None:
    """AC-006 parity: `protection_timeline` is identical to calling
    `build_protection_timeline` directly on that same adapter call's
    result (with the §11-reconciled `input_events`)."""
    direct = adapter_fn()
    input_events = direct.events if reconciled_input_events is None else reconciled_input_events
    expected = _timeline_to_dict(build_protection_timeline(direct.telemetry, direct.config, input_events))

    response = client.get(f"/api/v1/simulations/protection-scenarios/{scenario}")
    assert response.json()["protection_timeline"] == expected


def test_protection_scenario_thermal_trip_excludes_protection_derived_input_events() -> None:
    """AC-016, at the API boundary: Thermal Trip's returned Protection
    Timeline contains no `input_event` entry copied from the adapter's
    own protection-derived markers ("derating begins", "TRIPPED")."""
    response = client.get("/api/v1/simulations/protection-scenarios/thermal_trip")
    timeline = response.json()["protection_timeline"]
    input_labels = {e["label"] for e in timeline["events"] if e["category"] == "input_event"}
    assert "derating begins" not in input_labels
    assert "TRIPPED" not in input_labels


def test_protection_scenario_grid_sag_includes_genuine_input_events() -> None:
    """AC-016, at the API boundary: Grid Sag's genuine load/grid-input
    markers appear unchanged in the returned Protection Timeline."""
    direct = adapter.run_grid_sag()
    response = client.get("/api/v1/simulations/protection-scenarios/grid_sag")
    timeline = response.json()["protection_timeline"]
    input_labels = [e["label"] for e in timeline["events"] if e["category"] == "input_event"]
    assert input_labels == [label for _, label in direct.events]
