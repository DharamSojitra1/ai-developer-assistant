import { FileText, Inbox, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { MAX_DOCUMENT_ID_CHARS } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CopyButton } from "@/components/ui/CopyButton";
import { IconButton } from "@/components/ui/IconButton";
import { EmptyState } from "@/components/ui/States";
import { TextField } from "@/components/ui/TextField";
import { formatDateTime } from "@/lib/format";

import type { RecentDocument } from "./recentDocuments";
import { DOC_TYPE_LABELS } from "./constants";

export function ManagePanel({ documents, onDelete }: { documents: RecentDocument[]; onDelete: (documentId: string) => void }) {
  const [documentId, setDocumentId] = useState("");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = documentId.trim();
    if (trimmed) onDelete(trimmed);
  }

  return (
    <div className="space-y-10">
      <section aria-labelledby="recent-docs">
        <h3 id="recent-docs" className="text-sm font-semibold">
          Indexed from this browser
        </h3>
        <p className="mt-1 text-sm text-muted">
          The API doesn't list documents, so this shows what you've added here. Use search to find everything else.
        </p>

        {documents.length === 0 ? (
          <EmptyState
            className="mt-4 rounded-panel border border-dashed border-border"
            icon={<Inbox />}
            title="Nothing indexed here yet"
            description="Documents you upload or paste from this browser will be listed here."
          />
        ) : (
          <ul className="mt-4 divide-y divide-border rounded-panel border border-border">
            {documents.map((document) => (
              <li key={document.document_id} className="flex items-center gap-3 px-4 py-3">
                <FileText className="size-4 shrink-0 text-subtle" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{document.source}</p>
                  <p className="truncate font-mono text-xs text-subtle">{document.document_id}</p>
                </div>
                <div className="hidden items-center gap-1.5 md:flex">
                  <Badge>{DOC_TYPE_LABELS[document.doc_type] ?? document.doc_type}</Badge>
                  <Badge tone={document.visibility === "shared" ? "accent" : "neutral"}>{document.visibility}</Badge>
                  <span className="ml-1 text-xs text-subtle">{formatDateTime(new Date(document.indexed_at))}</span>
                </div>
                <CopyButton text={document.document_id} label="Copy document ID" />
                <IconButton size="sm" label={`Delete ${document.source}`} icon={<Trash2 />} onClick={() => onDelete(document.document_id)} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="delete-by-id">
        <h3 id="delete-by-id" className="text-sm font-semibold">
          Delete by document ID
        </h3>
        <p className="mt-1 text-sm text-muted">Remove any document you own, even one indexed elsewhere.</p>
        <form onSubmit={onSubmit} className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <TextField
              label="Document ID"
              value={documentId}
              maxLength={MAX_DOCUMENT_ID_CHARS}
              onChange={(event) => setDocumentId(event.target.value)}
              className="font-mono"
            />
          </div>
          <Button type="submit" variant="danger" disabled={!documentId.trim()} icon={<Trash2 className="size-4" />}>
            Delete
          </Button>
        </form>
      </section>
    </div>
  );
}
