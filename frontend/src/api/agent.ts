import { apiJson } from "./client";
import type { AgentChatResponse, ChatRequest } from "./types";

export function agentChat(body: ChatRequest, signal?: AbortSignal): Promise<AgentChatResponse> {
  return apiJson<AgentChatResponse>("/api/agent/chat", { method: "POST", json: body, signal });
}

export function decideApproval(runId: string, approved: boolean, signal?: AbortSignal): Promise<AgentChatResponse> {
  return apiJson<AgentChatResponse>(`/api/agent/runs/${encodeURIComponent(runId)}/approval`, {
    method: "POST",
    json: { approved },
    signal,
  });
}
