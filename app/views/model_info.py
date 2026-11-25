"""Page E: model card, held-out evaluation metrics and session statistics."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app import config
from app.components import cards, charts
from app.utils import state
from app.utils.artifacts import ArtifactError, load_feature_columns


def _kv_table(data: dict) -> None:
    frame = pd.DataFrame([(k, str(v)) for k, v in data.items()], columns=["Property", "Value"])
    st.dataframe(frame, use_container_width=True, hide_index=True)


def render() -> None:
    cards.page_header("Model Information", "How the detection model is built and how it performed on held-out test data.")

    cards.section_title("Model")
    left, right = st.columns(2)
    with left:
        st.markdown("**Model summary**")
        _kv_table(config.MODEL_INFO)
    with right:
        st.markdown("**Configuration**")
        _kv_table(config.MODEL_CONFIG)

    cards.section_title("Held-out test-set evaluation")
    st.info(
        f"These are historical results measured once on an independent test set of {config.TEST_SET_SIZE:,} rows "
        "during model development. They are not statistics about any file you upload, and they do not guarantee "
        "the same performance on different networks or traffic."
    )
    metrics = list(config.EVALUATION_METRICS.items())
    for row_start in range(0, len(metrics), 3):
        cols = st.columns(3)
        for col, (name, value) in zip(cols, metrics[row_start : row_start + 3]):
            with col:
                cards.kpi_card(name, f"{value:.4f}%", "test set", tone="accent")
        st.write("")

    cm = config.CONFUSION_MATRIX  # None unless real test-set counts were configured
    if cm:
        left, right = st.columns([1, 1])
        with left:
            charts.show(charts.confusion_matrix_fig(cm))
        with right:
            st.markdown("**Reading the matrix**")
            st.markdown(
                f"- True negatives (BENIGN correctly passed): **{cm['TN']:,}**\n"
                f"- False positives (BENIGN flagged as ATTACK): **{cm['FP']:,}**\n"
                f"- False negatives (ATTACK missed): **{cm['FN']:,}**\n"
                f"- True positives (ATTACK detected): **{cm['TP']:,}**"
            )
    else:
        st.caption(
            "Confusion matrix: not displayed, because the exact test-set counts have not been added to the "
            "configuration. SentinelAI never invents these values."
        )

    cards.section_title("Current session (uploaded traffic)")
    result = state.get_result()
    if result is None:
        st.caption("No uploaded traffic has been analyzed in this session.")
    else:
        cols = st.columns(4)
        with cols[0]:
            cards.kpi_card("Flows analyzed", f"{result.total:,}", "this session", tone="neutral")
        with cols[1]:
            cards.kpi_card("BENIGN predictions", f"{result.benign_count:,}", tone="neutral")
        with cols[2]:
            cards.kpi_card("ATTACK predictions", f"{result.attack_count:,}", tone="neutral")
        with cols[3]:
            cards.kpi_card("Attack percentage", f"{result.attack_pct:.2f}%", tone="neutral")
        st.caption(
            f"Predictions for {result.source_name}. These are model outputs on uploaded data, "
            "not evaluation metrics: no ground-truth labels are used here."
        )

    cards.section_title("Scope and limitations")
    st.markdown(
        "- The model is **binary**: it separates BENIGN from ATTACK and does not identify attack categories.\n"
        "- SentinelAI analyzes **uploaded flow CSV files**. It does not capture packets or monitor a live network.\n"
        f"- Input must contain the {config.EXPECTED_FEATURE_COUNT} numeric flow features used in training, "
        "in any column order; missing values are filled with the training medians."
    )

    try:
        features = load_feature_columns()
    except ArtifactError:
        features = ()
    if features:
        with st.expander(f"Required input features ({len(features)})"):
            st.dataframe(pd.DataFrame({"#": range(1, len(features) + 1), "Feature": features}), use_container_width=True, hide_index=True)
