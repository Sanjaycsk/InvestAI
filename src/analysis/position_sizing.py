"""
Conviction-scaled position sizing — the fix for the audit's headline finding:
~70-78% directional accuracy but still net losses, because every idea was
sized the same regardless of how confident the call actually was, and there
was no stop-loss capping how much a wrong call could cost.

Deliberately NOT sized off the raw sentiment/composite score — that score is
proven miscalibrated (see calibration.py: the highest-score band has the
worst hit rate). Sized off the *empirical* calibrated confidence instead, and
off a fixed risk-per-trade budget rather than a fixed share count, so a
low-confidence idea and a high-confidence idea can never cost the same amount
if the stop-loss fires.
"""
from __future__ import annotations

from config import config
from src.analysis.calibration import calibrated_confidence


def stop_loss_price(entry_price: float, *, stop_loss_pct: float | None = None) -> float:
    pct = config.STOP_LOSS_PCT if stop_loss_pct is None else stop_loss_pct
    return round(entry_price * (1 - pct / 100.0), 2)


def position_size(
    *,
    price: float,
    composite_score: float,
    stop_loss_pct: float | None = None,
    capital_at_risk_inr: float | None = None,
) -> tuple[int, float]:
    """
    Returns (suggested_qty, calibrated_confidence).

    No edge -> no trade: a confidence at or below 0.5 (coin-flip or worse)
    returns qty=0 regardless of how "strong" the raw score looked. Above
    that, size scales linearly with edge (confidence - 0.5), halved again if
    the score band is statistically unreliable (n < MIN_RELIABLE_N in the
    calibration table) — an unreliable band with an apparent edge still gets
    a small position, not zero and not full size.
    """
    stop_pct = config.STOP_LOSS_PCT if stop_loss_pct is None else stop_loss_pct
    risk_budget = config.MAX_RISK_PER_TRADE_INR if capital_at_risk_inr is None else capital_at_risk_inr

    confidence, is_reliable, _note = calibrated_confidence(composite_score)
    if confidence <= 0.5 or price <= 0 or stop_pct <= 0:
        return 0, confidence

    edge = confidence - 0.5                      # 0 .. 0.5
    conviction_multiplier = edge / 0.5            # 0 .. 1
    if not is_reliable:
        conviction_multiplier *= 0.5

    risk_per_share = price * (stop_pct / 100.0)
    qty = int((risk_budget * conviction_multiplier) // risk_per_share)
    return max(qty, 0), confidence
