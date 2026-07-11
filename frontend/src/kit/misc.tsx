import React from "react";
import { motion } from "framer-motion";
import { Check, Loader2, RefreshCw } from "lucide-react";
import { Button } from "./primitives";

/* ---------- ExecutionStages — streaming state list, never typing dots ---------- */
export function ExecutionStages({
  stages,
  active,
  done = false,
}: {
  stages: string[];
  active: number;
  done?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      {stages.map((s, i) => {
        const complete = done || i < active;
        const running = !done && i === active;
        if (!complete && !running) return null;
        return (
          <motion.div
            key={s}
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-2 text-[13px]"
          >
            {complete ? (
              <Check size={13} className="text-ok" strokeWidth={3} />
            ) : (
              <Loader2 size={13} className="animate-spin" style={{ color: "var(--accent)" }} />
            )}
            <span className={complete ? "text-muted" : "text-body"}>{s}</span>
          </motion.div>
        );
      })}
    </div>
  );
}

/* ---------- WakingBackend — Render free tier cold-start state ---------- */
export function WakingBackend({ onRetry, waking }: { onRetry: () => void; waking: boolean }) {
  return (
    <div className="flex h-full min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <img src="/mark.png" alt="" className="h-14 w-14 rounded-2xl border border-line object-cover opacity-80" />
      <div>
        <div className="text-[15px] font-semibold text-body">
          {waking ? "Waking the backend…" : "Backend unreachable"}
        </div>
        <div className="mx-auto mt-1 max-w-xs text-[13px] text-muted">
          {waking
            ? "Free-tier services sleep when idle. First start can take up to a minute."
            : "Could not reach the API. It may still be starting."}
        </div>
      </div>
      {waking ? (
        <Loader2 size={18} className="animate-spin" style={{ color: "var(--accent)" }} />
      ) : (
        <Button variant="secondary" onClick={onRetry}>
          <RefreshCw size={14} /> Retry
        </Button>
      )}
    </div>
  );
}

/* ---------- Field / label helpers ---------- */
export function Label({ children }: { children: React.ReactNode }) {
  return (
    <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted">
      {children}
    </label>
  );
}

export function Select({
  value,
  onChange,
  options,
  className = "",
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  className?: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`rounded-input border border-line-strong bg-surface-2 px-3 py-2 text-sm text-body outline-none focus:border-[var(--accent)] ${className}`}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

/* ---------- Segmented control ---------- */
export function Segmented({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: React.ReactNode; hint?: string }[];
}) {
  return (
    <div className="inline-flex rounded-xl border border-line bg-surface-2 p-1">
      {options.map((o) => (
        <button
          key={o.value}
          title={o.hint}
          onClick={() => onChange(o.value)}
          className={`relative rounded-lg px-3 py-1.5 text-[13px] font-medium transition-colors ${
            value === o.value ? "text-body" : "text-muted hover:text-dim"
          }`}
        >
          {value === o.value && (
            <motion.span
              layoutId="segmented-pill"
              className="absolute inset-0 rounded-lg border border-line-strong bg-surface"
              transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            />
          )}
          <span className="relative">{o.label}</span>
        </button>
      ))}
    </div>
  );
}
