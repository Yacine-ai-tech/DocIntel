import React, { useCallback, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  UploadCloud, FileText, Braces, LayoutGrid, RotateCw, Download, Copy, Check,
  ScanSearch, GitBranch, Table2, ShieldCheck, AlertTriangle,
} from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Button, Card, Chip, ConfidenceBadge, EmptyState } from "../kit/primitives";
import { PipelineFlow } from "../kit/PipelineFlow";
import { ExecutionStages, Label, Segmented, Select } from "../kit/misc";
import { JSONViewer } from "../kit/JSONViewer";
import { api, downloadBlob, fieldsToCSV, logActivity, ProcessResponse } from "../lib/api";

const ROUTES = [
  { value: "vision_premium", label: "Claude Vision", hint: "Best accuracy · cloud · multilingual" },
  { value: "vision_local", label: "Local Vision", hint: "Private · zero API cost · GPU host" },
  { value: "ocr_fallback", label: "OCR + LLM", hint: "Fast · lightweight · clean documents" },
];

const DOC_TYPES = ["auto", "invoice", "receipt", "contract", "financial_report", "default"].map(
  (v) => ({ value: v, label: v === "auto" ? "Auto-detect" : v.replace("_", " ") }),
);

const STAGES = [
  { id: "upload", label: "Upload", icon: UploadCloud },
  { id: "classify", label: "Classify", icon: ScanSearch },
  { id: "route", label: "Route", icon: GitBranch },
  { id: "extract", label: "Extract", icon: FileText },
  { id: "validate", label: "Validate", icon: ShieldCheck },
];

type Phase = "idle" | "working" | "done" | "error";

export default function Workspace() {
  const [file, setFile] = useState<File | null>(null);
  const [previewURL, setPreviewURL] = useState<string | null>(null);
  const [route, setRoute] = useState("vision_premium");
  const [docType, setDocType] = useState("auto");
  const [phase, setPhase] = useState<Phase>("idle");
  const [stage, setStage] = useState(0);
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [errMsg, setErrMsg] = useState("");
  const [showJSON, setShowJSON] = useState(false);
  const [edited, setEdited] = useState<Record<string, string>>({});
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const timers = useRef<number[]>([]);

  const pickFile = useCallback((f: File | null) => {
    if (!f) return;
    setFile(f);
    setPreviewURL((old) => {
      if (old) URL.revokeObjectURL(old);
      return URL.createObjectURL(f);
    });
    setPhase("idle");
    setResult(null);
    setEdited({});
  }, []);

  const run = useCallback(async () => {
    if (!file) return;
    setPhase("working");
    setStage(0);
    setErrMsg("");
    setResult(null);
    setEdited({});
    // No per-stage timing in the API (see GAP_REPORT §2): progress the first stages on a
    // timer while the single /process call runs, then fill final state from the real response.
    timers.current.forEach(clearTimeout);
    timers.current = [1, 2, 3].map((i) =>
      window.setTimeout(() => setStage((s) => Math.max(s, i)), i * 900),
    );
    try {
      const res = await api.process(file, route, docType);
      timers.current.forEach(clearTimeout);
      setStage(STAGES.length - 1);
      setResult(res);
      setPhase(res.error || res.fields?.error ? "error" : "done");
      logActivity({
        kind: "process",
        title: file.name,
        meta: {
          route: res.route, doc_type: res.doc_type, confidence: res.confidence,
          pages: res.page_count, ms: res.processing_time_ms,
          fallback: (res.fields as Record<string, unknown>)?._fallback_from ?? null,
        },
      });
    } catch (e) {
      timers.current.forEach(clearTimeout);
      setErrMsg(e instanceof Error ? e.message : String(e));
      setPhase("error");
    }
  }, [file, route, docType]);

  const fields = useMemo(() => {
    const f = result?.fields;
    if (!f || typeof f !== "object") return [];
    return Object.entries(f).filter(([k]) => !k.startsWith("_") && k !== "error" && k !== "note");
  }, [result]);

  const metaFields = (result?.fields ?? {}) as Record<string, unknown>;
  const fallbackFrom = metaFields._fallback_from as string | undefined;
  const note = metaFields._note as string | undefined;

  const exportJSON = () =>
    result && downloadBlob(`${file?.name ?? "document"}.json`, "application/json", JSON.stringify(result, null, 2));
  const exportCSV = () =>
    result?.fields && downloadBlob(`${file?.name ?? "document"}.csv`, "text/csv", fieldsToCSV(result.fields));

  return (
    <div>
      <PageHeader
        title={greeting()}
        sub="Upload a document. DocIntel classifies it, routes it to the right vision model, and returns structured, validated data."
      />

      {/* controls */}
      <div className="mb-4 flex flex-wrap items-end gap-4">
        <div>
          <Label>Extraction route</Label>
          <Segmented value={route} onChange={setRoute} options={ROUTES} />
        </div>
        <div>
          <Label>Document type</Label>
          <Select value={docType} onChange={setDocType} options={DOC_TYPES} />
        </div>
        {file && (
          <Button onClick={run} disabled={phase === "working"}>
            <RotateCw size={14} className={phase === "working" ? "animate-spin" : ""} />
            {phase === "working" ? "Processing…" : result ? "Re-run" : "Analyze"}
          </Button>
        )}
      </div>

      {/* upload zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files[0] ?? null); }}
        onClick={() => !file && inputRef.current?.click()}
        className={`relative overflow-hidden rounded-panel border transition-all duration-200 ${
          dragging ? "border-[var(--accent)] shadow-card" : "border-line"
        } ${!file ? "cursor-pointer hover:border-line-strong" : ""} bg-surface`}
        style={dragging ? { boxShadow: "0 0 0 3px rgba(199,154,45,.25)" } : undefined}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.tiff,.webp"
          className="hidden"
          onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
        />

        {!file ? (
          <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
            <motion.div
              animate={{ y: [0, -4, 0] }}
              transition={{ repeat: Infinity, duration: 2.4, ease: "easeInOut" }}
              className="flex h-14 w-14 items-center justify-center rounded-2xl border border-line-strong"
              style={{ color: "var(--accent)" }}
            >
              <UploadCloud size={24} strokeWidth={1.6} />
            </motion.div>
            <div className="text-[15px] font-semibold text-body">Drop your document here</div>
            <div className="text-[13px] text-muted">or click to browse — PDF · PNG · JPEG · TIFF</div>
          </div>
        ) : (
          <div className="p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <FileText size={18} className="text-dim" />
                <div>
                  <div className="text-sm font-semibold text-body">{file.name}</div>
                  <div className="text-xs text-muted">{(file.size / 1024).toFixed(0)} KB</div>
                </div>
              </div>
              <Button variant="ghost" onClick={() => inputRef.current?.click()}>
                Choose another file
              </Button>
            </div>
            <PipelineFlow stages={STAGES} active={stage} done={phase === "done"} error={phase === "error"} />
            {phase === "working" && (
              <div className="mt-3 border-t border-line pt-3">
                <ExecutionStages
                  stages={["Reading document", "Detecting type & layout", "Selecting model route", "Extracting fields", "Validating output"]}
                  active={Math.min(stage, 4)}
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* error */}
      <AnimatePresence>
        {phase === "error" && (
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-4">
            <Card>
              <div className="flex items-start gap-3">
                <AlertTriangle size={17} className="mt-0.5 shrink-0 text-bad" />
                <div>
                  <div className="text-sm font-semibold text-body">Extraction failed</div>
                  <div className="mt-1 text-[13px] text-dim">
                    {errMsg || String(metaFields.error ?? "Unknown error")} {note && `— ${note}`}
                  </div>
                </div>
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* results */}
      <AnimatePresence>
        {phase === "done" && result && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="mt-6"
          >
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Chip tone="accent" title="document type">{result.doc_type ?? "unknown"}</Chip>
              <Chip title="route actually used">
                <GitBranch size={11} /> {fallbackFrom ? `OCR fallback (from ${fallbackFrom})` : result.route}
              </Chip>
              {result.page_count != null && <Chip>{result.page_count} page{result.page_count === 1 ? "" : "s"}</Chip>}
              {typeof metaFields._tables_detected === "number" && (
                <Chip><Table2 size={11} /> {String(metaFields._tables_detected)} tables</Chip>
              )}
              {result.processing_time_ms != null && (
                <Chip className="num">{(result.processing_time_ms / 1000).toFixed(1)}s</Chip>
              )}
              <ConfidenceBadge value={result.confidence} />
              <div className="ml-auto flex items-center gap-2">
                <Segmented
                  value={showJSON ? "json" : "cards"}
                  onChange={(v) => setShowJSON(v === "json")}
                  options={[
                    { value: "cards", label: <span className="flex items-center gap-1"><LayoutGrid size={12} /> Cards</span> },
                    { value: "json", label: <span className="flex items-center gap-1"><Braces size={12} /> JSON</span> },
                  ]}
                />
                <Button variant="secondary" onClick={exportJSON}><Download size={13} /> JSON</Button>
                <Button variant="secondary" onClick={exportCSV}><Download size={13} /> CSV</Button>
              </div>
            </div>

            {note && (
              <div className="mb-3 rounded-xl border border-line bg-surface px-4 py-2.5 text-[13px] text-warn">
                {note}
              </div>
            )}

            <div className="grid gap-4 lg:grid-cols-2">
              <Card title="Document">
                {previewURL && file?.type.startsWith("image/") ? (
                  <img src={previewURL} alt={file.name} className="max-h-[520px] w-full rounded-lg object-contain" />
                ) : previewURL && file?.type === "application/pdf" ? (
                  <object data={previewURL} type="application/pdf" className="h-[520px] w-full rounded-lg">
                    <EmptyState icon={FileText} title="PDF preview unavailable in this browser" />
                  </object>
                ) : (
                  <EmptyState icon={FileText} title="No preview" />
                )}
              </Card>

              <Card title={showJSON ? "Structured output" : "Extracted fields"}>
                {showJSON ? (
                  <JSONViewer data={result} maxHeight={520} />
                ) : fields.length === 0 ? (
                  <EmptyState title="No fields extracted" hint={note ?? "Try the Claude Vision route for difficult documents."} />
                ) : (
                  <div className="max-h-[520px] space-y-2 overflow-y-auto pr-1">
                    {fields.map(([k, v]) => (
                      <FieldRow
                        key={k}
                        name={k}
                        value={edited[k] ?? (typeof v === "object" ? JSON.stringify(v) : String(v ?? ""))}
                        onChange={(val) => setEdited((e) => ({ ...e, [k]: val }))}
                      />
                    ))}
                  </div>
                )}
              </Card>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function FieldRow({ name, value, onChange }: { name: string; value: string; onChange: (v: string) => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="group flex items-center gap-3 rounded-xl border border-line bg-surface-2 px-3.5 py-2.5">
      <div className="w-32 shrink-0 truncate text-xs font-medium uppercase tracking-wide text-muted" title={name}>
        {name.replace(/_/g, " ")}
      </div>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="num min-w-0 flex-1 bg-transparent text-sm text-body outline-none"
      />
      <button
        className="opacity-0 transition-opacity group-hover:opacity-100"
        onClick={() => { navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1000); }}
        aria-label={`copy ${name}`}
      >
        {copied ? <Check size={13} className="text-ok" /> : <Copy size={13} className="text-muted hover:text-body" />}
      </button>
    </div>
  );
}

function greeting() {
  const h = new Date().getHours();
  const g = h < 12 ? "Good morning." : h < 18 ? "Good afternoon." : "Good evening.";
  return `${g} Ready to analyze documents.`;
}
