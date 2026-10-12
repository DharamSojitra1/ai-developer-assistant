import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { tokenStore } from "@/auth/tokenStore";

import { apiJson, refreshSession } from "./client";
import { ApiError } from "./errors";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const fetchMock = vi.fn<typeof fetch>();

function authHeader(call: number): string | null {
  const init = fetchMock.mock.calls[call][1];
  return new Headers(init?.headers).get("Authorization");
}

beforeEach(() => {
  tokenStore.clear("logout");
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch", () => {
  it("attaches the access token", async () => {
    tokenStore.setTokens({ access_token: "access-1", refresh_token: "refresh-1" });
    fetchMock.mockResolvedValueOnce(json(200, { ok: true }));

    await expect(apiJson("/api/usage/me")).resolves.toEqual({ ok: true });
    expect(authHeader(0)).toBe("Bearer access-1");
  });

  it("refreshes once on 401 and retries with the new token", async () => {
    tokenStore.setTokens({ access_token: "stale", refresh_token: "refresh-1" });
    fetchMock
      .mockResolvedValueOnce(json(401, { detail: "Invalid or expired access token" }))
      .mockResolvedValueOnce(json(200, { access_token: "fresh", refresh_token: "refresh-2", token_type: "bearer" }))
      .mockResolvedValueOnce(json(200, { ok: true }));

    await expect(apiJson("/api/chat/history")).resolves.toEqual({ ok: true });

    expect(fetchMock.mock.calls[1][0]).toContain("/api/auth/refresh");
    expect(authHeader(2)).toBe("Bearer fresh");
    expect(tokenStore.getRefreshToken()).toBe("refresh-2");
  });

  it("shares one refresh between concurrent callers, because refresh tokens rotate", async () => {
    tokenStore.setTokens({ access_token: "stale", refresh_token: "refresh-1" });
    let resolveRefresh!: (response: Response) => void;
    fetchMock.mockImplementationOnce(() => new Promise((resolve) => (resolveRefresh = resolve)));

    const first = refreshSession();
    const second = refreshSession();
    resolveRefresh(json(200, { access_token: "fresh", refresh_token: "refresh-2", token_type: "bearer" }));

    await expect(Promise.all([first, second])).resolves.toEqual([true, true]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("ends the session when the refresh token is rejected", async () => {
    tokenStore.setTokens({ access_token: "stale", refresh_token: "revoked" });
    fetchMock
      .mockResolvedValueOnce(json(401, { detail: "expired" }))
      .mockResolvedValueOnce(json(401, { detail: "Refresh token is revoked or invalid" }));

    const error = await apiJson("/api/chat/history").catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("SESSION_EXPIRED");
    expect(tokenStore.hasSession()).toBe(false);
    expect(tokenStore.getEndReason()).toBe("expired");
  });

  it("keeps the session when refreshing fails for a transient reason", async () => {
    tokenStore.setTokens({ access_token: "stale", refresh_token: "refresh-1" });
    fetchMock.mockResolvedValueOnce(json(429, { error: "Rate limit exceeded" }));

    await expect(refreshSession()).rejects.toMatchObject({ code: "RATE_LIMITED" });
    expect(tokenStore.getRefreshToken()).toBe("refresh-1");
  });

  it("reports network failures without exposing internals", async () => {
    tokenStore.setTokens({ access_token: "access", refresh_token: "refresh" });
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(apiJson("/api/usage/me")).rejects.toMatchObject({ code: "NETWORK_ERROR", status: 0 });
  });

  it("does not send credentials to public auth endpoints", async () => {
    fetchMock.mockResolvedValueOnce(json(401, { detail: "Invalid email or password" }));

    await expect(
      apiJson("/api/auth/login", { method: "POST", json: { email: "a@b.co", password: "x" }, auth: false }),
    ).rejects.toMatchObject({ status: 401, message: "Invalid email or password" });
    expect(authHeader(0)).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
