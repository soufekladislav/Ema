/* EMA PWA — offline shell only, NEVER cache authentication or mail content. */
const VERSION = "ema-mail-v1-shell-1";
const SHELL = [
  "/static/offline.html",
  "/static/app.css",
  "/static/mail-v1.js",
  "/static/mail-pager.js",
  "/static/mail-ui.js",
  "/static/icons/ema-192.png",
  "/static/icons/ema-512.png",
];
const ALLOWED = new Set(SHELL);
self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) => Promise.all(names.filter((name) => name.startsWith("ema-") && name !== VERSION).map((name) => caches.delete(name))))
      .then(() => self.clients.claim())
  );
});
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (ALLOWED.has(url.pathname)) {
    event.respondWith(caches.open(VERSION).then(async (cache) => (await cache.match(url.pathname)) || fetch(req)));
    return;
  }
  // All authenticated pages, JSON APIs, previews, attachments, contacts, inbox and
  // remote images remain network-only and MUST NOT be persisted in CacheStorage.
  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(async () =>
      (await caches.open(VERSION)).match("/static/offline.html")
    ));
  }
});
