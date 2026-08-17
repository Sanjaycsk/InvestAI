import { NextRequest, NextResponse } from "next/server";
import { AUTH_COOKIE, isValidSession } from "./lib/auth";

// Protect everything except the login page, the auth API, and static assets.
export const config = {
  // offline.html is listed so the service worker can precache it without the
  // auth redirect turning it into a copy of the login page.
  matcher: [
    "/((?!login|api/login|_next/static|_next/image|favicon.ico|manifest.json|sw.js|offline.html|icons/).*)",
  ],
};

export function middleware(req: NextRequest) {
  const cookie = req.cookies.get(AUTH_COOKIE)?.value;
  if (isValidSession(cookie)) return NextResponse.next();

  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.searchParams.set("next", req.nextUrl.pathname);
  return NextResponse.redirect(url);
}
