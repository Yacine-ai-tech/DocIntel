import React, { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { LucideIcon, Menu, X } from "lucide-react";

export type NavItem = { to: string; label: string; icon: LucideIcon };

export function AppShell({
  product,
  tagline,
  nav,
  health,
  children,
}: {
  product: string;
  tagline: string;
  nav: NavItem[];
  health: "ok" | "down" | "checking";
  children: React.ReactNode;
}) {
  const [drawer, setDrawer] = useState(false);
  const loc = useLocation();
  useEffect(() => setDrawer(false), [loc.pathname]);

  const sidebar = (
    <div className="flex h-full w-60 flex-col border-r border-line bg-surface">
      <div className="flex items-center gap-3 px-5 py-5">
        <img src="/mark.png" alt="" className="h-9 w-9 rounded-xl border border-line object-cover" />
        <div className="min-w-0">
          <div className="truncate text-[15px] font-bold leading-tight text-body">{product}</div>
          <div className="truncate text-[11px] text-muted">{tagline}</div>
        </div>
      </div>
      <nav className="mt-1 flex-1 space-y-0.5 px-3">
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive ? "bg-surface-2 text-body" : "text-dim hover:bg-surface-2 hover:text-body"
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.span
                    layoutId="nav-rail"
                    className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full"
                    style={{ background: "var(--accent)" }}
                  />
                )}
                <Icon size={17} strokeWidth={1.8} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="flex items-center gap-2 border-t border-line px-5 py-4 text-xs text-muted">
        <span
          className="inline-block h-2 w-2 rounded-full"
          style={{
            background:
              health === "ok" ? "var(--success)" : health === "down" ? "var(--danger)" : "var(--warning)",
          }}
        />
        {health === "ok" ? "Backend online" : health === "down" ? "Backend unreachable" : "Checking…"}
      </div>
    </div>
  );

  return (
    <div className="flex h-full">
      <div className="hidden lg:block">{sidebar}</div>
      <AnimatePresence>
        {drawer && (
          <motion.div
            className="fixed inset-0 z-40 flex lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div className="absolute inset-0 bg-black/60" onClick={() => setDrawer(false)} />
            <motion.div
              className="relative z-10 h-full"
              initial={{ x: -260 }}
              animate={{ x: 0 }}
              exit={{ x: -260 }}
              transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            >
              {sidebar}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-line px-5 py-3 lg:hidden">
          <button className="text-dim" onClick={() => setDrawer((d) => !d)} aria-label="Menu">
            {drawer ? <X size={20} /> : <Menu size={20} />}
          </button>
          <span className="text-sm font-semibold">{product}</span>
        </header>
        <main className="min-w-0 flex-1 overflow-y-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={loc.pathname}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
              className="mx-auto max-w-6xl px-5 py-8 lg:px-10"
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}

export function PageHeader({
  title,
  sub,
  actions,
}: {
  title: string;
  sub?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight text-body">{title}</h1>
        {sub && <p className="mt-1 max-w-2xl text-sm text-dim">{sub}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
