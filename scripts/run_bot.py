"""
PROCESS B — the long-running Telegram approval listener.

This must stay running for the approval buttons to work (the daily summary is a
one-shot send; this is what *listens* for your taps). Keep it alive with your
process manager of choice (NSSM/Task Scheduler on Windows, systemd/pm2 on Linux)
once you pick a deployment target.

Run from the project root:
    python -m scripts.run_bot
"""
from __future__ import annotations

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

from src.notifier.telegram_bot import run_bot  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

if __name__ == "__main__":
    run_bot()
