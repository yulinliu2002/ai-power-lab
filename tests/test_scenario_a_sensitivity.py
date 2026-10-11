"""Fixture-based trend regressions for the Scenario A sensitivity study
(SPEC-002, AC-011).

These are regressions against NAMED, deterministic fixtures -- the same
5-point grid the frontend sweep uses (min + i*(max-min)/4 over the
existing 0.005..0.08 range). They are not a claim that the trend holds
for every possible controller/protection/model configuration.

Every point goes through the same `adapter.run_load_step` the API calls;
nothing here re-implements the engine. The metric reductions below
(minimum V_dc, maximum |V_dc - V_ref| from the load step onward) mirror
`frontend/app/lib/transientMetrics.ts` and exist only to read the
adapter's output.
"""

from __future__ import annotations

from dashboard.adapters import simulation_adapter as adapter
from backend.schemas import LoadStepRequest
from src.config import load_config

# Existing slider/API bounds (ExperimentPanel.tsx CAPACITANCE_RANGE /
# TIME_CONSTANT_RANGE; backend/schemas.py LoadStepRequest) -- not new ranges.
RANGE_MIN = 0.005
RANGE_MAX = 0.08

SWEEP_GRID = [RANGE_MIN + i * (RANGE_MAX - RANGE_MIN) / 4 for i in range(5)]

# Held fixed across each sweep (the baseline experiment values).
FIXED_TIME_CONSTANT_S = 0.02
FIXED_CAPACITANCE_F = 0.02
FIXED_FINAL_FRACTION = 0.8

CAPACITANCE_FIXTURES_F = SWEEP_GRID
TIME_CONSTANT_FIXTURES_S = SWEEP_GRID


def _bounds(field_name: str) -> tuple[float, float]:
    metadata = LoadStepRequest.model_fields[field_name].metadata
    ge = next(m.ge for m in metadata if hasattr(m, "ge"))
    le = next(m.le for m in metadata if hasattr(m, "le"))
    return ge, le


def test_fixture_constants_match_authoritative_declarations() -> None:
    """AC-011: the bounds/baseline above are copies, not a second source
    of truth. If `backend/schemas.py` (the API's approved range) or
    `config/default.yaml` (the baseline this module holds fixed) ever
    changes, this fails loudly instead of letting the fixture silently
    drift from what it claims to test.
    """
    assert _bounds("capacitance_f") == (RANGE_MIN, RANGE_MAX)
    assert _bounds("time_constant_s") == (RANGE_MIN, RANGE_MAX)
    assert LoadStepRequest.model_fields["final_fraction"].default == FIXED_FINAL_FRACTION

    config = load_config("config/default.yaml")
    assert config.dc_bus.capacitance_f == FIXED_CAPACITANCE_F
    assert config.sst.time_constant_s == FIXED_TIME_CONSTANT_S


def _severity(**overrides: float) -> tuple[float, float]:
    """(minimum V_dc, maximum |V_dc - V_ref|) from the load step onward."""
    result = adapter.run_load_step(final_fraction=FIXED_FINAL_FRACTION, **overrides)
    step_time_s = result.events[0][0]
    v_ref = result.config.controller.voltage_reference_v
    t = result.telemetry
    after = t.time_s >= step_time_s
    v = t.v_dc_v[after]
    return float(v.min()), float(abs(v - v_ref).max())


def test_sweep_grid_fixture_matches_spec_and_stays_in_bounds() -> None:
    assert len(SWEEP_GRID) == 5
    assert SWEEP_GRID[0] == RANGE_MIN
    assert abs(SWEEP_GRID[4] - RANGE_MAX) < 1e-12
    assert abs(SWEEP_GRID[2] - 0.0425) < 1e-12


def test_capacitance_sweep_fixtures_trend() -> None:
    """More C_dc: minimum V_dc non-decreasing, max deviation non-increasing."""
    points = [
        _severity(capacitance_f=c, time_constant_s=FIXED_TIME_CONSTANT_S)
        for c in CAPACITANCE_FIXTURES_F
    ]
    min_v = [p[0] for p in points]
    max_dev = [p[1] for p in points]
    for a, b in zip(min_v, min_v[1:]):
        assert b >= a
    for a, b in zip(max_dev, max_dev[1:]):
        assert b <= a


def test_time_constant_sweep_fixtures_trend() -> None:
    """Slower SST: minimum V_dc non-increasing, max deviation non-decreasing."""
    points = [
        _severity(capacitance_f=FIXED_CAPACITANCE_F, time_constant_s=tau)
        for tau in TIME_CONSTANT_FIXTURES_S
    ]
    min_v = [p[0] for p in points]
    max_dev = [p[1] for p in points]
    for a, b in zip(min_v, min_v[1:]):
        assert b <= a
    for a, b in zip(max_dev, max_dev[1:]):
        assert b >= a


def test_sweep_does_not_mutate_shared_config() -> None:
    """AC-010: running sweep points leaves a later baseline unchanged."""
    before = adapter.run_load_step()
    for c in CAPACITANCE_FIXTURES_F:
        adapter.run_load_step(capacitance_f=c)
    after = adapter.run_load_step()
    assert after.telemetry.v_dc_v.tolist() == before.telemetry.v_dc_v.tolist()
