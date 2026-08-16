import { useEffect, useState } from "react";
import { Camera, CheckCircle2, RefreshCw, AlertTriangle, ShieldAlert } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { api, ApiError } from "../lib/api";

export default function CameraMobile() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [status, setStatus] = useState<"idle" | "uploading" | "success" | "error" | "insecure">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    // Most mobile browsers refuse camera capture (even via <input capture>) outside a
    // secure context — plain http:// on a LAN IP will silently fail with no camera UI
    // at all if we don't check this up front. See SELF_HOSTING.md.
    if (typeof window !== "undefined" && !window.isSecureContext) {
      setStatus("insecure");
      return;
    }
    if (!token) {
      setStatus("error");
      setErrorMsg("Invalid or missing token. Please scan the QR code from the DocIntel dashboard.");
    }
  }, [token]);

  const handleCapture = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    // No file means the user canceled the camera/picker, or the OS denied camera
    // permission before a file could be produced — either way, just return to idle
    // rather than showing a scary error for what's often a deliberate cancel.
    if (!file || !token) return;

    setStatus("uploading");
    try {
      await api.uploadCameraPhoto(token, file);
      setStatus("success");
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 403) {
        setErrorMsg("This pairing session expired or was reset. Go back to the DocIntel dashboard and generate a new QR code.");
      } else {
        setErrorMsg(err.message || "Upload failed");
      }
      setStatus("error");
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-white flex flex-col items-center justify-center p-6 font-sans">
      <div className="max-w-md w-full space-y-8 text-center">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100 mb-2">DocIntel Scanner</h1>
          <p className="text-zinc-400">
            {status === "idle" && "Ready to scan document"}
            {status === "uploading" && "Processing via Vision AI..."}
            {status === "success" && "Successfully uploaded!"}
            {status === "error" && "Error occurred"}
            {status === "insecure" && "Camera unavailable"}
          </p>
        </div>

        {status === "insecure" && (
          <div className="flex flex-col items-center py-12 text-amber-400">
            <ShieldAlert size={64} className="mb-6" />
            <p className="text-lg mb-2 px-4 font-medium">This page isn't loaded over HTTPS</p>
            <p className="text-zinc-400 px-4">
              Mobile browsers only allow camera access on a secure (HTTPS) connection.
              Ask whoever set up this DocIntel instance to put it behind HTTPS
              (a reverse proxy with TLS, or a tunnel) — plain <code className="text-zinc-300">http://</code> on
              a local network can't open your camera.
            </p>
          </div>
        )}

        {status === "idle" && (
          <div className="relative pt-8">
            {/* A <label htmlFor> triggers its input on mouse click natively, but labels
                aren't in the default tab order and Enter/Space on a focused one doesn't
                activate the input — same keyboard-inaccessibility gap as Workspace.tsx's
                dropzone. tabIndex + onKeyDown close it. */}
            <label
              htmlFor="camera-input"
              tabIndex={0}
              role="button"
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  document.getElementById("camera-input")?.click();
                }
              }}
              className="flex flex-col items-center justify-center w-full aspect-square rounded-full bg-emerald-500 hover:bg-emerald-600 transition-colors cursor-pointer shadow-[0_0_40px_rgba(16,185,129,0.3)] active:scale-95"
            >
              <Camera size={64} className="text-white mb-2" />
              <span className="text-lg font-bold">Take Photo</span>
            </label>
            <input 
              id="camera-input"
              type="file" 
              accept="image/*" 
              capture="environment" 
              onChange={handleCapture}
              className="hidden"
            />
          </div>
        )}

        {status === "uploading" && (
          <div className="flex flex-col items-center py-12 text-emerald-500">
            <RefreshCw size={64} className="animate-spin mb-6" />
            <p className="text-lg animate-pulse">Running Vision Extraction...</p>
          </div>
        )}

        {status === "success" && (
          <div className="flex flex-col items-center py-12 text-emerald-400">
            <CheckCircle2 size={80} className="mb-6" />
            <h2 className="text-xl font-bold mb-8">Upload Complete!</h2>
            <p className="text-zinc-400 mb-8">Check your desktop dashboard for results.</p>
            <button 
              onClick={() => setStatus("idle")}
              className="px-6 py-3 border border-zinc-700 rounded-lg text-white font-medium hover:bg-zinc-800 transition-colors"
            >
              Scan Another Document
            </button>
          </div>
        )}

        {status === "error" && (
          <div className="flex flex-col items-center py-12 text-red-400">
            <AlertTriangle size={64} className="mb-6" />
            <p className="text-lg mb-8 px-4">{errorMsg}</p>
            {token && (
              <button 
                onClick={() => { setStatus("idle"); setErrorMsg(""); }}
                className="px-6 py-3 bg-zinc-800 rounded-lg text-white font-medium"
              >
                Try Again
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
