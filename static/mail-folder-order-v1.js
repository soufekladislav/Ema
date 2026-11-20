/* EMA mail folders: one contextual interaction, not a wall of controls.
 * Right click / long press / Shift+F10 -> create via existing IMAP POST.
 * Drag to re-order sibling items in this user's view; never IMAP RENAME.
 * Runs AFTER mail-v11.js has assembled the IMAP folder hierarchy.
 */
(() => {
  "use strict";
  const root = document.querySelector("[data-mail-folder-root][data-folder-order-url]");
  if (!root) return;
  const entries = root.querySelector(".ema-mail-folder-entries");
  const status = root.querySelector("[data-folder-order-status]");
  if (!entries) return;
  const canManage = root.dataset.canManage === "1";
  const dialog = root.querySelector("[data-folder-create-dialog]");
  const menu = document.createElement("div");
  menu.className = "ema-folder-context-menu";
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", "Akce se složkou");
  menu.hidden = true;
  document.body.append(menu);
  const say = (message) => { if (status) status.textContent = message; };
  const rows = [];
  for (const link of entries.querySelectorAll("a.ema-mail-folder[data-folder-id]")) {
    const row = document.createElement("div");
    row.className = "ema-folder-sort-item";
    row.draggable = true;
    row.dataset.folderId = link.dataset.folderId;
    link.draggable = false; // The row is the only drag target.
    link.before(row);
    row.append(link);
    rows.push(row);
  }
  const order = () => Array.from(entries.querySelectorAll(".ema-folder-sort-item"))
    .map(row => Number(row.dataset.folderId));
  let saving = false;
  let queued = false;
  async function save() {
    queued = true;
    if (saving) return;
    saving = true;
    while (queued) {
      queued = false;
      const snapshot = order();
      say("Ukládám pořadí složek…");
      try {
        const response = await fetch(root.dataset.folderOrderUrl, {
          method: "POST", credentials: "same-origin", cache: "no-store",
          headers: {"Content-Type":"application/json", "Accept":"application/json",
                    "X-CSRF-Token":root.dataset.csrf},
          body: JSON.stringify({ids:snapshot})
        });
        const result = await response.json();
        if (!response.ok || !result.ok ||
            JSON.stringify(result.ids) !== JSON.stringify(snapshot)) {
          throw Error(result.error || "Pořadí nebylo potvrzeno serverem.");
        }
        say(queued ? "Ukládám další změnu…" : "Pořadí složek uloženo.");
      } catch (error) {
        say((error.message || "Uložení se nepovedlo.") +
            " Po obnovení se vrátí poslední potvrzené pořadí.");
      }
      if (JSON.stringify(order()) !== JSON.stringify(snapshot)) queued = true;
    }
    saving = false;
  }
  function neighbor(row, dir) {
    const candidate = dir < 0 ? row?.previousElementSibling : row?.nextElementSibling;
    return candidate?.matches(".ema-folder-sort-item") ? candidate : null;
  }
  function move(row, dir) {
    const other = neighbor(row, dir);
    if (!other) return;
    if (dir < 0) other.before(row); else other.after(row);
    row.querySelector("a")?.focus();
    void save();
  }
  let returnFocus = null;
  function hideMenu(restore=false) {
    if (menu.hidden) return;
    menu.hidden = true;
    menu.replaceChildren();
    if (restore && returnFocus?.isConnected) returnFocus.focus();
  }
  function openDialog(link) {
    hideMenu();
    if (!canManage || !dialog) return;
    const parent = dialog.querySelector("[data-folder-create-parent]");
    const label = dialog.querySelector("[data-folder-create-location]");
    const input = dialog.querySelector("[data-folder-create-name]");
    if (!parent || !input) return;
    parent.value = link?.dataset.folderId || "";
    if (label) label.textContent = link
      ? "Podsložka: " + (link.dataset.folderFullname || link.textContent || "").trim()
      : "Hlavní úroveň schránky";
    input.value = "";
    if (!dialog.open) dialog.showModal();
    input.focus();
  }
  const cancel = dialog?.querySelector("[data-folder-create-cancel]");
  if (cancel) cancel.addEventListener("click", () => dialog.close());
  dialog?.addEventListener("close", () => {
    if (returnFocus?.isConnected) returnFocus.focus();
  });
  function menuItem(label, action) {
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("role", "menuitem");
    button.textContent = label;
    button.addEventListener("click", () => {hideMenu(); action();});
    menu.append(button);
  }
  function showMenu(link, x, y) {
    if (!canManage) return;
    hideMenu();
    returnFocus = link || root.querySelector("summary");
    menuItem(link ? "Nová podsložka" : "Nová složka", () => openDialog(link));
    const row = link?.closest(".ema-folder-sort-item");
    if (row) {
      if (neighbor(row, -1)) menuItem("Posunout výše", () => move(row, -1));
      if (neighbor(row, 1)) menuItem("Posunout níže", () => move(row, 1));
    }
    menu.hidden = false;
    const width = menu.offsetWidth || 190;
    const height = menu.offsetHeight || 75;
    menu.style.left = Math.max(5, Math.min(x, window.innerWidth - width - 5)) + "px";
    menu.style.top = Math.max(5, Math.min(y, window.innerHeight - height - 5)) + "px";
    menu.querySelector("button")?.focus();
  }
  root.addEventListener("contextmenu", event => {
    const link = event.target.closest("a.ema-mail-folder[data-folder-id]");
    if (!link && !event.target.closest("summary, .ema-mail-folder-entries")) return;
    if (!canManage) return;
    event.preventDefault();
    const area = (link || root.querySelector("summary")).getBoundingClientRect();
    showMenu(link, event.clientX || area.left + 12,
             event.clientY || area.bottom);
  });
  document.addEventListener("pointerdown", event => {
    if (!menu.hidden && !menu.contains(event.target)) hideMenu();
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") {hideMenu(true); return;}
    if (event.key === "F10" && event.shiftKey &&
        root.contains(document.activeElement)) {
      const link = document.activeElement.closest("a.ema-mail-folder");
      event.preventDefault();
      const rect = (link || root.querySelector("summary")).getBoundingClientRect();
      showMenu(link, rect.left + 15, rect.bottom);
    }
  });
  window.addEventListener("scroll", () => hideMenu(), true);

  // HTML5 native DnD remains for a mouse or stylus.
  let dragged = null;
  root.addEventListener("dragstart", event => {
    const row = event.target.closest(".ema-folder-sort-item");
    if (!row) return;
    dragged = row;
    row.classList.add("is-dragging");
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", row.dataset.folderId);
    }
  });
  root.addEventListener("dragover", event => {
    const target = event.target.closest(".ema-folder-sort-item");
    if (!dragged || !target || target === dragged ||
        dragged.parentElement !== target.parentElement) return;
    event.preventDefault();
    const rect = target.getBoundingClientRect();
    target.parentElement.insertBefore(dragged,
      event.clientY < rect.top + rect.height / 2 ? target : target.nextSibling);
  });
  root.addEventListener("drop", event => {
    if (!dragged) return;
    event.preventDefault();
    dragged.classList.remove("is-dragging");
    dragged = null;
    void save();
  });
  root.addEventListener("dragend", () => {
    dragged?.classList.remove("is-dragging");
    dragged = null;
  });

  // Touch: normal swipe scrolls. Hold 450 ms then release -> context menu.
  // Hold then move -> reorder within the same parent, without navigating.
  let touch = null;
  let suppressClickUntil = 0;
  root.addEventListener("touchstart", event => {
    if (event.touches.length !== 1) return;
    const link = event.target.closest("a.ema-mail-folder[data-folder-id]");
    const summary = event.target.closest(".ema-mail-folders-root > summary");
    if (!link && !summary) return;
    const point = event.touches[0];
    touch = {link, row:link?.closest(".ema-folder-sort-item"), x:point.clientX,
             y:point.clientY, held:false, moved:false, timer:null};
    touch.timer = setTimeout(() => {if (touch) touch.held = true;}, 450);
  }, {passive:true});
  root.addEventListener("touchmove", event => {
    if (!touch || event.touches.length !== 1) return;
    const point = event.touches[0];
    const distance = Math.hypot(point.clientX-touch.x, point.clientY-touch.y);
    if (!touch.held) {
      if (distance > 12) {clearTimeout(touch.timer); touch = null;}
      return; // regular swipe, no obstruction
    }
    event.preventDefault();
    if (distance < 12 || !touch.row) return;
    touch.moved = true;
    touch.row.classList.add("is-dragging");
    const over = document.elementFromPoint(point.clientX, point.clientY)
      ?.closest(".ema-folder-sort-item");
    if (!over || over === touch.row ||
        over.parentElement !== touch.row.parentElement) return;
    const rect = over.getBoundingClientRect();
    over.parentElement.insertBefore(touch.row,
      point.clientY < rect.top + rect.height / 2 ? over : over.nextSibling);
  }, {passive:false});
  function finishTouch(event) {
    if (!touch) return;
    clearTimeout(touch.timer);
    const finished = touch;
    touch = null;
    if (!finished.held) return;
    event.preventDefault();
    suppressClickUntil = Date.now() + 700;
    finished.row?.classList.remove("is-dragging");
    if (finished.moved) {void save(); return;}
    const rect = (finished.link || root.querySelector("summary")).getBoundingClientRect();
    showMenu(finished.link, rect.left + 20, rect.bottom);
  }
  root.addEventListener("touchend", finishTouch, {passive:false});
  root.addEventListener("touchcancel", () => {
    if (touch) clearTimeout(touch.timer);
    touch?.row?.classList.remove("is-dragging");
    touch = null;
  });
  root.addEventListener("click", event => {
    if (Date.now() < suppressClickUntil) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);
})();