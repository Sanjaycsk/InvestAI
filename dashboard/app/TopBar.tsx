"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { LineChart, Refresh } from "./Icons";

export default function TopBar({ subtitle }: { subtitle: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function logout() {
    setBusy(true);
    await fetch("/api/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  return (
    <header className="topbar">
      <div className="topbar-brand">
        <span className="topbar-logo">
          <LineChart size={20} />
        </span>
        <div>
          <div className="topbar-title">InvestAI</div>
          <div className="topbar-sub">{subtitle}</div>
        </div>
      </div>
      <div className="topbar-actions">
        <button
          className="ghost icon-btn"
          onClick={() => router.refresh()}
          disabled={busy}
          aria-label="Refresh"
        >
          <Refresh size={16} />
        </button>
        <button className="ghost" onClick={logout} disabled={busy}>
          Sign out
        </button>
      </div>
    </header>
  );
}
