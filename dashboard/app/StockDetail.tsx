import { type Rec } from "@/lib/notion";
import { plainify } from "@/lib/plain";

// The expanded "more details" view for one stock: what the model decided, how
// sure it was, and the plain-English reason behind each of the six factors it
// weighs. Presentational only (no state) so it works inside a server-rendered
// <details> row and inside the client "all stocks" browser alike.

const DIR: Record<string, { arrow: string; text: string; cls: string }> = {
  Up: { arrow: "▲", text: "expects it to go up", cls: "pos" },
  Down: { arrow: "▼", text: "expects it to go down", cls: "neg" },
  Flat: { arrow: "▬", text: "expects little change", cls: "" },
};

const VERDICT_WORD: Record<string, { word: string; cls: string }> = {
  BUY: { word: "Buy", cls: "pos" },
  SELL: { word: "Sell / avoid", cls: "neg" },
  HOLD: { word: "Hold", cls: "warn" },
};

function fmtPrice(n: number | null): string {
  if (n === null) return "—";
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export default function StockDetail({ r }: { r: Rec }) {
  const v = r.verdict ? VERDICT_WORD[r.verdict] : null;
  const dir = r.expectedDirection ? DIR[r.expectedDirection] : null;
  const conf = typeof r.compositeScore === "number" ? r.compositeScore : null;

  return (
    <div className="sd">
      <div className="sd-top">
        {v && <span className={`sd-verdict ${v.cls}`}>{v.word}</span>}
        {r.category && <span className="sd-chip">{r.category}</span>}
        {dir && (
          <span className={`sd-chip ${dir.cls}`}>
            {dir.arrow} {dir.text}
          </span>
        )}
      </div>

      <div className="sd-meta">
        {r.refPrice != null && (
          <span>
            Price when checked <b>{fmtPrice(r.refPrice)}</b>
          </span>
        )}
        {conf != null && (
          <span className="sd-conf" title="How sure the model is, out of 100">
            <span className="sd-conf-bar" aria-hidden="true">
              <span className="sd-conf-fill" style={{ width: `${Math.max(0, Math.min(100, conf))}%` }} />
            </span>
            {conf}/100 sure
          </span>
        )}
      </div>

      {r.factors.length > 0 ? (
        <ul className="sd-factors">
          {r.factors.map((f, i) => (
            <li key={i}>
              <span className="sd-flabel">{f.label}</span>
              <span className="sd-ftext">{plainify(f.text)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="sd-empty">No detailed notes recorded for this one.</p>
      )}
    </div>
  );
}
