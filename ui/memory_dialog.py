"""Team-visible project memory and attributed history search."""
from __future__ import annotations

import json

import streamlit as st

from eir import recall
from eir.serde import to_dict
from ui import state


@st.dialog("Project memory", width="large", on_dismiss=state.close_dialog)
def render(ctx: state.PageContext) -> None:
    v = ctx.venture
    st.write("Review what your team has recorded and find earlier discussions with their sources.")
    a, b, c = st.columns(3)
    a.metric("Saved messages", len(v.conversation))
    b.metric("Daily summaries", len(v.day_summaries))
    c.metric("Assumptions", len(v.hypotheses))

    st.markdown("**Current project records**")
    st.write(v.focus.text or "Your team has not chosen a focus yet.")
    for hypothesis in v.hypotheses[:8]:
        st.write(f"• {hypothesis.statement}")
        st.caption(f"{hypothesis.rung.plain} · {hypothesis.status.value}")
    st.caption("Current records guide your Virtual EIR. Earlier statements remain attributed history; "
               "a retrieved statement does not become new evidence.")

    st.markdown("**Find an earlier discussion**")
    if v.ip_sensitive:
        st.info("History excerpts are disabled for this IP-sensitive project. Review the current business records "
                "and speak to your human EIR about sensitive material.")
    else:
        query = st.text_input("What would you like to find?", placeholder="For example: pricing, pickup, or 客户访谈",
                              key=f"memory_search_{v.id}")
        if query.strip():
            hits = recall.search(v, query)
            if not hits:
                st.info("No matching team statements or daily summaries were found. Try a project-specific word.")
            for hit in hits:
                with st.container(border=True):
                    st.caption(hit.source_label)
                    st.write(hit.text)
                    st.caption(f"Source: {hit.source_id}")
    with st.expander("Daily summaries"):
        days = sorted(v.day_summaries, key=lambda d: d.day, reverse=True)
        if not days:
            st.caption("A summary is prepared when your team returns on a later day.")
        for day in days:
            st.markdown(f"**{day.day}**")
            st.write(day.summary)
    st.download_button("Export project records", json.dumps(to_dict(v), ensure_ascii=False, indent=2),
                       file_name=f"project_records_{v.id}.json", mime="application/json",
                       key=f"memory_export_{v.id}")
    st.caption("The export includes your team's chats and practice history. Uploaded file contents are stored "
               "separately; this export alone is not a complete file backup.")
