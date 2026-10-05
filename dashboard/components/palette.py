"""Validated color palette for the dashboard's dark engineering-console theme.

These are the dataviz-skill reference palette's DARK-mode steps
(categorical palette, status colors, chart chrome) -- a generic,
colorblind-safe validated set, not brand colors. AI Power Lab commits to
a single dark theme (see .streamlit/config.toml, which mirrors these
exact hex values) rather than a light/dark toggle, so there is one
palette, not a light/dark pair. Keeping it in one module ensures every
chart, badge, and console panel draws from the same, consistent colors.
"""

from __future__ import annotations

#: Categorical hues, in validated fixed order. Never cycle/reassign
#: these per-filter -- a given entity (e.g. "P_load") should always use
#: the same slot across every chart it appears in.
CATS: dict[str, str] = {
    "blue": "#3987e5",
    "orange": "#d95926",
    "aqua": "#199e70",
    "yellow": "#c98500",
    "magenta": "#d55181",
    "green": "#008300",
    "violet": "#9085e9",
    "red": "#e66767",
}

#: Reserved for system state only -- never reused as a generic series color.
STATUS: dict[str, str] = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

#: Console chrome -- panel surfaces, ink, hairlines. Matches
#: .streamlit/config.toml's backgroundColor/secondaryBackgroundColor/
#: textColor/borderColor so custom st.html panels sit flush against
#: native Streamlit elements.
CHROME: dict[str, str] = {
    "canvas": "#0a0e14",
    "surface": "#121820",
    "surface_raised": "#1a232e",
    "text_primary": "#e7edf3",
    "text_secondary": "#aab4bd",
    "muted": "#6b7680",
    "gridline": "rgba(255,255,255,0.08)",
    "baseline": "rgba(255,255,255,0.18)",
    "hairline": "#24303c",
}

#: Reserved for the "energized / actively powered" cue in the power-flow
#: schematic -- the one brand accent, kept equal to CATS["blue"] so it
#: never introduces a second ad hoc hue.
ACCENT = CATS["blue"]

FONT_SANS = "'IBM Plex Sans', system-ui, sans-serif"
FONT_MONO = "'IBM Plex Mono', 'SFMono-Regular', monospace"

#: Maps the protection state machine's operating states (src/protection.py)
#: to a status-color role. Fixed, closed set -- single source of truth for
#: every badge/panel/schematic that displays operating_state.
OPERATING_STATE_STATUS: dict[str, str] = {
    "RUNNING": "good",
    "DERATED": "warning",
    "TRIPPED": "critical",
}
