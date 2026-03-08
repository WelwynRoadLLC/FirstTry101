"""
Fintech App Stats Dashboard

Bloomberg/Factset-style web app for comparing US fintech app download stats
using the data.ai (App Annie) Intelligence API.

Run with:
    streamlit run app.py
"""

import streamlit as st
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from config import FINTECH_APPS, DATA_AI_API_KEY
from data_client import DataAIClient
from charts import build_chart

MAX_APPS = 10

st.set_page_config(
    page_title="Fintech App Stats",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Dark theme override ───────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    html, body, [data-testid="stApp"] {
        background-color: #000000;
        color: #cccccc;
    }
    [data-testid="stSidebar"] {
        background-color: #0d0d0d;
        border-right: 1px solid #1f1f1f;
    }
    [data-testid="stSidebar"] * {
        color: #cccccc !important;
    }
    .stMultiSelect [data-baseweb="tag"] {
        background-color: #1a1a1a;
    }
    h1, h2, h3 {
        color: #ffffff;
        font-family: "Courier New", monospace;
    }
    .stDataFrame { background-color: #0d0d0d; }
    div[data-testid="metric-container"] {
        background-color: #0d0d0d;
        border: 1px solid #1f1f1f;
        border-radius: 4px;
        padding: 8px 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙ Controls")
    st.markdown("---")

    # App selector
    st.markdown("**Apps** *(select up to 10)*")
    all_app_names = list(FINTECH_APPS.keys())
    default_apps = ["Cash App", "Chime", "Current", "Venmo", "PayPal"]
    selected_apps = st.multiselect(
        label="Apps",
        options=all_app_names,
        default=default_apps,
        label_visibility="collapsed",
    )

    if len(selected_apps) > MAX_APPS:
        st.error(f"Please select no more than {MAX_APPS} apps.")
        selected_apps = selected_apps[:MAX_APPS]

    st.markdown("---")

    # Metric selector
    st.markdown("**Metric**")
    metric = st.radio(
        label="Metric",
        options=["Downloads", "DAU", "MAU"],
        index=0,
        label_visibility="collapsed",
        horizontal=True,
    )

    st.markdown("---")

    # Time period toggle
    st.markdown("**Time Period**")
    period_options = ["3M", "6M", "1Y", "2Y", "Custom"]
    period = st.radio(
        label="Time period",
        options=period_options,
        index=3,
        label_visibility="collapsed",
        horizontal=True,
    )

    today = date.today()

    if period == "Custom":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("From", value=today - relativedelta(years=2))
        with col2:
            end_date = st.date_input("To", value=today)
        period_label = f"{start_date.strftime('%b %Y')} – {end_date.strftime('%b %Y')}"
    else:
        delta_map = {
            "3M": relativedelta(months=3),
            "6M": relativedelta(months=6),
            "1Y": relativedelta(years=1),
            "2Y": relativedelta(years=2),
        }
        start_date = today - delta_map[period]
        end_date = today
        period_label_map = {
            "3M": "Last 3 Months",
            "6M": "Last 6 Months",
            "1Y": "Last 12 Months",
            "2Y": "Last 24 Months",
        }
        period_label = period_label_map[period]

    st.markdown("---")
    fetch_btn = st.button("Update Chart", use_container_width=True, type="primary")

# ── Main area ─────────────────────────────────────────────────────────────────
st.markdown("# Fintech App Stats")
st.markdown(
    f"**{metric}** · {period_label} · US · iOS"
)

client = DataAIClient(DATA_AI_API_KEY)

if client.is_demo:
    st.info(
        "**Demo mode** — no `DATA_AI_API_KEY` found. "
        "Showing estimated figures based on public reports (not official data). "
        "Add your key to `.env` to switch to live data.ai data.",
        icon="ℹ️",
    )

if not selected_apps:
    st.info("Select at least one app in the sidebar to get started.")
    st.stop()

# Auto-fetch on load, or re-fetch on button click
if fetch_btn or "last_fig" not in st.session_state:
    label = "Loading estimated data…" if client.is_demo else "Fetching data from data.ai…"
    with st.spinner(label):
        try:
            df = client.get_multi_app(selected_apps, metric, start_date, end_date)

            if df.empty:
                st.warning("No data returned for the selected apps and time range.")
                st.stop()

            chart_metric = f"{metric} (Estimated)" if client.is_demo else metric
            fig = build_chart(df, chart_metric, period_label)
            st.session_state["last_fig"] = fig
            st.session_state["last_df"] = df

        except PermissionError as e:
            st.error(f"**Authentication error:** {e}")
            st.stop()
        except RuntimeError as e:
            st.error(f"**API error:** {e}")
            st.stop()
        except Exception as e:
            st.error(f"**Unexpected error:** {e}")
            st.stop()

# Display chart
if "last_fig" in st.session_state:
    st.plotly_chart(
        st.session_state["last_fig"],
        use_container_width=True,
        config={
            "displayModeBar": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "toImageButtonOptions": {
                "format": "png",
                "filename": f"fintech_{metric}_{period}",
                "height": 720,
                "width": 1280,
                "scale": 2,
            },
        },
    )

    # Raw data table (collapsed by default)
    with st.expander("Raw Data"):
        df_display = (
            st.session_state["last_df"]
            .copy()
            .assign(date=lambda d: d["date"].dt.strftime("%Y-%m"))
            .rename(columns={"app_name": "App", "value": metric, "date": "Month"})
            .sort_values(["Month", "App"])
        )
        st.dataframe(df_display, use_container_width=True, hide_index=True)
