"""Cross-scenario stress comparison over already-run scenarios (SPEC-010).

Governing equations (none new -- see module-level note below)
---------------------------------------------------------------
Every field this module produces is one of:

  - A whole-run reduction (min/max/any) over an already-computed
    `Telemetry` array -- the same class of computation
    `dashboard/adapters/simulation_adapter.py::summary_metrics` already
    performs, extended with units/applicability documentation (SPEC-010
    §0/§5).
  - A read-through of an already-computed `ProtectionTimeline` field
    (SPEC-008/009) -- never a re-derivation of `outcome`, `recovery`,
    or `coordination`.
  - One call to `src.dc_bus.energy_from_voltage` (the engine's own
    existing pure function, `E = 0.5 * C_dc * V_dc^2`) to obtain the
    nominal DC-link energy at `voltage_reference_v`, compared against
    `min(telemetry.e_dc_j)` -- the engine's own already-integrated
    energy state. This module performs no new physical equation and no
    re-simulation.
  - A fixed, deterministic, four-branch decision tree (`dominant_stress`,
    SPEC-010 §6) over two already-authoritative categorical
    `ProtectionTimeline` fields (`outcome`, whether any segment reached
    `DERATED`) -- never an invented weighted score.

Units: SI throughout, matching `src/telemetry.py` and `src/config.py`
exactly. `dc_link_energy_excursion_j` is in joules [J];
`max_voltage_deviation_percent` is the one field expressed as a
percentage [%] rather than SI, mirroring
`frontend/app/lib/transientMetrics.ts`'s existing convention for the
same ratio.

Assumptions
-----------
- `telemetry`/`config` were produced by `src.simulation.run_simulation`
  (or an equivalent producer with the same per-step causality); this
  module only reads them.
- `timeline` is the `ProtectionTimeline` already computed for this same
  `telemetry`/`config` pair by `build_protection_timeline` -- this
  module never calls `build_protection_timeline` itself, so there is
  exactly one place in the codebase that classifies `outcome`/
  `coordination` (SPEC-010 §7, AC-043).

Limitations
-----------
- `dc_link_energy_excursion_j` is a snapshot of maximum observed
  depletion relative to nominal, not a measure of ongoing unmet energy
  demand -- see SPEC-010 §11. It saturates at the same numerical floor
  for every run whose stored energy reaches `config.dc_bus.min_energy_j`,
  so multiple scenarios may report the identical value despite different
  continuing deficits after that point.
- `dominant_stress` collapses `outcome == BUS_COLLAPSE_UNPROTECTED` into
  one category regardless of whether a grid disturbance or a thermal
  exhaustion caused it -- that distinction remains readable from the
  same row's `trip_event_time_s`/`coordination.result`/
  `grid_ever_unavailable` fields (SPEC-010 §6/§11).
- This module performs no numerical integration and has no stateful
  simulation of its own; it is a pure, deterministic function of an
  already-computed `Telemetry` + `Config` + `ProtectionTimeline`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from src.config import Config
from src.dc_bus import energy_from_voltage
from src.telemetry import Telemetry

from .protection_timeline import ProtectionTimeline, RideThroughOutcome


class DominantStress(Enum):
    DC_BUS_VIABILITY_LOSS = "DC_BUS_VIABILITY_LOSS"
    THERMAL_PROTECTION_TRIP = "THERMAL_PROTECTION_TRIP"
    SUSTAINED_THERMAL_DERATING = "SUSTAINED_THERMAL_DERATING"
    TRANSIENT_POWER_IMBALANCE = "TRANSIENT_POWER_IMBALANCE"


@dataclass(frozen=True)
class StressProfile:
    """One run's whole-series stress reductions plus its dominant-stress
    classification (SPEC-010 §5/§7). Every field is documented in SPEC-010
    §5's metric catalog; none is null -- every field below has a defined
    value for every one of the five fixed scenarios (§5's "Null/missing
    semantics" column).
    """

    min_v_dc_v: float
    max_v_dc_v: float
    max_voltage_deviation_v: float
    max_voltage_deviation_percent: float
    peak_power_deficit_w: float
    dc_link_energy_excursion_j: float
    max_temperature_c: float
    grid_ever_unavailable: bool
    min_grid_voltage_pu: float
    protection_states_reached: tuple[str, ...]
    dominant_stress: DominantStress
    dominant_stress_label: str
    dominant_stress_detail: str


_DOMINANT_STRESS_LABELS = {
    DominantStress.DC_BUS_VIABILITY_LOSS: "DC-bus viability lost",
    DominantStress.THERMAL_PROTECTION_TRIP: "Thermal protection tripped",
    DominantStress.SUSTAINED_THERMAL_DERATING: "Sustained thermal derating",
    DominantStress.TRANSIENT_POWER_IMBALANCE: "Transient power imbalance only",
}


def _protection_states_reached(timeline: ProtectionTimeline) -> tuple[str, ...]:
    """Distinct `segments[*].state` values in first-occurrence order
    (SPEC-010 §5) -- an index scan over the already-computed segments,
    no telemetry scan of its own.
    """
    seen: list[str] = []
    for segment in timeline.segments:
        if segment.state not in seen:
            seen.append(segment.state)
    return tuple(seen)


def _classify_dominant_stress(
    outcome: RideThroughOutcome, protection_states_reached: tuple[str, ...]
) -> DominantStress:
    """SPEC-010 §6's fixed, total, four-branch decision tree -- evaluated
    top to bottom, over `outcome` and whether `DERATED` was ever reached.
    """
    if outcome is RideThroughOutcome.BUS_COLLAPSE_UNPROTECTED:
        return DominantStress.DC_BUS_VIABILITY_LOSS
    if outcome is RideThroughOutcome.PROTECTION_TRIP:
        return DominantStress.THERMAL_PROTECTION_TRIP
    if "DERATED" in protection_states_reached:
        return DominantStress.SUSTAINED_THERMAL_DERATING
    return DominantStress.TRANSIENT_POWER_IMBALANCE


def _describe_dominant_stress(
    dominant_stress: DominantStress, timeline: ProtectionTimeline
) -> tuple[str, str]:
    """Backend-owned, plain-English, traceable label/detail (SPEC-010
    §6), following `protection_timeline.py`'s existing
    `_OUTCOME_LABELS`/`_describe_outcome` pattern exactly -- never
    inventing justification language beyond what `timeline` already
    determined.
    """
    label = _DOMINANT_STRESS_LABELS[dominant_stress]

    if dominant_stress is DominantStress.DC_BUS_VIABILITY_LOSS:
        assert timeline.bus_collapse_event_time_s is not None
        detail = (
            "outcome == BUS_COLLAPSE_UNPROTECTED (ProtectionTimeline, SPEC-008): the DC bus "
            f"reached its numerical energy floor at t = {timeline.bus_collapse_event_time_s:.3f} s."
        )
    elif dominant_stress is DominantStress.THERMAL_PROTECTION_TRIP:
        assert timeline.trip_event_time_s is not None
        # Mirrors `protection_timeline.py::_describe_outcome`'s own
        # three-way relation wording for PROTECTION_TRIP exactly (SPEC-008
        # §9's non-causal tie-break convention) -- the tie case must never
        # say "before" either, since a same-sample coincidence reflects two
        # conditions that became true independently, not one causing the
        # other.
        if timeline.bus_collapse_event_time_s is None:
            relation = "the DC bus's numerical energy floor was never reached"
        elif timeline.trip_event_time_s == timeline.bus_collapse_event_time_s:
            relation = (
                "the DC bus's numerical energy floor was reached at the exact same sample "
                "(a tie, resolved toward PROTECTION_TRIP by an explicit, non-causal convention "
                "-- not because the trip caused the floor contact)"
            )
        else:
            relation = "before the DC bus's numerical energy floor was reached"
        detail = (
            "outcome == PROTECTION_TRIP (ProtectionTimeline, SPEC-008): thermal protection "
            f"latched TRIPPED at t = {timeline.trip_event_time_s:.3f} s, {relation}."
        )
    elif dominant_stress is DominantStress.SUSTAINED_THERMAL_DERATING:
        detail = (
            "outcome == RIDE_THROUGH with at least one DERATED segment "
            "(ProtectionTimeline.outcome/segments, SPEC-008/009): sustained thermal load pushed "
            "the system into derating without losing DC-bus viability or latching TRIPPED."
        )
    else:
        detail = (
            "outcome == RIDE_THROUGH with no DERATED segment reached "
            "(ProtectionTimeline.outcome/segments, SPEC-008/009): the system rode through the "
            "disturbance without any modeled protection-state change."
        )

    return label, detail


def build_stress_profile(
    telemetry: Telemetry,
    config: Config,
    timeline: ProtectionTimeline,
) -> StressProfile:
    """Derive one run's `StressProfile` from its already-computed
    `Telemetry` + `Config` + `ProtectionTimeline`.

    Args:
        telemetry: a completed simulation run's Telemetry.
        config: the Config that run actually used.
        timeline: the `ProtectionTimeline` already built for this same
            run (via `build_protection_timeline`) -- not re-derived
            here (AC-043).

    Returns:
        A `StressProfile`.
    """
    v = telemetry.v_dc_v
    voltage_reference_v = config.controller.voltage_reference_v

    min_v_dc_v = float(v.min())
    max_v_dc_v = float(v.max())
    max_voltage_deviation_v = float(np.abs(v - voltage_reference_v).max())
    max_voltage_deviation_percent = max_voltage_deviation_v / voltage_reference_v * 100.0

    power_mismatch_w = telemetry.p_load_w - telemetry.p_sst_w
    peak_power_deficit_w = float(np.maximum(power_mismatch_w, 0.0).max())

    nominal_energy_j = energy_from_voltage(voltage_reference_v, config.dc_bus.capacitance_f)
    dc_link_energy_excursion_j = max(0.0, nominal_energy_j - float(telemetry.e_dc_j.min()))

    max_temperature_c = float(telemetry.temperature_c.max())
    grid_ever_unavailable = bool((~telemetry.grid_available).any())
    min_grid_voltage_pu = float(telemetry.grid_voltage_pu.min())

    protection_states_reached = _protection_states_reached(timeline)
    dominant_stress = _classify_dominant_stress(timeline.outcome, protection_states_reached)
    dominant_stress_label, dominant_stress_detail = _describe_dominant_stress(
        dominant_stress, timeline
    )

    return StressProfile(
        min_v_dc_v=min_v_dc_v,
        max_v_dc_v=max_v_dc_v,
        max_voltage_deviation_v=max_voltage_deviation_v,
        max_voltage_deviation_percent=max_voltage_deviation_percent,
        peak_power_deficit_w=peak_power_deficit_w,
        dc_link_energy_excursion_j=dc_link_energy_excursion_j,
        max_temperature_c=max_temperature_c,
        grid_ever_unavailable=grid_ever_unavailable,
        min_grid_voltage_pu=min_grid_voltage_pu,
        protection_states_reached=protection_states_reached,
        dominant_stress=dominant_stress,
        dominant_stress_label=dominant_stress_label,
        dominant_stress_detail=dominant_stress_detail,
    )
