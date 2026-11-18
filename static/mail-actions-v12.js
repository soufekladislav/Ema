/* EMA Mail: one set of server operations for mouse, touch, keyboard and DnD. */
(() => {
  "use strict";
  const items = document.getElementById("ema-mail-items");
  const menu = document.getElementById("ema-mail-context");
  const dialog = document.getElementById("ema-mail-folder-dialog");
  const targets = document.getElementById("ema-mail-target-list");
  const chooserCancel = document.getElementById("ema-mail-folder-cancel");
  const status = document.getElementById("ema-mail-operations-status");
  const bulk = document.getElementById("ema-mail-bulk-form");
  const bulkMove = document.getElementById("ema-bulk-move-button");
  const panel = document.getElementById("ema-mail-scrollpanel");
  if (!items || !menu || !dialog || !targets || !panel) return;

  const csrf = panel.dataset.csrf;
  let activeRow = null;
  let dragRow = null;
  let longPress = null;
  let longStart = null;
  let targetSelection = [];
  const inform = (text) => {
    if (status) status.textContent = text;
  };
  const rows = () => Array.from(items.querySelectorAll(".ema-mail-message-row"));
  function hideMenu() { menu.hidden = true; }
  function openMenu(row, x, y) {
    if (!row || !row.querySelector(".ema-mail-more")) return;
    activeRow = row;
    menu.hidden = false;
    const read = row.dataset.isRead === "true";
    const starred = row.dataset.starred === "true";
    menu.querySelector('[data-ema-mail-action="toggle-read"]').textContent =
      read ? "Označit jako nepřečtené" : "Označit jako přečtené";
    menu.querySelector('[data-ema-mail-action="toggle-star"]').textContent =
      starred ? "Odebrat příznak" : "Označit příznakem";
    const width = menu.offsetWidth || 230, height = menu.offsetHeight || 220;
    menu.style.left = Math.max(6, Math.min(x, innerWidth - width - 8)) + "px";
    menu.style.top = Math.max(6, Math.min(y, innerHeight - height - 8)) + "px";
    menu.querySelector("button")?.focus();
  }
  items.addEventListener("contextmenu", (event) => {
    const row = event.target.closest(".ema-mail-message-row");
    if (!row || !row.querySelector(".ema-mail-more")) return;
    event.preventDefault(); openMenu(row, event.clientX, event.clientY);
  });
  items.addEventListener("click", (event) => {
    const button = event.target.closest(".ema-mail-more");
    if (!button) return;
    event.preventDefault();event.stopPropagation();
    const pos = button.getBoundingClientRect();
    openMenu(button.closest(".ema-mail-message-row"), pos.left, pos.bottom + 4);
  });
  items.addEventListener("keydown", (event) => {
    const row = event.target.closest(".ema-mail-message-row");
    if (row && (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10"))) {
      event.preventDefault();
      const pos = row.getBoundingClientRect();
      openMenu(row, pos.left + 20, pos.top + 24);
    }
  });
  const clearLong = () => {
    if (longPress !== null) window.clearTimeout(longPress);
    longPress = null;longStart = null;
  };
  items.addEventListener("pointerdown", (event) => {
    if (event.pointerType === "mouse" || event.target.closest("input,button")) return;
    const row = event.target.closest(".ema-mail-message-row");
    if (!row || !row.querySelector(".ema-mail-more")) return;
    clearLong();
    longStart = [event.clientX, event.clientY];
    longPress = window.setTimeout(() => {
      openMenu(row, event.clientX, event.clientY);
      longPress = null;
    }, 550);
  });
  items.addEventListener("pointermove", (event) => {
    if (longStart && Math.hypot(event.clientX-longStart[0], event.clientY-longStart[1]) > 12) clearLong();
  });
  for (const type of ["pointerup","pointercancel","scroll"]) {
    items.addEventListener(type, clearLong, {passive:true});
  }
  document.addEventListener("click", (event) => {
    if (!event.target.closest("#ema-mail-context,.ema-mail-more")) hideMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {hideMenu();if (dialog.open) dialog.close();}
  });

  async function serverAction(row, action, targetFolderId) {
    const move = ["trash","archive","move"].includes(action);
    const url = move ? row.dataset.moveUrl : row.dataset.flagUrl;
    const body = new URLSearchParams({ action });
    if (targetFolderId) body.set("target_folder_id", String(targetFolderId));
    inform("Odesílám změnu na IMAP server…");
    const response = await fetch(url, {
      method:"POST", credentials:"same-origin", cache:"no-store",
      headers:{"X-CSRF-Token":csrf, "Accept":"application/json",
               "Content-Type":"application/x-www-form-urlencoded;charset=UTF-8"},
      body:body.toString()
    });
    const result = await response.json().catch(() => ({error:"Neplatná odpověď serveru"}));
    if (!response.ok || result.ok !== true) {
      throw Error(result.error || "Server změnu nepotvrdil");
    }
    if (move) {
      inform(result.message || "Zpráva byla přesunuta.");
      if (result.pending_cleanup) {
        window.alert(result.message || "Server ponechal originál označený ke smazání.");
      }
      window.location.reload();return;
    }
    row.dataset.isRead = String(result.read);
    row.dataset.starred = String(result.starred);
    row.classList.toggle("is-read",result.read);
    row.classList.toggle("is-unread",!result.read);
    row.classList.toggle("is-starred",result.starred);
    inform("Změna potvrzena na IMAP serveru.");
  }

  async function chooseFolder(chosen, allSelected) {
    hideMenu();
    if (!chosen || !chosen.length) return;
    const first = chosen[0];
    if (chosen.some(row => row.dataset.mailboxId !== first.dataset.mailboxId)) {
      inform("Přesun více zpráv je možný jen v jedné poštovní schránce.");
      return;
    }
    targetSelection = allSelected ? chosen : [first];
    targets.replaceChildren();
    const wait = document.createElement("p");
    wait.textContent = "Načítám serverové složky…";
    targets.append(wait);
    if (!dialog.open) dialog.showModal();
    try {
      const response = await fetch(first.dataset.targetsUrl,{credentials:"same-origin",cache:"no-store"});
      if (!response.ok) throw Error("Server odmítl seznam složek");
      const data = await response.json();
      if (String(data.mailbox_id) !== first.dataset.mailboxId) throw Error("Neplatná schránka");
      targets.replaceChildren();
      for (const folder of data.folders || []) {
        if (targetSelection.some(row => row.dataset.folderId === String(folder.id))) continue;
        const button = document.createElement("button");
        button.type = "button";button.className = "ema-mail-target-option";
        button.textContent = folder.name;
        button.addEventListener("click", async () => {
          dialog.close();
          try {
            if (targetSelection.length === 1 && !allSelected) {
              await serverAction(targetSelection[0],"move",folder.id);
            } else {
              const existing = bulk.querySelector('input[name="target_folder_id"]');
              existing?.remove();
              const input = document.createElement("input");
              input.type = "hidden";input.name = "target_folder_id";input.value = String(folder.id);
              bulk.append(input);
              const action = document.createElement("input");
              action.type="hidden";action.name="action";action.value="move";
              bulk.append(action);
              bulk.requestSubmit();
            }
          } catch (error) {inform(error.message);alert(error.message);}
        });
        targets.append(button);
      }
      if (!targets.children.length) targets.textContent = "Žádná vhodná cílová složka.";
    } catch(error) {targets.textContent = error.message || "Seznam složek nelze načíst";}
  }
  menu.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-ema-mail-action]");
    if (!button || !activeRow) return;
    const row = activeRow;
    const command = button.dataset.emaMailAction;
    hideMenu();
    if (command === "move") {await chooseFolder([row],false);return;}
    let action = command;
    if (command === "toggle-read") action = row.dataset.isRead === "true" ? "unread":"read";
    if (command === "toggle-star") action = row.dataset.starred === "true" ? "unstar":"star";
    try {await serverAction(row,action);}
    catch(error){inform(error.message);alert(error.message);}
  });
  chooserCancel?.addEventListener("click",() => dialog.close());
  bulkMove?.addEventListener("click",() => {
    const checked = rows().filter(row => row.querySelector(".ema-mail-select:checked"));
    if (!checked.length) {inform("Nejprve vyberte zprávy.");return;}
    if (checked.length > 50) {inform("Nejvýše 50 zpráv.");return;}
    void chooseFolder(checked,true);
  });

  items.addEventListener("dragstart",(event)=>{
    const row=event.target.closest(".ema-mail-message-row");
    if (!row || row.draggable !== true) return;
    dragRow=row;
    event.dataTransfer?.setData("application/x-ema-message",String(row.dataset.mailId));
    if (event.dataTransfer) event.dataTransfer.effectAllowed="move";
  });
  items.addEventListener("dragend",()=>{dragRow=null;document.querySelectorAll(".ema-mail-folder-drop").forEach(el=>el.classList.remove("ema-mail-folder-drop"));});
  document.querySelectorAll(".ema-mail-folder[data-folder-id]").forEach(folder=>{
    const valid = () => dragRow &&
      folder.dataset.folderMailboxId === dragRow.dataset.mailboxId &&
      folder.dataset.folderId !== dragRow.dataset.folderId;
    folder.addEventListener("dragover",(event)=>{
      if(!valid())return;
      event.preventDefault();
      folder.classList.add("ema-mail-folder-drop");
      if(event.dataTransfer) event.dataTransfer.dropEffect="move";
    });
    folder.addEventListener("dragleave",()=>folder.classList.remove("ema-mail-folder-drop"));
    folder.addEventListener("drop",async(event)=>{
      folder.classList.remove("ema-mail-folder-drop");
      if(!valid())return;
      event.preventDefault();
      const row=dragRow;dragRow=null;
      try {await serverAction(row,"move",Number(folder.dataset.folderId));}
      catch(error){inform(error.message);alert(error.message);}
    });
  });
})();