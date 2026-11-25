"""Reusable UI building blocks (cards, badges, headers, empty states).

All text passed in is HTML-escaped before it reaches ``unsafe_allow_html``,
so file names or column names from an upload can never inject markup.
The HTML is deliberately written without line breaks or indentation, because
Markdown would otherwise treat indented lines as code blocks.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from app.utils import state

TONES = {"accent", "benign", "attack", "warning", "neutral"}


def _tone(tone: str) -> str:
    return tone if tone in TONES else "accent"


def page_header(title: str, subtitle: str = "") -> None:
    sub = f"<p>{escape(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f'<div class="sx-header"><h1>{escape(title)}</h1>{sub}</div>',
        unsafe_allow_html=True,
    )


def section_title(text: str) -> None:
    st.markdown(f'<div class="sx-section">{escape(text)}</div>', unsafe_allow_html=True)


def kpi_card(label: str, value: str | int | float, sub: str = "", tone: str = "accent") -> None:
    sub_html = f'<div class="sx-kpi-sub">{escape(sub)}</div>' if sub else ""
    st.markdown(
        f'<div class="sx-card sx-kpi sx-tone-{_tone(tone)}">'
        f'<div class="sx-kpi-label">{escape(label)}</div>'
        f'<div class="sx-kpi-value">{escape(str(value))}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def badge_html(text: str, tone: str = "accent") -> str:
    return f'<span class="sx-badge sx-badge-{_tone(tone)}">{escape(text)}</span>'


def status_badge(text: str, tone: str = "accent") -> None:
    st.markdown(badge_html(text, tone), unsafe_allow_html=True)


def info_card(title: str, body: str) -> None:
    st.markdown(
        f'<div class="sx-card"><div class="sx-kpi-label">{escape(title)}</div>'
        f'<div style="margin-top:.35rem;color:#E6EDF7;font-size:.92rem;line-height:1.5">{escape(body)}</div></div>',
        unsafe_allow_html=True,
    )


def empty_state(title: str, message: str, icon: str = "📡") -> None:
    st.markdown(
        f'<div class="sx-empty"><div class="sx-empty-icon">{escape(icon)}</div>'
        f"<h3>{escape(title)}</h3><p>{escape(message)}</p></div>",
        unsafe_allow_html=True,
    )


def nav_button(label: str, page: str, key: str, primary: bool = False) -> None:
    """A button that switches the active page (uses a callback, so it is safe
    to change the sidebar radio's session-state key)."""
    st.button(
        label,
        key=key,
        on_click=state.go_to,
        args=(page,),
        type="primary" if primary else "secondary",
    )
