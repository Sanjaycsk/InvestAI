// Swap the most common market jargon for words a non-finance reader
// understands. Conservative, whole-word only. Shared by the home page, the
// per-stock detail drill-down, and the coffee-shop debate cards so the whole
// dashboard speaks the same plain English.
const GLOSSARY: [RegExp, string][] = [
  [/\b200-?DMA\b/gi, "its long-term average price"],
  [/\b50-?DMA\b/gi, "its average price"],
  [/\bDMA\b/gi, "average price"],
  [/\bMACD\b/gi, "the trend signal"],
  [/\bRSI\b/gi, "momentum"],
  [/\bP\/E\b/gi, "the price-vs-profit ratio"],
  [/\bEV\/EBITDA\b/gi, "the valuation ratio"],
  [/\bGNPA\b/gi, "bad-loan levels"],
  [/\bNIM\b/gi, "lending margin"],
  [/\bROE\b/gi, "return on money"],
  [/\bROCE\b/gi, "return on capital"],
  [/\bFCF\b/gi, "spare cash"],
  [/\bbullish\b/gi, "positive"],
  [/\bbearish\b/gi, "negative"],
  [/\boverbought\b/gi, "looking expensive"],
  [/\boversold\b/gi, "looking cheap"],
  [/\bbreakout\b/gi, "a sharp move up"],
  [/\bresistance\b/gi, "a price ceiling"],
  [/\bsupport\b/gi, "a price floor"],
];

export function plainify(s: string | null): string | null {
  if (!s) return s;
  let out = s;
  for (const [re, rep] of GLOSSARY) out = out.replace(re, rep);
  return out;
}
