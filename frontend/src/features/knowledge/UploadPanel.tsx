import { FileUp, X } from "lucide-react";
import { useId, useRef, useState, type DragEvent, type FormEvent } from "react";

import { errorMessage } from "@/api/errors";
import { uploadDocument } from "@/api/rag";
import { MAX_DOCUMENT_ID_CHARS, RAG_MAX_UPLOAD_BYTES, type IndexDocumentResponse, type Visibility } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { ErrorState } from "@/components/ui/States";
import { TextField } from "@/components/ui/TextField";
import { cn } from "@/lib/cn";
import { formatBytes } from "@/lib/format";

import { VISIBILITY_OPTIONS } from "./constants";
import { IndexResult } from "./shared";

const ACCEPTED_EXTENSIONS = [".txt", ".md", ".markdown", ".pdf"];

function validateFile(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!ACCEPTED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
    return `Unsupported file type. Use ${ACCEPTED_EXTENSIONS.join(", ")}.`;
  }
  if (file.size > RAG_MAX_UPLOAD_BYTES) return `File is larger than ${formatBytes(RAG_MAX_UPLOAD_BYTES)}.`;
  if (file.size === 0) return "File is empty.";
  return null;
}

export function UploadPanel({ onIndexed }: { onIndexed: (result: IndexDocumentResponse) => void }) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [documentId, setDocumentId] = useState("");
  const [visibility, setVisibility] = useState<Visibility>("private");
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IndexDocumentResponse | null>(null);

  function choose(next: File | undefined) {
    if (!next) return;
    setResult(null);
    setError(null);
    setFileError(validateFile(next));
    setFile(next);
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files[0]);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file || fileError || submitting) return;

    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const response = await uploadDocument(file, { documentId: documentId.trim() || undefined, visibility });
      setResult(response);
      onIndexed(response);
      setFile(null);
      setDocumentId("");
      if (inputRef.current) inputRef.current.value = "";
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "relative rounded-panel border border-dashed px-6 py-8 text-center transition-colors",
          dragging ? "border-accent bg-accent/5" : "border-border-strong hover:border-muted",
        )}
      >
        <FileUp className="mx-auto size-6 text-subtle" aria-hidden />
        <p className="mt-2.5 text-sm">
          <label htmlFor={inputId} className="cursor-pointer font-medium text-accent hover:underline">
            Choose a file
          </label>{" "}
          <span className="text-muted">or drag it here</span>
        </p>
        <p className="mt-1 text-xs text-subtle">
          TXT, Markdown, or PDF · up to {formatBytes(RAG_MAX_UPLOAD_BYTES)}
        </p>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(",")}
          className="sr-only"
          onChange={(event) => choose(event.target.files?.[0])}
        />
      </div>

      {file && (
        <div className="flex items-center gap-3 rounded-control border border-border bg-surface px-3 py-2 text-sm">
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium">{file.name}</p>
            <p className={cn("text-xs", fileError ? "text-danger" : "text-subtle")}>{fileError ?? formatBytes(file.size)}</p>
          </div>
          <button
            type="button"
            aria-label="Remove file"
            onClick={() => {
              setFile(null);
              setFileError(null);
              if (inputRef.current) inputRef.current.value = "";
            }}
            className="rounded p-1 text-muted hover:bg-hover hover:text-fg"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="Document ID (optional)"
          value={documentId}
          maxLength={MAX_DOCUMENT_ID_CHARS}
          onChange={(event) => setDocumentId(event.target.value)}
          hint="Reuse an ID to replace that document."
          className="font-mono"
        />
        <Select
          label="Visibility"
          value={visibility}
          options={VISIBILITY_OPTIONS}
          onChange={(event) => setVisibility(event.target.value as Visibility)}
        />
      </div>

      {error && <ErrorState title="Upload failed" message={error} />}

      <Button type="submit" variant="primary" loading={submitting} disabled={!file || Boolean(fileError)}>
        {submitting ? "Indexing…" : "Upload and index"}
      </Button>

      {result && <IndexResult result={result} />}
    </form>
  );
}
