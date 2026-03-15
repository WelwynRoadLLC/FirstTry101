"""
News Crawler

Fetches articles from RSS feeds across categories.
Uses feedparser for RSS parsing and trafilatura for full-text extraction.
"""

import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

import feedparser
import trafilatura

# ── News Sources ──────────────────────────────────────────────────────────────

NEWS_SOURCES = {
    "General": [
        {"name": "AP News", "url": "https://feeds.apnews.com/rss/topnews"},
        {"name": "Reuters World", "url": "https://feeds.reuters.com/reuters/worldNews"},
    ],
    "Business & Finance": [
        {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews"},
        {"name": "CNBC Top News", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"},
        {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex"},
        {"name": "WSJ Markets", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.aspx"},
    ],
    "Technology": [
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
        {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
        {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
        {"name": "Hacker News", "url": "https://hnrss.org/frontpage"},
    ],
    "Science": [
        {"name": "Scientific American", "url": "https://rss.sciam.com/ScientificAmerican-Global"},
        {"name": "Nature News", "url": "https://www.nature.com/nature.rss"},
    ],
    "Politics": [
        {"name": "Politico", "url": "https://www.politico.com/rss/politicopicks.xml"},
        {"name": "The Hill", "url": "https://thehill.com/rss/syndicator/19110"},
    ],
}

ALL_CATEGORIES = list(NEWS_SOURCES.keys())


@dataclass
class Article:
    title: str
    url: str
    source: str
    category: str
    published: Optional[datetime] = None
    summary: str = ""
    full_text: str = ""
    topics_matched: list = field(default_factory=list)


def _parse_published(entry) -> Optional[datetime]:
    """Parse publication date from feed entry."""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def fetch_articles(
    categories: list[str],
    max_per_feed: int = 10,
    timeout: int = 10,
) -> list[Article]:
    """
    Fetch articles from RSS feeds in the specified categories.

    Args:
        categories: List of category names to fetch from.
        max_per_feed: Maximum articles to take from each feed.
        timeout: HTTP timeout in seconds.

    Returns:
        List of Article objects, sorted newest-first.
    """
    articles: list[Article] = []

    for cat in categories:
        sources = NEWS_SOURCES.get(cat, [])
        for source in sources:
            try:
                feed = feedparser.parse(
                    source["url"],
                    request_headers={"User-Agent": "Mozilla/5.0 (compatible; NewsCrawler/1.0)"},
                )
                for entry in feed.entries[:max_per_feed]:
                    title = getattr(entry, "title", "").strip()
                    url = getattr(entry, "link", "").strip()
                    if not title or not url:
                        continue

                    summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                    # Strip any HTML from summary
                    if summary and "<" in summary:
                        try:
                            from html.parser import HTMLParser

                            class _Stripper(HTMLParser):
                                def __init__(self):
                                    super().__init__()
                                    self._parts = []

                                def handle_data(self, data):
                                    self._parts.append(data)

                                def get_text(self):
                                    return " ".join(self._parts)

                            s = _Stripper()
                            s.feed(summary)
                            summary = s.get_text().strip()
                        except Exception:
                            pass

                    articles.append(
                        Article(
                            title=title,
                            url=url,
                            source=source["name"],
                            category=cat,
                            published=_parse_published(entry),
                            summary=summary[:600],
                        )
                    )
            except Exception:
                # Silently skip feeds that fail (network, parse errors)
                pass

    # Sort newest-first; articles without dates go last
    articles.sort(
        key=lambda a: a.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return articles


def filter_by_topics(articles: list[Article], topics: list[str]) -> list[Article]:
    """
    Filter articles to those matching any of the given topics/keywords.
    If topics list is empty, returns all articles.
    """
    if not topics:
        return articles

    lower_topics = [t.lower().strip() for t in topics if t.strip()]
    if not lower_topics:
        return articles

    matched = []
    for article in articles:
        haystack = (article.title + " " + article.summary).lower()
        hits = [t for t in lower_topics if t in haystack]
        if hits:
            article.topics_matched = hits
            matched.append(article)
    return matched


def fetch_full_text(article: Article, timeout: int = 15) -> str:
    """
    Fetch and extract the full article text using trafilatura.
    Returns extracted text or empty string on failure.
    """
    try:
        downloaded = trafilatura.fetch_url(article.url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            return (text or "").strip()
    except Exception:
        pass
    return ""


def enrich_with_full_text(
    articles: list[Article],
    max_articles: int = 20,
    delay: float = 0.5,
) -> list[Article]:
    """
    Fetch full text for the top N articles to give Claude richer context.
    Adds a small delay between requests to be polite to servers.
    """
    for article in articles[:max_articles]:
        if not article.full_text:
            article.full_text = fetch_full_text(article)
            if delay > 0:
                time.sleep(delay)
    return articles
