"use client";

import { useState } from "react";
import { type Rec } from "@/lib/notion";
import { plainify } from "@/lib/plain";

// Browse any of the last 7 trading days' calls — capped at a week on
// purpose (this is a quick recent-history check, not a full archive; the
// "Does this actually work?" 1-year backtest further down covers the
// long view).

const VERDICT_WORD: Record<string, string> = {
  BUY: "Buy",
  SELL: "Sell / avoid",
  HOLD: "Hold",
};

function fmtDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}

function fmtDateShort(iso: string): { top: string; bottom: string } {
  const d = new Date(iso + "T00:00:00");
  return {
    top: d.toLocaleDateString("en-IN", { weekday: "short" }),
    bottom: d.toLocaleDateString("en-IN", { day: "numeric", month: "short" }),
  };
}

function signed(n: number | null): string {
  if (n === null) return "—";
  const s = n > 0 ? "+" : "";
  return `${s}${n.toFixed(1)}%`;
}

function DayRow({ r }: { r: Rec }) {
  const move = typeof r.actualMove === "number" ? r.actualMove : null;
  return (
    <li className="stock-row col">
      <div className="stock-row-top">
        <div className="stock-main">
          <span className="ticker">{r.ticker ?? "—"}</span>
          <span
            className={`verdict ${
              r.verdict === "BUY" ? "buy" : r.verdict === "SELL" ? "sell" : "hold"
            }`}
          >
            {r.verdict ? VERDICT_WORD[r.verdict] ?? r.verdict : "—"}
          </span>
        </div>
        <div className="stock-meta">
          {r.outcome && r.outcome !== "Pending" && (
            <span className={`outcome ${r.outcome === "Correct" ? "ok" : "bad"}`}>
              {r.outcome === "Correct" ? "✓ right" : "✗ wrong"}
            </span>
          )}
          {move !== null && (
            <span className={`move ${move > 0 ? "pos" : move < 0 ? "neg" : ""}`}>
              {signed(move)}
            </span>
          )}
        </div>
      </div>
      {r.why && <div className="why">{plainify(r.why)}</div>}
    </li>
  );
}

export default function DateFilter({
  days,
}: {
  days: { date: string; recs: Rec[] }[];
}) {
  const [sel, setSel] = useState(0);
  if (!days.length) return <p className="muted empty">No history yet.</p>;
  const chosen = days[Math.min(sel, days.length - 1)];
  const buys = chosen.recs.filter((r) => r.verdict === "BUY");
  const holds = chosen.recs.filter((r) => r.verdict === "HOLD");
  const sells = chosen.recs.filter((r) => r.verdict === "SELL");

  return (
    <div className="datefilter">
      <div className="datefilter-pills">
        {days.map((d, i) => {
          const { top, bottom } = fmtDateShort(d.date);
          return (
            <button
              key={d.date}
              type="button"
              className={`datefilter-pill${i === sel ? " active" : ""}`}
              onClick={() => setSel(i)}
            >
              <span className="dfp-top">{i === 0 ? "Today" : top}</span>
              <span className="dfp-bottom">{bottom}</span>
            </button>
          );
        })}
      </div>

      <div className="datefilter-summary">
        <span className="datefilter-date">{fmtDate(chosen.date)}</span>
        <span className="datefilter-counts">
          <span className="cns-count buy">{buys.length} Buy</span>
          <span className="cns-count hold">{holds.length} Hold</span>
          <span className="cns-count sell">{sells.length} Sell</span>
        </span>
      </div>

      {chosen.recs.length ? (
        <ul className="stock-list">
          {chosen.recs.map((r, i) => (
            <DayRow key={i} r={r} />
          ))}
        </ul>
      ) : (
        <p className="muted empty">No calls logged for this day.</p>
      )}
    </div>
  );
}
