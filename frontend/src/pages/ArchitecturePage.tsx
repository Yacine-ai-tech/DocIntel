import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity, Award, BookOpen, Boxes, Brain, Cable, Cloud, Cog, Cpu, Database, FileText, Filter,
  Gauge, GitBranch, Globe, Layers, Lock, Mic, Network, Pause, Play, Radio, RadioTower, Scale,
  Search, ShieldCheck, Sigma, Sparkles, Terminal, Wrench, Workflow, Zap, type LucideIcon,
} from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Button, Card, Chip } from "../kit/primitives";
import { PipelineFlow, type Stage } from "../kit/PipelineFlow";

const ICONS: Record<string, LucideIcon> = {
  Activity, Award, BookOpen, Boxes, Brain, Cable, Cloud, Cog, Cpu, Database, FileText, Filter,
  Gauge, GitBranch, Globe, Layers, Lock, Mic, Network, Radio, RadioTower, Scale, Search,
  ShieldCheck, Sigma, Sparkles, Terminal, Wrench, Workflow, Zap,
};

type NodeInfo = { id: string; label: string; layer: string; icon: string; summary: string; detail: string[]; env?: string[] };
type StageInfo = { id: string; label: string; icon: string; text: string; nodes: string[] };
type Arch = {
  title: string; sub: string; lifecycleTitle: string; layers: string[]; nodes: NodeInfo[]; stages: StageInfo[];
  endpoints: [string, string][]; decisions: [string, string][]; links: { to: string; label: string }[];
};

const DATA: Arch = {
  "title": "Architecture",
  "sub": "How a document becomes structured, normalised data — and which route does the work.",
  "lifecycleTitle": "Life of a document",
  "layers": [
    "Input",
    "Routes",
    "Structuring",
    "Output"
  ],
  "nodes": [
    {
      "id": "admit",
      "label": "Admission",
      "layer": "Input",
      "icon": "ShieldCheck",
      "summary": "Authentication, size and page limits, route resolution.",
      "detail": [
        "Upload and page limits are configuration, not code.",
        "Camera uploads from a paired phone use their own default route."
      ],
      "env": [
        "MAX_UPLOAD_SIZE_MB",
        "MAX_PDF_PAGES",
        "REQUIRE_INTERNAL_TOKEN",
        "DOCINTEL_MOBILE_ROUTE"
      ]
    },
    {
      "id": "prep",
      "label": "Preprocessing",
      "layer": "Input",
      "icon": "Layers",
      "summary": "Render PDF pages; deskew, contrast and resize images.",
      "detail": [
        "Large PDFs can be rendered on a separate host above a page threshold.",
        "Radon-transform deskew improves noisy phone photos."
      ],
      "env": [
        "RENDER_URL",
        "RENDER_PAGE_THRESHOLD",
        "PDF_MAX_EDGE_PX"
      ]
    },
    {
      "id": "routeA",
      "label": "Route A · Claude Vision",
      "layer": "Routes",
      "icon": "Sparkles",
      "summary": "Frontier vision model for complex, handwritten or mixed-language layouts.",
      "detail": [
        "Large documents are processed in page chunks and merged.",
        "Maximum accuracy; cost per page."
      ],
      "env": [
        "LLM_VISION_ROUTE_A",
        "VISION_PAGES_PER_CALL"
      ]
    },
    {
      "id": "routeB",
      "label": "Route B · Ollama vision",
      "layer": "Routes",
      "icon": "Cpu",
      "summary": "A vision model on hardware you control: private, zero per-page cost.",
      "detail": [
        "Local or remote Ollama host; a host that is still starting is polled within a time budget.",
        "When unavailable, requests are processed by Route C and flagged."
      ],
      "env": [
        "ROUTE_B_MODE",
        "OLLAMA_MODEL",
        "ROUTE_B_REMOTE_ENDPOINT",
        "ROUTE_B_FORCE_FALLBACK"
      ]
    },
    {
      "id": "routeC",
      "label": "Route C · OCR + LLM cleanup",
      "layer": "Routes",
      "icon": "Search",
      "summary": "Surya or Tesseract extracts text; a small model structures it.",
      "detail": [
        "The engine is a configuration choice and never switches at run time.",
        "A Surya failure is an error, not a silent downgrade.",
        "Routes A and B fall back here and use the configured engine."
      ],
      "env": [
        "SURYA_ENABLED",
        "SURYA_MODE",
        "OCR_LANGS",
        "LLM_CLEANUP"
      ]
    },
    {
      "id": "merge",
      "label": "Merge pages",
      "layer": "Structuring",
      "icon": "Workflow",
      "summary": "Type-agnostic rules combine page chunks.",
      "detail": [
        "Lists concatenate in page order, totals take the last page, header fields the first page, confidence the minimum."
      ]
    },
    {
      "id": "normalize",
      "label": "Normalisation",
      "layer": "Structuring",
      "icon": "Gauge",
      "summary": "Locale-aware amounts, ISO currencies (incl. FCFA/XOF), ISO 8601 dates.",
      "detail": [
        "Deterministic: language models are unreliable at locale-specific numbers.",
        "Conservative: unparseable values are left untouched."
      ]
    },
    {
      "id": "out",
      "label": "Library, batch, webhooks",
      "layer": "Output",
      "icon": "Database",
      "summary": "Session-scoped library, batch jobs, camera sessions and result webhooks.",
      "detail": [
        "Postgres when configured, local files otherwise.",
        "Batch jobs and camera sessions expire after a configurable period."
      ],
      "env": [
        "POSTGRES_URL",
        "BATCH_JOB_TTL_SECONDS",
        "CAMERA_SESSION_TTL_SECONDS"
      ]
    }
  ],
  "stages": [
    {
      "id": "admit",
      "label": "Admit",
      "icon": "ShieldCheck",
      "text": "Authenticate, check size and page limits, resolve the route.",
      "nodes": [
        "admit"
      ]
    },
    {
      "id": "prep",
      "label": "Prepare",
      "icon": "Layers",
      "text": "Render pages and preprocess images.",
      "nodes": [
        "prep"
      ]
    },
    {
      "id": "extract",
      "label": "Extract",
      "icon": "Search",
      "text": "A or B read the pages with a vision model in chunks; C runs OCR then structures the text.",
      "nodes": [
        "routeA",
        "routeB",
        "routeC"
      ]
    },
    {
      "id": "merge",
      "label": "Merge & normalise",
      "icon": "Gauge",
      "text": "Combine page chunks, then clean amounts, currencies and dates deterministically.",
      "nodes": [
        "merge",
        "normalize"
      ]
    },
    {
      "id": "deliver",
      "label": "Deliver",
      "icon": "Database",
      "text": "Store in the library, notify a webhook and return fields, route and flags.",
      "nodes": [
        "out"
      ]
    }
  ],
  "endpoints": [
    [
      "POST /process, /process/async, /extract",
      "Extract a document (synchronous or as a job)"
    ],
    [
      "POST /extract/text, /extract/marker",
      "Text and Marker extraction modes"
    ],
    [
      "POST /extract-fields, /extract-llm, /extract-tables",
      "Focused extraction modes"
    ],
    [
      "POST /classify, /classify-image",
      "Document and image classification"
    ],
    [
      "POST /batch/upload · GET /batch/{id} · /batch/{id}/results",
      "Batch jobs"
    ],
    [
      "POST /camera/pair · GET /camera/qr/{token} · POST /camera/upload",
      "Mobile capture"
    ],
    [
      "GET /api/documents · DELETE /api/documents/{id}",
      "Document library"
    ],
    [
      "GET /health · GET /ready · GET /benchmarks",
      "Liveness, readiness and published figures"
    ]
  ],
  "decisions": [
    [
      "Three routes, chosen explicitly",
      "Accuracy, privacy and cost trade off differently per document, so the choice is visible and per request."
    ],
    [
      "Engine fixed by configuration",
      "A silent engine switch would change accuracy without telling anyone."
    ],
    [
      "Deterministic normalisation",
      "Numbers, currencies and dates are cleaned by rules, never trusted from a model."
    ]
  ],
  "links": [
    {
      "to": "/research",
      "label": "Research"
    },
    {
      "to": "/benchmarks",
      "label": "Benchmarks"
    }
  ]
};

export default function ArchitecturePage() {
  const [selected, setSelected] = useState<string>(DATA.nodes[0].id);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [filter, setFilter] = useState("");

  const stages: (Stage & { text: string; nodes: string[] })[] = useMemo(
    () => DATA.stages.map((s) => ({ ...s, icon: ICONS[s.icon] ?? Zap })), []);

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => setStep((s) => (s + 1) % (stages.length + 1)), 1800);
    return () => clearInterval(t);
  }, [playing, stages.length]);

  const current = stages[Math.min(step, stages.length - 1)];
  const lit = useMemo(() => new Set(step < stages.length ? current.nodes : []), [step, current, stages.length]);
  const node = DATA.nodes.find((n) => n.id === selected) ?? DATA.nodes[0];
  const endpoints = DATA.endpoints.filter(([r, p]) => (r + " " + p).toLowerCase().includes(filter.toLowerCase()));

  return (
    <div className="p-8 max-w-6xl mx-auto h-full overflow-y-auto space-y-8">
      <PageHeader
        title={DATA.title}
        sub={DATA.sub}
        actions={
          <div className="flex gap-2">
            {DATA.links.map((l) => (
              <Link key={l.to} to={l.to}><Button variant="secondary">{l.label}</Button></Link>
            ))}
          </div>
        }
      />

      <Card title={DATA.lifecycleTitle}>
        <div className="flex items-center justify-between mb-2">
          <div className="text-xs text-dim">Pick a stage or let it play; the components involved are highlighted below.</div>
          <Button variant="secondary" onClick={() => setPlaying((p) => !p)}>
            {playing ? <Pause size={14} className="mr-1 inline" /> : <Play size={14} className="mr-1 inline" />}
            {playing ? "Pause" : "Play"}
          </Button>
        </div>
        <PipelineFlow stages={stages} active={step} done={step >= stages.length} />
        <div className="mt-3 flex flex-wrap gap-2">
          {stages.map((s, i) => (
            <button key={s.id} onClick={() => { setPlaying(false); setStep(i); }}
              className={`rounded-lg border px-3 py-1 text-xs ${i === step ? "border-accent text-body" : "border-line text-dim"}`}>
              {i + 1}. {s.label}
            </button>
          ))}
        </div>
        <p className="mt-3 text-sm text-dim">{step < stages.length ? current.text : "Complete."}</p>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          {DATA.layers.map((layer) => (
            <Card key={layer} title={layer}>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {DATA.nodes.filter((n) => n.layer === layer).map((n) => {
                  const Icon = ICONS[n.icon] ?? Boxes;
                  const active = selected === n.id;
                  return (
                    <button key={n.id} onClick={() => setSelected(n.id)}
                      className={`text-left rounded-xl border p-3 transition-colors ${active ? "border-accent bg-surface-2" : "border-line bg-surface"} ${lit.has(n.id) ? "ring-1 ring-accent" : ""}`}>
                      <div className="flex items-center gap-2 text-sm font-semibold text-body"><Icon size={14} /> {n.label}</div>
                      <div className="mt-1 text-xs text-dim">{n.summary}</div>
                    </button>
                  );
                })}
              </div>
            </Card>
          ))}
        </div>

        <Card title={node.label} className="h-fit lg:sticky lg:top-4">
          <p className="text-sm text-dim">{node.summary}</p>
          <ul className="mt-3 space-y-2 text-xs text-dim list-disc pl-4">
            {node.detail.map((d) => <li key={d}>{d}</li>)}
          </ul>
          {node.env && node.env.length > 0 && (
            <div className="mt-4">
              <div className="text-[11px] uppercase tracking-wider text-muted mb-1">Configuration</div>
              <div className="flex flex-wrap gap-1.5">{node.env.map((e) => <Chip key={e}>{e}</Chip>)}</div>
            </div>
          )}
        </Card>
      </div>

      <Card title="Interfaces">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter routes…"
          aria-label="Filter routes"
          className="w-full mb-3 rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs text-body outline-none focus:border-accent"
        />
        <div className="divide-y divide-line text-xs">
          {endpoints.map(([r, p]) => (
            <div key={r} className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4 py-2">
              <code className="sm:w-72 shrink-0 text-body">{r}</code>
              <span className="text-dim">{p}</span>
            </div>
          ))}
          {endpoints.length === 0 && <div className="py-3 text-dim">No route matches.</div>}
        </div>
      </Card>

      <Card title="Design decisions">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-dim">
          {DATA.decisions.map(([t, d]) => (
            <div key={t} className="rounded-xl border border-line bg-surface-2 p-4">
              <div className="font-semibold text-body text-sm mb-1">{t}</div>{d}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
