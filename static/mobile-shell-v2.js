/* A new filename bypasses old cache-first SW controlling the initial navigation. */
(() => {
  "use strict";
  const toggle = document.getElementById("ema-mobile-nav-toggle");
  const sidebar = document.getElementById("ema-app-main-nav");
  const backdrop = document.getElementById("ema-appmenu-backdrop");
  const closer = document.getElementById("ema-appmenu-close");
  if (!toggle || !sidebar || !backdrop || !closer) return;
  let priorFocus = null;
  function close(restore=true) {
    if (!document.body.classList.contains("ema-appmenu-open")) return;
    document.body.classList.remove("ema-appmenu-open");
    backdrop.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
    sidebar.removeAttribute("role");
    sidebar.removeAttribute("aria-modal");
    if (restore && priorFocus && priorFocus.isConnected) priorFocus.focus();
  }
  function open() {
    if (!window.matchMedia("(max-width:760px)").matches) return;
    priorFocus = document.activeElement;
    document.body.classList.add("ema-appmenu-open");
    document.body.classList.remove("ema-folder-pane-open");
    document.getElementById("ema-folder-drawer-toggle")?.setAttribute("aria-expanded","false");
    backdrop.hidden = false;
    toggle.setAttribute("aria-expanded","true");
    sidebar.setAttribute("role","dialog");
    sidebar.setAttribute("aria-modal","true");
    closer.focus();
  }
  // Capture the click before a previously cached mail-v1.js can attach its older handler.
  toggle.addEventListener("click",(ev) => {
    ev.stopImmediatePropagation();
    if (document.body.classList.contains("ema-appmenu-open")) close();
    else open();
  }, true);
  closer.addEventListener("click", () => close());
  backdrop.addEventListener("click", () => close());
  sidebar.addEventListener("click", (ev) => {
    if (ev.target.closest("a")) close(false);
  }, true);
  document.addEventListener("keydown",(ev) => {
    if (!document.body.classList.contains("ema-appmenu-open")) return;
    if (ev.key === "Escape") {ev.preventDefault();close();return;}
    if (ev.key !== "Tab") return;
    const nodes = Array.from(sidebar.querySelectorAll(
      'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled])'
    )).filter(el => el.getClientRects().length > 0);
    if (!nodes.length) return;
    if (ev.shiftKey && document.activeElement === nodes[0]) {
      ev.preventDefault();nodes[nodes.length-1].focus();
    } else if (!ev.shiftKey && document.activeElement === nodes[nodes.length-1]) {
      ev.preventDefault();nodes[0].focus();
    }
  }, true);
  window.addEventListener("resize",() => {
    if (!window.matchMedia("(max-width:760px)").matches) close(false);
  });
})();
