/**
 * Access tokens live only in memory. The refresh token is persisted in
 * localStorage so sessions survive reloads: the backend returns it in the
 * JSON body rather than as an httpOnly cookie, so this is the trade-off.
 */
export const REFRESH_TOKEN_KEY = "ada.refresh_token";
export const USER_EMAIL_KEY = "ada.user_email";

export type SessionEndReason = "logout" | "expired";

type Listener = () => void;

let accessToken: string | null = null;
let endReason: SessionEndReason | null = null;
const listeners = new Set<Listener>();

function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // Storage can be unavailable (private mode); the session then lasts one page load.
  }
}

function emit(): void {
  listeners.forEach((listener) => listener());
}

export const tokenStore = {
  getAccessToken(): string | null {
    return accessToken;
  },

  /** Read from storage each time, so a token rotated by another tab is used. */
  getRefreshToken(): string | null {
    return readStorage(REFRESH_TOKEN_KEY);
  },

  getEmail(): string | null {
    return readStorage(USER_EMAIL_KEY);
  },

  getEndReason(): SessionEndReason | null {
    return endReason;
  },

  setTokens(tokens: { access_token: string; refresh_token: string }, email?: string): void {
    accessToken = tokens.access_token;
    endReason = null;
    writeStorage(REFRESH_TOKEN_KEY, tokens.refresh_token);
    if (email) writeStorage(USER_EMAIL_KEY, email);
    emit();
  },

  /** Another tab rotated the refresh token; our access token is still valid. */
  syncFromStorage(): void {
    if (!readStorage(REFRESH_TOKEN_KEY)) {
      accessToken = null;
      endReason = "logout";
    }
    emit();
  },

  clear(reason: SessionEndReason): void {
    accessToken = null;
    endReason = reason;
    writeStorage(REFRESH_TOKEN_KEY, null);
    if (reason === "logout") writeStorage(USER_EMAIL_KEY, null);
    emit();
  },

  hasSession(): boolean {
    return accessToken !== null || readStorage(REFRESH_TOKEN_KEY) !== null;
  },

  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};
