/** Only same-app paths are allowed as post-login destinations. */
export function safeRedirectPath(candidate: unknown, fallback = "/"): string {
  if (typeof candidate !== "string") return fallback;
  if (!candidate.startsWith("/") || candidate.startsWith("//") || candidate.includes("\\")) return fallback;
  if (candidate.startsWith("/login") || candidate.startsWith("/register")) return fallback;
  return candidate;
}
