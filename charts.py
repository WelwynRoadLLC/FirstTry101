"""
Bloomberg/Factset-style Plotly chart builder.

Dark background, colorful high-contrast lines, monospace font.
"""

import pandas as pd
import plotly.graph_objects as go
from config import LINE_COLORS


def _format_value(value: float, metric: str) -> str:
    """Human-readable axis tick labels."""
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}K"
    return str(int(value))


def build_chart(df: pd.DataFrame, metric: str, period_label: str) -> go.Figure:
    """
    Build a Bloomberg-style dark line chart.

    Args:
        df:           DataFrame with columns [date, app_name, value]
        metric:       Metric display name, e.g. "Downloads", "DAU", "MAU"
        period_label: Human-readable period, e.g. "Last 12 Months"

    Returns:
        Plotly Figure
    """
    fig = go.Figure()

    apps = df["app_name"].unique()

    for i, app in enumerate(apps):
        app_df = df[df["app_name"] == app].sort_values("date")
        color = LINE_COLORS[i % len(LINE_COLORS)]

        fig.add_trace(
            go.Scatter(
                x=app_df["date"],
                y=app_df["value"],
                mode="lines+markers",
                name=app,
                line=dict(color=color, width=2),
                marker=dict(size=4, color=color),
                hovertemplate=(
                    f"<b>{app}</b><br>"
                    "%{x|%b %Y}<br>"
                    f"{metric}: %{{y:,.0f}}<extra></extra>"
                ),
            )
        )

    title = f"US {metric} — {period_label}"

    fig.update_layout(
        title=dict(
            text=title,
            font=dict(family="Courier New, monospace", size=18, color="#ffffff"),
            x=0.0,
            xanchor="left",
        ),
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(family="Courier New, monospace", color="#cccccc"),
        xaxis=dict(
            showgrid=True,
            gridcolor="#1a1a1a",
            gridwidth=1,
            tickformat="%b %Y",
            tickfont=dict(color="#999999", size=11),
            linecolor="#333333",
            tickangle=-30,
            dtick="M3",
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#1a1a1a",
            gridwidth=1,
            tickfont=dict(color="#999999", size=11),
            linecolor="#333333",
            tickformat=",",
        ),
        legend=dict(
            bgcolor="#0d0d0d",
            bordercolor="#333333",
            borderwidth=1,
            font=dict(color="#cccccc", size=11),
            orientation="v",
            x=1.01,
            xanchor="left",
            y=1,
            yanchor="top",
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#111111",
            font=dict(color="#ffffff", family="Courier New, monospace"),
            bordercolor="#333333",
        ),
        margin=dict(l=60, r=180, t=60, b=60),
    )

    return fig
