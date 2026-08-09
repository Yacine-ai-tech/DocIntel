import { defineConfig } from "vite";
import { configDefaults } from "vitest/config";
import react from "@vitejs/plugin-react";

// Dev: `VITE_PROXY_TARGET=http://localhost:8000 npm run dev` proxies API calls to a
// running backend (local uvicorn or the live Render URL). Prod build is same-origin —
// FastAPI serves dist/ itself.
const target = process.env.VITE_PROXY_TARGET || "http://localhost:8000";
const apiPaths = [
  "/health", "/classify", "/classify-image", "/extract", "/process",
  "/extract-llm", "/extract-tables", "/batch", "/docs", "/openapi.json",
];

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(
      apiPaths.map((p) => [p, { target, changeOrigin: true, secure: false }]),
    ),
  },
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
      },
    },
  },
  test: {
    // e2e/ holds Playwright specs (npm run test:e2e) — vitest's default glob would
    // otherwise also try to collect them and fail on the missing @playwright/test runtime.
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
