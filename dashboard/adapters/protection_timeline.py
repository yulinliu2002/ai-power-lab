"""Derived Protection & Ride-Through Timeline over an already-run scenario.

Governing logic (not new physics -- see SPEC-008)
--------------------------------------------------
This module computes no new physical quantity. Every value it produces
is one of:

  - A run-length encoding of `telemetry.operating_state` into
    contiguous `StateSegment`s (§8).
  - A reconciled, chronological list of `TimelineEvent`s: protection
    state transitions (derived from `operating_state`/`temperature_c`/
    `trip_active`/`trip_reason`), bus-energy numerical-floor
    entries/exits (derived from `v_dc_v` vs. the existing numerical
    floor voltage, `src.dc_bus.voltage_from_energy` applied to
    `config.dc_bus`), and genuine load/grid input markers the caller
    passes in verbatim (`input_events`).
  - A three-way `outcome` classification (`RIDE_THROUGH` /
    `PROTECTION_TRIP` / `BUS_COLLAPSE_UNPROTECTED`) by comparing which
    of two already-derived terminal-event times occurs first (§9).
  - A separate `recovery` classification, reusing the exact ±1%
    settling-band scan `frontend/app/lib/transientMetrics.ts` already
    implements for Scenario A, ported here and applied over the whole
    run rather than anchored to one event.

Units: inputs/outputs are SI, matching `src/telemetry.py` and
`src/config.py` exactly. `StateSegment`/`TimelineEvent` times and
durations are seconds [s]; temperatures are degC; voltages are V.

Assumptions
-----------
- `telemetry` was produced by `src.simulation.run_simulation` (or an
  equivalent producer with the same per-step causality); this module
  only reads it, it never re-simulates anything.
- The bus-energy numerical floor tolerance (`<= floor_v + 0.5`) matches
  `scenarios/plotting.py:plot_voltage`'s existing convention exactly,
  so a "bus energy at numerical floor" event here always agrees with
  that plot's shaded region.
- The same-sample tie-break in `outcome`'s classification (§9) is an
  explicit, arbitrary, non-causal convention, not a claim that one
  condition causes the other -- see `_classify_outcome`'s docstring.

Limitations
-----------
- `RUNNING`/`DERATED`/`TRIPPED` remain the sole authoritative output of
  `src/protection.py`; the bus-energy-floor event this module adds is a
  derived observation of an existing numerical safeguard, never a new
  protection action (`src/protection.py` knows nothing about it).
- `recovery`'s binary (`RECOVERED`/`NOT_RECOVERED`) granularity is a
  stated, open limitation (SPEC-008 §15 item 2) -- no existing
  repository-authoritative tolerance distinguishes a "partial"
  recovery, so this module does not invent one.
- This module performs no numerical integration and has no stateful
  simulation of its own; it is a pure, deterministic function of an
  already-computed `Telemetry` + `Config`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from src.config import Config
from src.dc_bus import voltage_from_energy
from src.telemetry import Telemetry

#: One labeled instant in a run, exactly as `simulation_adapter.ScenarioResult.events`
#: and `scenarios/plotting.py` already define it -- not redefined as a new type here.
EventMarkers = list[tuple[float, str]]

#: Tolerance matching `scenarios/plotting.py:plot_voltage`'s existing
#: "at the numerical floor" shading convention exactly.
_BUS_FLOOR_TOLERANCE_V = 0.5

#: ±1% of V_ref -- the exact settling-band fraction
#: `frontend/app/lib/transientMetrics.ts` already uses ("the standard
#: engineering settling-time criterion"), ported here rather than
#: invented fresh (SPEC-008 §9).
_RECOVERY_BAND_FRACTION = 0.01


@dataclass(frozen=True)
class StateSegment:
    """A maximal run of consecutive samples sharing one `operating_state`.

    `end_time_s` of every segment except the last is the timestamp of
    the *next* segment's first sample (the transition instant), so
    segment durations for one run sum exactly to
    `telemetry.time_s[-1] - telemetry.time_s[0]` (SPEC-008 §10). The
    last segment's `end_time_s` is the run's final sample time, never
    extrapolated.
    """

    state: str  # "RUNNING" | "DERATED" | "TRIPPED" -- authoritative
    # src/protection.py output only.
    start_time_s: float
    end_time_s: float
    duration_s: float
    is_open_ended: bool


@dataclass(frozen=True)
class TimelineEvent:
    """One point-in-time entry in the Protection Timeline's event list.

    `cause` is a short, fixed categorical tag naming which of SPEC-008
    §6's three authoritative cause kinds applies
    ("config_threshold_crossing" | "debounce_condition" |
    "numerical_safeguard_contact"), or "" for a genuine `input_event`
    (which is already fully labeled and has no derived "cause" of its
    own). `detail` is the full config/telemetry-traceable human-
    readable text; for a `protection_state` event transitioning to
    `TRIPPED`, `detail` contains the exact `telemetry.trip_reason`
    value verbatim (AC-017).
    """

    time_s: float
    category: str  # "protection_state" | "input_event" | "bus_energy"
    label: str
    cause: str
    detail: str


class RideThroughOutcome(Enum):
    RIDE_THROUGH = "RIDE_THROUGH"
    PROTECTION_TRIP = "PROTECTION_TRIP"
    BUS_COLLAPSE_UNPROTECTED = "BUS_COLLAPSE_UNPROTECTED"


class RecoveryStatus(Enum):
    RECOVERED = "RECOVERED"
    NOT_RECOVERED = "NOT_RECOVERED"
    NOT_APPLICABLE = "NOT_APPLICABLE"  # outcome == PROTECTION_TRIP only, §9


class CoordinationResult(Enum):
    """SPEC-009 §6 -- a fixed, five-member, non-causal classification of
    the ordering of `trip_event_time_s` and `bus_collapse_event_time_s`.
    Strictly more granular than `RideThroughOutcome`: it is the one
    place that also records whether protection ever acted at all, even
    when it acted after an already-determined bus collapse.
    """

    NO_TERMINAL_EVENT = "NO_TERMINAL_EVENT"
    PROTECTION_ACTED_NO_VIABILITY_LOSS = "PROTECTION_ACTED_NO_VIABILITY_LOSS"
    PROTECTION_ACTED_BEFORE_VIABILITY_LOSS = "PROTECTION_ACTED_BEFORE_VIABILITY_LOSS"
    VIABILITY_LOST_NO_PROTECTION_ACTION = "VIABILITY_LOST_NO_PROTECTION_ACTION"
    VIABILITY_LOST_BEFORE_PROTECTION_ACTION = "VIABILITY_LOST_BEFORE_PROTECTION_ACTION"


@dataclass(frozen=True)
class EventSeparation:
    """One non-negative time interval between two named events (SPEC-009
    §6.1). `label` states the chronological direction except for the
    one tied case, where it is a fixed, non-directional label and
    `duration_s == 0.0`.
    """

    label: str
    from_time_s: float
    to_time_s: float
    duration_s: float


@dataclass(frozen=True)
class CoordinationAnalysis:
    """SPEC-009 §6 -- derived, additive classification of the two
    already-computed terminal-event candidate times. Adds no new
    telemetry scan and no new physical quantity.
    """

    result: CoordinationResult
    result_label: str  # backend-owned, verbatim (SPEC-009 §8)
    result_detail: str  # backend-owned, verbatim (SPEC-009 §8)
    derating_preceded_terminal_event: bool | None
    separations: tuple[EventSeparation, ...]


@dataclass(frozen=True)
class CoverageEntry:
    """One row of the static protection-coverage matrix (SPEC-009 §5)."""

    function: str
    modeled: bool
    detail: str


#: Static, run-independent fact about `src/protection.py`'s
#: implementation (SPEC-009 §5) -- the same five rows for every run.
#: Every `modeled=False` row traces to a sentence already in
#: `src/protection.py`'s own docstring or to the literal absence of a
#: corresponding parameter/branch there -- never inferred from a
#: particular scenario's telemetry, and never a claim about real
#: hardware.
PROTECTION_COVERAGE: tuple[CoverageEntry, ...] = (
    CoverageEntry(
        function="Sustained thermal overtemperature",
        modeled=True,
        detail="src/protection.py: debounced (thermal_trip_time_s), latched TRIPPED state.",
    ),
    CoverageEntry(
        function="DC-bus undervoltage",
        modeled=False,
        detail=(
            "No voltage-based trip exists in src/protection.py. The numerical energy floor "
            "(dashboard bus_energy events) is an observation of src/dc_bus.py's energy "
            "floor, never a protection action."
        ),
    ),
    CoverageEntry(
        function="DC-bus overvoltage",
        modeled=False,
        detail="Same basis as DC-bus undervoltage: no voltage-based trip of any kind exists.",
    ),
    CoverageEntry(
        function="Automatic trip reset",
        modeled=False,
        detail=(
            "src/protection.py's own module docstring: 'No reset mechanism... TRIPPED state "
            "stays TRIPPED for the rest of the scenario.'"
        ),
    ),
    CoverageEntry(
        function="Grid-availability-based protection",
        modeled=False,
        detail=(
            "No grid_available-driven protection logic exists in src/protection.py; "
            "grid loss is handled only as a load/source condition in src/simulation.py."
        ),
    ),
)


@dataclass(frozen=True)
class ProtectionTimeline:
    segments: tuple[StateSegment, ...]
    events: tuple[TimelineEvent, ...]
    outcome: RideThroughOutcome
    outcome_event_time_s: float | None  # the terminal-event time that
    # determined `outcome`; None for RIDE_THROUGH.
    outcome_label: str  # backend-owned plain-English label -- frontend
    # reads verbatim.
    outcome_detail: str  # backend-owned, traceable explanation --
    # frontend reads verbatim.
    recovery: RecoveryStatus
    recovery_label: str  # backend-owned plain-English label --
    # frontend reads verbatim.
    trip_event_time_s: float | None  # SPEC-009 §3 -- the first
    # `trip_active=True` sample, exposed from `_classify_outcome`'s own
    # internal computation; None if the run never trips.
    bus_collapse_event_time_s: float | None  # SPEC-009 §3 -- the first
    # numerical-floor-contact sample, exposed from `_classify_outcome`'s
    # own internal computation; None if the bus never reaches the floor.
    coordination: CoordinationAnalysis  # SPEC-009 §6.
    coverage: tuple[CoverageEntry, ...]  # SPEC-009 §5 -- always
    # `PROTECTION_COVERAGE`, attached per-run for presentation
    # uniformity only (static, identical across every call).


def build_protection_timeline(
    telemetry: Telemetry,
    config: Config,
    input_events: EventMarkers,
) -> ProtectionTimeline:
    """Derive the Protection & Ride-Through Timeline for one run.

    Args:
        telemetry: a completed simulation run's Telemetry.
        config: the Config that run actually used.
        input_events: genuine load/grid-input markers only -- the
            caller is responsible for excluding any adapter-provided
            marker that is itself derived from `operating_state`/
            `derate_factor`/`trip_active` (SPEC-008 §11's
            reconciliation rule); this function performs no filtering
            of its own and merges whatever it is given.

    Returns:
        A `ProtectionTimeline`.

    Raises:
        ValueError: if `telemetry` has zero samples.
    """
    n = len(telemetry.time_s)
    if n < 1:
        raise ValueError("build_protection_timeline requires at least one telemetry sample")

    segments = _build_segments(telemetry)
    protection_events = _build_protection_state_events(telemetry, config)
    floor_v = voltage_from_energy(config.dc_bus.min_energy_j, config.dc_bus.capacitance_f)
    bus_energy_events = _build_bus_energy_events(telemetry, floor_v)
    input_timeline_events = tuple(
        TimelineEvent(time_s=float(t), category="input_event", label=label, cause="", detail="")
        for t, label in input_events
    )
    events = tuple(
        sorted(
            (*input_timeline_events, *protection_events, *bus_energy_events),
            key=lambda e: e.time_s,
        )
    )

    trip_event_time_s = _first_true_time(telemetry.trip_active, telemetry.time_s)
    bus_collapse_event_time_s = _first_floor_contact_time(telemetry, floor_v)

    outcome, outcome_event_time_s = _classify_outcome(
        trip_event_time_s, bus_collapse_event_time_s
    )
    outcome_label, outcome_detail = _describe_outcome(
        outcome, outcome_event_time_s, trip_event_time_s, bus_collapse_event_time_s
    )

    recovery = _classify_recovery(telemetry, outcome, config.controller.voltage_reference_v)
    recovery_label = _RECOVERY_LABELS[recovery]

    coordination = classify_coordination(
        trip_event_time_s, bus_collapse_event_time_s, segments, outcome_event_time_s
    )

    return ProtectionTimeline(
        segments=segments,
        events=events,
        outcome=outcome,
        outcome_event_time_s=outcome_event_time_s,
        outcome_label=outcome_label,
        outcome_detail=outcome_detail,
        recovery=recovery,
        recovery_label=recovery_label,
        trip_event_time_s=trip_event_time_s,
        bus_collapse_event_time_s=bus_collapse_event_time_s,
        coordination=coordination,
        coverage=PROTECTION_COVERAGE,
    )


def _build_segments(telemetry: Telemetry) -> tuple[StateSegment, ...]:
    states = telemetry.operating_state
    times = telemetry.time_s
    n = len(times)

    segments: list[StateSegment] = []
    start_idx = 0
    for i in range(1, n):
        if states[i] != states[start_idx]:
            segments.append(
                StateSegment(
                    state=str(states[start_idx]),
                    start_time_s=float(times[start_idx]),
                    end_time_s=float(times[i]),
                    duration_s=float(times[i] - times[start_idx]),
                    is_open_ended=False,
                )
            )
            start_idx = i

    segments.append(
        StateSegment(
            state=str(states[start_idx]),
            start_time_s=float(times[start_idx]),
            end_time_s=float(times[-1]),
            duration_s=float(times[-1] - times[start_idx]),
            is_open_ended=True,
        )
    )
    return tuple(segments)


def _build_protection_state_events(telemetry: Telemetry, config: Config) -> tuple[TimelineEvent, ...]:
    """One `category="protection_state"` event at each segment boundary.

    Every cause string is a lookup against `telemetry`/`config` fields
    already produced upstream, never inferred from a chart's shape
    (SPEC-008 §6).
    """
    states = telemetry.operating_state
    times = telemetry.time_s
    temps = telemetry.temperature_c
    trip_reasons = telemetry.trip_reason
    n = len(times)

    derate_start_c = config.protection.thermal_derate_start_c
    trip_c = config.protection.thermal_trip_c
    trip_time_s = config.protection.thermal_trip_time_s

    events: list[TimelineEvent] = []
    prev_idx = 0
    for i in range(1, n):
        if states[i] == states[prev_idx]:
            continue
        new_state = str(states[i])
        temperature_c = float(temps[i])

        if new_state == "DERATED":
            label = "DERATED begins"
            cause = "config_threshold_crossing"
            detail = (
                f"DERATED begins — temperature_c ({temperature_c:.1f} °C) crossed "
                f"thermal_derate_start_c ({derate_start_c} °C)"
            )
        elif new_state == "RUNNING":
            label = "RUNNING resumes"
            cause = "config_threshold_crossing"
            detail = (
                f"RUNNING resumes — temperature_c ({temperature_c:.1f} °C) dropped back "
                f"below thermal_derate_start_c ({derate_start_c} °C)"
            )
        elif new_state == "TRIPPED":
            trip_reason = str(trip_reasons[i])
            label = "TRIPPED"
            cause = "debounce_condition"
            detail = (
                f"TRIPPED — trip_reason: {trip_reason}; thermal_trip_time_s "
                f"({trip_time_s} s) elapsed while temperature_c stayed at/above "
                f"thermal_trip_c ({trip_c} °C)"
            )
        else:  # pragma: no cover - exhaustive over OperatingState in practice
            label = f"{new_state} begins"
            cause = "config_threshold_crossing"
            detail = f"{new_state} begins — temperature_c ({temperature_c:.1f} °C)"

        events.append(
            TimelineEvent(
                time_s=float(times[i]), category="protection_state", label=label, cause=cause, detail=detail
            )
        )
        prev_idx = i

    return tuple(events)


def _build_bus_energy_events(telemetry: Telemetry, floor_v: float) -> tuple[TimelineEvent, ...]:
    """One entry/exit `category="bus_energy"` pair per contiguous
    numerical-floor excursion (SPEC-008 §8) -- a general run-length
    encoding over the floor-contact boolean, not a single-shot
    detector. An excursion still active at the run's end produces an
    entry event with no matching exit event; that absence *is* the
    open-ended signal (no duration/end-time/is_open_ended field is
    added to `TimelineEvent` for this).
    """
    v = telemetry.v_dc_v
    times = telemetry.time_s
    n = len(v)
    at_floor = v <= (floor_v + _BUS_FLOOR_TOLERANCE_V)

    events: list[TimelineEvent] = []
    i = 0
    while i < n:
        if not at_floor[i]:
            i += 1
            continue
        entry_idx = i
        j = i
        while j < n and at_floor[j]:
            j += 1
        events.append(
            TimelineEvent(
                time_s=float(times[entry_idx]),
                category="bus_energy",
                label="bus energy at numerical floor",
                cause="numerical_safeguard_contact",
                detail=(
                    f"v_dc_v ({float(v[entry_idx]):.1f} V) reached the numerical floor voltage "
                    f"({floor_v:.1f} V, from config.dc_bus.min_energy_j/capacitance_f) -- V1 has "
                    "no DC-bus undervoltage protection; this is a numerical safeguard, not a "
                    "protection trip"
                ),
            )
        )
        if j < n:
            events.append(
                TimelineEvent(
                    time_s=float(times[j]),
                    category="bus_energy",
                    label="bus energy recovers",
                    cause="numerical_safeguard_contact",
                    detail=(
                        f"v_dc_v ({float(v[j]):.1f} V) rose back above the numerical floor "
                        f"voltage ({floor_v:.1f} V)"
                    ),
                )
            )
        i = j

    return tuple(events)


def _first_true_time(flags: np.ndarray, times: np.ndarray) -> float | None:
    if not flags.any():
        return None
    return float(times[flags.argmax()])


def _first_floor_contact_time(telemetry: Telemetry, floor_v: float) -> float | None:
    at_floor = telemetry.v_dc_v <= (floor_v + _BUS_FLOOR_TOLERANCE_V)
    return _first_true_time(at_floor, telemetry.time_s)


def _classify_outcome(
    trip_event_time_s: float | None,
    bus_collapse_event_time_s: float | None,
) -> tuple[RideThroughOutcome, float | None]:
    """Ordered-terminal-event classification (SPEC-008 §9, Engineering
    Lead Decision 2/3) -- never final-state inspection, and a later
    event never retroactively changes an earlier-determined outcome.

    The `<=` tie-break below is an explicit, arbitrary, non-causal
    convention applied only when both candidate times are exactly
    equal: per `src/simulation.py`'s documented step order, a trip's
    own effect on `v_dc_v` propagates through two separate numerical
    lags (the SST's first-order power-response lag, then the bus's own
    energy-integration step) and is visible no earlier than two
    recorded samples after the sample where `trip_active` first reads
    `True` -- never at that same sample. A same-sample coincidence
    therefore reflects two conditions that became true independently,
    not one causing the other; the convention exists only to make the
    classification total and deterministic for that edge case.
    """
    if trip_event_time_s is not None and (
        bus_collapse_event_time_s is None or trip_event_time_s <= bus_collapse_event_time_s
    ):
        return RideThroughOutcome.PROTECTION_TRIP, trip_event_time_s
    if bus_collapse_event_time_s is not None and (
        trip_event_time_s is None or bus_collapse_event_time_s < trip_event_time_s
    ):
        return RideThroughOutcome.BUS_COLLAPSE_UNPROTECTED, bus_collapse_event_time_s
    return RideThroughOutcome.RIDE_THROUGH, None


_OUTCOME_LABELS = {
    RideThroughOutcome.RIDE_THROUGH: "Rode through cleanly",
    RideThroughOutcome.PROTECTION_TRIP: "Thermal protection tripped",
    RideThroughOutcome.BUS_COLLAPSE_UNPROTECTED: "Bus energy exhausted — unprotected",
}

_RECOVERY_LABELS = {
    RecoveryStatus.RECOVERED: "Recovered to nominal",
    RecoveryStatus.NOT_RECOVERED: "Did not recover",
    RecoveryStatus.NOT_APPLICABLE: "Not applicable — TRIPPED is latched",
}


def _describe_outcome(
    outcome: RideThroughOutcome,
    outcome_event_time_s: float | None,
    trip_event_time_s: float | None,
    bus_collapse_event_time_s: float | None,
) -> tuple[str, str]:
    label = _OUTCOME_LABELS[outcome]

    if outcome is RideThroughOutcome.RIDE_THROUGH:
        detail = (
            "Neither thermal protection latched TRIPPED nor the DC bus's numerical energy "
            "floor was reached at any point during this run."
        )
    elif outcome is RideThroughOutcome.PROTECTION_TRIP:
        assert outcome_event_time_s is not None
        if bus_collapse_event_time_s is None:
            relation = "the DC bus's numerical energy floor was never reached"
        elif trip_event_time_s == bus_collapse_event_time_s:
            # Exact-timestep tie: §9's explicit, arbitrary, non-causal
            # tie-break convention -- never phrase this as "before".
            relation = (
                "the DC bus's numerical energy floor was reached at the exact same sample "
                "(a tie, resolved toward PROTECTION_TRIP by an explicit, non-causal convention "
                "-- not because the trip caused the floor contact)"
            )
        else:
            relation = "before the DC bus's numerical energy floor was reached"
        detail = (
            f"Thermal protection latched TRIPPED at t = {outcome_event_time_s:.3f} s, "
            f"{relation}. This is the protection system acting as designed."
        )
    else:
        assert outcome_event_time_s is not None
        detail = (
            f"The DC bus reached its numerical energy floor at t = {outcome_event_time_s:.3f} s, "
            "before thermal protection ever latched TRIPPED (or it never latched at all). "
            "V1 models only sustained thermal overtemperature protection and has no DC-bus "
            "undervoltage/overvoltage protection -- this outcome exposes that educational V1 "
            "model gap. It is not a claim about how a real SST and its surrounding protection "
            "system would necessarily behave."
        )

    return label, detail


def _classify_recovery(
    telemetry: Telemetry, outcome: RideThroughOutcome, voltage_reference_v: float
) -> RecoveryStatus:
    """±1%-of-`V_ref` settling-band scan, ported from
    `frontend/app/lib/transientMetrics.ts`'s existing `recoveryTimeS`
    logic and applied over the whole run (SPEC-008 §9) -- not a new
    threshold.
    """
    if outcome is RideThroughOutcome.PROTECTION_TRIP:
        # The trip deliberately forces derate_factor = 0.0 for the rest
        # of the run (no automatic reset in V1); the resulting
        # near-floor voltage is the trip working as designed, not a
        # recovery question this field answers.
        return RecoveryStatus.NOT_APPLICABLE

    v = telemetry.v_dc_v
    n = len(v)
    band_v = _RECOVERY_BAND_FRACTION * voltage_reference_v
    outside_band = np.abs(v - voltage_reference_v) > band_v

    if not outside_band.any():
        return RecoveryStatus.RECOVERED

    last_breach_idx = int(np.where(outside_band)[0][-1])
    if last_breach_idx == n - 1:
        return RecoveryStatus.NOT_RECOVERED
    return RecoveryStatus.RECOVERED


_COORDINATION_LABELS = {
    CoordinationResult.NO_TERMINAL_EVENT: "No terminal protection or bus-energy event",
    CoordinationResult.PROTECTION_ACTED_NO_VIABILITY_LOSS: (
        "Thermal protection acted; DC-bus viability was never lost"
    ),
    CoordinationResult.PROTECTION_ACTED_BEFORE_VIABILITY_LOSS: (
        "Thermal protection acted before DC-bus viability was lost"
    ),
    CoordinationResult.VIABILITY_LOST_NO_PROTECTION_ACTION: (
        "DC-bus viability was lost; thermal protection never acted"
    ),
    CoordinationResult.VIABILITY_LOST_BEFORE_PROTECTION_ACTION: (
        "DC-bus viability was lost before the modeled thermal trip"
    ),
}


def _describe_coordination(
    result: CoordinationResult,
    trip_event_time_s: float | None,
    bus_collapse_event_time_s: float | None,
) -> tuple[str, str]:
    """Backend-owned label/detail text for `CoordinationResult` (SPEC-009
    §6) -- no causal language anywhere; the tied case (§6 case 3a) is
    worded to state the two events share the exact same recorded
    sample, and must never contain the word "before".
    """
    if (
        result is CoordinationResult.PROTECTION_ACTED_BEFORE_VIABILITY_LOSS
        and trip_event_time_s is not None
        and trip_event_time_s == bus_collapse_event_time_s
    ):
        # Exact-timestep tie (§6 case 3a) -- the label must never say
        # "before" either, not only the detail text.
        label = "Thermal protection acted at the same recorded sample as DC-bus viability loss"
    else:
        label = _COORDINATION_LABELS[result]

    if result is CoordinationResult.NO_TERMINAL_EVENT:
        detail = (
            "No terminal protection action or bus-energy-floor event occurred at any point "
            "in this run -- equivalent to outcome == RIDE_THROUGH."
        )
    elif result is CoordinationResult.PROTECTION_ACTED_NO_VIABILITY_LOSS:
        assert trip_event_time_s is not None
        detail = (
            f"Thermal protection latched TRIPPED at t = {trip_event_time_s:.3f} s; the DC bus "
            "never reached its numerical energy floor at any point in this run."
        )
    elif result is CoordinationResult.PROTECTION_ACTED_BEFORE_VIABILITY_LOSS:
        assert trip_event_time_s is not None and bus_collapse_event_time_s is not None
        if trip_event_time_s == bus_collapse_event_time_s:
            detail = (
                "Thermal protection latched TRIPPED at the same recorded sample the bus "
                f"reached its numerical energy floor (t = {trip_event_time_s:.3f} s) -- an "
                "exact-timestep tie, resolved toward 'protection acted' by an explicit, "
                "non-causal convention (SPEC-008 §9), not because one event preceded or "
                "caused the other."
            )
        else:
            detail = (
                f"Thermal protection latched TRIPPED at t = {trip_event_time_s:.3f} s, before "
                "the DC bus reached its numerical energy floor at "
                f"t = {bus_collapse_event_time_s:.3f} s."
            )
    elif result is CoordinationResult.VIABILITY_LOST_NO_PROTECTION_ACTION:
        assert bus_collapse_event_time_s is not None
        detail = (
            "The DC bus reached its numerical energy floor at "
            f"t = {bus_collapse_event_time_s:.3f} s; thermal protection never latched TRIPPED "
            "at any point in this run."
        )
    else:  # VIABILITY_LOST_BEFORE_PROTECTION_ACTION
        assert trip_event_time_s is not None and bus_collapse_event_time_s is not None
        detail = (
            "The DC bus reached its numerical energy floor at "
            f"t = {bus_collapse_event_time_s:.3f} s, before thermal protection later latched "
            f"TRIPPED at t = {trip_event_time_s:.3f} s."
        )

    return label, detail


def _classify_coordination_result(
    trip_event_time_s: float | None,
    bus_collapse_event_time_s: float | None,
) -> CoordinationResult:
    """Total function over the four nullability/ordering combinations
    (SPEC-009 §6). The exact-timestep tie (§6 case 3a) reuses
    `_classify_outcome`'s own `<=` tie-break convention exactly, so
    `CoordinationResult` never disagrees with `outcome` about which
    classification a tie resolves to.
    """
    if trip_event_time_s is None and bus_collapse_event_time_s is None:
        return CoordinationResult.NO_TERMINAL_EVENT
    if trip_event_time_s is not None and bus_collapse_event_time_s is None:
        return CoordinationResult.PROTECTION_ACTED_NO_VIABILITY_LOSS
    if trip_event_time_s is None and bus_collapse_event_time_s is not None:
        return CoordinationResult.VIABILITY_LOST_NO_PROTECTION_ACTION
    assert trip_event_time_s is not None and bus_collapse_event_time_s is not None
    if trip_event_time_s <= bus_collapse_event_time_s:
        return CoordinationResult.PROTECTION_ACTED_BEFORE_VIABILITY_LOSS
    return CoordinationResult.VIABILITY_LOST_BEFORE_PROTECTION_ACTION


def _derating_preceded_terminal_event(
    first_derated_start_s: float | None,
    outcome_event_time_s: float | None,
) -> bool | None:
    """SPEC-009 §6.1 -- one comparison target (`outcome_event_time_s`),
    an explicit rule for every case. `None` if either side of the
    comparison does not exist; otherwise a strict `<` comparison.
    """
    if outcome_event_time_s is None or first_derated_start_s is None:
        return None
    return first_derated_start_s < outcome_event_time_s


def _build_separations(
    trip_event_time_s: float | None,
    bus_collapse_event_time_s: float | None,
    derating_preceded_terminal_event: bool | None,
    first_derated_start_s: float | None,
    outcome_event_time_s: float | None,
) -> tuple[EventSeparation, ...]:
    """SPEC-009 §6.1 -- exactly two small, explicit rules; never a loop
    populating every possible pair, and never a negative `duration_s`.
    """
    separations: list[EventSeparation] = []

    if trip_event_time_s is not None and bus_collapse_event_time_s is not None:
        if trip_event_time_s == bus_collapse_event_time_s:
            separations.append(
                EventSeparation(
                    label="Thermal trip / bus energy floor — same recorded sample",
                    from_time_s=trip_event_time_s,
                    to_time_s=trip_event_time_s,
                    duration_s=0.0,
                )
            )
        elif bus_collapse_event_time_s < trip_event_time_s:
            separations.append(
                EventSeparation(
                    label="Bus energy floor -> thermal trip",
                    from_time_s=bus_collapse_event_time_s,
                    to_time_s=trip_event_time_s,
                    duration_s=trip_event_time_s - bus_collapse_event_time_s,
                )
            )
        else:
            separations.append(
                EventSeparation(
                    label="Thermal trip -> bus energy floor",
                    from_time_s=trip_event_time_s,
                    to_time_s=bus_collapse_event_time_s,
                    duration_s=bus_collapse_event_time_s - trip_event_time_s,
                )
            )

    if derating_preceded_terminal_event is True:
        assert first_derated_start_s is not None and outcome_event_time_s is not None
        separations.append(
            EventSeparation(
                label="Derating begins -> terminal event",
                from_time_s=first_derated_start_s,
                to_time_s=outcome_event_time_s,
                duration_s=outcome_event_time_s - first_derated_start_s,
            )
        )

    return tuple(separations)


def classify_coordination(
    trip_event_time_s: float | None,
    bus_collapse_event_time_s: float | None,
    segments: tuple[StateSegment, ...],
    outcome_event_time_s: float | None,
) -> CoordinationAnalysis:
    """Derive `CoordinationAnalysis` from the two already-computed
    terminal-event candidate times plus `segments` (SPEC-009 §6/§6.1).
    Performs no telemetry scan of its own.
    """
    result = _classify_coordination_result(trip_event_time_s, bus_collapse_event_time_s)
    result_label, result_detail = _describe_coordination(
        result, trip_event_time_s, bus_collapse_event_time_s
    )

    first_derated_start_s = next(
        (s.start_time_s for s in segments if s.state == "DERATED"), None
    )
    derating_preceded_terminal_event = _derating_preceded_terminal_event(
        first_derated_start_s, outcome_event_time_s
    )
    separations = _build_separations(
        trip_event_time_s,
        bus_collapse_event_time_s,
        derating_preceded_terminal_event,
        first_derated_start_s,
        outcome_event_time_s,
    )

    return CoordinationAnalysis(
        result=result,
        result_label=result_label,
        result_detail=result_detail,
        derating_preceded_terminal_event=derating_preceded_terminal_event,
        separations=separations,
    )
