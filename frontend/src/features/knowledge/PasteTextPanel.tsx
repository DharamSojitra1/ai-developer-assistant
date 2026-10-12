import { useState, type FormEvent } from "react";

import { errorMessage } from "@/api/errors";
import { indexText } from "@/api/rag";
import { MAX_DOCUMENT_ID_CHARS, MAX_SOURCE_CHARS, type IndexDocumentResponse, type Visibility } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { ErrorState } from "@/components/ui/States";
import { fieldClass, TextField } from "@/components/ui/TextField";
import { cn } from "@/lib/cn";

import { VISIBILITY_OPTIONS } from "./constants";
import { IndexResult } from "./shared";

export function PasteTextPanel({ onIndexed }: { onIndexed: (result: IndexDocumentResponse) => void }) {
  const [text, setText] = useState("");
  const [source, setSource] = useState("");
  const [docType, setDocType] = useState<"text" | "markdown">("markdown");
  const [documentId, setDocumentId] = useState("");
  const [visibility, setVisibility] = useState<Visibility>("private");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IndexDocumentResponse | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim() || submitting) return;

    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const response = await indexText({
        text,
        source: source.trim() || undefined,
        doc_type: docType,
        document_id: documentId.trim() || undefined,
        visibility,
      });
      setResult(response);
      onIndexed(response);
      setText("");
      setDocumentId("");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="Source name"
          placeholder="e.g. deployment-guide.md"
          value={source}
          maxLength={MAX_SOURCE_CHARS}
          onChange={(event) => setSource(event.target.value)}
          hint="Shown with search results. Defaults to “api”."
        />
        <Select
          label="Format"
          value={docType}
          options={[
            { value: "markdown", label: "Markdown" },
            { value: "text", label: "Plain text" },
          ]}
          onChange={(event) => setDocType(event.target.value as "text" | "markdown")}
          hint="Markdown is split along its headings."
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="paste-text" className="block text-[0.8125rem] font-medium">
          Content
        </label>
        <textarea
          id="paste-text"
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={10}
          required
          placeholder="Paste documentation, notes, or any text the assistant should know about."
          className={cn(fieldClass, "min-h-48 resize-y py-2.5 font-mono text-[0.8125rem] leading-6")}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="Document ID (optional)"
          value={documentId}
          maxLength={MAX_DOCUMENT_ID_CHARS}
          onChange={(event) => setDocumentId(event.target.value)}
          className="font-mono"
        />
        <Select
          label="Visibility"
          value={visibility}
          options={VISIBILITY_OPTIONS}
          onChange={(event) => setVisibility(event.target.value as Visibility)}
        />
      </div>

      {error && <ErrorState title="Indexing failed" message={error} />}

      <Button type="submit" variant="primary" loading={submitting} disabled={!text.trim()}>
        {submitting ? "Indexing…" : "Index text"}
      </Button>

      {result && <IndexResult result={result} />}
    </form>
  );
}
