/* CogSec Tracker service worker.
 *
 * Goal is a home-screen app that opens instantly and degrades honestly when
 * offline. Deliberately NOT an offline-write queue: every form here is a
 * last-write-wins upsert, so replaying queued writes later would silently
 * clobber whatever you logged in between. Offline is read-only by design.
 *
 * Bump VERSION to force clients onto new assets.
 */
const VERSION = 'cogsec-v1';
const ASSETS = `${VERSION}-assets`;
const PAGES = `${VERSION}-pages`;

// Auth-exempt on the server, so these are fetchable before you log in.
const PRECACHE = [
  '/static/style.css',
  '/static/offline.html',
  '/static/icons/icon-192.png',
  '/static/icons/apple-touch-icon.png',
  '/manifest.webmanifest',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(ASSETS)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// Logging out should not leave your journal sitting in the cache.
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'clear-cache') {
    event.waitUntil(caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k)))));
  }
});

function isCacheablePage(request, response) {
  // Don't store redirects (an expired session redirects to /login — caching
  // that would pin the login page in place of the real one), or the auth pages.
  const path = new URL(request.url).pathname;
  return response
    && response.ok
    && !response.redirected
    && path !== '/login'
    && path !== '/logout';
}

self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Writes must always hit the network — never serve or store a stale POST.
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Pages: network-first, so you always see current data when you have a signal.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (isCacheablePage(request, response)) {
            const copy = response.clone();
            caches.open(PAGES).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => caches.match(request).then((hit) => hit || caches.match('/static/offline.html')))
    );
    return;
  }

  // Assets: cache-first, they're versioned by the cache name above.
  event.respondWith(
    caches.match(request).then((hit) => hit || fetch(request).then((response) => {
      if (response.ok && response.type === 'basic') {
        const copy = response.clone();
        caches.open(ASSETS).then((cache) => cache.put(request, copy));
      }
      return response;
    }))
  );
});
