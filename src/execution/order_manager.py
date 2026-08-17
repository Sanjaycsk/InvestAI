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
    if _side_for(rec.recommended_action) == "BUY":
        stops_today = db.count_stop_losses_today()
        if stops_today >= config.MAX_DAILY_STOP_LOSSES:
            return False, (
                f"circuit breaker: {stops_today} stop-loss(es) already fired today "
                f"(cap {config.MAX_DAILY_STOP_LOSSES}) — no new BUYs until tomorrow."
            )
    return True, "ok"


def check_stop_loss(rec: Recommendation, live_price: float) -> bool:
    """True if a held BUY/ACCUMULATE idea has breached its stop-loss."""
    return (
        rec.stop_loss_price is not None
        and _side_for(rec.recommended_action) == "BUY"
        and live_price <= rec.stop_loss_price
    )


def record_stop_loss(rec: Recommendation, live_price: float) -> None:
    """
    Log a stop-loss trip to the audit trail (feeds the daily circuit breaker
    in `_guardrails_ok`). Call this from the position-monitoring loop when
    `check_stop_loss` is True; actually exiting the position is a separate,
    explicit SELL recommendation through the normal approval flow — this
    function only records that the stop fired, it does not place an order.
    """
    detail = (
        f"{rec.ticker}: live ₹{live_price:,.2f} <= stop ₹{rec.stop_loss_price:,.2f} "
        f"(entry ₹{rec.price_at_analysis:,.2f})."
    )
    log.warning("STOP-LOSS: %s", detail)
    db.log_event("STOPPED_OUT", rec.recommendation_id, detail)


def execute_recommendation(
    rec: Recommendation,
    *,
    kite: KiteClient | None = None,
) -> ExecutionResult:
    """
    Called by the bot AFTER the human approves. Re-validates everything from
    scratch — never trusts that approval implies safety, and never trusts the
    caller's word that approval happened at all: the stored status is re-read
    here rather than taken from the passed-in object, so a stale in-memory
    Recommendation cannot be replayed into an order.
    """
    stored = db.get_recommendation(rec.recommendation_id)
    if stored is None or stored.status is not RecStatus.APPROVED:
        found = "unknown" if stored is None else stored.status.value
        msg = f"refusing to execute {rec.ticker}: stored status is {found}, not APPROVED."
        log.warning(msg)
        return ExecutionResult(False, False, RecStatus.REJECTED, msg)

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
