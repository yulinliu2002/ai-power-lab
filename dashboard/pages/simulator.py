"""Simulator page: an engineering-workstation view of the V1 engine.

Every run goes through dashboard/adapters/simulation_adapter.py, which
calls straight into src/simulation.py -- no physics is implemented on
this page. Each scenario's run is st.cache_data-cached on its
parameters so moving a slider doesn't force visitors to wait on a
recompute of a run they've already seen.

Layout: sidebar (scenario + parameters) -- top KPI strip + hero
power-flow schematic + time scrubber + system-state chip, kept in
lockstep inside one st.fragment so scrubbing/playing can never show
the schematic and the KPI strip at two different instants -- then
full-width telemetry plots across the whole run.

Known Streamlit limitation (see CLAUDE.md working agreement on not
fighting the framework): the bottom telemetry plots render outside
that fragment, for performance -- re-plotting four Plotly charts on
every autoplay tick (~5.5 Hz) would make Play feel sluggish, especially
on the two long scenarios (90k-200k samples). They get a restrained
current-time marker (see plots.py's `_mark_current_time`) that updates
on a manual scrub -- `_stop_playing_on_manual_scrub` escalates that one
interaction to a full top-level rerun via `st.rerun()` -- but not on
every autoplay tick, which stays fragment-scoped as before.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.adapters import simulation_adapter as adapter
from dashboard.components.console_theme import inject_console_css, kpi_tile_html, status_chip_html
from dashboard.components.palette import OPERATING_STATE_STATUS
from dashboard.components.plots import (
    plot_grid_voltage,
    plot_power,
    plot_protection,
    plot_temperature,
    plot_voltage,
)
from dashboard.components.schematic import FlowSnapshot, bus_status, grid_status, render_power_flow_svg, sst_status
from src.dc_bus import voltage_from_energy

inject_console_css()

st.markdown('<div class="console-app-title">Simulator</div>', unsafe_allow_html=True)
st.caption("An engineering-workstation view of the V1 engine -- every value below is read from a live run.")

SCENARIO_LABELS: dict[str, str] = {
    "load_step": "AI load step",
    "sustained_high_load": "Sustained high load",
    "thermal_trip": "Thermal derating / trip",
    "grid_sag": "Grid sag",
    "grid_loss": "Grid loss",
}

_default_key = st.session_state.get("simulator_preselect", "load_step")
if _default_key not in SCENARIO_LABELS:
    _default_key = "load_step"
_keys = list(SCENARIO_LABELS.keys())

scenario_key = st.selectbox(
    "SCENARIO",
    options=_keys,
    index=_keys.index(_default_key),
    format_func=lambda k: SCENARIO_LABELS[k],
)
# Clear the cross-page preselect once consumed so it doesn't stick on reruns.
st.session_state.pop("simulator_preselect", None)


@st.cache_data(show_spinner="Running simulation...")
def _cached_load_step(initial_fraction, final_fraction, step_time_s, duration_s, rated_power_w, voltage_reference_v):
    return adapter.run_load_step(
        initial_fraction=initial_fraction,
        final_fraction=final_fraction,
        step_time_s=step_time_s,
        duration_s=duration_s,
        rated_power_w=rated_power_w,
        voltage_reference_v=voltage_reference_v,
    )


@st.cache_data(show_spinner="Running simulation...")
def _cached_sustained_high_load(load_w, duration_s):
    return adapter.run_sustained_high_load(load_w=load_w, duration_s=duration_s)


@st.cache_data(show_spinner="Running simulation...")
def _cached_thermal_trip(overload_w, duration_s):
    return adapter.run_thermal_trip(overload_w=overload_w, duration_s=duration_s)


@st.cache_data(show_spinner="Running simulation...")
def _cached_grid_sag(load_w, sag_voltage_pu, sag_start_s, sag_duration_s, duration_s):
    return adapter.run_grid_sag(
        load_w=load_w,
        sag_voltage_pu=sag_voltage_pu,
        sag_start_s=sag_start_s,
        sag_duration_s=sag_duration_s,
        duration_s=duration_s,
    )


@st.cache_data(show_spinner="Running simulation...")
def _cached_grid_loss(load_w, outage_start_s, duration_s):
    return adapter.run_grid_loss(load_w=load_w, outage_start_s=outage_start_s, duration_s=duration_s)


with st.sidebar:
    st.markdown('<div class="console-panel-header">SCENARIO &amp; PARAMETERS</div>', unsafe_allow_html=True)

    if scenario_key == "load_step":
        initial_fraction = st.slider("Initial AI load [fraction of rated]", 0.0, 1.0, 0.4, 0.05)
        final_fraction = st.slider("Final AI load [fraction of rated]", 0.0, 1.0, 0.8, 0.05)
        duration_s = st.slider("Simulation duration [s]", 0.2, 2.0, 0.6, 0.1)
        step_time_s = st.slider("Step time [s]", 0.0, duration_s, min(0.2, duration_s), 0.05)
        rated_power_kw = st.slider("SST rated power [kW]", 100, 1000, 500, 50)
        voltage_reference_v = st.slider("Voltage reference V_ref [V]", 600, 900, 800, 10)
        result = _cached_load_step(
            initial_fraction, final_fraction, step_time_s, duration_s,
            rated_power_kw * 1e3, float(voltage_reference_v),
        )

    elif scenario_key == "sustained_high_load":
        load_kw = st.slider("Sustained load [kW]", 50, 400, 200, 10)
        duration_s = st.slider("Simulation duration [s]", 10, 300, 200, 10)
        result = _cached_sustained_high_load(load_kw * 1e3, float(duration_s))

    elif scenario_key == "thermal_trip":
        overload_kw = st.slider("Sustained overload [kW]", 200, 500, 450, 10)
        duration_s = st.slider("Simulation duration [s]", 10, 120, 90, 5)
        result = _cached_thermal_trip(overload_kw * 1e3, float(duration_s))

    elif scenario_key == "grid_sag":
        load_kw = st.slider("Load [kW]", 100, 400, 300, 10)
        sag_voltage_pu = st.slider("Sag voltage [p.u.]", 0.0, 1.0, 0.5, 0.05)
        duration_s = st.slider("Simulation duration [s]", 0.5, 3.0, 1.2, 0.1)
        sag_start_s = st.slider("Sag start time [s]", 0.0, duration_s, min(0.3, duration_s), 0.05)
        sag_duration_s = st.slider("Sag duration [s]", 0.05, 1.0, 0.2, 0.05)
        result = _cached_grid_sag(load_kw * 1e3, sag_voltage_pu, sag_start_s, sag_duration_s, duration_s)

    else:  # grid_loss
        load_kw = st.slider("Load [kW]", 100, 400, 300, 10)
        duration_s = st.slider("Simulation duration [s]", 0.2, 2.0, 0.5, 0.1)
        outage_start_s = st.slider("Outage start time [s]", 0.0, duration_s, min(0.2, duration_s), 0.05)
        result = _cached_grid_loss(load_kw * 1e3, outage_start_s, duration_s)

telemetry = result.telemetry
config = result.config
events = result.events
n_samples = len(telemetry.time_s)
floor_v = voltage_from_energy(config.dc_bus.min_energy_j, config.dc_bus.capacitance_f)

if scenario_key == "load_step":
    st.caption(
        "Causal chain: AI load increases → power demand exceeds SST output temporarily → "
        "DC bus energy decreases → V_dc falls → PI controller increases command → "
        "SST output rises → energy balance is restored → V_dc recovers."
    )

# Reset the scrubber whenever the scenario or its parameters change -- an
# index valid for a 200,000-sample run is meaningless for a 300-sample one.
# NOTE: this must be a value-based fingerprint, not id(telemetry) --
# st.cache_data returns a fresh deep-copied object on every call (by design,
# to prevent callers mutating the cache), so object identity changes on
# every single rerun even when the scenario and parameters are unchanged.
_result_token = (
    scenario_key, n_samples,
    float(telemetry.time_s[-1]), float(telemetry.p_load_w[0]), float(telemetry.p_sst_w[0]),
)
if st.session_state.get("_scrub_token") != _result_token:
    st.session_state["scrub_slider"] = 0
    st.session_state["playing"] = False
    st.session_state["_scrub_token"] = _result_token
st.session_state.setdefault("scrub_slider", 0)


def _snapshot_at(idx: int) -> FlowSnapshot:
    return FlowSnapshot(
        t_s=float(telemetry.time_s[idx]),
        grid_voltage_pu=float(telemetry.grid_voltage_pu[idx]),
        grid_available=bool(telemetry.grid_available[idx]),
        p_sst_w=float(telemetry.p_sst_w[idx]),
        p_load_w=float(telemetry.p_load_w[idx]),
        rated_power_w=config.sst.rated_power_w,
        v_dc_v=float(telemetry.v_dc_v[idx]),
        v_ref_v=config.controller.voltage_reference_v,
        temperature_c=float(telemetry.temperature_c[idx]),
        operating_state=str(telemetry.operating_state[idx]),
        derate_factor=float(telemetry.derate_factor[idx]),
        floor_v=floor_v,
    )


# Fixed tick rate, always on -- NOT conditional on `playing`. `run_every` is
# evaluated once, from the enclosing (non-fragment) script, at decoration
# time; clicking the Play button only triggers a fragment-scoped rerun, so a
# `run_every` that depended on `st.session_state["playing"]` would never
# actually start ticking after that click (confirmed while building this).
# A no-op tick while paused just redraws the same frame -- cheap enough that
# this is the simpler, correct choice over fighting the fragment's rerun
# scoping to make the interval itself reactive.
_TICK_SECONDS = 0.18


def _stop_playing_on_manual_scrub() -> None:
    """on_change callback for the scrubber: a manual drag always takes over
    from autoplay, the way scrubbing a video player pauses it.

    st.rerun() escalates this one interaction from the default
    fragment-scoped rerun to a full top-level rerun, so the telemetry
    charts below (rendered outside the fragment, deliberately -- see the
    module docstring) pick up the new scrub position for their
    current-time marker. Autoplay ticking does NOT go through this
    callback (it mutates session_state directly inside the fragment), so
    this never fires at the ~5.5 Hz tick rate -- only once per manual
    drag.
    """
    st.session_state["playing"] = False
    st.rerun()


@st.fragment(run_every=_TICK_SECONDS)
def _hero_fragment() -> None:
    playing = st.session_state.get("playing", False)

    if playing:
        # Advance the ONE canonical position (the slider's own widget state)
        # before the slider is instantiated below -- this is the only safe
        # way to move a widget programmatically. Never also pre-assign this
        # key unconditionally on every run: that would clobber a genuine
        # drag happening on this very run (confirmed by AppTest while
        # building this -- the naive "mirror idx into the widget key every
        # run" version silently discarded the user's own drag).
        step = max(1, n_samples // 60)  # ~60 frames across the full run
        idx = min(st.session_state["scrub_slider"] + step, n_samples - 1)
        st.session_state["scrub_slider"] = idx
        if idx >= n_samples - 1:
            st.session_state["playing"] = False

    idx = st.session_state["scrub_slider"]
    snapshot = _snapshot_at(idx)

    # Single source of truth for this instant's per-stage status, reused
    # by both the KPI strip below and the schematic it sits above -- so
    # the two can never silently disagree (see schematic.py's own
    # rendering of the same three functions).
    bus_role, _ = bus_status(snapshot)
    sst_role, _ = sst_status(snapshot)
    grid_role, _ = grid_status(snapshot)

    kpi_cols = st.columns(6, gap="small")
    with kpi_cols[0]:
        st.markdown(kpi_tile_html("VDC", f"{snapshot.v_dc_v:.1f}", "V", bus_role), unsafe_allow_html=True)
    with kpi_cols[1]:
        st.markdown(kpi_tile_html("P_SST", f"{snapshot.p_sst_w / 1e3:.1f}", "kW", sst_role), unsafe_allow_html=True)
    with kpi_cols[2]:
        # Neutral, always -- P_load is an exogenous demand, not a
        # protected entity (see schematic.py); it never gets a
        # health-status color, no matter how high it reads.
        st.markdown(kpi_tile_html("P_LOAD", f"{snapshot.p_load_w / 1e3:.1f}", "kW", "neutral"), unsafe_allow_html=True)
    with kpi_cols[3]:
        st.markdown(kpi_tile_html("TEMPERATURE", f"{snapshot.temperature_c:.1f}", "°C", sst_role), unsafe_allow_html=True)
    with kpi_cols[4]:
        st.markdown(kpi_tile_html("DERATE", f"{snapshot.derate_factor * 100:.0f}", "%", sst_role), unsafe_allow_html=True)
    with kpi_cols[5]:
        grid_value = f"{snapshot.grid_voltage_pu:.2f}" if snapshot.grid_available else "LOST"
        grid_unit = "p.u." if snapshot.grid_available else ""
        st.markdown(kpi_tile_html("GRID", grid_value, grid_unit, grid_role), unsafe_allow_html=True)

    hero_col, status_col = st.columns([3, 1], gap="large")

    with hero_col:
        with st.container(border=True):
            st.markdown('<div class="console-panel-header">POWER FLOW</div>', unsafe_allow_html=True)
            # st.html() cannot be used here -- Streamlit sanitizes it through
            # DOMPurify's "html"-only profile, which strips all SVG elements
            # outright (see the rendering note in schematic.py). st.iframe
            # hosts the schematic in an unsanitized iframe instead.
            st.iframe(render_power_flow_svg(snapshot), height="content")

            slider_col, play_col = st.columns([6, 1], vertical_alignment="center")
            with slider_col:
                st.slider(
                    "Scrub time", 0, n_samples - 1, key="scrub_slider",
                    on_change=_stop_playing_on_manual_scrub, label_visibility="collapsed",
                )
            with play_col:
                if st.button("Pause" if playing else "Play", key="play_toggle", width="stretch"):
                    if not playing and idx >= n_samples - 1:
                        st.session_state["scrub_slider"] = 0
                    st.session_state["playing"] = not playing

            st.caption(
                f"t = {snapshot.t_s:.4f} s  ·  sample {idx + 1} / {n_samples}",
            )

    with status_col:
        with st.container(border=True):
            st.markdown('<div class="console-panel-header">SYSTEM STATE</div>', unsafe_allow_html=True)
            # The six raw values that used to live here as a second,
            # duplicate set of numbers now live only in the KPI strip
            # above -- two surfaces showing the same number is exactly
            # how P_load's status color silently went stale (see
            # palette.py's STATUS["neutral"]). This panel keeps only the
            # one thing that isn't already in the strip: the overall SST
            # operating-state verdict.
            st.markdown(
                status_chip_html(snapshot.operating_state, OPERATING_STATE_STATUS.get(snapshot.operating_state, "warning")),
                unsafe_allow_html=True,
            )


_hero_fragment()

# Read back what the fragment just set -- on a full top-level rerun (the
# only kind that reaches this point; see _stop_playing_on_manual_scrub)
# the fragment has already run inline above, so this is the current
# scrub position, not a stale one.
_scrub_idx = st.session_state.get("scrub_slider", 0)
_current_t_s = float(telemetry.time_s[_scrub_idx])

_NO_MODEBAR = {"displayModeBar": False}

st.divider()
st.markdown('<div class="console-panel-header">TELEMETRY</div>', unsafe_allow_html=True)
st.caption("Full run, start to finish -- the thin blue line marks the current scrub position above.")

col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(
        plot_voltage(
            telemetry, v_ref_v=config.controller.voltage_reference_v, events=events,
            floor_v=floor_v, current_t_s=_current_t_s,
        ),
        width="stretch", config=_NO_MODEBAR,
    )
with col2:
    st.plotly_chart(
        plot_power(
            telemetry, events=events, include_target=(scenario_key == "load_step"),
            current_t_s=_current_t_s,
        ),
        width="stretch", config=_NO_MODEBAR,
    )

if scenario_key in ("sustained_high_load", "thermal_trip"):
    col3, col4 = st.columns(2)
    with col3:
        st.plotly_chart(
            plot_temperature(
                telemetry,
                derate_start_c=config.protection.thermal_derate_start_c,
                trip_c=config.protection.thermal_trip_c,
                events=events,
                current_t_s=_current_t_s,
            ),
            width="stretch", config=_NO_MODEBAR,
        )
    with col4:
        st.plotly_chart(
            plot_protection(telemetry, events=events, current_t_s=_current_t_s),
            width="stretch", config=_NO_MODEBAR,
        )

if scenario_key in ("grid_sag", "grid_loss"):
    st.plotly_chart(
        plot_grid_voltage(telemetry, events=events, current_t_s=_current_t_s),
        width="stretch", config=_NO_MODEBAR,
    )

with st.expander("Raw telemetry (first 200 rows)"):
    df = pd.DataFrame(
        {
            "time_s": telemetry.time_s,
            "v_dc_v": telemetry.v_dc_v,
            "p_load_w": telemetry.p_load_w,
            "p_sst_w": telemetry.p_sst_w,
            "temperature_c": telemetry.temperature_c,
            "operating_state": telemetry.operating_state,
        }
    )
    st.dataframe(df.iloc[:: max(1, len(df) // 200)].head(200), width="stretch")
