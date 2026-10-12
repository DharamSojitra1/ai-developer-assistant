import { apiFetch, apiJson } from "./client";
import type {
  ChatHistoryResponse,
  ChatRequest,
  ConversationDetail,
  ConversationListResponse,
  DeleteHistoryResponse,
} from "./types";

/** Starts a token stream; read the body with `readTextStream`. */
export function streamChat(body: ChatRequest, signal?: AbortSignal): Promise<Response> {
  return apiFetch("/api/chat/chat/stream", { method: "POST", json: body, signal });
}

export function getChatHistory(params: { limit: number; skip: number }, signal?: AbortSignal): Promise<ChatHistoryResponse> {
  return apiJson<ChatHistoryResponse>("/api/chat/history", { query: params, signal });
}

export function deleteChatHistory(): Promise<DeleteHistoryResponse> {
  return apiJson<DeleteHistoryResponse>("/api/chat/history", { method: "DELETE" });
}

export function listConversations(
  params: { limit: number; skip: number },
  signal?: AbortSignal,
): Promise<ConversationListResponse> {
  return apiJson<ConversationListResponse>("/api/chat/conversations", { query: params, signal });
}

export function getConversation(conversationId: string, signal?: AbortSignal): Promise<ConversationDetail> {
  return apiJson<ConversationDetail>(`/api/chat/conversations/${encodeURIComponent(conversationId)}`, { signal });
}

export function deleteConversation(conversationId: string): Promise<DeleteHistoryResponse> {
  return apiJson<DeleteHistoryResponse>(`/api/chat/conversations/${encodeURIComponent(conversationId)}`, {
    method: "DELETE",
  });
}
