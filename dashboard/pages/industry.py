"""Industry page: structured, curated public SST / AI-power intelligence.

Reads a local, curated YAML knowledge base (data/industry/*.yaml) via
dashboard/adapters/industry_data.py -- no scraping, no live web access
from the app itself (see CLAUDE.md / V1.1 scope). Visually separates
Commercial Product / Industry Architecture & Standard / Research, and
clearly flags any "sample" placeholder record so it cannot be mistaken
for a verified one.
"""

from __future__ import annotations

import streamlit as st

from dashboard.adapters.industry_data import MATURITY_LABELS, load_records
from dashboard.components.console_theme import inject_console_css
from dashboard.components.palette import CATS, CHROME, STATUS

inject_console_css()

st.title("Industry")
st.caption(
    "A structured, curated public-knowledge base -- not a news feed. Every verified record "
    "carries a real public source; sample records are explicitly flagged as placeholders."
)

records = load_records()

st.subheader("Maturity legend")
legend_cols = st.columns(3)
legend_colors = {"commercial_product": STATUS["good"], "architecture_standard": CATS["blue"], "research": CATS["violet"]}
for col, (maturity, label) in zip(legend_cols, MATURITY_LABELS.items()):
    color = legend_colors[maturity]
    col.markdown(
        f'<span class="status-chip"><span class="dot" style="background:{color};"></span>{label}</span>',
        unsafe_allow_html=True,
    )

st.divider()

organizations = sorted({r.organization for r in records})
categories = sorted({r.category for r in records})
tech_areas = sorted({r.technology_area for r in records})

filter_cols = st.columns(3)
selected_orgs = filter_cols[0].multiselect("Organization", organizations)
selected_cats = filter_cols[1].multiselect("Category", categories)
selected_tech = filter_cols[2].multiselect("Technology area", tech_areas)

filtered = [
    r
    for r in records
    if (not selected_orgs or r.organization in selected_orgs)
    and (not selected_cats or r.category in selected_cats)
    and (not selected_tech or r.technology_area in selected_tech)
]
filtered.sort(key=lambda r: r.date, reverse=True)

st.subheader(f"Latest Developments ({len(filtered)})")

for record in filtered:
    with st.container(border=True):
        header_cols = st.columns([4, 1])
        with header_cols[0]:
            st.markdown(f"**{record.title}**")
            st.markdown(
                f'<span class="console-mono" style="color:{CHROME["text_secondary"]};font-size:0.8rem;">'
                f"{record.organization} · {record.date} · {record.category}</span>",
                unsafe_allow_html=True,
            )
        with header_cols[1]:
            color = legend_colors[record.maturity]
            st.markdown(
                f'<span class="status-chip"><span class="dot" style="background:{color};"></span>'
                f"{MATURITY_LABELS[record.maturity]}</span>",
                unsafe_allow_html=True,
            )
        if record.status == "sample":
            st.markdown(
                f'<span class="status-chip"><span class="dot" style="background:{STATUS["warning"]};"></span>'
                "SAMPLE — NOT A VERIFIED RECORD</span>",
                unsafe_allow_html=True,
            )
        st.write(record.summary)
        if record.relevance_to_sst:
            st.caption(f"**Relevance to SST:** {record.relevance_to_sst}")
        if record.relevance_to_ai_data_centers:
            st.caption(f"**Relevance to AI data centers:** {record.relevance_to_ai_data_centers}")
        if record.status == "verified":
            st.markdown(f"[{record.source_name}]({record.source_url}) · verified {record.verified_date}")
        else:
            st.caption("No source — illustrative placeholder only.")
