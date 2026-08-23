"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { LineChart } from "../Icons";

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/";
  const [passcode, setPasscode] = useState("");
  // null = no error yet. A server misconfiguration (no session secret) must
  // not be reported as "wrong passcode" — that sends someone hunting for a
  // passcode that was right all along.
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ passcode }),
    });
    setLoading(false);
    if (res.ok) {
      router.replace(next);
      router.refresh();
      return;
    }
    setError(
      res.status >= 500
        ? "Server isn't set up correctly — sign-in is unavailable."
        : "Wrong passcode — try again."
    );
    setPasscode("");
  }

  return (
    <main className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="login-logo">
          <LineChart size={34} />
        </div>
        <h1>InvestAI</h1>
        <p className="login-sub">Enter passcode to view today&apos;s calls</p>
        <input
          type="password"
          inputMode="text"
          autoFocus
          value={passcode}
          onChange={(e) => setPasscode(e.target.value)}
          placeholder="Passcode"
          className={error ? "input err" : "input"}
        />
        {error && <p className="login-err">{error}</p>}
        <button type="submit" disabled={loading || !passcode}>
          {loading ? "Checking…" : "Enter"}
        </button>
      </form>
    </main>
  );
}
