import type { AgentChatResponse, ChatHistoryItem } from "@/api/types";
import type { StreamOutcome } from "@/api/stream";

import type { AssistantMessage, ChatMessage, ChatMode } from "./types";

export type ConversationLoad =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "not_found" }
  | { status: "error"; error: string };

export interface ChatState {
  messages: ChatMessage[];
  /** The conversation on screen; null until a new chat's first message is sent. */
  conversationId: string | null;
  load: ConversationLoad;
}

export const initialChatState: ChatState = { messages: [], conversationId: null, load: { status: "idle" } };

export type ChatAction =
  | {
      type: "submit";
      conversationId: string;
      userId: string;
      assistantId: string;
      prompt: string;
      mode: ChatMode;
      now: number;
    }
  | { type: "retry"; id: string; now: number }
  | { type: "append"; id: string; text: string }
  | { type: "streamFinished"; id: string; outcome: StreamOutcome }
  | { type: "agentResolved"; id: string; response: AgentChatResponse }
  | { type: "failed"; id: string; error: string }
  | { type: "approvalSubmitting"; id: string; approved: boolean }
  | { type: "approvalResolved"; id: string; approved: boolean; response: AgentChatResponse }
  | { type: "approvalFailed"; id: string; error: string; closed: boolean }
  | { type: "reset" }
  | { type: "loadStarted"; conversationId: string }
  | { type: "loadSucceeded"; conversationId: string; items: ChatHistoryItem[]; now: number }
  | { type: "loadFailed"; conversationId: string; notFound: boolean; error: string };

function fromSavedTurns(items: ChatHistoryItem[], now: number): ChatMessage[] {
  return items.flatMap((item): ChatMessage[] => [
    { id: `${item.id}-q`, role: "user", content: item.message },
    {
      id: `${item.id}-a`,
      role: "assistant",
      mode: "history",
      prompt: item.message,
      content: item.response,
      status: "completed",
      startedAt: now,
    },
  ]);
}

function updateAssistant(
  state: ChatState,
  id: string,
  update: (message: AssistantMessage) => AssistantMessage,
): ChatState {
  return {
    ...state,
    messages: state.messages.map((message) =>
      message.id === id && message.role === "assistant" ? update(message) : message,
    ),
  };
}

function fromAgentResponse(message: AssistantMessage, response: AgentChatResponse): AssistantMessage {
  const awaiting = response.status === "awaiting_approval" && Boolean(response.approval?.length);

  return {
    ...message,
    content: response.response,
    status: awaiting ? "awaiting_approval" : "completed",
    route: response.route,
    sources: response.sources,
    runId: response.run_id,
    approval: awaiting ? response.approval : message.approval,
    error: undefined,
  };
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "submit":
      return {
        ...state,
        conversationId: action.conversationId,
        messages: [
          ...state.messages,
          { id: action.userId, role: "user", content: action.prompt },
          {
            id: action.assistantId,
            role: "assistant",
            mode: action.mode,
            prompt: action.prompt,
            content: "",
            status: action.mode === "stream" ? "streaming" : "pending",
            startedAt: action.now,
          },
        ],
      };

    case "retry":
      return updateAssistant(state, action.id, (message) => ({
        ...message,
        content: "",
        status: message.mode === "stream" ? "streaming" : "pending",
        startedAt: action.now,
        route: undefined,
        sources: undefined,
        runId: undefined,
        approval: undefined,
        approvalState: undefined,
        error: undefined,
      }));

    case "append":
      return updateAssistant(state, action.id, (message) => ({
        ...message,
        content: message.content + action.text,
      }));

    case "streamFinished":
      return updateAssistant(state, action.id, (message) => {
        if (action.outcome === "completed") return { ...message, status: "completed" };
        if (action.outcome === "aborted") return { ...message, status: "stopped" };
        return {
          ...message,
          status: "interrupted",
          error: message.content
            ? "The connection was interrupted before the response finished."
            : "The response stream failed before any text arrived.",
        };
      });

    case "agentResolved":
      return updateAssistant(state, action.id, (message) => ({
        ...fromAgentResponse(message, action.response),
        approvalState: action.response.status === "awaiting_approval" ? { phase: "idle" } : undefined,
      }));

    case "failed":
      return updateAssistant(state, action.id, (message) => ({
        ...message,
        status: "failed",
        error: action.error,
      }));

    case "approvalSubmitting":
      return updateAssistant(state, action.id, (message) => ({
        ...message,
        approvalState: { phase: "submitting", approved: action.approved },
        error: undefined,
      }));

    case "approvalResolved":
      return updateAssistant(state, action.id, (message) => {
        const next = fromAgentResponse(message, action.response);
        const stillWaiting = next.status === "awaiting_approval";
        return {
          ...next,
          approvalState: stillWaiting ? { phase: "idle" } : { phase: "resolved", approved: action.approved },
        };
      });

    case "approvalFailed":
      return updateAssistant(state, action.id, (message) =>
        action.closed
          ? { ...message, status: "completed", approvalState: { phase: "closed", reason: action.error } }
          : { ...message, approvalState: { phase: "idle" }, error: action.error },
      );

    case "reset":
      return initialChatState;

    case "loadStarted":
      return { messages: [], conversationId: action.conversationId, load: { status: "loading" } };

    case "loadSucceeded":
      if (state.conversationId !== action.conversationId) return state;
      return { ...state, messages: fromSavedTurns(action.items, action.now), load: { status: "idle" } };

    case "loadFailed":
      if (state.conversationId !== action.conversationId) return state;
      return {
        ...state,
        load: action.notFound ? { status: "not_found" } : { status: "error", error: action.error },
      };
  }
}
