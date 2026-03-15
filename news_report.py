"""
Daily Morning Research Report

AI-powered news crawler and report generator.
Fetches articles from RSS feeds, filters by topics, and uses Claude to
synthesize a polished morning briefing.

Run with:
    streamlit run news_report.py
"""

import os
from datetime import date

import streamlit as st
from dotenv import load_dotenv

from news_crawler import (
    ALL_CATEGORIES,
    NEWS_SOURCES,
    fetch_articles,
    filter_by_topics,
    enrich_with_full_text,
)
from report_generator import generate_report

load_dotenv()

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Morning Research Report",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Dark Theme ────────────────────────────────────────────────────────────────
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
    [data-testid="stSidebar"] * { color: #cccccc !important; }
    h1, h2, h3, h4 {
        color: #ffffff;
        font-family: "Courier New", monospace;
    }
    .stButton > button {
        background-color: #1a1a1a;
        color: #ffffff;
        border: 1px solid #333;
    }
    .stButton > button:hover { border-color: #888; }
    .stTextInput input, .stTextArea textarea {
        background-color: #0d0d0d;
        color: #cccccc;
        border: 1px solid #1f1f1f;
    }
    .stCheckbox label { color: #cccccc !important; }
    div[data-testid="metric-container"] {
        background-color: #0d0d0d;
        border: 1px solid #1f1f1f;
        border-radius: 4px;
        padding: 8px 16px;
    }
    .report-box {
        background-color: #0d0d0d;
        border: 1px solid #1f1f1f;
        border-radius: 6px;
        padding: 24px 28px;
        font-family: "Georgia", serif;
        line-height: 1.7;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📰 Report Settings")
    st.markdown("---")

    # API key
    st.markdown("**Anthropic API Key**")
    env_key = os.getenv("ANTHROPIC_API_KEY", "")
    api_key_input = st.text_input(
        "API Key",
        value=env_key,
        type="password",
        placeholder="sk-ant-...",
        label_visibility="collapsed",
    )
    if not api_key_input:
        st.warning("Add your Anthropic API key to generate reports.")

    st.markdown("---")

    # Categories
    st.markdown("**News Categories**")
    selected_categories = []
    default_cats = {"General", "Business & Finance", "Technology"}
    for cat in ALL_CATEGORIES:
        if st.checkbox(cat, value=(cat in default_cats)):
            selected_categories.append(cat)

    st.markdown("---")

    # Topics / keywords
    st.markdown("**Topic Filters** *(optional)*")
    st.caption("Comma-separated keywords to focus the report. Leave blank for all news.")
    topics_input = st.text_area(
        "Topics",
        placeholder="e.g. AI, interest rates, climate, earnings",
        height=80,
        label_visibility="collapsed",
    )
    topics = [t.strip() for t in topics_input.split(",") if t.strip()] if topics_input else []

    st.markdown("---")

    # Crawl options
    st.markdown("**Crawl Options**")
    max_per_feed = st.slider("Articles per feed", min_value=5, max_value=25, value=10)
    fetch_full = st.checkbox(
        "Fetch full article text",
        value=False,
        help="Slower but gives Claude richer context. Fetches up to 15 articles.",
    )

    st.markdown("---")

    generate_btn = st.button(
        "Generate Morning Report",
        use_container_width=True,
        type="primary",
        disabled=not api_key_input,
    )

# ── Main Area ─────────────────────────────────────────────────────────────────
today = date.today()

st.markdown("# Daily Morning Research Report")
st.markdown(f"*{today.strftime('%A, %B %d, %Y')}*")
st.markdown("---")

if generate_btn:
    if not selected_categories:
        st.error("Select at least one news category in the sidebar.")
        st.stop()

    # Step 1: Crawl
    with st.status("Crawling news feeds…", expanded=True) as status:
        st.write(f"Fetching from {sum(len(NEWS_SOURCES[c]) for c in selected_categories)} feeds…")
        articles = fetch_articles(selected_categories, max_per_feed=max_per_feed)
        st.write(f"Found **{len(articles)}** articles.")

        if topics:
            articles = filter_by_topics(articles, topics)
            st.write(f"After topic filtering: **{len(articles)}** articles match your keywords.")

        if not articles:
            status.update(label="No articles found.", state="error")
            st.error(
                "No articles matched your filters. "
                "Try broader topics or more categories."
            )
            st.stop()

        if fetch_full:
            st.write(f"Fetching full text for up to 15 articles…")
            articles = enrich_with_full_text(articles, max_articles=15)

        status.update(label=f"Crawl complete — {len(articles)} articles ready.", state="complete")

    # Stats row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Articles", len(articles))
    with col2:
        sources = {a.source for a in articles}
        st.metric("Sources", len(sources))
    with col3:
        cats = {a.category for a in articles}
        st.metric("Categories", len(cats))

    st.markdown("---")

    # Step 2: Generate report via Claude (streaming)
    st.markdown("### Generating report with Claude…")
    report_placeholder = st.empty()

    report_text = ""
    try:
        for chunk in generate_report(
            articles=articles,
            topics=topics,
            report_date=today,
            api_key=api_key_input,
        ):
            report_text += chunk
            report_placeholder.markdown(
                f'<div class="report-box">{report_text}</div>',
                unsafe_allow_html=True,
            )
    except Exception as e:
        st.error(f"Report generation failed: {e}")
        st.stop()

    # Store in session so it survives reruns
    st.session_state["report"] = report_text
    st.session_state["report_date"] = today.isoformat()
    st.session_state["article_count"] = len(articles)

    # Download button
    st.markdown("---")
    st.download_button(
        label="Download Report (.md)",
        data=report_text,
        file_name=f"morning_report_{today.isoformat()}.md",
        mime="text/markdown",
    )

    # Article list (collapsed)
    with st.expander(f"View all {len(articles)} crawled articles"):
        for a in articles:
            pub = a.published.strftime("%Y-%m-%d %H:%M") if a.published else "—"
            st.markdown(f"- **[{a.title}]({a.url})** — {a.source} · {a.category} · {pub}")

elif "report" in st.session_state:
    # Show last generated report
    st.info(
        f"Showing report from {st.session_state['report_date']} "
        f"({st.session_state['article_count']} articles). "
        "Click **Generate Morning Report** to refresh.",
        icon="ℹ️",
    )
    st.markdown(
        f'<div class="report-box">{st.session_state["report"]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.download_button(
        label="Download Report (.md)",
        data=st.session_state["report"],
        file_name=f"morning_report_{st.session_state['report_date']}.md",
        mime="text/markdown",
    )
else:
    # Landing state
    st.markdown(
        """
        ### How it works

        1. **Select categories** in the sidebar (General, Finance, Tech, etc.)
        2. Optionally enter **topic keywords** to focus the report (e.g. `AI, Fed, earnings`)
        3. Click **Generate Morning Report**

        Claude will crawl the latest RSS feeds, filter the articles, and write
        a structured briefing covering:
        - Executive summary
        - Key stories
        - Themes & trends
        - Market signals
        - What to watch today

        ---

        **Available sources:**
        """
    )
    for cat, sources in NEWS_SOURCES.items():
        st.markdown(f"**{cat}:** " + " · ".join(s["name"] for s in sources))
