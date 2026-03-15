"""
Morning Intelligence Brief

Hedge-fund-style daily briefing: pre-market data, news crawl, social signals,
key themes with tickers, catalyst calendar, and tactical watchlist.

Run with:
    streamlit run news_report.py
"""

import io
import os
import textwrap
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
from market_data import (
    DEFAULT_WATCHLIST,
    ALL_DEFAULT_TICKERS,
    fetch_premarket_data,
    quotes_to_markdown_table,
    extract_tickers_from_text,
)
from report_generator import generate_report

load_dotenv()

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Morning Intelligence Brief",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styles ────────────────────────────────────────────────────────────────────
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
        padding: 24px 32px;
        font-family: "Georgia", serif;
        font-size: 15px;
        line-height: 1.75;
        color: #dddddd;
    }
    .report-box h1 { font-size: 1.6em; border-bottom: 1px solid #333; padding-bottom: 8px; }
    .report-box h2 { font-size: 1.2em; color: #aaaaff; margin-top: 1.4em; }
    .report-box h3 { font-size: 1.05em; color: #88ccff; }
    .report-box table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
    .report-box th { background: #111; color: #aaa; padding: 6px 10px; text-align: left; }
    .report-box td { padding: 5px 10px; border-bottom: 1px solid #1a1a1a; }
    .report-box code { background: #1a1a1a; padding: 1px 5px; border-radius: 3px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 Brief Settings")
    st.markdown("---")

    # Anthropic key
    st.markdown("**Anthropic API Key**")
    api_key_input = st.text_input(
        "Anthropic", value=os.getenv("ANTHROPIC_API_KEY", ""),
        type="password", placeholder="sk-ant-...", label_visibility="collapsed",
    )
    if not api_key_input:
        st.warning("Anthropic API key required.")

    st.markdown("---")

    # ── Market Watchlist ──────────────────────────────────────────────────────
    st.markdown("**Market Watchlist**")
    st.caption("Tickers for the pre-market snapshot. Edit to add your positions.")
    default_ticker_str = ", ".join(ALL_DEFAULT_TICKERS)
    watchlist_input = st.text_area(
        "Watchlist", value=default_ticker_str, height=100, label_visibility="collapsed",
        help="Comma-separated tickers. Futures: ES=F, NQ=F. Index: ^VIX, ^TNX.",
    )
    custom_tickers = [t.strip().upper() for t in watchlist_input.split(",") if t.strip()]

    st.markdown("---")

    # ── News Categories ───────────────────────────────────────────────────────
    st.markdown("**News Categories** *(RSS)*")
    selected_categories: list[str] = []
    default_cats = {"Business & Finance", "Technology"}
    for cat in ALL_CATEGORIES:
        if st.checkbox(cat, value=(cat in default_cats), key=f"cat_{cat}"):
            selected_categories.append(cat)

    st.markdown("---")

    # ── X.com ─────────────────────────────────────────────────────────────────
    st.markdown("**X.com**")
    use_x = st.checkbox("Include X.com posts", value=False)
    if use_x:
        x_bearer = st.text_input(
            "Bearer Token", value=os.getenv("X_BEARER_TOKEN", ""),
            type="password", placeholder="AAAA...", label_visibility="collapsed",
        )
        x_queries_raw = st.text_area(
            "Queries", label_visibility="collapsed", height=90,
            value="AI financial services\nLLM banking fintech\nFed interest rates\nAI earnings Wall Street",
            help="One query per line.",
        )
        x_queries = [q.strip() for q in x_queries_raw.splitlines() if q.strip()]
        x_max = st.slider("Posts per query", 5, 10, 10)
    else:
        x_bearer, x_queries, x_max = "", [], 10

    st.markdown("---")

    # ── Truth Social ──────────────────────────────────────────────────────────
    st.markdown("**Truth Social**")
    use_truth = st.checkbox("Include Truth Social posts", value=False)
    if use_truth:
        truth_queries_raw = st.text_area(
            "Search terms", label_visibility="collapsed", height=70,
            value="economy\nAI\nbanks\nfintech\nFed",
            help="One term per line. No API key needed.",
        )
        truth_queries = [q.strip() for q in truth_queries_raw.splitlines() if q.strip()]
        truth_timeline = st.checkbox("Include public timeline", value=False)
        truth_max = st.slider("Posts per term", 5, 20, 10)
    else:
        truth_queries, truth_timeline, truth_max = [], False, 10

    st.markdown("---")

    # ── Topic Filter ──────────────────────────────────────────────────────────
    st.markdown("**Topic Filters**")
    topics_input = st.text_area(
        "Topics", label_visibility="collapsed", height=70,
        value="AI, artificial intelligence, financial services, fintech, banking, Fed, interest rates, earnings, markets, LLM, machine learning",
        help="Comma-separated. Applied across all sources.",
    )
    topics = [t.strip() for t in topics_input.split(",") if t.strip()] if topics_input else []

    st.markdown("---")

    # ── Crawl Options ─────────────────────────────────────────────────────────
    st.markdown("**Crawl Options**")
    max_per_feed = st.slider("Articles per RSS feed", 5, 25, 10)
    fetch_full = st.checkbox("Fetch full article text", value=False,
                             help="Slower but richer. Up to 15 articles.")

    st.markdown("---")

    has_source = bool(selected_categories or (use_x and x_bearer) or use_truth)
    generate_btn = st.button(
        "Generate Brief",
        use_container_width=True,
        type="primary",
        disabled=not api_key_input or not has_source,
    )

# ── Main ──────────────────────────────────────────────────────────────────────
today = date.today()

st.markdown("# Morning Intelligence Brief")
st.markdown(f"*{today.strftime('%A, %B %d, %Y')}  ·  Financial Services & AI Focus*")
st.markdown("---")

if generate_btn:
    all_items: list = []
    market_table = ""

    with st.status("Gathering intelligence…", expanded=True) as status:

        # Pre-market data
        if custom_tickers:
            st.write(f"Fetching pre-market data for **{len(custom_tickers)}** tickers…")
            quotes = fetch_premarket_data(custom_tickers)
            market_table = quotes_to_markdown_table(quotes)
            valid = sum(1 for q in quotes if q.last_price)
            st.write(f"Market data: **{valid}** quotes retrieved.")

        # RSS
        if selected_categories:
            n_feeds = sum(len(NEWS_SOURCES[c]) for c in selected_categories)
            st.write(f"Fetching from **{n_feeds}** RSS feeds…")
            rss = fetch_articles(selected_categories, max_per_feed=max_per_feed)
            st.write(f"RSS: **{len(rss)}** articles.")
            all_items.extend(rss)

        # X.com
        if use_x and x_bearer and x_queries:
            st.write(f"Searching X.com ({len(x_queries)} queries)…")
            try:
                x_posts = fetch_x_posts(x_bearer, x_queries, max_per_query=x_max)
                st.write(f"X.com: **{len(x_posts)}** posts.")
                all_items.extend(x_posts)
            except ValueError as e:
                st.warning(f"X.com: {e}")
        elif use_x and not x_bearer:
            st.warning("X.com skipped — no Bearer Token.")

        # Truth Social
        if use_truth:
            st.write("Fetching Truth Social posts…")
            try:
                ts = fetch_truth_social_posts(truth_queries, truth_max, truth_timeline)
                st.write(f"Truth Social: **{len(ts)}** posts.")
                all_items.extend(ts)
            except Exception as e:
                st.warning(f"Truth Social: {e}")

        # Add any tickers mentioned in articles to the market data pull
        if all_items and custom_tickers:
            combined_text = " ".join(a.title + " " + a.summary for a in all_items)
            mentioned = extract_tickers_from_text(combined_text)
            new_tickers = [t for t in mentioned if t not in custom_tickers][:10]
            if new_tickers:
                st.write(f"Auto-detected tickers in news: {', '.join('$'+t for t in new_tickers)}")
                extra_quotes = fetch_premarket_data(new_tickers)
                # Append extra quotes to market table
                from market_data import quotes_to_markdown_table as _qtm
                extra_table = _qtm([q for q in extra_quotes if q.last_price])
                if extra_table and extra_table != "*No market data available.*":
                    market_table = market_table.rstrip() + "\n" + "\n".join(
                        extra_table.splitlines()[2:]  # skip duplicate header
                    )

        # Topic filter
        if topics and all_items:
            before = len(all_items)
            all_items = filter_by_topics(all_items, topics)
            st.write(f"Topic filter: {len(all_items)} of {before} items kept.")

        if not all_items:
            status.update(label="No content found.", state="error")
            st.error("No items matched. Try broader topics or more sources.")
            st.stop()

        if fetch_full:
            st.write("Fetching full article text (up to 15)…")
            all_items = enrich_with_full_text(all_items, max_articles=15)

        status.update(label=f"Ready — {len(all_items)} items + market data.", state="complete")

    # Stats
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Items", len(all_items))
    col2.metric("Articles", sum(1 for a in all_items if a.item_type == "article"))
    col3.metric("Social Posts", sum(1 for a in all_items if a.item_type == "post"))
    col4.metric("Tickers Tracked", len(custom_tickers))
    st.markdown("---")

    # Pre-market table preview
    if market_table and market_table != "*No market data available.*":
        with st.expander("Pre-Market Snapshot (raw data)", expanded=False):
            st.markdown(market_table)

    # Stream the brief
    st.markdown("### Generating brief with Claude…")
    report_placeholder = st.empty()
    report_text = ""

    try:
        for chunk in generate_report(
            articles=all_items,
            topics=topics,
            market_table=market_table,
            report_date=today,
            api_key=api_key_input,
        ):
            report_text += chunk
            report_placeholder.markdown(
                f'<div class="report-box">{report_text}</div>',
                unsafe_allow_html=True,
            )
    except Exception as e:
        st.error(f"Generation failed: {e}")
        st.stop()

    st.session_state["report"] = report_text
    st.session_state["report_date"] = today.isoformat()
    st.session_state["item_count"] = len(all_items)

    st.markdown("---")

    # ── Download buttons ──────────────────────────────────────────────────────
    col_md, col_pdf = st.columns(2)

    with col_md:
        st.download_button(
            "⬇ Download Markdown",
            data=report_text,
            file_name=f"brief_{today.isoformat()}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with col_pdf:
        try:
            pdf_bytes = _render_pdf(report_text, today)
            st.download_button(
                "⬇ Download PDF (Newsletter)",
                data=pdf_bytes,
                file_name=f"brief_{today.isoformat()}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.info(f"PDF export unavailable: {e}", icon="ℹ️")

    with st.expander(f"All {len(all_items)} crawled items"):
        for a in sorted(all_items, key=lambda x: x.category):
            icon = "💬" if a.item_type == "post" else "📄"
            pub = a.published.strftime("%H:%M UTC") if a.published else "—"
            author = f" · {a.author}" if a.author else ""
            st.markdown(f"{icon} **[{a.title}]({a.url})** — {a.source}{author} · {pub}")

elif "report" in st.session_state:
    st.info(
        f"Last brief: {st.session_state['report_date']} "
        f"({st.session_state['item_count']} items). Click **Generate Brief** to refresh.",
        icon="ℹ️",
    )
    report_text = st.session_state["report"]
    report_date_str = st.session_state["report_date"]
    st.markdown(f'<div class="report-box">{report_text}</div>', unsafe_allow_html=True)
    st.markdown("---")

    col_md, col_pdf = st.columns(2)
    with col_md:
        st.download_button(
            "⬇ Download Markdown",
            data=report_text,
            file_name=f"brief_{report_date_str}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with col_pdf:
        try:
            pdf_bytes = _render_pdf(report_text, date.fromisoformat(report_date_str))
            st.download_button(
                "⬇ Download PDF (Newsletter)",
                data=pdf_bytes,
                file_name=f"brief_{report_date_str}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.info(f"PDF export unavailable: {e}", icon="ℹ️")

else:
    st.markdown(
        """
        ### What this generates

        A hedge-fund-style morning intelligence brief with:

        | Section | Content |
        |---------|---------|
        | **Market Snapshot** | Pre-market prices, futures, VIX, yields, FX |
        | **Key Themes** | 3-5 macro/sector themes with tickers and positioning bias |
        | **Catalyst Calendar** | Today's earnings, FOMC, data releases |
        | **Sector Intelligence** | What's moving in Financials, Tech, AI, etc. |
        | **Social Signals** | X.com / Truth Social narrative analysis |
        | **Risk Flags** | Tail risks with trigger conditions |
        | **Tactical Watchlist** | 5-8 names with thesis, catalyst, and long/short bias |

        **To get started:** configure sources in the sidebar, then click **Generate Brief**.

        ---

        **RSS sources available:**
        """
    )
    for cat, srcs in NEWS_SOURCES.items():
        st.markdown(f"**{cat}:** " + " · ".join(s["name"] for s in srcs))
    st.markdown(
        "**Social:** X.com (Bearer Token required) · Truth Social (no key needed)"
    )


# ── PDF Renderer ──────────────────────────────────────────────────────────────

def _render_pdf(markdown_text: str, report_date: date) -> bytes:
    """
    Convert the markdown report to a styled PDF newsletter using weasyprint.
    Falls back gracefully if weasyprint is not installed.
    """
    try:
        import markdown as md_lib
        from weasyprint import HTML, CSS
    except ImportError:
        raise ImportError(
            "Install weasyprint and markdown to enable PDF export: "
            "pip install weasyprint markdown"
        )

    html_body = md_lib.markdown(
        markdown_text,
        extensions=["tables", "fenced_code"],
    )

    css = CSS(string="""
        @page {
            size: A4;
            margin: 18mm 20mm 18mm 20mm;
            @top-center {
                content: "MORNING INTELLIGENCE BRIEF — CONFIDENTIAL";
                font-family: 'Helvetica Neue', Arial, sans-serif;
                font-size: 7pt;
                color: #999;
                letter-spacing: 0.08em;
            }
            @bottom-right {
                content: counter(page) " / " counter(pages);
                font-family: 'Helvetica Neue', Arial, sans-serif;
                font-size: 7pt;
                color: #999;
            }
            @bottom-left {
                content: "Generated """ + report_date.strftime("%B %d, %Y") + """";
                font-family: 'Helvetica Neue', Arial, sans-serif;
                font-size: 7pt;
                color: #999;
            }
        }

        body {
            font-family: 'Georgia', 'Times New Roman', serif;
            font-size: 10pt;
            line-height: 1.65;
            color: #1a1a1a;
            background: #ffffff;
        }

        h1 {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            font-size: 20pt;
            font-weight: 700;
            color: #0a1628;
            border-bottom: 2px solid #0a1628;
            padding-bottom: 6pt;
            margin-bottom: 14pt;
            letter-spacing: -0.02em;
        }

        h2 {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            font-size: 12pt;
            font-weight: 700;
            color: #0a1628;
            background: #f0f4fa;
            padding: 4pt 8pt;
            border-left: 3pt solid #1a4080;
            margin-top: 18pt;
            margin-bottom: 8pt;
            page-break-after: avoid;
        }

        h3 {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            font-size: 10.5pt;
            font-weight: 600;
            color: #1a4080;
            margin-top: 12pt;
            margin-bottom: 4pt;
            page-break-after: avoid;
        }

        p { margin: 0 0 7pt 0; }

        ul, ol { margin: 4pt 0 8pt 0; padding-left: 16pt; }
        li { margin-bottom: 3pt; }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 9pt;
            margin: 8pt 0 12pt 0;
            font-family: 'Helvetica Neue', Arial, sans-serif;
        }
        th {
            background: #0a1628;
            color: #ffffff;
            padding: 5pt 8pt;
            text-align: left;
            font-weight: 600;
        }
        td {
            padding: 4pt 8pt;
            border-bottom: 0.5pt solid #dde3ed;
        }
        tr:nth-child(even) td { background: #f7f9fc; }

        code {
            font-family: 'Courier New', monospace;
            font-size: 8.5pt;
            background: #f0f4fa;
            padding: 1pt 4pt;
            border-radius: 2pt;
        }

        strong { color: #0a1628; }

        em {
            font-size: 8pt;
            color: #666;
        }

        hr {
            border: none;
            border-top: 0.5pt solid #c0c8d8;
            margin: 14pt 0;
        }

        blockquote {
            border-left: 3pt solid #c0c8d8;
            margin: 8pt 0;
            padding: 2pt 10pt;
            color: #555;
            font-style: italic;
        }
    """)

    full_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body>{html_body}</body>
</html>"""

    buf = io.BytesIO()
    HTML(string=full_html).write_pdf(buf, stylesheets=[css])
    return buf.getvalue()
