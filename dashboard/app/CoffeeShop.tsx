import { type CoffeeOpinion } from "@/lib/notion";

// The six coffee-shop characters, in a fixed display order.
const PERSONAS: { key: string; emoji: string; tag: string }[] = [
  { key: "Vihaan", emoji: "🧓", tag: "Veteran — buys quality, holds for years" },
  { key: "Aarav", emoji: "⚡", tag: "Hotshot — rides short-term momentum" },
  { key: "Rohan", emoji: "👀", tag: "Watcher — waits for a dip, rarely buys" },
  { key: "Meera", emoji: "💼", tag: "Delegator — safe, set-and-forget SIPs" },
  { key: "Neel", emoji: "🪙", tag: "Small budget — sticks to cheap ETFs" },
  { key: "Diya", emoji: "🎲", tag: "Experimenter — small risky punts" },
];
const STANCE_CLS: Record<string, string> = {
  Buy: "st-buy",
  SIP: "st-sip",
  Hold: "st-hold",
  Wait: "st-wait",
  Avoid: "st-avoid",
  Punt: "st-punt",
};

// Six investors argue over a BUY shortlist; same facts, different moves.
// `coffee` is already narrowed to one run (or all, for a single panel).
export default function CoffeeShop({
  coffee,
  buyOrder,
  title = "☕ The coffee-shop table",
  subtitle = "6 friends · shortlist",
}: {
  coffee: CoffeeOpinion[];
  buyOrder: string[];
  title?: string;
  subtitle?: string;
}) {
  if (!coffee.length) return null;

  // Tickers across the bottom, ordered by today's BUY conviction then any extras.
  const tickers = Array.from(
    new Set(coffee.map((c) => c.ticker).filter((t): t is string => !!t))
  ).sort((a, b) => {
    const ia = buyOrder.indexOf(a);
    const ib = buyOrder.indexOf(b);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });

  const k = (p: string, t: string) => `${p}|${t}`;
  const lookup = new Map<string, CoffeeOpinion>();
  for (const c of coffee) {
    if (c.persona && c.ticker) lookup.set(k(c.persona, c.ticker), c);
  }

  return (
    <section className="card">
      <div className="card-head">
        <h2>{title}</h2>
        <span className="muted">{subtitle}</span>
      </div>
      <div className="coffee-scroll">
        <table className="coffee-matrix">
          <thead>
            <tr>
              <th className="cm-corner">Friend</th>
              {tickers.map((t) => (
                <th className="cm-tk" key={t}>
                  {t}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {PERSONAS.map((p) => (
              <tr key={p.key}>
                <th className="cm-friend">
                  <span className="cm-emoji">{p.emoji}</span>
                  <span className="cm-name">{p.key}</span>
                  <span className="cm-tag">{p.tag}</span>
                </th>
                {tickers.map((t) => {
                  const o = lookup.get(k(p.key, t));
                  return (
                    <td key={t}>
                      <span
                        className={`stance ${
                          o?.stance ? STANCE_CLS[o.stance] ?? "" : "st-none"
                        }`}
                        title={o?.take ?? ""}
                      >
                        {o?.stance ?? "—"}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="coffee-takes">
        <summary>💬 Hear them debate</summary>
        {tickers.map((t) => {
          const transcript =
            coffee.find((c) => c.ticker === t && c.debate)?.debate ?? null;
          const lines = transcript
            ? transcript
                .split(/\r?\n/)
                .map((s) => s.trim())
                .filter(Boolean)
            : [];
          return (
            <div className="ct-stock" key={t}>
              <div className="ct-tk">{t}</div>
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
                        <span className="dl-text">{m ? m[2] : ln}</span>
                      </p>
                    );
                  })}
                </div>
              )}
              <ul className="ct-takes">
                {PERSONAS.map((p) => {
                  const o = lookup.get(k(p.key, t));
                  if (!o?.take) return null;
                  return (
                    <li key={p.key}>
                      <span className="ct-who">
                        {p.emoji} {p.key}
                      </span>
                      <span
                        className={`stance sm ${
                          o.stance ? STANCE_CLS[o.stance] ?? "" : ""
                        }`}
                      >
                        {o.stance}
                      </span>
                      <span className="ct-take">{o.take}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </details>
    </section>
  );
}
