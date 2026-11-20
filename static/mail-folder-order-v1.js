/* EMA: display-only IMAP folder ordering, per user, per mailbox.
 * Do not rename, delete or MOVE server folders. Touch users get ↑ / ↓ controls.
 * Applied after mail-v11.js builds the visible IMAP hierarchy.
 */
(() => {
  "use strict";
  const root = document.querySelector("[data-mail-folder-root][data-folder-order-url]");
  if (!root) return;
  const entries = root.querySelector(".ema-mail-folder-entries");
  const status = root.querySelector("[data-folder-order-status]");
  if (!entries) return;
  const say = (message) => { if (status) status.textContent = message; };
  const links = Array.from(entries.querySelectorAll("a.ema-mail-folder[data-folder-id]"));
  const items = [];
  for (const link of links) {
    const row = document.createElement("div");
    row.className = "ema-folder-sort-item";
    row.draggable = true;
    row.dataset.folderId = link.dataset.folderId;
    link.before(row);
    row.append(link);
    const actions = document.createElement("span");
    actions.className = "ema-folder-sort-actions";
    for (const [direction, symbol, label] of [
      [-1, "↑", "Posunout složku nahoru"], [1, "↓", "Posunout složku dolů"]
    ]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "ema-folder-sort-button";
      button.textContent = symbol;
      button.title = label;
      button.setAttribute("aria-label", label + ": " + (link.textContent || "").trim());
      button.addEventListener("click", () => move(row, direction));
      actions.append(button);
    }
    row.append(actions);
    items.push(row);
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
      say("Ukládám vlastní pořadí složek…");
      try {
        const response = await fetch(root.dataset.folderOrderUrl, {
          method: "POST", credentials: "same-origin", cache: "no-store",
          headers: {"Content-Type": "application/json", "Accept": "application/json",
                    "X-CSRF-Token": root.dataset.csrf},
          body: JSON.stringify({ids:snapshot})
        });
        const result = await response.json();
        if (!response.ok || result.ok !== true ||
            JSON.stringify(result.ids) !== JSON.stringify(snapshot)) {
          throw Error(result.error || "Server nepotvrdil pořadí.");
        }
        say(queued ? "Ukládám další změnu…" : "Pořadí složek uloženo.");
      } catch (error) {
        say((error.message || "Uložení se nepovedlo.") + " Po obnovení se vrátí poslední potvrzené pořadí.");
      }
      if (JSON.stringify(order()) !== JSON.stringify(snapshot)) queued = true;
    }
    saving = false;
  }
  function move(row, direction) {
    const sibling = direction < 0 ? row.previousElementSibling : row.nextElementSibling;
    // Stay within a single IMAP parent group. Reparenting would require a
    // separate server RENAME operation and is deliberately NOT implemented.
    if (!sibling || !sibling.classList.contains("ema-folder-sort-item")) return;
    if (direction < 0) row.parentNode.insertBefore(row, sibling);
    else row.parentNode.insertBefore(row, sibling.nextSibling);
    row.querySelector("a")?.focus();
    void save();
  }
  let dragged = null;
  root.addEventListener("dragstart", (event) => {
    const row = event.target.closest(".ema-folder-sort-item");
    if (!row) return;
    dragged = row;
    row.classList.add("is-dragging");
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", row.dataset.folderId);
    }
  });
  root.addEventListener("dragover", (event) => {
    const target = event.target.closest(".ema-folder-sort-item");
    if (!dragged || !target || target === dragged || dragged.parentElement !== target.parentElement) return;
    event.preventDefault();
    const rect = target.getBoundingClientRect();
    target.parentNode.insertBefore(dragged, event.clientY < rect.top + rect.height/2 ? target : target.nextSibling);
  });
  root.addEventListener("drop", (event) => {
    if (!dragged) return;
    event.preventDefault();
    dragged.classList.remove("is-dragging");
    dragged = null;
    void save();
  });
  root.addEventListener("dragend", () => {
    if (dragged) dragged.classList.remove("is-dragging");
    dragged = null;
  });
  root.addEventListener("keydown", (event) => {
    if (!event.altKey || !["ArrowUp", "ArrowDown"].includes(event.key)) return;
    const row = event.target.closest(".ema-folder-sort-item");
    if (!row) return;
    event.preventDefault();
    move(row, event.key === "ArrowUp" ? -1 : 1);
  });
})();