import { apiJson } from "./client";
import type {
  DeleteDocumentResponse,
  IndexDocumentRequest,
  IndexDocumentResponse,
  SearchRequest,
  SearchResponse,
  Visibility,
} from "./types";

export function uploadDocument(
  file: File,
  options: { documentId?: string; visibility: Visibility },
): Promise<IndexDocumentResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("visibility", options.visibility);
  if (options.documentId) form.append("document_id", options.documentId);

  return apiJson<IndexDocumentResponse>("/api/rag/upload", { method: "POST", body: form });
}

export function indexText(body: IndexDocumentRequest): Promise<IndexDocumentResponse> {
  return apiJson<IndexDocumentResponse>("/api/rag/index", { method: "POST", json: body });
}

export function searchDocuments(body: SearchRequest, signal?: AbortSignal): Promise<SearchResponse> {
  return apiJson<SearchResponse>("/api/rag/search", { method: "POST", json: body, signal });
}

export function deleteDocument(documentId: string): Promise<DeleteDocumentResponse> {
  return apiJson<DeleteDocumentResponse>(`/api/rag/documents/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
  });
}
