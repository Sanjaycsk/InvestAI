"use client";

import { useEffect, useState } from "react";
import Toggle from "./Toggle";

// This dashboard is shared by ~15 people and everyone's actual portfolio is
// different, so there is no single "your holdings" the server can know —
// each viewer's own phone remembers it instead (localStorage, per device).
// This turns the model's portfolio-agnostic BUY/HOLD/SELL verdict into a
// personal "what do I actually do" action: someone holding nothing sees
// "Don't buy" instead of a confusing "Sell" on a stock they never bought.
const STORAGE_KEY = "investai:holdings";

function readHoldings(): Record<string, boolean> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function writeHoldings(h: Record<string, boolean>) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(h));
  } catch {
    // Storage disabled/full — ownership just won't persist; not fatal.
  }
}

// What to actually DO, given the model's verdict + whether you hold it.
const PERSONAL_ACTION: Record<
  string,
  (owned: boolean) => { word: string; cls: "pos" | "neg" | "warn" }
> = {
  BUY: () => ({ word: "Buy", cls: "pos" }),
  SELL: (owned) =>
    owned
      ? { word: "Sell", cls: "neg" }
      : { word: "Don't buy", cls: "neg" },
  HOLD: (owned) =>
    owned
      ? { word: "Hold what you have", cls: "warn" }
      : { word: "Skip for now", cls: "warn" },
};

export default function OwnBadge({
  ticker,
  verdict,
}: {
  ticker: string | null;
  verdict: string | null;
}) {
  const [owned, setOwned] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!ticker) return;
    setOwned(!!readHoldings()[ticker]);
    setReady(true);
  }, [ticker]);

  if (!ticker || !verdict || !PERSONAL_ACTION[verdict]) return null;
  // Avoid a flash of the wrong (default-false) state before localStorage loads.
  if (!ready) return null;

  const action = PERSONAL_ACTION[verdict](owned);

  const toggle = (v: boolean) => {
    setOwned(v);
    const h = readHoldings();
    if (v) h[ticker] = true;
    else delete h[ticker];
    writeHoldings(h);
  };

  return (
    <div className="own-badge">
      <span className={`own-action ${action.cls}`}>
        For you: <strong>{action.word}</strong>
      </span>
      <Toggle on={owned} onChange={toggle} label="I own this" />
    </div>
  );
}
