"use client";

import { type ReactNode, useState } from "react";
import Toggle from "./Toggle";

// A stock-list card that flips between a compact one-line-per-stock view and a
// detailed view (the "why" text + intraday timeline). The toggle only changes a
// CSS class on the list wrapper, so the rows themselves stay server-rendered.
export default function ListCard({
  title,
  titleClass,
  hint,
  hasItems = true,
  startDetailed = false,
  children,
}: {
  title: ReactNode;
  titleClass?: string;
  hint?: string;
  hasItems?: boolean;
  startDetailed?: boolean;
  children: ReactNode;
}) {
  const [detailed, setDetailed] = useState(startDetailed);
  return (
    <section className="card">
      <div className="card-head">
        <div className="card-head-main">
          <h2 className={titleClass}>{title}</h2>
          {hint && <span className="card-hint">{hint}</span>}
        </div>
        {hasItems && (
          <Toggle on={detailed} onChange={setDetailed} label="Details" />
        )}
      </div>
      <div className={`list ${detailed ? "detailed" : "compact"}`}>
        {children}
      </div>
    </section>
  );
}
