// Safe Auto-Updating Service Worker (Stale-While-Revalidate)
const CACHE_NAME = 'ysiddo-docintel-v1';

self.addEventListener('install', (e) => {
  // Instantly take over, do not wait for the user to close all tabs
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  // Instantly claim all controlled clients to apply the new rules immediately
  e.waitUntil(self.clients.claim());
  
  // Purge any stale legacy caches (like v1 or other apps on the same host)
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME && key.startsWith('ysiddo-docintel')) return caches.delete(key);
          // Also purge the old buggy global cache
          if (key === 'omniintel-sw-v2') return caches.delete(key);
        })
      );
    })
  );
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  
  // Bypass SW for API routes, websockets, and extensions
  if (url.pathname.startsWith('/api') || url.pathname.startsWith('/health') || url.pathname.startsWith('/socket.io')) return;

  // 1. HTML Navigation: Network-First
  // Always get fresh HTML to ensure new JS bundles are referenced.
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

  // 2. Assets (JS, CSS, Images, Fonts): Stale-While-Revalidate
  // Returns instantly from cache (super fast UI), but ALWAYS fetches in background to update cache.
  // Prevents the "forever stale" bug on non-hashed assets.
  e.respondWith(
    caches.match(e.request).then((cachedResponse) => {
      const fetchPromise = fetch(e.request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
          const responseClone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(e.request, responseClone));
        }
        return networkResponse;
      }).catch(() => {
        // Fail silently for offline
      });

      // Return cached immediately if available, otherwise wait for network
      return cachedResponse || fetchPromise;
    })
  );
});
