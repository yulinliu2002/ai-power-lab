"""AI Data Center page: why SST and 800 VDC matter, architecturally.

Static educational content plus two conceptual flow diagrams
(traditional AC architecture vs. emerging 800 VDC architecture). Makes
no performance claims beyond what's sourced in the Industry section --
see that page for specific, attributed public figures.
"""

from __future__ import annotations

import streamlit as st

from dashboard.components.console_theme import inject_console_css
from dashboard.components.diagram import render_flow_diagram
from dashboard.components.palette import CATS

inject_console_css()

st.title("AI Data Center")
st.caption("Why AI racks need so much power, and why the industry is exploring new architectures to deliver it.")

st.subheader("Why AI racks require so much power")
st.markdown(
    """
Modern AI accelerator racks concentrate many high-power GPUs/accelerators
into a single enclosure, driving rack power densities far above
traditional enterprise IT racks. Training and inference workloads can
also swing power demand quickly (see Learn → Level 1 → Dynamic Load),
which is exactly the kind of transient this project's Load Step demo
represents in simplified form.
"""
)

st.divider()
st.subheader("Architecture comparison")

st.markdown("**Traditional architecture**")
st.plotly_chart(
    render_flow_diagram(
        ["MV AC", "Transformer", "LV AC", "UPS / Distribution", "Rack PSU", "LV DC", "Compute"],
        box_color=CATS["orange"],
    ),
    width="stretch",
    config={"displayModeBar": False},
)

st.markdown("**Emerging architecture**")
st.plotly_chart(
    render_flow_diagram(
        ["MV AC", "Power Conversion / SST", "800 VDC", "Rack DC/DC", "Compute"],
        box_color=CATS["aqua"],
    ),
    width="stretch",
    config={"displayModeBar": False},
)

st.caption(
    "Public industry sources (NVIDIA, the Open Compute Project) describe this emerging "
    "architecture as reducing the number of power-conversion stages between the grid and "
    "the compute load. This is described as an emerging industry direction, not a claim that "
    "all future data centers will necessarily use this exact architecture -- see the "
    "Industry section for sourced detail."
)

st.divider()
st.subheader("Topics")

topics = [
    (
        "Rack power & power density",
        "Centralizing conversion and distributing at a higher DC voltage is one proposed way "
        "to manage rising rack power density without proportionally scaling up low-voltage "
        "distribution infrastructure.",
    ),
    (
        "Dynamic GPU loads",
        "AI accelerator power draw can change quickly with workload phase. This project's "
        "Dynamic Load topic (Learn → Level 1) and AI Load Step demo (Simulator) show a "
        "simplified version of this kind of transient.",
    ),
    (
        "Conversion stages",
        "Each AC/DC or DC/DC conversion stage in the traditional chain costs efficiency and "
        "adds complexity. The emerging architecture's appeal, per public industry sources, is "
        "fewer total stages between grid and compute.",
    ),
    (
        "Energy storage concept",
        "Backup energy storage (UPS, battery) sits somewhere in both architectures to ride "
        "through a grid disturbance -- V1 has no energy-storage concept at all (see Learn → "
        "Level 3 → Grid Loss); the bus simply discharges per its own energy balance.",
    ),
    (
        "Grid interaction",
        "Both architectures ultimately interface with the same medium-voltage grid; how "
        "gracefully they tolerate grid disturbances (sags, outages) is explored in Learn → "
        "Level 3 and the Grid Sag / Grid Loss demos.",
    ),
    (
        "Architecture evolution",
        "This is described in public sources as an emerging, actively-standardized direction "
        "(see Industry → Open Compute Project), not a settled, universal replacement for "
        "every data-center architecture.",
    ),
]
for title, body in topics:
    with st.expander(title):
        st.write(body)

st.divider()
st.info(
    "**Future work (not implemented in V1.1):** an Architecture Comparison Simulator, "
    "comparing conversion stages, assumed losses, power flow, transient behavior, energy "
    "storage, and fault behavior between the traditional and emerging architectures above."
)
