"""
Daily Morning Research Report

AI-powered news crawler and report generator.
Sources: RSS feeds (Bloomberg, FT, Reuters, CNBC, etc.),
         X.com (Twitter API v2), and Truth Social.

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
    fetch_x_posts,
    fetch_truth_social_posts,
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
    .source-tag {
        display: inline-block;
        background: #1a1a1a;
        border: 1px solid #333;
        border-radius: 3px;
        padding: 1px 6px;
        font-size: 0.8em;
        margin: 1px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📰 Report Settings")
    st.markdown("---")

    # Anthropic API key
    st.markdown("**Anthropic API Key**")
    env_anthropic = os.getenv("ANTHROPIC_API_KEY", "")
    api_key_input = st.text_input(
        "Anthropic API Key",
        value=env_anthropic,
        type="password",
        placeholder="sk-ant-...",
        label_visibility="collapsed",
    )
    if not api_key_input:
        st.warning("Add your Anthropic API key to generate reports.")

    st.markdown("---")

    # ── RSS News Categories ───────────────────────────────────────────────────
    st.markdown("**News Categories** *(RSS)*")
    selected_categories: list[str] = []
    default_cats = {"Business & Finance", "Technology"}
    for cat in ALL_CATEGORIES:
        if st.checkbox(cat, value=(cat in default_cats), key=f"cat_{cat}"):
            selected_categories.append(cat)

    st.markdown("---")

    # ── X.com ─────────────────────────────────────────────────────────────────
    st.markdown("**X.com (Twitter)**")
    use_x = st.checkbox("Include X.com posts", value=False, key="use_x")
    if use_x:
        env_x = os.getenv("X_BEARER_TOKEN", "")
        x_bearer = st.text_input(
            "X Bearer Token",
            value=env_x,
            type="password",
            placeholder="AAAA...",
            label_visibility="collapsed",
        )
        st.caption("Twitter API v2 Bearer Token from developer.twitter.com")
        x_queries_raw = st.text_area(
            "X search queries",
            value="AI financial services\nLLM banking fintech\nFed interest rates\nAI earnings Wall Street",
            height=90,
            help="One search query per line. Each is fetched separately.",
            label_visibility="collapsed",
        )
        x_queries = [q.strip() for q in x_queries_raw.splitlines() if q.strip()]
        x_max = st.slider("Posts per query (X)", min_value=5, max_value=10, value=10)
    else:
        x_bearer = ""
        x_queries = []
        x_max = 10

    st.markdown("---")

    # ── Truth Social ──────────────────────────────────────────────────────────
    st.markdown("**Truth Social**")
    use_truth = st.checkbox("Include Truth Social posts", value=False, key="use_truth")
    if use_truth:
        truth_queries_raw = st.text_area(
            "Truth Social search terms",
            value="economy\nAI\nbanks\nfintech\nFed",
            height=90,
            help="One search term per line. No API key required.",
            label_visibility="collapsed",
        )
        truth_queries = [q.strip() for q in truth_queries_raw.splitlines() if q.strip()]
        truth_timeline = st.checkbox(
            "Also include public timeline",
            value=False,
            help="Pulls latest posts from the Truth Social public feed (no search filter).",
        )
        truth_max = st.slider("Posts per query (Truth Social)", min_value=5, max_value=20, value=10)
    else:
        truth_queries = []
        truth_timeline = False
        truth_max = 10

    st.markdown("---")

    # ── Topic Filter ──────────────────────────────────────────────────────────
    st.markdown("**Topic Filters** *(optional)*")
    st.caption("Comma-separated keywords applied across ALL sources. Leave blank for all content.")
    topics_input = st.text_area(
        "Topics",
        value="AI, artificial intelligence, financial services, fintech, banking, Fed, interest rates, earnings, markets, LLM, machine learning",
        height=80,
        label_visibility="collapsed",
    )
    topics = [t.strip() for t in topics_input.split(",") if t.strip()] if topics_input else []

    st.markdown("---")

    # ── Crawl Options ─────────────────────────────────────────────────────────
    st.markdown("**Crawl Options**")
    max_per_feed = st.slider("Articles per RSS feed", min_value=5, max_value=25, value=10)
    fetch_full = st.checkbox(
        "Fetch full article text",
        value=False,
        help="Slower but gives Claude richer context. Fetches up to 15 articles.",
    )

    st.markdown("---")

    has_any_source = bool(selected_categories or (use_x and x_bearer and x_queries) or use_truth)
    generate_btn = st.button(
        "Generate Morning Report",
        use_container_width=True,
        type="primary",
        disabled=not api_key_input or not has_any_source,
    )

# ── Main Area ─────────────────────────────────────────────────────────────────
today = date.today()

st.markdown("# Daily Morning Research Report")
st.markdown(f"*{today.strftime('%A, %B %d, %Y')}*")
st.markdown("---")

if generate_btn:
    all_items: list = []

    with st.status("Gathering content…", expanded=True) as status:

        # RSS
        if selected_categories:
            n_feeds = sum(len(NEWS_SOURCES[c]) for c in selected_categories)
            st.write(f"Fetching from **{n_feeds}** RSS feeds…")
            rss_articles = fetch_articles(selected_categories, max_per_feed=max_per_feed)
            st.write(f"RSS: **{len(rss_articles)}** articles found.")
            all_items.extend(rss_articles)

        # X.com
        if use_x and x_bearer and x_queries:
            st.write(f"Searching X.com for **{len(x_queries)}** queries…")
            try:
                x_posts = fetch_x_posts(x_bearer, x_queries, max_per_query=x_max)
                st.write(f"X.com: **{len(x_posts)}** posts found.")
                all_items.extend(x_posts)
            except ValueError as e:
                st.warning(f"X.com skipped: {e}")
        elif use_x and not x_bearer:
            st.warning("X.com skipped — no Bearer Token provided.")
        elif use_x and not x_queries:
            st.warning("X.com skipped — no search queries entered.")

        # Truth Social
        if use_truth:
            q_label = f"**{len(truth_queries)}** queries" if truth_queries else "public timeline only"
            st.write(f"Fetching Truth Social posts ({q_label})…")
            try:
                ts_posts = fetch_truth_social_posts(
                    queries=truth_queries,
                    max_per_query=truth_max,
                    include_public_timeline=truth_timeline,
                )
                st.write(f"Truth Social: **{len(ts_posts)}** posts found.")
                all_items.extend(ts_posts)
            except Exception as e:
                st.warning(f"Truth Social skipped: {e}")

        # Topic filtering
        if topics and all_items:
            before = len(all_items)
            all_items = filter_by_topics(all_items, topics)
            st.write(
                f"Topic filter applied — **{len(all_items)}** of {before} items match: "
                + ", ".join(f"`{t}`" for t in topics)
            )

        if not all_items:
            status.update(label="No content found.", state="error")
            st.error("No items matched your filters. Try broader topics or add more sources.")
            st.stop()

        # Full text enrichment (articles only)
        if fetch_full:
            n_articles = sum(1 for a in all_items if a.item_type == "article")
            st.write(f"Fetching full text for up to 15 of {n_articles} articles…")
            all_items = enrich_with_full_text(all_items, max_articles=15)

        status.update(
            label=f"Done — {len(all_items)} items ready for Claude.",
            state="complete",
        )

    # Stats row
    n_articles = sum(1 for a in all_items if a.item_type == "article")
    n_posts = sum(1 for a in all_items if a.item_type == "post")
    sources = {a.source for a in all_items}

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Items", len(all_items))
    col2.metric("Articles", n_articles)
    col3.metric("Social Posts", n_posts)
    col4.metric("Sources", len(sources))

    st.markdown("---")

    # Stream the report
    st.markdown("### Generating report with Claude…")
    report_placeholder = st.empty()

    report_text = ""
    try:
        for chunk in generate_report(
            articles=all_items,
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

    st.session_state["report"] = report_text
    st.session_state["report_date"] = today.isoformat()
    st.session_state["item_count"] = len(all_items)

    st.markdown("---")
    st.download_button(
        label="Download Report (.md)",
        data=report_text,
        file_name=f"morning_report_{today.isoformat()}.md",
        mime="text/markdown",
    )

    with st.expander(f"View all {len(all_items)} crawled items"):
        for a in sorted(all_items, key=lambda x: x.category):
            pub = a.published.strftime("%Y-%m-%d %H:%M") if a.published else "—"
            icon = "💬" if a.item_type == "post" else "📄"
            author = f" · {a.author}" if a.author else ""
            st.markdown(
                f"{icon} **[{a.title}]({a.url})** — "
                f"{a.source}{author} · {a.category} · {pub}"
            )

elif "report" in st.session_state:
    st.info(
        f"Showing report from {st.session_state['report_date']} "
        f"({st.session_state['item_count']} items). "
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
    st.markdown(
        """
        ### How it works

        1. **Select news categories** (General, Finance, Tech, Politics…)
        2. Optionally enable **X.com** (requires Twitter API v2 Bearer Token)
        3. Optionally enable **Truth Social** (no API key needed)
        4. Enter **topic keywords** to focus the report *(optional)*
        5. Click **Generate Morning Report**

        Claude reads all the content and writes a structured briefing covering:
        - Executive summary
        - Key stories
        - Themes & trends
        - Market & economic signals
        - Social media pulse *(if social sources are enabled)*
        - What to watch today

        ---

        **RSS Sources available:**
        """
    )
    for cat, srcs in NEWS_SOURCES.items():
        names = " · ".join(s["name"] for s in srcs)
        st.markdown(f"**{cat}:** {names}")

    st.markdown(
        """
        ---
        **Social Media Sources:**
        - **X.com** — Real-time posts via Twitter API v2 search (Bearer Token required)
        - **Truth Social** — Public posts via open Mastodon-compatible API (no key needed)
        """
    )
