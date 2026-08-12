# InvestAI — Self-Grading Stock Research Agent

A multi-run, **autonomous** equity-research agent built on **Claude (Anthropic)**. On
every trading day it issues a **BUY / HOLD / SELL** verdict on a fixed 26-instrument NSE
watchlist before the open, re-checks that thesis as the day plays out, and **grades its
own previous calls against what actually happened** — with every decision logged and
auditable.

> 📊 **Trust comes from accountability, not "the AI said so."** Every call is graded
> against reality, logged with its reasoning, and the method is version-controlled
> and open to inspection. A human makes every actual decision — the agent **never trades.**

📄 **Shareable explainer:** [`docs/how-it-works.html`](docs/how-it-works.html) ·
📐 **Architecture diagram:** [`docs/architecture-diagram.svg`](docs/architecture-diagram.svg) ·
🧠 **Agent definition (source of truth):** [`AGENT.md`](AGENT.md)

---

## The trading day (three runs)

All times **IST**, **weekdays only** — weekends and NSE holidays are skipped automatically.
The rhythm is **anticipate → confirm → de-risk**:

| Run | Time | What it does |
| --- | --- | --- |
| **1 · Pre-market** | 08:30 | Full analysis. Grades yesterday, learns, then scores all 26 and logs today's **BUY/HOLD/SELL**. This is the **verdict of record**. |
| **2 · Confirm** | 10:00 | Light delta-check ~30 min after the open: does the morning thesis still hold? Folds in a friend's Notion notes. Annotates only. |
| **3 · De-risk** | 15:00 | Light check ~30 min before the close: exit/trim only a position whose thesis has **materially broken**, so an overnight gap can't hurt. |

**The verdict is frozen after Run 1.** Runs 2 and 3 never change it — they only add their
own intraday annotations. That keeps the headline accuracy honest:

- **Forecast accuracy** is graded against **Run 1's verdict only** — the comparable 45-day stat.
- **Management alpha** is tracked **separately**: did the 15:00 de-risk exits actually save
  money vs holding to the close? This answers "is intraday management earning its keep?"
  without contaminating the forecast score.

### Run 1, in four steps
1. **Review & grade yesterday** — read each pending call's actual close, mark it
   Correct/Wrong, compute accuracy % and a self-rating /100, grade any prior-day de-risk
   exits into *management alpha*, and log the real Nifty 50 move for the day alongside it
   (so accuracy can be checked against the market, not just against zero).
2. **Learn** — read recent daily reviews and apply their lessons as standing rules for
   today. Each lesson is tagged to the ticker it's about, so a name with repeat mistakes
   gets flagged specifically instead of being lost in one generic pool (genuine
   market-driven misses are left alone, and the standing rule set is capped and
   consolidated once it gets too long).
3. **Analyze today** — first reads the overall market regime (bullish / bearish /
   sideways) and adjusts the playbook accordingly, then scores six factors per
   instrument, weighted by instrument type. A boundary-case call (near a category
   cutoff, or in a historically overconfident band) gets a quick bull-vs-bear
   self-check before the score is finalized.
4. **Decide & log** — map the composite score to a category and verdict, write it (with
   per-factor reasoning) to the Notion audit database, and freeze it for the day.

### Scoring (equities)
Fundamental 30 · Technical 20 · Valuation 20 · Macro 15 · Sentiment 5 · Risk 10 (Risk
can veto). Commodity & index ETFs use type-specific weights. Composite 0–100 →
Strong Buy (>80) / Buy on Dip (70–80) / Watchlist (60–70) / Hold (45–60) / Avoid·Sell (<45).

---

## ☕ The coffee-shop panel (perspective layer)

Alongside each run, six recurring investor **characters** debate the day's BUY shortlist —
like friends in a coffee shop — and each records what *they* personally would do. They
revisit the same shortlist three times a day (pre-market, after the open, before the
close), so you can watch opinions shift. It's **perspective only — it never changes the
verdict.** On the dashboard this now shows up inside each stock's own lookup detail
(pick the stock, then see what the friends think of it) rather than as a separate tab.

🧓 Vihaan (buys quality, holds for years) · ⚡ Aarav (rides short-term momentum) ·
👀 Rohan (waits for a dip) · 💼 Meera (safe, set-and-forget SIPs) ·
🪙 Neel (small budget, cheap ETFs) · 🎲 Diya (small risky punts).

---

## Architecture

Cooperating environments, each chosen for where its data is actually reachable:

```
YouTube ─▶ Home PC (residential) ─▶ Public GitHub ─┐
                                                    ▼
  Friend's notes (Notion) ─┐         CLAUDE CLOUD ROUTINES  ⇄  Notion (audit memory)
                           ├──────▶   Run 1 · Run 2 · Run 3        │  (each hosts a coffee debate)
  Live Web ────────────────┘        (anticipate·confirm·de-risk)   ▼
                                                              Dashboard (PWA) ─▶ You (decide)
```

- **Home PC** — fetches transcripts from trusted YouTube channels (YouTube only loads
  from a residential IP). Companion repo: **[youtube-stock-reader](https://github.com/Sanjaycsk/youtube-stock-reader)**.
- **Public GitHub** — holds the transcript data feed + the version-controlled agent prompts.
- **Anthropic cloud** — three scheduled Claude routines (Run 1 / 2 / 3); each one also
  hosts its coffee-shop debate as a final step. They research the live web, analyze, and
  grade. Model: `Claude Sonnet 4.6`.
- **Notion** — the permanent, human-readable audit trail (`Recommendations`, `Daily Review`,
  `Coffee Shop`, plus a friend-input `Inputs` table).
- **Dashboard** — a mobile PWA (Vercel) that reads live from Notion. See [`dashboard/`](dashboard/).

See [`AGENT.md`](AGENT.md) for every routine ID, schema, and the exact wiring.

---

## The 26 instruments (fixed universe, NSE)

**Equities (23):** RELIANCE, HDFCBANK, ICICIBANK, TCS, INFY, BHARTIARTL, ITC,
HINDUNILVR, LT, MARUTI, SUNPHARMA, TATASTEEL, SBIN, FEDERALBNK, SUZLON, TATAPOWER,
WAAREEENER, NTPC, ADANIENT, BEL, BHEL, VEDL, BPCL
**Index ETF (1):** GROWWN200 (Groww Nifty 200 ETF — market proxy)
**Commodity ETFs (2):** GOLDBEES (Gold), SILVERBEES (Silver)

The dashboard's "Beating the market?" panel compares paper performance against the
**real Nifty 50 index** (`benchmarks.NIFTY50` in the price feed) where it's been logged,
falling back to GROWWN200 (a Nifty 200 ETF, also in the 26) on older days.

---

## Why it can be trusted

- **Held accountable daily** — every call is checked against the real close and scored;
  wins *and* losses are recorded.
- **Prediction kept separate from management** — the morning verdict is frozen and graded
  on its own; intraday exits are scored as a separate "management alpha" line, so the
  accuracy number can't be quietly rewritten with hindsight.
- **Fully auditable** — each recommendation is stored with its reasoning, sources, and a
  timestamp; nothing is ephemeral.
- **Learns from mistakes** — errors are classified (fixable vs market), tagged to the
  ticker they're about, and fixable ones become standing rules applied the next day.
- **Checked against the market, not just itself** — paper performance is compared to the
  real Nifty 50, so "accuracy" can't just mean "the whole market went up that day."
- **No black box** — the agents' exact instructions are version-controlled here.
- **Human-in-the-loop** — it only suggests; a person decides. It never auto-trades.

### Honest limits
Markets are uncertain; it uses only public data (no insider/private feeds); the intraday
runs are lightweight checks, not a tick-by-tick trading system; and it is
**research/education only — not financial advice.**

---

## Repository layout

```
AGENT.md                     source-of-truth for the live cloud routines (all 6)
agent/routine_prompt.md      the exact Run-1 prompt + the sibling routine list
docs/how-it-works.html       shareable, non-technical explainer
docs/architecture-diagram.svg  editable vector diagram (Figma-importable)
dashboard/                   mobile PWA (Next.js) — reads live from Notion
backtest/                    experimental trend-forecasting research (GBM/ARIMA/LSTM) —
                              honest walk-forward results, none wired into the live agent
config/  src/  scripts/  tests/   original local Python toolkit (200-DMA, RSS,
                                   discovery, simulated execution) — the prototype
                                   this evolved from; kept for local/offline use.
```

> The original Python pipeline (the earlier discovery/portfolio prototype) still runs
> locally and offline, but the **live system is the Claude cloud routines** described above.

---

## Status

The agent has been live for **45+ days**; the dashboard's stock-lookup tab now shows each
name's own track record over that whole run, not just the system-wide number. Telegram
delivery of the daily brief is deferred; results land in the Notion audit databases, the
dashboard, and each routine's run history.

**2026-08-11 v2** — a round of changes based on live feedback and a look at
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) (see
`AGENT.md` for the detailed rationale of what did/didn't transfer):
- Real Nifty 50 benchmark comparison (was GROWWN200-proxy only)
- Market-regime awareness (bullish/bearish/sideways) feeding into Step 2
- Ticker-tagged lesson memory + a deterministic cap, replacing an unbounded, generic
  lessons list
- A boundary-case bull/bear self-check before committing a close-call score
- Dashboard: Coffee Shop folded into the per-stock lookup instead of its own tab, a new
  **Error Management** panel surfacing the model's own logged mistakes, and a
  **Beating the market?** panel replacing the old self-grading accuracy chart

**2026-08-11/12 v2.1** — personalization, sector view, and an honest research dead-end:
- Dashboard: per-viewer **holdings toggle** (localStorage, no accounts) that labels each
  call "you own this" vs not; a **sector board** showing per-sector Bullish/Bearish/Mixed
  mood; a dynamic **entry-window banner** (flags the 9:15–11:00 AM IST buying window vs a
  stale 8:30 AM verdict); a 7-day **date filter** on the Details/lookup tab
- Agent: Run 1 Step 1 gained a **SELF-INCENTIVE** check — states whether today's accuracy
  cleared a 75% bar and applies Step 1.5's lessons more strictly after a miss (edited in
  `agent/routine_prompt.md` / `RUN1_prompt_ready_to_paste.txt`; **not yet pushed to the
  live cloud routine** — needs a separate RemoteTrigger update)
- Experimental **trend-prediction models** (`backtest/`): five honest attempts at 15/5-day
  directional forecasting (gradient boosting, ARIMA, GBM with richer features, LSTM) —
  none beat a naive baseline on walk-forward testing, so none are surfaced in the
  dashboard; kept in the repo as an honest research record rather than deleted
- UI fixes: a real Chromium paint bug in the accordion collapse animation (a closed
  section could still show a sliver of content); removed the now-redundant accuracy mood
  badge (duplicated the Accuracy KPI card) and a duplicate standalone Gold & Silver panel;
  "Browse a past day" / "Yesterday's scorecard" are now collapsible dropdowns like the
  rest of the app
