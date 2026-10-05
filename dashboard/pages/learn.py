"""Learn page: engineering content connected to the simulator.

Not a generic encyclopedia -- content is organized by the project's
learning priority (System Architecture + Controls first, SST
architecture second, system behavior third, future deep dives last)
and every topic that has a matching demo links straight to the
Simulator page via `simulator_preselect` session state.
"""

from __future__ import annotations

import streamlit as st

from dashboard.adapters.content_loader import LEVELS, topics_by_level
from dashboard.components.console_theme import inject_console_css

inject_console_css()

st.title("Learn")
st.caption("An engineering learning system connected to the simulator -- not a generic encyclopedia.")

grouped = topics_by_level()

level_code = st.segmented_control(
    "Level", options=list(LEVELS.keys()), format_func=lambda k: LEVELS[k], default=list(LEVELS.keys())[0],
)
level_code = level_code or list(LEVELS.keys())[0]

topics = grouped[level_code]
if not topics:
    st.info("No topics yet at this level.")
    st.stop()

# A pill rail reads closer to a knowledge-map's node row than a dropdown --
# a lightweight step toward that visual language without building a full
# graph engine (out of scope for this pass; see CLAUDE.md "framework first").
topic_titles = [t.title for t in topics]
selected_title = st.pills(
    "Topic", options=topic_titles, selection_mode="single", required=True, default=topic_titles[0],
)
topic = next(t for t in topics if t.title == selected_title)

st.header(topic.title)

if topic.try_it_scenario:
    if st.button(f"Try it in Simulator: {topic.try_it_scenario}", icon=":material/play_arrow:"):
        st.session_state["simulator_preselect"] = topic.try_it_scenario
        st.switch_page("dashboard/pages/simulator.py")

sections = [
    ("What is it?", topic.what_is_it),
    ("Why does it exist?", topic.why_it_exists),
    ("Inputs / Outputs", topic.inputs_outputs),
    ("Key physics", topic.key_physics),
    ("Key control idea", topic.key_control_idea),
    ("What can go wrong?", topic.what_can_go_wrong),
    ("How AI Power Lab models it", topic.how_modeled),
    ("What the current model ignores", topic.what_ignored),
    ("Real industry relevance", topic.industry_relevance),
]

for heading, body in sections:
    if not body:
        continue
    st.subheader(heading)
    st.write(body)

if topic.equations:
    st.subheader("Important equations")
    for eq in topic.equations:
        st.code(eq, language="text")
