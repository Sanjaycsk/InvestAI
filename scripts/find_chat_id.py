"""
One-shot helper: print the chat id(s) that have messaged your bot.

Run this where the Telegram Bot API is reachable (e.g. your VPS — many home
ISPs block api.telegram.org). Steps:
    1) In Telegram, open your bot and send it any message (e.g. "hi").
    2) python -m scripts.find_chat_id
    3) Copy the printed CHAT_ID into config/.env as TELEGRAM_CHAT_ID.

Needs only TELEGRAM_BOT_TOKEN set in config/.env.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from config import config  # noqa: E402


def main() -> None:
    token = config.TELEGRAM_BOT_TOKEN.strip()
    if not token:
        print("No TELEGRAM_BOT_TOKEN in config/.env — add it first.")
        return

    base = f"https://api.telegram.org/bot{token}"
    try:
        me = requests.get(f"{base}/getMe", timeout=20).json()
    except requests.exceptions.RequestException as exc:
        print(f"Could not reach api.telegram.org ({type(exc).__name__}).")
        print("If you're on a home connection, your ISP may block the Bot API — "
              "run this on your VPS or via a VPN.")
        return

    if not me.get("ok"):
        print("Token rejected by Telegram:", me)
        return
    print("Bot OK:", me["result"].get("username"))

    updates = requests.get(f"{base}/getUpdates", timeout=20).json()
    seen: dict = {}
    for upd in updates.get("result", []):
        msg = upd.get("message") or upd.get("edited_message") or upd.get("channel_post") or {}
        chat = msg.get("chat", {})
        if chat:
            seen[chat["id"]] = (chat.get("type"), chat.get("first_name") or chat.get("title"))

    if not seen:
        print("No chats yet. Open your bot in Telegram, send it a message, then re-run.")
        return
    for cid, (ctype, name) in seen.items():
        print(f"CHAT_ID: {cid}  | type: {ctype} | name: {name}")
    print("\nCopy the CHAT_ID above into config/.env as TELEGRAM_CHAT_ID.")


if __name__ == "__main__":
    main()
