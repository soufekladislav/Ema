/* EMA Mail V1 — mobile navigation, inline preview and CRM contact suggestions.
 * Never stores mail content or auth information in local/session storage.
 */
(() => {
  "use strict";
  const appToggle = document.getElementById("ema-mobile-nav-toggle");
  if (appToggle) appToggle.addEventListener("click", () => {
    const opened = document.body.classList.toggle("ema-appmenu-open");
    appToggle.setAttribute("aria-expanded", String(opened));
  });

  const foldersToggle = document.getElementById("ema-folder-drawer-toggle");
  if (foldersToggle) foldersToggle.addEventListener("click", () => {
    const opened = document.body.classList.toggle("ema-folder-pane-open");
    foldersToggle.setAttribute("aria-expanded", String(opened));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    document.body.classList.remove("ema-appmenu-open", "ema-folder-pane-open");
    if (foldersToggle) foldersToggle.setAttribute("aria-expanded", "false");
    if (appToggle) appToggle.setAttribute("aria-expanded", "false");
  });

  // Only folder view preferences (not mail bodies/tokens) are persisted in localStorage.
  // The IMAP hierarchy separator is provider-defined: "." or "/" are both common.
  const folderRoot = document.querySelector("[data-mail-folder-root]");
  if (folderRoot) {
    const prefKey = "ema-mail-folders-v1:" + folderRoot.dataset.mailFolderRoot;
    const entries = folderRoot.querySelector(".ema-mail-folder-entries");
    const prefGet = (key) => {
      try { return window.localStorage.getItem(prefKey + ":" + key); }
      catch (_) { return null; }
    };
    const prefSet = (key, value) => {
      try { window.localStorage.setItem(prefKey + ":" + key, value); }
      catch (_) { /* Private browsing/no storage: current view still works. */ }
    };
    const savedRoot = prefGet("root");
    if (savedRoot === "closed") folderRoot.open = false;
    folderRoot.addEventListener("toggle", () => {
      prefSet("root", folderRoot.open ? "open" : "closed");
    });
    if (entries) {
      const links = Array.from(entries.querySelectorAll(":scope > .ema-mail-folder"));
      links.forEach((link) => {
        const full = link.dataset.folderFullname || "";
        const separator = link.dataset.folderDelimiter || "/";
        if (!separator || !full.includes(separator)) return;
        const parts = full.split(separator).filter(Boolean);
        if (parts.length < 2) return;
        let parent = entries;
        for (let i = 0; i < parts.length - 1; i += 1) {
          const groupName = parts.slice(0, i + 1).join(separator);
          const key = "group:" + separator + ":" + groupName;
          let group = Array.from(parent.children).find((node) =>
            node.classList?.contains("ema-mail-folder-group") &&
            node.dataset.groupName === groupName);
          if (!group) {
            group = document.createElement("details");
            group.className = "ema-mail-folder-group";
            group.dataset.groupName = groupName;
            const summary = document.createElement("summary");
            summary.textContent = parts[i];
            const content = document.createElement("div");
            content.className = "ema-mail-folder-group-children";
            group.append(summary, content);
            group.open = prefGet(key) !== "closed";
            group.addEventListener("toggle", () => {
              prefSet(key, group.open ? "open" : "closed");
            });
            parent.appendChild(group);
          }
          parent = group.querySelector(".ema-mail-folder-group-children");
        }
        const title = link.querySelector("span");
        if (title) title.textContent = "▸ " + parts[parts.length - 1];
        parent.appendChild(link);
      });
    }
  }

  const items = document.getElementById("ema-mail-items");
  const bulk = document.getElementById("ema-mail-bulk-form");
  const selectAll = document.getElementById("ema-select-all");
  const selectedSummary = document.getElementById("ema-mail-selection-summary");
  const updateSelection = () => {
    if (!items || !bulk) return;
    const all = Array.from(items.querySelectorAll(".ema-mail-select"));
    const selected = all.filter((input) => input.checked);
    if (selectAll) {
      selectAll.indeterminate = selected.length > 0 && selected.length < all.length;
      selectAll.checked = selected.length > 0 && selected.length === all.length;
    }
    if (selectedSummary) selectedSummary.textContent = selected.length ? selected.length + " vybráno (max. 50)" : "";
    bulk.querySelectorAll("button[name='action']").forEach((button) => {
      button.disabled = !selected.length || selected.length > 50;
    });
  };
  if (selectAll && items) {
    selectAll.addEventListener("change", () => {
      items.querySelectorAll(".ema-mail-select").forEach((input, index) => {
        input.checked = selectAll.checked && index < 50;
      });
      updateSelection();
    });
    items.addEventListener("change", (event) => {
      if (event.target.matches(".ema-mail-select")) updateSelection();
    });
    if (bulk) bulk.addEventListener("submit", (event) => {
      if (items.querySelectorAll(".ema-mail-select:checked").length > 50) event.preventDefault();
    });
    updateSelection();
  }

  // Single inline preview, no browser caching. A normal Ctrl+Click still opens full detail.
  if (items) items.addEventListener("click", async (event) => {
    const imageButton = event.target.closest(".ema-quick-images");
    const link = event.target.closest(".ema-mail-quick-link");
    if (!imageButton && !(link && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey && event.button === 0)) return;
    event.preventDefault();
    const row = (imageButton || link).closest("[data-mail-id]");
    const slot = row?.querySelector(".ema-mail-inline-slot");
    if (!row || !slot) return;
    if (link && !slot.hidden) {
      slot.replaceChildren();
      slot.hidden = true;
      row.classList.remove("ema-mail-expanded");
      link.setAttribute("aria-expanded", "false");
      return;
    }
    // Remove prior preview including any iframe and remote images.
    items.querySelectorAll(".ema-mail-inline-slot").forEach((other) => {
      if (other !== slot) { other.replaceChildren(); other.hidden = true; }
    });
    items.querySelectorAll(".ema-mail-expanded").forEach((node) => {
      if (node !== row) {
        node.classList.remove("ema-mail-expanded");
        node.querySelector(".ema-mail-quick-link")?.setAttribute("aria-expanded", "false");
      }
    });
    slot.hidden = false;
    slot.textContent = "Načítám obsah přímo z IMAP…";
    const url = imageButton ? imageButton.dataset.imageUrl : link.dataset.previewUrl;
    try {
      const response = await fetch(url, { credentials: "same-origin", cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw Error(payload.error || "Náhled nelze načíst");
      slot.innerHTML = payload.html;
      row.classList.add("ema-mail-expanded", "is-read");
      row.classList.remove("is-unread");
      row.querySelector(".ema-mail-quick-link")?.setAttribute("aria-expanded", "true");
    } catch (error) {
      slot.textContent = error.message || "Náhled není dostupný. Otevři detail zprávy.";
    }
  });

  // CRM autocomplete is limited by backend ACL to contacts in sender mailbox's firm.
  const recipient = document.getElementById("ema-compose-to");
  const sender = document.getElementById("ema-from-box");
  const datalist = document.getElementById("ema-contact-datalist");
  if (recipient && sender && datalist) {
    let seq = 0;
    const suggest = async () => {
      const value = recipient.value.trim();
      if (value.length < 2 || value.includes(",") || value.includes(";")) {
        datalist.replaceChildren();
        return;
      }
      const mySeq = ++seq;
      const url = new URL(sender.dataset.suggestUrl, location.href);
      url.searchParams.set("box", sender.value);
      url.searchParams.set("q", value);
      try {
        const response = await fetch(url, { credentials: "same-origin", cache: "no-store" });
        if (!response.ok) return;
        const data = await response.json();
        if (seq !== mySeq) return;
        datalist.replaceChildren();
        (data.contacts || []).forEach((contact) => {
          const option = document.createElement("option");
          option.value = contact.email;
          option.label = contact.name;
          datalist.appendChild(option);
        });
      } catch (_) { datalist.replaceChildren(); }
    };
    recipient.addEventListener("input", suggest);
    sender.addEventListener("change", suggest);
  }
})();
