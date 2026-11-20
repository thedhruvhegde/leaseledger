/* Lease Ledger service worker (hand-written, no dependencies).
 * - install: precache the app shell (index.html + every built asset listed in /precache-manifest.json),
 *   the offline basemap, campus points, icons and manifest.
 * - navigations: network first, fall back to the cached shell (works offline, SPA routes).
 * - same-origin static files: cache first (hashed assets never change).
 * - the API (another origin in dev, or same-origin /api/* in production) is never intercepted: numbers are always live or clearly unavailable. */
const VERSION = 'll-v4';
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/favicon.svg', '/basemap.geojson', '/campus.geojson',
  '/icons/icon-192.png', '/icons/icon-512.png', '/icons/icon-maskable-512.png', '/icons/apple-touch-icon.png'];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(VERSION);
    let assets = [];
    try { assets = await (await fetch('/precache-manifest.json', { cache: 'no-store' })).json(); } catch { /* dev server: runtime caching only */ }
    await cache.addAll([...SHELL, ...assets.map((a) => `/${a}`)]);
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== VERSION) await caches.delete(k);
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  // Same-origin API (production: /api/* on the same host) always goes straight to the network.
  if (url.pathname.startsWith('/api/') || url.pathname === '/api') return;
  if (req.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const res = await fetch(req);
        const cache = await caches.open(VERSION);
        cache.put('/index.html', res.clone());
        return res;
      } catch {
        return (await caches.match('/index.html')) || (await caches.match('/')) || Response.error();
      }
    })());
    return;
  }
  event.respondWith((async () => {
    const hit = await caches.match(req);
    if (hit) return hit;
    const res = await fetch(req);
    if (res.ok && (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/') || /\.(geojson|woff2?|png|jpe?g|webp|svg|css|js)$/.test(url.pathname))) {
      const cache = await caches.open(VERSION);
      cache.put(req, res.clone());
    }
    return res;
  })());
});
