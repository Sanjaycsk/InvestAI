"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

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
      <div>
        <div className="topbar-title">📈 InvestAI</div>
        <div className="topbar-sub">{subtitle}</div>
      </div>
      <div className="topbar-actions">
        <button className="ghost" onClick={() => router.refresh()} disabled={busy}>
          ↻
        </button>
        <button className="ghost" onClick={logout} disabled={busy}>
          Sign out
        </button>
      </div>
    </header>
  );
}
