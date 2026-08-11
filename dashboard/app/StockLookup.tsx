"use client";

import { useState } from "react";
import { type Rec, type CoffeeOpinion, type Dashboard } from "@/lib/notion";
import { plainify } from "@/lib/plain";
import StockDetail from "./StockDetail";
import { PERSONAS, STANCE_CLS } from "./coffeeMeta";

// One dropdown to look up ANY of the day's watchlist names, and — since the
// dedicated Coffee Shop tab and the old "how accurate over time" chart both
// got folded in here instead of living as separate pages — this is also
// where the deep-dive detail for a single stock lives: yesterday's call,
// this name's own track record, and the coffee-shop friends' take on it.
// Picking a stock keeps the home page itself a quick, uncluttered skim.

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

const RUN_LABEL: Record<string, string> = {
  "Pre-market": "Morning call",
  Confirm: "After the open",
  "De-risk": "Before the close",
};
const RUN_ORDER = ["Pre-market", "Confirm", "De-risk"];

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
}: {
  stocks: Rec[];
  yesterday: Rec[];
  tickerStats: Dashboard["tickerStats"];
  trackRecordDays: number;
  coffee: CoffeeOpinion[];
}) {
  const withTicker = stocks.filter((s) => s.ticker);
  const [sel, setSel] = useState<string>("");

  if (!withTicker.length) return null;
  const chosen = withTicker.find((s) => s.ticker === sel) ?? null;
  const y = chosen ? yesterday.find((r) => r.ticker === chosen.ticker) ?? null : null;
  const stats = chosen?.ticker ? tickerStats[chosen.ticker] : null;
  const myCoffee = chosen?.ticker
    ? coffee.filter((c) => c.ticker === chosen.ticker)
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

          {/* Coffee-shop friends, folded in per-stock instead of a separate tab */}
          {myCoffee.length > 0 && (
            <div className="lookup-block">
              <div className="lookup-block-title">What the coffee-shop friends think</div>
              {RUN_ORDER.filter((run) =>
                myCoffee.some((c) => (c.run ?? "Pre-market") === run)
              ).map((run) => {
                const rows = myCoffee.filter((c) => (c.run ?? "Pre-market") === run);
                const transcript = rows.find((c) => c.debate)?.debate ?? null;
                const lines = transcript
                  ? transcript.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)
                  : [];
                return (
                  <details className="cns" key={run}>
                    <summary className="cns-head">
                      <span className="cns-tk">{RUN_LABEL[run] ?? run}</span>
                      <span className="cns-counts">
                        {rows.map((r, i) => (
                          <span
                            key={i}
                            className={`cns-count ${STANCE_CLS[r.stance ?? ""] ?? ""}`}
                          >
                            {r.stance ?? "—"}
                          </span>
                        ))}
                      </span>
                      <span className="cns-chev" aria-hidden="true" />
                    </summary>
                    <div className="cns-body">
                      {lines.length > 0 && (
                        <div className="debate">
                          {lines.map((ln, i) => {
                            const m = ln.match(/^([A-Za-z]+)\s*[:–—-]\s*(.*)$/);
                            const who = m ? m[1] : null;
                            const emoji = who
                              ? PERSONAS.find((p) => p.key === who)?.emoji ?? "💬"
                              : "";
                            return (
                              <p className="debate-line" key={i}>
                                {who && (
                                  <span className="dl-who">
                                    {emoji} {who}
                                  </span>
                                )}
                                <span className="dl-text">{plainify(m ? m[2] : ln)}</span>
                              </p>
                            );
                          })}
                        </div>
                      )}
                      <ul className="cns-matrix">
                        {rows.map((r, i) => {
                          const p = PERSONAS.find((pp) => pp.key === r.persona);
                          return (
                            <li key={i}>
                              <span className="cm-who">
                                {p?.emoji ?? "💬"} {r.persona}
                              </span>
                              <span
                                className={`stance sm ${
                                  r.stance ? STANCE_CLS[r.stance] ?? "" : ""
                                }`}
                              >
                                {r.stance ?? "—"}
                              </span>
                              {r.take && <span className="cm-take">{plainify(r.take)}</span>}
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  </details>
                );
              })}
            </div>
          )}
        </div>
      ) : (
        <p className="allstocks-hint">
          Pick any of the {withTicker.length} names to see what the model
          thinks, how it did yesterday, its track record, and what the
          coffee-shop friends say.
        </p>
      )}
    </div>
  );
}
