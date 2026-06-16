"""
YouTube ingestion for the Discovery layer.

Pipeline per channel (from config/channels.json):
    channel URL/@handle  ->  channel_id  ->  uploads RSS feed  ->  recent video ids
                                                                        |
                                                              transcript per video
                                                                        |
                                                                  TranscriptDoc

Design choices that matter:
  * Video discovery uses the public uploads RSS feed
    (youtube.com/feeds/videos.xml?channel_id=...) — free, no API key, no quota.
  * Transcripts use youtube-transcript-api (handles both the 0.6.x classmethod
    API and the 1.x instance API). These work best from a RESIDENTIAL IP.
  * DISCOVERY_DRY_RUN uses bundled SAMPLE_TRANSCRIPTS so the pipeline runs with
    no network and no keys. A real run NEVER silently substitutes samples.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from config import config

log = logging.getLogger(__name__)

_UPLOADS_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}


def _proxies() -> dict | None:
    """requests-style proxy dict from config, or None for a direct connection."""
    url = config.YOUTUBE_PROXY_URL.strip()
    return {"http": url, "https": url} if url else None


@dataclass
class TranscriptDoc:
    channel: str
    weight: float
    url: str
    text: str
    language: str = "en"
    meta: dict = field(default_factory=dict)


def load_channels() -> list[dict]:
    with open(config.CHANNELS_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh).get("channels", [])


# ---------------------------------------------------------------- ids
def extract_video_id(url: str) -> str | None:
    """Pull a video id from a watch/share/embed URL, else None."""
    for pat in (r"v=([\w-]{11})", r"youtu\.be/([\w-]{11})", r"/embed/([\w-]{11})"):
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def resolve_channel_id(url: str) -> str | None:
    """
    Turn any channel URL/@handle into its UC... channel id.
    Direct /channel/UC... is parsed; handles/custom URLs are resolved by
    fetching the page and reading the embedded channelId.
    """
    m = re.search(r"/channel/(UC[\w-]+)", url)
    if m:
        return m.group(1)
    try:
        import requests

        resp = requests.get(url, headers=_HEADERS, timeout=15, proxies=_proxies())
        resp.raise_for_status()
        m = re.search(r'"(?:channelId|externalId)":"(UC[\w-]+)"', resp.text)
        if m:
            return m.group(1)
        m = re.search(r'/channel/(UC[\w-]+)', resp.text)
        return m.group(1) if m else None
    except Exception as exc:
        log.warning("Could not resolve channel id for %s: %s", url, exc)
        return None


def recent_video_ids(channel_id: str, limit: int) -> list[str]:
    """Latest video ids from a channel's uploads RSS feed."""
    try:
        import feedparser
        import requests

        # Fetch via requests so the optional proxy applies (YouTube blocks many
        # datacenter IPs); feedparser then parses the returned bytes.
        resp = requests.get(
            _UPLOADS_FEED.format(cid=channel_id),
            headers=_HEADERS, timeout=15, proxies=_proxies(),
        )
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
        ids = []
        for entry in parsed.entries[:limit]:
            vid = entry.get("yt_videoid") or extract_video_id(entry.get("link", ""))
            if vid:
                ids.append(vid)
        return ids
    except Exception as exc:
        log.warning("Uploads feed failed for %s: %s", channel_id, exc)
        return []


# --------------------------------------------------------- transcripts
def fetch_transcript(video_id: str, languages: list[str] | None = None) -> str:
    """Fetch one transcript as plain text. Returns '' on any failure."""
    languages = languages or ["en", "hi", "en-IN"]
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        proxy_url = config.YOUTUBE_PROXY_URL.strip()

        # 0.6.x classmethod API
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            kwargs = {"proxies": _proxies()} if proxy_url else {}
            parts = YouTubeTranscriptApi.get_transcript(
                video_id, languages=languages, **kwargs
            )
            return " ".join(p["text"] for p in parts)
        # 1.x instance API
        if proxy_url:
            from youtube_transcript_api.proxies import GenericProxyConfig

            api = YouTubeTranscriptApi(
                proxy_config=GenericProxyConfig(http_url=proxy_url, https_url=proxy_url)
            )
        else:
            api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=languages)
        return " ".join(snippet.text for snippet in fetched)
    except Exception as exc:
        log.warning("Transcript unavailable for %s: %s", video_id, exc)
        return ""


# ------------------------------------------------------------- collect
def collect_transcripts() -> list[TranscriptDoc]:
    """Gather recent transcripts across all configured channels."""
    if config.DISCOVERY_DRY_RUN:
        log.info("DISCOVERY_DRY_RUN: using %d sample transcripts.", len(SAMPLE_TRANSCRIPTS))
        return list(SAMPLE_TRANSCRIPTS)

    docs: list[TranscriptDoc] = []
    for ch in load_channels():
        name = ch.get("name", "?")
        weight = float(ch.get("weight", 0.5))
        langs = [ch["language"], "en"] if ch.get("language") else None
        for url in ch.get("urls", []):
            vid = extract_video_id(url)
            video_ids = [vid] if vid else []
            if not video_ids:
                cid = resolve_channel_id(url)
                if cid:
                    video_ids = recent_video_ids(cid, config.MAX_VIDEOS_PER_CHANNEL)
            for vid in video_ids:
                text = fetch_transcript(vid, languages=langs)
                if text:
                    docs.append(TranscriptDoc(
                        channel=name, weight=weight,
                        url=f"https://www.youtube.com/watch?v={vid}",
                        text=text, language=(ch.get("language") or "en"),
                    ))
    log.info("Collected %d transcripts from %d channels.",
             len(docs), len(load_channels()))
    return docs


# ----------------------------------------------------- sample (dry-run)
SAMPLE_TRANSCRIPTS: list[TranscriptDoc] = [
    TranscriptDoc(
        channel="Sample Markets Channel", weight=0.8,
        url="https://www.youtube.com/watch?v=SAMPLE0001",
        text=(
            "Let's talk about my top conviction ideas. Reliance Industries "
            "continues to look strong — the Jio and retail story is a multi-year "
            "compounder and I'm accumulating on dips. TCS is another high quality "
            "name; the order book is robust and I remain bullish for the long term. "
            "I'm a little cautious on Paytm here — the path to profitability is "
            "still uncertain and I'd avoid adding until clarity improves. HDFC Bank "
            "remains a core holding, steady and undervalued after the merger."
        ),
    ),
    TranscriptDoc(
        channel="Sample Long-Term Investing", weight=0.6,
        url="https://www.youtube.com/watch?v=SAMPLE0002",
        text=(
            "Infosys numbers were decent and the stock looks attractive for "
            "patient investors — I am positive and would buy. Tata Motors has had "
            "a great run; the JLR turnaround is real but I'd book some profits as "
            "it looks overheated. I continue to like Reliance for the long haul. "
            "Stay away from richly valued momentum names for now."
        ),
    ),
]
