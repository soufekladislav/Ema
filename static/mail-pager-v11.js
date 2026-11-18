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
        const label = document.querySelector('[data-mailbox-count="' + mailbox + '"]');
        if (label && Array.isArray(data.indexed_count)) {
          label.textContent = data.indexed_count[0] + " nepřečtených / " +
            data.indexed_count[1] + " načtených" +
            (data.server_total != null ? " · IMAP celkem " + data.server_total : "");
        }
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

  // The combined inbox is an indexed view, not a server mailbox.
  // Refresh one included IMAP inbox at a time; never fetch full MIME bodies.
  const included = (panel.dataset.includedBoxIds || "").split(",")
    .map((value) => Number(value)).filter((value) => Number.isInteger(value) && value > 0);
  let refreshing = false;
  const refreshAll = async () => {
    if (remote || refreshing || document.hidden || !included.length) return;
    refreshing = true;
    let updated = 0;
    let errors = [];
    say("Aktualizuji příchozí zprávy ze " + included.length + " schránek…");
    try {
      for (const id of included) {
        if (document.hidden) break;
        try {
          const response = await fetch(panel.dataset.aggregateSyncUrl, {
            method: "POST", credentials: "same-origin", cache: "no-store",
            headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
            body: JSON.stringify({ box_id: id }),
          });
          const result = await response.json();
          if (!response.ok) throw Error(result.error || "IMAP synchronizace selhala");
          updated += 1;
          const countLabel = document.querySelector('[data-mailbox-count="' + id + '"]');
          if (countLabel) {
            countLabel.textContent = result.unread + " nepřečtených · " + result.indexed +
              " v přehledu" + (result.server_total != null ? " · IMAP " + result.server_total : "");
          }
        } catch (error) {
          errors.push("Schránka " + id + ": " + (error.message || "chyba synchronizace"));
        }
      }
      const url = new URL(panel.dataset.aggregateUrl, window.location.href);
      url.searchParams.set("offset", "0");
      const response = await fetch(url, { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw Error("Nedaří se načíst aktualizovaný souhrn");
      const result = await response.json();
      const temp = document.createElement("div");
      temp.innerHTML = result.html || "";
      const existing = new Set(Array.from(container.querySelectorAll("[data-mail-id]"))
        .map((node) => node.dataset.mailId));
      const fresh = Array.from(temp.children).filter((node) => node.dataset.mailId &&
        !existing.has(node.dataset.mailId));
      const beforeHeight = panel.scrollHeight;
      // Prepend in reverse to preserve newest-first order from the server.
      for (let i = fresh.length - 1; i >= 0; i -= 1) container.prepend(fresh[i]);
      if (panel.scrollTop > 60) panel.scrollTop += panel.scrollHeight - beforeHeight;
      offset += fresh.length;
      if (result.has_more) hasMore = true;
      say("Souhrn: aktualizováno " + updated + "/" + included.length +
          " schránek, " + fresh.length + " nových zpráv." +
          (errors.length ? " Chyby: " + errors.slice(0, 2).join("; ") : ""));
    } catch (error) {
      say(error.message || "Souhrn se nepodařilo aktualizovat.");
    } finally {
      refreshing = false;
    }
  };
  if (!remote && included.length) {
    void refreshAll();
    window.setInterval(() => { void refreshAll(); }, 120000);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) void refreshAll();
    });
  }
})();
