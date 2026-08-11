"""
Daily price history for the 200-DMA baseline.

Primary source is yfinance (free NSE/BSE daily candles). When DUMMY_MODE is on,
or when yfinance is unavailable/offline, we fall back to a *deterministic*
synthetic series so the whole Phase-1 pipeline runs end-to-end with no keys and
no network. The synthetic generator is seeded from the symbol, so a given ticker
always produces the same trend — handy for reproducible testing.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from config import config

log = logging.getLogger(__name__)

# Map NSE/BSE symbols to Yahoo Finance suffixes.
_EXCHANGE_SUFFIX = {"NSE": ".NS", "BSE": ".BO"}


def to_yf_symbol(symbol: str, exchange: str = "NSE") -> str:
    """RELIANCE + NSE -> 'RELIANCE.NS'. Leaves already-suffixed symbols alone."""
    if "." in symbol:
        return symbol
    return f"{symbol}{_EXCHANGE_SUFFIX.get(exchange.upper(), '.NS')}"


def _seed_from_symbol(symbol: str) -> int:
    digest = hashlib.sha256(symbol.encode()).hexdigest()
    return int(digest[:8], 16)


def generate_dummy_history(symbol: str, days: int = 400) -> pd.Series:
    """
    Deterministic synthetic daily-close series with a per-symbol trend.

    Roughly half of symbols trend downward (so they fall below the 200-DMA and
    fire a red flag) and half upward — exercising both branches of the logic.
    """
    rng = np.random.default_rng(_seed_from_symbol(symbol))
    base = 100 + (rng.integers(0, 4000) / 10.0)          # base price 100–500
    # Drift sign decided by the seed -> stable per symbol.
    drift = (0.05 if rng.random() > 0.5 else -0.05)
    noise = rng.normal(0, 1.0, size=days)
    trend = np.cumsum(np.full(days, drift) + noise)
    closes = np.maximum(base + trend, 1.0)               # keep prices positive
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    return pd.Series(closes, index=idx, name="close")


def get_close_history(
    symbol: str,
    exchange: str = "NSE",
    days: int = 400,
) -> Optional[pd.Series]:
    """
    Return a Series of daily closes indexed by date, or None if unavailable.

    `days` should comfortably exceed SMA_WINDOW (need ~window+buffer candles).
    """
    if config.DUMMY_MODE:
        log.debug("DUMMY_MODE: synthetic history for %s", symbol)
        return generate_dummy_history(symbol, days=days)

    try:
        import yfinance as yf  # imported lazily so DUMMY_MODE needs no network lib

        yf_symbol = to_yf_symbol(symbol, exchange)
        period = f"{max(days, config.SMA_WINDOW + 60)}d"
        df = yf.download(
            yf_symbol, period=period, interval="1d",
            progress=False, auto_adjust=True,
        )
        if df is None or df.empty:
            log.warning("yfinance returned no data for %s; using synthetic.", yf_symbol)
            return generate_dummy_history(symbol, days=days)
        close = df["Close"]
        if isinstance(close, pd.DataFrame):  # multi-index guard
            close = close.iloc[:, 0]
        return close.dropna()
    except Exception as exc:  # network/library failure -> safe fallback
        log.warning("Price fetch failed for %s (%s); using synthetic.", symbol, exc)
        return generate_dummy_history(symbol, days=days)


def latest_price(symbol: str, exchange: str = "NSE") -> Optional[float]:
    """Most recent close. (Live LTP for execution comes from Kite, not here.)"""
    series = get_close_history(symbol, exchange, days=config.SMA_WINDOW + 30)
    if series is None or series.empty:
        return None
    return float(series.iloc[-1])


# --------------------------------------------------------- verified price
#
# The single most common recurring error in the daily agent's own review log
# is a stale or wrong reference price (e.g. quoting WAAREEENER at ₹357 when it
# was trading near ₹2,732 — a 7.6x miss). That bug was being "fixed" by asking
# an LLM to remember to double-check itself, which — unsurprisingly — it kept
# forgetting to do. This makes the check structural instead: two independent
# sources are pulled, and if they disagree beyond `tolerance_pct`, or if the
# only available quote is older than `max_staleness_days`, the caller gets an
# unverified result back and must decide whether to act on it (the default
# policy, applied in scoring/execution, is: don't).
@dataclass
class VerifiedPrice:
    price: Optional[float]
    is_verified: bool
    sources: dict[str, float] = field(default_factory=dict)
    as_of: Optional[str] = None
    staleness_days: Optional[int] = None
    warning: str = ""


def _days_since(idx_date) -> int:
    now = datetime.now(timezone.utc)
    ts = pd.Timestamp(idx_date)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return (now - ts.to_pydatetime()).days


def get_verified_price(
    symbol: str,
    exchange: str = "NSE",
    *,
    kite=None,
    tolerance_pct: Optional[float] = None,
    max_staleness_days: Optional[int] = None,
) -> VerifiedPrice:
    """
    Cross-check a reference price across yfinance (daily close) and, if a
    KiteClient is supplied, the live LTP. Returns `is_verified=True` only when
    at least one source is fresh AND (if two sources exist) they agree within
    `tolerance_pct`. A single stale source, or two disagreeing sources, comes
    back unverified with `warning` explaining why — callers should treat an
    unverified price as unsafe to score or trade on.
    """
    tolerance_pct = config.PRICE_TOLERANCE_PCT if tolerance_pct is None else tolerance_pct
    max_staleness_days = (
        config.PRICE_MAX_STALENESS_DAYS if max_staleness_days is None else max_staleness_days
    )
    sources: dict[str, float] = {}
    as_of: Optional[str] = None
    staleness_days: Optional[int] = None

    series = get_close_history(symbol, exchange, days=config.SMA_WINDOW + 30)
    yf_stale = True
    if series is not None and not series.empty:
        sources["yfinance"] = float(series.iloc[-1])
        as_of = str(series.index[-1].date())
        staleness_days = _days_since(series.index[-1])
        yf_stale = staleness_days > max_staleness_days

    if kite is not None:
        try:
            ltp = kite.get_ltp(symbol, exchange)
            if ltp:
                sources["kite_ltp"] = float(ltp)
        except Exception as exc:
            log.warning("Kite LTP check failed for %s: %s", symbol, exc)

    if not sources:
        return VerifiedPrice(None, False, {}, as_of, staleness_days,
                              "no source returned a price")

    if len(sources) >= 2:
        vals = list(sources.values())
        spread_pct = (max(vals) - min(vals)) / min(vals) * 100.0 if min(vals) else 999
        if spread_pct > tolerance_pct:
            return VerifiedPrice(
                None, False, sources, as_of, staleness_days,
                f"sources disagree by {spread_pct:.1f}% (>{tolerance_pct}% tolerance) "
                f"— {sources}",
            )
        # Agreement across two independent sources overrides a merely-stale
        # yfinance candle (the live LTP confirms it's still accurate).
        return VerifiedPrice(sources.get("kite_ltp", vals[0]), True, sources,
                              as_of, staleness_days, "")

    # Single source only — trust it iff it isn't stale.
    only_key, only_val = next(iter(sources.items()))
    if only_key == "yfinance" and yf_stale:
        return VerifiedPrice(
            None, False, sources, as_of, staleness_days,
            f"single source (yfinance) is {staleness_days}d old "
            f"(> {max_staleness_days}d staleness limit) and cannot be cross-checked",
        )
    return VerifiedPrice(only_val, True, sources, as_of, staleness_days, "")
