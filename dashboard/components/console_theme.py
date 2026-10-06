"""Shared console chrome: CSS injected on every page, on top of the
native theme in .streamlit/config.toml.

Per the developing-with-streamlit skill, colors/fonts/borders belong in
config.toml, not CSS -- this module exists only for the structural,
instrument-panel chrome config.toml cannot express (panel density,
status-accent utility classes, the power-flow schematic's live-flow
animation, tabular numeric styling). The user explicitly requested a
custom console look beyond what native theming can reach; this is that
narrow, intentional exception, not a wholesale CSS reskin.

Targets Streamlit's documented `data-testid` hooks rather than hashed
class names, which are the more stable (if still not guaranteed)
surface for this kind of structural override.
"""

from __future__ import annotations

import streamlit as st

from dashboard.components.palette import CHROME, FONT_MONO, STATUS

_CSS = f"""
<style>
/* Denser console body: Streamlit's default top padding reads as "web app",
   not "instrument panel". */
.block-container {{
    padding-top: 2rem;
    padding-bottom: 2rem;
}}

/* Sidebar: a console side panel, not a content drawer. */
[data-testid="stSidebar"] {{
    border-right: 1px solid {CHROME["hairline"]};
}}
[data-testid="stSidebarUserContent"] {{
    padding-top: 1.25rem;
}}

/* Tabular, non-jittering numerals for anything that updates live --
   reserved for live values only, never for static labels (see the
   console design note in dashboard/components/palette.py). */
.console-mono {{
    font-family: {FONT_MONO};
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.01em;
}}

/* A bordered instrument panel: sharp corners, hairline border, no
   drop shadow -- deliberately not the rounded-card-with-soft-shadow
   default. */
.console-panel {{
    border: 1px solid {CHROME["hairline"]};
    border-radius: 4px;
    background: {CHROME["surface"]};
    padding: 0.9rem 1rem;
}}
.console-panel-header {{
    font-size: 0.72rem;
    font-weight: 600;
    color: {CHROME["muted"]};
    letter-spacing: 0.04em;
    margin-bottom: 0.6rem;
}}

/* Application identity -- replaces native st.title on the Simulator page.
   Sized against the panel-header scale below, not web-page convention:
   the data is the headline here, not the page's own name. */
.console-app-title {{
    font-size: 1.3rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    color: {CHROME["text_primary"]};
    /* Streamlit's own fixed top header (Deploy/menu) is ~52.5px tall and
       sits in a separate, higher-stacked layer -- native st.title's
       larger height happened to clear it; this smaller title needs
       explicit top clearance or it renders hidden underneath. */
    margin: 1.25rem 0 0.15rem 0;
}}

/* Status chip: filled dot + label, never color alone. */
.status-chip {{
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 0.15rem 0.6rem;
    border-radius: 3px;
    border: 1px solid {CHROME["hairline"]};
    background: {CHROME["surface_raised"]};
    color: {CHROME["text_primary"]};
}}
.status-chip .dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex: none;
}}

/* KPI strip: one compact instrument tile per headline telemetry value.
   Flat by default -- the top border only takes a status color when that
   value's role is neither "good" nor "neutral" (see kpi_tile_html), so
   color appears on screen only when it means something, never as
   decoration on a value that's currently fine. */
.kpi-tile {{
    border: 1px solid {CHROME["hairline"]};
    border-top: 2px solid {CHROME["hairline"]};
    border-radius: 4px;
    background: {CHROME["surface"]};
    padding: 0.5rem 0.65rem;
}}
.kpi-label {{
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: {CHROME["muted"]};
    margin-bottom: 0.3rem;
    white-space: nowrap;
}}
.kpi-value-row {{
    display: flex;
    align-items: baseline;
    gap: 0.25rem;
}}
.kpi-value {{
    font-size: 1.3rem;
    font-weight: 600;
    color: {CHROME["text_primary"]};
}}
.kpi-unit {{
    font-size: 0.68rem;
    font-weight: 500;
    color: {CHROME["muted"]};
}}

/* Power-flow schematic: live dash-flow cue. Only ever applied to a
   line when the underlying telemetry says power is actually flowing
   (see dashboard/components/schematic.py) -- speed is set inline per
   line from the real power magnitude, never decorative. */
@keyframes console-flow {{
    to {{ stroke-dashoffset: -24; }}
}}
.flow-line {{
    animation-name: console-flow;
    animation-timing-function: linear;
    animation-iteration-count: infinite;
}}
</style>
"""


def inject_console_css() -> None:
    """Inject the shared console CSS. Call once near the top of every page."""
    st.html(_CSS)


def status_chip_html(label: str, status_role: str) -> str:
    """A filled-dot status chip, e.g. for RUNNING/DERATED/TRIPPED."""
    color = STATUS.get(status_role, STATUS["warning"])
    return (
        f'<span class="status-chip">'
        f'<span class="dot" style="background:{color};"></span>{label}</span>'
    )


def kpi_tile_html(label: str, value: str, unit: str, status_role: str = "good") -> str:
    """One KPI-strip tile: uppercase label, dominant tabular value,
    subordinate unit. The top border escalates to `status_role`'s color
    only when that role is neither "good" nor "neutral" -- a value with
    no pass/fail meaning (e.g. P_load) should use "neutral" so it is
    never colored as if it were a health signal.
    """
    accent = CHROME["hairline"] if status_role in ("good", "neutral") else STATUS.get(status_role, CHROME["hairline"])
    return (
        f'<div class="kpi-tile" style="border-top-color:{accent};">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value-row">'
        f'<span class="kpi-value console-mono">{value}</span>'
        f'<span class="kpi-unit">{unit}</span>'
        f"</div></div>"
    )
