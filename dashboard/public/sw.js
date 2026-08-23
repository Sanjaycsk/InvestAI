// Service worker — VERSIONED so every deploy invalidates the old cache and the
// installed mobile app self-updates (no manual "clear site data" needed).
//
// Why the rewrite: the previous SW used a constant cache name ("investai-v1"),
// so redeploys never busted the cache and phones stayed stuck on an old build.
// It also cached the HTML document, which could serve a stale page referencing
// dead JS chunks. This version: (1) bumps the cache name every release, (2)
// NEVER caches the live HTML (network-only for navigations), (3) cache-firsts
// only immutable hashed build assets, (4) purges old caches on activate.
//
// ⚠️ Bump CACHE_VERSION on every meaningful release (or when in doubt).
const CACHE_VERSION = "2026-08-17a";
const CACHE = `investai-${CACHE_VERSION}`;

// Only precache tiny, stable things. NOT "/" — the dashboard must be live.
// offline.html is the navigation fallback: previously that fell back to
// manifest.json, i.e. raw JSON rendered where a page was expected.
const OFFLINE_URL = "/offline.html";
const PRECACHE = ["/manifest.json", OFFLINE_URL];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)).catch(() => {}));
  self.skipWaiting(); // take over as soon as installed
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim()) // control open pages immediately
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Never touch API/auth — always live.
  if (url.pathname.startsWith("/api/")) return;

  // The HTML document (page navigations): NETWORK-ONLY so the app is never
  // stale. Only if truly offline do we fall back to whatever we have.
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req).catch(() =>
        caches.match(req).then((r) => r || caches.match(OFFLINE_URL))
      )
    );
    return;
  }

  // Immutable, content-hashed build assets + icons: cache-first is safe because
  // the URL changes whenever the content changes.
  if (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/icons/")
  ) {
    e.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
            return res;
          })
      )
    );
    return;
  }

  // Everything else: network-first, fall back to cache when offline.
  e.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(req))
  );
});

// Let the page trigger an immediate activation of a waiting SW.
self.addEventListener("message", (e) => {
  if (e.data === "SKIP_WAITING") self.skipWaiting();
});
