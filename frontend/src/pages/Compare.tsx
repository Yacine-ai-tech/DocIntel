import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { FileText, GitCompareArrows, AlertTriangle } from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Button, Card, Chip, ConfidenceBadge, EmptyState } from "../kit/primitives";
import { ExecutionStages, Label, Select } from "../kit/misc";
import { api, ProcessResponse } from "../lib/api";

/* v1 "Compare outputs / switch AI model" — the same document through two REAL routes,
   side by side. Two live /process calls, nothing simulated. */

const ROUTE_OPTS = [
  { value: "vision_premium", label: "Claude Vision (premium)" },
  { value: "vision_local", label: "Local vision (qwen2.5-VL)" },
  { value: "ocr_fallback", label: "OCR + LLM cleanup" },
];
const DOC_TYPES = ["auto", "invoice", "receipt", "contract", "financial_report", "default"].map(
  (v) => ({ value: v, label: v === "auto" ? "Auto-detect" : v.replace("_", " ") }),
);

export default function Compare() {
  const [file, setFile] = useState<File | null>(null);
  const [routeA, setRouteA] = useState("vision_premium");
  const [routeB, setRouteB] = useState("ocr_fallback");
  const [docType, setDocType] = useState("auto");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [results, setResults] = useState<[ProcessResponse, ProcessResponse] | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const run = async () => {
    if (!file) return;
    setBusy(true); setErr(""); setResults(null);
    try {
      const [a, b] = await Promise.all([
        api.process(file, routeA, docType),
        api.process(file, routeB, docType),
      ]);
      setResults([a, b]);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  };

  const fieldKeys = results
    ? [...new Set(results.flatMap((r) => Object.keys(r.fields ?? {}).filter((k) => !k.startsWith("_"))))]
    : [];

  return (
    <div>
      <PageHeader
        title="Compare routes"
        sub="Run one document through two extraction routes simultaneously and compare fields, confidence and latency — both calls are live."
      />

      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <Label>Document</Label>
            <Button variant="secondary" onClick={() => inputRef.current?.click()}>
              <FileText size={14} /> {file ? file.name : "Choose file"}
            </Button>
            <input ref={inputRef} type="file" accept=".pdf,.png,.jpg,.jpeg,.tiff,.webp" className="hidden"
              onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResults(null); }} />
          </div>
          <div><Label>Route A</Label><Select value={routeA} onChange={setRouteA} options={ROUTE_OPTS} /></div>
          <div><Label>Route B</Label><Select value={routeB} onChange={setRouteB} options={ROUTE_OPTS} /></div>
          <div><Label>Document type</Label><Select value={docType} onChange={setDocType} options={DOC_TYPES} /></div>
          <Button onClick={run} disabled={!file || busy || routeA === routeB}>
            <GitCompareArrows size={14} /> {busy ? "Running both…" : "Compare"}
          </Button>
        </div>
        {routeA === routeB && <p className="mt-2 text-[12px] text-warn">Pick two different routes.</p>}
      </Card>

      {busy && (
        <Card className="mt-4">
          <ExecutionStages stages={[`Route A — ${routeA}`, `Route B — ${routeB}`, "Aligning fields"]} active={1} />
        </Card>
      )}
      {err && (
        <Card className="mt-4">
          <div className="flex items-start gap-3"><AlertTriangle size={16} className="mt-0.5 text-bad" /><div className="text-[13px] text-dim">{err}</div></div>
        </Card>
      )}

      {results && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mt-5">
          <div className="grid grid-cols-[1fr_repeat(2,minmax(0,1.2fr))] items-center gap-2 border-b border-line px-2 pb-2 text-[11px] font-medium uppercase tracking-wide text-muted">
            <span>Field</span>
            {results.map((r, i) => (
              <span key={i} className="flex flex-wrap items-center gap-1.5">
                {i === 0 ? routeA : routeB}
                {(r.fields as Record<string, unknown>)?._fallback_from ? <Chip tone="warn">OCR fallback</Chip> : null}
                <ConfidenceBadge value={r.confidence} />
                {r.processing_time_ms != null && <Chip className="num">{(r.processing_time_ms / 1000).toFixed(1)}s</Chip>}
              </span>
            ))}
          </div>
          {fieldKeys.length === 0 ? (
            <EmptyState title="No fields extracted by either route" />
          ) : (
            <div className="divide-y divide-[var(--border)]">
              {fieldKeys.map((k) => {
                const [va, vb] = results.map((r) => {
                  const v = (r.fields ?? {})[k];
                  return v == null ? "" : typeof v === "object" ? JSON.stringify(v) : String(v);
                });
                const agree = va !== "" && va === vb;
                return (
                  <div key={k} className="grid grid-cols-[1fr_repeat(2,minmax(0,1.2fr))] items-center gap-2 px-2 py-2.5">
                    <span className="truncate text-xs font-medium uppercase tracking-wide text-muted" title={k}>{k.replace(/_/g, " ")}</span>
                    {[va, vb].map((v, i) => (
                      <span key={i} className={`num truncate text-[13px] ${v === "" ? "text-muted" : agree ? "text-body" : "text-warn"}`} title={v}>
                        {v === "" ? "—" : v}
                      </span>
                    ))}
                  </div>
                );
              })}
            </div>
          )}
          <p className="mt-3 text-[12px] text-muted">
            Matching values render normally; disagreements are highlighted. Route metadata (fallbacks,
            confidence, latency) comes straight from each response.
          </p>
        </motion.div>
      )}
    </div>
  );
}
