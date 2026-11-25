"""Streamlit session-state access in one place.

Views never touch ``st.session_state`` keys directly; they use these helpers
so key names and invariants live in a single module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import streamlit as st

from app import config
from app.utils.analysis import AnalysisResult, ReportExport
from app.utils.validation import ValidationResult

KEY_PAGE = "sentinel_page"
KEY_UPLOAD_DF = "sentinel_upload_df"
KEY_UPLOAD_META = "sentinel_upload_meta"
KEY_RESULT = "sentinel_result"
KEY_HISTORY = "sentinel_history"
KEY_UPLOADER_NONCE = "sentinel_uploader_nonce"
KEY_EXPORT = "sentinel_export"


@dataclass
class UploadMeta:
    file_name: str
    size_bytes: int
    encoding: str
    validation: ValidationResult
    uploaded_at: datetime
    analyzed: bool = False

    @property
    def signature(self) -> tuple[str, int]:
        """Identifies an upload so reruns don't re-parse the same file."""
        return (self.file_name, self.size_bytes)


@dataclass(frozen=True)
class HistoryEntry:
    timestamp: datetime
    file_name: str
    total: int
    benign: int
    attack: int
    attack_pct: float


def init_state() -> None:
    """Create all keys with defaults. Safe to call on every rerun."""
    defaults = {
        KEY_PAGE: config.PAGES[0],
        KEY_UPLOAD_DF: None,
        KEY_UPLOAD_META: None,
        KEY_RESULT: None,
        KEY_HISTORY: [],
        KEY_UPLOADER_NONCE: 0,
        KEY_EXPORT: None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ---- navigation ------------------------------------------------------------ #
def get_page() -> str:
    return st.session_state[KEY_PAGE]


def go_to(page: str) -> None:
    """Navigation callback (use as ``on_click=state.go_to, args=(page,)``)."""
    if page in config.PAGES:
        st.session_state[KEY_PAGE] = page


# ---- uploader ---------------------------------------------------------------- #
def uploader_key() -> str:
    """Widget key that changes on reset so the file uploader is emptied."""
    return f"sentinel_uploader_{st.session_state[KEY_UPLOADER_NONCE]}"


# ---- pending upload ---------------------------------------------------------- #
def store_upload(df: pd.DataFrame, meta: UploadMeta) -> None:
    """Keep a parsed upload awaiting analysis. The last completed result is kept."""
    st.session_state[KEY_UPLOAD_DF] = df
    st.session_state[KEY_UPLOAD_META] = meta


def get_upload_df() -> pd.DataFrame | None:
    return st.session_state[KEY_UPLOAD_DF]


def get_upload_meta() -> UploadMeta | None:
    return st.session_state[KEY_UPLOAD_META]


def clear_upload() -> None:
    st.session_state[KEY_UPLOAD_DF] = None
    st.session_state[KEY_UPLOAD_META] = None


# ---- analysis results ---------------------------------------------------------- #
def store_result(result: AnalysisResult) -> None:
    """Save a completed analysis and log it in the activity history.

    The raw upload frame is released: ``result.original_df()`` reproduces it,
    so large files are not held in memory twice.
    """
    st.session_state[KEY_RESULT] = result
    st.session_state[KEY_UPLOAD_DF] = None
    st.session_state[KEY_EXPORT] = None
    meta = get_upload_meta()
    if meta is not None:
        meta.analyzed = True

    entry = HistoryEntry(
        timestamp=result.analyzed_at,
        file_name=result.source_name,
        total=result.total,
        benign=result.benign_count,
        attack=result.attack_count,
        attack_pct=result.attack_pct,
    )
    history = [entry, *st.session_state[KEY_HISTORY]]
    st.session_state[KEY_HISTORY] = history[: config.HISTORY_LIMIT]


def get_result() -> AnalysisResult | None:
    return st.session_state[KEY_RESULT]


def has_result() -> bool:
    return st.session_state[KEY_RESULT] is not None


def get_history() -> list[HistoryEntry]:
    return list(st.session_state[KEY_HISTORY])


# ---- prepared report export ------------------------------------------------------ #
def set_export(token: str, selection: str, export: ReportExport) -> None:
    st.session_state[KEY_EXPORT] = (token, selection, export)


def get_export(token: str, selection: str) -> ReportExport | None:
    """Return the prepared export only if it matches this result and selection."""
    stored = st.session_state[KEY_EXPORT]
    if stored and stored[0] == token and stored[1] == selection:
        return stored[2]
    return None


def reset_session() -> None:
    """Clear uploads, results, history and the file uploader (keeps the page)."""
    st.session_state[KEY_UPLOAD_DF] = None
    st.session_state[KEY_UPLOAD_META] = None
    st.session_state[KEY_RESULT] = None
    st.session_state[KEY_HISTORY] = []
    st.session_state[KEY_EXPORT] = None
    st.session_state[KEY_UPLOADER_NONCE] += 1
