import { Cloud, Cpu, ScanText } from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Card, Chip } from "../kit/primitives";

/* Factual route cards — model IDs verified against core/config.py (GAP_REPORT §1). */

const MODELS = [
  {
    icon: Cloud,
    name: "Claude Sonnet Vision",
    route: "vision_premium",
    model: "anthropic/claude-sonnet-4-6",
    isDefault: true,
    traits: ["Best accuracy", "Cloud", "Multilingual", "Complex & multi-page layouts"],
    note: "Reads photos, scans and PDFs directly with a frontier vision model. 100% on the invoice benchmark; 92.5% on phone-photo receipts.",
  },
  {
    icon: Cpu,
    name: "Local Vision",
    route: "vision_local",
    model: "ollama/qwen2.5vl:7b",
    isDefault: false,
    traits: ["Private", "Zero API cost", "GPU-accelerated", "On-demand host"],
    note: "Fully private path on a GPU host (T4). 77% on receipts — far above OCR — and 100% on the French/FCFA sample. When the host is asleep, the API falls back to OCR and reports the fallback in the response.",
  },
  {
    icon: ScanText,
    name: "OCR + LLM cleanup",
    route: "ocr_fallback",
    model: "tesseract + anthropic/claude-haiku-4-5",
    isDefault: false,
    traits: ["Fast", "Lightweight", "Excellent on clean documents"],
    note: "Tesseract OCR with a small-model JSON cleanup pass. 100% on clean invoices; weak on noisy photos (28.5% on CORD receipts) — that contrast is the reason DocIntel is vision-first.",
  },
];

export default function Models() {
  return (
    <div>
      <PageHeader
        title="Vision models"
        sub="Three real extraction routes. Every /process call names the route it used — including automatic OCR fallback — so results are always attributable."
      />
      <div className="grid gap-4 lg:grid-cols-3">
        {MODELS.map((m) => (
          <Card key={m.route} hover>
            <div className="flex items-center justify-between">
              <m.icon size={20} style={{ color: "var(--accent)" }} strokeWidth={1.6} />
              {m.isDefault && <Chip tone="accent">default route</Chip>}
            </div>
            <div className="mt-3 text-[15px] font-semibold text-body">{m.name}</div>
            <div className="num mt-0.5 font-mono text-[11.5px] text-muted">{m.model}</div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {m.traits.map((t) => (
                <Chip key={t}>{t}</Chip>
              ))}
            </div>
            <p className="mt-3 text-[13px] leading-6 text-dim">{m.note}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
