import { useState } from "react";

import { errorMessage } from "@/api/errors";
import { deleteDocument } from "@/api/rag";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { useToast } from "@/components/ui/Toast";

export function DeleteDocumentDialog({
  documentId,
  onClose,
  onDeleted,
}: {
  documentId: string | null;
  onClose: () => void;
  onDeleted: (documentId: string) => void;
}) {
  const toast = useToast();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function close() {
    if (submitting) return;
    setError(null);
    onClose();
  }

  async function onConfirm() {
    if (!documentId) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await deleteDocument(documentId);
      onDeleted(result.document_id);
      toast.show(
        result.chunks_deleted
          ? `Deleted “${result.document_id}” (${result.chunks_deleted} ${result.chunks_deleted === 1 ? "chunk" : "chunks"}).`
          : `No indexed chunks were found for “${result.document_id}”.`,
        result.chunks_deleted ? "success" : "info",
      );
      setSubmitting(false);
      onClose();
    } catch (caught) {
      setError(errorMessage(caught));
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={documentId !== null}
      onClose={close}
      title="Delete document?"
      description={
        <>
          All indexed chunks of <span className="break-all font-mono text-fg">{documentId}</span> will be removed. The
          assistant will no longer find it.
        </>
      }
      footer={
        <>
          <Button variant="ghost" onClick={close} disabled={submitting}>
            Cancel
          </Button>
          <Button variant="danger" onClick={() => void onConfirm()} loading={submitting}>
            Delete
          </Button>
        </>
      }
    >
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </Dialog>
  );
}
