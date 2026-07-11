import { motion } from "framer-motion";
import { Check, Loader2, LucideIcon } from "lucide-react";

export type Stage = {
  id: string;
  label: string;
  icon?: LucideIcon;
  detail?: string;
};

/** The signature visual: a horizontal pipeline of stages with an animated active edge.
 *  `active` = index of the running stage; anything below it is complete.
 *  `done=true` marks every stage complete; `error` paints the active stage as failed. */
export function PipelineFlow({
  stages,
  active,
  done = false,
  error = false,
}: {
  stages: Stage[];
  active: number;
  done?: boolean;
  error?: boolean;
}) {
  return (
    <div className="flex w-full items-start overflow-x-auto py-2">
      {stages.map((s, i) => {
        const complete = done || i < active;
        const running = !done && i === active;
        const failed = error && running;
        return (
          <div key={s.id} className="flex min-w-0 flex-1 items-start">
            <div className="flex min-w-[72px] flex-1 flex-col items-center gap-1.5 px-1 text-center">
              <div
                className="flex h-8 w-8 items-center justify-center rounded-full border transition-colors"
                style={{
                  borderColor: complete || running ? "var(--accent)" : "var(--border-strong)",
                  background: complete ? "var(--accent)" : "var(--surface-2)",
                  color: complete ? "#0e0d09" : failed ? "var(--danger)" : running ? "var(--accent)" : "var(--text-muted)",
                }}
              >
                {complete ? (
                  <Check size={15} strokeWidth={3} />
                ) : running && !failed ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : s.icon ? (
                  <s.icon size={14} />
                ) : (
                  <span className="text-[11px] font-semibold">{i + 1}</span>
                )}
              </div>
              <div
                className={`text-[11px] font-medium leading-tight ${
                  complete || running ? "text-body" : "text-muted"
                }`}
              >
                {s.label}
              </div>
              {s.detail && <div className="text-[10px] text-muted">{s.detail}</div>}
            </div>
            {i < stages.length - 1 && (
              <div className="relative mt-4 h-px w-full min-w-4 flex-1 bg-line-strong">
                <motion.div
                  className="absolute inset-y-0 left-0"
                  style={{ background: "var(--accent)" }}
                  initial={false}
                  animate={{ width: complete ? "100%" : "0%" }}
                  transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
