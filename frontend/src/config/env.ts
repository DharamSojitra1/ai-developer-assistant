const rawBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

/** Empty means same origin (the Vite dev proxy or a reverse proxy). */
export const API_BASE_URL = rawBaseUrl.trim().replace(/\/+$/, "");
