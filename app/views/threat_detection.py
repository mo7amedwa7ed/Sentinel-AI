"""Page C: detailed prediction results, filters and CSV report download."""
from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd
import streamlit as st

from app import config
from app.components import cards
from app.utils import state
from app.utils.analysis import AnalysisResult, build_report_csv

FILTERS = {"All flows": "ALL", "Attacks only": config.LABEL_ATTACK, "Benign only": config.LABEL_BENIGN}
PAGE_SIZES = (100, 250, 500, 1000)


def _label_style(value: object) -> str:
    c = config.COLORS
    if value == config.LABEL_ATTACK:
        return f"color:{c['attack']};font-weight:700;background-color:rgba(239,68,68,.14)"
    if value == config.LABEL_BENIGN:
        return f"color:{c['benign']};font-weight:700;background-color:rgba(34,197,94,.12)"
    return ""


def _styled(page: pd.DataFrame, column: str):
    styler = page.style
    apply = getattr(styler, "map", None) or styler.applymap  # pandas >= 2.1 vs 2.0
    return apply(_label_style, subset=[column])


def _download_name(source: str, selection: str) -> str:
    stem = re.sub(r"\.csv$", "", source, flags=re.IGNORECASE)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_")[:50] or "traffic"
    return f"sentinelai_report_{stem}_{selection.lower()}.csv"


def _results_table(result: AnalysisResult) -> None:
    pred = result.prediction_column
    f1, f2, f3 = st.columns([3, 1, 1])
    with f1:
        choice = st.radio("Show", list(FILTERS), horizontal=True, key="td_filter")
    with f2:
        page_size = st.selectbox("Rows per page", PAGE_SIZES, key="td_page_size")

    selection = FILTERS[choice]
    labels = result.report_df[pred]
    positions = np.arange(len(labels)) if selection == "ALL" else np.flatnonzero((labels == selection).to_numpy())
    n = len(positions)
    if n == 0:
        st.info("No flows match this filter.")
        return

    n_pages = max(1, math.ceil(n / page_size))
    with f3:
        if n_pages > 1:
            # key includes the filter/size so the page resets instead of going out of range
            page_no = int(st.number_input("Page", 1, n_pages, 1, key=f"td_page_{choice}_{page_size}_{n_pages}"))
        else:
            page_no = 1
            st.write("")
    start = (page_no - 1) * page_size
    page_positions = positions[start : start + page_size]

    page = result.report_df.iloc[page_positions]
    ordered = [pred] + [c for c in page.columns if c != pred]
    page = page[ordered].copy()
    page.insert(0, "Row #", page_positions + 1)

    st.dataframe(_styled(page, pred), use_container_width=True, hide_index=True)
    st.caption(
        f"Rows {start + 1:,}–{start + len(page):,} of {n:,} matching flows · page {page_no} of {n_pages}. "
        "The prediction column is shown first; all original columns are included."
    )


def _download(result: AnalysisResult) -> None:
    cards.section_title("Download report")
    st.caption(
        "The report contains every original column and row of the upload plus one appended "
        f"`{result.prediction_column}` column."
    )
    options = {"All flows": "ALL", "Attacks only": config.LABEL_ATTACK, "Benign only": config.LABEL_BENIGN}
    c1, c2, _ = st.columns([1.3, 1.3, 2.4])
    with c1:
        choice = st.selectbox("Report contents", list(options), key="td_export_choice")
    selection = options[choice]
    rows = {"ALL": result.total, config.LABEL_ATTACK: result.attack_count, config.LABEL_BENIGN: result.benign_count}[selection]
    export = state.get_export(result.token, selection)

    with c2:
        st.write("")
        st.write("")
        if export is None:
            if st.button(f"Prepare CSV ({rows:,} rows)", key="td_prepare", disabled=rows == 0):
                with st.spinner("Building report…"):
                    export = build_report_csv(result, selection)
                state.set_export(result.token, selection, export)
        if export is not None:
            st.download_button(
                f"Download CSV ({export.rows:,} rows)",
                data=export.data,
                file_name=_download_name(result.source_name, selection),
                mime="text/csv",
                key="td_download",
                type="primary",
            )
    if export is not None and export.neutralized_cells:
        st.info(
            f"{export.neutralized_cells:,} text cell(s) beginning with = + - or @ were prefixed with an "
            "apostrophe in this download so spreadsheet software cannot run them as formulas. "
            "The data inside the app is unchanged."
        )


def render() -> None:
    cards.page_header("Threat Detection", "Per-flow classification of the uploaded traffic: BENIGN or ATTACK.")
    result = state.get_result()
    if result is None:
        cards.empty_state(
            "No analysis available",
            "Upload and analyze a flow CSV first. Results appear here once the analysis has run.",
            icon="🛡️",
        )
        st.write("")
        cards.nav_button("Go to Traffic Analysis", "Traffic Analysis", "td_go_upload", primary=True)
        return

    st.caption(f"Source: {result.source_name} · analyzed {result.analyzed_at:%Y-%m-%d %H:%M:%S}")
    cols = st.columns(4)
    with cols[0]:
        cards.kpi_card("Flows analyzed", f"{result.total:,}", tone="accent")
    with cols[1]:
        cards.kpi_card("BENIGN", f"{result.benign_count:,}", f"{result.benign_pct:.2f}% of flows", tone="benign")
    with cols[2]:
        cards.kpi_card("ATTACK", f"{result.attack_count:,}", f"{result.attack_pct:.2f}% of flows", tone="attack")
    with cols[3]:
        cards.kpi_card("Attack percentage", f"{result.attack_pct:.2f}%", tone="warning" if result.attack_count else "benign")

    cards.section_title("Prediction table")
    _results_table(result)
    _download(result)
    st.caption(
        "Labels are binary model predictions (BENIGN or ATTACK). They are not confirmed ground truth "
        "and the model does not identify attack categories."
    )
