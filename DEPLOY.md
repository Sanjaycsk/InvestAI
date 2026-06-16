# Deploying the Discovery bot to a VPS

You only need this because your home ISP **blocks the Telegram Bot API**
(`api.telegram.org` is DNS-poisoned + SNI-reset on many Indian ISPs). A VPS sits
on a datacenter network where Telegram is reachable.

This guide covers the **discovery-only** setup: pull YouTube + blog RSS → rank
stock ideas → push to Telegram, on a daily schedule. The always-on approval bot
(`scripts/run_bot.py`) is **not** needed yet — that's only for the later Zerodha
order-approval phase.

---

## The one trade-off to know

| Service | Home IP | Datacenter / VPS IP |
|---|---|---|
| Telegram Bot API | ❌ blocked by your ISP | ✅ works |
| YouTube transcripts | ✅ works | ⚠️ often IP-blocked |

So on a VPS, Telegram works but YouTube transcript fetching **may** get blocked.
Mitigations, in order of preference:

1. **Just try it first.** Not every datacenter range is blocked by YouTube. Run
   one discovery and check how many transcripts came back. News/blog RSS always
   works regardless, so you still get ideas even if YouTube returns 0.
2. **Add a proxy** if YouTube blocks you: set `YOUTUBE_PROXY_URL` in `.env` to a
   residential/rotating proxy (e.g. Webshare). Already wired in — no code change.
3. **A small Mumbai-region VPS** tends to fare better for both than a US/EU one.

Provider suggestions: Hetzner / DigitalOcean / Linode (~₹350–500/mo), or Oracle
Cloud "Always Free" (no cost). Pick Ubuntu 22.04+.

---

## Steps (on a fresh Ubuntu VPS)

```bash
# 1) System deps
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git

# 2) Get the code onto the VPS
#    Option A: git clone <your repo>      (if you push it to GitHub — keep .env OUT)
#    Option B: scp the folder up from your PC:
#       scp -r "investment-research-system" user@VPS_IP:~/
cd ~/investment-research-system

# 3) venv + deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4) Config. DO NOT copy your local .env with secrets over git — recreate it here.
cp config/.env.example config/.env
nano config/.env
#    Set at minimum:
#      DISCOVERY_DRY_RUN=False
#      TELEGRAM_BOT_TOKEN=...      (from @BotFather)
#      TELEGRAM_CHAT_ID=           (leave blank — next step finds it)
#    channels.json / feeds.json copy over as-is.

# 5) Find your chat id (Telegram is reachable here, unlike at home).
#    First: open your bot in Telegram and send it any message.
python -m scripts.find_chat_id
#    Copy the printed CHAT_ID into config/.env -> TELEGRAM_CHAT_ID

# 6) First real run — delivers to your Telegram.
python -m scripts.discover
#    Check the logs: "Collected N transcripts" tells you if YouTube worked.
#    If N=0 and you want YouTube, set YOUTUBE_PROXY_URL in .env and re-run.
```

---

## Schedule it daily (cron)

Run once every morning, e.g. 08:30 IST. `crontab -e`:

```cron
30 8 * * *  cd /home/USER/investment-research-system && /home/USER/investment-research-system/.venv/bin/python -m scripts.discover >> /home/USER/discover.log 2>&1
```

(Adjust the path/username. The VPS clock may be UTC — `08:30 IST` is `03:00 UTC`,
so use `0 3 * * *` if the server runs UTC.)

That's it — ranked stock ideas land in your Telegram every morning.

---

## Later: Zerodha + approval buttons

When you add live broker integration, `scripts/run_bot.py` becomes the always-on
process that listens for your ✅/❌ taps. Keep it alive with systemd:

```ini
# /etc/systemd/system/invest-bot.service
[Unit]
Description=Investment approval bot
After=network-online.target

[Service]
WorkingDirectory=/home/USER/investment-research-system
ExecStart=/home/USER/investment-research-system/.venv/bin/python -m scripts.run_bot
Restart=always
User=USER

[Install]
WantedBy=multi-user.target
```

`sudo systemctl enable --now invest-bot`. Run `security-review` before enabling
any live order execution.
