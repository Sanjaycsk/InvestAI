"""
DISCOVERY pipeline entrypoint — the focus of this build.

    trusted YouTube channels ─┐
                              ├─▶ extract tickers + sentiment ─▶ Claude/heuristic
    financial-blog RSS feeds ─┘                │
                                               ▼
                              ranked stock ideas ─▶ Telegram

Run from the project root:
    python -m scripts.discover

Try it with zero keys / offline first:
    $env:DISCOVERY_DRY_RUN = "True"; python -m scripts.discover
This uses bundled sample transcripts + articles and the heuristic synthesizer,
so you see real output before adding ANTHROPIC_API_KEY / Telegram credentials.
"""
from __future__ import annotations

import asyncio
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# Windows consoles default to cp1252; force UTF-8 so emoji/dashes don't crash print().
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import config  # noqa: E402
from src.analysis.synthesizer import synthesize  # noqa: E402
from src.data.news_ingest import fetch_recent_articles  # noqa: E402
from src.data.youtube_ingest import collect_transcripts  # noqa: E402
from src.notifier.formatter import format_discovery  # noqa: E402
from src.notifier.telegram_bot import send_summary  # noqa: E402
from src.store import db  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("discover")


async def main() -> None:
    mode = "DRY-RUN (sample data)" if config.DISCOVERY_DRY_RUN else "LIVE"
    engine = "Claude" if config.ANTHROPIC_API_KEY else "heuristic"
    log.info("Discovery starting — %s, synthesis via %s.", mode, engine)
    db.init_db()

    # 1) Read YouTube + financial blogs.
    transcripts = collect_transcripts()
    articles = fetch_recent_articles()
    log.info("Ingested %d transcripts, %d articles.", len(transcripts), len(articles))

    # 2) Suggest stocks.
    recs = synthesize(transcripts, articles)
    for rec in recs:
        db.save_recommendation(rec)
    log.info("Synthesized %d ticker verdict(s).", len(recs))

    # 3) Send the ranked ideas to Telegram (console preview if no token).
    summary = format_discovery(recs, top_n=config.TOP_N_SUGGESTIONS)
    await send_summary(summary)
    log.info("Discovery complete.")


if __name__ == "__main__":
    asyncio.run(main())
