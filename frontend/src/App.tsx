import UserGuidePage from './pages/UserGuidePage';
import BenchmarkPage from './pages/BenchmarkPage';
import ApiDocsPage from './pages/ApiDocsPage';
import { Component, ReactNode, lazy, Suspense, useCallback, useEffect, useState } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { Camera, FileScan, Image, Layers, BarChart3, Cpu, History, Workflow, GitCompareArrows, FolderOpen, Settings2, Code2, BookOpen } from "lucide-react";
import { AppShell } from "./kit/AppShell";
import { WakingBackend } from "./kit/misc";
import { Skeleton } from "./kit/primitives";
import { api } from "./lib/api";
import Workspace from "./pages/Workspace";
import ImageIntel from "./pages/ImageIntel";
import Batch from "./pages/Batch";
import Models from "./pages/Models";
import Activity from "./pages/Activity";
import Pipelines from "./pages/Pipelines";
import Compare from "./pages/Compare";
import Documents from "./pages/Documents";
import Settings from "./pages/Settings";
import CameraDashboard from "./pages/CameraDashboard";
import CameraMobile from "./pages/CameraMobile";

const Benchmarks = lazy(() => import("./pages/Benchmarks"));

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  resetKey?: string;
}

class ErrorBoundary extends Component<{ children: ReactNode; resetKey?: string }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null, resetKey: this.props.resetKey };

  static getDerivedStateFromProps(props: { resetKey?: string }, state: ErrorBoundaryState) {
    if (props.resetKey !== state.resetKey) {
      return { hasError: false, error: null, resetKey: props.resetKey };
    }
    return null;
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error("DocIntel UI Error caught by boundary:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-center text-red-400 bg-red-950/30 rounded-xl border border-red-800/50 m-4">
          <h2 className="text-xl font-bold mb-2">Component Error</h2>
          <p className="text-sm opacity-80 mb-4">{this.state.error?.message || "An unexpected error occurred."}</p>
          <div className="flex gap-2 justify-center">
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg text-sm transition"
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function RouteErrorBoundary({ children }: { children: ReactNode }) {
  const location = useLocation();
  return <ErrorBoundary resetKey={location.pathname}>{children}</ErrorBoundary>;
}

const NAV = [
  { to: "/", label: "Workspace", icon: FileScan },
  { to: "/documents", label: "Documents", icon: FolderOpen },
  { to: "/images", label: "Image Intelligence", icon: Image },
  { to: "/camera", label: "Mobile Scanner", icon: Camera },
  { to: "/pipelines", label: "Pipelines", icon: Workflow },
  { to: "/compare", label: "Compare Routes", icon: GitCompareArrows },
  { to: "/batch", label: "Batch", icon: Layers },
  { to: "/benchmarks", label: "Benchmarks", icon: BarChart3 },
  { to: "/models", label: "Vision Models", icon: Cpu },
  { to: "/activity", label: "Activity", icon: History },
  { to: "/settings", label: "Settings", icon: Settings2 },
  { to: "/api-docs", label: "API Docs", icon: Code2 },
  { to: "/user-guide", label: "User Guide", icon: BookOpen }
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

  useEffect(() => {
    if (health === "down" && attempts < 6) {
      const t = setTimeout(() => setAttempts((a) => a + 1), 8000);
      return () => clearTimeout(t);
    }
  }, [health, attempts]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/camera/mobile" element={<CameraMobile />} />
        <Route path="*" element={
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
                <RouteErrorBoundary>
                  <Routes>
                    <Route path="/" element={<Workspace />} />
                    <Route path="/documents" element={<Documents />} />
                    <Route path="/images" element={<ImageIntel />} />
                    <Route path="/camera" element={<CameraDashboard />} />
                    <Route path="/pipelines" element={<Pipelines />} />
                    <Route path="/compare" element={<Compare />} />
                    <Route path="/batch" element={<Batch />} />
                    <Route path="/benchmarks" element={<Benchmarks />} />
                    <Route path="/models" element={<Models />} />
                    <Route path="/activity" element={<Activity />} />
                    <Route path="/settings" element={<Settings />} />
                    <Route path="/api-docs" element={<ApiDocsPage />} />
                    <Route path="/benchmark" element={<BenchmarkPage />} />
                    <Route path="/user-guide" element={<UserGuidePage />} />
                    <Route path="*" element={<Workspace />} />
                  </Routes>
                </RouteErrorBoundary>
              </Suspense>
            )}
          </AppShell>
        } />
      </Routes>
    </BrowserRouter>
  );
}
