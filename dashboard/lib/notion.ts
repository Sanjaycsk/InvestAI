// Live read layer for the InvestAI dashboard.
// Talks to the Notion REST API directly (no SDK) using the data-source query
// endpoint, so it stays correct under Notion's multi-source data model.

const NOTION_API = "https://api.notion.com/v1";
const NOTION_VERSION = "2025-09-03";

const RECS_DS = process.env.NOTION_RECOMMENDATIONS_DS!;
const REVIEW_DS = process.env.NOTION_DAILY_REVIEW_DS!;
// A data-source id is an identifier, not a secret (NOTION_TOKEN is the secret),
// so a hardcoded fallback is fine and saves adding a new Vercel env var.
const COFFEE_DS =
  process.env.NOTION_COFFEESHOP_DS || "fee73e14-f1c4-48b7-a285-c319ccb781b7";

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

// The agent is supposed to score 0-100, but on some days it logs on a 0-10
// scale instead (e.g. a BUY at 7.05 instead of 70.5), which then rendered as
// an alarming "confidence 7/100" next to a Buy verdict. Normalise any 0-10
// value up to the 0-100 scale so the number always matches the Category bands
// (Strong Buy >80, Buy 70-80, Hold 45-60, Sell <45). The real fix is in the
// routine prompt (enforce integer 0-100); this keeps old + stray rows sane.
const pScore = (p: any): number | null => {
  const n = pNumber(p);
  if (n === null) return null;
  return n > 0 && n <= 10 ? Math.round(n * 10) : Math.round(n);
};

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
  factors: { label: string; text: string }[]; // per-factor notes for the drill-down
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

// Plain-English labels for the six scoring factors, in display order.
const FACTOR_LABELS: [string, string][] = [
  ["Fundamental", "Business health"],
  ["Technical", "Price trend"],
  ["Valuation", "Is it cheap or pricey"],
  ["Macro", "Big-picture / economy"],
  ["Sentiment", "What people are saying"],
  ["Risk", "What could go wrong"],
];

// Pick the single most decision-relevant one-liner for "why this call".
function deriveWhy(pr: any): string | null {
  const order = ["Technical", "Macro", "Fundamental", "Sentiment", "Valuation", "Risk"];
  for (const f of order) {
    const t = pText(pr[f]);
    if (t && !/^n\/a/i.test(t.trim())) return t.trim();
  }
  return null;
}

// The full per-factor breakdown for the stock-detail drill-down. Skips factors
// the agent marked N/A (index / commodity) and any that are empty.
function buildFactors(pr: any): { label: string; text: string }[] {
  const out: { label: string; text: string }[] = [];
  for (const [key, label] of FACTOR_LABELS) {
    const t = pText(pr[key]);
    if (t && t.trim() && !/^n\/a/i.test(t.trim())) out.push({ label, text: t.trim() });
  }
  return out;
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
  correctableErrors: string | null; // analysis mistakes the model could have avoided
  marketDrivenMisses: string | null; // sound calls the market moved against unforeseeably
  mgmtAlpha: number | null; // ₹ saved/lost by Run 3 de-risk exits that day
  exitsCount: number | null; // how many Run 3 exits/trims fired
  // Real NIFTY 50 benchmark reading for the day (added 2026-08-11 — needs the
  // "Nifty Close" / "Nifty Move %" columns added to Daily Review in Notion and
  // the live prompt updated to fill them; null on every row until both happen,
  // in which case the dashboard falls back to the GROWWN200 proxy).
  niftyClose: number | null;
  niftyMovePct: number | null;
};

function mapRec(page: any): Rec {
  const pr = page.properties;
  return {
    ticker: pSelect(pr["Ticker"]),
    company: pText(pr["Company"]),
    date: pDate(pr["Date"]),
    verdict: pSelect(pr["Verdict"]),
    category: pSelect(pr["Category"]),
    compositeScore: pScore(pr["Composite Score"]),
    refPrice: pNumber(pr["Ref Price"]),
    expectedDirection: pSelect(pr["Expected Direction"]),
    outcome: pSelect(pr["Outcome"]),
    actualMove: pNumber(pr["Actual Move %"]),
    rationale: pTitle(pr["Entry"]),
    why: deriveWhy(pr),
    factors: buildFactors(pr),
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
    correctableErrors: pText(pr["Correctable Errors"]),
    marketDrivenMisses: pText(pr["Market-Driven Misses"]),
    mgmtAlpha: pNumber(pr["Mgmt Alpha"]),
    exitsCount: pNumber(pr["Exits Count"]),
    niftyClose: pNumber(pr["Nifty Close"]),
    niftyMovePct: pNumber(pr["Nifty Move %"]),
  };
}

// One character's call on one shortlisted stock, from the coffee-shop panel.
export type CoffeeOpinion = {
  date: string | null;
  ticker: string | null;
  persona: string | null; // Vihaan | Aarav | Rohan | Meera | Neel | Diya
  stance: string | null; // Buy | SIP | Hold | Wait | Avoid | Punt
  horizon: string | null; // Long | Short | Mixed
  take: string | null;
  run: string | null; // Pre-market | Confirm | De-risk
  debate: string | null; // per-ticker transcript (set on that ticker's Vihaan row)
};

function mapCoffee(page: any): CoffeeOpinion {
  const pr = page.properties;
  return {
    date: pDate(pr["Date"]),
    ticker: pText(pr["Ticker"]),
    persona: pSelect(pr["Persona"]),
    stance: pSelect(pr["Stance"]),
    horizon: pSelect(pr["Horizon"]),
    take: pText(pr["Take"]),
    run: pSelect(pr["Run"]),
    debate: pText(pr["Debate"]),
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
  today: Rec[]; // every instrument for the latest day (for the "all stocks" browser)
  todayBuys: Rec[];
  todaySells: Rec[];
  todayHolds: Rec[];
  yesterday: Rec[];
  commodities: Rec[]; // latest-day Gold (GOLDBEES) + Silver (SILVERBEES)
  todayDerisk: Rec[]; // latest-day Run 3 de-risk actions (Exit / Trim)
  coffee: CoffeeOpinion[]; // coffee-shop panel for its latest date
  coffeeDate: string | null;
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
    dataErrors: number; // graded rows dropped from P&L as implausible (bad Ref Price)
    marketAlpha: number | null; // strategy return minus the market's return, same days
    marketAlphaDays: number; // how many graded days that comparison covers
    marketAlphaNiftyDays: number; // of those, how many used the REAL Nifty 50 reading (rest use the GROWWN200 proxy)
    // Every graded call weighted equally (not "average of each day's accuracy%",
    // which over/under-weights light vs heavy days) — the honest "would my calls
    // have been right" number, over trackRecordDays.
    accuracyTrackRecord: number | null;
  };
  // Whole-history hit rate per ticker (not a rolling window — the dashboard's
  // been live since inception, so "last 45 days" and "all time" are close to
  // the same thing; trackRecordDays makes the actual span honest either way).
  tickerStats: Record<string, { correct: number; wrong: number; n: number; hitRate: number }>;
  trackRecordDays: number; // distinct graded trading days behind tickerStats
  // Ref Price over time per ticker, ascending by date — for the stock-lookup price chart.
  priceHistory: Record<string, { date: string; refPrice: number }[]>;
  // What to check before trusting today's calls — surfaced from the Daily
  // Review fields that used to exist in Notion but never rendered anywhere.
  errorManagement: {
    asOfDate: string | null;
    correctableErrors: string[]; // yesterday's analysis mistakes, one per line
    marketDrivenMisses: string[]; // yesterday's sound-call-but-market-moved misses
    standingLessons: string[]; // the model's current running rule set
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
    const [recPages, reviewPages, coffeePages] = await Promise.all([
      queryAll(RECS_DS, {
        sorts: [{ property: "Date", direction: "descending" }],
      }),
      queryAll(REVIEW_DS, {
        sorts: [{ property: "Date", direction: "ascending" }],
      }),
      // New, optional feature — never let a Coffee Shop hiccup break the page.
      queryAll(COFFEE_DS, {
        sorts: [{ property: "Date", direction: "descending" }],
      }).catch(() => [] as any[]),
    ]);

    const recs = recPages.map(mapRec);
    const reviews = reviewPages.map(mapReview).filter((r) => r.date);

    // Coffee-shop opinions, narrowed to the most recent date that has any.
    const coffeeAll = coffeePages
      .map(mapCoffee)
      .filter((c) => c.date && c.ticker && c.persona);
    const coffeeDate = distinctDatesDesc(
      coffeeAll.map((c) => ({ date: c.date } as Rec))
    )[0] ?? null;
    const coffee = coffeeDate
      ? coffeeAll.filter((c) => c.date === coffeeDate)
      : [];

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

    // Paper strategy P&L, expressed as a REAL return.
    //
    // The old version summed every graded call's Actual Move % into one running
    // total. That is not a return: it grows without bound as more calls are
    // graded, and a handful of bad-data rows (the agent occasionally scrapes a
    // wrong Ref Price from the web, e.g. a GOLDBEES row logged at ₹68 instead of
    // ₹117 → a fake +72% move) dragged the headline to an impossible -115% on a
    // long-only paper book. Two fixes:
    //   1. Drop rows whose Actual Move % is physically implausible for a single
    //      day — these are data errors, not real moves — and count them so the
    //      UI can flag that the underlying data needs cleaning.
    //   2. Treat each day as an equal-weight book (long every BUY, short every
    //      SELL, HOLD flat) and COMPOUND the daily returns, exactly like the
    //      backtest's equity curve. This is bounded and comparable over time.
    const graded = recs.filter(
      (r) => r.outcome === "Correct" || r.outcome === "Wrong"
    );
    const movers = graded.filter((r) => typeof r.actualMove === "number");
    const MAX_PLAUSIBLE_DAILY_MOVE = 20; // % — beyond this is a bad Ref Price, not a real day
    const dataErrors = movers.filter(
      (r) => Math.abs(r.actualMove as number) > MAX_PLAUSIBLE_DAILY_MOVE
    ).length;
    const clean = movers.filter(
      (r) => Math.abs(r.actualMove as number) <= MAX_PLAUSIBLE_DAILY_MOVE
    );

    let strategyPnl: number | null = null;
    if (clean.length) {
      const byDay = new Map<string, number[]>();
      for (const r of clean) {
        const m = r.actualMove as number;
        const dayRet =
          r.verdict === "SELL" ? -m : r.verdict === "BUY" ? m : null; // HOLD flat
        if (dayRet === null || !r.date) continue;
        const bucket = byDay.get(r.date) ?? [];
        bucket.push(dayRet / 100);
        byDay.set(r.date, bucket);
      }
      let equity = 1;
      for (const day of [...byDay.keys()].sort()) {
        const rets = byDay.get(day)!;
        const eqWeight = rets.reduce((a, b) => a + b, 0) / rets.length;
        equity *= 1 + eqWeight;
      }
      strategyPnl = (equity - 1) * 100;
    }

    // Market alpha: is the paper strategy actually beating the market, or just
    // riding a broad rally? Every call has so far been graded on absolute move
    // only ("+0.8% on a BUY = Correct") even on a day the whole market rose 2% —
    // that's not stock-picking skill, that's beta.
    //
    // Prefer the REAL Nifty 50 reading (Daily Review's "Nifty Move %" — added
    // 2026-08-11, requires that Notion column + a live-prompt update, so it's
    // null until both land) over the GROWWN200 (Nifty 200 ETF) proxy, which is
    // already one of the 26 tracked instruments and needs no schema change —
    // used as the fallback so this comparison works today and upgrades itself
    // automatically once real Nifty data starts flowing in.
    const niftyByDate = new Map<string, number>();
    for (const r of reviews) {
      if (r.date && typeof r.niftyMovePct === "number") {
        niftyByDate.set(r.date, r.niftyMovePct);
      }
    }
    const growwn200ByDate = new Map<string, number>();
    for (const r of recs) {
      if (
        r.ticker === "GROWWN200" &&
        r.date &&
        typeof r.actualMove === "number" &&
        Math.abs(r.actualMove) <= MAX_PLAUSIBLE_DAILY_MOVE
      ) {
        growwn200ByDate.set(r.date, r.actualMove);
      }
    }
    let marketAlpha: number | null = null;
    let marketAlphaDays = 0;
    let marketAlphaNiftyDays = 0;
    if (clean.length && (niftyByDate.size || growwn200ByDate.size)) {
      const byDayForAlpha = new Map<string, number[]>();
      for (const r of clean) {
        const m = r.actualMove as number;
        const dayRet =
          r.verdict === "SELL" ? -m : r.verdict === "BUY" ? m : null;
        if (dayRet === null || !r.date) continue;
        const bucket = byDayForAlpha.get(r.date) ?? [];
        bucket.push(dayRet / 100);
        byDayForAlpha.set(r.date, bucket);
      }
      let stratEq = 1;
      let benchEq = 1;
      for (const day of [...byDayForAlpha.keys()].sort()) {
        const realNifty = niftyByDate.get(day);
        const benchMove = realNifty !== undefined ? realNifty : growwn200ByDate.get(day);
        if (benchMove === undefined) continue; // only days with a benchmark reading
        const rets = byDayForAlpha.get(day)!;
        const eqWeight = rets.reduce((a, b) => a + b, 0) / rets.length;
        stratEq *= 1 + eqWeight;
        benchEq *= 1 + benchMove / 100;
        marketAlphaDays++;
        if (realNifty !== undefined) marketAlphaNiftyDays++;
      }
      if (marketAlphaDays > 0) {
        marketAlpha = (stratEq - 1) * 100 - (benchEq - 1) * 100;
      }
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

    // Best stock by hit rate (min 2 graded calls), and — since the dashboard's
    // been live long enough that "last 45 days" and "whole track record" are
    // close to the same window — the full per-ticker breakdown for the stock
    // lookup page's accuracy bar.
    const perTicker = new Map<string, { correct: number; wrong: number; n: number }>();
    const gradedDates = new Set<string>();
    for (const r of graded) {
      if (r.date) gradedDates.add(r.date);
      if (!r.ticker) continue;
      const t = perTicker.get(r.ticker) ?? { correct: 0, wrong: 0, n: 0 };
      t.n += 1;
      if (r.outcome === "Correct") t.correct += 1;
      else if (r.outcome === "Wrong") t.wrong += 1;
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
    const tickerStats: Dashboard["tickerStats"] = {};
    for (const [ticker, { correct, wrong, n }] of perTicker) {
      tickerStats[ticker] = { correct, wrong, n, hitRate: n ? (correct / n) * 100 : 0 };
    }
    const trackRecordDays = gradedDates.size;

    // Track-record accuracy: every graded call weighted equally, over the
    // whole run — different from `accuracy7d`, which averages each day's
    // accuracy% and so treats a 1-call day the same as a 10-call day.
    const accuracyTrackRecord = graded.length
      ? (graded.filter((r) => r.outcome === "Correct").length / graded.length) * 100
      : null;

    // Price history per ticker (ascending), for the stock-lookup line chart.
    // Ref Price is already logged daily for every instrument, so this needs
    // no new data source.
    const priceHistory: Dashboard["priceHistory"] = {};
    for (const r of recs) {
      if (!r.ticker || !r.date || typeof r.refPrice !== "number") continue;
      const arr = priceHistory[r.ticker] ?? (priceHistory[r.ticker] = []);
      arr.push({ date: r.date, refPrice: r.refPrice });
    }
    for (const ticker of Object.keys(priceHistory)) {
      priceHistory[ticker].sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
    }

    // Error management: what to check before trusting today's calls, pulled
    // from Daily Review fields that were always in Notion but never rendered
    // anywhere on the dashboard. Split each field on newlines (the routine
    // writes one item per line) and drop anything blank.
    const splitLines = (s: string | null): string[] =>
      (s ?? "")
        .split(/\r?\n/)
        .map((l) => l.replace(/^[-•*]\s*/, "").trim())
        .filter(Boolean);
    const errorManagement: Dashboard["errorManagement"] = {
      asOfDate: latestReview?.date ?? null,
      correctableErrors: splitLines(latestReview?.correctableErrors ?? null),
      marketDrivenMisses: splitLines(latestReview?.marketDrivenMisses ?? null),
      standingLessons: splitLines(latestReview?.lessons ?? null),
    };

    // Streak: consecutive most-recent reviews with accuracy >= 50.
    let correctStreak = 0;
    for (let i = reviews.length - 1; i >= 0; i--) {
      const a = reviews[i].accuracy;
      if (typeof a === "number" && a >= 50) correctStreak += 1;
      else break;
    }

    // Everything for the latest day, verdict-grouped then by conviction, for
    // the "browse all stocks" dropdown.
    const VERDICT_RANK: Record<string, number> = { BUY: 0, HOLD: 1, SELL: 2 };
    const today = [...todayAll].sort(
      (a, b) =>
        (VERDICT_RANK[a.verdict ?? ""] ?? 3) - (VERDICT_RANK[b.verdict ?? ""] ?? 3) ||
        byScore(a, b)
    );

    return {
      latestDate,
      prevDate,
      today,
      todayBuys,
      todaySells,
      todayHolds,
      yesterday,
      commodities,
      todayDerisk,
      coffee,
      coffeeDate,
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
        dataErrors,
        marketAlpha,
        marketAlphaDays,
        marketAlphaNiftyDays,
        accuracyTrackRecord,
      },
      tickerStats,
      trackRecordDays,
      priceHistory,
      errorManagement,
    };
  } catch (e: any) {
    return {
      latestDate: null,
      prevDate: null,
      today: [],
      todayBuys: [],
      todaySells: [],
      todayHolds: [],
      yesterday: [],
      commodities: [],
      todayDerisk: [],
      coffee: [],
      coffeeDate: null,
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
        dataErrors: 0,
        marketAlpha: null,
        marketAlphaDays: 0,
        marketAlphaNiftyDays: 0,
        accuracyTrackRecord: null,
      },
      tickerStats: {},
      trackRecordDays: 0,
      priceHistory: {},
      errorManagement: {
        asOfDate: null,
        correctableErrors: [],
        marketDrivenMisses: [],
        standingLessons: [],
      },
      error: e?.message ?? "Unknown error fetching Notion data",
    };
  }
}
