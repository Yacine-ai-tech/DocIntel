import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { FileScan, Image, Layers, BarChart3, Cpu, History } from "lucide-react";
import { AppShell } from "./kit/AppShell";
import { WakingBackend } from "./kit/misc";
import { Skeleton } from "./kit/primitives";
import { api } from "./lib/api";
import Workspace from "./pages/Workspace";
import ImageIntel from "./pages/ImageIntel";
import Batch from "./pages/Batch";
import Models from "./pages/Models";
import Activity from "./pages/Activity";

const Benchmarks = lazy(() => import("./pages/Benchmarks"));

const NAV = [
  { to: "/", label: "Workspace", icon: FileScan },
  { to: "/images", label: "Image Intelligence", icon: Image },
  { to: "/batch", label: "Batch", icon: Layers },
  { to: "/benchmarks", label: "Benchmarks", icon: BarChart3 },
  { to: "/models", label: "Vision Models", icon: Cpu },
  { to: "/activity", label: "Activity", icon: History },
];

export default function App() {
  const [health, setHealth] = useState<"ok" | "down" | "checking">("checking");
  const [attempts, setAttempts] = useState(0);

  const check = useCallback(() => {
    setHealth("checking");
    api
      .health()
      .then(() => setHealth("ok"))
      .catch(() => setHealth("down"));
  }, []);

  useEffect(() => {
    check();
  }, [check, attempts]);

  // Free-tier cold start: retry automatically a few times before declaring failure.
  useEffect(() => {
    if (health === "down" && attempts < 6) {
      const t = setTimeout(() => setAttempts((a) => a + 1), 8000);
      return () => clearTimeout(t);
    }
  }, [health, attempts]);

  return (
    <BrowserRouter>
      <AppShell
        product="DocIntel"
        tagline="Vision Document Intelligence"
        nav={NAV}
        health={health}
      >
        {health !== "ok" && !(health === "checking" && attempts === 0) ? (
          <WakingBackend waking={attempts < 6} onRetry={() => setAttempts(0)} />
        ) : (
          <Suspense fallback={<Skeleton className="h-64 w-full" />}>
            <Routes>
              <Route path="/" element={<Workspace />} />
              <Route path="/images" element={<ImageIntel />} />
              <Route path="/batch" element={<Batch />} />
              <Route path="/benchmarks" element={<Benchmarks />} />
              <Route path="/models" element={<Models />} />
              <Route path="/activity" element={<Activity />} />
              <Route path="*" element={<Workspace />} />
            </Routes>
          </Suspense>
        )}
      </AppShell>
    </BrowserRouter>
  );
}
