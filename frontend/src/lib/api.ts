export class ApiError extends Error { constructor(public status: number, message: string) { super(message); this.name = 'ApiError'; } }

/** Typed client for the DocIntel API. Same-origin in production (FastAPI serves dist/);
 *  in dev the Vite proxy forwards to VITE_PROXY_TARGET. */

export type ProcessResponse = {
  doc_type?: string | null;
  route: string;
  confidence?: number | null;
  page_count?: number | null;
  processing_time_ms?: number | null;
  fields?: Record<string, unknown> | null;
  raw_text?: string | null;
  error?: string | null;
};

export type ClassifyImageResponse = {
  category?: string;
  confidence?: number;
  reasoning?: string;
  processing_time_ms?: number;
  error?: string;
};

export type BatchStatus = {
  id: string;
  status: string;
  total: number;
  processed: number;
  failed: number;
};

export type BatchResults = {
  job_id: string;
  results: { filename: string; fields: Record<string, unknown> | null; confidence: number | null; page_count: number | null }[];
};

const BASE = import.meta.env.VITE_API_BASE_URL || "";

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

async function req<T>(path: string, init?: RequestInit, retryCount = 0): Promise<T> {
  try {
    const res = await fetch(BASE + path, init);
    if (!res.ok) {
      if (res.status >= 500 && retryCount < 5) {
        await delay(2000 * (retryCount + 1));
        return req<T>(path, init, retryCount + 1);
      }
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail ?? JSON.stringify(body);
      } catch { /* keep statusText */ }
      throw new ApiError(res.status, detail);
    }
    return res.json() as Promise<T>;
  } catch (err: any) {
    if ((err instanceof TypeError || err.message === 'Failed to fetch') && retryCount < 5) {
      await delay(2000 * (retryCount + 1));
      return req<T>(path, init, retryCount + 1);
    }
    throw err;
  }
}

export const api = {
  health: () => req<{ status: string; service: string; version: string }>("/health"),

  process(file: File, route: string, docType: string) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("route", route);
    fd.append("doc_type", docType);
    return req<ProcessResponse>("/process", { method: "POST", body: fd });
  },

  classifyImage(file: File, categories: string[]) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("categories", categories.join(","));
    return req<ClassifyImageResponse>("/classify-image", { method: "POST", body: fd });
  },

  batchUpload(files: File[], route: string, docType: string) {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("route", route);
    fd.append("doc_type", docType);
    return req<{ job_id: string; total: number }>("/batch/upload", { method: "POST", body: fd });
  },

  batchStatus: (id: string) => req<BatchStatus>(`/batch/${id}`),
  batchResults: (id: string) => req<BatchResults>(`/batch/${id}/results`),
};

/* ---------- session-local activity log (real events only) ---------- */
export type ActivityEvent = {
  ts: number;
  kind: "process" | "classify-image" | "batch";
  title: string;
  meta: Record<string, unknown>;
};

const ACT_KEY = "docintel.activity";

export function logActivity(ev: Omit<ActivityEvent, "ts">) {
  const list: ActivityEvent[] = JSON.parse(localStorage.getItem(ACT_KEY) ?? "[]");
  list.unshift({ ...ev, ts: Date.now() });
  localStorage.setItem(ACT_KEY, JSON.stringify(list.slice(0, 100)));
}

export function readActivity(): ActivityEvent[] {
  return JSON.parse(localStorage.getItem(ACT_KEY) ?? "[]");
}

/* ---------- export helpers ---------- */
export function downloadBlob(name: string, mime: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function fieldsToCSV(fields: Record<string, unknown>): string {
  const rows = Object.entries(fields).filter(([k]) => !k.startsWith("_"));
  const esc = (s: string) => `"${s.replace(/"/g, '""')}"`;
  return ["field,value", ...rows.map(([k, v]) => `${esc(k)},${esc(typeof v === "object" ? JSON.stringify(v) : String(v ?? ""))}`)].join("\n");
}

/* ---------- client preferences (Settings page) ---------- */
export type Prefs = { route: string; docType: string; view: "cards" | "json" };
const PREFS_KEY = "docintel.prefs";
export function readPrefs(): Prefs {
  try { return { route: "vision_premium", docType: "auto", view: "cards", ...JSON.parse(localStorage.getItem(PREFS_KEY) ?? "{}") }; }
  catch { return { route: "vision_premium", docType: "auto", view: "cards" }; }
}
export function savePrefs(p: Partial<Prefs>) {
  localStorage.setItem(PREFS_KEY, JSON.stringify({ ...readPrefs(), ...p }));
}

/* ---------- session document library (Documents page) ---------- */
export type StoredDoc = {
  ts: number;
  name: string;
  size: number;
  result: ProcessResponse;
};
const DOCS_KEY = "docintel.documents";
export function saveDocument(d: StoredDoc) {
  const list: StoredDoc[] = JSON.parse(localStorage.getItem(DOCS_KEY) ?? "[]");
  list.unshift(d);
  try { localStorage.setItem(DOCS_KEY, JSON.stringify(list.slice(0, 20))); }
  catch { localStorage.setItem(DOCS_KEY, JSON.stringify(list.slice(0, 5))); }
}
export function readDocuments(): StoredDoc[] {
  try { return JSON.parse(localStorage.getItem(DOCS_KEY) ?? "[]"); } catch { return []; }
}
export function clearDocuments() { localStorage.removeItem(DOCS_KEY); }
