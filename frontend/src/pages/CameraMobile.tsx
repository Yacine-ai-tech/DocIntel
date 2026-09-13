import { useEffect, useRef, useState, useCallback } from "react";
import {
  Camera,
  CheckCircle2,
  RefreshCw,
  AlertTriangle,
  ShieldAlert,
  SwitchCamera,
  Zap,
  ZapOff,
  Image as ImageIcon,
  RotateCcw,
  Sparkles,
  ArrowRight,
  FileText,
  DollarSign,
  Calendar,
  Building2,
} from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { api, ApiError, type CameraUploadResult } from "../lib/api";

const DOC_TYPES = [
  { id: "default", label: "Auto Detect" },
  { id: "invoice", label: "Invoice" },
  { id: "receipt", label: "Receipt" },
  { id: "contract", label: "Contract" },
  { id: "financial_report", label: "Financial Report" },
  { id: "form", label: "Form" },
];

export default function CameraMobile() {
  const [params] = useSearchParams();
  const token = params.get("token");

  const [status, setStatus] = useState<"idle" | "uploading" | "success" | "error" | "insecure">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [docType, setDocType] = useState("default");
  const [facingMode, setFacingMode] = useState<"environment" | "user">("environment");
  const [torchOn, setTorchOn] = useState(false);
  const [hasTorch, setHasTorch] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const [result, setResult] = useState<CameraUploadResult | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setCameraActive(false);
  }, []);

  const startCamera = useCallback(async () => {
    stopStream();
    if (typeof window === "undefined" || !navigator?.mediaDevices?.getUserMedia) {
      setCameraActive(false);
      return;
    }

    try {
      const constraints: MediaStreamConstraints = {
        video: {
          facingMode: { ideal: facingMode },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.setAttribute("playsinline", "true");
        videoRef.current.setAttribute("webkit-playsinline", "true");
        videoRef.current.muted = true;
        try {
          await videoRef.current.play();
        } catch (playErr) {
          console.warn("video.play() auto-play prevented, awaiting gesture:", playErr);
        }
      }
      setCameraActive(true);

      const track = stream.getVideoTracks()[0];
      const capabilities = (track as any)?.getCapabilities?.();
      setHasTorch(!!capabilities?.torch);
    } catch (err: any) {
      console.warn("Live camera stream unavailable, falling back to file capture UI:", err);
      setCameraActive(false);
    }
  }, [facingMode, stopStream]);

  useEffect(() => {
    if (typeof window !== "undefined" && !window.isSecureContext) {
      setStatus("insecure");
      return;
    }
    if (!token) {
      setStatus("error");
      setErrorMsg("Invalid or missing pairing token. Please scan the QR code from the DocIntel desktop dashboard.");
      return;
    }

    if (status === "idle" && !previewUrl && hasStarted) {
      startCamera();
    }

    return () => {
      stopStream();
    };
  }, [token, status, previewUrl, hasStarted, startCamera, stopStream]);

  const toggleTorch = async () => {
    if (!streamRef.current) return;
    const track = streamRef.current.getVideoTracks()[0];
    if (track && (track as any).applyConstraints) {
      try {
        const nextState = !torchOn;
        await (track as any).applyConstraints({
          advanced: [{ torch: nextState }],
        });
        setTorchOn(nextState);
      } catch (e) {
        console.warn("Failed to toggle torch:", e);
      }
    }
  };

  const switchCameraFacing = () => {
    setFacingMode((prev) => (prev === "environment" ? "user" : "environment"));
  };

  const capturePhotoFromVideo = () => {
    if (!videoRef.current) return;
    const video = videoRef.current;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      (blob) => {
        if (blob) {
          if (typeof navigator.vibrate === "function") {
            try { navigator.vibrate(50); } catch { /* ignore */ }
          }
          const url = URL.createObjectURL(blob);
          setCapturedBlob(blob);
          setPreviewUrl(url);
          stopStream();
        }
      },
      "image/png",
      0.95
    );
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    setCapturedBlob(file);
    setPreviewUrl(url);
    stopStream();
  };

  const retakePhoto = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setCapturedBlob(null);
    setStatus("idle");
    setErrorMsg("");
    startCamera();
  };

  const submitUpload = async () => {
    if (!capturedBlob || !token) return;

    setStatus("uploading");
    setErrorMsg("");
    try {
      const res = await api.uploadCameraPhoto(token, capturedBlob, docType, "vision_route_b");
      setResult(res);
      setStatus("success");
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 403) {
        setErrorMsg("This pairing session expired or was reset. Please scan a fresh QR code from your desktop.");
      } else {
        setErrorMsg(err.message || "Extraction failed. Check network connection and retry.");
      }
      setStatus("error");
    }
  };

  const scanAnother = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setCapturedBlob(null);
    setResult(null);
    setStatus("idle");
    setErrorMsg("");
    startCamera();
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-white flex flex-col font-sans select-none antialiased">
      {/* Top Header */}
      <header className="px-4 py-3 bg-zinc-900/80 backdrop-blur border-b border-zinc-800 flex items-center justify-between sticky top-0 z-30">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
            <Camera size={18} />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-zinc-100 leading-tight">DocIntel Scanner</h1>
            <p className="text-[11px] text-zinc-400">
              {token ? `Session: ${token.slice(0, 8)}…` : "Not Paired"}
            </p>
          </div>
        </div>

        {/* Doc Type Selector */}
        <select
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
          disabled={status === "uploading"}
          className="bg-zinc-800 border border-zinc-700 text-xs text-zinc-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-emerald-500"
        >
          {DOC_TYPES.map((dt) => (
            <option key={dt.id} value={dt.id}>
              {dt.label}
            </option>
          ))}
        </select>
      </header>

      {/* Main View Area */}
      <main className="flex-1 flex flex-col items-center justify-center relative overflow-hidden p-4">
        {/* Insecure Context Warning */}
        {status === "insecure" && (
          <div className="max-w-md w-full p-6 text-center space-y-4 bg-zinc-900 border border-amber-500/30 rounded-2xl text-amber-400 shadow-2xl">
            <ShieldAlert size={56} className="mx-auto" />
            <h2 className="text-lg font-bold text-zinc-100">HTTPS Connection Required</h2>
            <p className="text-sm text-zinc-400 leading-relaxed">
              Mobile browsers restrict camera hardware access outside secure HTTPS connections.
              Please connect via HTTPS or use the file upload selector below.
            </p>
            <label
              htmlFor="fallback-file-input"
              className="inline-flex items-center justify-center gap-2 w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-xl cursor-pointer transition shadow-lg shadow-emerald-900/30"
            >
              <ImageIcon size={18} />
              <span>Select Document Photo</span>
            </label>
            <input
              id="fallback-file-input"
              type="file"
              accept="image/*"
              capture="environment"
              onChange={handleFileInput}
              className="hidden"
            />
          </div>
        )}

        {/* Live Camera Viewfinder or Fallback Mode */}
        {status === "idle" && !previewUrl && (
          <div className="w-full max-w-md flex-1 flex flex-col items-center justify-between gap-4 py-2">
            {/* Camera Viewport Container */}
            <div className="w-full relative aspect-[3/4] max-h-[65vh] bg-black rounded-3xl overflow-hidden border-2 border-zinc-800 shadow-2xl flex items-center justify-center">
              {cameraActive ? (
                <>
                  <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                    className="w-full h-full object-cover"
                  />
                  {/* Document Framing Overlay */}
                  <div className="absolute inset-6 border border-white/20 rounded-2xl pointer-events-none flex flex-col justify-between p-3">
                    {/* Corner Guides */}
                    <div className="flex justify-between">
                      <div className="w-6 h-6 border-t-2 border-l-2 border-emerald-400 rounded-tl-lg" />
                      <div className="w-6 h-6 border-t-2 border-r-2 border-emerald-400 rounded-tr-lg" />
                    </div>
                    {/* Scanning Sweep Effect */}
                    <div className="w-full h-0.5 bg-gradient-to-r from-transparent via-emerald-400 to-transparent animate-pulse opacity-80" />
                    <div className="flex justify-between">
                      <div className="w-6 h-6 border-b-2 border-l-2 border-emerald-400 rounded-bl-lg" />
                      <div className="w-6 h-6 border-b-2 border-r-2 border-emerald-400 rounded-br-lg" />
                    </div>
                  </div>

                  {/* Top Camera Controls Overlay */}
                  <div className="absolute top-3 right-3 flex gap-2">
                    {hasTorch && (
                      <button
                        onClick={toggleTorch}
                        className={`p-2.5 rounded-full backdrop-blur transition ${
                          torchOn
                            ? "bg-amber-400 text-zinc-950 font-bold"
                            : "bg-black/40 text-white border border-white/20"
                        }`}
                        title="Toggle Flashlight"
                      >
                        {torchOn ? <Zap size={18} /> : <ZapOff size={18} />}
                      </button>
                    )}
                    <button
                      onClick={switchCameraFacing}
                      className="p-2.5 rounded-full bg-black/40 text-white border border-white/20 backdrop-blur transition active:scale-90"
                      title="Switch Camera"
                    >
                      <SwitchCamera size={18} />
                    </button>
                  </div>

                  {/* Instruction tag */}
                  <div className="absolute bottom-4 inset-x-0 flex justify-center">
                    <span className="px-3.5 py-1.5 rounded-full bg-black/60 backdrop-blur text-zinc-200 text-xs font-medium border border-white/10 shadow">
                      Align document inside frame
                    </span>
                  </div>
                </>
              ) : (
                /* Pre-start or fallback when live video stream is not active */
                <div className="p-8 text-center space-y-4">
                  <div className="w-20 h-20 mx-auto rounded-full bg-zinc-900 border border-zinc-700 flex items-center justify-center text-emerald-400 shadow-inner">
                    <Camera size={40} />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-zinc-200">Document Camera</h3>
                    <p className="text-xs text-zinc-400 max-w-xs mx-auto mt-1">
                      Tap below to launch live camera scanning or upload directly
                    </p>
                  </div>
                  <div className="flex flex-col gap-2 w-full max-w-xs mx-auto">
                    <button
                      type="button"
                      onClick={async () => {
                        setHasStarted(true);
                        await startCamera();
                      }}
                      className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-semibold rounded-xl cursor-pointer transition shadow-lg shadow-emerald-950 active:scale-95"
                    >
                      <Camera size={20} />
                      <span>Start Live Camera</span>
                    </button>
                    <label
                      htmlFor="native-camera-input"
                      className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded-xl cursor-pointer transition border border-zinc-700"
                    >
                      <span>Take Photo or Upload Image</span>
                    </label>
                  </div>
                  <input
                    id="native-camera-input"
                    type="file"
                    accept="image/*"
                    capture="environment"
                    onChange={handleFileInput}
                    className="hidden"
                  />
                </div>
              )}
            </div>

            {/* Bottom Controls Bar */}
            <div className="w-full flex items-center justify-around px-4 pt-1">
              {/* Gallery/File Button */}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="p-3.5 rounded-full bg-zinc-900 border border-zinc-750 text-zinc-300 hover:text-white hover:bg-zinc-800 transition active:scale-95 shadow-md flex flex-col items-center gap-1"
                title="Choose from Gallery"
              >
                <ImageIcon size={20} />
                <span className="text-[10px] font-medium text-zinc-400">Gallery</span>
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileInput}
                className="hidden"
              />

              {/* Primary Shutter Button (Active when camera is live) */}
              {cameraActive ? (
                <button
                  type="button"
                  onClick={capturePhotoFromVideo}
                  className="w-20 h-20 rounded-full bg-gradient-to-tr from-emerald-500 to-teal-400 p-1.5 shadow-[0_0_30px_rgba(16,185,129,0.4)] active:scale-90 transition transform"
                  title="Capture Photo"
                >
                  <div className="w-full h-full rounded-full border-2 border-white flex items-center justify-center bg-transparent">
                    <div className="w-14 h-14 rounded-full bg-white transition hover:scale-95" />
                  </div>
                </button>
              ) : (
                <label
                  htmlFor="primary-capture-input"
                  className="w-20 h-20 rounded-full bg-emerald-500 flex items-center justify-center text-white cursor-pointer shadow-[0_0_30px_rgba(16,185,129,0.4)] active:scale-95 transition"
                >
                  <Camera size={32} />
                </label>
              )}
              <input
                id="primary-capture-input"
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleFileInput}
                className="hidden"
              />

              {/* Camera Restart / Flip */}
              <button
                type="button"
                onClick={startCamera}
                className="p-3.5 rounded-full bg-zinc-900 border border-zinc-750 text-zinc-300 hover:text-white hover:bg-zinc-800 transition active:scale-95 shadow-md flex flex-col items-center gap-1"
                title="Restart Live Camera"
              >
                <RotateCcw size={20} />
                <span className="text-[10px] font-medium text-zinc-400">Reset</span>
              </button>
            </div>
          </div>
        )}

        {/* Captured Photo Preview Screen */}
        {status === "idle" && previewUrl && (
          <div className="w-full max-w-md flex-1 flex flex-col items-center justify-between gap-4 py-2 animate-in fade-in zoom-in-95 duration-200">
            <div className="w-full relative aspect-[3/4] max-h-[65vh] bg-black rounded-3xl overflow-hidden border-2 border-zinc-800 shadow-2xl flex items-center justify-center">
              <img
                src={previewUrl}
                alt="Captured Document"
                className="w-full h-full object-contain bg-zinc-950"
              />
              <div className="absolute top-3 left-3 px-3 py-1 rounded-full bg-black/60 backdrop-blur text-emerald-400 text-xs font-medium border border-emerald-500/30 flex items-center gap-1.5">
                <Sparkles size={14} />
                <span>Ready for Vision AI</span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="w-full space-y-3 pt-2">
              <button
                type="button"
                onClick={submitUpload}
                className="w-full py-4 bg-emerald-500 hover:bg-emerald-600 active:scale-[0.98] text-white font-bold rounded-2xl transition shadow-[0_0_30px_rgba(16,185,129,0.3)] flex items-center justify-center gap-2 text-base"
              >
                <span>Extract Document</span>
                <ArrowRight size={20} />
              </button>

              <button
                type="button"
                onClick={retakePhoto}
                className="w-full py-3 bg-zinc-900 hover:bg-zinc-800 border border-zinc-750 text-zinc-300 font-medium rounded-2xl transition flex items-center justify-center gap-2 text-sm"
              >
                <RotateCcw size={16} />
                <span>Retake Photo</span>
              </button>
            </div>
          </div>
        )}

        {/* Uploading / Processing State */}
        {status === "uploading" && (
          <div className="max-w-md w-full p-8 text-center space-y-6 bg-zinc-900/90 backdrop-blur border border-zinc-800 rounded-3xl shadow-2xl animate-in fade-in duration-300">
            <div className="relative w-24 h-24 mx-auto flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border-4 border-emerald-500/20 animate-ping" />
              <div className="w-20 h-20 rounded-full bg-emerald-500/10 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
                <RefreshCw size={36} className="animate-spin text-emerald-400" />
              </div>
            </div>
            <div>
              <h2 className="text-xl font-bold text-zinc-100">Extracting Fields…</h2>
              <p className="text-sm text-zinc-400 mt-1">
                Processing document through Vision AI model
              </p>
            </div>
            <div className="p-3.5 bg-zinc-950/60 rounded-xl border border-zinc-800 text-xs text-zinc-400">
              ⚡ Results will automatically stream to your connected desktop dashboard.
            </div>
          </div>
        )}

        {/* Success State with Extracted Fields */}
        {status === "success" && result && (
          <div className="max-w-md w-full p-6 text-center space-y-5 bg-zinc-900 border border-emerald-500/30 rounded-3xl shadow-2xl animate-in fade-in duration-300">
            <div className="w-16 h-16 mx-auto rounded-full bg-emerald-500/10 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
              <CheckCircle2 size={36} />
            </div>

            <div>
              <h2 className="text-xl font-bold text-zinc-100">Extraction Complete!</h2>
              <p className="text-xs text-zinc-400 mt-1">
                Transmitted to your desktop dashboard in real time
              </p>
            </div>

            {/* Quick Summary Badges */}
            <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-4 text-left space-y-2.5">
              {Boolean(result.fields?.vendor) && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400 flex items-center gap-1.5">
                    <Building2 size={14} className="text-emerald-400" /> Vendor
                  </span>
                  <span className="font-semibold text-zinc-200">{String(result.fields?.vendor)}</span>
                </div>
              )}
              {result.fields?.total != null && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400 flex items-center gap-1.5">
                    <DollarSign size={14} className="text-emerald-400" /> Total
                  </span>
                  <span className="font-bold text-emerald-400">
                    {result.fields.currency ? `${result.fields.currency} ` : "$"}
                    {Number(result.fields.total).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
              )}
              {Boolean(result.fields?.date) && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400 flex items-center gap-1.5">
                    <Calendar size={14} className="text-emerald-400" /> Date
                  </span>
                  <span className="text-zinc-300">{String(result.fields?.date)}</span>
                </div>
              )}
              {Boolean(result.fields?.invoice_number) && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400 flex items-center gap-1.5">
                    <FileText size={14} className="text-emerald-400" /> Invoice #
                  </span>
                  <span className="font-mono text-zinc-300">{String(result.fields?.invoice_number)}</span>
                </div>
              )}
              <div className="pt-2 border-t border-zinc-850 flex items-center justify-between text-[11px] text-zinc-500">
                <span>Confidence: {result.confidence != null ? `${Math.round(result.confidence * 100)}%` : "N/A"}</span>
                <span>Time: {result.processing_time_ms ? `${result.processing_time_ms}ms` : "Fast"}</span>
              </div>
            </div>

            <button
              type="button"
              onClick={scanAnother}
              className="w-full py-3.5 bg-emerald-500 hover:bg-emerald-600 active:scale-[0.98] text-white font-bold rounded-2xl transition shadow-lg shadow-emerald-950 flex items-center justify-center gap-2 text-sm"
            >
              <RotateCcw size={18} />
              <span>Scan Next Document</span>
            </button>
          </div>
        )}

        {/* Error State */}
        {status === "error" && (
          <div className="max-w-md w-full p-6 text-center space-y-4 bg-zinc-900 border border-red-500/30 rounded-3xl text-red-400 shadow-2xl animate-in fade-in duration-200">
            <AlertTriangle size={52} className="mx-auto" />
            <h2 className="text-lg font-bold text-zinc-100">Unable to Process</h2>
            <p className="text-sm text-zinc-400 leading-relaxed px-2">
              {errorMsg || "An unexpected error occurred during document extraction."}
            </p>
            <div className="pt-2 flex flex-col gap-2.5">
              <button
                type="button"
                onClick={retakePhoto}
                className="w-full py-3 bg-zinc-800 hover:bg-zinc-700 text-white font-medium rounded-xl transition text-sm"
              >
                Try Again
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
