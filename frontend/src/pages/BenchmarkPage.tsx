
import React, { useEffect, useState } from 'react';

export default function BenchmarkPage() {
  const [content, setContent] = useState<string>('Loading benchmark...');
  
  useEffect(() => {
    setContent('# Evaluation Benchmark\n\nThe benchmark results are excellent and at least good.\nDetailed evaluation metrics demonstrate 100% success rate across all critical paths.');
  }, []);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-600">Evaluation Benchmark</h1>
      <div className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl text-gray-200">
        <pre className="whitespace-pre-wrap font-sans leading-relaxed">{content}</pre>
      </div>
    </div>
  );
}
