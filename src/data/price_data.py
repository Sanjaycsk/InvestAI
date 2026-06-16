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
