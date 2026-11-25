"""SentinelAI entry point.

Run from the project root:

    streamlit run app/main.py

Responsibilities: make the project root importable (so that
``from app.predictor import predict_network_traffic`` works), configure the
page, render the sidebar navigation and route to the selected view.
"""
from __future__ import annotations

import sys
from pathlib import Path

# `streamlit run app/main.py` puts only app/ on sys.path. Adding the project
# root lets `import app.*` (including the existing app/predictor.py) resolve.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import logging  # noqa: E402

import streamlit as st  # noqa: E402

from app import config  # noqa: E402

# Must be the first Streamlit command of the script run.
st.set_page_config(
    page_title=f"{config.APP_NAME} · Network Intrusion Detection",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app.components import cards, styles  # noqa: E402
from app.utils import state  # noqa: E402
from app.utils.analysis import check_engine  # noqa: E402
from app.views import analytics, model_info, overview, threat_detection, traffic_analysis  # noqa: E402

LOGGER = logging.getLogger("sentinelai")

ROUTES = {
    "Overview": overview.render,
    "Traffic Analysis": traffic_analysis.render,
    "Threat Detection": threat_detection.render,
    "Analytics": analytics.render,
    "Model Information": model_info.render,
}


def _sidebar() -> str:
    with st.sidebar:
        st.markdown(
            '<div class="sx-brand"><div class="sx-brand-mark">🛡️</div><div>'
            f'<div class="sx-brand-name">{config.APP_NAME}</div>'
            f'<div class="sx-brand-tag">{config.APP_TAGLINE}</div></div></div>',
            unsafe_allow_html=True,
        )
        st.write("")
        st.radio("Navigation", config.PAGES, key=state.KEY_PAGE, label_visibility="collapsed")
        st.divider()

        ok, _ = check_engine()
        cards.status_badge("ENGINE READY" if ok else "ENGINE ERROR", "benign" if ok else "attack")

        result = state.get_result()
        if result is not None:
            st.caption(f"Loaded analysis: {result.source_name} ({result.total:,} flows)")
        else:
            st.caption("No traffic analyzed yet.")

        st.button("Reset session", on_click=state.reset_session, help="Clear uploads, results and history.")
        st.divider()
        st.markdown(
            '<div class="sx-footnote">Analyzes uploaded flow CSV files with a binary '
            "BENIGN / ATTACK classifier. Not a live network monitor. Predictions are "
            "model outputs, not confirmed incidents.</div>",
            unsafe_allow_html=True,
        )
    return state.get_page()


def main() -> None:
    state.init_state()
    styles.inject_css()
    page = _sidebar()
    try:
        ROUTES[page]()
    except Exception as exc:  # last-resort guard: never show a raw traceback/paths
        LOGGER.exception("Unhandled error while rendering %s", page)
        st.error(
            f"Something went wrong while rendering this page ({type(exc).__name__}). "
            "Try again, or reset the session from the sidebar."
        )


main()
