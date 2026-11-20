(() => {
  "use strict";
  const more = document.querySelector("[data-ema-mobile-more]");
  const toggle = document.getElementById("ema-mobile-nav-toggle");
  if (!more || !toggle) return;
  more.addEventListener("click", () => toggle.click());
})();