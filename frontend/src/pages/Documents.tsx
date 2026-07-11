import { useState } from "react";
import { FileText, Trash2, FolderOpen } from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Button, Card, Chip, ConfidenceBadge, EmptyState } from "../kit/primitives";
import { JSONViewer } from "../kit/JSONViewer";
import { clearDocuments, downloadBlob, fieldsToCSV, readDocuments, StoredDoc } from "../lib/api";

/* v1 "Documents" nav — a working document library. The API is stateless by design,
   so this is your session's processed documents with their full structured results. */

export default function Documents() {
  const [docs, setDocs] = useState<StoredDoc[]>(readDocuments());
  const [open, setOpen] = useState<number | null>(null);

  return (
    <div>
      <PageHeader
        title="Documents"
        sub="Processed documents from this browser session, with their complete structured results (stored locally — the API keeps nothing)."
        actions={
          docs.length > 0 && (
            <Button variant="ghost" onClick={() => { clearDocuments(); setDocs([]); }}>
              <Trash2 size={14} /> Clear
            </Button>
          )
        }
      />
      {docs.length === 0 ? (
        <Card>
          <EmptyState icon={FolderOpen} title="No documents this session"
            hint="Process a document in the Workspace — it lands here with its full extraction result." />
        </Card>
      ) : (
        <div className="space-y-3">
          {docs.map((d, i) => (
            <Card key={d.ts}>
              <button className="flex w-full flex-wrap items-center gap-3 text-left" onClick={() => setOpen(open === i ? null : i)}>
                <FileText size={16} className="shrink-0 text-dim" />
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-body">{d.name}</span>
                <Chip tone="accent">{d.result.doc_type ?? "unknown"}</Chip>
                <Chip>{d.result.route}</Chip>
                {d.result.page_count != null && <Chip className="num">{d.result.page_count} p.</Chip>}
                <ConfidenceBadge value={d.result.confidence} />
                <span className="num text-[11.5px] text-muted">{new Date(d.ts).toLocaleString()}</span>
              </button>
              {open === i && (
                <div className="mt-4 space-y-3 border-t border-line pt-4">
                  <div className="flex gap-2">
                    <Button variant="secondary" onClick={() => downloadBlob(`${d.name}.json`, "application/json", JSON.stringify(d.result, null, 2))}>Export JSON</Button>
                    {d.result.fields && (
                      <Button variant="secondary" onClick={() => downloadBlob(`${d.name}.csv`, "text/csv", fieldsToCSV(d.result.fields!))}>Export CSV</Button>
                    )}
                  </div>
                  <JSONViewer data={d.result} maxHeight={320} />
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
