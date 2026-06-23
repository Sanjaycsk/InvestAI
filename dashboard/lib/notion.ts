// Live read layer for the InvestAI dashboard.
// Talks to the Notion REST API directly (no SDK) using the data-source query
// endpoint, so it stays correct under Notion's multi-source data model.

const NOTION_API = "https://api.notion.com/v1";
const NOTION_VERSION = "2025-09-03";

const RECS_DS = process.env.NOTION_RECOMMENDATIONS_DS!;
const REVIEW_DS = process.env.NOTION_DAILY_REVIEW_DS!;

function headers() {
  return {
    Authorization: `Bearer ${process.env.NOTION_TOKEN}`,
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
  };
}

// ---- low-level: query every page of a data source ----
async function queryAll(dataSourceId: string, body: Record<string, unknown>) {
  const results: any[] = [];
  let cursor: string | undefined = undefined;
  do {
    const res: Response = await fetch(
      `${NOTION_API}/data_sources/${dataSourceId}/query`,
      {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ page_size: 100, start_cursor: cursor, ...body }),
        cache: "no-store",
      }
    );
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Notion query failed (${res.status}): ${text}`);
    }
    const data: any = await res.json();
    results.push(...(data.results ?? []));
    cursor = data.has_more ? data.next_cursor : undefined;
  } while (cursor);
  return results;
}

// ---- property accessors ----
const pSelect = (p: any) => p?.select?.name ?? null;
const pNumber = (p: any) => (typeof p?.number === "number" ? p.number : null);
const pDate = (p: any) => p?.date?.start ?? null;
const pText = (p: any) =>
  (p?.rich_text ?? []).map((t: any) => t.plain_text).join("") || null;
const pTitle = (p: any) =>
  (p?.title ?? []).map((t: any) => t.plain_text).join("") || null;

// ---- typed shapes ----
export type Rec = {
  ticker: string | null;
  company: string | null;
  date: string | null;
  verdict: string | null; // BUY | HOLD | SELL
  category: string | null;
  compositeScore: number | null;
  refPrice: number | null;
  expectedDirection: string | null; // Up | Down | Flat
  outcome: string | null; // Correct | Wrong | Pending
  actualMove: number | null;
  rationale: string | null;
  why: string | null; // one-sentence reason, derived from the driving factor
  // ---- intraday runs (Run 2 confirm @10:00, Run 3 de-risk @15:00) ----
  run2Status: string | null; // Intact | Weakening | Broken
  run2Action: string | null; // None | Watch
  run2Note: string | null;
  run2Price: number | null;
  run3Status: string | null; // Intact | Weakening | Broken
  run3Action: string | null; // None | Trim | Exit
  run3Note: string | null;
  run3Price: number | null;
  exitPrice: number | null;
  mgmtSaved: number | null; // Exit Price − actual close (graded next morning)
};

// Pick the single most decision-relevant one-liner for "why this call".
function deriveWhy(pr: any): string | null {
  const order = ["Technical", "Macro", "Fundamental", "Sentiment", "Valuation", "Risk"];
  for (const f of order) {
    const t = pText(pr[f]);
    if (t && !/^n\/a/i.test(t.trim())) return t.trim();
  }
  return null;
}

export type Review = {
  day: string | null;
  date: string | null;
  accuracy: number | null;
  correct: number | null;
  evaluated: number | null;
  selfRating: number | null;
  summary: string | null;
  lessons: string | null;
  mgmtAlpha: number | null; // ₹ saved/lost by Run 3 de-risk exits that day
  exitsCount: number | null; // how many Run 3 exits/trims fired
};

function mapRec(page: any): Rec {
  const pr = page.properties;
  return {
    ticker: pSelect(pr["Ticker"]),
    company: pText(pr["Company"]),
    date: pDate(pr["Date"]),
    verdict: pSelect(pr["Verdict"]),
    category: pSelect(pr["Category"]),
    compositeScore: pNumber(pr["Composite Score"]),
    refPrice: pNumber(pr["Ref Price"]),
    expectedDirection: pSelect(pr["Expected Direction"]),
    outcome: pSelect(pr["Outcome"]),
    actualMove: pNumber(pr["Actual Move %"]),
    rationale: pTitle(pr["Entry"]),
    why: deriveWhy(pr),
    run2Status: pSelect(pr["Run2 Status"]),
    run2Action: pSelect(pr["Run2 Action"]),
    run2Note: pText(pr["Run2 Note"]),
    run2Price: pNumber(pr["Run2 Price"]),
    run3Status: pSelect(pr["Run3 Status"]),
    run3Action: pSelect(pr["Run3 Action"]),
    run3Note: pText(pr["Run3 Note"]),
    run3Price: pNumber(pr["Run3 Price"]),
    exitPrice: pNumber(pr["Exit Price"]),
    mgmtSaved: pNumber(pr["Mgmt Saved"]),
  };
}

function mapReview(page: any): Review {
  const pr = page.properties;
  return {
    day: pTitle(pr["Day"]),
    date: pDate(pr["Date"]),
    accuracy: pNumber(pr["Accuracy %"]),
    correct: pNumber(pr["Correct"]),
    evaluated: pNumber(pr["Stocks Evaluated"]),
    selfRating: pNumber(pr["Self Rating"]),
    summary: pText(pr["Summary"]),
    lessons: pText(pr["Lessons"]),
    mgmtAlpha: pNumber(pr["Mgmt Alpha"]),
    exitsCount: pNumber(pr["Exits Count"]),
  };
}

export type MarketSentiment = {
  label: string; // e.g. "Bullish", "Risk-off"
  tone: "pos" | "neg" | "neutral";
  index: number; // -1 (crash) .. +1 (euphoric)
  counts: { buy: number; hold: number; sell: number };
  avgScore: number | null; // mean composite score across the day
  narrative: string; // generated one-liner from breadth
  agentNote: string | null; // latest Daily Review summary, if any
};

// ---- aggregated dashboard payload ----
export type Dashboard = {
  latestDate: string | null;
  prevDate: string | null;
  todayBuys: Rec[];
  todaySells: Rec[];
  todayHolds: Rec[];
  yesterday: Rec[];
  commodities: Rec[]; // latest-day Gold (GOLDBEES) + Silver (SILVERBEES)
  todayDerisk: Rec[]; // latest-day Run 3 de-risk actions (Exit / Trim)
  sentiment: MarketSentiment;
  reviews: Review[]; // ascending by date, for the chart
  kpi: {
    accuracy: number | null; // latest review accuracy
    accuracy7d: number | null; // mean of last 7 reviews
    selfRating: number | null;
    strategyPnl: number | null; // paper: +move on BUY, -move on SELL, graded only
    mgmtAlpha: number | null; // cumulative % saved by Run 3 de-risk exits (separate from forecast)
    bestStock: { ticker: string; hitRate: number; n: number } | null;
    correctStreak: number; // consecutive latest reviews with accuracy >= 50
    gradedCount: number;
  };
  error?: string;
};

function distinctDatesDesc(recs: Rec[]): string[] {
  const set = new Set<string>();
  for (const r of recs) if (r.date) set.add(r.date);
  return [...set].sort((a, b) => (a < b ? 1 : -1));
}

function mean(xs: number[]): number | null {
  const v = xs.filter((x) => typeof x === "number" && !Number.isNaN(x));
  if (!v.length) return null;
  return v.reduce((a, b) => a + b, 0) / v.length;
}

function neutralSentiment(): MarketSentiment {
  return {
    label: "No data",
    tone: "neutral",
    index: 0,
    counts: { buy: 0, hold: 0, sell: 0 },
    avgScore: null,
    narrative: "No calls published yet for the latest day.",
    agentNote: null,
  };
}

// The system's market stance for the day, derived from its own breadth:
// how the 14 instruments split across BUY/HOLD/SELL, the average conviction
// score, and the net expected direction.
function computeSentiment(
  today: Rec[],
  latestReview: Review | null
): MarketSentiment {
  if (!today.length) return neutralSentiment();

  const counts = { buy: 0, hold: 0, sell: 0 };
  const verdictVals: number[] = [];
  const dirVals: number[] = [];
  for (const r of today) {
    if (r.verdict === "BUY") {
      counts.buy++;
      verdictVals.push(1);
    } else if (r.verdict === "SELL") {
      counts.sell++;
      verdictVals.push(-1);
    } else if (r.verdict === "HOLD") {
      counts.hold++;
      verdictVals.push(0);
    }
    if (r.expectedDirection === "Up") dirVals.push(1);
    else if (r.expectedDirection === "Down") dirVals.push(-1);
    else if (r.expectedDirection === "Flat") dirVals.push(0);
  }

  const breadth = mean(verdictVals) ?? 0; // -1..1
  const direction = mean(dirVals) ?? 0; // -1..1
  const avgScore = mean(
    today.map((r) => r.compositeScore ?? NaN)
  );

  // Blend breadth and direction into a single -1..1 index.
  const index = Math.max(-1, Math.min(1, 0.6 * breadth + 0.4 * direction));

  let label: string;
  let tone: "pos" | "neg" | "neutral";
  if (index >= 0.5) {
    label = "Feeling greedy";
    tone = "pos";
  } else if (index >= 0.2) {
    label = "Optimistic";
    tone = "pos";
  } else if (index > -0.2) {
    label = "Calm / mixed";
    tone = "neutral";
  } else if (index > -0.5) {
    label = "Nervous";
    tone = "neg";
  } else {
    label = "Fearful";
    tone = "neg";
  }

  const total = counts.buy + counts.hold + counts.sell || 1;
  const upPct = Math.round((dirVals.filter((d) => d > 0).length / total) * 100);
  const scoreTxt =
    avgScore === null
      ? ""
      : ` On average it's ${avgScore.toFixed(0)} out of 100 sure of its picks.`;
  const narrative =
    `Out of ${total} things it watches, the model wants to BUY ${counts.buy}, ` +
    `HOLD ${counts.hold} and SELL ${counts.sell} today. ` +
    `It expects about ${upPct}% of them to go up.${scoreTxt}`;

  return {
    label,
    tone,
    index,
    counts,
    avgScore,
    narrative,
    agentNote: latestReview?.summary ?? null,
  };
}

export async function getDashboard(): Promise<Dashboard> {
  try {
    const [recPages, reviewPages] = await Promise.all([
      queryAll(RECS_DS, {
        sorts: [{ property: "Date", direction: "descending" }],
      }),
      queryAll(REVIEW_DS, {
        sorts: [{ property: "Date", direction: "ascending" }],
      }),
    ]);

    const recs = recPages.map(mapRec);
    const reviews = reviewPages.map(mapReview).filter((r) => r.date);

    const dates = distinctDatesDesc(recs);
    const latestDate = dates[0] ?? null;
    const prevDate = dates[1] ?? null;

    const onDate = (d: string | null) =>
      d ? recs.filter((r) => r.date === d) : [];

    const byScore = (a: Rec, b: Rec) =>
      (b.compositeScore ?? -Infinity) - (a.compositeScore ?? -Infinity);

    const todayAll = onDate(latestDate);
    const todayBuys = todayAll
      .filter((r) => r.verdict === "BUY")
      .sort(byScore);
    const todaySells = todayAll
      .filter((r) => r.verdict === "SELL")
      .sort(byScore);
    const todayHolds = todayAll
      .filter((r) => r.verdict === "HOLD")
      .sort(byScore);
    const yesterday = onDate(prevDate).sort(byScore);

    // Gold + Silver pinned in a fixed order (latest day).
    const COMMODITY_ORDER = ["GOLDBEES", "SILVERBEES"];
    const commodities = COMMODITY_ORDER.map(
      (t) => todayAll.find((r) => r.ticker === t)
    ).filter((r): r is Rec => !!r);

    // Run 3 de-risk actions taken on the latest day (Exit / Trim).
    const todayDerisk = todayAll.filter(
      (r) => r.run3Action === "Exit" || r.run3Action === "Trim"
    );

    // ---- KPIs ----
    const latestReview = reviews[reviews.length - 1] ?? null;
    const sentiment = computeSentiment(todayAll, latestReview);
    const accuracy = latestReview?.accuracy ?? null;
    const accuracy7d = mean(
      reviews.slice(-7).map((r) => r.accuracy ?? NaN)
    );
    const selfRating = latestReview?.selfRating ?? null;

    // Paper strategy P&L: sum graded moves, long on BUY, short on SELL.
    const graded = recs.filter(
      (r) => r.outcome === "Correct" || r.outcome === "Wrong"
    );
    let strategyPnl: number | null = null;
    const movers = graded.filter((r) => typeof r.actualMove === "number");
    if (movers.length) {
      strategyPnl = movers.reduce((sum, r) => {
        const m = r.actualMove as number;
        if (r.verdict === "SELL") return sum - m;
        if (r.verdict === "BUY") return sum + m;
        return sum; // HOLD contributes nothing
      }, 0);
    }

    // Management alpha: cumulative % the Run 3 de-risk exits saved (or cost),
    // tracked separately from forecast accuracy. Mgmt Saved is in price units,
    // normalised to % of the exit price so it sums comparably across stocks.
    const exited = recs.filter(
      (r) =>
        (r.run3Action === "Exit" || r.run3Action === "Trim") &&
        typeof r.mgmtSaved === "number" &&
        typeof r.exitPrice === "number" &&
        (r.exitPrice as number) > 0
    );
    const mgmtAlpha = exited.length
      ? exited.reduce(
          (sum, r) => sum + ((r.mgmtSaved as number) / (r.exitPrice as number)) * 100,
          0
        )
      : null;

    // Best stock by hit rate (min 2 graded calls).
    const perTicker = new Map<string, { correct: number; n: number }>();
    for (const r of graded) {
      if (!r.ticker) continue;
      const t = perTicker.get(r.ticker) ?? { correct: 0, n: 0 };
      t.n += 1;
      if (r.outcome === "Correct") t.correct += 1;
      perTicker.set(r.ticker, t);
    }
    let bestStock: Dashboard["kpi"]["bestStock"] = null;
    for (const [ticker, { correct, n }] of perTicker) {
      if (n < 2) continue;
      const hitRate = (correct / n) * 100;
      if (!bestStock || hitRate > bestStock.hitRate) {
        bestStock = { ticker, hitRate, n };
      }
    }

    // Streak: consecutive most-recent reviews with accuracy >= 50.
    let correctStreak = 0;
    for (let i = reviews.length - 1; i >= 0; i--) {
      const a = reviews[i].accuracy;
      if (typeof a === "number" && a >= 50) correctStreak += 1;
      else break;
    }

    return {
      latestDate,
      prevDate,
      todayBuys,
      todaySells,
      todayHolds,
      yesterday,
      commodities,
      todayDerisk,
      sentiment,
      reviews,
      kpi: {
        accuracy,
        accuracy7d,
        selfRating,
        strategyPnl,
        mgmtAlpha,
        bestStock,
        correctStreak,
        gradedCount: graded.length,
      },
    };
  } catch (e: any) {
    return {
      latestDate: null,
      prevDate: null,
      todayBuys: [],
      todaySells: [],
      todayHolds: [],
      yesterday: [],
      commodities: [],
      todayDerisk: [],
      sentiment: neutralSentiment(),
      reviews: [],
      kpi: {
        accuracy: null,
        accuracy7d: null,
        selfRating: null,
        strategyPnl: null,
        mgmtAlpha: null,
        bestStock: null,
        correctStreak: 0,
        gradedCount: 0,
      },
      error: e?.message ?? "Unknown error fetching Notion data",
    };
  }
}
