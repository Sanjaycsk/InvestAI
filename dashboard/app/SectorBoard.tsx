import { type Rec } from "@/lib/notion";
import { SECTOR_LABEL, SECTOR_ORDER, sectorFor, type SectorKey } from "@/lib/sectors";

// Groups the latest day's calls by sector so you can see at a glance whether
// a whole sector is leaning up or down, not just one name at a time — e.g.
// "all 4 banks are BUY today" is a stronger signal than any single bank call.
// Server-rendered (no client state needed; it's a read-only summary).

const VERDICT_WORD: Record<string, string> = {
  BUY: "Buy",
  SELL: "Sell / avoid",
  HOLD: "Hold",
};

function sectorMood(recs: Rec[]): { label: string; cls: "pos" | "neg" | "neutral" } {
  let score = 0;
  for (const r of recs) {
    if (r.verdict === "BUY") score += 1;
    else if (r.verdict === "SELL") score -= 1;
  }
  if (recs.length === 1) {
    // A single-name "sector" can't show breadth — just mirror that call.
    if (score > 0) return { label: "Bullish", cls: "pos" };
    if (score < 0) return { label: "Bearish", cls: "neg" };
    return { label: "Mixed", cls: "neutral" };
  }
  const ratio = score / recs.length;
  if (ratio >= 0.4) return { label: "Bullish", cls: "pos" };
  if (ratio <= -0.4) return { label: "Bearish", cls: "neg" };
  return { label: "Mixed", cls: "neutral" };
}

export default function SectorBoard({ stocks }: { stocks: Rec[] }) {
  const groups = new Map<SectorKey, Rec[]>();
  for (const r of stocks) {
    if (!r.ticker) continue;
    const key = sectorFor(r.ticker);
    const arr = groups.get(key) ?? [];
    arr.push(r);
    groups.set(key, arr);
  }

  const order = SECTOR_ORDER.filter((k) => groups.has(k));
  if (!order.length) return <p className="muted empty">No sector data for the latest day.</p>;

  return (
    <div className="sector-board">
      {order.map((key) => {
        const recs = [...(groups.get(key) ?? [])].sort(
          (a, b) => (b.compositeScore ?? -1) - (a.compositeScore ?? -1)
        );
        const mood = sectorMood(recs);
        return (
          <div className="sector-block" key={key}>
            <div className="sector-head">
              <span className="sector-name">{SECTOR_LABEL[key]}</span>
              <span className={`sector-mood ${mood.cls}`}>{mood.label}</span>
            </div>
            <ul className="sector-tickers">
              {recs.map((r, i) => (
                <li key={i}>
                  <span className="ticker">{r.ticker}</span>
                  <span
                    className={`verdict ${
                      r.verdict === "BUY" ? "buy" : r.verdict === "SELL" ? "sell" : "hold"
                    }`}
                  >
                    {r.verdict ? VERDICT_WORD[r.verdict] ?? r.verdict : "—"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
