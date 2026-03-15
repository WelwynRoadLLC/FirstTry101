"""
Report Generator

Uses the Claude API (claude-opus-4-6) with adaptive thinking to synthesize
a hedge-fund-style morning intelligence brief from crawled news and market data.
"""

from datetime import date
from typing import Generator, Optional

import anthropic

from news_crawler import Article

MODEL = "claude-opus-4-6"
MAX_TOKENS = 8192

_SYSTEM_PROMPT = """\
You are a senior research analyst at a multi-strategy hedge fund.
You write the firm's daily morning intelligence brief — the document the PMs
read before markets open. It must be:
- Actionable: every section ties back to positioning or risk
- Specific: name tickers, sectors, spreads, and catalysts explicitly
- Concise: no filler, no passive voice, no restating the obvious
- Opinionated: surface the 2-3 ideas that genuinely matter today

Use Markdown for formatting. Use $TICKER notation for all equity references."""

_REPORT_TEMPLATE = """\
Today is {date}. Markets {market_status}.

TOPICS OF FOCUS: {topics}

──────────────────────────────────────────────────────────────
PRE-MARKET DATA (fetched live)
──────────────────────────────────────────────────────────────
{market_table}

──────────────────────────────────────────────────────────────
NEWS & SOCIAL CONTENT ({n_items} items from {n_sources} sources)
──────────────────────────────────────────────────────────────
{articles_block}

──────────────────────────────────────────────────────────────

Write the morning brief using EXACTLY this structure. Do not add or remove sections.

---

# Morning Intelligence Brief — {date}

## Market Snapshot
Interpret the pre-market data above. Summarize the overall tone (risk-on/off,
direction of futures, yield moves, VIX). 2-4 sentences max.

## Key Themes
### 1. [Theme Title]
- **What's happening:** 2-3 sentences
- **Tickers in play:** $XXX, $YYY
- **Implication:** One clear sentence on long/short/avoid/watch positioning

### 2. [Theme Title]
*(repeat structure — include 3-5 themes total)*

## Catalyst Calendar
Bullet list of known events **today** and **this week** visible in the news
(earnings, FOMC, macro data releases, regulatory decisions). Include estimated
times where mentioned. Flag surprises vs. consensus.

## Sector Intelligence
One crisp bullet per relevant sector (only sectors with actual news):
- **Financials:** …
- **Technology / AI:** …
- *(add others as needed)*

## Social Signals
*(Include only if social media posts are present — skip section entirely if not)*
- 3-5 notable narratives circulating on X.com or Truth Social
- Flag any posts amplifying or contradicting mainstream coverage
- Note if any high-profile accounts are driving a specific narrative

## Risk Flags
2-4 tail risks or uncertainty items worth monitoring. Format:
- ⚠️ **[Risk label]:** Brief explanation of the risk and trigger conditions

## Tactical Watchlist
Table of specific names the PM should have on their screen today:

| Ticker | Thesis | Catalyst | Bias |
|--------|--------|----------|------|
| $XXX | … | … | Long/Short/Neutral |

*(Include 5-8 names drawn from the news and market data above)*

---
*Brief compiled from {n_items} sources including {sources_list}.*
*Pre-market data as of report generation time.*
"""


def _build_articles_block(articles: list[Article], max_chars: int = 700) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        pub = a.published.strftime("%Y-%m-%d %H:%M UTC") if a.published else "unknown"

        if a.item_type == "post":
            author_str = f" | {a.author}" if a.author else ""
            lines.append(
                f"[{i}] [SOCIAL — {a.source}]{author_str} | {pub}\n"
                f"    {a.summary}\n"
            )
        else:
            text = a.full_text or a.summary
            if len(text) > max_chars:
                text = text[:max_chars] + "…"
            lines.append(
                f"[{i}] {a.title}\n"
                f"    Source: {a.source} | {a.category} | {pub}\n"
                f"    URL: {a.url}\n"
                f"    {text}\n"
            )
    return "\n".join(lines)


def generate_report(
    articles: list[Article],
    topics: list[str],
    market_table: str = "",
    report_date: Optional[date] = None,
    api_key: Optional[str] = None,
) -> Generator[str, None, None]:
    """
    Stream a hedge-fund morning brief using Claude.

    Args:
        articles: Crawled articles and social posts.
        topics: Topic filters in use.
        market_table: Pre-formatted markdown table of market data.
        report_date: Report date (defaults to today).
        api_key: Anthropic API key (falls back to env var).

    Yields:
        Text chunks from the streaming Claude response.
    """
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    if not articles:
        yield "# Morning Intelligence Brief\n\n*No content found matching the selected criteria.*"
        return

    if report_date is None:
        report_date = date.today()

    date_str = report_date.strftime("%B %d, %Y")
    topics_str = ", ".join(topics) if topics else "Financial services, AI, macro"
    sources = sorted({a.source for a in articles})

    # Determine market status string
    from datetime import datetime, timezone
    now_hour = datetime.now(timezone.utc).hour
    if 9 <= now_hour < 14:   # 9-14 UTC = pre-market / early US
        market_status = "open in pre-market / early session"
    elif 14 <= now_hour < 21:
        market_status = "are in regular session"
    else:
        market_status = "are closed (after-hours)"

    prompt = _REPORT_TEMPLATE.format(
        date=date_str,
        market_status=market_status,
        topics=topics_str,
        market_table=market_table or "*Market data not available.*",
        n_items=len(articles),
        n_sources=len(sources),
        articles_block=_build_articles_block(articles),
        sources_list=", ".join(sources[:8]) + ("…" if len(sources) > 8 else ""),
    )

    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for event in stream:
            if (
                event.type == "content_block_delta"
                and hasattr(event, "delta")
                and event.delta.type == "text_delta"
            ):
                yield event.delta.text


def generate_report_full(
    articles: list[Article],
    topics: list[str],
    market_table: str = "",
    report_date: Optional[date] = None,
    api_key: Optional[str] = None,
) -> str:
    """Non-streaming version — returns the complete report string."""
    return "".join(generate_report(articles, topics, market_table, report_date, api_key))
