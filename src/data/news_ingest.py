"""
Financial-blog / news ingestion via RSS (your chosen source).

Pulls recent articles from the feeds in config/feeds.json (Moneycontrol, ET,
LiveMint, Business Standard by default — add your own blog feeds), tags each
article with any NSE tickers it mentions, and exposes them grouped by ticker so
the synthesizer can corroborate what YouTube surfaced.

Free, no API key. DISCOVERY_DRY_RUN uses bundled SAMPLE_ARTICLES so the pipeline
runs offline. A real run never silently substitutes samples.
(If you later want deeper coverage, news_ingest is where Bright Data would slot
in alongside RSS — see requirements.txt.)
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from config import config
from src.analysis.tickers import extract_candidates

log = logging.getLogger(__name__)


@dataclass
class Article:
    title: str
    summary: str
    url: str
    source: str
    weight: float = 0.5
    published: str | None = None
    tickers: dict[str, int] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return f"{self.title}. {self.summary}"


def load_feeds() -> list[dict]:
    try:
        with open(config.FEEDS_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh).get("feeds", [])
    except FileNotFoundError:
        log.warning("feeds.json not found at %s", config.FEEDS_PATH)
        return []


def _recent_enough(entry, cutoff: datetime) -> bool:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return True  # keep undated entries rather than dropping silently
    published = datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)
    return published >= cutoff


def fetch_recent_articles() -> list[Article]:
    """Fetch + ticker-tag recent articles across all configured feeds."""
    if config.DISCOVERY_DRY_RUN:
        log.info("DISCOVERY_DRY_RUN: using %d sample articles.", len(SAMPLE_ARTICLES))
        return [_tag(a) for a in SAMPLE_ARTICLES]

    import feedparser

    cutoff = datetime.now(timezone.utc) - timedelta(days=config.NEWS_LOOKBACK_DAYS)
    articles: list[Article] = []
    for feed in load_feeds():
        name, weight, url = feed.get("name", "?"), float(feed.get("weight", 0.5)), feed.get("url", "")
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries:
                if not _recent_enough(entry, cutoff):
                    continue
                art = Article(
                    title=entry.get("title", ""),
                    summary=re_strip(entry.get("summary", "")),
                    url=entry.get("link", ""),
                    source=name,
                    weight=weight,
                    published=entry.get("published"),
                )
                articles.append(_tag(art))
        except Exception as exc:
            log.warning("Feed failed (%s): %s", name, exc)
    log.info("Fetched %d recent articles from %d feeds.", len(articles), len(load_feeds()))
    return articles


def _tag(art: Article) -> Article:
    art.tickers = extract_candidates(art.text)
    return art


def re_strip(html: str) -> str:
    """Crude HTML-tag stripper for RSS summaries (avoids a bs4 dependency)."""
    import re
    return re.sub(r"<[^>]+>", "", html or "").strip()


def group_by_ticker(articles: list[Article]) -> dict[str, list[Article]]:
    grouped: dict[str, list[Article]] = {}
    for art in articles:
        for symbol in art.tickers:
            grouped.setdefault(symbol, []).append(art)
    return grouped


# ----------------------------------------------------- sample (dry-run)
SAMPLE_ARTICLES: list[Article] = [
    Article(
        title="Reliance Industries hits fresh high as retail, Jio momentum continues",
        summary="Analysts stay bullish on Reliance citing strong subscriber growth and retail expansion.",
        url="https://example.com/reliance-high", source="Sample Markets Wire", weight=0.8,
    ),
    Article(
        title="TCS wins large multi-year deal; brokerages positive on IT major",
        summary="TCS order book strengthens; long-term outlook remains constructive.",
        url="https://example.com/tcs-deal", source="Sample Markets Wire", weight=0.8,
    ),
    Article(
        title="Paytm shares slip as profitability concerns linger",
        summary="Investors remain cautious on Paytm amid regulatory and margin pressures.",
        url="https://example.com/paytm-slip", source="Sample Business Daily", weight=0.7,
    ),
    Article(
        title="Infosys guidance reassures Street; stock seen attractive long term",
        summary="Infosys margins steady; analysts see value for patient investors.",
        url="https://example.com/infosys-guidance", source="Sample Business Daily", weight=0.7,
    ),
]
