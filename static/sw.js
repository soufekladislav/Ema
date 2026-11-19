/* EMA offline shell v2: never serve stale application JS/CSS, authenticated data stays network-only. */
const VERSION = "ema-shell-20261119-original-ema";
const SHELL = [
  "/static/offline.html",
  "/static/icons/ema-192.png",
  "/static/icons/ema-512.png",
  "/static/icons/ema-avatar.png",
  "/static/icons/ema-source.jpg",
];
const ALLOWED = new Set(SHELL);
self.addEventListener("install",(event)=>{
  event.waitUntil(caches.open(VERSION).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting()));
});
self.addEventListener("activate",(event)=>{
  event.waitUntil(
    caches.keys().then(keys=>Promise.all(keys.filter(
      key=>key.startsWith("ema-") && key!==VERSION
    ).map(key=>caches.delete(key)))).then(()=>self.clients.claim())
  );
});
self.addEventListener("fetch",(event)=>{
  const req=event.request;
  if(req.method!=="GET")return;
  const url=new URL(req.url);
  if(url.origin!==self.location.origin)return;
  if(ALLOWED.has(url.pathname)){
    event.respondWith(caches.open(VERSION).then(async cache=>(await cache.match(url.pathname))||fetch(req)));
    return;
  }
  // Stylesheets and JS must ALWAYS be fetched from server. No stale cache-first
  // app.css/mail-v1.js after future deploys, even when old files keep same names.
  if(url.pathname.startsWith("/static/"))return;
  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(async()=>(await caches.open(VERSION)).match("/static/offline.html")));
  }
  // No other responses (API, mail content, files or logged-in HTML) are cached.
});
