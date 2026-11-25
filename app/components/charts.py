"""Plotly figure builders sharing one dark SOC style.

Every function returns a ``plotly.graph_objects.Figure``; ``show`` renders it.
Only counts and statistics of the *uploaded data* are plotted here, plus the
documented confusion matrix when real values are configured.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app import config

C = config.COLORS
LABEL_COLORS = {config.LABEL_BENIGN: C["benign"], config.LABEL_ATTACK: C["attack"]}
_FONT = "Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif"


def show(fig: go.Figure) -> None:
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})


def _style(fig: go.Figure, *, height: int = 340, title: str | None = None) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=_FONT, color=C["text"], size=13),
        height=height,
        margin=dict(l=10, r=10, t=48 if title else 16, b=10),
        legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"),
        hoverlabel=dict(bgcolor=C["surface_alt"], bordercolor=C["border"], font_color=C["text"]),
    )
    if title:
        fig.update_layout(title=dict(text=title, x=0, font=dict(size=15)))
    fig.update_xaxes(gridcolor=C["border"], zerolinecolor=C["border"], linecolor=C["border"])
    fig.update_yaxes(gridcolor=C["border"], zerolinecolor=C["border"], linecolor=C["border"])
    return fig


# --------------------------------------------------------------------------- #
# Distribution charts
# --------------------------------------------------------------------------- #
def distribution_donut(benign: int, attack: int, title: str | None = "Benign vs Attack") -> go.Figure:
    fig = go.Figure(
        go.Pie(
            labels=list(config.VALID_LABELS),
            values=[benign, attack],
            hole=0.64,
            sort=False,
            marker=dict(colors=[C["benign"], C["attack"]], line=dict(color=C["bg"], width=3)),
            textinfo="percent",
            hovertemplate="%{label}: %{value:,} flows (%{percent})<extra></extra>",
        )
    )
    fig.add_annotation(
        text=f"<b>{benign + attack:,}</b><br><span style='font-size:12px;color:{C['text_muted']}'>flows</span>",
        showarrow=False,
        font=dict(size=22),
    )
    return _style(fig, title=title)


def distribution_bar(benign: int, attack: int, title: str | None = "Flow counts by predicted class") -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=list(config.VALID_LABELS),
            y=[benign, attack],
            marker_color=[C["benign"], C["attack"]],
            text=[f"{benign:,}", f"{attack:,}"],
            textposition="outside",
            hovertemplate="%{x}: %{y:,} flows<extra></extra>",
        )
    )
    fig.update_yaxes(title="Flows", rangemode="tozero")
    fig.update_layout(showlegend=False)
    return _style(fig, title=title)


def attack_gauge(pct: float, title: str | None = "Attack percentage") -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=pct,
            number=dict(suffix="%", valueformat=".2f", font=dict(size=34)),
            gauge=dict(
                axis=dict(range=[0, 100], tickcolor=C["text_muted"]),
                bar=dict(color=C["attack"], thickness=0.28),
                bgcolor=C["surface_alt"],
                borderwidth=0,
            ),
        )
    )
    return _style(fig, height=300, title=title)


def attack_rate_by_position(is_attack: np.ndarray, bins: int = 40) -> go.Figure:
    """Share of rows predicted ATTACK across consecutive blocks of the file.

    The x axis is *row position in the uploaded file*, not time.
    """
    n = len(is_attack)
    bins = max(1, min(bins, n))
    edges = np.linspace(0, n, bins + 1).astype(int)
    starts, ends, pcts = [], [], []
    for i in range(bins):
        seg = is_attack[edges[i] : edges[i + 1]]
        if len(seg):
            starts.append(int(edges[i]) + 1)
            ends.append(int(edges[i + 1]))
            pcts.append(float(100 * seg.mean()))
    fig = go.Figure(
        go.Bar(
            x=starts,
            y=pcts,
            customdata=np.column_stack([starts, ends]),
            marker_color=C["attack"],
            hovertemplate="Rows %{customdata[0]:,}–%{customdata[1]:,}<br>%{y:.1f}% ATTACK<extra></extra>",
        )
    )
    fig.update_xaxes(title="Row position in uploaded file")
    fig.update_yaxes(title="% predicted ATTACK", range=[0, 100])
    fig.update_layout(showlegend=False, bargap=0.15)
    return _style(fig, height=320, title="Attack share across the file")


def history_bar(entries: Sequence) -> go.Figure:
    """Stacked benign/attack counts per recorded analysis (oldest to newest)."""
    ordered = list(reversed(entries))
    labels = [f"{e.timestamp:%H:%M:%S} · {e.file_name[:18]}" for e in ordered]
    fig = go.Figure()
    fig.add_bar(x=labels, y=[e.benign for e in ordered], name=config.LABEL_BENIGN, marker_color=C["benign"])
    fig.add_bar(x=labels, y=[e.attack for e in ordered], name=config.LABEL_ATTACK, marker_color=C["attack"])
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title="Flows")
    return _style(fig, height=300, title="Session analyses")


# --------------------------------------------------------------------------- #
# Feature comparison charts (descriptive statistics of the uploaded data)
# --------------------------------------------------------------------------- #
def top_difference_bar(summary: pd.DataFrame) -> go.Figure:
    data = summary.iloc[::-1]  # largest at the top
    colors = [C["attack"] if v > 0 else C["benign"] for v in data["Std. difference"]]
    fig = go.Figure(
        go.Bar(
            x=data["Std. difference"],
            y=data["Feature"],
            orientation="h",
            marker_color=colors,
            hovertemplate="%{y}<br>Std. difference: %{x:.2f}<extra></extra>",
        )
    )
    fig.update_xaxes(title="Standardized mean difference (ATTACK − BENIGN)")
    fig.update_layout(showlegend=False)
    return _style(fig, height=400, title="Features that differ most between predicted classes")


def feature_histogram(sample: pd.DataFrame, feature: str, label_col: str, log_y: bool = False) -> go.Figure:
    fig = px.histogram(
        sample,
        x=feature,
        color=label_col,
        barmode="overlay",
        opacity=0.65,
        nbins=60,
        color_discrete_map=LABEL_COLORS,
        category_orders={label_col: list(config.VALID_LABELS)},
    )
    if log_y:
        fig.update_yaxes(type="log")
    fig.update_yaxes(title="Flows (sampled)")
    fig.update_layout(legend_title_text="")
    return _style(fig, height=380, title=f"Distribution: {feature}")


def feature_box(sample: pd.DataFrame, feature: str, label_col: str) -> go.Figure:
    fig = px.box(
        sample,
        x=label_col,
        y=feature,
        color=label_col,
        color_discrete_map=LABEL_COLORS,
        category_orders={label_col: list(config.VALID_LABELS)},
    )
    fig.update_xaxes(title="")
    fig.update_layout(showlegend=False)
    return _style(fig, height=380, title=f"Spread: {feature}")


# --------------------------------------------------------------------------- #
# Model evaluation
# --------------------------------------------------------------------------- #
def confusion_matrix_fig(cm: dict[str, int]) -> go.Figure:
    z = [[cm["TN"], cm["FP"]], [cm["FN"], cm["TP"]]]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=["Predicted BENIGN", "Predicted ATTACK"],
            y=["Actual BENIGN", "Actual ATTACK"],
            text=[[f"{v:,}" for v in row] for row in z],
            texttemplate="%{text}",
            textfont=dict(size=18),
            colorscale=[[0, C["surface_alt"]], [1, "#0E7490"]],
            showscale=False,
            hovertemplate="%{y} / %{x}: %{z:,}<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed")
    return _style(fig, height=340, title="Confusion matrix (held-out test set)")
