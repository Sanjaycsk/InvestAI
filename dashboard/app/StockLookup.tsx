"use client";

import { useState } from "react";
import { type Rec, type CoffeeOpinion, type Dashboard } from "@/lib/notion";
import StockDetail from "./StockDetail";
import PriceChart from "./PriceChart";
import { PERSONAS, ROLE_LABEL, STANCE_MEANING } from "./coffeeMeta";

// One dropdown to look up ANY of the day's watchlist names — this is where
// the deep-dive detail for a single stock lives: yesterday's call, this
// name's own track record, a price chart, and what different kinds of
// investors would do. Picking a stock keeps the home page itself a quick,
// uncluttered skim.

const VERDICT_TAG: Record<string, string> = {
  BUY: "▲ Buy",
  SELL: "▼ Sell",
  HOLD: "▬ Hold",
};

const VERDICT_WORD: Record<string, string> = {
  BUY: "Buy",
  SELL: "Sell / avoid",
  HOLD: "Hold",
};

// Most-advanced-run-wins: if the day's gone all the way to the 3 PM check,
// that's the freshest read; otherwise fall back earlier in the day.
const RUN_PRIORITY = ["De-risk", "Confirm", "Pre-market"];

function signed(n: number | null): string {
  if (n === null) return "—";
  const s = n > 0 ? "+" : "";
  return `${s}${n.toFixed(1)}%`;
}

export default function StockLookup({
  stocks,
  yesterday,
  tickerStats,
  trackRecordDays,
  coffee,
  priceHistory,
}: {
  stocks: Rec[];
  yesterday: Rec[];
  tickerStats: Dashboard["tickerStats"];
  trackRecordDays: number;
  coffee: CoffeeOpinion[];
  priceHistory: Dashboard["priceHistory"];
}) {
  const withTicker = stocks.filter((s) => s.ticker);
  const [sel, setSel] = useState<string>("");

  if (!withTicker.length) return null;
  const chosen = withTicker.find((s) => s.ticker === sel) ?? null;
  const y = chosen ? yesterday.find((r) => r.ticker === chosen.ticker) ?? null : null;
  const stats = chosen?.ticker ? tickerStats[chosen.ticker] : null;
  const history = chosen?.ticker ? priceHistory[chosen.ticker] ?? [] : [];

  // Plain-language "who'd do what" — the single freshest run for this
  // ticker, one line per persona, no transcript.
  const myCoffee = chosen?.ticker ? coffee.filter((c) => c.ticker === chosen.ticker) : [];
  const latestRun = RUN_PRIORITY.find((run) =>
    myCoffee.some((c) => (c.run ?? "Pre-market") === run)
  );
  const opinionRows = latestRun
    ? PERSONAS.map((p) => ({
        p,
        o: myCoffee.find(
          (c) => c.persona === p.key && (c.run ?? "Pre-market") === latestRun
        ),
      })).filter((x): x is { p: (typeof PERSONAS)[number]; o: CoffeeOpinion } => !!x.o)
    : [];

  return (
    <div className="allstocks">
      <label className="allstocks-label" htmlFor="stock-picker">
        Pick a stock
      </label>
      <div className="allstocks-select-wrap">
        <select
          id="stock-picker"
          className="allstocks-select"
          value={sel}
          onChange={(e) => setSel(e.target.value)}
        >
          <option value="">Choose a stock…</option>
          {withTicker.map((s) => (
            <option key={s.ticker} value={s.ticker!}>
              {s.ticker}
              {s.company ? ` — ${s.company}` : ""}
              {s.verdict ? `  (${VERDICT_TAG[s.verdict] ?? s.verdict})` : ""}
            </option>
          ))}
        </select>
        <span className="allstocks-chev" aria-hidden="true" />
      </div>

      {chosen ? (
        <div className="allstocks-detail" key={chosen.ticker}>
          <div className="allstocks-detail-head">
            <span className="ticker">{chosen.ticker}</span>
            {chosen.company && <span className="coname">{chosen.company}</span>}
          </div>
          <StockDetail r={chosen} />

          {/* Yesterday's call — did it work out? */}
          {y && (
            <div className="lookup-block">
              <div className="lookup-block-title">Yesterday&apos;s call</div>
              <p className="explain top">
                The model said{" "}
                <strong>{y.verdict ? VERDICT_WORD[y.verdict] ?? y.verdict : "—"}</strong>.{" "}
                {y.outcome === "Correct" && "It was right."}
                {y.outcome === "Wrong" && "It was wrong."}
                {(!y.outcome || y.outcome === "Pending") && "Still being graded."}
                {typeof y.actualMove === "number" && (
                  <> The price moved <strong>{signed(y.actualMove)}</strong>.</>
                )}
              </p>
            </div>
          )}

          {/* This one name's own track record — not just the system-wide number */}
          {stats && stats.n >= 2 && (
            <div className="lookup-block">
              <div className="lookup-block-title">
                Track record — last {trackRecordDays} days
              </div>
              <div className="sd-conf" title={`${stats.correct} right, ${stats.wrong} wrong`}>
                <span className="sd-conf-bar" aria-hidden="true">
                  <span
                    className="sd-conf-fill"
                    style={{ width: `${Math.max(0, Math.min(100, Math.round(stats.hitRate)))}%` }}
                  />
                </span>
                {stats.correct}/{stats.n} right ({stats.hitRate.toFixed(0)}%)
              </div>
              <p className="explain">
                Out of the last {stats.n} times the model called this stock, it
                was right {stats.correct} time{stats.correct === 1 ? "" : "s"}.
              </p>
            </div>
          )}

          {/* Price over time, with a simple trend read */}
          {history.length > 0 && (
            <div className="lookup-block">
              <div className="lookup-block-title">Price so far</div>
              <PriceChart data={history} />
            </div>
          )}

          {/* Different kinds of investors, in one line each — plain
              language, not a conversation. */}
          {opinionRows.length > 0 && (
            <div className="lookup-block">
              <details className="cns-legend">
                <summary>What would different kinds of investors do?</summary>
                <ul className="opinion-list">
                  {opinionRows.map(({ p, o }, i) => (
                    <li key={i}>
                      <span className="opinion-who">
                        {p.emoji} {ROLE_LABEL[p.key] ?? p.key}
                      </span>{" "}
                      would: <strong>{o.stance ? STANCE_MEANING[o.stance] ?? o.stance : "—"}</strong>
                    </li>
                  ))}
                </ul>
                <p className="explain">
                  Just perspective from six different money mindsets — it never
                  changes the model&apos;s actual BUY/HOLD/SELL call above.
                </p>
              </details>
            </div>
          )}
        </div>
      ) : (
        <p className="allstocks-hint">
          Pick any of the {withTicker.length} names to see what the model
          thinks, how it did yesterday, its track record, a price chart, and
          what different kinds of investors would do.
        </p>
      )}
    </div>
  );
}
