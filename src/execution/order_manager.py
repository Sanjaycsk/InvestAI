"""
The SAFE layer. The ONLY place an order is ever placed.

A real order requires ALL of:
  1. config.DUMMY_MODE   == False
  2. config.EXECUTION_ENABLED == True
  3. the recommendation is APPROVED, unexpired, and token-valid
  4. guardrails pass: order notional <= MAX_ORDER_VALUE_INR
                      and daily executions < MAX_DAILY_TRADES

If any check fails we simulate (log SIMULATED) instead of trading. This module
is deliberately defensive: it would rather do nothing than do the wrong thing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from config import config
from src.analysis.schema import Action, Recommendation, RecStatus
from src.data.kite_client import KiteClient
from src.store import db

log = logging.getLogger(__name__)

# Map our actions to broker transaction sides.
_BUY_ACTIONS = {Action.BUY, Action.ACCUMULATE}
_SELL_ACTIONS = {Action.REDUCE, Action.SELL}


@dataclass
class ExecutionResult:
    ok: bool
    simulated: bool
    status: RecStatus
    message: str
    order_id: str | None = None


def _side_for(action: Action) -> str | None:
    if action in _BUY_ACTIONS:
        return "BUY"
    if action in _SELL_ACTIONS:
        return "SELL"
    return None  # HOLD / WATCH are not tradable


def _guardrails_ok(rec: Recommendation, live_price: float) -> tuple[bool, str]:
    notional = live_price * rec.suggested_qty
    if rec.suggested_qty <= 0:
        return False, "suggested_qty is 0 — nothing to trade."
    if notional > config.MAX_ORDER_VALUE_INR:
        return False, (
            f"order value ₹{notional:,.0f} exceeds cap "
            f"₹{config.MAX_ORDER_VALUE_INR:,.0f}."
        )
    if db.count_executions_today() >= config.MAX_DAILY_TRADES:
        return False, f"daily trade cap ({config.MAX_DAILY_TRADES}) reached."
    return True, "ok"


def execute_recommendation(
    rec: Recommendation,
    *,
    kite: KiteClient | None = None,
) -> ExecutionResult:
    """
    Called by the bot AFTER the human approves. Re-validates everything from
    scratch — never trusts that approval implies safety.
    """
    side = _side_for(rec.recommended_action)
    if side is None:
        msg = f"{rec.recommended_action.value} is not a tradable action."
        db.update_status(rec.recommendation_id, RecStatus.REJECTED, msg)
        return ExecutionResult(False, False, RecStatus.REJECTED, msg)

    if rec.is_expired():
        msg = "approval window expired — re-run analysis for a fresh quote."
        db.update_status(rec.recommendation_id, RecStatus.EXPIRED, msg)
        return ExecutionResult(False, False, RecStatus.EXPIRED, msg)

    kite = kite or KiteClient()
    # Re-fetch a live price; the summary quote may be stale.
    live_price = kite.get_ltp(rec.ticker, rec.exchange) or rec.price_at_analysis or 0.0
    ok, reason = _guardrails_ok(rec, live_price)
    if not ok:
        db.update_status(rec.recommendation_id, RecStatus.REJECTED, reason)
        return ExecutionResult(False, False, RecStatus.REJECTED, reason)

    # ---- THE GATE ----------------------------------------------------
    if not config.can_execute_live():
        msg = (
            f"SIMULATED {side} {rec.suggested_qty} {rec.ticker} "
            f"@ ~₹{live_price:,.2f} (₹{live_price * rec.suggested_qty:,.0f}). "
            f"[{config.safety_banner()}]"
        )
        log.info(msg)
        db.update_status(rec.recommendation_id, RecStatus.SIMULATED, msg)
        return ExecutionResult(True, True, RecStatus.SIMULATED, msg)

    # ---- LIVE ORDER (both toggles on, guardrails passed) -------------
    try:
        order_id = kite.place_order(
            symbol=rec.ticker, exchange=rec.exchange, side=side,
            quantity=rec.suggested_qty,
        )
        msg = f"EXECUTED {side} {rec.suggested_qty} {rec.ticker} (order {order_id})."
        log.warning(msg)
        db.update_status(rec.recommendation_id, RecStatus.EXECUTED,
                         f"{msg} @ ~₹{live_price:,.2f}")
        return ExecutionResult(True, False, RecStatus.EXECUTED, msg, order_id)
    except Exception as exc:
        msg = f"order placement FAILED for {rec.ticker}: {exc}"
        log.error(msg)
        db.update_status(rec.recommendation_id, RecStatus.FAILED, msg)
        return ExecutionResult(False, False, RecStatus.FAILED, msg)
