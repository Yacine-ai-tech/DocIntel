import type { ComponentType, ReactNode } from "react";
import {
  BookOpen, GitBranch, Coins, Layers, PenTool, Languages, FileType, Camera,
  UploadCloud, BarChart3, ShieldAlert, CheckCircle, Code2,
} from "lucide-react";

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-gray-900 p-4 rounded-lg border border-gray-700 ${className}`}>{children}</div>
  );
}

function Section({
  icon: Icon, iconColor, title, children,
}: {
  icon: ComponentType<{ className?: string }>;
  iconColor: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl">
      <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-white">
        <Icon className={`w-6 h-6 ${iconColor}`} /> {title}
      </h2>
      {children}
    </section>
  );
}

export default function UserGuidePage() {
  return (
    <div className="p-8 max-w-5xl mx-auto h-full overflow-y-auto">
      <div className="flex items-center gap-3 mb-8">
        <BookOpen className="w-10 h-10 text-blue-500" />
        <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-600">
          DocIntel User Guide
        </h1>
      </div>

      <p className="text-lg text-gray-300 mb-8 leading-relaxed">
        DocIntel is a vision-first document intelligence pipeline: upload a PDF, image, or scan and
        get back structured fields, tables, and text — with three extraction routes trading off
        accuracy, privacy, and cost, and deterministic post-processing for currency and dates.
      </p>

      <div className="space-y-8 text-gray-200">

        {/* Route cascade */}
        <Section icon={GitBranch} iconColor="text-purple-400" title="The 3-Route Extraction Cascade">
          <p className="text-sm text-gray-300 mb-4">
            Every extraction endpoint (<code>/process</code>, <code>/extract</code>,{" "}
            <code>/batch/upload</code>) takes a <code>route</code> parameter selecting one of three
            engines. Route B automatically falls back to Route C on failure; Route A does not
            fall back (it fails explicitly so callers know premium extraction was attempted).
          </p>
          <div className="space-y-4">
            <Card>
              <h3 className="font-semibold text-blue-400 text-lg mb-2">Route A — <code>vision_route_a</code> (Claude Sonnet 4.6 Vision, premium)</h3>
              <p className="text-sm text-gray-300">
                Cloud vision LLM via LiteLLM (<code>LLM_VISION_ROUTE_A</code>, default{" "}
                <code>anthropic/claude-sonnet-4-6</code>). Highest accuracy on complex, multilingual,
                and multi-page layouts. No automatic fallback — use it when correctness matters more
                than cost. Legacy alias: <code>vision_premium</code>.
              </p>
            </Card>
            <Card>
              <h3 className="font-semibold text-green-400 text-lg mb-2">Route B — <code>vision_route_b</code> (Ollama vision, local or remote)</h3>
              <p className="text-sm text-gray-300">
                Any Ollama-served vision model (default <code>qwen2.5vl:7b</code> via{" "}
                <code>OLLAMA_MODEL</code>), running on a local/LAN GPU or a remote Ollama-compatible
                endpoint (<code>ROUTE_B_MODE=local|remote</code>). Zero per-request API cost and
                fully private — data never leaves the host. Automatically falls back to Route C if
                the model call fails. Legacy alias: <code>vision_local</code>.
              </p>
            </Card>
            <Card>
              <h3 className="font-semibold text-amber-400 text-lg mb-2">Route C — <code>ocr_fallback</code> (Tesseract + LLM cleanup)</h3>
              <p className="text-sm text-gray-300">
                Tesseract OCR extracts raw text, then a cheap LLM (<code>LLM_CLEANUP</code>, default{" "}
                <code>anthropic/claude-haiku-4-5</code>) structures it into fields. Cheapest and
                fastest route; excellent on clean, born-digital documents but loses accuracy on
                noisy phone-photo scans (see benchmark numbers below). Also the automatic landing
                spot when Route B fails.
              </p>
            </Card>
          </div>
          <p className="text-sm text-gray-400 mt-4">
            <strong className="text-gray-300">Choosing a route:</strong> Route A for maximum
            accuracy or when a document is complex/handwritten/mixed-language; Route B when data
            privacy or zero API cost matters and a GPU is available; Route C for high-volume, clean
            documents where cost and latency dominate.
          </p>
        </Section>

        {/* Currency normalization */}
        <Section icon={Coins} iconColor="text-yellow-400" title="Currency Normalization">
          <p className="text-sm text-gray-300 mb-3">
            Extracted amounts and currencies are run through a deterministic post-processing layer
            (<code>services/normalize.py</code>) rather than trusted to the LLM's locale parsing.
            It recognizes <strong className="text-white">54 ISO-4217 currency codes</strong> directly
            (USD, EUR, GBP, JPY, CNY, INR, XOF, XAF, and 48 more), plus symbol and word aliases —{" "}
            <code>FCFA</code> / <code>F CFA</code> / <code>CFA</code> for the{" "}
            <strong className="text-white">West African CFA franc (XOF)</strong>, <code>US$</code>,{" "}
            <code>RM</code>, <code>Rs</code>, <code>zł</code>, <code>Kč</code>, and currency symbols
            (€ £ ¥ ₹ ₩ ₫ ฿ ₱ ₦ ₽ ₪ ₺).
          </p>
          <p className="text-sm text-gray-300">
            Numeric amounts in US (<code>1,234.56</code>), European (<code>1.234,56</code>), spaced
            (<code>1 234 567</code>), and Swiss (<code>1'234.56</code>) formats are all converted to
            plain floats, with parenthesised negatives handled too — the rightmost{" "}
            <code>.</code>/<code>,</code> is treated as the decimal mark.
          </p>
        </Section>

        {/* Multi-page / large documents */}
        <Section icon={Layers} iconColor="text-cyan-400" title="Multi-Page & Large Document Handling">
          <p className="text-sm text-gray-300 mb-3">
            PDFs are handled as genuinely multi-page: vision routes receive every page as an image
            and reason across all of them together (a grand total that only appears on page 2 is
            still captured), while the OCR route concatenates text from every page.
          </p>
          <p className="text-sm text-gray-300 mb-3">
            Large documents use <strong className="text-white">chunked map-reduce</strong>: Route A
            sends up to <code>VISION_PAGES_PER_CALL</code> (default 8) pages per model call, Route B
            sends up to <code>VISION_PAGES_PER_CALL_LOCAL</code> (default 2, since local models have
            smaller context windows), and per-chunk results are merged back into one document. A
            hard ceiling of <code>MAX_PDF_PAGES</code> / <code>MAX_VISION_PAGES</code> (default{" "}
            <strong className="text-white">200 pages</strong>) bounds cost and latency.
          </p>
          <p className="text-sm text-gray-300">
            For 100+ page documents, the OCR route (Route C, validated on a 120-page PDF) or Route A
            is recommended over Route B, whose smaller local context window is the limiting factor.
          </p>
        </Section>

        {/* Handwriting */}
        <Section icon={PenTool} iconColor="text-pink-400" title="Handwriting Support">
          <p className="text-sm text-gray-300 mb-3">
            Vision-route prompts explicitly instruct the model to transcribe handwritten values
            alongside printed text, and the <code>form</code> document type includes checkbox states
            (true/false) and handwritten field entries in its schema.
          </p>
          <p className="text-sm text-gray-300">
            Route C also exposes a dedicated Tesseract handwriting path
            (<code>extract_handwriting</code>) for OCR-only pipelines. Robustness on noisy, scanned,
            handwritten forms is validated against the FUNSD dataset (50 documents) as part of the
            scale/ingestion benchmark — see the numbers below.
          </p>
        </Section>

        {/* Multilingual OCR */}
        <Section icon={Languages} iconColor="text-indigo-400" title="Multilingual OCR">
          <p className="text-sm text-gray-300 mb-3">
            Route C (Tesseract) loads language packs for{" "}
            <strong className="text-white">English, French, German, Dutch, Spanish, and Italian</strong>{" "}
            by default (<code>OCR_LANGS=eng+fra+deu+nld+spa+ita</code>), and gracefully falls back to
            English-only if a requested pack isn't installed on the host.
          </p>
          <p className="text-sm text-gray-300">
            Vision routes (A and B) are not limited to this list — the underlying vision-LLM reads
            whatever language appears in the document image. The invoice benchmark set specifically
            covers EN/FR/DE/NL multi-page invoices, and a French-language, FCFA-denominated invoice
            is separately benchmarked (see below).
          </p>
        </Section>

        {/* Document types */}
        <Section icon={FileType} iconColor="text-orange-400" title="Supported Document Types">
          <p className="text-sm text-gray-300 mb-3">
            Each <code>doc_type</code> maps to its own extraction schema (<code>services/vision_extractor.py</code>):
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              ["invoice", "vendor, invoice_number, date, due_date, line_items, subtotal, tax, total, currency"],
              ["contract", "parties, effective_date, expiration_date, payment_terms, governing_law, term, key_clauses, signatures"],
              ["receipt", "merchant, date, total, currency, tax, items, payment_method"],
              ["financial_report", "period, revenue, cogs, opex, ebitda, net_income, key_metrics_summary"],
              ["auction_listing", "item_title, category, condition, asking_price, currency, location, key_specs"],
              ["form", "form_title, fields{label: value} (handwritten + checkboxes)"],
            ].map(([type, schema]) => (
              <Card key={type}>
                <div className="font-mono text-sm text-blue-300 mb-1">{type}</div>
                <div className="text-xs text-gray-400">{schema}</div>
              </Card>
            ))}
          </div>
          <p className="text-sm text-gray-400 mt-3">
            Passing <code>doc_type=auto</code> to <code>/process</code> content-classifies the
            document first (falling back to a filename heuristic), then runs the chosen route.
          </p>
        </Section>

        {/* Camera / mobile pairing */}
        <Section icon={Camera} iconColor="text-red-400" title="Camera / Mobile QR-Pairing Workflow">
          <ol className="space-y-2 text-sm text-gray-300 list-decimal list-inside">
            <li>The desktop app calls <code>POST /camera/pair</code>, which returns a pairing token
              (24-hour expiry) and a base64-encoded QR code image.</li>
            <li>The user scans the QR code with their phone camera. It encodes a URL to this
              frontend's <code>/camera/mobile?token=...</code> route (<code>CameraMobile.tsx</code>).</li>
            <li>The phone (now a lightweight mobile capture page) takes a photo and{" "}
              <code>POST</code>s it to <code>/camera/upload</code> with the pairing token,{" "}
              the file, and an optional <code>doc_type</code>.</li>
            <li>The server validates the token is active and unexpired (403 otherwise), records the
              upload against the session, and automatically routes the photo through{" "}
              <strong className="text-white">Route B</strong> (local/self-hosted Ollama vision) —
              falling back to Route C (OCR) on any failure.</li>
            <li>The extraction result is returned to the <strong className="text-white">phone's</strong>{" "}
              own HTTP response, but the desktop dashboard (<code>CameraDashboard.tsx</code>) never
              sees that response directly — it polls{" "}
              <code>GET /camera/status/{"{token}"}</code> every few seconds while showing the QR
              code, and displays <code>last_result</code> the moment it appears.</li>
          </ol>
          <p className="text-sm text-amber-300/90 mt-3">
            Requires HTTPS (or <code>localhost</code>) — most mobile browsers refuse camera capture
            on a plain <code>http://</code> origin. Set <code>FRONTEND_URL</code> to wherever your
            phone can actually reach the frontend, or the QR code will encode an unreachable address.
          </p>
        </Section>

        {/* Batch upload */}
        <Section icon={UploadCloud} iconColor="text-teal-400" title="Batch Upload">
          <p className="text-sm text-gray-300 mb-3">
            <code>POST /batch/upload</code> accepts multiple files (<code>.pdf</code>,{" "}
            <code>.png</code>, <code>.jpg</code>/<code>.jpeg</code>, <code>.tiff</code>) in a single
            request and returns a <code>job_id</code> immediately — processing runs in the
            background. Files are processed concurrently with a bounded semaphore
            (<code>BATCH_MAX_CONCURRENCY</code>, default 8) and each file is isolated: one failure
            never aborts the batch.
          </p>
          <p className="text-sm text-gray-300 mb-3">
            Poll <code>GET /batch/{"{job_id}"}</code> for progress (<code>processed</code>,{" "}
            <code>failed</code>, <code>percent</code>), then fetch{" "}
            <code>GET /batch/{"{job_id}"}/results</code> for the index-aligned array of per-file
            results once complete. The scale benchmark below exercised 550 documents through this
            same concurrent pipeline with zero unhandled errors.
          </p>
          <p className="text-sm text-gray-300">
            Prefer a callback over polling? Pass a <code>webhook_url</code> form field and DocIntel
            POSTs <code>{"{job_id, status, total, processed, failed, finished_at, results}"}</code> to
            it the moment the job completes — the integration point for n8n or any workflow
            automation tool (see <code>docs/n8n/README.md</code> in the repo for a worked example,
            including an importable n8n workflow template).
          </p>
        </Section>

        {/* Benchmarks */}
        <Section icon={BarChart3} iconColor="text-lime-400" title="Real Benchmark Numbers">
          <p className="text-sm text-gray-300 mb-3">
            From <code>eval/BENCHMARK.md</code> — a 550-document corpus (CORD-v2 receipts, invoice2data
            EN/FR/DE/NL invoices, FUNSD handwritten forms) — and <code>eval/SROIE_BENCHMARK.md</code>.
            Numbers are reproducible via the scripts referenced in those files.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left border-collapse">
              <thead>
                <tr className="text-gray-400 border-b border-gray-700">
                  <th className="py-2 pr-4">Measure</th>
                  <th className="py-2 pr-4">Route / Engine</th>
                  <th className="py-2">Result</th>
                </tr>
              </thead>
              <tbody className="text-gray-300">
                {[
                  ["Ingestion at scale (550 docs)", "OCR ingestion, no LLM", "550/550 = 100.0% (0 failures)"],
                  ["Invoices (39, multilingual multi-page)", "Route A — Claude Sonnet 4.6 Vision", "39/39 = 100%"],
                  ["Receipts (40, CORD phone photos)", "Route A — Claude Sonnet 4.6 Vision", "37/40 = 92.5%"],
                  ["Invoices (clean PDFs)", "Route C — Tesseract + LLM cleanup", "100%"],
                  ["Receipts (200, CORD phone photos)", "Route C — Tesseract + LLM cleanup", "57/200 = 28.5%"],
                  ["Receipts (100, CORD phone photos)", "Route B — Ollama qwen2.5-VL 7B (T4 GPU)", "77/100 = 77.0%"],
                  ["Invoices (39, multilingual multi-page)", "Route B — Ollama qwen2.5-VL 7B (T4 GPU)", "25/39 = 64.1%"],
                  ["French + FCFA (XOF) sample (7)", "Route A / Route C", "7/7 = 100% (both)"],
                  ["SROIE receipts (N=20, zero-shot)", "Route A — Claude Sonnet 4.6 Vision", "95.0% overall (57/60 fields)"],
                ].map(([measure, route, result]) => (
                  <tr key={measure} className="border-b border-gray-800">
                    <td className="py-2 pr-4">{measure}</td>
                    <td className="py-2 pr-4 font-mono text-xs">{route}</td>
                    <td className="py-2 font-semibold text-white">{result}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-500 mt-3">
            The SROIE figure is drawn from a small (N=20) Hugging Face mirror of the test split and
            is indicative rather than a full-test-set score; CORD (494 receipts) provides a larger
            second data point. Route B numbers are on a single NVIDIA T4 GPU, released after each
            run.
          </p>
        </Section>

        {/* Setup */}
        <Section icon={Code2} iconColor="text-gray-300" title="Environment Setup">
          <p className="text-sm text-gray-300 mb-3">
            To run DocIntel locally, set at minimum:
          </p>
          <ul className="list-disc list-inside text-sm font-mono text-green-300 space-y-2 ml-2 bg-gray-950 p-4 rounded-lg">
            <li><code>ANTHROPIC_API_KEY</code> — required for Route A</li>
            <li><code>OLLAMA_HOST</code> / <code>ROUTE_B_MODE</code> / <code>OLLAMA_MODEL</code> — Route B</li>
            <li><code>OMNIINTEL_INTERNAL_TOKEN</code> + <code>REQUIRE_INTERNAL_TOKEN=true</code> — gate the API</li>
          </ul>
          <p className="text-sm text-gray-300 mt-4">
            See <code>.env.example</code> for the full list. Start the backend with{" "}
            <code>uvicorn api:app</code> (or the project's Docker setup) and the frontend with{" "}
            <code>npm run dev</code> in <code>frontend/</code>.
          </p>
        </Section>

        {/* Security */}
        <Section icon={ShieldAlert} iconColor="text-red-400" title="Security & Best Practices">
          <ul className="space-y-3">
            <li className="flex items-start gap-2">
              <CheckCircle className="w-5 h-5 text-green-400 shrink-0 mt-0.5" />
              <span className="text-sm text-gray-300">
                Never commit <code>.env</code> files or hardcode API keys — credentials load
                dynamically via <code>os.getenv()</code>.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="w-5 h-5 text-green-400 shrink-0 mt-0.5" />
              <span className="text-sm text-gray-300">
                Set <code>REQUIRE_INTERNAL_TOKEN=true</code> and a strong{" "}
                <code>OMNIINTEL_INTERNAL_TOKEN</code> before exposing the API beyond localhost —
                without it, extraction routes are unauthenticated.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="w-5 h-5 text-green-400 shrink-0 mt-0.5" />
              <span className="text-sm text-gray-300">
                Pairing tokens for mobile capture expire after 24 hours and are single-purpose —
                treat a leaked QR code as a leaked upload credential for that window.
              </span>
            </li>
          </ul>
        </Section>

      </div>
    </div>
  );
}
