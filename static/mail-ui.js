/* Mailbox order: native drag-and-drop with keyboard fallback; no external libraries. */
(() => {
  "use strict";
  const list = document.getElementById("ema-mailbox-sort-list");
  if (!list) return;
  const info = document.getElementById("ema-mail-order-status");
  const items = () => Array.from(list.querySelectorAll(":scope > [data-mailbox-id]"));
  let dragged = null;
  let pending = false;
  const say = (value) => { if (info) info.textContent = value; };
  const save = async () => {
    if (pending) return;
    const ids = items().map((node) => Number(node.dataset.mailboxId));
    pending = true;
    say("Ukládám pořadí…");
    try {
      const response = await fetch(list.dataset.orderUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": list.dataset.csrf,
        },
        body: JSON.stringify({ ids }),
      });
      if (!response.ok) throw Error("order");
      say("Pořadí schránek uloženo.");
    } catch (_) {
      say("Pořadí se nepodařilo uložit. Obnov stránku a zkus to znovu.");
    } finally {
      pending = false;
    }
  };
  list.addEventListener("dragstart", (event) => {
    const row = event.target.closest("[data-mailbox-id]");
    if (!row) return;
    dragged = row;
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", row.dataset.mailboxId);
    }
    row.classList.add("is-dragging");
  });
  list.addEventListener("dragover", (event) => {
    if (!dragged) return;
    const over = event.target.closest("[data-mailbox-id]");
    if (!over || over === dragged) return;
    event.preventDefault();
    const { top, height } = over.getBoundingClientRect();
    list.insertBefore(dragged, event.clientY < top + height / 2 ? over : over.nextSibling);
  });
  list.addEventListener("drop", (event) => {
    if (!dragged) return;
    event.preventDefault();
    dragged.classList.remove("is-dragging");
    dragged = null;
    void save();
  });
  list.addEventListener("dragend", () => {
    if (dragged) {
      dragged.classList.remove("is-dragging");
      dragged = null;
    }
  });
  list.addEventListener("keydown", (event) => {
    if (!["ArrowUp", "ArrowDown"].includes(event.key)) return;
    if (!event.target.matches(".ema-mail-draghandle")) return;
    const row = event.target.closest("[data-mailbox-id]");
    if (!row) return;
    const sibling = event.key === "ArrowUp" ? row.previousElementSibling : row.nextElementSibling;
    if (!sibling || !sibling.matches("[data-mailbox-id]")) return;
    event.preventDefault();
    if (event.key === "ArrowUp") list.insertBefore(row, sibling);
    else list.insertBefore(row, sibling.nextSibling);
    event.target.focus();
    void save();
  });
})();
