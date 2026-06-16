"""
Technical signal layer.

Phase 1 implements the 200-day Simple Moving Average baseline you specified:
  * close < SMA(200)  -> RED  flag "Trend Weakening"  (action: REDUCE)
  * close > SMA(200)  -> GREEN flag "Above long-term trend" (action: HOLD/ACCUMULATE)

The SMA is intentionally simple and lagging; treat it as a *first* filter.
Phases 2/3 layer transcript + news sentiment on top via the synthesizer.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from config import config
from src.analysis.schema import Action, Flag, Recommendation

log = logging.getLogger(__name__)


def simple_moving_average(closes: pd.Series, window: int) -> Optional[float]:
    """Latest SMA value, or None if there isn't enough history."""
    if closes is None or len(closes) < window:
        return None
    return float(closes.rolling(window=window).mean().iloc[-1])


def assess_trend(
    ticker: str,
    closes: pd.Series,
    *,
    exchange: str = "NSE",
    held_qty: int = 0,
    window: Optional[int] = None,
) -> Recommendation:
    """
    Build a technical Recommendation for one ticker from its close history.

    `held_qty` (current holding size) lets us suggest a sensible REDUCE quantity
    for a red flag; for non-holdings it stays 0 and the action is WATCH/HOLD.
    """
    window = window or config.SMA_WINDOW
    last_close = float(closes.iloc[-1]) if len(closes) else None
    sma = simple_moving_average(closes, window)

    rec = Recommendation(
        ticker=ticker,
        exchange=exchange,
        price_at_analysis=last_close,
        source=f"technical:{window}dma",
    )

    if sma is None or last_close is None:
        rec.flag = Flag.NEUTRAL
        rec.recommended_action = Action.WATCH
        rec.rationale = (
            f"Insufficient history (<{window} candles) to compute the SMA. "
            "No trend signal yet."
        )
        rec.sentiment_score = 0.0
        return rec

    gap_pct = (last_close - sma) / sma * 100.0

    if gap_pct < -config.SMA_RED_FLAG_BUFFER * 100.0:
        rec.flag = Flag.RED
        rec.recommended_action = Action.REDUCE if held_qty > 0 else Action.WATCH
        # Suggest trimming a quarter of the position as a conservative default.
        rec.suggested_qty = max(1, held_qty // 4) if held_qty > 0 else 0
        rec.sentiment_score = round(max(-1.0, gap_pct / 20.0), 3)
        rec.rationale = (
            f"🔴 Trend Weakening — last close ₹{last_close:,.2f} is "
            f"{abs(gap_pct):.1f}% BELOW the {window}-day SMA (₹{sma:,.2f}). "
            "Long-term trend is turning down."
        )
    else:
        rec.flag = Flag.GREEN
        rec.recommended_action = Action.HOLD if held_qty > 0 else Action.WATCH
        rec.sentiment_score = round(min(1.0, gap_pct / 20.0), 3)
        rec.rationale = (
            f"🟢 Above long-term trend — last close ₹{last_close:,.2f} is "
            f"{gap_pct:.1f}% ABOVE the {window}-day SMA (₹{sma:,.2f})."
        )

    return rec
