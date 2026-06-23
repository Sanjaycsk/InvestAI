import { getDashboard } from "@/lib/notion";
import TopBar from "../TopBar";
import TabNav from "../TabNav";
import CoffeeShop from "../CoffeeShop";

// Always render fresh from Notion.
export const dynamic = "force-dynamic";
export const revalidate = 0;

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

// The three points in the day the table weighs in.
const RUNS: { key: string; title: string; subtitle: string }[] = [
  {
    key: "Pre-market",
    title: "🌅 Pre-market",
    subtitle: "before the market opens · 9:30 AM",
  },
  {
    key: "Confirm",
    title: "📈 After the open",
    subtitle: "about an hour into trading · 10:30 AM",
  },
  {
    key: "De-risk",
    title: "🛡️ Before the close",
    subtitle: "last call before the 3:30 close · 3:20 PM",
  },
];

export default async function CoffeePage() {
  const d = await getDashboard();
  const buyOrder = d.todayBuys
    .map((r) => r.ticker)
    .filter((t): t is string => !!t);

  // Legacy rows with no Run default to Pre-market.
  const forRun = (run: string) =>
    d.coffee.filter((c) => (c.run ?? "Pre-market") === run);

  const anySection = RUNS.some((r) => forRun(r.key).length > 0);

  return (
    <main className="container">
      <TopBar subtitle={`Coffee shop · ${fmtDate(d.coffeeDate)}`} />
      <TabNav active="coffee" />

      <p className="explain top">
        Six very different investors argue over the day&apos;s buy ideas — and revisit
        them as the market moves: at the open, an hour in, and just before the close.
        Same facts, totally different moves. Find whichever one sounds like you.
      </p>

      {anySection ? (
        RUNS.map((r) => {
          const rows = forRun(r.key);
          return rows.length ? (
            <CoffeeShop
              key={r.key}
              coffee={rows}
              buyOrder={buyOrder}
              title={r.title}
              subtitle={r.subtitle}
            />
          ) : null;
        })
      ) : (
        <div className="card">
          <p className="muted empty">
            No coffee-shop opinions yet. The table meets at 9:30, 10:30 and 15:20 IST
            on trading days — check back after the next session.
          </p>
        </div>
      )}

      <footer className="foot">Perspective only · never changes the official verdict</footer>
    </main>
  );
}
