import { useEffect, useState } from 'react';
import { api } from '../lib/api';

export default function BenchmarkPage() {
  const [content, setContent] = useState<string | null>(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    api.benchmarks()
      .then((r) => setContent(r.markdown))
      .catch((e) => setErr(e.message || 'Failed to load live benchmark data'));
  }, []);

  return (
    <div className="p-8 max-w-5xl mx-auto overflow-auto h-full">
      <h1 className="text-3xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-600">Evaluation Benchmark</h1>
      <div className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl text-gray-200">
        {err ? (
          <div className="text-sm text-red-400">{err}</div>
        ) : content === null ? (
          <div className="text-sm text-gray-400">Loading…</div>
        ) : (
          <pre className="whitespace-pre-wrap font-sans leading-relaxed text-sm">{content}</pre>
        )}
      </div>
    </div>
  );
}
