import { useEffect, useRef, useState } from "react";
import {
  Camera, Smartphone, RefreshCw, CheckCircle2, X, ZoomIn, Scan, FileText,
} from "lucide-react";
import { Button, Card, Chip, ConfidenceBadge } from "../kit/primitives";
import { api, type CameraUploadResult, demoSessionId } from "../lib/api";

const POLL_INTERVAL_MS = 3000;

type ScanHistoryItem = {
  id: string;
  timestamp: Date;
  result: CameraUploadResult;
  previewImage?: string | null;
};

export default function CameraDashboard() {
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<CameraUploadResult | null>(null);
  const [scanStatus, setScanStatus] = useState<"waiting" | "processing" | "completed" | "error">("waiting");
  const [statusError, setStatusError] = useState<string | null>(null);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null);
  const [scanHistory, setScanHistory] = useState<ScanHistoryItem[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => stopPolling, []); // clear on unmount

  const handlePair = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    setPreviewImage(null);
    setScanStatus("waiting");
    setStatusError(null);
    try {
      // Pass session id so the upload is visible in the history tab
      const data = await api.pairCamera(demoSessionId());
      setQrCode(data.qr_code);
      setToken(data.token);

      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const status = await api.cameraStatus(data.token);
          if (status.last_result) {
            const r = status.last_result;
            setResult(r);
            if (r.preview_image) setPreviewImage(r.preview_image);
            setScanStatus("completed");
            // Append to session history
            setScanHistory((prev) => [
              {
                id: `scan_${Date.now()}`,
                timestamp: new Date(),
                result: r,
                previewImage: r.preview_image,
              },
              ...prev.slice(0, 9), // keep last 10 scans
            ]);
            stopPolling(); // stop after first result; "Scan Another" starts a fresh session
          } else if (
            status.status === "processing" ||
            (status.last_upload && !status.last_result && status.status !== "error")
          ) {
            setScanStatus("processing");
          } else if (status.status === "error" || status.last_error) {
            setScanStatus("error");
            setStatusError(status.last_error || "Extraction failed");
          } else if (!status.active) {
            stopPolling(); // token expired/revoked with nothing uploaded
          }
        } catch {
          // transient network hiccup — keep polling, don't surface an error
        }
      }, POLL_INTERVAL_MS);
    } catch (err: any) {
      setError(err.message || "Failed to pair camera");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    stopPolling();
    setQrCode(null);
    setToken("");
    setResult(null);
    setPreviewImage(null);
    setScanStatus("waiting");
    setStatusError(null);
  };

  return (
    <div className="space-y-6">
      {/* Lightbox Modal */}
      {lightboxSrc && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4 animate-in fade-in duration-200"
          onClick={() => setLightboxSrc(null)}
        >
          <div className="relative max-w-4xl w-full" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setLightboxSrc(null)}
              className="absolute -top-10 right-0 text-zinc-400 hover:text-white p-2 transition"
            >
              <X size={24} />
            </button>
            <img
              src={lightboxSrc}
              alt="Scanned Document Preview"
              className="w-full max-h-[85vh] object-contain rounded-2xl border border-zinc-700 shadow-2xl"
            />
          </div>
        </div>
      )}

      {/* Page Header */}
      <div className="flex items-center gap-3 pb-4 border-b border-line">
        <div className="p-2 bg-surface-2 rounded-lg border border-line">
          <Camera size={20} className="text-dim" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-body">Mobile Scanner</h1>
          <p className="text-sm text-muted">
            Pair your smartphone to directly scan physical documents into the Vision pipeline
          </p>
        </div>
      </div>

      {/* QR / Result Panel */}
      <Card className="max-w-2xl mx-auto p-8 text-center space-y-6">
        {!qrCode ? (
          <>
            <div className="flex justify-center mb-6 text-zinc-500">
              <Smartphone size={64} />
            </div>
            <h2 className="text-xl font-medium text-white">Connect Mobile Device</h2>
            <p className="text-zinc-400 max-w-sm mx-auto">
              Scan a QR code to temporarily pair your smartphone's camera. Photos will be
              automatically uploaded and processed via the Vision AI pipeline.
            </p>
            <Button onClick={handlePair} disabled={loading} className="mt-6 w-48">
              {loading ? (
                <RefreshCw className="animate-spin mr-2" size={18} />
              ) : (
                <Camera className="mr-2" size={18} />
              )}
              {loading ? "Generating..." : "Generate QR"}
            </Button>
            {error && <p className="text-red-400 mt-4">{error}</p>}
          </>
        ) : (
          <div className="space-y-6 animate-in fade-in duration-300">
            <h2 className="text-xl font-medium text-white">
              {result ? "Scan Received ✓" : "Ready to Scan"}
            </h2>

            {/* QR + Waiting indicators */}
            {!result && (
              <>
                <p className="text-zinc-400">Scan this QR code with your phone's camera</p>
                <div className="inline-block p-4 bg-white rounded-xl shadow-lg my-4">
                  <img
                    src={qrCode ?? undefined}
                    alt="Pairing QR Code"
                    className="w-64 h-64 mx-auto"
                  />
                </div>
                <p className="text-sm font-mono text-zinc-500">Token: {token}</p>
                {scanStatus === "processing" ? (
                  <div className="flex items-center justify-center space-x-2 text-amber-400 bg-amber-500/10 border border-amber-500/30 rounded-xl py-2.5 px-4 animate-pulse">
                    <RefreshCw className="animate-spin text-amber-400" size={16} />
                    <span className="font-medium text-sm">
                      Photo received! Extracting fields via Vision AI…
                    </span>
                  </div>
                ) : scanStatus === "error" ? (
                  <div className="text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-xl py-2.5 px-4 text-sm text-center">
                    Upload error: {statusError || "Extraction failed"}. Please retry from your phone.
                  </div>
                ) : (
                  <div className="flex items-center justify-center space-x-2 text-emerald-400">
                    <RefreshCw className="animate-spin" size={16} />
                    <span>Waiting for mobile upload...</span>
                  </div>
                )}
              </>
            )}

            {/* Extraction Result */}
            {result && (
              <div className="text-left space-y-4">
                {/* Scanned Photo Preview */}
                {previewImage && (
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted uppercase font-semibold tracking-wider">
                      Scanned Document
                    </p>
                    <div
                      className="relative group overflow-hidden rounded-xl border border-line cursor-zoom-in"
                      onClick={() => setLightboxSrc(previewImage)}
                    >
                      <img
                        src={previewImage}
                        alt="Scanned document preview"
                        className="w-full max-h-64 object-contain bg-zinc-950"
                      />
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition flex items-center justify-center">
                        <ZoomIn
                          size={28}
                          className="text-white opacity-0 group-hover:opacity-100 transition"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Status Banner */}
                <div className="flex items-center justify-between p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 size={20} />
                    <span className="font-semibold text-sm">Document Processed Successfully</span>
                  </div>
                  <span className="text-xs font-mono bg-emerald-500/20 px-2.5 py-1 rounded-full">
                    {result.confidence != null
                      ? `${Math.round(result.confidence * 100)}% confidence`
                      : "Complete"}
                  </span>
                </div>

                {/* Route + Type badges */}
                {(result.doc_type || result.route) && (
                  <div className="flex items-center gap-2 flex-wrap">
                    {result.doc_type && <Chip tone="accent">{result.doc_type}</Chip>}
                    {result.route && <Chip>{result.route}</Chip>}
                  </div>
                )}

                {/* Key Fields Grid */}
                {result.fields && typeof result.fields === "object" && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3.5 bg-surface-2 rounded-xl border border-line text-xs">
                    {Boolean(result.fields.vendor) && (
                      <div className="p-2 bg-surface-1 rounded-lg border border-line">
                        <span className="text-muted block text-[10px] uppercase font-semibold">Vendor</span>
                        <span className="text-body font-medium truncate block">
                          {String(result.fields.vendor)}
                        </span>
                      </div>
                    )}
                    {result.fields.total != null && (
                      <div className="p-2 bg-surface-1 rounded-lg border border-line">
                        <span className="text-muted block text-[10px] uppercase font-semibold">Total</span>
                        <span className="text-emerald-400 font-bold block">
                          {result.fields.currency ? `${result.fields.currency} ` : "$"}
                          {Number(result.fields.total).toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                          })}
                        </span>
                      </div>
                    )}
                    {Boolean(result.fields.date) && (
                      <div className="p-2 bg-surface-1 rounded-lg border border-line">
                        <span className="text-muted block text-[10px] uppercase font-semibold">Date</span>
                        <span className="text-body block">{String(result.fields.date)}</span>
                      </div>
                    )}
                    {Boolean(result.fields.invoice_number) && (
                      <div className="p-2 bg-surface-1 rounded-lg border border-line">
                        <span className="text-muted block text-[10px] uppercase font-semibold">Invoice #</span>
                        <span className="text-body font-mono block truncate">
                          {String(result.fields.invoice_number)}
                        </span>
                      </div>
                    )}
                  </div>
                )}

                {/* Raw JSON */}
                <div>
                  <div className="flex items-center justify-between pb-1.5 text-xs text-muted font-medium">
                    <span>Extracted JSON Payload</span>
                    {result.processing_time_ms && <span>{result.processing_time_ms} ms</span>}
                  </div>
                  <pre className="bg-zinc-950 border border-line rounded-xl p-4 text-xs text-zinc-300 font-mono overflow-auto max-h-72">
                    {JSON.stringify(result.fields, null, 2)}
                  </pre>
                </div>
              </div>
            )}

            <div className="pt-4">
              <Button variant="secondary" onClick={handleReset}>
                {result ? "Scan Another Document" : "Reset Pairing Session"}
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Recent Mobile Scans — session history */}
      {scanHistory.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-body">
            <Scan size={16} className="text-dim" />
            <span>Recent Mobile Scans This Session</span>
            <span className="text-xs text-muted font-normal">({scanHistory.length})</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {scanHistory.map((item) => (
              <Card key={item.id} className="p-4 space-y-3">
                {/* Thumbnail */}
                {item.previewImage ? (
                  <div
                    className="relative group cursor-zoom-in overflow-hidden rounded-lg border border-line"
                    onClick={() => setLightboxSrc(item.previewImage!)}
                  >
                    <img
                      src={item.previewImage}
                      alt="Scan preview"
                      className="w-full h-28 object-contain bg-zinc-950"
                    />
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition flex items-center justify-center">
                      <ZoomIn
                        size={20}
                        className="text-white opacity-0 group-hover:opacity-100 transition"
                      />
                    </div>
                  </div>
                ) : (
                  <div className="w-full h-16 rounded-lg border border-line bg-surface-2 flex items-center justify-center">
                    <FileText size={24} className="text-dim" />
                  </div>
                )}

                {/* Meta */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    {item.result.doc_type && (
                      <Chip tone="accent" className="text-[10px]">
                        {item.result.doc_type}
                      </Chip>
                    )}
                    <ConfidenceBadge value={item.result.confidence} />
                  </div>
                  {Boolean(item.result.fields?.vendor) && (
                    <p className="text-xs text-body truncate font-medium">
                      {String(item.result.fields!.vendor)}
                    </p>
                  )}
                  {item.result.fields?.total != null && (
                    <p className="text-xs text-emerald-400 font-bold">
                      {item.result.fields.currency
                        ? `${String(item.result.fields.currency)} `
                        : "$"}
                      {Number(item.result.fields.total).toLocaleString()}
                    </p>
                  )}
                  <p className="text-[10px] text-muted">{item.timestamp.toLocaleTimeString()}</p>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
