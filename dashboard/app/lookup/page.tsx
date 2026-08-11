import { getDashboard } from "@/lib/notion";
import TopBar from "../TopBar";
import TabNav from "../TabNav";
import StockLookup from "../StockLookup";

// Always render fresh from Notion.
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function LookupPage() {
  const d = await getDashboard();

  if (d.error) {
    return (
      <main className="container">
        <TopBar subtitle="Connection error" />
        <div className="card error-card">
          <strong>Couldn&apos;t reach Notion.</strong>
          <p>{d.error}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="container">
      <TopBar subtitle="Look up any stock" />
      <TabNav active="lookup" />

      <p className="explain top">
        Pick any of the watchlist names to see today&apos;s call, how
        yesterday&apos;s call went, this stock&apos;s own track record, and
        what the six coffee-shop friends think of it.
      </p>

      <section className="card allstocks-card">
        <StockLookup
          stocks={d.today}
          yesterday={d.yesterday}
          tickerStats={d.tickerStats}
          trackRecordDays={d.trackRecordDays}
          coffee={d.coffee}
        />
      </section>

      <footer className="foot">Reads live from Notion</footer>
    </main>
  );
}
