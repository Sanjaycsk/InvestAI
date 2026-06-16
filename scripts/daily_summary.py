"""
PROCESS A — the daily analysis job (Phase 1, runnable now).

Pipeline:
    holdings (Kite/DUMMY) -> price history -> 200-DMA assessment
        -> persist recommendations -> format brief -> send (or console preview)

Run from the project root:
    python -m scripts.daily_summary
or:
    python scripts/daily_summary.py

With DUMMY_MODE=True (the default) this runs fully offline against a sample
portfolio and synthetic price history — no API keys required.
"""
from __future__ import annotations

import asyncio
import logging
import pathlib
import sys

# Make `config` and `src` importable regardless of how the script is launched.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# Windows consoles default to cp1252; force UTF-8 so emoji/dashes don't crash print().
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import config  # noqa: E402
from src.analysis.technical import assess_trend  # noqa: E402
from src.data.kite_client import KiteClient  # noqa: E402
from src.data.price_data import get_close_history  # noqa: E402
from src.notifier.formatter import actionable, format_daily_summary  # noqa: E402
from src.notifier.telegram_bot import send_summary  # noqa: E402
from src.store import db  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("daily_summary")


def review_portfolio() -> list:
    """Assess every holding against its 200-DMA; return Recommendations."""
    kite = KiteClient()
    holdings = kite.get_holdings()
    recs = []
    for h in holdings:
        closes = get_close_history(h.symbol, h.exchange, days=config.SMA_WINDOW + 60)
        if closes is None or closes.empty:
            log.warning("No price history for %s — skipping.", h.symbol)
            continue
        rec = assess_trend(
            h.symbol, closes, exchange=h.exchange, held_qty=h.quantity
        )
        recs.append(rec)
    return recs


async def main() -> None:
    log.info(config.safety_banner())
    db.init_db()

    portfolio_recs = review_portfolio()

    # Persist with an approval TTL so any buttons can't be replayed later.
    for rec in portfolio_recs:
        rec.with_ttl(config.APPROVAL_TTL_MINUTES)
        db.save_recommendation(rec)

    # Phase 2 will populate discovery_recs from transcripts + news + Claude.
    discovery_recs: list = []

    summary = format_daily_summary(portfolio_recs, discovery_recs)
    await send_summary(summary, actionable(portfolio_recs + discovery_recs))
    log.info("Daily summary complete: %d holdings assessed.", len(portfolio_recs))


if __name__ == "__main__":
    asyncio.run(main())
