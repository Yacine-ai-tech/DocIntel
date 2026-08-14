import { useState } from "react";
import { Terminal, Copy, Check, Code2, Globe, Shield, Zap, BookOpen } from "lucide-react";

// Same resolution order as lib/api.ts's request client: an explicit VITE_API_BASE_URL
// (for split frontend/backend deployments) wins, otherwise fall back to the current
// origin (same-origin deployments, e.g. the Docker single-container setup) — so the
// copy-paste examples always match wherever this page is actually being served from,
// author's deployment or any self-hoster's, instead of a hardcoded URL.
const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== "undefined" ? window.location.origin : "");

type Group = "Core extraction" | "Classification" | "Batch processing" | "Camera / mobile pairing";

interface Endpoint {
  method: string;
  path: string;
  group: Group;
  desc: string;
  auth: boolean;
  body: string | null;
  query?: string;
  response: string;
}

const ENDPOINTS: Endpoint[] = [
  // ── Core extraction ─────────────────────────────────────────────────────
  {
    method: "POST",
    path: "/process",
    group: "Core extraction",
    desc: "One-shot pipeline: upload -> (auto-classify) -> multi-page extract -> structured JSON. The recommended default endpoint for most integrations.",
    auth: true,
    body: "multipart/form-data\n  file: <pdf | png | jpg | jpeg | tiff>\n  route: vision_route_a | vision_route_b | ocr_fallback  (form field, default \"vision_route_a\")\n  doc_type: auto | invoice | contract | receipt | financial_report | auction_listing | form  (form field, default \"auto\")",
    response:
      "{\n  \"doc_type\": \"invoice\",\n  \"route\": \"vision_route_a\",\n  \"confidence\": 0.96,\n  \"page_count\": 2,\n  \"processing_time_ms\": 1840.2,\n  \"fields\": {\n    \"vendor\": \"ACME Ltd\",\n    \"invoice_number\": \"INV-2044\",\n    \"total\": 1500.0,\n    \"currency\": \"USD\",\n    \"_confidence\": 0.96,\n    \"_pages\": 2,\n    \"_tables_detected\": 1,\n    \"_used_route\": \"vision_route_a\",\n    \"_fallback_used\": false\n  },\n  \"raw_text\": null,\n  \"error\": null\n}",
  },
  {
    method: "POST",
    path: "/extract",
    group: "Core extraction",
    desc: "Extract structured fields from a document without the auto-classify step — doc_type is supplied explicitly (default \"invoice\"). Same 3-route cascade as /process.",
    auth: true,
    body: "multipart/form-data\n  file: <pdf | png | jpg | jpeg | tiff>\n  route: vision_route_a | vision_route_b | ocr_fallback  (form field, default \"vision_route_a\")\n  doc_type: invoice | contract | receipt | financial_report | auction_listing | form  (form field, default \"invoice\")",
    response:
      "{\n  \"doc_type\": \"invoice\",\n  \"route\": \"vision_route_a\",\n  \"confidence\": 0.96,\n  \"page_count\": 1,\n  \"processing_time_ms\": 1120.4,\n  \"fields\": { \"vendor\": \"ACME Ltd\", \"total\": 1500.0, \"currency\": \"USD\", \"_confidence\": 0.96 },\n  \"raw_text\": null,\n  \"error\": null\n}",
  },
  {
    method: "POST",
    path: "/extract-llm",
    group: "Core extraction",
    desc: "Text-only structured extraction (Route C step in isolation) — skip OCR entirely and hand DocIntel text you already have. Always runs via ocr_fallback's LLM-cleanup model.",
    auth: true,
    body: "multipart/form-data (form fields only, no file)\n  text: <raw text>  (required)\n  doc_type: invoice | contract | receipt | financial_report | auction_listing | form  (default \"invoice\")",
    response:
      "{\n  \"doc_type\": \"invoice\",\n  \"route\": \"ocr_fallback\",\n  \"confidence\": null,\n  \"page_count\": null,\n  \"processing_time_ms\": 640.1,\n  \"fields\": { \"vendor\": \"ACME Ltd\", \"total\": 1500.0, \"currency\": \"USD\" },\n  \"raw_text\": null,\n  \"error\": null\n}",
  },
  {
    method: "POST",
    path: "/extract-tables",
    group: "Core extraction",
    desc: "Table-detection only, via pdfplumber. No LLM call — fast, deterministic, PDF-only.",
    auth: true,
    body: "multipart/form-data\n  file: <pdf>",
    response: "{\n  \"tables\": [[[\"Item\", \"Qty\", \"Price\"], [\"Widget\", \"3\", \"9.99\"]]],\n  \"table_count\": 1\n}",
  },
  {
    method: "POST",
    path: "/extract/marker",
    group: "Core extraction",
    desc: "Explicit PDF -> Markdown conversion via Marker. Useful for feeding a born-digital PDF's full text/structure into a downstream LLM step rather than field extraction.",
    auth: true,
    body: "multipart/form-data\n  file: <pdf>",
    response: "{\n  \"markdown\": \"# Invoice\\n\\n| Item | Qty | Price |\\n|---|---|---|\\n| Widget | 3 | 9.99 |\",\n  \"metadata\": { \"...\": \"...\" },\n  \"method\": \"marker\",\n  \"num_images\": 0\n}",
  },
  {
    method: "POST",
    path: "/extract/text",
    group: "Core extraction",
    desc: "Full document text — the RAG-ingestion path (used by IntelAI's document delegation). Every other endpoint returns typed, invoice-shaped fields; this returns the document's actual prose, which is the wrong/right shape depending on whether you're populating a form or a knowledge base.",
    auth: true,
    body: "multipart/form-data\n  file: <pdf | png | jpg | jpeg | tiff>\n  route: auto | marker | ocr  (form field, default \"auto\" — Marker if installed, else the native text layer / per-page OCR)\n  max_pages: <int>  (form field, default 0 = MAX_PDF_PAGES)",
    response: "{\n  \"text\": \"FACTURE\\n\\nTECHNOLOGIE DAKAR SARL...\",\n  \"method\": \"native_or_ocr\",\n  \"page_count\": 1,\n  \"chars\": 412,\n  \"processing_time_ms\": 640.1\n}",
  },
  {
    method: "POST",
    path: "/extract/text/batch",
    group: "Core extraction",
    desc: "Async equivalent of /extract/text, for documents too large/slow to finish inside a synchronous request/reverse-proxy timeout — e.g. route=marker on a long document. Poll the same way as /batch/upload: GET /batch/{job_id} for status, GET /batch/{job_id}/results for the {text, method, page_count, chars} shape per file. Pass webhook_url for a completion callback instead of polling.",
    auth: true,
    body: "multipart/form-data\n  files: [<doc1>, <doc2>, ...]  (repeated \"files\" field, required)\n  route: auto | marker | ocr  (form field, default \"auto\")\n  max_pages: <int>  (form field, default 0 = MAX_PDF_PAGES)\n  webhook_url: <URL>  (form field, optional)",
    response: "{ \"job_id\": \"b3f1c9de-...\", \"total\": 3, \"webhook_url\": null }",
  },
  {
    method: "POST",
    path: "/extract-fields",
    group: "Core extraction",
    desc: "Generic form label-to-value extraction, independent of the invoice/contract/receipt schemas the other endpoints use — for documents that are just \"a bunch of filled-in fields\" (applications, questionnaires) rather than one of the typed doc_types.",
    auth: true,
    body: "multipart/form-data\n  file: <pdf | png | jpg | jpeg | tiff>\n  route: vision_route_a | vision_route_b | ocr_fallback  (form field, default \"vision_route_a\")",
    response: "{\n  \"route\": \"vision_route_a\",\n  \"page_count\": 1,\n  \"form_title\": \"Application Form\",\n  \"fields\": { \"Applicant Name\": \"Jane Doe\", \"Date\": \"2026-08-09\" },\n  \"confidence\": 0.98,\n  \"processing_time_ms\": 2100.3,\n  \"error\": null\n}",
  },
  // ── Classification ───────────────────────────────────────────────────────
  {
    method: "POST",
    path: "/classify",
    group: "Classification",
    desc: "Fast document-type classification only (no field extraction). Content-based (text sample + the same classifier /process uses), with a filename heuristic as a fallback signal.",
    auth: true,
    body: "multipart/form-data\n  file: <pdf | png | jpg | jpeg | tiff>",
    response: "{\n  \"doc_type\": \"invoice\",\n  \"route\": \"classify\",\n  \"confidence\": 0.85,\n  \"page_count\": null,\n  \"processing_time_ms\": null,\n  \"fields\": null,\n  \"raw_text\": null,\n  \"error\": null\n}",
  },
  {
    method: "POST",
    path: "/classify-image",
    group: "Classification",
    desc: "Vision-first object classification against a caller-supplied category list (the auction-listing pattern) — Route A (Claude Sonnet 4.6 Vision) only.",
    auth: true,
    body: "multipart/form-data\n  file: <image>\n  categories: \"tractor,lathe,crane\"  (comma-separated string, required)",
    response: "{\n  \"category\": \"tractor\",\n  \"confidence\": 0.93,\n  \"reasoning\": \"Visible tracked chassis and front loader arm.\",\n  \"processing_time_ms\": 780.5\n}",
  },
  // ── Batch processing ─────────────────────────────────────────────────────
  {
    method: "POST",
    path: "/batch/upload",
    group: "Batch processing",
    desc: "Submit multiple documents for background async processing. Returns immediately with a job_id; files are processed concurrently (bounded by BATCH_MAX_CONCURRENCY, default 8) with per-file error isolation — one bad file never aborts the batch. Pass webhook_url to get a callback on completion instead of polling (see the n8n integration guide).",
    auth: true,
    body: "multipart/form-data\n  files: [<doc1>, <doc2>, ...]  (repeated \"files\" field, required)\n  route: vision_route_a | vision_route_b | ocr_fallback  (form field, default \"vision_premium\" legacy alias)\n  doc_type: invoice | contract | receipt | financial_report | auction_listing | form  (form field, default \"invoice\")\n  webhook_url: <URL>  (form field, optional — POSTed with {job_id, status, total, processed, failed, finished_at, results} when the job completes; e.g. an n8n Webhook node's URL)",
    response: "{ \"job_id\": \"b3f1c9de-...\", \"total\": 12, \"webhook_url\": null }",
  },
  {
    method: "GET",
    path: "/batch/{job_id}",
    group: "Batch processing",
    desc: "Poll job status/progress (no per-file results). 404 if the job_id is unknown.",
    auth: true,
    body: null,
    response:
      "{\n  \"id\": \"b3f1c9de-...\",\n  \"status\": \"running\",\n  \"total\": 12,\n  \"processed\": 7,\n  \"failed\": 0,\n  \"percent\": 58.3,\n  \"created_at\": \"2026-08-09T10:00:00Z\",\n  \"updated_at\": \"2026-08-09T10:00:42Z\",\n  \"started_at\": \"2026-08-09T10:00:01Z\",\n  \"finished_at\": null\n}",
  },
  {
    method: "GET",
    path: "/batch/{job_id}/results",
    group: "Batch processing",
    desc: "Fetch per-file results, index-aligned with the original upload order. Entries are null for files not yet processed; failed files carry {error, filename} instead of fields. 404 if the job_id is unknown.",
    auth: true,
    body: null,
    response:
      "{\n  \"job_id\": \"b3f1c9de-...\",\n  \"results\": [\n    { \"filename\": \"invoice1.pdf\", \"fields\": { \"total\": 1500.0 }, \"confidence\": 0.96, \"page_count\": 1 },\n    { \"error\": \"OCR extraction failed\", \"filename\": \"scan2.jpg\" }\n  ]\n}",
  },
  // ── Camera / mobile pairing ──────────────────────────────────────────────
  {
    method: "POST",
    path: "/camera/pair",
    group: "Camera / mobile pairing",
    desc: "Generate a pairing token (24h expiry) and a base64 QR code image encoding the mobile-capture URL, so a phone can join the session by scanning it. The QR encodes FRONTEND_URL (or http://localhost:8001 if unset) — set this env var to your real frontend URL or phones on a different network can't reach it.",
    auth: true,
    body: "multipart/form-data (form fields)\n  user: <string>  (default \"demo_user\")\n  device: <string>  (default \"Mobile\")",
    response: "{\n  \"token\": \"7fQ3z...\",\n  \"qr_available\": true,\n  \"qr_code\": \"data:image/png;base64,iVBORw0...\",\n  \"expires_in_hours\": 24,\n  \"frontend_url\": \"https://your-frontend.example.com\"\n}",
  },
  {
    method: "GET",
    path: "/camera/qr/{token}",
    group: "Camera / mobile pairing",
    desc: "Return the raw QR code as a PNG image (image/png, not JSON) for a previously issued pairing token. 404 if the token is unknown or QR generation failed.",
    auth: true,
    body: null,
    response: "<binary image/png bytes>",
  },
  {
    method: "POST",
    path: "/camera/upload",
    group: "Camera / mobile pairing",
    desc: "The paired mobile device uploads a captured photo. The token is validated (must be active, unexpired) and the upload is automatically routed through Route B (local/self-hosted Ollama vision) with automatic fallback to Route C (OCR) on failure; the result is stored on the session for the desktop side to pick up via /camera/status. 403 if the token is invalid or expired.",
    auth: true,
    body: "multipart/form-data\n  token: <pairing token from /camera/pair>  (required)\n  file: <photo>  (required)\n  doc_type: invoice | contract | receipt | financial_report | auction_listing | form | default  (form field, default \"default\")",
    response: "{\n  \"fields\": { \"vendor\": \"ACME Ltd\", \"total\": 1500.0, \"_used_route\": \"vision_route_b\", \"_fallback_used\": false },\n  \"confidence\": 0.9,\n  \"page_count\": 1,\n  \"processing_time_ms\": 2400.1\n}",
  },
  {
    method: "GET",
    path: "/camera/status/{token}",
    group: "Camera / mobile pairing",
    desc: "Desktop polling target — call this after /camera/pair (every few seconds) to find out whether the paired phone has uploaded yet and, once it has, the extraction result. Doesn't require the session to still be unexpired the way /camera/upload does, so you can still read the last result after the token expires.",
    auth: true,
    body: null,
    response: "{\n  \"active\": true,\n  \"uploads\": 1,\n  \"last_upload\": \"2026-08-09T19:01:45Z\",\n  \"last_result\": { \"fields\": { \"vendor\": \"ACME Ltd\" }, \"confidence\": 0.9, \"page_count\": 1, \"processing_time_ms\": 2400.1 }\n}",
  },
  // ── Meta ──────────────────────────────────────────────────────────────────
  {
    method: "GET",
    path: "/",
    group: "Core extraction",
    desc: "Serves the built DocIntel SPA (this frontend) when present, else a minimal {service, docs} JSON. Not part of the OpenAPI schema. No auth required.",
    auth: false,
    body: null,
    response: "{ \"service\": \"docintel\", \"docs\": \"/docs\" }",
  },
  {
    method: "GET",
    path: "/health",
    group: "Core extraction",
    desc: "Liveness/readiness check. No auth required — always reachable, used by uptime monitors and the frontend's connection banner.",
    auth: false,
    body: null,
    response: "{ \"status\": \"ok\", \"service\": \"docintel\", \"version\": \"0.1.0\" }",
  },
];

// Stable display order: group headers, then the endpoints as declared above.
const GROUP_ORDER: Group[] = ["Core extraction", "Classification", "Batch processing", "Camera / mobile pairing"];

const SNIPPETS = {
  curl: (ep: Endpoint) => {
    if (!ep.body) return `curl "${BASE_URL}${ep.path}"`;
    if (ep.body.startsWith("multipart")) {
      const hasFile = /\bfile:/.test(ep.body) || /files:/.test(ep.body);
      const fileFlag = ep.path === "/extract-llm" ? "" : hasFile ? ` -F "file=@document.pdf"` : "";
      return `curl -X ${ep.method} "${BASE_URL}${ep.path}" \\\n  -H "X-OmniIntel-Internal-Token: $OMNIINTEL_INTERNAL_TOKEN"${fileFlag} \\\n  -F "route=vision_route_a"`;
    }
    return `curl -X ${ep.method} "${BASE_URL}${ep.path}" \\\n  -H "Content-Type: application/json" \\\n  -d '${ep.body}'`;
  },
  python: (ep: Endpoint) => {
    if (!ep.body) return `import requests\n\nresp = requests.get("${BASE_URL}${ep.path}")\nprint(resp.json())`;
    if (ep.body.startsWith("multipart")) {
      return `import requests\n\nwith open("document.pdf", "rb") as f:\n    resp = requests.post(\n        "${BASE_URL}${ep.path}",\n        headers={"X-OmniIntel-Internal-Token": OMNIINTEL_INTERNAL_TOKEN},\n        files={"file": f},\n        data={"route": "vision_route_a", "doc_type": "invoice"},\n    )\nprint(resp.json())`;
    }
    return `import requests\n\nresp = requests.${ep.method.toLowerCase()}(\n    "${BASE_URL}${ep.path}",\n    json=...,  # see request body\n)\nprint(resp.json())`;
  },
  node: (ep: Endpoint) => {
    if (!ep.body) return `const res = await fetch("${BASE_URL}${ep.path}");\nconst data = await res.json();\nconsole.log(data);`;
    if (ep.body.startsWith("multipart")) {
      return `const form = new FormData();\nform.append("file", fileInput.files[0]);\nform.append("route", "vision_route_a");\n\nconst res = await fetch("${BASE_URL}${ep.path}", {\n  method: "${ep.method}",\n  headers: { "X-OmniIntel-Internal-Token": OMNIINTEL_INTERNAL_TOKEN },\n  body: form,\n});\nconst data = await res.json();`;
    }
    return `const res = await fetch("${BASE_URL}${ep.path}", {\n  method: "${ep.method}",\n  headers: { "Content-Type": "application/json" },\n  body: JSON.stringify(/* see request body */),\n});\nconst data = await res.json();`;
  },
};

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
      style={{ background: "none", border: "none", cursor: "pointer", color: copied ? "#4ade80" : "#94a3b8", padding: "4px" }}
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}

function CodeBlock({ code }: { code: string }) {
  return (
    <div style={{ position: "relative", background: "rgba(0,0,0,0.4)", borderRadius: 8, padding: "14px 40px 14px 14px", fontFamily: "monospace", fontSize: "0.78rem", color: "#e2e8f0", whiteSpace: "pre-wrap", wordBreak: "break-word", lineHeight: 1.6 }}>
      <div style={{ position: "absolute", top: 8, right: 8 }}><CopyBtn text={code} /></div>
      {code}
    </div>
  );
}

export default function ApiDocs() {
  const [lang, setLang] = useState<"curl" | "python" | "node">("curl");
  const [active, setActive] = useState(0);
  const ep = ENDPOINTS[active];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1160, color: "#e2e8f0" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
        <Terminal size={28} color="#a78bfa" />
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, margin: 0 }}>DocIntel API Reference</h1>
          <p style={{ margin: 0, fontSize: "0.85rem", color: "#94a3b8" }}>
            Vision-first document extraction — 15 endpoints across extraction, classification, batch and mobile capture
          </p>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 12, margin: "20px 0" }}>
        {[
          { icon: Globe, label: "Base URL", value: BASE_URL, color: "#38bdf8" },
          { icon: Shield, label: "Auth", value: "X-OmniIntel-Internal-Token", color: "#4ade80" },
          { icon: Zap, label: "Format", value: "REST · multipart / JSON", color: "#f59e0b" },
          { icon: BookOpen, label: "Interactive docs", value: "/docs (Swagger)", color: "#a78bfa" },
        ].map(({ icon: Icon, label, value, color }) => (
          <div key={label} style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, padding: "12px 16px", display: "flex", gap: 10, alignItems: "center" }}>
            <Icon size={18} color={color} />
            <div>
              <div style={{ fontSize: "0.7rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600, wordBreak: "break-all" }}>{value}</div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ background: "rgba(167,139,250,0.08)", border: "1px solid rgba(167,139,250,0.25)", borderRadius: 10, padding: "12px 16px", marginBottom: 20, fontSize: "0.8rem", color: "#c4b5fd", lineHeight: 1.6 }}>
        <strong style={{ color: "#e2e8f0" }}>Auth:</strong> when <code>REQUIRE_INTERNAL_TOKEN=true</code> on the server, every
        route except <code>/</code>, <code>/health</code>, <code>/docs</code>, <code>/openapi.json</code> and the static asset
        paths requires an <code>X-OmniIntel-Internal-Token</code> header (or an <code>Authorization</code> header containing the
        token) matching the server's <code>OMNIINTEL_INTERNAL_TOKEN</code>. Requests without a valid token get{" "}
        <code>403</code>.
        <br />
        <strong style={{ color: "#e2e8f0" }}>Vision route selection:</strong> the extraction endpoints take a{" "}
        <code>route</code> form field with three values —{" "}
        <code>vision_route_a</code> (Claude Sonnet 4.6 Vision, premium, no fallback),{" "}
        <code>vision_route_b</code> (Ollama vision — local or remote, mode via <code>ROUTE_B_MODE</code> and{" "}
        <code>OLLAMA_MODEL</code> env vars — auto-falls back to Route C on failure), and{" "}
        <code>ocr_fallback</code> (Tesseract OCR + LLM cleanup, Route C). The legacy names{" "}
        <code>vision_premium</code> and <code>vision_local</code> are still accepted and mapped to Route A / Route B
        respectively for backward compatibility.
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 20 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {GROUP_ORDER.map((group) => (
            <div key={group}>
              <div style={{ fontSize: "0.7rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>
                {group}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {ENDPOINTS.map((e, i) => e.group === group && (
                  <button
                    key={i}
                    onClick={() => setActive(i)}
                    style={{
                      textAlign: "left",
                      background: active === i ? "rgba(124,58,237,0.15)" : "rgba(255,255,255,0.03)",
                      border: active === i ? "1px solid rgba(124,58,237,0.4)" : "1px solid rgba(255,255,255,0.07)",
                      borderRadius: 8,
                      padding: "10px 14px",
                      cursor: "pointer",
                    }}
                  >
                    <span style={{
                      fontSize: "0.68rem", fontWeight: 700, fontFamily: "monospace",
                      background: e.method === "GET" ? "rgba(56,189,248,0.15)" : "rgba(167,139,250,0.15)",
                      color: e.method === "GET" ? "#38bdf8" : "#a78bfa",
                      borderRadius: 4, padding: "2px 6px", marginRight: 8,
                    }}>{e.method}</span>
                    <span style={{ fontSize: "0.8rem", fontFamily: "monospace", color: active === i ? "#e2e8f0" : "#94a3b8" }}>{e.path}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, padding: "16px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
              <span style={{
                fontSize: "0.75rem", fontWeight: 700, fontFamily: "monospace",
                background: ep.method === "GET" ? "rgba(56,189,248,0.15)" : "rgba(167,139,250,0.15)",
                color: ep.method === "GET" ? "#38bdf8" : "#a78bfa",
                borderRadius: 5, padding: "3px 8px",
              }}>{ep.method}</span>
              <code style={{ fontSize: "0.9rem", wordBreak: "break-all" }}>{BASE_URL}{ep.path}</code>
              {!ep.auth && (
                <span style={{ fontSize: "0.68rem", fontWeight: 600, color: "#4ade80", background: "rgba(74,222,128,0.12)", borderRadius: 4, padding: "2px 8px" }}>
                  no auth required
                </span>
              )}
            </div>
            <p style={{ margin: 0, fontSize: "0.85rem", color: "#94a3b8", lineHeight: 1.6 }}>{ep.desc}</p>
          </div>

          {ep.body && (
            <div>
              <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
                <Code2 size={13} /> Request body
              </div>
              <CodeBlock code={ep.body} />
            </div>
          )}

          <div>
            <div style={{ display: "flex", gap: 6, marginBottom: 8, alignItems: "center" }}>
              <span style={{ fontSize: "0.75rem", color: "#64748b", marginRight: 4 }}>Language:</span>
              {(["curl", "python", "node"] as const).map((l) => (
                <button
                  key={l}
                  onClick={() => setLang(l)}
                  style={{
                    padding: "4px 12px", borderRadius: 6, border: "1px solid",
                    borderColor: lang === l ? "#7c3aed" : "rgba(255,255,255,0.1)",
                    background: lang === l ? "rgba(124,58,237,0.2)" : "transparent",
                    color: lang === l ? "#c4b5fd" : "#94a3b8",
                    cursor: "pointer", fontSize: "0.78rem", fontWeight: 600,
                  }}
                >
                  {l}
                </button>
              ))}
            </div>
            <CodeBlock code={SNIPPETS[lang](ep)} />
          </div>

          <div>
            <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
              <Check size={13} color="#4ade80" /> Sample response
            </div>
            <CodeBlock code={ep.response} />
          </div>
        </div>
      </div>
    </div>
  );
}
