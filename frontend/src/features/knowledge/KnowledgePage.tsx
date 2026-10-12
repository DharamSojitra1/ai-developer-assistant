import { FolderCog, Plus, Search } from "lucide-react";
import { useState } from "react";

import { useAuth } from "@/auth/useAuth";
import { TopBar } from "@/components/layout/TopBar";
import { Tabs } from "@/components/ui/Tabs";

import { DeleteDocumentDialog } from "./DeleteDocumentDialog";
import { ManagePanel } from "./ManagePanel";
import { PasteTextPanel } from "./PasteTextPanel";
import { useRecentDocuments } from "./recentDocuments";
import { SearchPanel } from "./SearchPanel";
import { UploadPanel } from "./UploadPanel";

type Section = "add" | "search" | "manage";
type AddMethod = "upload" | "paste";

export default function KnowledgePage() {
  const { email } = useAuth();
  const { documents, record, forget } = useRecentDocuments(email);
  const [section, setSection] = useState<Section>("add");
  const [method, setMethod] = useState<AddMethod>("upload");
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  return (
    <>
      <TopBar />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 pb-16 pt-2 sm:px-6 lg:pt-6">
          <header>
            <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">Knowledge base</h1>
            <p className="mt-1.5 max-w-2xl text-sm leading-6 text-muted">
              Documents you add here are split into passages and searched by the agent when it answers. Private documents
              are only visible to you.
            </p>
          </header>

          <div className="mt-6">
            <Tabs
              label="Knowledge base sections"
              value={section}
              onChange={setSection}
              items={[
                { value: "add", label: "Add documents", icon: <Plus /> },
                { value: "search", label: "Search", icon: <Search /> },
                { value: "manage", label: "Manage", icon: <FolderCog /> },
              ]}
            />
          </div>

          <div role="tabpanel" className="pt-6">
            {section === "add" && (
              <>
                <Tabs
                  label="How to add a document"
                  variant="pill"
                  value={method}
                  onChange={setMethod}
                  items={[
                    { value: "upload", label: "Upload file" },
                    { value: "paste", label: "Paste text" },
                  ]}
                />
                <div className="mt-5">
                  {method === "upload" ? <UploadPanel onIndexed={record} /> : <PasteTextPanel onIndexed={record} />}
                </div>
              </>
            )}
            {section === "search" && <SearchPanel onDelete={setPendingDelete} />}
            {section === "manage" && <ManagePanel documents={documents} onDelete={setPendingDelete} />}
          </div>
        </div>
      </div>

      <DeleteDocumentDialog documentId={pendingDelete} onClose={() => setPendingDelete(null)} onDeleted={forget} />
    </>
  );
}
