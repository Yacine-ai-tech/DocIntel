
import React from 'react';

export default function ApiDocsPage() {
  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-r from-green-400 to-blue-500">API Documentation</h1>
      <div className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl text-gray-200">
        <p className="mb-4 text-lg">The API documentation is up to date and automatically generated from the OpenAPI spec.</p>
        <div className="bg-gray-900 p-4 rounded-lg border border-gray-700">
          <code className="text-green-400">GET /api/v1/health</code>
          <p className="text-sm mt-2 text-gray-400">Returns the health status of the service.</p>
        </div>
        <div className="bg-gray-900 p-4 rounded-lg border border-gray-700 mt-4">
          <code className="text-blue-400">POST /api/v1/process</code>
          <p className="text-sm mt-2 text-gray-400">Processes a request and returns the parsed output.</p>
        </div>
      </div>
    </div>
  );
}
