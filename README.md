# InvestAI — Self-Grading Stock Research Agent

A multi-run, **autonomous** equity-research agent built on **Claude (Anthropic)**. On
every trading day it issues a **BUY / HOLD / SELL** verdict on a fixed 24-instrument NSE
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
| **1 · Pre-market** | 08:30 | Full analysis. Grades yesterday, learns, then scores all 24 and logs today's **BUY/HOLD/SELL**. This is the **verdict of record**. |
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
   Correct/Wrong, compute accuracy % and a self-rating /100, and grade any prior-day
   de-risk exits into *management alpha*.
2. **Learn** — read recent daily reviews and apply their *correctable-error* lessons as
   standing rules for today (genuine market-driven misses are left alone).
3. **Analyze today** — score six factors per instrument, weighted by instrument type.
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
verdict.**

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

## The 24 instruments (fixed universe, NSE)

**Equities (21):** RELIANCE, HDFCBANK, ICICIBANK, TCS, INFY, BHARTIARTL, ITC,
HINDUNILVR, LT, MARUTI, SUNPHARMA, TATASTEEL, SBIN, FEDERALBNK, SUZLON, TATAPOWER,
WAAREEENER, NTPC, ADANIENT, BEL, BHEL
**Index ETF (1):** GROWWN200 (Groww Nifty 200 ETF — market proxy)
**Commodity ETFs (2):** GOLDBEES (Gold), SILVERBEES (Silver)

---

## Why it can be trusted

- **Held accountable daily** — every call is checked against the real close and scored;
  wins *and* losses are recorded.
- **Prediction kept separate from management** — the morning verdict is frozen and graded
  on its own; intraday exits are scored as a separate "management alpha" line, so the
  accuracy number can't be quietly rewritten with hindsight.
- **Fully auditable** — each recommendation is stored with its reasoning, sources, and a
  timestamp; nothing is ephemeral.
- **Learns from mistakes** — errors are classified (fixable vs market) and fixable ones
  become rules it applies the next day.
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
config/  src/  scripts/  tests/   original local Python toolkit (200-DMA, RSS,
                                   discovery, simulated execution) — the prototype
                                   this evolved from; kept for local/offline use.
```

> The original Python pipeline (the earlier discovery/portfolio prototype) still runs
> locally and offline, but the **live system is the Claude cloud routines** described above.

---

## Status

A **45-day evaluation** of the agent's accuracy is underway. Telegram delivery of the
daily brief is deferred; results land in the Notion audit databases, the dashboard, and
each routine's run history.
