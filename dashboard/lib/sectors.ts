// Static sector map for the 31-instrument watchlist. Mirrors the
// sector-appropriate groupings already used by the routine prompt's
// Fundamental scoring guidance (agent/routine_prompt.md STEP 2), so "sector"
// here means the same thing the model already reasons about — not a new
// taxonomy invented for the dashboard. Small watchlist (31 names), so this
// is a plain lookup table rather than pulled from an external classifier.
//
// Extend as the watchlist grows: anything not listed falls into "Other".

export type SectorKey =
  | "banking"
  | "it"
  | "fmcg"
  | "auto"
  | "pharma"
  | "metals"
  | "energy"
  | "power"
  | "industrials"
  | "renewables"
  | "defense"
  | "telecom"
  | "broad-market"
  | "commodities"
  | "other";

export const SECTOR_LABEL: Record<SectorKey, string> = {
  banking: "Banking & Finance",
  it: "IT & Technology",
  fmcg: "FMCG & Consumer",
  auto: "Auto",
  pharma: "Pharma & Healthcare",
  metals: "Metals & Mining",
  energy: "Oil, Gas & Energy",
  power: "Power & Utilities",
  industrials: "Industrials & Capital Goods",
  renewables: "Renewable Energy",
  defense: "Defense",
  telecom: "Telecom",
  "broad-market": "Broad Market",
  commodities: "Gold & Silver",
  other: "Other",
};

// Display order on the dashboard — biggest/most-watched groups first.
export const SECTOR_ORDER: SectorKey[] = [
  "banking",
  "it",
  "energy",
  "fmcg",
  "power",
  "industrials",
  "renewables",
  "metals",
  "auto",
  "pharma",
  "defense",
  "telecom",
  "broad-market",
  "commodities",
  "other",
];

const TICKER_SECTOR: Record<string, SectorKey> = {
  // Banking & Finance
  HDFCBANK: "banking",
  ICICIBANK: "banking",
  SBIN: "banking",
  FEDERALBNK: "banking",
  // IT & Technology
  TCS: "it",
  INFY: "it",
  // FMCG & Consumer
  ITC: "fmcg",
  HINDUNILVR: "fmcg",
  // Auto
  MARUTI: "auto",
  // Pharma & Healthcare
  SUNPHARMA: "pharma",
  // Metals & Mining
  TATASTEEL: "metals",
  VEDL: "metals",
  HINDZINC: "metals",
  VAML: "metals",
  VISL: "metals",
  // Oil, Gas & Energy (incl. diversified energy conglomerate)
  RELIANCE: "energy",
  BPCL: "energy",
  ADANIENT: "energy",
  VOGL: "energy",
  // Power & Utilities
  NTPC: "power",
  TATAPOWER: "power",
  VEDPOWER: "power",
  // Industrials & Capital Goods
  LT: "industrials",
  BHEL: "industrials",
  // Renewable Energy
  SUZLON: "renewables",
  WAAREEENER: "renewables",
  // Defense
  BEL: "defense",
  // Telecom
  BHARTIARTL: "telecom",
  // Broad market
  GROWWN200: "broad-market",
  // Commodities
  GOLDBEES: "commodities",
  SILVERBEES: "commodities",
};

export function sectorFor(ticker: string | null): SectorKey {
  if (!ticker) return "other";
  return TICKER_SECTOR[ticker.toUpperCase()] ?? "other";
}
