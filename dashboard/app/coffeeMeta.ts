// Shared coffee-shop metadata: the six characters, the stance colours, and
// plain-English meanings for every stance word (used by the legend so nobody
// has to wonder what "Punt" or "SIP" means).

export const PERSONAS: { key: string; emoji: string; tag: string }[] = [
  { key: "Vihaan", emoji: "🧓", tag: "Veteran — buys quality, holds for years" },
  { key: "Aarav", emoji: "⚡", tag: "Hotshot — rides short-term momentum" },
  { key: "Rohan", emoji: "👀", tag: "Watcher — waits for a dip, rarely buys" },
  { key: "Meera", emoji: "💼", tag: "Delegator — safe, set-and-forget SIPs" },
  { key: "Neel", emoji: "🪙", tag: "Small budget — sticks to cheap ETFs" },
  { key: "Diya", emoji: "🎲", tag: "Experimenter — small risky punts" },
];

export const STANCE_CLS: Record<string, string> = {
  Buy: "st-buy",
  SIP: "st-sip",
  Hold: "st-hold",
  Wait: "st-wait",
  Avoid: "st-avoid",
  Punt: "st-punt",
};

// Display order for the consensus breakdown (most positive → most negative).
export const STANCE_ORDER = ["Buy", "SIP", "Hold", "Wait", "Avoid", "Punt"];

// Plain-English meaning of each stance — shown in the legend.
export const STANCE_INFO: { key: string; meaning: string }[] = [
  { key: "Buy", meaning: "buy it now" },
  { key: "SIP", meaning: "buy a little every month (auto-invest)" },
  { key: "Hold", meaning: "already own it? keep it" },
  { key: "Wait", meaning: "hold off — watch for a better price" },
  { key: "Avoid", meaning: "stay away (or sell if you hold it)" },
  { key: "Punt", meaning: "a small risky gamble for a quick gain" },
];
