import type { ReactNode } from "react";

// A plain, always-open card with a header — no collapse/dropdown.
// Used for the context & track-record sections (the dropdown toggle is
// reserved for the first three action sections: Buy / Sell / Hold).
export default function Panel({
  title,
  titleClass,
  hint,
  className,
  children,
}: {
  title: ReactNode;
  titleClass?: string;
  hint?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`card ${className ?? ""}`}>
      <div className="card-head">
        <h2 className={titleClass}>{title}</h2>
        {hint && <span className="muted">{hint}</span>}
      </div>
      {children}
    </section>
  );
}
