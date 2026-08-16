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

export type CameraPairResponse = {
  token: string;
  qr_available: boolean;
  qr_code: string | null;
  expires_in_hours: number;
  frontend_url: string;
};

export type CameraUploadResult = {
  fields: Record<string, unknown> | null;
  confidence: number | null;
  page_count: number | null;
  processing_time_ms: number;
};

export type CameraStatusResponse = {
  active: boolean;
  uploads: number;
  last_upload: string | null;
  last_result: CameraUploadResult | null;
};

export type CameraUploadResponse = CameraUploadResult;

const BASE = import.meta.env.VITE_API_BASE_URL || "";

// Sent as X-OmniIntel-Internal-Token on every request when set. The backend's
// REQUIRE_INTERNAL_TOKEN production-hardening flag (see UserGuidePage) has no
// effect on this app unless this is configured at build time — previously
// there was no way for this shipped frontend to send that token at all, so
// following the backend's own documented hardening step broke the app's own
// UI outright. Optional: leave unset for the common case where the frontend
// and backend are same-origin/trusted-network and REQUIRE_INTERNAL_TOKEN
// stays off.
const INTERNAL_TOKEN = import.meta.env.VITE_OMNIINTEL_INTERNAL_TOKEN || "";

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Only GET (the default fetch method, and the only one used read-only by this
// client) is safe to auto-retry. A POST that already reached the server can
// have done real, costly work (a paid vision/LLM call, a new batch job) before
// a 5xx or dropped connection on the *response* — retrying blindly risked
// silently doubling that cost/work. Mutating calls now fail visibly instead;
// the caller decides whether to retry.
function isIdempotent(init?: RequestInit): boolean {
  const method = (init?.method || "GET").toUpperCase();
  return method === "GET" || method === "HEAD";
}

async function req<T>(path: string, init?: RequestInit, retryCount = 0): Promise<T> {
  const headers = new Headers(init?.headers);
  if (INTERNAL_TOKEN) headers.set("X-OmniIntel-Internal-Token", INTERNAL_TOKEN);
  const finalInit: RequestInit = { ...init, headers };
  try {
    const res = await fetch(BASE + path, finalInit);
    if (!res.ok) {
      if (res.status >= 500 && isIdempotent(init) && retryCount < 5) {
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
    if ((err instanceof TypeError || err.message === 'Failed to fetch') && isIdempotent(init) && retryCount < 5) {
      await delay(2000 * (retryCount + 1));
      return req<T>(path, init, retryCount + 1);
    }
    throw err;
  }
}

export type BenchmarksResponse = {
  summary: {
    corpus?: { total_documents: number; ground_truth_documents: number; sources: { name: string; type: string; docs: number; ground_truth: string | null }[] };
    robustness?: { documents_processed: number; documents_total: number; success_rate_pct: number; unhandled_errors: number };
    route_comparison?: { set: string; vision_route_a: number; vision_route_b: number; ocr_fallback: number }[];
    stat_tiles?: { route_a_invoices: { correct: number; total: number; pct: number }; sroie_zero_shot_pct: number; fcfa: { correct: number; total: number; pct: number } };
    sroie?: { n: number; company_pct: number; date_pct: number; total_pct: number; overall_pct: number };
  };
  markdown: string | null;
};

export const api = {
  health: () => req<{ status: string; service: string; version: string }>("/health"),

  benchmarks: () => req<BenchmarksResponse>("/benchmarks"),

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

  pairCamera(user = "demo_user", device = "Mobile") {
    const fd = new FormData();
    fd.append("user", user);
    fd.append("device", device);
    return req<CameraPairResponse>("/camera/pair", { method: "POST", body: fd });
  },

  cameraStatus: (token: string) => req<CameraStatusResponse>(`/camera/status/${token}`),

  uploadCameraPhoto(token: string, file: File, docType = "default") {
    const fd = new FormData();
    fd.append("token", token);
    fd.append("file", file);
    fd.append("doc_type", docType);
    return req<CameraUploadResponse>("/camera/upload", { method: "POST", body: fd });
  },
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
