"""AI Power Lab -- Streamlit platform entry point.

Launch with: streamlit run app.py

This file only wires up navigation across the five platform sections.
Each page under dashboard/pages/ is pure presentation; all simulation,
content, and industry-data plumbing lives under dashboard/adapters/.
No physics or content is defined here.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="AI Power Lab", page_icon="⚡", layout="wide")

pages = [
    st.Page("dashboard/pages/overview.py", title="Overview", icon="\U0001f3e0", default=True),
    st.Page("dashboard/pages/simulator.py", title="Simulator", icon="\U0001f4c8"),
    st.Page("dashboard/pages/learn.py", title="Learn", icon="\U0001f4da"),
    st.Page("dashboard/pages/ai_datacenter.py", title="AI Data Center", icon="\U0001f5a5️"),
    st.Page("dashboard/pages/industry.py", title="Industry", icon="\U0001f30e"),
]

nav = st.navigation(pages)
nav.run()
