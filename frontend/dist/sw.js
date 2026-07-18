// Safe Auto-Updating Service Worker (Network-First for HTML)
const CACHE_NAME = 'omniintel-sw-v2';

self.addEventListener('install', (e) => {
  // Instantly take over, do not wait for the user to close all tabs
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  // Instantly claim all controlled clients to apply the new rules immediately
  e.waitUntil(self.clients.claim());
  
  // Purge any stale legacy caches (like v1)
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) return caches.delete(key);
        })
      );
    })
  );
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  
  // Never intercept API routes
  if (url.pathname.startsWith('/api') || url.pathname.startsWith('/health')) return;

  // 1. HTML Documents: Network-First Strategy
  // Guarantees users ALWAYS get the latest index.html on reload.
  // Only falls back to the cached version if there is absolutely no internet connection.
  if (e.request.mode === 'navigate' || e.request.destination === 'document') {
    e.respondWith(
      fetch(e.request)
        .then((response) => {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(e.request, responseClone));
          return response;
        })
        .catch(() => caches.match(e.request)) // Offline fallback
    );
    return;
  }

  // 2. Static Assets (Vite hashes JS/CSS): Cache-First Strategy
  // Safe to cache aggressively because Vite guarantees file names change on every build.
  e.respondWith(
    caches.match(e.request).then((cachedResponse) => {
      if (cachedResponse) return cachedResponse;
      
      return fetch(e.request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
          const responseClone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(e.request, responseClone));
        }
        return networkResponse;
      }).catch(() => {
        // Fail silently for missing images/fonts offline
      });
    })
  );
});
