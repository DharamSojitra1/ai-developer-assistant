import { useCallback, useEffect, useState } from "react";

import type { DocumentType, IndexDocumentResponse, Visibility } from "@/api/types";

/**
 * The API has no endpoint to list documents, so this keeps the results of
 * uploads made from this browser, per account. It is a convenience list,
 * not the source of truth.
 */
export interface RecentDocument {
  document_id: string;
  source: string;
  doc_type: DocumentType;
  visibility: Visibility;
  chunks_indexed: number;
  indexed_at: string;
}

const MAX_ENTRIES = 50;
const CHANGE_EVENT = "ada:recent-documents";

function storageKey(email: string | null): string {
  return `ada.indexed_documents:${email ?? "anonymous"}`;
}

function read(email: string | null): RecentDocument[] {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(storageKey(email)) ?? "[]");
    return Array.isArray(parsed) ? (parsed as RecentDocument[]) : [];
  } catch {
    return [];
  }
}

function write(email: string | null, documents: RecentDocument[]): void {
  try {
    window.localStorage.setItem(storageKey(email), JSON.stringify(documents.slice(0, MAX_ENTRIES)));
  } catch {
    // Best effort only.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function useRecentDocuments(email: string | null) {
  const [documents, setDocuments] = useState<RecentDocument[]>(() => read(email));

  useEffect(() => {
    const sync = () => setDocuments(read(email));
    sync();
    window.addEventListener(CHANGE_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(CHANGE_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [email]);

  const record = useCallback(
    (result: IndexDocumentResponse) => {
      const entry: RecentDocument = {
        document_id: result.document_id,
        source: result.source,
        doc_type: result.doc_type,
        visibility: result.visibility,
        chunks_indexed: result.chunks_indexed,
        indexed_at: new Date().toISOString(),
      };
      write(email, [entry, ...read(email).filter((item) => item.document_id !== entry.document_id)]);
    },
    [email],
  );

  const forget = useCallback(
    (documentId: string) => write(email, read(email).filter((item) => item.document_id !== documentId)),
    [email],
  );

  return { documents, record, forget };
}
