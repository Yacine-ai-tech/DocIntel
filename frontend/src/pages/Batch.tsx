import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Layers, ChevronDown, ChevronRight, FilePlus2 } from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Button, Card, Chip, ConfidenceBadge, EmptyState } from "../kit/primitives";
import { Label, Segmented, Select } from "../kit/misc";
import { JSONViewer } from "../kit/JSONViewer";
import { api, BatchResults, BatchStatus, logActivity } from "../lib/api";

const ROUTES = [
  { value: "vision_premium", label: "Claude Vision" },
  { value: "vision_local", label: "Local Vision" },
  { value: "ocr_fallback", label: "OCR + LLM" },
];
const DOC_TYPES = ["invoice", "receipt", "contract", "financial_report", "default"].map((v) => ({
  value: v,
  label: v.replace("_", " "),
}));

type Job = { id: string; total: number; status?: BatchStatus; results?: BatchResults };

export default function Batch() {
  const [files, setFiles] = useState<File[]>([]);
  const [route, setRoute] = useState("vision_premium");
  const [docType, setDocType] = useState("invoice");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // poll running jobs
  useEffect(() => {
    const running = jobs.filter((j) => !j.results && j.status?.status !== "failed");
    if (running.length === 0) return;
    const t = setInterval(async () => {
      for (const j of running) {
        try {
          const status = await api.batchStatus(j.id);
          let results: BatchResults | undefined;
          if (status.status === "completed" || status.processed + status.failed >= status.total) {
            results = await api.batchResults(j.id);
          }
          setJobs((all) => all.map((x) => (x.id === j.id ? { ...x, status, results: results ?? x.results } : x)));
        } catch { /* transient poll error — keep trying */ }
      }
    }, 1500);
    return () => clearInterval(t);
  }, [jobs]);

  const start = async () => {
    if (files.length === 0) return;
    setBusy(true);
    try {
      const { job_id, total } = await api.batchUpload(files, route, docType);
      setJobs((j) => [{ id: job_id, total }, ...j]);
      logActivity({ kind: "batch", title: `Batch of ${total} files`, meta: { job_id, route, doc_type: docType } });
      setFiles([]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Batch processing"
        sub="Process a folder's worth of documents concurrently. Jobs run in the background on the server; progress below is live."
      />

      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <Label>Files</Label>
            <Button variant="secondary" onClick={() => inputRef.current?.click()}>
              <FilePlus2 size={14} />
              {files.length ? `${files.length} file${files.length > 1 ? "s" : ""} selected` : "Choose files"}
            </Button>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg,.tiff"
              className="hidden"
              onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
            />
          </div>
          <div>
            <Label>Route</Label>
            <Segmented value={route} onChange={setRoute} options={ROUTES} />
          </div>
          <div>
            <Label>Document type</Label>
            <Select value={docType} onChange={setDocType} options={DOC_TYPES} />
          </div>
          <Button onClick={start} disabled={files.length === 0 || busy}>
            <Layers size={14} /> Start batch
          </Button>
        </div>
      </Card>

      <div className="mt-5 space-y-4">
        {jobs.length === 0 ? (
          <Card>
            <EmptyState
              icon={Layers}
              title="No batch jobs this session"
              hint="Select several documents and start a batch — each file is processed with per-file error isolation."
            />
          </Card>
        ) : (
          jobs.map((j) => <JobCard key={j.id} job={j} />)
        )}
      </div>
    </div>
  );
}

function JobCard({ job }: { job: Job }) {
  const s = job.status;
  const done = !!job.results;
  const pct = s ? Math.round(((s.processed + s.failed) / Math.max(s.total, 1)) * 100) : 0;
  return (
    <Card
      title={<span className="num">Job {job.id.slice(0, 8)}</span>}
      actions={
        <div className="flex items-center gap-2">
          {s && s.failed > 0 && <Chip tone="bad">{s.failed} failed</Chip>}
          <Chip tone={done ? "ok" : "warn"}>{done ? "completed" : (s?.status ?? "queued")}</Chip>
        </div>
      }
    >
      <div className="mb-2 flex items-center justify-between text-xs text-muted">
        <span className="num">
          {s ? `${s.processed + s.failed} / ${s.total}` : `0 / ${job.total}`} documents
        </span>
        <span className="num">{done ? 100 : pct}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
        <motion.div
          className="h-full rounded-full"
          style={{ background: "var(--accent-grad)" }}
          animate={{ width: `${done ? 100 : pct}%` }}
          transition={{ duration: 0.4 }}
        />
      </div>

      {job.results && (
        <div className="mt-4 divide-y divide-[var(--border)] rounded-xl border border-line">
          {job.results.results.map((r, i) => (
            <ResultRow key={i} r={r} />
          ))}
        </div>
      )}
    </Card>
  );
}

function ResultRow({ r }: { r: BatchResults["results"][number] }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface-2"
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <ChevronDown size={14} className="text-muted" /> : <ChevronRight size={14} className="text-muted" />}
        <span className="min-w-0 flex-1 truncate text-sm text-body">{r.filename}</span>
        {r.page_count != null && <span className="num text-xs text-muted">{r.page_count} p.</span>}
        <ConfidenceBadge value={r.confidence} />
      </button>
      {open && (
        <div className="px-4 pb-4">
          <JSONViewer data={r.fields ?? {}} maxHeight={280} />
        </div>
      )}
    </div>
  );
}
