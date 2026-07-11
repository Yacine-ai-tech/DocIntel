import { useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ImagePlus, Sparkles, X, AlertTriangle } from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Button, Card, Chip, ConfidenceBadge, EmptyState } from "../kit/primitives";
import { ExecutionStages, Label } from "../kit/misc";
import { api, ClassifyImageResponse, logActivity } from "../lib/api";

const DEFAULT_CATS = ["tractor", "excavator", "crane", "forklift", "lathe"];

export default function ImageIntel() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [cats, setCats] = useState<string[]>(DEFAULT_CATS);
  const [catInput, setCatInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ClassifyImageResponse | null>(null);
  const [err, setErr] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const pick = (f: File | null) => {
    if (!f) return;
    setFile(f);
    setPreview((old) => { if (old) URL.revokeObjectURL(old); return URL.createObjectURL(f); });
    setResult(null);
  };

  const addCat = () => {
    const c = catInput.trim().toLowerCase();
    if (c && !cats.includes(c)) setCats((cs) => [...cs, c]);
    setCatInput("");
  };

  const run = async () => {
    if (!file || cats.length === 0) return;
    setBusy(true);
    setErr("");
    setResult(null);
    try {
      const res = await api.classifyImage(file, cats);
      setResult(res);
      logActivity({ kind: "classify-image", title: file.name, meta: { category: res.category, confidence: res.confidence } });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Image Intelligence"
        sub="Vision-first object classification — the auction-listing pattern. Give the model your categories; it returns the match, its confidence, and its reasoning."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Image">
          {!preview ? (
            <div
              onClick={() => inputRef.current?.click()}
              className="flex cursor-pointer flex-col items-center gap-3 rounded-xl border border-dashed border-line-strong px-6 py-16 text-center hover:border-[var(--accent)]"
            >
              <ImagePlus size={24} className="text-muted" strokeWidth={1.5} />
              <div className="text-sm font-medium text-dim">Drop or click to add an image</div>
              <div className="text-xs text-muted">PNG · JPEG · WEBP</div>
            </div>
          ) : (
            <div className="relative">
              <img src={preview} alt="" className="max-h-[420px] w-full rounded-lg object-contain" />
              <button
                className="absolute right-2 top-2 rounded-full border border-line bg-surface p-1.5 text-dim hover:text-body"
                onClick={() => { setFile(null); setPreview(null); setResult(null); }}
                aria-label="remove image"
              >
                <X size={14} />
              </button>
            </div>
          )}
          <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={(e) => pick(e.target.files?.[0] ?? null)} />

          <div className="mt-5">
            <Label>Categories</Label>
            <div className="flex flex-wrap items-center gap-2">
              {cats.map((c) => (
                <Chip key={c} tone="accent">
                  {c}
                  <button onClick={() => setCats((cs) => cs.filter((x) => x !== c))} aria-label={`remove ${c}`}>
                    <X size={11} className="text-muted hover:text-body" />
                  </button>
                </Chip>
              ))}
              <input
                value={catInput}
                onChange={(e) => setCatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addCat()}
                onBlur={addCat}
                placeholder="add category…"
                className="w-32 rounded-input border border-line bg-surface-2 px-2.5 py-1.5 text-xs text-body outline-none focus:border-[var(--accent)]"
              />
            </div>
          </div>

          <div className="mt-5">
            <Button onClick={run} disabled={!file || busy || cats.length === 0}>
              <Sparkles size={14} /> {busy ? "Classifying…" : "Classify"}
            </Button>
          </div>
        </Card>

        <Card title="Vision result">
          {busy ? (
            <ExecutionStages stages={["Uploading image", "Vision model reasoning", "Scoring categories"]} active={1} />
          ) : err ? (
            <div className="flex items-start gap-3">
              <AlertTriangle size={16} className="mt-0.5 text-bad" />
              <div className="text-[13px] text-dim">{err}</div>
            </div>
          ) : !result ? (
            <EmptyState title="No classification yet" hint="Add an image and your candidate categories, then run the vision model." />
          ) : result.error ? (
            <div className="flex items-start gap-3">
              <AlertTriangle size={16} className="mt-0.5 text-bad" />
              <div className="text-[13px] text-dim">{result.error}</div>
            </div>
          ) : (
            <AnimatePresence>
              <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
                <div className="text-xs font-medium uppercase tracking-wide text-muted">Detected category</div>
                <div className="mt-1 text-[26px] font-bold capitalize" style={{ color: "var(--accent)" }}>
                  {result.category}
                </div>
                <div className="mt-3 flex items-center gap-3">
                  <ConfidenceBadge value={result.confidence} />
                  {result.processing_time_ms != null && (
                    <span className="num text-xs text-muted">{(result.processing_time_ms / 1000).toFixed(1)}s</span>
                  )}
                </div>
                {result.reasoning && (
                  <div className="mt-5">
                    <div className="text-xs font-medium uppercase tracking-wide text-muted">Model reasoning</div>
                    <p className="mt-2 rounded-xl border border-line bg-surface-2 p-4 text-[13px] leading-6 text-dim">
                      {result.reasoning}
                    </p>
                  </div>
                )}
              </motion.div>
            </AnimatePresence>
          )}
        </Card>
      </div>
    </div>
  );
}
