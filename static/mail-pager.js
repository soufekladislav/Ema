/* EMA mail: IMAP-backed 50-header pages; scroll only inside the message pane. */
(() => {
  "use strict";
  const panel = document.getElementById("ema-mail-scrollpanel");
  if (!panel) return;
  const container = document.getElementById("ema-mail-items");
  const loader = document.getElementById("ema-mail-loader");
  const folderForm = document.getElementById("ema-mail-folder-select-form");
  const folderSelect = document.getElementById("ema-folder-select");
  if (folderForm && folderSelect) folderSelect.addEventListener("change", () => folderForm.submit());

  const mailbox = Number(panel.dataset.mailboxId || 0);
  const folder = Number(panel.dataset.folderId || 0);
  const remote = mailbox > 0 && folder > 0;
  const csrf = panel.dataset.csrf;
  let hasMore = panel.dataset.hasMore === "true";
  let cursor = Number(panel.dataset.nextCursor || 0) || null;
  let offset = container.querySelectorAll("[data-mail-id]").length;
  let busy = false;
  let failed = false;
  let refreshRequired = remote;
  const say = (message) => { loader.textContent = message; };
  const addRows = (html, replace) => {
    if (replace) container.innerHTML = html;
    else {
      const area = document.createElement("div");
      area.innerHTML = html;
      const existing = new Set(Array.from(container.querySelectorAll("[data-mail-id]"))
        .map((node) => node.dataset.mailId));
      Array.from(area.children).forEach((node) => {
        if (!existing.has(node.dataset.mailId)) {
          container.appendChild(node);
          existing.add(node.dataset.mailId);
        }
      });
    }
  };
  const updateFolders = (folders) => {
    if (!folderSelect || !Array.isArray(folders)) return;
    const known = new Set(Array.from(folderSelect.options).map((opt) => opt.value));
    folders.forEach((item) => {
      if (!Number.isInteger(item.id) || known.has(String(item.id))) return;
      const option = document.createElement("option");
      option.value = String(item.id);
      option.textContent = String(item.name);
      folderSelect.add(option);
      known.add(option.value);
    });
  };
  const load = async (first = false) => {
    if (busy || failed) return;
    if (!first && !hasMore) return;
    busy = true;
    say(first ? "Načítám posledních 50 e-mailů z IMAP…" : "Načítám dalších až 50 zpráv…");
    try {
      let response;
      if (remote) {
        response = await fetch(panel.dataset.pageUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify({ folder_id: folder, before_uid: first ? null : cursor }),
        });
      } else {
        const url = new URL(panel.dataset.aggregateUrl, window.location.href);
        url.searchParams.set("offset", String(offset));
        response = await fetch(url, { credentials: "same-origin" });
      }
      const data = await response.json();
      if (!response.ok) throw Error(data.error || "Zprávy se nepodařilo načíst");
      addRows(data.html || "", first);
      hasMore = Boolean(data.has_more);
      if (remote) {
        cursor = Number(data.next_cursor) || null;
        updateFolders(data.folders);
        refreshRequired = false;
      } else offset = Number(data.next_offset) || offset;
      say(hasMore ? "Posuň seznam dolů pro dalších 50 zpráv." : (
        container.children.length ? "Konec dostupných zpráv." : "Složka neobsahuje zprávy."
      ));
    } catch (error) {
      failed = true;
      say(error.message || "Synchronizace selhala. Obnov stránku a zkus to znovu.");
    } finally {
      busy = false;
    }
  };
  panel.addEventListener("scroll", () => {
    if (refreshRequired || busy || failed || !hasMore) return;
    if (panel.scrollTop + panel.clientHeight >= panel.scrollHeight - 230) void load();
  }, { passive: true });
  if (remote) void load(true);
  else if (hasMore && panel.scrollHeight <= panel.clientHeight + 60) void load();
})();
