"""Page B: upload, validate, preview and run the analysis."""
from __future__ import annotations

from datetime import datetime
from html import escape

import streamlit as st

from app import config
from app.components import cards
from app.utils import state
from app.utils.analysis import AnalysisError, run_analysis
from app.utils.artifacts import ArtifactError
from app.utils.validation import (
    CSVReadError,
    read_uploaded_csv,
    validate_traffic_dataframe,
)


def _ingest(uploaded) -> str | None:
    """Parse + validate a newly uploaded file. Returns an error message or None."""
    signature = (uploaded.name, uploaded.size)
    meta = state.get_upload_meta()
    if meta is not None and meta.signature == signature:
        return None  # same file as before: do not re-parse on every rerun

    with st.spinner("Reading and validating file…"):
        try:
            df, encoding = read_uploaded_csv(uploaded)
        except CSVReadError as exc:
            state.clear_upload()
            return str(exc)
        validation = validate_traffic_dataframe(df)

    state.store_upload(
        df,
        state.UploadMeta(
            file_name=uploaded.name,
            size_bytes=uploaded.size,
            encoding=encoding,
            validation=validation,
            uploaded_at=datetime.now(),
        ),
    )
    return None


def _file_banner(meta: state.UploadMeta) -> None:
    size_mb = meta.size_bytes / 1024**2
    st.markdown(
        f'<div class="sx-card"><div class="sx-kpi-label">Selected file</div>'
        f'<div style="margin-top:.3rem;font-size:1rem;font-weight:600">{escape(meta.file_name)}</div>'
        f'<div class="sx-kpi-sub">{size_mb:.2f} MB · encoding {escape(meta.encoding)}</div></div>',
        unsafe_allow_html=True,
    )


def _validation_summary(meta: state.UploadMeta) -> None:
    v = meta.validation
    found = config.EXPECTED_FEATURE_COUNT - len(v.missing_columns)
    cols = st.columns(4)
    with cols[0]:
        cards.kpi_card("Rows", f"{v.n_rows:,}", tone="accent")
    with cols[1]:
        cards.kpi_card("Columns", f"{v.n_columns:,}", tone="accent")
    with cols[2]:
        cards.kpi_card(
            "Required features",
            f"{found}/{config.EXPECTED_FEATURE_COUNT}",
            "all present" if not v.missing_columns else "missing columns",
            tone="benign" if not v.missing_columns else "attack",
        )
    with cols[3]:
        needs = v.quality.rows_needing_imputation
        cards.kpi_card(
            "Rows needing imputation",
            f"{needs:,}",
            "NaN or infinite values" if needs else "none",
            tone="warning" if needs else "benign",
        )

    st.write("")
    for message in v.errors:
        st.error(message)
    for message in v.warnings:
        st.warning(message)
    for message in v.notices:
        st.info(message)
    if v.is_valid and not (v.warnings or v.notices):
        st.success("Validation passed. No data-quality issues were found.")
    elif v.is_valid:
        st.success("Validation passed. The file can be analyzed (see notes above).")


def _validation_details(meta: state.UploadMeta) -> None:
    v = meta.validation
    if v.missing_columns:
        with st.expander(f"Missing required columns ({len(v.missing_columns)})", expanded=True):
            st.code("\n".join(v.missing_columns), language=None)
    if v.non_numeric:
        with st.expander(f"Non-numeric values ({len(v.non_numeric)} columns)", expanded=True):
            st.dataframe(
                [
                    {"Feature": name, "Cells": info.count, "Example rows": ", ".join(map(str, info.example_rows))}
                    for name, info in v.non_numeric.items()
                ],
                use_container_width=True,
                hide_index=True,
            )
    if v.quality.has_issues:
        with st.expander("Data-quality details (missing and infinite values per feature)"):
            st.dataframe(v.quality.to_frame(), use_container_width=True, hide_index=True)
            st.caption(
                "Infinite values are converted to NaN, then every NaN is filled with the "
                "training median stored in the saved imputer. No rows are removed."
            )
    if v.extra_columns or v.ignored_reserved_columns or v.trimmed_columns:
        with st.expander("Column handling"):
            if v.ignored_reserved_columns:
                st.markdown("**Reserved (never model input, kept in report):** " + ", ".join(f"`{c}`" for c in v.ignored_reserved_columns))
            if v.extra_columns:
                shown = v.extra_columns[:40]
                more = len(v.extra_columns) - len(shown)
                st.markdown("**Ignored for prediction, kept in report:** " + ", ".join(f"`{c}`" for c in shown) + (f" … and {more} more" if more > 0 else ""))
            if v.trimmed_columns:
                st.markdown("**Matched after trimming spaces:** " + ", ".join(f"`{k}` → `{t}`" for k, t in list(v.trimmed_columns.items())[:20]))


def _preview() -> None:
    cards.section_title("Dataset preview")
    df = state.get_upload_df()
    if df is None and state.has_result():
        df = state.get_result().original_df()
    if df is None:
        return
    shown = min(len(df), config.PREVIEW_ROWS)
    st.dataframe(df.head(shown), use_container_width=True, hide_index=True)
    st.caption(f"Showing the first {shown:,} of {len(df):,} rows.")


def _completed(meta: state.UploadMeta) -> None:
    result = state.get_result()
    if result is None:
        return
    st.success(
        f"Analysis complete: {result.total:,} flows classified "
        f"({result.attack_count:,} ATTACK, {result.benign_count:,} BENIGN) "
        f"in {result.duration_seconds:.1f} s."
    )
    if result.infinite_cells_converted:
        st.caption(f"{result.infinite_cells_converted:,} infinite value(s) were converted to NaN before prediction.")
    c1, c2, _ = st.columns([1, 1, 3])
    with c1:
        cards.nav_button("View threat detection", "Threat Detection", "go_threats", primary=True)
    with c2:
        cards.nav_button("View analytics", "Analytics", "go_analytics")


def render() -> None:
    cards.page_header(
        "Traffic Analysis",
        "Upload a CSV of network flow records. The file is validated before any prediction is made.",
    )

    uploaded = st.file_uploader(
        "Upload network flow CSV",
        type=["csv"],
        key=state.uploader_key(),
        help=f"CSV only, up to {config.MAX_UPLOAD_MB} MB. All {config.EXPECTED_FEATURE_COUNT} model features are required; extra columns are ignored.",
    )

    try:
        if uploaded is not None:
            error = _ingest(uploaded)
            if error:
                st.error(error)
                return
        else:
            meta = state.get_upload_meta()
            if meta is not None and not meta.analyzed:
                state.clear_upload()  # file removed from the uploader before analysis
    except ArtifactError as exc:
        st.error(str(exc))
        return

    meta = state.get_upload_meta()
    if meta is None:
        if state.has_result():
            result = state.get_result()
            st.info(
                f"The last analysis ({result.source_name}, {result.total:,} flows) is still available "
                "in the other pages. Upload another file to analyze new traffic."
            )
        else:
            cards.empty_state(
                "No file selected",
                f"Upload a CSV containing the {config.EXPECTED_FEATURE_COUNT} flow features used to train the model. "
                "This prototype analyzes uploaded flow files; it does not capture live traffic.",
                icon="📁",
            )
        return

    _file_banner(meta)
    cards.section_title("Validation")
    _validation_summary(meta)
    _validation_details(meta)

    if meta.analyzed:
        cards.section_title("Result")
        _completed(meta)
    elif meta.validation.is_valid:
        cards.section_title("Run")
        if st.button("Run analysis", type="primary", key="run_analysis"):
            df = state.get_upload_df()
            if df is None:
                st.error("The uploaded data is no longer available. Please upload the file again.")
            else:
                try:
                    with st.spinner(f"Classifying {len(df):,} flows…"):
                        result = run_analysis(df, meta.file_name, meta.validation)
                    state.store_result(result)
                except AnalysisError as exc:
                    st.error(str(exc))
                else:
                    _completed(meta)
    else:
        st.warning("Fix the issues above and upload the corrected file to continue.")

    _preview()
