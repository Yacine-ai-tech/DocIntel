import { useMemo, useState } from "react";
import { Check, ChevronDown, ChevronRight, Copy } from "lucide-react";

/** Lightweight collapsible JSON tree (no editor dependency — Monaco is banned). */
function Node({ k, v, depth }: { k?: string; v: unknown; depth: number }) {
  const [open, setOpen] = useState(depth < 2);
  const pad = { paddingLeft: depth * 16 };
  const key = k !== undefined && (
    <span style={{ color: "var(--accent-2)" }} className="brightness-150">
      "{k}"
    </span>
  );
  const colon = k !== undefined ? ": " : "";

  if (v !== null && typeof v === "object") {
    const isArr = Array.isArray(v);
    const entries = isArr ? (v as unknown[]).map((x, i) => [i, x] as const) : Object.entries(v as object);
    const brackets = isArr ? ["[", "]"] : ["{", "}"];
    return (
      <div>
        <div
          style={pad}
          className="flex cursor-pointer items-center gap-1 rounded px-1 hover:bg-surface-2"
          onClick={() => setOpen((o) => !o)}
        >
          {open ? <ChevronDown size={12} className="shrink-0 text-muted" /> : <ChevronRight size={12} className="shrink-0 text-muted" />}
          <span className="truncate">
            {key}
            {colon}
            <span className="text-muted">
              {brackets[0]}
              {!open && ` …${entries.length} ${brackets[1]}`}
            </span>
          </span>
        </div>
        {open && (
          <>
            {entries.map(([kk, vv]) => (
              <Node key={String(kk)} k={isArr ? undefined : String(kk)} v={vv} depth={depth + 1} />
            ))}
            <div style={pad} className="px-1 text-muted">
              <span className="pl-4">{brackets[1]}</span>
            </div>
          </>
        )}
      </div>
    );
  }

  const color =
    typeof v === "string" ? "var(--success)" : typeof v === "number" ? "var(--warning)" : "var(--danger)";
  return (
    <div style={pad} className="truncate px-1 pl-5">
      {key}
      {colon}
      <span style={{ color }}>{typeof v === "string" ? `"${v}"` : String(v)}</span>
    </div>
  );
}

export function JSONViewer({ data, maxHeight = 420 }: { data: unknown; maxHeight?: number }) {
  const [copied, setCopied] = useState(false);
  const text = useMemo(() => JSON.stringify(data, null, 2), [data]);
  return (
    <div className="relative rounded-xl border border-line bg-bg">
      <button
        className="absolute right-2 top-2 z-10 flex items-center gap-1 rounded-lg border border-line bg-surface px-2 py-1 text-[11px] text-dim hover:text-body"
        onClick={() => {
          navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        }}
      >
        {copied ? <Check size={11} className="text-ok" /> : <Copy size={11} />}
        {copied ? "Copied" : "Copy"}
      </button>
      <div
        className="num overflow-auto p-3 font-mono text-[12px] leading-5"
        style={{ maxHeight }}
      >
        <Node v={data} depth={0} />
      </div>
    </div>
  );
}
