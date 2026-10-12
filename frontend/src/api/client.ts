import { tokenStore } from "@/auth/tokenStore";
import { API_BASE_URL } from "@/config/env";

import { ApiError, isAbortError, networkError, normalizeApiError } from "./errors";
import type { TokenResponse } from "./types";

type QueryValue = string | number | boolean | undefined | null;

export interface RequestOptions {
  method?: "GET" | "POST" | "DELETE";
  json?: unknown;
  body?: FormData;
  query?: Record<string, QueryValue>;
  signal?: AbortSignal;
  /** Attach the access token and refresh it on 401. Defaults to true. */
  auth?: boolean;
}

export function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }

  const search = params.toString();
  return `${API_BASE_URL}${path}${search ? `?${search}` : ""}`;
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text().catch(() => "");
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export async function toApiError(response: Response): Promise<ApiError> {
  return normalizeApiError(response.status, await readBody(response), response.headers);
}

function sessionExpired(): ApiError {
  return new ApiError("Your session has expired. Please sign in again.", {
    status: 401,
    code: "SESSION_EXPIRED",
  });
}

async function send(path: string, options: RequestOptions, accessToken: string | null): Promise<Response> {
  const headers = new Headers({ Accept: "application/json, text/plain" });
  let body: BodyInit | undefined;

  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.json);
  } else if (options.body) {
    body = options.body;
  }

  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  try {
    return await fetch(buildUrl(path, options.query), {
      method: options.method ?? "GET",
      headers,
      body,
      signal: options.signal,
    });
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw networkError();
  }
}

/** Serializes refreshes across tabs where Web Locks are available. */
async function runExclusive<T>(task: () => Promise<T>): Promise<T> {
  const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
  if (locks?.request) {
    return locks.request("ada-token-refresh", task) as Promise<T>;
  }
  return task();
}

async function performRefresh(attempt = 0): Promise<boolean> {
  const refreshToken = tokenStore.getRefreshToken();

  if (!refreshToken) {
    tokenStore.clear("expired");
    return false;
  }

  const response = await send("/api/auth/refresh", { method: "POST", json: { refresh_token: refreshToken }, auth: false }, null);

  if (response.ok) {
    tokenStore.setTokens((await response.json()) as TokenResponse);
    return true;
  }

  if (response.status === 401) {
    // Rotation revokes the old token; another tab may have just rotated it.
    const latest = tokenStore.getRefreshToken();
    if (attempt === 0 && latest && latest !== refreshToken) return performRefresh(attempt + 1);

    tokenStore.clear("expired");
    return false;
  }

  // Rate limits or outages: keep the session and let the caller retry later.
  throw await toApiError(response);
}

let refreshInFlight: Promise<boolean> | null = null;

/**
 * Refreshes the token pair once, however many callers ask at the same time.
 * Refresh tokens rotate, so parallel refreshes would revoke each other.
 */
export function refreshSession(): Promise<boolean> {
  refreshInFlight ??= runExclusive(() => performRefresh()).finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

/** Sends a request and returns the response if it succeeded; throws ApiError otherwise. */
export async function apiFetch(path: string, options: RequestOptions = {}): Promise<Response> {
  const auth = options.auth ?? true;

  if (auth && !tokenStore.getAccessToken()) {
    if (!(await refreshSession())) throw sessionExpired();
  }

  const usedToken = auth ? tokenStore.getAccessToken() : null;
  let response = await send(path, options, usedToken);

  if (auth && response.status === 401) {
    // Another request may already have refreshed while this one was in flight.
    if (tokenStore.getAccessToken() === usedToken && !(await refreshSession())) {
      throw sessionExpired();
    }

    response = await send(path, options, tokenStore.getAccessToken());

    if (response.status === 401) {
      tokenStore.clear("expired");
      throw sessionExpired();
    }
  }

  if (!response.ok) throw await toApiError(response);
  return response;
}

export async function apiJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await apiFetch(path, options);
  return (await response.json()) as T;
}
