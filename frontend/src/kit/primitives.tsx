import React from "react";
import { motion } from "framer-motion";
import { LucideIcon, Inbox } from "lucide-react";

/* ---------- Button ---------- */
type BtnVariant = "primary" | "secondary" | "ghost" | "danger";
export function Button({
  variant = "primary",
  className = "",
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant }) {
  const base =
    "inline-flex items-center gap-2 rounded-btn px-4 py-2 text-sm font-medium transition-all duration-150 disabled:opacity-40 disabled:pointer-events-none active:translate-y-px";
  const styles: Record<BtnVariant, string> = {
    primary: "text-[#0e0d09] shadow-card hover:brightness-110",
    secondary: "border border-line-strong text-body hover:bg-surface-2",
    ghost: "text-dim hover:text-body hover:bg-surface-2",
    danger: "border border-line-strong text-bad hover:bg-surface-2",
  };
  return (
    <button
      className={`${base} ${styles[variant]} ${className}`}
      style={variant === "primary" ? { background: "var(--accent-grad)" } : undefined}
      {...rest}
    >
      {children}
    </button>
  );
}

/* ---------- Card ---------- */
export function Card({
  title,
  actions,
  className = "",
  children,
  hover = false,
}: {
  title?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
  hover?: boolean;
}) {
  return (
    <div
      className={`rounded-card border border-line bg-surface shadow-card ${
        hover ? "transition-transform duration-150 hover:-translate-y-px" : ""
      } ${className}`}
    >
      {(title || actions) && (
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <div className="text-sm font-semibold text-body">{title}</div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  );
}

/* ---------- StatTile ---------- */
export function StatTile({
  label,
  value,
  sub,
  delta,
  icon: Icon,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  delta?: { text: string; good?: boolean };
  icon?: LucideIcon;
}) {
  return (
    <div className="rounded-card border border-line bg-surface p-5 shadow-card">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-muted">{label}</span>
        {Icon && <Icon size={15} className="text-muted" />}
      </div>
      <div className="num mt-2 text-[28px] font-bold leading-none text-body">{value}</div>
      <div className="mt-2 flex items-center gap-2 text-xs">
        {delta && (
          <span className={delta.good === false ? "text-bad" : "text-ok"}>{delta.text}</span>
        )}
        {sub && <span className="text-muted">{sub}</span>}
      </div>
    </div>
  );
}

/* ---------- ConfidenceBadge (High/Medium/Low — never a bare %) ---------- */
export function ConfidenceBadge({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-xs text-muted">—</span>;
  const pct = value > 1 ? value / 100 : value;
  const level = pct >= 0.85 ? "High" : pct >= 0.6 ? "Medium" : "Low";
  const color = pct >= 0.85 ? "var(--success)" : pct >= 0.6 ? "var(--warning)" : "var(--danger)";
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full border border-line px-2.5 py-1 text-xs font-medium"
      title={`confidence ${(pct * 100).toFixed(0)}%`}
    >
      <span style={{ color }}>{level}</span>
      <span className="h-1 w-12 overflow-hidden rounded-full bg-surface-2">
        <motion.span
          className="block h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${Math.round(pct * 100)}%` }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        />
      </span>
    </span>
  );
}

/* ---------- DemoBadge — REQUIRED on any non-live element ---------- */
export function DemoBadge({ label = "Demo data" }: { label?: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-line px-2 py-0.5 text-[11px] font-medium text-warn">
      {label}
    </span>
  );
}

/* ---------- EmptyState ---------- */
export function EmptyState({
  icon: Icon = Inbox,
  title,
  hint,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-14 text-center">
      <Icon size={26} className="text-muted" strokeWidth={1.5} />
      <div className="text-sm font-medium text-dim">{title}</div>
      {hint && <div className="max-w-sm text-xs text-muted">{hint}</div>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

/* ---------- Skeleton ---------- */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-2 ${className}`} />;
}

/* ---------- Chip ---------- */
export function Chip({
  children,
  tone = "default",
  title,
  className = "",
}: {
  children: React.ReactNode;
  tone?: "default" | "ok" | "warn" | "bad" | "accent";
  title?: string;
  className?: string;
}) {
  const tones = {
    default: "text-dim border-line",
    ok: "text-ok border-line",
    warn: "text-warn border-line",
    bad: "text-bad border-line",
    accent: "text-body border-line-strong",
  } as const;
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
