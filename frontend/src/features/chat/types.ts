import type { AgentRoute, ApprovalRequest, SourceReference } from "@/api/types";

export type ChatMode = "agent" | "stream";

export type AssistantStatus =
  | "pending"
  | "streaming"
  | "completed"
  | "awaiting_approval"
  | "failed"
  | "interrupted"
  | "stopped";

export type ApprovalState =
  | { phase: "idle" }
  | { phase: "submitting"; approved: boolean }
  | { phase: "resolved"; approved: boolean }
  | { phase: "closed"; reason: string };

export interface UserMessage {
  id: string;
  role: "user";
  content: string;
}

export interface AssistantMessage {
  id: string;
  role: "assistant";
  /** `history` marks a reply loaded from a saved conversation. */
  mode: ChatMode | "history";
  prompt: string;
  content: string;
  status: AssistantStatus;
  startedAt: number;
  route?: AgentRoute | null;
  sources?: SourceReference[];
  runId?: string;
  approval?: ApprovalRequest[] | null;
  approvalState?: ApprovalState;
  error?: string;
}

export type ChatMessage = UserMessage | AssistantMessage;

export function isAssistant(message: ChatMessage): message is AssistantMessage {
  return message.role === "assistant";
}
