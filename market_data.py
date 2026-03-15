"""
Market Data

Fetches pre-market / real-time price data via yfinance (no API key required).
Used to populate the Market Snapshot section of the morning brief.
"""

import re
from dataclasses import dataclass
from typing import Optional

import yfinance as yf

# ── Default Watchlist ─────────────────────────────────────────────────────────

DEFAULT_WATCHLIST = {
    "Indices & Futures": ["ES=F", "NQ=F", "RTY=F", "YM=F"],
    "ETFs": ["SPY", "QQQ", "IWM", "XLF", "XLK", "XBI"],
    "Rates & Vol": ["^VIX", "TLT", "HYG", "^TNX"],
    "Financials": ["GS", "JPM", "MS", "BAC", "BLK", "BX", "SCHW"],
    "AI & Tech": ["NVDA", "MSFT", "GOOGL", "META", "AMZN", "AAPL", "AMD", "TSLA"],
    "Commodities": ["GLD", "USO", "DX-Y.NYB"],
}

ALL_DEFAULT_TICKERS = [t for group in DEFAULT_WATCHLIST.values() for t in group]

# Friendly display names for common tickers
TICKER_NAMES = {
    "ES=F": "S&P 500 Futures",
    "NQ=F": "Nasdaq Futures",
    "RTY=F": "Russell 2000 Futures",
    "YM=F": "Dow Futures",
    "SPY": "S&P 500 ETF",
    "QQQ": "Nasdaq 100 ETF",
    "IWM": "Russell 2000 ETF",
    "XLF": "Financials ETF",
    "XLK": "Technology ETF",
    "XBI": "Biotech ETF",
    "^VIX": "VIX (Fear Index)",
    "TLT": "20Y Treasury ETF",
    "HYG": "High Yield Bond ETF",
    "^TNX": "10Y Treasury Yield",
    "GLD": "Gold ETF",
    "USO": "Crude Oil ETF",
    "DX-Y.NYB": "US Dollar Index",
    "GS": "Goldman Sachs",
    "JPM": "JPMorgan",
    "MS": "Morgan Stanley",
    "BAC": "Bank of America",
    "BLK": "BlackRock",
    "BX": "Blackstone",
    "SCHW": "Charles Schwab",
    "NVDA": "NVIDIA",
    "MSFT": "Microsoft",
    "GOOGL": "Alphabet",
    "META": "Meta",
    "AMZN": "Amazon",
    "AAPL": "Apple",
    "AMD": "AMD",
    "TSLA": "Tesla",
}


@dataclass
class Quote:
    ticker: str
    name: str
    prev_close: Optional[float]
    last_price: Optional[float]
    pre_market_price: Optional[float]
    change: Optional[float]          # vs prev close
    change_pct: Optional[float]      # vs prev close
    pre_market_change: Optional[float]
    pre_market_change_pct: Optional[float]
    volume: Optional[int]
    error: str = ""

    @property
    def display_price(self) -> str:
        p = self.pre_market_price or self.last_price
        return f"{p:.2f}" if p else "N/A"

    @property
    def display_change(self) -> str:
        chg = self.pre_market_change if self.pre_market_price else self.change
        pct = self.pre_market_change_pct if self.pre_market_price else self.change_pct
        if chg is None or pct is None:
            return "N/A"
        arrow = "▲" if chg >= 0 else "▼"
        sign = "+" if chg >= 0 else ""
        return f"{arrow} {sign}{chg:.2f} ({sign}{pct:.2f}%)"

    @property
    def is_pre_market(self) -> bool:
        return self.pre_market_price is not None


def _safe_float(val) -> Optional[float]:
    try:
        f = float(val)
        return f if f == f else None  # NaN check
    except (TypeError, ValueError):
        return None


def fetch_quote(ticker: str) -> Quote:
    """Fetch a single quote using yfinance fast_info."""
    name = TICKER_NAMES.get(ticker, ticker)
    try:
        t = yf.Ticker(ticker)
        fi = t.fast_info

        prev_close = _safe_float(getattr(fi, "previous_close", None))
        last = _safe_float(getattr(fi, "last_price", None))
        pre = _safe_float(getattr(fi, "pre_market_price", None))

        change = (last - prev_close) if last and prev_close else None
        change_pct = (change / prev_close * 100) if change and prev_close else None

        pre_change = (pre - prev_close) if pre and prev_close else None
        pre_change_pct = (pre_change / prev_close * 100) if pre_change and prev_close else None

        volume = None
        try:
            volume = int(getattr(fi, "three_month_average_volume", None) or 0) or None
        except (TypeError, ValueError):
            pass

        return Quote(
            ticker=ticker,
            name=name,
            prev_close=prev_close,
            last_price=last,
            pre_market_price=pre,
            change=change,
            change_pct=change_pct,
            pre_market_change=pre_change,
            pre_market_change_pct=pre_change_pct,
            volume=volume,
        )
    except Exception as e:
        return Quote(
            ticker=ticker, name=name,
            prev_close=None, last_price=None, pre_market_price=None,
            change=None, change_pct=None,
            pre_market_change=None, pre_market_change_pct=None,
            volume=None, error=str(e),
        )


def fetch_premarket_data(tickers: list[str]) -> list[Quote]:
    """
    Fetch pre-market / latest quotes for a list of tickers.
    Returns one Quote per ticker, skipping those with errors.
    """
    quotes = []
    for ticker in tickers:
        ticker = ticker.strip().upper()
        if not ticker:
            continue
        q = fetch_quote(ticker)
        quotes.append(q)
    return quotes


def quotes_to_markdown_table(quotes: list[Quote]) -> str:
    """Render quotes as a markdown table for the report prompt."""
    rows = []
    for q in quotes:
        if q.error and not q.last_price:
            continue
        pre_flag = " *(pre-mkt)*" if q.is_pre_market else ""
        rows.append(
            f"| {q.ticker} | {q.name} | {q.display_price}{pre_flag} | {q.display_change} |"
        )
    if not rows:
        return "*No market data available.*"
    header = "| Ticker | Name | Price | Change |"
    divider = "|--------|------|-------|--------|"
    return "\n".join([header, divider] + rows)


def extract_tickers_from_text(text: str) -> list[str]:
    """
    Extract $TICKER patterns from article/post text.
    Returns up to 20 unique tickers, uppercased.
    """
    matches = re.findall(r"\$([A-Z]{1,5})", text.upper())
    seen = []
    for m in matches:
        if m not in seen:
            seen.append(m)
        if len(seen) >= 20:
            break
    return seen
