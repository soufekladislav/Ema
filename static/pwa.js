/* Register the offline-shell PWA only in a secure context. */
(() => {
  if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js", {scope:"/"})
      .then((registration) => registration.update())
      .catch(() => { /* PWA is optional; mail must still work online. */ });
  });
})();
