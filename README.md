# Investment Research & Management System

A modular, **human-in-the-loop** assistant for mid-to-long-term equity holding.
It reviews your portfolio, synthesizes expert opinion + news, and proposes
actions — but **you** approve every trade. Nothing executes automatically.

> ⚠️ **Safety first.** Two independent switches gate any real order:
> `DUMMY_MODE` (default **True**) and `EXECUTION_ENABLED` (default **False**).
> Both must be flipped *and* per-trade guardrails must pass before a single
> rupee moves. Leave them at defaults until you've watched the system's
> decisions for several days.

---

## The two-process model

The approval *buttons* require a process that is always listening. So the
system runs as two cooperating processes that share a SQLite state DB:

| Process | File | Cadence | Job |
|---|---|---|---|
| **A — Analysis job** | `scripts/daily_summary.py` | once daily (cron/scheduler) | pull data → analyze → save recommendations → send brief |
| **B — Approval bot** | `scripts/run_bot.py` | always-on | listen for your button taps → validate → route to execution |

```
holdings ─▶ price history ─▶ 200-DMA ─▶ Recommendation(schema)
                                              │
                                        [SQLite state DB] ◀── audit log
                                              │
                       Telegram brief + ✅/❌ buttons  (Process A)
                                              │  (you tap)
                       validate token+chat+TTL+guardrails  (Process B)
                                              │
                    DUMMY → simulate & log   |   LIVE → Kite order
```

The layers never import each other's logic — they agree only on the
`Recommendation` schema (`src/analysis/schema.py`). That's what keeps it modular.

---

## Layout

```
config/        .env (secrets) · .env.example · channels.json · feeds.json · config.py
src/data/      kite_client · price_data (200-DMA) · youtube_ingest · news_ingest (RSS)
src/analysis/  schema (the contract) · technical (200-DMA) · tickers · synthesizer (Claude)
src/notifier/  formatter · telegram_bot (summary + approval listener)
src/execution/ order_manager (THE gate — disabled by default)
src/store/     db (SQLite state + append-only audit log)
scripts/       daily_summary.py (portfolio) · discover.py (YouTube+blogs) · run_bot.py
tests/         test_technical.py · test_discovery.py
```

---

## Quick start

```powershell
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config\.env.example config\.env   # then fill in values locally

# Phase 1 — portfolio review (offline, DUMMY_MODE):
python -m scripts.daily_summary

# Discovery — YouTube + blogs -> stock ideas -> Telegram.
# Try it offline first with zero keys (sample data + heuristic synthesis):
$env:DISCOVERY_DRY_RUN = "True"; python -m scripts.discover

pytest -q
```

For a *live* discovery run: set `DISCOVERY_DRY_RUN=False`, add your real channels
to `config/channels.json`, optionally add `ANTHROPIC_API_KEY` (Claude synthesis;
without it a transparent heuristic is used), and `TELEGRAM_BOT_TOKEN` +
`TELEGRAM_CHAT_ID` to deliver instead of console-preview.

With no Telegram token set, the brief prints to your console (read-only
preview). Add `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` to deliver it for real.

---

## Build phases

- **Phase 1 (built):** portfolio review · 200-DMA red/green flags · daily brief ·
  approval-button plumbing · simulated execution · audit log.
- **Discovery (built):** YouTube transcript ingestion (RSS video discovery +
  `youtube-transcript-api`) · financial-blog/news via **RSS feeds** · ticker
  recognition · **Claude synthesis** (heuristic fallback) →
  `{ticker, sentiment_score, rationale, recommended_action}` · ranked ideas to
  Telegram. Entry point: `scripts/discover.py`.
- **Phase 3 (gated):** flip the toggles, enable live Kite orders behind the
  guardrails. Run `security-review` before this phase.

---

## Operational notes

- **Kite token expires daily (~06:00 IST).** No headless official refresh — run
  the login flow each morning (`kite_client.print_login_instructions()`),
  optionally semi-automated with `pyotp` + `KITE_TOTP_SECRET`.
- **YouTube transcripts prefer a residential IP** (datacenter IPs get blocked) —
  a factor when you choose where to deploy.
- **Deployment is deliberately deferred.** The two-process split is host-neutral,
  so it lifts to a Mumbai-region VPS or a home always-on machine with no code
  change. Keep Process B alive with a process manager (Task Scheduler/NSSM on
  Windows; systemd/pm2 on Linux).

## Guardrails (config/.env)

`MAX_ORDER_VALUE_INR` · `MAX_DAILY_TRADES` · `APPROVAL_TTL_MINUTES` — enforced in
`order_manager` on every approval, after a fresh live-price re-check.
