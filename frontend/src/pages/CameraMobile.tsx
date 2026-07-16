import { useEffect, useState } from "react";
import { Camera, CheckCircle2, RefreshCw, AlertTriangle } from "lucide-react";
import { useSearchParams } from "react-router-dom";

export default function CameraMobile() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [status, setStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setErrorMsg("Invalid or missing token. Please scan the QR code from the DocIntel dashboard.");
    }
  }, [token]);

  const handleCapture = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !token) return;

    setStatus("uploading");
    try {
      const form = new FormData();
      form.append("token", token);
      form.append("file", file);
      form.append("doc_type", "default");

      // Mobile app should use absolute backend URL or relative if hosted together
      const res = await fetch("/api/v1/camera/upload", {
        method: "POST",
        body: form,
      });
      
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(err.detail || "Upload failed");
      }
      
      setStatus("success");
    } catch (err: any) {
      setErrorMsg(err.message);
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
          </p>
        </div>

        {status === "idle" && (
          <div className="relative pt-8">
            <label 
              htmlFor="camera-input"
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
