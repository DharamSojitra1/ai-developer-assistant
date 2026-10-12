import { createContext, useCallback, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";

import * as authApi from "@/api/auth";
import { refreshSession } from "@/api/client";
import { msUntilRefresh } from "@/lib/jwt";

import { REFRESH_TOKEN_KEY, tokenStore, type SessionEndReason } from "./tokenStore";

export type AuthStatus = "restoring" | "authenticated" | "unauthenticated" | "unreachable";

export interface AuthContextValue {
  status: AuthStatus;
  email: string | null;
  endReason: SessionEndReason | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  retryRestore: () => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue | null>(null);

const REFRESH_RETRY_MS = 30_000;

function useAccessToken(): string | null {
  return useSyncExternalStore(tokenStore.subscribe, tokenStore.getAccessToken);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const accessToken = useAccessToken();
  const endReason = useSyncExternalStore(tokenStore.subscribe, tokenStore.getEndReason);
  const email = useSyncExternalStore(tokenStore.subscribe, tokenStore.getEmail);
  const [restoreState, setRestoreState] = useState<"pending" | "done" | "unreachable">(() =>
    tokenStore.getRefreshToken() ? "pending" : "done",
  );
  const [restoreAttempt, setRestoreAttempt] = useState(0);

  // Restore the session from the stored refresh token on load.
  useEffect(() => {
    if (restoreState !== "pending") return;
    let cancelled = false;

    refreshSession()
      .then(() => !cancelled && setRestoreState("done"))
      .catch(() => !cancelled && setRestoreState("unreachable"));

    return () => {
      cancelled = true;
    };
  }, [restoreState, restoreAttempt]);

  // Refresh shortly before the access token expires.
  useEffect(() => {
    if (!accessToken) return;
    const delay = msUntilRefresh(accessToken);
    if (delay === null) return;

    let timer = window.setTimeout(function tick() {
      refreshSession().catch(() => {
        timer = window.setTimeout(tick, REFRESH_RETRY_MS);
      });
    }, delay);

    return () => window.clearTimeout(timer);
  }, [accessToken]);

  // Keep tabs in sync: rotated refresh tokens and logouts.
  useEffect(() => {
    function onStorage(event: StorageEvent) {
      if (event.key === REFRESH_TOKEN_KEY || event.key === null) tokenStore.syncFromStorage();
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const login = useCallback(async (rawEmail: string, password: string) => {
    const normalized = rawEmail.trim().toLowerCase();
    const tokens = await authApi.login({ email: normalized, password });
    tokenStore.setTokens(tokens, normalized);
    setRestoreState("done");
  }, []);

  const register = useCallback(
    async (rawEmail: string, password: string) => {
      const normalized = rawEmail.trim().toLowerCase();
      await authApi.register({ email: normalized, password });
      await login(normalized, password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    const refreshToken = tokenStore.getRefreshToken();
    tokenStore.clear("logout");
    if (refreshToken) {
      // Revocation is best effort; local tokens are already gone.
      await authApi.logout(refreshToken).catch(() => undefined);
    }
  }, []);

  const retryRestore = useCallback(() => {
    setRestoreState("pending");
    setRestoreAttempt((attempt) => attempt + 1);
  }, []);

  const status: AuthStatus =
    restoreState === "pending"
      ? "restoring"
      : restoreState === "unreachable" && !accessToken
        ? "unreachable"
        : accessToken
          ? "authenticated"
          : "unauthenticated";

  const value = useMemo<AuthContextValue>(
    () => ({ status, email, endReason, login, register, logout, retryRestore }),
    [status, email, endReason, login, register, logout, retryRestore],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
