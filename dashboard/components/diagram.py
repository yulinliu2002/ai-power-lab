"""Reusable left-to-right flow-diagram renderer for system diagrams.

Used by the Overview and AI Data Center pages to draw conceptual
power-chain diagrams (e.g. Grid -> SST -> 800 VDC Bus -> AI Load).
Built from plain Plotly shapes/annotations rather than a graphviz
dependency, per CLAUDE.md's "no framework/library that is not clearly
necessary" rule.
"""

from __future__ import annotations

import plotly.graph_objects as go

from dashboard.components.palette import CATS, CHROME


def render_flow_diagram(
    stages: list[str],
    *,
    title: str | None = None,
    box_color: str = CATS["blue"],
    height: int = 150,
) -> go.Figure:
    """Render a horizontal box-and-arrow diagram of `stages`.

    Each entry in `stages` becomes one box; arrows connect consecutive
    boxes left to right. Purely illustrative -- carries no simulation
    data.
    """
    fig = go.Figure()
    n = len(stages)
    fig.update_xaxes(visible=False, range=[-0.5, n - 0.5], fixedrange=True)
    fig.update_yaxes(visible=False, range=[-1, 1], fixedrange=True)

    # Arrows are added before the box labels: Plotly layers annotations in
    # the order they're added (later = on top), so the arrow lines must come
    # first or they render on top of, and visibly cut through, the box text.
    for x in range(n - 1):
        fig.add_annotation(
            x=x + 1, y=0, ax=x, ay=0, xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=3, arrowsize=1.2, arrowwidth=2,
            arrowcolor=CHROME["muted"], text="",
        )
    for x, label in enumerate(stages):
        fig.add_annotation(
            x=x, y=0, text=label, showarrow=False,
            font=dict(size=13, color=CHROME["text_primary"]),
            bgcolor=CHROME["surface"], bordercolor=box_color, borderwidth=1.5,
            borderpad=10, align="center",
        )

    fig.update_layout(
        title=title,
        height=height,
        margin=dict(l=10, r=10, t=40 if title else 10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig
