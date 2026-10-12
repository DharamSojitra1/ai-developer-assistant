import { describe, expect, it } from "vitest";

import { getTokenExpiry, msUntilRefresh } from "./jwt";

function token(claims: object): string {
  const encode = (value: object) => btoa(JSON.stringify(value)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `${encode({ alg: "HS256", typ: "JWT" })}.${encode(claims)}.signature`;
}

describe("jwt", () => {
  it("reads the exp claim in milliseconds", () => {
    expect(getTokenExpiry(token({ sub: "u1", exp: 1_700_000_000 }))).toBe(1_700_000_000_000);
  });

  it("returns null for malformed tokens or a missing exp", () => {
    expect(getTokenExpiry("not-a-jwt")).toBeNull();
    expect(getTokenExpiry(token({ sub: "u1" }))).toBeNull();
  });

  it("schedules the refresh before expiry, never in the past", () => {
    const now = 1_000_000;
    const expiresIn15Min = token({ exp: (now + 15 * 60_000) / 1000 });
    expect(msUntilRefresh(expiresIn15Min, 60_000, now)).toBe(14 * 60_000);

    const expired = token({ exp: (now - 1000) / 1000 });
    expect(msUntilRefresh(expired, 60_000, now)).toBe(0);
  });
});
