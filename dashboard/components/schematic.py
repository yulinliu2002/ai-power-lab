"""The Simulator's hero visualization: a state-aware SST power-flow schematic.

Every value and color on this diagram is read directly from one
instant of a scenario's real Telemetry (via `FlowSnapshot`, built by
dashboard/pages/simulator.py from a scrubbed time index) and the
engine's own status logic (src/protection.py's operating states,
src/grid.py's availability factor). Nothing here is decorative or
fabricated:

- Stage border color = that stage's actual status (grid availability,
  SST operating_state, bus regulation band -- see `bus_status`).
- Flow-line thickness/opacity = the real power magnitude on that
  segment, normalized to the SST's rated power.
- The flowing-dash animation only plays on a segment, and only as fast
  as, the real power actually flowing on it (near-zero power -> a
  static, unanimated line) -- see console_theme.py's `.flow-line`.

This intentionally does NOT attempt switching-level or 3D-hardware
realism (out of V1 scope, see CLAUDE.md) -- it is a schematic, not a
rendering of physical hardware.

Rendering note: this is returned as a *complete, self-contained* HTML
document (own <style>, own background) and must be hosted with
`st.iframe`, not `st.html`. Streamlit's `st.html` runs all content
through DOMPurify configured with only the "html" sanitizer profile (no
"svg" profile), which silently strips every SVG element (<svg>, <defs>,
<marker>, <line>, <rect>, <circle>, <path>, <text>) regardless of any
`st.html` flag -- confirmed by inspecting Streamlit 1.65's bundled
frontend JS. `st.iframe` renders its body in an unsanitized iframe
instead, so the SVG survives. Because an iframe is a separate document,
the page's own CSS (dashboard/components/console_theme.py) can't reach
inside it -- the flow-line keyframe animation and background are
therefore duplicated here, scoped to this one document, rather than
shared.
"""

from __future__ import annotations

from dataclasses import dataclass

from dashboard.components.palette import ACCENT, CHROME, FONT_MONO, OPERATING_STATE_STATUS, STATUS
from src.grid import grid_power_availability_factor


@dataclass(frozen=True)
class FlowSnapshot:
    """One instant of a scenario's telemetry, for the schematic to render."""

    t_s: float
    grid_voltage_pu: float
    grid_available: bool
    p_sst_w: float
    p_load_w: float
    rated_power_w: float
    v_dc_v: float
    v_ref_v: float
    temperature_c: float
    operating_state: str
    derate_factor: float
    floor_v: float | None = None


#: Not prefixed with `_` -- the Simulator page's SYSTEM STATE panel reuses
#: these three directly, so its per-row accent colors can never drift out
#: of sync with the status this same schematic is drawing.
def grid_status(snapshot: FlowSnapshot) -> tuple[str, str]:
    if not snapshot.grid_available:
        return "critical", "LOST"
    if snapshot.grid_voltage_pu < 0.95:
        return "warning", "SAGGED"
    return "good", "NOMINAL"


def bus_status(snapshot: FlowSnapshot) -> tuple[str, str]:
    if snapshot.floor_v is not None and snapshot.v_dc_v <= snapshot.floor_v + 0.5:
        return "critical", "COLLAPSED"
    deviation = abs(snapshot.v_dc_v - snapshot.v_ref_v) / snapshot.v_ref_v
    if deviation <= 0.05:
        return "good", "IN REGULATION"
    if deviation <= 0.15:
        return "warning", "DROOPING"
    return "critical", "OUT OF REGULATION"


def sst_status(snapshot: FlowSnapshot) -> tuple[str, str]:
    role = OPERATING_STATE_STATUS.get(snapshot.operating_state, "warning")
    return role, snapshot.operating_state


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _flow_segment(x1: float, y: float, x2: float, frac: float, color: str, dim: bool) -> str:
    """One animated/static power-flow line between two stage boxes.

    `frac` in [0, 1] (power / rated_power) drives both stroke width and
    animation speed -- a thicker, faster-animated line always means
    more real power, never a styling choice. `dim` forces a thin, inert
    gray line (e.g. grid lost) regardless of `frac`.
    """
    if dim or frac < 0.01:
        stroke = CHROME["hairline"]
        width = 1.5
        cls = ""
        style = ""
    else:
        stroke = color
        width = 2 + 5 * _clamp01(frac)
        duration = max(0.25, 1.4 - 1.1 * _clamp01(frac))
        cls = "flow-line"
        style = f'style="animation-duration:{duration:.2f}s;"'
    return (
        f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{stroke}" '
        f'stroke-width="{width}" stroke-dasharray="6 6" stroke-linecap="round" '
        f'class="{cls}" {style} marker-end="url(#arrow-{_safe(stroke)})" />'
    )


def _safe(color: str) -> str:
    """SVG marker ids can't contain '#' or ','."""
    return color.replace("#", "c").replace(",", "").replace("(", "").replace(")", "").replace(".", "")


def _stage_box(
    x: float, y: float, w: float, h: float, *, title: str, color: str,
    status_label: str, lines: list[str],
) -> str:
    rows = "".join(
        f'<text x="{x + w / 2}" y="{y + 70 + i * 20}" text-anchor="middle" '
        f'class="console-mono" font-size="15" fill="{CHROME["text_primary"]}">{line}</text>'
        for i, line in enumerate(lines)
    )
    return f"""
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{CHROME['surface_raised']}"
          stroke="{color}" stroke-width="2" />
    <text x="{x + w / 2}" y="{y + 24}" text-anchor="middle" font-size="12.5" font-weight="600"
          letter-spacing="0.03em" fill="{CHROME['text_secondary']}">{title}</text>
    <circle cx="{x + 16}" cy="{y + 42}" r="4.5" fill="{color}" />
    <text x="{x + 26}" y="{y + 46}" font-size="11" font-weight="600" fill="{color}">{status_label}</text>
    {rows}
    """


def render_power_flow_svg(snapshot: FlowSnapshot) -> str:
    """Build the full schematic as an inline-SVG HTML fragment for `st.html`."""
    grid_role, grid_label = grid_status(snapshot)
    sst_role, sst_label = sst_status(snapshot)
    bus_role, bus_label = bus_status(snapshot)

    rated = max(snapshot.rated_power_w, 1.0)
    sst_frac = _clamp01(snapshot.p_sst_w / rated)
    load_frac = _clamp01(snapshot.p_load_w / rated)
    availability = grid_power_availability_factor(snapshot.grid_voltage_pu, snapshot.grid_available)

    box_w, box_h = 190, 118
    y = 40
    xs = [30, 290, 550, 810]
    width = xs[-1] + box_w + 30

    grid_box = _stage_box(
        xs[0], y, box_w, box_h, title="MV GRID", color=STATUS[grid_role], status_label=grid_label,
        lines=[f"{snapshot.grid_voltage_pu:.2f} p.u."],
    )
    sst_box = _stage_box(
        xs[1], y, box_w, box_h, title="SST", color=STATUS[sst_role], status_label=sst_label,
        lines=[
            f"P {snapshot.p_sst_w / 1e3:.1f} kW",
            f"T {snapshot.temperature_c:.1f} °C · derate {snapshot.derate_factor * 100:.0f}%",
        ],
    )
    bus_box = _stage_box(
        xs[2], y, box_w, box_h, title="800 VDC BUS", color=STATUS[bus_role], status_label=bus_label,
        lines=[f"{snapshot.v_dc_v:.1f} V", f"ref {snapshot.v_ref_v:.0f} V"],
    )
    # The load is an exogenous demand sink, not a protected/controlled entity
    # (src/load.py) -- it gets the neutral accent, never a health-status color.
    load_box = _stage_box(
        xs[3], y, box_w, box_h, title="AI COMPUTE LOAD", color=ACCENT,
        status_label="DEMAND", lines=[f"P {snapshot.p_load_w / 1e3:.1f} kW"],
    )

    mid_y = y + box_h / 2
    seg1 = _flow_segment(xs[0] + box_w, mid_y, xs[1], sst_frac, ACCENT, dim=(availability < 0.01))
    seg2 = _flow_segment(xs[1] + box_w, mid_y, xs[2], sst_frac, ACCENT, dim=False)
    seg3 = _flow_segment(xs[2] + box_w, mid_y, xs[3], load_frac, ACCENT, dim=False)

    markers = "".join(
        f"""<marker id="arrow-{_safe(c)}" viewBox="0 0 10 10" refX="8" refY="5"
                markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="{c}" />
            </marker>"""
        for c in {CHROME["hairline"], ACCENT}
    )

    return f"""<!doctype html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        html, body {{ margin: 0; padding: 0; background: {CHROME["canvas"]}; }}
        .console-mono {{
            font-family: {FONT_MONO};
            font-variant-numeric: tabular-nums;
            letter-spacing: -0.01em;
        }}
        @keyframes console-flow {{ to {{ stroke-dashoffset: -24; }} }}
        .flow-line {{
            animation-name: console-flow;
            animation-timing-function: linear;
            animation-iteration-count: infinite;
        }}
    </style>
    </head>
    <body>
    <div style="overflow-x:auto;">
    <svg viewBox="0 0 {width} {y + box_h + 20}" width="100%" style="min-width:720px;">
        <defs>{markers}</defs>
        {seg1}{seg2}{seg3}
        {grid_box}{sst_box}{bus_box}{load_box}
    </svg>
    </div>
    </body>
    </html>
    """
