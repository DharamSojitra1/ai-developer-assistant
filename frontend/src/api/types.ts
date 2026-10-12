// Mirrors the Pydantic models in app/schemas.py and app/routes/usage.py.

/** Backend default of CHAT_MAX_MESSAGE_CHARS. */
export const CHAT_MAX_MESSAGE_CHARS = 8000;
/** Backend default of RAG_MAX_UPLOAD_BYTES. */
export const RAG_MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
export const MAX_SEARCH_QUERY_CHARS = 500;
export const MAX_DOCUMENT_ID_CHARS = 128;
export const MAX_SOURCE_CHARS = 255;
export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_LENGTH = 128;

// Auth
export interface UserRegisterRequest {
  email: string;
  password: string;
}

export interface UserResponse {
  id: string;
  email: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

// Chat
export interface ChatRequest {
  message: string;
  temperature?: number;
  max_tokens?: number;
  /** Context comes only from earlier messages in this conversation. */
  conversation_id?: string;
}

export interface SourceReference {
  document_id: string;
  text: string;
}

export interface ChatHistoryItem {
  id: string;
  message: string;
  response: string;
  model: string;
  created_at: string;
  conversation_id?: string | null;
}

export interface ChatHistoryResponse {
  count: number;
  history: ChatHistoryItem[];
}

export interface ConversationSummary {
  id: string;
  /** The conversation's first message, shortened by the server. */
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationListResponse {
  count: number;
  conversations: ConversationSummary[];
}

export interface ConversationDetail {
  id: string;
  /** Oldest first. */
  messages: ChatHistoryItem[];
}

export interface DeleteHistoryResponse {
  deleted: number;
}

// Agent
export type AgentRoute = "knowledge_base" | "calculation" | "chat" | "multi_agent" | "general";
export type AgentRunStatus = "completed" | "awaiting_approval";

export interface ApprovalRequest {
  tool_call_id: string;
  action: string;
  document_id: string;
  source: string | null;
  found: boolean;
}

export interface AgentChatResponse {
  response: string;
  sources: SourceReference[];
  run_id: string;
  conversation_id?: string | null;
  route: AgentRoute | null;
  status: AgentRunStatus;
  approval: ApprovalRequest[] | null;
}

export interface ApprovalDecision {
  approved: boolean;
}

// RAG
export type DocumentType = "text" | "markdown" | "pdf";
export type Visibility = "shared" | "private";

export interface IndexDocumentRequest {
  text: string;
  document_id?: string;
  source?: string;
  doc_type?: "text" | "markdown";
  visibility?: Visibility;
}

export interface IndexDocumentResponse {
  document_id: string;
  status: "indexed" | "unchanged";
  chunks_indexed: number;
  chunks_embedded: number;
  source: string;
  doc_type: DocumentType;
  visibility: Visibility;
}

export interface SearchRequest {
  query: string;
  top_k?: number;
  source?: string;
  doc_type?: DocumentType;
}

/** Chunk metadata stored by RAGService.index_document. */
export interface ChunkMetadata {
  document_id?: string;
  source?: string;
  doc_type?: DocumentType;
  visibility?: Visibility;
  section?: string;
  chunk_index?: number;
  [key: string]: unknown;
}

export interface SearchResult {
  id: string;
  text: string;
  distance: number | null;
  keyword_score: number | null;
  rerank_score: number | null;
  metadata: ChunkMetadata;
}

export interface SearchResponse {
  results: SearchResult[];
}

export interface DeleteDocumentResponse {
  document_id: string;
  chunks_deleted: number;
}

// Usage
export interface UsageTotals {
  requests: number;
  llm_calls: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export interface DailyUsage extends UsageTotals {
  date: string;
}

export interface UsageResponse {
  days: number;
  totals: UsageTotals;
  daily: DailyUsage[];
}
