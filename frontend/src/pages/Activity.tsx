import { useState } from "react";
import { FileScan, Image, Layers, History, Trash2 } from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Button, Card, Chip, EmptyState } from "../kit/primitives";
import { readActivity, ActivityEvent } from "../lib/api";

const ICONS = { process: FileScan, "classify-image": Image, batch: Layers } as const;

export default function Activity() {
  const [events, setEvents] = useState<ActivityEvent[]>(readActivity());

  return (
    <div>
      <PageHeader
        title="Activity"
        sub="Documents processed in this browser session (stored locally — the API itself is stateless)."
        actions={
          events.length > 0 && (
            <Button variant="ghost" onClick={() => { localStorage.removeItem("docintel.activity"); setEvents([]); }}>
              <Trash2 size={14} /> Clear
            </Button>
          )
        }
      />
      <Card>
        {events.length === 0 ? (
          <EmptyState
            icon={History}
            title="Nothing processed yet"
            hint="Run a document through the Workspace and it will appear here."
          />
        ) : (
          <div className="divide-y divide-[var(--border)]">
            {events.map((e, i) => {
              const Icon = ICONS[e.kind] ?? History;
              return (
                <div key={i} className="flex items-center gap-3 py-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-line text-dim">
                    <Icon size={14} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-body">{e.title}</div>
                    <div className="text-xs text-muted">{new Date(e.ts).toLocaleString()}</div>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {Object.entries(e.meta)
                      .filter(([, v]) => v != null)
                      .slice(0, 4)
                      .map(([k, v]) => (
                        <Chip key={k} title={k}>
                          {k}: {typeof v === "number" ? (k === "confidence" ? v.toFixed(2) : v) : String(v)}
                        </Chip>
                      ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
