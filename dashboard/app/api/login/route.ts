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

  const res = NextResponse.json({ ok: true });
  res.cookies.set(AUTH_COOKIE, sessionSecret(), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 30, // 30 days
  });
  return res;
}
