import React from 'react';
import {
  FileScan, Image, Layers, Sparkles, Scale, Globe2,
  CheckCircle2, Terminal, BookOpen, ExternalLink, Cpu,
  BarChart3, Landmark, Workflow, ScanLine
} from 'lucide-react';
import { PageHeader } from '../kit/AppShell';
import { Card, Button } from '../kit/primitives';
import { Link } from 'react-router-dom';

export default function ResearchPage() {
  return (
    <div className="p-8 max-w-6xl mx-auto h-full overflow-y-auto space-y-8">
      <PageHeader
        title="DocIntel — Vision-LLM Document Understanding Research"
        sub="Multimodal extraction architectures, deterministic normalization layers, tri-route fallback topology, and empirical layout benchmarks."
        actions={
          <div className="flex gap-2">
            <Link to="/benchmarks">
              <Button variant="primary">
                <BarChart3 size={14} className="mr-1 inline" /> View Benchmarks
              </Button>
            </Link>
            <Link to="/user-guide">
              <Button variant="secondary">
                <BookOpen size={14} className="mr-1 inline" /> User Guide
              </Button>
            </Link>
          </div>
        }
      />

      {/* Abstract */}
      <Card title="Abstract & Architectural Focus" className="bg-surface/80">
        <p className="text-dim leading-relaxed text-sm mb-4">
          DocIntel extracts structured JSON schemas directly from complex visual documents (invoices, receipts, contracts, tax declarations) using a <strong className="text-body">vision-LLM-first methodology</strong>. By presenting raw page images directly to multimodal vision models, DocIntel preserves typographical hierarchy, reading order, table cells, and handwriting that traditional OCR-then-NER pipelines inevitably discard.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          <div className="rounded-xl border border-line bg-surface-2 p-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-accent mb-1">Vision-First</div>
            <div className="font-semibold text-body text-sm mb-1">Image-to-JSON Reasoning</div>
            <div className="text-xs text-dim">No intermediate text flattening. Multimodal LLMs reason over layout, geometry, and semantics jointly.</div>
          </div>
          <div className="rounded-xl border border-line bg-surface-2 p-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-ok mb-1">Tri-Route Topology</div>
            <div className="font-semibold text-body text-sm mb-1">A / B / C Fallback Chain</div>
            <div className="text-xs text-dim">Route A (Frontier Claude), Route B (Local Qwen2.5-VL), Route C (Surya OCR + LLM fallback) balancing cost and sovereignty.</div>
          </div>
          <div className="rounded-xl border border-line bg-surface-2 p-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-primary mb-1">Post-Processing</div>
            <div className="font-semibold text-body text-sm mb-1">Deterministic Normalizer</div>
            <div className="text-xs text-dim">Rule-based standardization to ISO 4217 (currencies) and ISO 8601 (dates) correcting LLM formatting jitter.</div>
          </div>
        </div>
      </Card>

      {/* Tri-Route Architecture */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card title="Route A: Frontier Cloud Vision">
          <div className="space-y-3 text-xs text-dim leading-relaxed">
            <div className="font-semibold text-body text-sm">Claude Sonnet 4.6 Vision</div>
            <p>
              High-accuracy commercial route with per-call token metering (<code className="text-accent">litellm.completion_cost()</code>).
            </p>
            <ul className="list-disc pl-4 space-y-1">
              <li>100% field accuracy on multi-page complex invoices.</li>
              <li>92.5% on camera-photographed CORD-v2 receipts.</li>
              <li>95.0% zero-shot on SROIE Task 3.</li>
            </ul>
          </div>
        </Card>

        <Card title="Route B: Self-Hosted Vision">
          <div className="space-y-3 text-xs text-dim leading-relaxed">
            <div className="font-semibold text-body text-sm">Ollama Qwen 2.5-VL 7B</div>
            <p>
              Air-gapped on-premises inference with zero third-party data egress or API costs.
            </p>
            <ul className="list-disc pl-4 space-y-1">
              <li>97.8% overall field accuracy on 106-document sample.</li>
              <li>100% accuracy on French/FCFA UEMOA corpus.</li>
              <li>Radon-transform deskew pre-processing.</li>
            </ul>
          </div>
        </Card>

        <Card title="Route C: OCR + LLM Fallback">
          <div className="space-y-3 text-xs text-dim leading-relaxed">
            <div className="font-semibold text-body text-sm">Surya OCR + Tesseract</div>
            <p>
              High-throughput fallback when vision-model rate limits or quotas are exceeded.
            </p>
            <ul className="list-disc pl-4 space-y-1">
              <li>Layout-aware text box detection via Surya GPU.</li>
              <li>Automatic Tesseract CPU fallback.</li>
              <li>96.3% field accuracy on 650-document test suite.</li>
            </ul>
          </div>
        </Card>
      </div>

      {/* Multi-Page & Deterministic Normalization */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="1. Multi-Page Chunking & Merge Logic">
          <div className="space-y-3 text-xs text-dim leading-relaxed">
            <p>
              PDF documents exceeding single-turn context limits (up to 200 pages) are chunked across sequential vision calls and unified via <code className="text-accent">services/doc_merge.py</code>:
            </p>
            <ul className="list-disc pl-4 space-y-1">
              <li><strong className="text-body">Line Items:</strong> Concatenated sequentially across chunks with duplicate deduplication.</li>
              <li><strong className="text-body">Running Totals:</strong> Resolved to the final non-empty chunk (representing document end totals).</li>
              <li><strong className="text-body">Metadata Headers:</strong> Resolved to the first non-null header detected (vendor, invoice date).</li>
            </ul>
          </div>
        </Card>

        <Card title="2. Locale & Currency Normalization">
          <div className="space-y-3 text-xs text-dim leading-relaxed">
            <p>
              Models frequently err on localized number conventions. <code className="text-accent">services/normalize.py</code> provides deterministic normalization:
            </p>
            <ul className="list-disc pl-4 space-y-1">
              <li><strong className="text-body">Currency Standard:</strong> Maps 40+ national currency tokens to ISO 4217, specializing in West/Central African CFA franc (<code className="text-accent">FCFA / CFA → XOF / XAF</code>).</li>
              <li><strong className="text-body">Amount Formatting:</strong> Parses US (1,234.56), EU (1.234,56), space-grouped (1 234 567), and Swiss (1'234.56) figures.</li>
              <li><strong className="text-body">ISO 8601:</strong> Standardizes dates across varied local formats.</li>
            </ul>
          </div>
        </Card>
      </div>

      {/* Academic Citations */}
      <Card title="3. Literature & Benchmark References">
        <div className="space-y-3 text-xs text-dim">
          <div className="border-b border-line pb-2">
            <div className="font-semibold text-body">ICDAR 2019 Competition on Scanned Receipts OCR and Information Extraction (SROIE)</div>
            <div className="text-muted">Huang, Z., et al. (2019). Standard Task 3 key-information extraction benchmark.</div>
          </div>
          <div className="border-b border-line pb-2">
            <div className="font-semibold text-body">CORD: A Consolidated Receipt Dataset for Post-OCR Parsing</div>
            <div className="text-muted">Park, S., et al. (NeurIPS 2019 Workshop on Document Intelligence). Standard real-world receipt extraction corpus.</div>
          </div>
          <div className="border-b border-line pb-2">
            <div className="font-semibold text-body">LayoutLMv3: Pre-training for Document AI with Unified Text and Image Masking</div>
            <div className="text-muted">Huang, Y., et al. (ACM MM 2022). Purpose-built layout model benchmark baseline.</div>
          </div>
          <div>
            <div className="font-semibold text-body">Qwen2.5-VL Technical Report</div>
            <div className="text-muted">Qwen Team (Alibaba Cloud, 2025). Multimodal vision-language architecture for dense text and document understanding.</div>
          </div>
        </div>
      </Card>
    </div>
  );
}
