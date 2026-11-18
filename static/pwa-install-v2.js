/* EMA install v2: explain WHY native install is unavailable; no silent "Rozumím" dead end. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const install = $("ema-install-button");
  const modal = $("ema-install-dialog");
  const instructions = $("ema-install-instructions");
  const checks = $("ema-pwa-diagnostics-output");
  const checkButton = $("ema-pwa-check");
  const copyButton = $("ema-pwa-copy");
  const retryButton = $("ema-pwa-retry");
  const closer = $("ema-install-close");
  const done = $("ema-install-ok");
  const splash = $("ema-pwa-splash");
  let deferredPrompt = null;
  let latestReport = "";
  let installedThisSession = false;
  const standalone = () => window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;
  const ios = () => /iPad|iPhone|iPod/i.test(navigator.userAgent || "") ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const android = () => /Android/i.test(navigator.userAgent || "");
  const chromium = () => /Chrome|Chromium|CriOS|EdgA/i.test(navigator.userAgent || "");
  const setInstallVisibility = () => {
    if (install) install.hidden = standalone() || installedThisSession;
  };
  const showModal = () => {
    if (!modal) return;
    if (typeof modal.showModal === "function") {
      if (!modal.open) modal.showModal();
    } else {
      modal.setAttribute("open", "");
      modal.setAttribute("aria-modal", "true");
    }
  };
  const hideModal = () => {
    if (!modal) return;
    if (typeof modal.close === "function" && modal.open) modal.close();
    else modal.removeAttribute("open");
  };
  const announce = (text) => {
    if (instructions) instructions.textContent = text;
  };
  const setRetry = () => {
    if (retryButton) retryButton.hidden = !deferredPrompt || standalone();
  };

  async function nativePrompt() {
    if (!deferredPrompt || standalone()) return false;
    // Calling prompt() must be triggered directly by a real user click.
    const event = deferredPrompt;
    deferredPrompt = null;
    setRetry();
    try {
      await event.prompt();
      const decision = await event.userChoice;
      if (decision?.outcome === "dismissed") {
        announce("Instalaci jsi v systémovém dialogu odmítl. Pro opakování musí Chrome nabídnout nový instalační dialog.");
      } else if (decision?.outcome === "accepted") {
        announce("Chrome přijal požadavek na instalaci. Dokončení potvrdí prohlížeč; EMA se na ploše může objevit s krátkým zpožděním.");
      }
    } catch (error) {
      announce("Chrome instalační dialog neotevřel (" +
        (error?.name || "chyba") + "). Zkus nabídku Chrome ⋮ → Přidat na plochu.");
    }
    return true;
  }

  function manualGuidance() {
    if (ios()) return "iPhone/iPad: otevři EMA v Safari → Sdílet → Přidat na plochu. iOS neumožňuje tuto instalaci automaticky spustit tlačítkem.";
    if (android()) return "Chrome zatím nenabídl aplikaci k instalaci. Otevři v Chrome nabídku ⋮ → Přidat na plochu / Nainstalovat aplikaci. Pokud nabízí jen zástupce, použij níže diagnostiku – může jít o neplatný manifest, chybějící ikonu nebo už nainstalovanou EMA.";
    return "Chrome/Edge: použij menu prohlížeče ⋮ → Nainstalovat EMA. Není-li tato možnost dostupná, spusť kontrolu níže. Samotné tlačítko Zavřít nic neinstaluje.";
  }

  function openGuidance() {
    announce(manualGuidance());
    setRetry();
    showModal();
    void diagnose();
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    setInstallVisibility();
    setRetry();
    if (modal?.open) announce("Chrome nyní nabízí instalaci. Klepni na „Spustit instalaci“.");
  });
  window.addEventListener("appinstalled", () => {
    installedThisSession = true;
    deferredPrompt = null;
    setInstallVisibility();
    hideModal();
  });
  setInstallVisibility();
  install?.addEventListener("click", () => {
    if (deferredPrompt) void nativePrompt();
    else openGuidance();
  });
  retryButton?.addEventListener("click", () => {
    if (deferredPrompt) void nativePrompt();
    else openGuidance();
  });
  closer?.addEventListener("click", hideModal);
  done?.addEventListener("click", hideModal);
  modal?.addEventListener("click", (event) => {
    if (event.target === modal) hideModal();
  });
  modal?.addEventListener("cancel", hideModal);
  document.querySelectorAll("[data-ema-pwa-diagnose]").forEach((element) => {
    element.addEventListener("click", openGuidance);
  });

  // Report contains no cookies, tokens, email addresses, user-agent string or message data.
  async function diagnose() {
    if (!checks) return;
    checks.textContent = "Kontroluji manifest, ikony a Service Worker…";
    const lines = [
      "EMA PWA diagnostika",
      "HTTPS / bezpečný kontext: " + (window.isSecureContext ? "ANO" : "NE"),
      "Zařízení: " + (ios() ? "iOS" : android() ? "Android" : "Desktop/jiné"),
      "Prohlížeč Chromium: " + (chromium() ? "pravděpodobně" : "nebo nerozpoznáno"),
      "Režim samostatné aplikace: " + (standalone() ? "ANO" : "NE"),
      "Chrome poskytl beforeinstallprompt: " + (deferredPrompt ? "ANO" : "NE"),
    ];
    const path = document.querySelector('link[rel="manifest"]')?.getAttribute("href");
    if (!path) {
      lines.push("Manifest: CHYBÍ odkaz v HTML");
    } else {
      try {
        const response = await fetch(path, {credentials:"same-origin",cache:"no-store"});
        if (!response.ok) throw Error("HTTP " + response.status);
        const manifest = await response.json();
        const url = new URL(path, location.href);
        lines.push("Manifest: HTTP 200, JSON OK");
        lines.push("Název: " + (manifest.short_name || manifest.name || "CHYBÍ"));
        lines.push("Display: " + (manifest.display || "CHYBÍ"));
        lines.push("Start URL: " + (manifest.start_url || "CHYBÍ"));
        const icons = Array.isArray(manifest.icons) ? manifest.icons : [];
        for (const size of ["192x192", "512x512"]) {
          const icon = icons.find((entry) => (entry.sizes || "").split(/\s+/).includes(size));
          if (!icon) {
            lines.push("Ikona " + size + ": CHYBÍ");
            continue;
          }
          const iconUrl = new URL(icon.src, url);
          if (iconUrl.origin !== location.origin) {
            lines.push("Ikona " + size + ": mimo doménu, neověřena");
            continue;
          }
          try {
            const imageResponse = await fetch(iconUrl.href, {credentials:"same-origin", cache:"no-store"});
            if (!imageResponse.ok) throw Error("HTTP " + imageResponse.status);
            const blob = await imageResponse.blob();
            lines.push("Ikona " + size + ": OK (" + Math.round(blob.size/1024) + " KiB)");
          } catch (error) {
            lines.push("Ikona " + size + ": CHYBA " + (error.message || "fetch"));
          }
        }
      } catch (error) {
        lines.push("Manifest: CHYBA " + (error.message || "neplatný soubor"));
      }
    }
    if (!("serviceWorker" in navigator)) {
      lines.push("Service Worker: prohlížeč nepodporuje");
    } else {
      try {
        const response = await fetch("/service-worker.js", {credentials:"same-origin",cache:"no-store"});
        lines.push("SW soubor: HTTP " + response.status);
        const reg = await navigator.serviceWorker.getRegistration("/");
        lines.push("SW registrace: " + (reg ? (reg.active ? "AKTIVNÍ" : "čeká na aktivaci") : "NENÍ"));
      } catch (error) {
        lines.push("Service Worker: CHYBA " + (error?.name || "registrace"));
      }
    }
    if (!deferredPrompt) lines.push("Pozn.: Chrome neposkytl instalační událost. Důvod nelze z JavaScriptu vždy zjistit; aplikace může být již instalována nebo ji Chrome zatím nevyhodnotil jako instalovatelnou.");
    latestReport = lines.join("\n");
    checks.textContent = latestReport;
  }
  checkButton?.addEventListener("click", () => void diagnose());
  copyButton?.addEventListener("click", async () => {
    if (!latestReport) await diagnose();
    try {
      await navigator.clipboard.writeText(latestReport);
      copyButton.textContent = "Zkopírováno";
    } catch (_) {
      if (checks) {
        const select = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(checks);
        select.removeAllRanges();
        select.addRange(range);
      }
      copyButton.textContent = "Označeno ke kopírování";
    }
  });

  if (splash && standalone()) {
    let shown = false;
    try {
      shown = sessionStorage.getItem("ema.pwa.launch.v1") === "shown";
      if (!shown) sessionStorage.setItem("ema.pwa.launch.v1", "shown");
    } catch (_) { /* Storage optional */ }
    if (!shown) {
      splash.hidden = false;
      const dismiss = () => {
        splash.classList.add("ema-pwa-splash-out");
        window.setTimeout(() => { splash.hidden = true; }, 220);
      };
      window.setTimeout(dismiss, 900);
    }
  }
})();
