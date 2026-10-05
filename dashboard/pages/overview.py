"""Overview page: the landing page.

Pure presentation -- answers "what is this?" in about 30 seconds and
sets the modeling-scope expectations (educational / system-level /
average-value / not calibrated to a commercial SST) before a visitor
touches the Simulator.
"""

from __future__ import annotations

import streamlit as st

from dashboard.components.console_theme import inject_console_css
from dashboard.components.diagram import render_flow_diagram
from dashboard.components.palette import CHROME

inject_console_css()

st.title("AI POWER LAB")
st.caption("Solid-State Transformer + 800 VDC AI Infrastructure")

st.markdown(
    """
AI Power Lab is a **system-level simulation and visualization platform**
for learning how a solid-state-transformer-powered, 800 VDC AI
data-center power chain actually behaves end-to-end -- electrically,
thermally, and under protection logic.
"""
)

# Neutral scope tags, not data -- deliberately CHROME (console border/surface
# tones), not a CATS categorical hue, and matching the console's 4px base
# radius rather than an ad hoc pill shape.
badge_cols = st.columns(4)
for col, label in zip(
    badge_cols, ["educational", "system-level", "average-value", "not calibrated to a commercial SST"]
):
    col.markdown(
        f'<div style="text-align:center;padding:6px 10px;border:1px solid {CHROME["hairline"]};'
        f'border-radius:4px;background:{CHROME["surface_raised"]};color:{CHROME["text_secondary"]};'
        f'font-size:0.78rem;">{label}</div>',
        unsafe_allow_html=True,
    )

st.divider()
st.subheader("The power chain this project simulates")
st.plotly_chart(
    render_flow_diagram(["MV Grid", "SST / Power Conversion", "800 VDC Bus", "AI Compute Load"]),
    width="stretch",
    config={"displayModeBar": False},
)

coupled_cols = st.columns(2)
with coupled_cols[0]:
    with st.container(border=True):
        st.markdown("**Thermal model** (coupled via SST conversion loss)")
        st.caption("Loss → heat → temperature. See Learn → Level 3 → Thermal Dynamics.")
with coupled_cols[1]:
    with st.container(border=True):
        st.markdown("**Protection / derating** (coupled via temperature)")
        st.caption("Temperature → derate factor → available power. See Learn → Level 3 → Protection.")

st.divider()
st.subheader("Thirty seconds on what this is")

qa = [
    (
        "What is an SST?",
        "A power-electronic converter that performs voltage transformation (and "
        "often AC/DC conversion) using active semiconductor switching and a "
        "medium-frequency transformer, instead of a passive line-frequency "
        "transformer. See Learn → Level 2.",
    ),
    (
        "Why does 800 VDC matter?",
        "Public industry sources (NVIDIA, the Open Compute Project) describe an "
        "industry shift toward centralized power conversion and an 800 VDC "
        "distribution bus for high-density AI racks, aiming to cut the number of "
        "conversion stages between the grid and the compute load. See the AI "
        "Data Center and Industry sections.",
    ),
    (
        "Why do AI data centers create new power challenges?",
        "AI compute workloads can swing power demand fast and hard -- this "
        "project's flagship demo (Simulator → AI Load Step) shows exactly "
        "that kind of transient and how the system responds to it.",
    ),
    (
        "What does this project simulate?",
        "The full causal chain Grid → SST (average-value model) → 800 "
        "VDC bus → AI load, including a PI voltage controller, a lumped "
        "thermal model, and thermal-driven protection/derating -- see the "
        "Simulator section.",
    ),
    (
        "What does it NOT simulate yet?",
        "No switching-level semiconductor behavior, no detailed SiC/GaN device "
        "physics, no medium-frequency-transformer electromagnetics, no AC "
        "power flow -- the SST is one aggregate average-value block. See Learn "
        "→ Level 2 for exactly which real SST stages this abstracts over.",
    ),
]
for question, answer in qa:
    with st.expander(question):
        st.write(answer)

st.divider()
st.info(
    "This is an educational, system-level, average-value model. It is **not** "
    "calibrated to any specific commercial SST, and does not represent detailed "
    "AFE, DC/DC, medium-frequency-transformer, PWM, or semiconductor physics. "
    "See the Learn section for exactly what the current model does and does not "
    "represent at each architectural level."
)
