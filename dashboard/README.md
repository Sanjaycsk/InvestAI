# InvestAI Dashboard 📈

A mobile-first **PWA** that shows today's InvestAI calls at a glance. Reads
**live from Notion** (the same Recommendations + Daily Review databases the
daily agent writes to). Gated by a **shared passcode**.

Two tabs: **📊 Today** and **🔍 Look up a stock**.

**Today** shows:

- **Entry-window banner** — flags whether you're inside the 9:15–11:00 AM IST buying
  window or looking at a stale 8:30 AM verdict later in the day
- **Error management** — what the model has gotten wrong before and the standing rules
  it's applying today, shown *before* the calls themselves so you know what to
  double-check
- **Strategy P&L (paper)** — return if you followed every graded BUY (and shorted SELLs)
- **Accuracy** (latest) + **7-day average** + 🔥 streak
- **Self-rating** and **best-read stock**
- **Saved by selling early** — cumulative management alpha from the 15:00 de-risk exits
- **Beating the market?** — paper return vs the real Nifty 50 (or the GROWWN200 proxy on
  older days), on the same days the model made a call
- **By sector** — per-sector Bullish/Bearish/Mixed mood, collapsible
- **Buy today** / **Sell-or-avoid today** lists, each row with a **"Through the day"
  timeline** (10 AM status → 3 PM action) once the intraday runs have annotated it, and an
  **"you own this"** badge if you've flagged that ticker as a holding (per-device toggle,
  stored only in your browser — no accounts)
- **🛡️ Sold before the close** — the day's Run 3 de-risk exits
- **Yesterday's calls** with graded outcomes (✓ / ✗) and actual move %

**Look up a stock** — pick any of the 26 names and see: today's call and full reasoning,
**yesterday's call and whether it worked**, that stock's **own accuracy track record**
over the whole run (not just the system-wide number), and what the six coffee-shop
friends think of it (folded in here instead of living on its own tab). "Browse a past
day" (7-day date filter) and "Yesterday's scorecard" are collapsible dropdowns here too.

> An experimental trend-forecasting model (`backtest/train_ml_trend.py` + ARIMA/LSTM
> variants) was tried and evaluated honestly on walk-forward accuracy — none beat a naive
> baseline, so none of it is surfaced in the UI. The scripts and data stay in the repo as
> a research record.

---

## 1. One-time Notion setup

1. Go to <https://www.notion.so/my-integrations> → **New integration**
   (internal). Copy the **Internal Integration Secret** (`secret_…`).
2. Open the **INVESTAI** page in Notion → **•••** → **Connections** →
   add your integration. (This grants it read access to both databases.)

The data-source IDs are already known and pre-filled in
`.env.local.example`:

| Database        | Data source ID                          |
| --------------- | --------------------------------------- |
| Recommendations | `8f225b65-31b3-4f12-9700-34e7a2a459e0`  |
| Daily Review    | `a69929f7-e386-4d9a-bf60-16f468dd4325`  |
| Coffee Shop     | `fee73e14-f1c4-48b7-a285-c319ccb781b7`  |

The Coffee Shop id has a built-in fallback in `lib/notion.ts`, so setting
`NOTION_COFFEESHOP_DS` is optional. (A data-source id isn't a secret — only
`NOTION_TOKEN` is.)

**Daily Review also needs two new Number columns** (added 2026-08-11, not yet in every
workspace): **Nifty Close** and **Nifty Move %**, populated by Run 1 from the real Nifty
50 index. Without them the dashboard just falls back to the GROWWN200 proxy for the
"Beating the market?" comparison — nothing breaks, it just upgrades automatically once
they're added and the agent starts filling them in.

## 2. Configure environment

```bash
cp .env.local.example .env.local
```

Fill in:

- `NOTION_TOKEN` — the `secret_…` from step 1
- `DASHBOARD_PASSCODE` — the password you'll share with trusted people
- `DASHBOARD_SESSION_SECRET` — a long random string:
  ```bash
  node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
  ```

## 3. Run locally

```bash
npm install
npm run dev
```

Open <http://localhost:3000>, enter the passcode.

## 4. Deploy to Vercel (free)

```bash
npm i -g vercel        # if you don't have it
vercel                 # link/create the project
vercel --prod          # deploy
```

Then in the Vercel dashboard → **Settings → Environment Variables**, add the
same four variables from `.env.local`. Redeploy.

You'll get a URL like `https://investai-xxxx.vercel.app`.

## 5. Install on your phone (home-screen app)

- **iPhone (Safari):** open the URL → Share → **Add to Home Screen**
- **Android (Chrome):** open the URL → menu → **Install app**

It launches full-screen with its own icon — feels native, no App Store.

---

## How it works

```
Phone (PWA)  →  Next.js server (Vercel)  →  Notion REST API
                       │                        ├─ Recommendations
                  passcode gate                 └─ Daily Review
```

- `lib/notion.ts` — queries the Notion data sources, paginates, computes KPIs (incl.
  management alpha, the market-alpha benchmark comparison, per-ticker accuracy stats, and
  the error-management summary). The Notion token lives only server-side; the browser
  never sees it.
- `middleware.ts` + `app/api/login` — passcode → session cookie.
- `app/page.tsx` (Today) + `app/lookup/page.tsx` (Look up a stock) — server components,
  `force-dynamic` so every load is fresh; `app/TabNav.tsx` switches between them.
- `app/StockLookup.tsx` — the stock picker + its detail (today's call, yesterday's call,
  track record, coffee-shop opinions), used only on the lookup tab.
- `app/StockDetail.tsx` — the per-factor reasoning drill-down, shared by both tabs.

## "Today" / "Yesterday" logic

The dashboard does **not** rely on the device clock. It reads the two most
recent distinct `Date` values present in Recommendations: the newest is
"today", the one before it is "yesterday". So it always shows the latest run,
even before/after the 08:30 IST agent run.

## Upgrading the sign-in later

Today it's a shared passcode. To move to per-person Google sign-in with an
email allowlist, swap `middleware.ts` + `app/api/login` for Auth.js
(NextAuth) with a Google provider and an `allowedEmails` check. The rest of
the app is unchanged.
