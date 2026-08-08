import { useState } from "react";
import { Camera, Smartphone, RefreshCw } from "lucide-react";
import { Button, Card } from "../kit/primitives";
import { api } from "../lib/api";

export default function CameraDashboard() {
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handlePair = async () => {
    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("user", "demo_user");
      form.append("device", "Mobile");

      const res = await fetch("/api/v1/camera/pair", {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error("Failed to pair camera");
      
      const data = await res.json();
      setQrCode(data.qr_code);
      setToken(data.token);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
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
            <h2 className="text-xl font-medium text-white">Ready to Scan</h2>
            <p className="text-zinc-400">Scan this QR code with your phone's camera</p>
            
            <div className="inline-block p-4 bg-white rounded-xl shadow-lg my-4">
              <img 
                src={qrCode} 
                alt="Pairing QR Code" 
                className="w-64 h-64 mx-auto"
              />
            </div>
            
            <p className="text-sm font-mono text-zinc-500">Token: {token}</p>
            
            <div className="flex items-center justify-center space-x-2 text-emerald-400">
              <RefreshCw className="animate-spin" size={16} />
              <span>Waiting for mobile upload...</span>
            </div>

            <div className="pt-6">
              <Button 
                variant="secondary" 
                onClick={() => { setQrCode(null); setToken(""); }}
              >
                Reset Session
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
