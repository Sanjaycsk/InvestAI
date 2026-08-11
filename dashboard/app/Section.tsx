"use client";

import { type ReactNode, useState } from "react";
import { Chevron } from "./Icons";

// A collapsible dropdown section. Tap the header to open/close the whole panel.
// The header shows the title, an optional count badge, and — while collapsed —
// a one-line summary (e.g. the tickers inside), so you can scan without opening.
// Children stay server-rendered; only the open/closed class lives on the client.
export default function Section({
  title,
  titleClass,
  tone,
  count,
  summary,
  hint,
  defaultOpen = false,
  className,
  children,
}: {
  title: ReactNode;
  titleClass?: string;
  tone?: "buy" | "sell" | "hold";
  count?: number;
  summary?: string;
  hint?: string;
  defaultOpen?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className={`acc card ${open ? "open" : ""} ${className ?? ""}`}>
      <button
        type="button"
        className="acc-head"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="acc-head-main">
          <span className={`acc-title ${titleClass ?? ""}`}>{title}</span>
          {typeof count === "number" && (
            <span className={`acc-count ${tone ?? ""}`}>{count}</span>
          )}
          {!open && summary ? (
            <span className="acc-summary">{summary}</span>
          ) : hint ? (
            <span className="acc-hint">{hint}</span>
          ) : null}
        </span>
        <Chevron size={18} className="acc-chev" />
      </button>
      <div className="acc-panel">
        <div className="acc-panel-inner">{children}</div>
      </div>
    </section>
  );
}
