"""
Telegram integration — two distinct jobs (see the README's two-process model):

  send_summary(...)   one-shot. Called by the daily analysis job. Posts the
                      brief and attaches an approval button to each actionable
                      recommendation. Falls back to console print if no token.

  run_bot()           long-running. The approval LISTENER. Handles button
                      presses, validates them, and routes APPROVE -> execution.

python-telegram-bot v20+ is async, so both paths are coroutines. callback_data
encodes (action, recommendation_id, approval_token) so a press can be verified
against the stored recommendation — a forged or stale button does nothing.
"""
from __future__ import annotations

import logging

from config import config
from src.analysis.schema import Recommendation, RecStatus
from src.notifier.formatter import actionable, format_daily_summary
from src.store import db

log = logging.getLogger(__name__)

_CB_SEP = "|"  # callback_data: "APPROVE|<rec_id>|<token>"


def _buttons_for(rec: Recommendation):
    """Inline keyboard: Approve / Reject for one recommendation."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    approve = f"APPROVE{_CB_SEP}{rec.recommendation_id}{_CB_SEP}{rec.approval_token}"
    reject = f"REJECT{_CB_SEP}{rec.recommendation_id}{_CB_SEP}{rec.approval_token}"
    label = f"{rec.recommended_action.value} {rec.suggested_qty} {rec.ticker}"
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ Approve {label}", callback_data=approve),
        InlineKeyboardButton("❌ Reject", callback_data=reject),
    ]])


async def send_summary(
    summary_text: str,
    actionable_recs: list[Recommendation] | None = None,
) -> None:
    """Post the brief + one message-with-buttons per actionable recommendation."""
    actionable_recs = actionable_recs or []

    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        # No credentials yet -> behave as a "read-only" notifier on the console.
        print("\n=== [Telegram disabled — console preview] ===")
        print(summary_text.replace("<b>", "").replace("</b>", "")
              .replace("<u>", "").replace("</u>", "").replace("<i>", "")
              .replace("</i>", "").replace("&amp;", "&"))
        for r in actionable_recs:
            print(f"  [button] APPROVE {r.recommended_action.value} "
                  f"{r.suggested_qty} {r.ticker}  (id={r.recommendation_id[:8]})")
        print("=== end preview ===\n")
        return

    from telegram import Bot
    from telegram.constants import ParseMode

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    await bot.send_message(
        chat_id=config.TELEGRAM_CHAT_ID, text=summary_text,
        parse_mode=ParseMode.HTML,
    )
    for rec in actionable_recs:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=f"Action for <b>{rec.ticker}</b>: {rec.rationale}",
            parse_mode=ParseMode.HTML,
            reply_markup=_buttons_for(rec),
        )


async def _on_button(update, context) -> None:  # noqa: ANN001 (telegram types)
    """CallbackQueryHandler: validate the press, then approve/reject."""
    query = update.callback_query
    await query.answer()

    # 1) Lock to the owner's chat.
    if str(query.message.chat_id) != str(config.TELEGRAM_CHAT_ID):
        await query.edit_message_text("Unauthorized.")
        return

    try:
        action, rec_id, token = query.data.split(_CB_SEP, 2)
    except ValueError:
        await query.edit_message_text("Malformed action.")
        return

    rec = db.get_recommendation(rec_id)
    # 2) Validate existence + token + freshness + not-already-handled.
    if rec is None or token != rec.approval_token:
        await query.edit_message_text("This action is invalid or has expired.")
        return
    if rec.status is not RecStatus.PENDING:
        await query.edit_message_text(f"Already handled: {rec.status.value}.")
        return
    if rec.is_expired():
        db.update_status(rec_id, RecStatus.EXPIRED, "expired before approval")
        await query.edit_message_text("⌛ Approval window expired.")
        return

    if action == "REJECT":
        db.update_status(rec_id, RecStatus.REJECTED, "rejected by user")
        await query.edit_message_text(f"❌ Rejected {rec.ticker}.")
        return

    # 3) APPROVE -> hand to the execution layer (which re-checks everything).
    db.update_status(rec_id, RecStatus.APPROVED, "approved by user")
    from src.execution.order_manager import execute_recommendation

    result = execute_recommendation(rec)
    await query.edit_message_text(result.message)


def run_bot() -> None:
    """Start the long-running approval listener (blocking)."""
    if not config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing; set it in config/.env.")
    from telegram.ext import ApplicationBuilder, CallbackQueryHandler

    db.init_db()
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(_on_button))
    log.info("Approval bot started. %s", config.safety_banner())
    app.run_polling()
