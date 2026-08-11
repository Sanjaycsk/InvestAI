"""
Results-day guard.

The daily review log shows this exact miss repeating across weeks (SUZLON
-8.5%, MARUTI +12.1%, HINDUNILVR -13.5% intraday, ADANIENT, BEL — each one
logged as "results calendar not checked" and patched with a new prompt
sentence telling the model to remember next time). A quarterly-results date
is a known, static fact well before the event; there is no reason this should
ever depend on an LLM "remembering" it. `config/earnings_calendar.json` is
the source of truth — update it once a quarter from the NSE announcements
calendar, and this becomes a hard gate instead of a hope.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta

from config import config

log = logging.getLogger(__name__)


def _load() -> dict[str, list[str]]:
    try:
        with open(config.EARNINGS_CALENDAR_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh).get("results_dates", {})
    except FileNotFoundError:
        log.warning("earnings_calendar.json not found at %s", config.EARNINGS_CALENDAR_PATH)
        return {}


def is_results_window(ticker: str, on: date, window_days: int = 1) -> bool:
    """True if `on` falls within `window_days` of a known results date (either side)."""
    dates = _load().get(ticker.upper(), [])
    for d in dates:
        results_date = datetime.strptime(d, "%Y-%m-%d").date()
        if abs((on - results_date).days) <= window_days:
            return True
    return False


def event_risk_note(ticker: str, on: date, window_days: int = 1) -> str | None:
    if is_results_window(ticker, on, window_days):
        return (
            f"{ticker} has a quarterly results date within {window_days} day(s) of "
            f"{on.isoformat()} — treat as event-risk: cap conviction, do not issue "
            "Strong Buy/Sell on pre-results drift, and re-verify price post-results."
        )
    return None
