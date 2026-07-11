import { useMemo } from "react";
import {
  UploadCloud, ScanSearch, GitBranch, FileText, ShieldCheck, PackageCheck,
  Cloud, Cpu, ScanText, ArrowDown,
} from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Card, Chip, EmptyState, StatTile } from "../kit/primitives";
import { PipelineFlow } from "../kit/PipelineFlow";
import { readActivity } from "../lib/api";

/* v1 "Pipelines" page — the real processing pipeline visualized, with live timings
   aggregated from documents processed in this browser session (Activity log). */

const STAGES = [
  { id: "upload", label: "Upload", icon: UploadCloud, detail: "PDF · PNG · JPEG · TIFF" },
  { id: "classify", label: "Classification", icon: ScanSearch, detail: "content + filename" },
  { id: "route", label: "Routing", icon: GitBranch, detail: "3 model routes" },
  { id: "extract", label: "Extraction", icon: FileText, detail: "multi-page vision/OCR" },
  { id: "validate", label: "Validation", icon: ShieldCheck, detail: "typed fields + confidence" },
  { id: "output", label: "Output", icon: PackageCheck, detail: "structured JSON" },
];

const ROUTES = [
  { icon: Cloud, name: "vision_premium", model: "Claude Sonnet 4.6 Vision", when: "default — photos, scans, complex and multi-page layouts" },
  { icon: Cpu, name: "vision_local", model: "qwen2.5-VL 7B (Ollama)", when: "private path on a GPU host; degrades to OCR with an explicit note when asleep" },
  { icon: ScanText, name: "ocr_fallback", model: "Tesseract + Claude Haiku cleanup", when: "clean digital documents; also the automatic fallback for both vision routes" },
];

export default function Pipelines() {
  const runs = useMemo(() => readActivity().filter((e) => e.kind === "process" && typeof e.meta.ms === "number"), []);
  const times = runs.map((r) => r.meta.ms as number);
  const avg = times.length ? times.reduce((a, b) => a + b, 0) / times.length : null;
  const fallbacks = runs.filter((r) => r.meta.fallback).length;

  return (
    <div>
      <PageHeader
        title="Pipeline"
        sub="Every document takes this path. The route stage picks a vision model per document; both vision routes fall back to OCR automatically and say so in the response."
      />

      <Card title="Processing stages">
        <PipelineFlow stages={STAGES} active={STAGES.length} done />
      </Card>

      <Card title="Routing" className="mt-4">
        <div className="space-y-3">
          {ROUTES.map((r, i) => (
            <div key={r.name} className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface-2 px-4 py-3">
              <r.icon size={17} style={{ color: "var(--accent)" }} className="shrink-0" />
              <span className="num w-36 shrink-0 font-mono text-[12px] text-body">{r.name}</span>
              <Chip>{r.model}</Chip>
              <span className="min-w-0 flex-1 text-[12.5px] text-dim">{r.when}</span>
              {i < 2 && <ArrowDown size={13} className="text-muted max-sm:hidden" />}
            </div>
          ))}
        </div>
        <p className="mt-3 text-[12.5px] leading-5 text-muted">
          The response always names the route that actually ran — including{" "}
          <code className="font-mono text-[11.5px]">_fallback_from</code> when OCR stepped in — so
          every extraction is attributable.
        </p>
      </Card>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <StatTile label="Documents this session" value={runs.length} sub="from your browser" />
        <StatTile
          label="Avg end-to-end time"
          value={avg == null ? "—" : `${(avg / 1000).toFixed(1)}s`}
          sub={times.length ? `across ${times.length} runs` : "process a document to populate"}
        />
        <StatTile
          label="OCR fallbacks"
          value={runs.length ? fallbacks : "—"}
          sub="vision route degraded gracefully"
          delta={runs.length ? { text: fallbacks === 0 ? "none needed" : "reported in-response", good: fallbacks === 0 } : undefined}
        />
      </div>

      {runs.length === 0 && (
        <Card className="mt-4">
          <EmptyState title="No timing data yet" hint="Run a document through the Workspace — real per-run timings appear here." />
        </Card>
      )}
    </div>
  );
}
