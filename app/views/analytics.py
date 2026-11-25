"""Page D: visual summaries of the uploaded-traffic predictions."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from app import config
from app.components import cards, charts
from app.utils import state
from app.utils.analysis import AnalysisResult
from app.utils.validation import build_feature_frame

LABEL_COL = "Predicted label"


@st.cache_data(show_spinner="Computing feature statistics…")
def _feature_stats(_result: AnalysisResult, token: str):
    """Descriptive statistics comparing rows predicted ATTACK vs BENIGN.

    ``token`` (the analysis timestamp) is the cache key; ``_result`` is excluded
    from hashing. Returns (summary, sample) or (None, None) if one class is empty.
    """
    labels = _result.report_df[_result.prediction_column]
    is_attack = (labels == config.LABEL_ATTACK).to_numpy()
    if is_attack.all() or not is_attack.any():
        return None, None

    feats, _ = build_feature_frame(_result.original_df(), _result.validation.column_map)
    feats = feats.replace([np.inf, -np.inf], np.nan)  # display statistics only

    mean_attack = feats[is_attack].mean()
    mean_benign = feats[~is_attack].mean()
    std = feats.std(ddof=0).replace(0, np.nan)
    diff = (mean_attack - mean_benign) / std
    summary = (
        pd.DataFrame(
            {
                "Feature": feats.columns,
                "Mean (ATTACK)": mean_attack.to_numpy(),
                "Mean (BENIGN)": mean_benign.to_numpy(),
                "Std. difference": diff.to_numpy(),
            }
        )
        .dropna()
        .assign(_abs=lambda d: d["Std. difference"].abs())
        .sort_values("_abs", ascending=False)
        .drop(columns="_abs")
        .reset_index(drop=True)
    )

    # Stratified, capped sample keeps the plots fast on very large uploads.
    cap = config.ANALYTICS_SAMPLE_PER_CLASS
    parts = []
    for flag, name in ((True, config.LABEL_ATTACK), (False, config.LABEL_BENIGN)):
        subset = feats[is_attack == flag]
        if len(subset) > cap:
            subset = subset.sample(cap, random_state=42)
        parts.append(subset.assign(**{LABEL_COL: pd.Categorical([name] * len(subset), categories=list(config.VALID_LABELS))}))
    return summary, pd.concat(parts, ignore_index=True)


def _summary_table(result: AnalysisResult) -> None:
    q = result.validation.quality
    rows = [
        ("Source file", result.source_name),
        ("Analyzed at", f"{result.analyzed_at:%Y-%m-%d %H:%M:%S}"),
        ("Flows analyzed", f"{result.total:,}"),
        ("Columns in upload", f"{len(result.original_columns):,}"),
        ("Model features used", f"{len(result.feature_columns)}"),
        ("Rows needing imputation", f"{q.rows_needing_imputation:,}"),
        ("Missing (NaN) cells filled", f"{q.total_nan:,}"),
        ("Infinite cells converted to NaN", f"{result.infinite_cells_converted:,}"),
        ("Processing time", f"{result.duration_seconds:.2f} s"),
    ]
    st.dataframe(pd.DataFrame(rows, columns=["Item", "Value"]), use_container_width=True, hide_index=True)


def render() -> None:
    cards.page_header("Analytics", "Visual summaries of the predictions for the uploaded traffic.")
    result = state.get_result()
    if result is None:
        cards.empty_state(
            "No data to visualize",
            "Charts appear after a flow CSV has been analyzed.",
            icon="📊",
        )
        st.write("")
        cards.nav_button("Go to Traffic Analysis", "Traffic Analysis", "an_go_upload", primary=True)
        return

    cols = st.columns(4)
    with cols[0]:
        cards.kpi_card("Flows analyzed", f"{result.total:,}")
    with cols[1]:
        cards.kpi_card("BENIGN", f"{result.benign_count:,}", f"{result.benign_pct:.2f}%", tone="benign")
    with cols[2]:
        cards.kpi_card("ATTACK", f"{result.attack_count:,}", f"{result.attack_pct:.2f}%", tone="attack")
    with cols[3]:
        cards.kpi_card("Attack percentage", f"{result.attack_pct:.2f}%", tone="warning" if result.attack_count else "benign")

    cards.section_title("Class distribution")
    left, middle, right = st.columns([1.1, 1, 1])
    with left:
        charts.show(charts.distribution_donut(result.benign_count, result.attack_count))
    with middle:
        charts.show(charts.distribution_bar(result.benign_count, result.attack_count))
    with right:
        charts.show(charts.attack_gauge(result.attack_pct))

    cards.section_title("Traffic summary")
    s_left, s_right = st.columns([1, 1.4])
    with s_left:
        _summary_table(result)
    with s_right:
        is_attack = (result.report_df[result.prediction_column] == config.LABEL_ATTACK).to_numpy()
        charts.show(charts.attack_rate_by_position(is_attack))
        st.caption("Each bar covers a consecutive block of rows in the uploaded file (row order, not time).")

    cards.section_title("Feature comparison between predicted classes")
    summary, sample = _feature_stats(result, result.token)
    if summary is None:
        st.info("Only one predicted class is present in this upload, so there is nothing to compare.")
        return

    top = summary.head(10)
    t_left, t_right = st.columns([1.2, 1])
    with t_left:
        charts.show(charts.top_difference_bar(top))
    with t_right:
        shown = top.copy()
        for col in ("Mean (ATTACK)", "Mean (BENIGN)", "Std. difference"):
            shown[col] = shown[col].round(3)
        st.dataframe(shown, use_container_width=True, hide_index=True, height=400)
    st.caption(
        "Descriptive only: this compares how rows the model labelled ATTACK differ from rows it labelled BENIGN "
        "in this upload. It is not an explanation of the model's decisions and not evidence of any specific attack type."
    )

    feature = st.selectbox("Inspect a feature", list(summary["Feature"]), index=0, key="an_feature")
    log_y = st.toggle("Logarithmic count axis", value=False, key="an_log")
    h_col, b_col = st.columns(2)
    with h_col:
        charts.show(charts.feature_histogram(sample, feature, LABEL_COL, log_y))
    with b_col:
        charts.show(charts.feature_box(sample, feature, LABEL_COL))
    st.caption(
        f"Distribution plots use a stratified sample of up to {config.ANALYTICS_SAMPLE_PER_CLASS:,} rows per class "
        "for speed; counts and statistics above use all rows. Infinite values are excluded from these statistics."
    )
