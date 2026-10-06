"""Interactive Plotly chart builders for the dashboard.

Pure presentation layer: every function consumes a `Telemetry` object
already produced by `src/simulation.py` (via a dashboard adapter). No
physics or derived-quantity calculation happens here -- this is the
interactive counterpart to the static matplotlib plots in
scenarios/plotting.py, used by the Streamlit Simulator page.
"""

from __future__ import annotations

import plotly.graph_objects as go

from dashboard.components.palette import CATS, CHROME, FONT_SANS, STATUS
from src.telemetry import Telemetry

EventMarkers = list[tuple[float, str]]


def _with_alpha(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _apply_chrome(fig: go.Figure, title: str, x_title: str, y_title: str) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(color=CHROME["text_primary"], size=14)),
        xaxis_title=x_title,
        yaxis_title=y_title,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=CHROME["text_secondary"], family=FONT_SANS, size=12),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(color=CHROME["text_secondary"]),
        ),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=CHROME["surface_raised"], font=dict(color=CHROME["text_primary"], family=FONT_SANS)),
        annotationdefaults=dict(font=dict(color=CHROME["text_secondary"], family=FONT_SANS, size=11)),
        margin=dict(l=10, r=10, t=60, b=10),
        height=320,
    )
    fig.update_xaxes(
        gridcolor=CHROME["gridline"], zerolinecolor=CHROME["baseline"],
        color=CHROME["text_secondary"], linecolor=CHROME["hairline"],
    )
    fig.update_yaxes(
        gridcolor=CHROME["gridline"], zerolinecolor=CHROME["baseline"],
        color=CHROME["text_secondary"], linecolor=CHROME["hairline"],
    )
    return fig


def _mark_events(fig: go.Figure, events: EventMarkers | None) -> None:
    if not events:
        return
    for t_s, label in events:
        fig.add_vline(
            x=t_s, line_dash="dot", line_color=CHROME["muted"], line_width=1,
            annotation_text=label, annotation_position="top",
        )


def _mark_current_time(fig: go.Figure, current_t_s: float | None) -> None:
    """A restrained solid line at the Simulator hero panel's current scrub
    position -- visually distinct from `_mark_events`' dotted/muted event
    markers (ACCENT, solid, no label) so "where the scrubber is" never
    reads as "something that happened". Presentation-only: this does not
    re-run on every autoplay tick (see simulator.py), only on a manual
    scrub, to avoid re-sending a full chart on an animation-frame cadence.
    """
    if current_t_s is None:
        return
    fig.add_vline(x=current_t_s, line_color=CATS["blue"], line_width=1.5)


def plot_voltage(
    telemetry: Telemetry,
    v_ref_v: float = 800.0,
    events: EventMarkers | None = None,
    floor_v: float | None = None,
    current_t_s: float | None = None,
    title: str = "DC Bus Voltage vs Time",
) -> go.Figure:
    """V_dc vs time. If `floor_v` is given, it is marked as a numerical
    (non-physical) safety floor -- see src/dc_bus.py -- not a real
    residual bus voltage.
    """
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=telemetry.time_s, y=telemetry.v_dc_v, mode="lines",
                   name="V_dc", line=dict(color=CATS["blue"], width=2))
    )
    fig.add_hline(
        y=v_ref_v, line_dash="dash", line_color=CHROME["baseline"],
        annotation_text=f"V_ref = {v_ref_v:.0f} V", annotation_position="bottom right",
    )
    if floor_v is not None:
        fig.add_hline(
            y=floor_v, line_dash="dot", line_color=STATUS["critical"],
            annotation_text="numerical floor (non-physical)", annotation_position="top right",
        )
    _mark_events(fig, events)
    _mark_current_time(fig, current_t_s)
    return _apply_chrome(fig, title, "time [s]", "DC bus voltage [V]")


def plot_power(
    telemetry: Telemetry,
    events: EventMarkers | None = None,
    include_target: bool = False,
    current_t_s: float | None = None,
    title: str = "Load Power vs SST Delivered Power",
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=telemetry.time_s, y=telemetry.p_load_w / 1e3, mode="lines",
                   name="P_load", line=dict(color=CATS["orange"], width=2))
    )
    fig.add_trace(
        go.Scatter(x=telemetry.time_s, y=telemetry.p_sst_w / 1e3, mode="lines",
                   name="P_sst", line=dict(color=CATS["aqua"], width=2))
    )
    if include_target:
        fig.add_trace(
            go.Scatter(x=telemetry.time_s, y=telemetry.p_target_w / 1e3, mode="lines",
                       name="P_target", line=dict(color=CATS["violet"], width=1, dash="dash"))
        )
    _mark_events(fig, events)
    _mark_current_time(fig, current_t_s)
    return _apply_chrome(fig, title, "time [s]", "power [kW]")


def plot_temperature(
    telemetry: Telemetry,
    derate_start_c: float | None = None,
    trip_c: float | None = None,
    events: EventMarkers | None = None,
    current_t_s: float | None = None,
    title: str = "SST Temperature vs Time",
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=telemetry.time_s, y=telemetry.temperature_c, mode="lines",
                   name="T (SST, representative)", line=dict(color=CATS["yellow"], width=2))
    )
    if derate_start_c is not None:
        fig.add_hline(
            y=derate_start_c, line_dash="dash", line_color=STATUS["warning"],
            annotation_text=f"derate start = {derate_start_c:.0f} °C", annotation_position="bottom right",
        )
    if trip_c is not None:
        fig.add_hline(
            y=trip_c, line_dash="dash", line_color=STATUS["critical"],
            annotation_text=f"trip = {trip_c:.0f} °C", annotation_position="top right",
        )
    _mark_events(fig, events)
    _mark_current_time(fig, current_t_s)
    return _apply_chrome(fig, title, "time [s]", "temperature [°C]")


def plot_protection(
    telemetry: Telemetry,
    events: EventMarkers | None = None,
    current_t_s: float | None = None,
    title: str = "Derate Factor vs Time",
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=telemetry.time_s, y=telemetry.derate_factor, mode="lines",
                   name="derate_factor", line=dict(color=CATS["magenta"], width=2))
    )
    if telemetry.trip_active.any():
        fig.add_trace(
            go.Scatter(
                x=telemetry.time_s, y=telemetry.trip_active.astype(float),
                name="TRIPPED", fill="tozeroy", mode="none",
                fillcolor=_with_alpha(STATUS["critical"], 0.18),
            )
        )
    _mark_events(fig, events)
    _mark_current_time(fig, current_t_s)
    fig.update_yaxes(range=[-0.05, 1.05])
    return _apply_chrome(fig, title, "time [s]", "derate factor [-]")


def plot_grid_voltage(
    telemetry: Telemetry,
    events: EventMarkers | None = None,
    current_t_s: float | None = None,
    title: str = "Grid Voltage vs Time",
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=telemetry.time_s, y=telemetry.grid_voltage_pu, mode="lines",
                   name="grid_voltage_pu", line=dict(color=CATS["blue"], width=2))
    )
    unavailable = (~telemetry.grid_available).astype(float)
    if unavailable.any():
        fig.add_trace(
            go.Scatter(
                x=telemetry.time_s, y=unavailable * 1.2,
                name="grid unavailable", fill="tozeroy", mode="none",
                fillcolor=_with_alpha(STATUS["critical"], 0.18),
            )
        )
    _mark_events(fig, events)
    _mark_current_time(fig, current_t_s)
    fig.update_yaxes(range=[-0.05, 1.2])
    return _apply_chrome(fig, title, "time [s]", "grid voltage [p.u.]")
