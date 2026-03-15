"""
Report Generator

Uses the Claude API (claude-opus-4-6) with adaptive thinking to synthesize
a polished morning research report from crawled news articles.
"""

from datetime import date
from typing import Generator

import anthropic

from news_crawler import Article

MODEL = "claude-opus-4-6"
MAX_TOKENS = 8192

_SYSTEM_PROMPT = """\
You are an elite research analyst producing a daily morning briefing.
Your reports are concise, insightful, and structured.
Write in a professional yet readable tone — no filler, no fluff.
Use Markdown for formatting."""

_REPORT_TEMPLATE = """\
Today is {date}. You have been given {n_items} items (news articles and/or social media posts) \
across {n_topics} topic areas.

Topics of interest: {topics}

---

CONTENT:
{articles_block}

---

Write a **Daily Morning Research Report** with the following structure:

# Morning Research Report — {date}

## Executive Summary
A 3-5 sentence overview of the most important developments today.

## Key Stories
For each major story (pick the 5-8 most significant), write:
- **Headline** (source, category)
- 2-4 sentence summary with key facts
- 1 sentence on why this matters

## Themes & Trends
Identify 2-4 cross-cutting themes connecting multiple stories and posts.
Bullet points with brief explanations.

## Market & Economic Signals
(Include only if finance/business articles are present)
Brief bullet list of relevant market-moving news.

## Social Media Pulse
(Include only if social media posts are present — X.com and/or Truth Social)
- 3-5 notable posts or emerging narratives from social media
- Flag any posts that contradict or amplify mainstream news coverage
- Note influential accounts or viral topics if visible

## What to Watch
2-3 forward-looking items: upcoming events, decisions, or developments to monitor.

---
*Report generated from {n_items} items. Sources: {sources_list}*
"""


def _build_articles_block(articles: list[Article], max_chars_per_article: int = 800) -> str:
    """Format articles and social posts into a compact block for the prompt."""
    lines = []
    for i, a in enumerate(articles, 1):
        pub = a.published.strftime("%Y-%m-%d %H:%M UTC") if a.published else "unknown date"

        if a.item_type == "post":
            # Social media post — summary already contains the full text + engagement
            text = a.summary
            author_line = f" | Author: {a.author}" if a.author else ""
            lines.append(
                f"[{i}] [SOCIAL POST] {a.source}{author_line}\n"
                f"    Category: {a.category} | Published: {pub}\n"
                f"    URL: {a.url}\n"
                f"    {text}\n"
            )
        else:
            # News article
            text = a.full_text or a.summary
            if len(text) > max_chars_per_article:
                text = text[:max_chars_per_article] + "…"
            lines.append(
                f"[{i}] **{a.title}**\n"
                f"    Source: {a.source} | Category: {a.category} | Published: {pub}\n"
                f"    URL: {a.url}\n"
                f"    {text}\n"
            )
    return "\n".join(lines)


def generate_report(
    articles: list[Article],
    topics: list[str],
    report_date: date | None = None,
    api_key: str | None = None,
) -> Generator[str, None, None]:
    """
    Stream a markdown morning research report using Claude.

    Args:
        articles: List of crawled articles.
        topics: User-specified topic filters.
        report_date: Date for the report header (defaults to today).
        api_key: Anthropic API key (falls back to ANTHROPIC_API_KEY env var).

    Yields:
        Text chunks from the streaming Claude response.
    """
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    if not articles:
        yield "# Morning Research Report\n\n*No articles found matching the selected criteria.*"
        return

    if report_date is None:
        report_date = date.today()

    date_str = report_date.strftime("%B %d, %Y")
    topics_str = ", ".join(topics) if topics else "General news"
    sources = sorted({a.source for a in articles})
    sources_list = ", ".join(sources)

    articles_block = _build_articles_block(articles)

    prompt = _REPORT_TEMPLATE.format(
        date=date_str,
        n_items=len(articles),
        n_topics=len(set(a.category for a in articles)),
        topics=topics_str,
        articles_block=articles_block,
        sources_list=sources_list,
    )

    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for event in stream:
            # Only yield text deltas (skip thinking blocks)
            if (
                event.type == "content_block_delta"
                and hasattr(event, "delta")
                and event.delta.type == "text_delta"
            ):
                yield event.delta.text


def generate_report_full(
    articles: list[Article],
    topics: list[str],
    report_date: date | None = None,
    api_key: str | None = None,
) -> str:
    """Non-streaming version — returns the complete report string."""
    return "".join(generate_report(articles, topics, report_date, api_key))
