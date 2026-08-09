import { useEffect, useRef, useState } from "react";
import { Camera, Smartphone, RefreshCw, CheckCircle2 } from "lucide-react";
import { Button, Card } from "../kit/primitives";
import { api, type CameraUploadResult } from "../lib/api";

const POLL_INTERVAL_MS = 3000;

export default function CameraDashboard() {
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<CameraUploadResult | null>(null);
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
    try {
      const data = await api.pairCamera();
      setQrCode(data.qr_code);
      setToken(data.token);

      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const status = await api.cameraStatus(data.token);
          if (status.last_result) {
            setResult(status.last_result);
            stopPolling(); // stop after the first result; "Scan Another" starts a fresh session
          } else if (!status.active) {
            stopPolling(); // token expired/revoked with nothing uploaded
          }
        } catch {
          // transient network hiccup — keep polling, don't surface an error for this
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
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 pb-4 border-b border-line">
        <div className="p-2 bg-surface-2 rounded-lg border border-line">
          <Camera size={20} className="text-dim" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-body">Mobile Scanner</h1>
          <p className="text-sm text-muted">Pair your smartphone to directly scan physical documents into the Vision pipeline</p>
        </div>
      </div>

      <Card className="max-w-2xl mx-auto p-8 text-center space-y-6">
        {!qrCode ? (
          <>
            <div className="flex justify-center mb-6 text-zinc-500">
              <Smartphone size={64} />
            </div>
            <h2 className="text-xl font-medium text-white">Connect Mobile Device</h2>
            <p className="text-zinc-400 max-w-sm mx-auto">
              Scan a QR code to temporarily pair your smartphone's camera. Photos will be automatically uploaded and processed via the local vision route.
            </p>
            <Button
              onClick={handlePair}
              disabled={loading}
              className="mt-6 w-48"
            >
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
              {result ? "Scan Received" : "Ready to Scan"}
            </h2>

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
                <div className="flex items-center justify-center space-x-2 text-emerald-400">
                  <RefreshCw className="animate-spin" size={16} />
                  <span>Waiting for mobile upload...</span>
                </div>
              </>
            )}

            {result && (
              <div className="text-left space-y-3">
                <div className="flex items-center justify-center gap-2 text-emerald-400 mb-2">
                  <CheckCircle2 size={20} />
                  <span>
                    Photo processed
                    {result.confidence != null ? ` — confidence ${(result.confidence * 100).toFixed(0)}%` : ""}
                  </span>
                </div>
                <pre className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 text-xs text-zinc-300 overflow-auto max-h-72">
                  {JSON.stringify(result.fields, null, 2)}
                </pre>
              </div>
            )}

            <div className="pt-6">
              <Button variant="secondary" onClick={handleReset}>
                {result ? "Scan Another" : "Reset Session"}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
