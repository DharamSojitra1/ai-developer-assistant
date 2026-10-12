import { apiJson } from "./client";
import type { UsageResponse } from "./types";

export function getMyUsage(days: number, signal?: AbortSignal): Promise<UsageResponse> {
  return apiJson<UsageResponse>("/api/usage/me", { query: { days }, signal });
}
