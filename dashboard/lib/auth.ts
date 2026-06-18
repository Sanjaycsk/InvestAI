// Shared-passcode session. The cookie holds the server's session secret;
// middleware just checks the cookie equals that secret. Simple and adequate
// for a small trusted audience.

export const AUTH_COOKIE = "investai_auth";

export function sessionSecret(): string {
  return process.env.DASHBOARD_SESSION_SECRET ?? "";
}

export function isValidSession(cookieValue: string | undefined): boolean {
  const secret = sessionSecret();
  return !!secret && cookieValue === secret;
}
