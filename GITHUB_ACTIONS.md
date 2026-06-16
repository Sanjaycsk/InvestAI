# Running on GitHub Actions (no VPN, no VPS, free)

Your home ISP blocks the Telegram Bot API. GitHub's servers don't — so we let
GitHub run the discovery pipeline on a daily schedule and deliver to Telegram.

**What works here:** Telegram delivery ✅, news/blog RSS ✅.
**What may not:** YouTube transcripts — GitHub's IPs are often blocked by
YouTube. You still get news-based ideas; see "YouTube" at the bottom to fix it.

Two workflows are already in `.github/workflows/`:
- `discover.yml` — the daily run (+ a manual "Run workflow" button)
- `find-chat-id.yml` — one-time helper to get your Telegram chat id

---

## One-time setup

### 1. Put the code on GitHub
Make a **private** repo (keep it private — it's your trading research).

```bash
# from the investment-research-system folder
git init
git add .
git commit -m "Investment discovery bot"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

`config/.env` is gitignored, so your token/secrets are **not** uploaded — good.
On GitHub they come from repository *Secrets* instead (next step).

### 2. Add your secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret**.
Add:

| Secret name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | your @BotFather token |
| `TELEGRAM_CHAT_ID`   | leave for now — step 3 finds it |

(Optional later: `YOUTUBE_PROXY_URL`, `ANTHROPIC_API_KEY`.)

### 3. Find your chat id
1. In Telegram, open your bot and send it any message ("hi").
2. Repo → **Actions** tab → **Find Telegram Chat ID** → **Run workflow**.
3. Open the finished run's logs — it prints `CHAT_ID: 123456789`.
4. Add that as the `TELEGRAM_CHAT_ID` secret (Settings → Secrets, as above).

### 4. Test delivery
Actions tab → **Daily Stock Discovery** → **Run workflow**. Within a minute or
two you should get the ranked ideas in Telegram. Done.

After that it runs automatically every day at 03:00 UTC (08:30 IST). Change the
`cron:` line in `discover.yml` to retime it.

---

## Notes

- **Scheduled runs pause after 60 days of repo inactivity** (a GitHub rule). Any
  push, or a manual run, resets the clock.
- **Schedule isn't second-precise** — GitHub may start it a few minutes late
  under load. Fine for a daily brief.

## YouTube on GitHub Actions

GitHub's datacenter IPs are frequently blocked by YouTube, so transcript fetches
may return 0. Check a run's log line `Collected N transcripts`. If N=0 and you
want YouTube ideas (not just news), add a residential proxy:

1. Get a proxy (e.g. Webshare has a small free tier) → URL like
   `http://user:pass@host:port`.
2. Add it as the `YOUTUBE_PROXY_URL` secret. It's already wired into the code.

News/blog RSS works regardless, so the bot is useful even with YouTube off.
