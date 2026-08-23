import { NextRequest, NextResponse } from "next/server";
import { AUTH_COOKIE, sessionSecret } from "@/lib/auth";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  let passcode = "";
  try {
    const body = await req.json();
    passcode = String(body?.passcode ?? "");
  } catch {
    // ignore — empty passcode will fail below
  }

  const expected = process.env.DASHBOARD_PASSCODE ?? "";
  if (!expected || passcode !== expected) {
    return NextResponse.json({ ok: false }, { status: 401 });
  }

  // Without a session secret the cookie we'd set is empty, isValidSession()
  // rejects it, and middleware bounces straight back here — an invisible
  // redirect loop that looks like "the right passcode doesn't work". Fail
  // loudly on the misconfiguration instead of handing out a dud session.
  const secret = sessionSecret();
  if (!secret) {
    console.error("DASHBOARD_SESSION_SECRET is not set — cannot issue a session.");
    return NextResponse.json(
      { ok: false, error: "Server is missing DASHBOARD_SESSION_SECRET." },
      { status: 500 }
    );
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set(AUTH_COOKIE, secret, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 30, // 30 days
  });
  return res;
}
