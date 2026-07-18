import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LabelList,
} from "recharts";
import { PageHeader } from "../kit/AppShell";
import { Card, StatTile } from "../kit/primitives";
import { FileCheck2, Globe2, Landmark, ScanLine } from "lucide-react";

/* All figures verified against eval/BENCHMARK.md and eval/SROIE_BENCHMARK.md
   (GAP_REPORT.md §4). Do not edit without re-running the benchmark. */

const ROUTE_COMPARISON = [
  { set: "Invoices (multilingual, multi-page)", "Claude Vision (A)": 100, "Local qwen2.5-VL (B)": 64.1, "OCR + LLM (C)": 100 },
  { set: "Receipts (CORD phone photos)", "Claude Vision (A)": 92.5, "Local qwen2.5-VL (B)": 77.0, "OCR + LLM (C)": 28.5 },
  { set: "French + FCFA invoice", "Claude Vision (A)": 100, "Local qwen2.5-VL (B)": 100, "OCR + LLM (C)": 100 },
];

const BARS = [
  { key: "Claude Vision (A)", color: "var(--accent)" },
  { key: "Local qwen2.5-VL (B)", color: "#4aa8ff" },
  { key: "OCR + LLM (C)", color: "#6d7785" },
];

export default function Benchmarks() {
  return (
    <div>
      <PageHeader
        title="Benchmarks"
        sub={
          <>
            A released, reproducible benchmark on <strong>real third-party documents</strong> (CORD-v2,
            invoice2data, FUNSD, SROIE). Full methodology in{" "}
            <a
              className="underline decoration-dotted hover:text-body"
              href="https://github.com/Yacine-ai-tech/DocIntel/blob/master/eval/BENCHMARK.md"
              target="_blank"
              rel="noreferrer"
            >
              eval/BENCHMARK.md
            </a>
            .
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Robustness at scale"
          value="550 / 550"
          sub="documents ingested, 0 unhandled errors"
          delta={{ text: "100% success" }}
          icon={FileCheck2}
        />
        <StatTile
          label="Route A · invoices"
          value="39 / 39"
          sub="multilingual, multi-page field accuracy"
          delta={{ text: "100%" }}
          icon={Globe2}
        />
        <StatTile
          label="SROIE zero-shot"
          value="95.0%"
          sub="ICDAR-2019 Task 3 — no task-specific training"
          icon={ScanLine}
        />
        <StatTile
          label="French + FCFA (XOF)"
          value="7 / 7"
          sub="UEMOA convention, 18% TVA — Routes A & C"
          delta={{ text: "100%" }}
          icon={Landmark}
        />
      </div>

      <Card title="Field accuracy by route" className="mt-5">
        <div className="h-[340px]">
          {!Array.isArray(ROUTE_COMPARISON) || ROUTE_COMPARISON.length === 0 ? (
             <div className="text-sm text-muted">No benchmark data.</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={ROUTE_COMPARISON} margin={{ top: 18, right: 8, left: -18, bottom: 0 }} barGap={4}>
                <CartesianGrid stroke="var(--grid-line)" vertical={false} />
                <XAxis
                  dataKey="set"
                  tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                  axisLine={{ stroke: "var(--border)" }}
                  tickLine={false}
                  interval={0}
                />
                <YAxis
                  unit="%"
                  domain={[0, 100]}
                  tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,.03)" }}
                  contentStyle={{
                    background: "var(--surface-2)",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 12,
                    color: "var(--text)",
                    fontSize: 12,
                  }}
                  formatter={(v: number) => [`${v}%`]}
                />
                {BARS.map((b) => (
                  <Bar key={b.key} dataKey={b.key} fill={b.color} radius={[6, 6, 0, 0]} maxBarSize={44} isAnimationActive={false}>
                    <LabelList dataKey={b.key} position="top" formatter={(v: number) => `${v}%`} style={{ fill: "var(--text-2)", fontSize: 10 }} />
                  </Bar>
                ))}
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        <p className="mt-3 text-xs leading-5 text-muted">
          Receipts are the central finding: premium vision reads crumpled thermal-paper photos at 92.5%
          where pure OCR collapses to 28.5% — and the fully-private local route holds 77% at zero API cost.
          Invoices: Route A scores 100% including a total that appears only on page 2. SROIE detail: company
          95% · date 90% · total 100% (see eval/SROIE_BENCHMARK.md).
        </p>
      </Card>

      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        <Card title="Corpus">
          <ul className="space-y-2 text-[13px] text-dim">
            <li><strong className="text-body">494</strong> CORD-v2 phone-photo receipts (IDR ground truth)</li>
            <li><strong className="text-body">6</strong> invoice2data invoices — EN/FR/DE/NL, multi-page</li>
            <li><strong className="text-body">50</strong> FUNSD noisy scanned forms (handwriting)</li>
          </ul>
        </Card>
        <Card title="Scoring">
          <p className="text-[13px] leading-6 text-dim">
            Only fields present in each ground-truth record are scored. Numeric tolerance max(0.02, 1%);
            vendor by case-insensitive substring; identifiers &amp; dates exact; currency normalized to ISO-4217.
          </p>
        </Card>
        <Card title="Reproduce">
          <pre className="num overflow-x-auto rounded-xl border border-line bg-bg p-3 font-mono text-[11.5px] leading-5 text-dim">{`python eval/build_corpus.py --target 500
python eval/run_benchmark.py --scale-only \\
  --concurrency 12`}</pre>
        </Card>
      </div>
    </div>
  );
}
