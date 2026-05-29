import re
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

try:
    import feedparser
    _FEEDPARSER_AVAILABLE = True
except ImportError:
    _FEEDPARSER_AVAILABLE = False

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 8  # seconds; sources that don't respond are skipped silently

RSS_FEEDS = {
    "Reuters": "https://feeds.reuters.com/reuters/businessNews",
    "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "MarketWatch": "https://www.marketwatch.com/rss/topstories",
    "SeekingAlpha": "https://seekingalpha.com/market_currents.xml",
}

TICKER_RE = re.compile(r'\$([A-Z]{1,5})\b')


@dataclass
class NewsItem:
    source: str
    headline: str
    summary: str
    url: str
    published_at: datetime
    ticker: Optional[str] = None


def _parse_feed_entry(source: str, entry) -> Optional[NewsItem]:
    try:
        headline = entry.get("title", "").strip()
        if not headline:
            return None
        summary = BeautifulSoup(
            entry.get("summary", entry.get("description", "")), "html.parser"
        ).get_text()[:500]
        url = entry.get("link", "")
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if published:
            pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
        else:
            pub_dt = datetime.now(timezone.utc)
        tickers = TICKER_RE.findall(headline + " " + summary)
        return NewsItem(
            source=source,
            headline=headline,
            summary=summary,
            url=url,
            published_at=pub_dt,
            ticker=tickers[0] if tickers else None,
        )
    except Exception as e:
        logger.debug("Failed to parse feed entry from %s: %s", source, e)
        return None


class NewsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def fetch_all(self, tickers: list[str]) -> list[NewsItem]:
        items: list[NewsItem] = []
        items += self._fetch_rss_feeds()
        for ticker in tickers:
            items += self._fetch_yahoo_finance(ticker)
            items += self._fetch_stocktwits(ticker)
        return self._deduplicate(items)

    def _fetch_rss_feeds(self) -> list[NewsItem]:
        if not _FEEDPARSER_AVAILABLE:
            return self._fetch_rss_via_requests()
        items = []
        for source, url in RSS_FEEDS.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:20]:
                    item = _parse_feed_entry(source, entry)
                    if item:
                        items.append(item)
            except Exception as e:
                logger.warning("RSS feed error for %s: %s", source, e)
        return items

    def _fetch_rss_via_requests(self) -> list[NewsItem]:
        """Fallback RSS parser using requests + BeautifulSoup when feedparser unavailable."""
        items = []
        for source, url in RSS_FEEDS.items():
            try:
                resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.content, "xml")
                for entry in soup.find_all("item")[:20]:
                    headline = entry.find("title")
                    headline = headline.get_text().strip() if headline else ""
                    if not headline:
                        continue
                    summary_tag = entry.find("description") or entry.find("summary")
                    summary = BeautifulSoup(summary_tag.get_text() if summary_tag else "", "html.parser").get_text()[:500]
                    link = entry.find("link")
                    url_str = link.get_text().strip() if link else ""
                    tickers = TICKER_RE.findall(headline + " " + summary)
                    items.append(NewsItem(
                        source=source,
                        headline=headline,
                        summary=summary,
                        url=url_str,
                        published_at=datetime.now(timezone.utc),
                        ticker=tickers[0] if tickers else None,
                    ))
            except Exception as e:
                logger.warning("RSS fallback error for %s: %s", source, e)
        return items

    def _fetch_yahoo_finance(self, ticker: str) -> list[NewsItem]:
        try:
            url = f"https://query1.finance.yahoo.com/v1/finance/search?q={ticker}&newsCount=10&enableFuzzyQuery=false"
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return []
            news = resp.json().get("news", [])
            items = []
            for n in news[:10]:
                headline = n.get("title", "").strip()
                if not headline:
                    continue
                pub_ts = n.get("providerPublishTime", 0)
                pub_dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc) if pub_ts else datetime.now(timezone.utc)
                items.append(NewsItem(
                    source="Yahoo Finance",
                    headline=headline,
                    summary="",
                    url=n.get("link", ""),
                    published_at=pub_dt,
                    ticker=ticker,
                ))
            return items
        except Exception as e:
            logger.warning("Yahoo Finance news error for %s: %s", ticker, e)
            return []

    def _fetch_stocktwits(self, ticker: str) -> list[NewsItem]:
        try:
            url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return []
            data = resp.json()
            messages = data.get("messages", [])
            items = []
            for msg in messages[:15]:
                body = msg.get("body", "").strip()
                if not body:
                    continue
                created = msg.get("created_at", "")
                try:
                    pub_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except Exception:
                    pub_dt = datetime.now(timezone.utc)
                items.append(NewsItem(
                    source="Stocktwits",
                    headline=body[:120],
                    summary=body[:500],
                    url=f"https://stocktwits.com/symbol/{ticker}",
                    published_at=pub_dt,
                    ticker=ticker,
                ))
            return items
        except Exception as e:
            logger.warning("Stocktwits error for %s: %s", ticker, e)
            return []

    def _deduplicate(self, items: list[NewsItem]) -> list[NewsItem]:
        seen: set[str] = set()
        unique = []
        for item in items:
            key = item.headline.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique
