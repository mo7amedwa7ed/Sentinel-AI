"""Page A: overview dashboard (session-level summary and system status)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app import config
from app.components import cards, charts
from app.utils import state
from app.utils.analysis import check_engine


def _status_row() -> None:
    ok, message = check_engine()
    left, right = st.columns([1, 3])
    with left:
        cards.status_badge("SYSTEM READY" if ok else "ATTENTION REQUIRED", "benign" if ok else "attack")
    with right:
        st.caption(
            "Detection engine loaded. Mode: uploaded flow-file analysis (no live capture)."
            if ok
            else message
        )


def _history_table(history: list[state.HistoryEntry]) -> None:
    frame = pd.DataFrame(
        [
            {
                "Time": h.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "File": h.file_name,
                "Flows": h.total,
                "BENIGN": h.benign,
                "ATTACK": h.attack,
                "Attack %": round(h.attack_pct, 2),
            }
            for h in history
        ]
    )
    st.dataframe(
        frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Flows": st.column_config.NumberColumn(format="%d"),
            "BENIGN": st.column_config.NumberColumn(format="%d"),
            "ATTACK": st.column_config.NumberColumn(format="%d"),
            "Attack %": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )


def render() -> None:
    cards.page_header(
        "Overview",
        "Summary of the traffic analyzed in this session. SentinelAI classifies uploaded network flow records as BENIGN or ATTACK.",
    )
    _status_row()
    st.write("")

    result = state.get_result()
    if result is None:
        cards.empty_state(
            "No traffic analyzed yet",
            "Upload a network flow CSV to see totals, the benign/attack split and recent activity. "
            "Nothing is shown until real predictions exist.",
            icon="🛰️",
        )
        st.write("")
        cards.nav_button("Upload traffic for analysis", "Traffic Analysis", "ov_go_upload", primary=True)
        return

    st.caption(f"Latest analysis: {result.source_name} · {result.analyzed_at:%Y-%m-%d %H:%M:%S}")
    cols = st.columns(4)
    with cols[0]:
        cards.kpi_card("Total analyzed flows", f"{result.total:,}", tone="accent")
    with cols[1]:
        cards.kpi_card("Benign flows", f"{result.benign_count:,}", f"{result.benign_pct:.2f}%", tone="benign")
    with cols[2]:
        cards.kpi_card("Detected attacks", f"{result.attack_count:,}", f"{result.attack_pct:.2f}%", tone="attack")
    with cols[3]:
        cards.kpi_card("Attack percentage", f"{result.attack_pct:.2f}%", tone="warning" if result.attack_count else "benign")

    cards.section_title("Distribution")
    left, right = st.columns([1, 1])
    with left:
        charts.show(charts.distribution_donut(result.benign_count, result.attack_count))
    with right:
        charts.show(charts.distribution_bar(result.benign_count, result.attack_count))

    history = state.get_history()
    cards.section_title("Recent analysis activity")
    total_flows = sum(h.total for h in history)
    st.caption(f"{len(history)} analysis run(s) in this session · {total_flows:,} flows in total.")
    h_left, h_right = st.columns([1.5, 1])
    with h_left:
        _history_table(history)
    with h_right:
        charts.show(charts.history_bar(history))

    st.write("")
    c1, c2, _ = st.columns([1, 1, 3])
    with c1:
        cards.nav_button("Open threat detection", "Threat Detection", "ov_go_threats", primary=True)
    with c2:
        cards.nav_button("Open analytics", "Analytics", "ov_go_analytics")
