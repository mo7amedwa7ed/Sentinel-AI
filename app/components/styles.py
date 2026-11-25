"""Global dark SOC styling, injected once per run.

The CSS is static (no user-supplied text is ever interpolated into it).
Base theme colours come from ``.streamlit/config.toml``; this file refines
cards, spacing, the sidebar and typography.
"""
from __future__ import annotations

from string import Template

import streamlit as st

from app import config

_CSS = Template(
    """
<style>
:root { --sx-font: "Inter", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
html, body, .stApp, [class*="st-"] { font-family: var(--sx-font); }
.stApp { background: $bg; }
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px; }

/* ---- sidebar ---- */
[data-testid="stSidebar"] { background: $surface; border-right: 1px solid $border; }
[data-testid="stSidebar"] .block-container { padding-top: 1.4rem; }
.sx-brand { display: flex; align-items: center; gap: .65rem; margin-bottom: .3rem; }
.sx-brand-mark { width: 34px; height: 34px; border-radius: 9px; display: grid; place-items: center;
  background: rgba(34,211,238,.12); border: 1px solid rgba(34,211,238,.45); font-size: 1.1rem; }
.sx-brand-name { font-size: 1.2rem; font-weight: 700; letter-spacing: .02em; color: $text; line-height: 1.1; }
.sx-brand-tag { font-size: .72rem; color: $text_muted; letter-spacing: .04em; }
[data-testid="stSidebar"] [role="radiogroup"] { gap: .25rem; }
[data-testid="stSidebar"] [role="radiogroup"] label { padding: .5rem .75rem; border-radius: 8px;
  border: 1px solid transparent; width: 100%; }
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: $surface_alt; }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) { background: rgba(34,211,238,.10);
  border-color: rgba(34,211,238,.35); }
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child { display: none; }

/* ---- page header ---- */
.sx-header { margin-bottom: 1.4rem; padding-bottom: 1rem; border-bottom: 1px solid $border; }
.sx-header h1 { font-size: 1.75rem; font-weight: 700; margin: 0; padding: 0; color: $text; letter-spacing: .01em; }
.sx-header p { color: $text_muted; margin: .3rem 0 0 0; font-size: .95rem; }
.sx-section { font-size: 1.02rem; font-weight: 600; color: $text; margin: 1.6rem 0 .7rem 0;
  display: flex; align-items: center; gap: .6rem; }
.sx-section::after { content: ""; flex: 1; height: 1px; background: $border; }

/* ---- cards ---- */
.sx-card { background: $surface; border: 1px solid $border; border-radius: 12px; padding: 1rem 1.2rem;
  box-shadow: 0 1px 2px rgba(0,0,0,.35); }
.sx-kpi { border-left: 3px solid $accent; height: 100%; }
.sx-kpi-label { font-size: .7rem; text-transform: uppercase; letter-spacing: .09em; color: $text_muted; font-weight: 600; }
.sx-kpi-value { font-size: 1.9rem; font-weight: 700; color: $text; line-height: 1.25; margin-top: .15rem;
  font-variant-numeric: tabular-nums; }
.sx-kpi-sub { font-size: .8rem; color: $text_muted; margin-top: .1rem; }
.sx-tone-accent { border-left-color: $accent; }
.sx-tone-benign { border-left-color: $benign; }
.sx-tone-benign .sx-kpi-value { color: $benign; }
.sx-tone-attack { border-left-color: $attack; }
.sx-tone-attack .sx-kpi-value { color: $attack; }
.sx-tone-warning { border-left-color: $warning; }
.sx-tone-warning .sx-kpi-value { color: $warning; }
.sx-tone-neutral { border-left-color: $border; }

/* ---- badges ---- */
.sx-badge { display: inline-flex; align-items: center; gap: .45rem; padding: .28rem .7rem; border-radius: 999px;
  font-size: .76rem; font-weight: 600; letter-spacing: .04em; border: 1px solid $border; background: $surface_alt; }
.sx-badge::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.sx-badge-benign { color: $benign; border-color: rgba(34,197,94,.45); background: rgba(34,197,94,.10); }
.sx-badge-attack { color: $attack; border-color: rgba(239,68,68,.45); background: rgba(239,68,68,.10); }
.sx-badge-warning { color: $warning; border-color: rgba(245,158,11,.45); background: rgba(245,158,11,.10); }
.sx-badge-accent { color: $accent; border-color: rgba(34,211,238,.45); background: rgba(34,211,238,.10); }

/* ---- empty state ---- */
.sx-empty { text-align: center; padding: 2.8rem 1.5rem; border: 1px dashed $border; border-radius: 12px;
  background: rgba(17,26,46,.6); }
.sx-empty-icon { font-size: 2rem; margin-bottom: .4rem; }
.sx-empty h3 { margin: 0 0 .35rem 0; font-size: 1.15rem; color: $text; }
.sx-empty p { margin: 0 auto; max-width: 560px; color: $text_muted; font-size: .92rem; }

/* ---- misc widgets ---- */
.stButton > button, .stDownloadButton > button { border-radius: 8px; font-weight: 600; }
[data-testid="stFileUploader"] section { border-radius: 12px; border: 1px dashed $border; background: $surface; }
[data-testid="stDataFrame"] { border: 1px solid $border; border-radius: 10px; overflow: hidden; }
[data-testid="stExpander"] { border: 1px solid $border; border-radius: 10px; background: $surface; }
hr { border-color: $border; }
.sx-footnote { font-size: .72rem; color: $text_muted; line-height: 1.45; }
</style>
"""
)


def inject_css() -> None:
    """Inject the global stylesheet (call once at the top of every run)."""
    st.markdown(_CSS.safe_substitute(config.COLORS), unsafe_allow_html=True)
