import React, { useCallback, useEffect, useRef, useState } from "react";

/** Resizable two-pane split (v1/v2 layout requirement). Drag the divider; the ratio
 *  persists per `storageKey`. Collapses to stacked below `minWidth` viewport. */
export function SplitPane({
  left,
  right,
  storageKey,
  initial = 50,
  min = 25,
  max = 75,
}: {
  left: React.ReactNode;
  right: React.ReactNode;
  storageKey: string;
  initial?: number;
  min?: number;
  max?: number;
}) {
  const [pct, setPct] = useState<number>(() => {
    const saved = Number(localStorage.getItem(`split.${storageKey}`));
    return saved >= min && saved <= max ? saved : initial;
  });
  const [narrow, setNarrow] = useState(window.innerWidth < 1024);
  const ref = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  useEffect(() => {
    const onResize = () => setNarrow(window.innerWidth < 1024);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const onMove = useCallback(
    (e: PointerEvent) => {
      if (!dragging.current || !ref.current) return;
      const r = ref.current.getBoundingClientRect();
      const p = Math.min(max, Math.max(min, ((e.clientX - r.left) / r.width) * 100));
      setPct(p);
    },
    [min, max],
  );

  useEffect(() => {
    const up = () => {
      if (dragging.current) {
        dragging.current = false;
        document.body.style.cursor = "";
        setPct((p) => {
          localStorage.setItem(`split.${storageKey}`, String(Math.round(p)));
          return p;
        });
      }
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", up);
    };
  }, [onMove, storageKey]);

  if (narrow) return <div className="space-y-4">{left}{right}</div>;

  return (
    <div ref={ref} className="flex min-w-0 items-stretch gap-0">
      <div style={{ width: `${pct}%` }} className="min-w-0">{left}</div>
      <div
        role="separator"
        aria-orientation="vertical"
        title="Drag to resize"
        onPointerDown={() => { dragging.current = true; document.body.style.cursor = "col-resize"; }}
        className="group mx-1.5 flex w-2 shrink-0 cursor-col-resize items-center justify-center"
      >
        <div className="h-16 w-1 rounded-full bg-line-strong transition-colors group-hover:bg-[var(--accent)]" />
      </div>
      <div style={{ width: `${100 - pct}%` }} className="min-w-0">{right}</div>
    </div>
  );
}
