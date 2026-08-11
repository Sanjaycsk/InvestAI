"""
Central configuration. Loads config/.env and exposes typed settings.

Two independent safety switches gate ALL real-money behaviour:
    DUMMY_MODE         -> when True, broker calls are simulated.
    EXECUTION_ENABLED  -> must ALSO be True for any real order.

Both are designed to fail safe: if the value is missing or unparseable,
we default to the *safe* setting (DUMMY_MODE=True, EXECUTION_ENABLED=False).
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data_store"
DATA_DIR.mkdir(exist_ok=True)

ENV_PATH = CONFIG_DIR / ".env"
CHANNELS_PATH = CONFIG_DIR / "channels.json"
FEEDS_PATH = CONFIG_DIR / "feeds.json"
EARNINGS_CALENDAR_PATH = CONFIG_DIR / "earnings_calendar.json"
SCORE_CALIBRATION_PATH = CONFIG_DIR / "score_calibration.json"
DB_PATH = DATA_DIR / "state.db"

# Load .env (silently no-ops if the file is absent — defaults still apply).
load_dotenv(ENV_PATH)


# ----------------------------------------------------------------------
# Parsers
# ----------------------------------------------------------------------
def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


# ----------------------------------------------------------------------
# Safety switches (fail safe)
# ----------------------------------------------------------------------
DUMMY_MODE: bool = _as_bool(os.getenv("DUMMY_MODE"), default=True)
EXECUTION_ENABLED: bool = _as_bool(os.getenv("EXECUTION_ENABLED"), default=False)

# ----------------------------------------------------------------------
# Zerodha
# ----------------------------------------------------------------------
KITE_API_KEY = os.getenv("KITE_API_KEY", "")
KITE_API_SECRET = os.getenv("KITE_API_SECRET", "")
KITE_USER_ID = os.getenv("KITE_USER_ID", "")
KITE_TOTP_SECRET = os.getenv("KITE_TOTP_SECRET", "")
KITE_ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN", "")

# ----------------------------------------------------------------------
# Telegram
# ----------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ----------------------------------------------------------------------
# Claude (synthesis)
# ----------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# ----------------------------------------------------------------------
# Bright Data (Phase 2)
# ----------------------------------------------------------------------
BRIGHTDATA_API_KEY = os.getenv("BRIGHTDATA_API_KEY", "")

# ----------------------------------------------------------------------
# Risk guardrails
# ----------------------------------------------------------------------
MAX_ORDER_VALUE_INR = _as_float(os.getenv("MAX_ORDER_VALUE_INR"), 25_000.0)
MAX_DAILY_TRADES = _as_int(os.getenv("MAX_DAILY_TRADES"), 5)
APPROVAL_TTL_MINUTES = _as_int(os.getenv("APPROVAL_TTL_MINUTES"), 30)
# Per-position stop-loss (independent of the 200-DMA, which is far too
# lagging to cap a single trade's downside — the audit found the only exit
# trigger was the SMA cross, letting wrong calls run well past what a stop
# would have allowed).
STOP_LOSS_PCT = _as_float(os.getenv("STOP_LOSS_PCT"), 5.0)
# Circuit breaker: once this many stop-losses fire in a day, no new BUY
# recommendations are sized above zero for the rest of the session — a bad
# day for the model shouldn't compound into a bad day for the book.
MAX_DAILY_STOP_LOSSES = _as_int(os.getenv("MAX_DAILY_STOP_LOSSES"), 3)
# get_verified_price(): max allowed disagreement between independent price
# sources, and max age of a single-source quote, before it's rejected as
# unverified rather than acted on.
PRICE_TOLERANCE_PCT = _as_float(os.getenv("PRICE_TOLERANCE_PCT"), 3.0)
PRICE_MAX_STALENESS_DAYS = _as_int(os.getenv("PRICE_MAX_STALENESS_DAYS"), 4)
# Max rupees willing to LOSE on a single position if its stop-loss fires
# (not the position's notional — its risk). Position size is derived from
# this budget, the stop distance, and the calibrated confidence for the
# score band — see src/analysis/position_sizing.py. Tune to your real
# capital; this default is a conservative paper-trading placeholder.
MAX_RISK_PER_TRADE_INR = _as_float(os.getenv("MAX_RISK_PER_TRADE_INR"), 1_000.0)

# ----------------------------------------------------------------------
# Market / analysis
# ----------------------------------------------------------------------
SMA_WINDOW = _as_int(os.getenv("SMA_WINDOW"), 200)
# A holding is "Trend Weakening" when its close is more than this fraction
# below the SMA (small buffer avoids flapping right at the line).
SMA_RED_FLAG_BUFFER = _as_float(os.getenv("SMA_RED_FLAG_BUFFER"), 0.0)
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
DEFAULT_EXCHANGE = os.getenv("DEFAULT_EXCHANGE", "NSE")

# ----------------------------------------------------------------------
# Discovery (YouTube + blogs/news -> Claude synthesis)
# ----------------------------------------------------------------------
# When True, ingestion uses bundled sample data instead of hitting the network,
# and synthesis falls back to a heuristic if no ANTHROPIC_API_KEY — so the whole
# pipeline runs offline with zero keys. When False, ingestion uses ONLY real
# data (it never silently injects samples — an empty result stays empty so a
# real run is never mistaken for canned content).
DISCOVERY_DRY_RUN = _as_bool(os.getenv("DISCOVERY_DRY_RUN"), default=False)
# Optional proxy for YouTube ingestion. Datacenter/VPS IPs are frequently blocked
# by YouTube for transcript fetching; route through a (residential) proxy to avoid
# that. Leave blank to connect directly (the default, correct for a home/residential
# IP). Format: http://user:pass@host:port  (used for both video discovery + transcripts).
YOUTUBE_PROXY_URL = os.getenv("YOUTUBE_PROXY_URL", "")
# How many recent videos to pull per channel, and news lookback window.
MAX_VIDEOS_PER_CHANNEL = _as_int(os.getenv("MAX_VIDEOS_PER_CHANNEL"), 4)
NEWS_LOOKBACK_DAYS = _as_int(os.getenv("NEWS_LOOKBACK_DAYS"), 5)
# Only surface suggestions at/above this confidence; cap the Telegram list.
MIN_MENTIONS_TO_SUGGEST = _as_int(os.getenv("MIN_MENTIONS_TO_SUGGEST"), 1)
TOP_N_SUGGESTIONS = _as_int(os.getenv("TOP_N_SUGGESTIONS"), 3)


def safety_banner() -> str:
    """Human-readable one-liner describing the current safety posture."""
    if DUMMY_MODE:
        return "🟢 DUMMY_MODE ON — all trades simulated. No real orders possible."
    if not EXECUTION_ENABLED:
        return "🟡 DUMMY_MODE OFF but EXECUTION_ENABLED=False — orders still blocked."
    return "🔴 LIVE EXECUTION ARMED — real orders can be placed on approval."


def can_execute_live() -> bool:
    """Both switches must be set for a real order to ever be placed."""
    return (not DUMMY_MODE) and EXECUTION_ENABLED
