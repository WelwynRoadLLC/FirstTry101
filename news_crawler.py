"""
News Crawler

Fetches articles from RSS feeds and social media posts.
Sources: RSS feeds (including Bloomberg, FT), X.com (Twitter API v2),
         and Truth Social public API.
"""

import time
import requests
from datetime import datetime, timezone
from dataclasses import dataclass, field
from html.parser import HTMLParser
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
        {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss"},
        {"name": "Bloomberg Technology", "url": "https://feeds.bloomberg.com/technology/news.rss"},
        {"name": "Financial Times", "url": "https://www.ft.com/rss/home"},
        {"name": "FT Markets", "url": "https://www.ft.com/myft/following/topics/topic/MTA0-U2VjdGlvbnM=.rss"},
    ],
    "Technology": [
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
        {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
        {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
        {"name": "Hacker News", "url": "https://hnrss.org/frontpage"},
        {"name": "Bloomberg Technology", "url": "https://feeds.bloomberg.com/technology/news.rss"},
    ],
    "Science": [
        {"name": "Scientific American", "url": "https://rss.sciam.com/ScientificAmerican-Global"},
        {"name": "Nature News", "url": "https://www.nature.com/nature.rss"},
    ],
    "Politics": [
        {"name": "Politico", "url": "https://www.politico.com/rss/politicopicks.xml"},
        {"name": "The Hill", "url": "https://thehill.com/rss/syndicator/19110"},
        {"name": "Bloomberg Politics", "url": "https://feeds.bloomberg.com/politics/news.rss"},
    ],
}

ALL_CATEGORIES = list(NEWS_SOURCES.keys())

# X.com API v2
_X_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"
_X_TWEET_FIELDS = "created_at,text,public_metrics,author_id"
_X_EXPANSIONS = "author_id"
_X_USER_FIELDS = "name,username"

# Truth Social API (Mastodon-compatible, public)
_TRUTH_SEARCH_URL = "https://truthsocial.com/api/v2/search"
_TRUTH_TIMELINE_URL = "https://truthsocial.com/api/v1/timelines/public"

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsCrawler/1.0)"}


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class Article:
    title: str
    url: str
    source: str
    category: str
    published: Optional[datetime] = None
    summary: str = ""
    full_text: str = ""
    item_type: str = "article"        # "article" | "post"
    author: str = ""                  # for social posts
    topics_matched: list = field(default_factory=list)


# ── HTML Stripper ─────────────────────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str):
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts).strip()


def _strip_html(html: str) -> str:
    if not html or "<" not in html:
        return html
    try:
        s = _HTMLStripper()
        s.feed(html)
        return s.get_text()
    except Exception:
        return html


# ── RSS Fetching ──────────────────────────────────────────────────────────────

def _parse_published(entry) -> Optional[datetime]:
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
) -> list[Article]:
    """Fetch articles from RSS feeds in the specified categories."""
    articles: list[Article] = []
    seen_urls: set[str] = set()

    for cat in categories:
        sources = NEWS_SOURCES.get(cat, [])
        for source in sources:
            try:
                feed = feedparser.parse(
                    source["url"],
                    request_headers=_HEADERS,
                )
                for entry in feed.entries[:max_per_feed]:
                    title = getattr(entry, "title", "").strip()
                    url = getattr(entry, "link", "").strip()
                    if not title or not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    raw_summary = (
                        getattr(entry, "summary", "")
                        or getattr(entry, "description", "")
                    )
                    summary = _strip_html(raw_summary)[:600]

                    articles.append(
                        Article(
                            title=title,
                            url=url,
                            source=source["name"],
                            category=cat,
                            published=_parse_published(entry),
                            summary=summary,
                        )
                    )
            except Exception:
                pass

    articles.sort(
        key=lambda a: a.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return articles


# ── X.com (Twitter API v2) ────────────────────────────────────────────────────

def fetch_x_posts(
    bearer_token: str,
    queries: list[str],
    max_per_query: int = 10,
) -> list[Article]:
    """
    Fetch recent posts from X.com matching the given search queries.

    Requires a Twitter API v2 Bearer Token.
    Free tier supports up to 10 results per query.

    Args:
        bearer_token: Twitter API v2 Bearer Token.
        queries: List of search query strings (e.g. ["Fed interest rates", "AI earnings"]).
        max_per_query: Max tweets per query (1–100; free tier capped at 10).

    Returns:
        List of Article objects with item_type="post".
    """
    if not bearer_token or not queries:
        return []

    headers = {"Authorization": f"Bearer {bearer_token}"}
    posts: list[Article] = []
    seen_ids: set[str] = set()

    for raw_query in queries:
        query = raw_query.strip()
        if not query:
            continue
        # Append filters: English language, no retweets
        full_query = f"({query}) lang:en -is:retweet"

        try:
            resp = requests.get(
                _X_SEARCH_URL,
                headers=headers,
                params={
                    "query": full_query,
                    "max_results": min(max_per_query, 10),
                    "tweet.fields": _X_TWEET_FIELDS,
                    "expansions": _X_EXPANSIONS,
                    "user.fields": _X_USER_FIELDS,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                raise ValueError("X.com: Invalid Bearer Token (401 Unauthorized).") from e
            if e.response is not None and e.response.status_code == 403:
                raise ValueError(
                    "X.com: Access forbidden (403). Your API plan may not support search."
                ) from e
            continue
        except Exception:
            continue

        # Build author lookup from includes
        users = {
            u["id"]: u
            for u in data.get("includes", {}).get("users", [])
        }

        for tweet in data.get("data", []):
            tid = tweet.get("id", "")
            if tid in seen_ids:
                continue
            seen_ids.add(tid)

            author_id = tweet.get("author_id", "")
            user = users.get(author_id, {})
            username = user.get("username", "unknown")
            display_name = user.get("name", username)

            text = tweet.get("text", "").strip()
            created_at = tweet.get("created_at")
            published = None
            if created_at:
                try:
                    published = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except Exception:
                    pass

            metrics = tweet.get("public_metrics", {})
            engagement = (
                f"♥ {metrics.get('like_count', 0)}  "
                f"🔁 {metrics.get('retweet_count', 0)}  "
                f"💬 {metrics.get('reply_count', 0)}"
            )

            posts.append(
                Article(
                    title=text[:120] + ("…" if len(text) > 120 else ""),
                    url=f"https://x.com/{username}/status/{tid}",
                    source="X.com",
                    category="Social: X.com",
                    published=published,
                    summary=f"{text}\n\n{engagement}",
                    item_type="post",
                    author=f"@{username} ({display_name})",
                )
            )

    posts.sort(
        key=lambda a: a.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return posts


# ── Truth Social ──────────────────────────────────────────────────────────────

def fetch_truth_social_posts(
    queries: list[str],
    max_per_query: int = 10,
    include_public_timeline: bool = False,
    timeline_limit: int = 20,
) -> list[Article]:
    """
    Fetch posts from Truth Social.

    Uses the public Mastodon-compatible API — no authentication required.

    Args:
        queries: Search terms to look for (e.g. ["economy", "election"]).
        max_per_query: Max posts to fetch per search query.
        include_public_timeline: Also pull from the public timeline.
        timeline_limit: Posts to grab from the public timeline.

    Returns:
        List of Article objects with item_type="post".
    """
    posts: list[Article] = []
    seen_ids: set[str] = set()

    def _process_status(status: dict, query_label: str = "") -> Optional[Article]:
        sid = status.get("id", "")
        if sid in seen_ids:
            return None
        seen_ids.add(sid)

        content_html = status.get("content", "")
        text = _strip_html(content_html).strip()
        if not text:
            return None

        account = status.get("account", {})
        username = account.get("username", "unknown")
        display_name = account.get("display_name", username) or username
        url = status.get("url", f"https://truthsocial.com/@{username}/{sid}")

        created_at = status.get("created_at", "")
        published = None
        if created_at:
            try:
                published = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except Exception:
                pass

        stats = (
            f"♥ {status.get('favourites_count', 0)}  "
            f"🔁 {status.get('reblogs_count', 0)}  "
            f"💬 {status.get('replies_count', 0)}"
        )

        return Article(
            title=text[:120] + ("…" if len(text) > 120 else ""),
            url=url,
            source="Truth Social",
            category="Social: Truth Social",
            published=published,
            summary=f"{text}\n\n{stats}",
            item_type="post",
            author=f"@{username} ({display_name})",
        )

    # Search by queries
    for query in queries:
        query = query.strip()
        if not query:
            continue
        try:
            resp = requests.get(
                _TRUTH_SEARCH_URL,
                headers=_HEADERS,
                params={"q": query, "type": "statuses", "resolve": "false", "limit": max_per_query},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            for status in data.get("statuses", [])[:max_per_query]:
                article = _process_status(status, query)
                if article:
                    posts.append(article)
        except Exception:
            pass

    # Optionally pull from public timeline
    if include_public_timeline:
        try:
            resp = requests.get(
                _TRUTH_TIMELINE_URL,
                headers=_HEADERS,
                params={"limit": timeline_limit},
                timeout=15,
            )
            resp.raise_for_status()
            for status in resp.json():
                article = _process_status(status, "timeline")
                if article:
                    posts.append(article)
        except Exception:
            pass

    posts.sort(
        key=lambda a: a.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return posts


# ── Filtering & Enrichment ────────────────────────────────────────────────────

def filter_by_topics(articles: list[Article], topics: list[str]) -> list[Article]:
    """
    Filter articles/posts to those matching any of the given topics/keywords.
    If topics list is empty, returns all items.
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
    """Fetch and extract full article text using trafilatura."""
    if article.item_type == "post":
        return ""  # Social posts have all their text in summary already
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
    """Fetch full text for the top N articles (skips social posts)."""
    count = 0
    for article in articles:
        if count >= max_articles:
            break
        if article.item_type == "post" or article.full_text:
            continue
        article.full_text = fetch_full_text(article)
        count += 1
        if delay > 0:
            time.sleep(delay)
    return articles
