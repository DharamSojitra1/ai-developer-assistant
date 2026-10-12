/**
 * Reads the `exp` claim of a JWT, for scheduling refreshes only. The
 * signature is not (and cannot be) verified here; the server does that.
 */
export function getTokenExpiry(token: string): number | null {
  const payload = token.split(".")[1];
  if (!payload) return null;

  try {
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const claims = JSON.parse(atob(padded)) as { exp?: unknown };
    return typeof claims.exp === "number" ? claims.exp * 1000 : null;
  } catch {
    return null;
  }
}

/** Milliseconds until the token should be refreshed, or null if unknown. */
export function msUntilRefresh(token: string, leewayMs = 60_000, now = Date.now()): number | null {
  const expiresAt = getTokenExpiry(token);
  if (expiresAt === null) return null;
  return Math.max(0, expiresAt - leewayMs - now);
}
