/* EMA V1.3: durable mailbox ordering and resizeable desktop folder pane.
   Only layout preferences (never message content) are saved client-side. */
(() => {
  "use strict";
  const list = document.getElementById("ema-mailbox-sort-list");
  const info = document.getElementById("ema-mail-order-status");
  const say = (text) => { if (info) info.textContent = text; };
  if (list) {
    const items = () => Array.from(list.querySelectorAll(":scope > [data-mailbox-id]"));
    const ids = () => items().map(row => Number(row.dataset.mailboxId));
    let dragged = null, queued = false, sending = false;
    let latest = ids().join(",");
    async function save() {
      queued = true;
      if (sending) return;
      sending = true;
      // Serialize requests. A drag made while the first request is in flight
      // must still be sent after it, never silently discarded.
      while (queued) {
        queued = false;
        const snapshot = ids();
        say("Ukládám pořadí schránek…");
        let succeeded = false;
        try {
          const response = await fetch(list.dataset.orderUrl, {
            method: "POST", credentials: "same-origin", cache: "no-store",
            headers: {"Content-Type":"application/json",
                      "X-CSRF-Token":list.dataset.csrf,
                      "Accept":"application/json"},
            body: JSON.stringify({ids:snapshot})
          });
          const data = await response.json();
          if (!response.ok || data.ok !== true ||
              JSON.stringify(data.ids) !== JSON.stringify(snapshot)) {
            throw Error("Server nepotvrdil pořadí schránek.");
          }
          latest = snapshot.join(",");
          succeeded = true;
          say(queued ? "Ukládám další změnu…" : "Pořadí schránek uloženo na serveru.");
        } catch (error) {
          say((error.message || "Uložení selhalo") +
              " Pořadí není potvrzené, po obnovení se může změnit.");
          // Do not issue concurrent retries; user can deliberately reorder again.
        }
        if (succeeded && !queued && ids().join(",") !== latest) queued = true;
      }
      sending = false;
    }
    list.addEventListener("dragstart", event => {
      const row = event.target.closest("[data-mailbox-id]");
      if (!row) return;
      dragged = row;
      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain",row.dataset.mailboxId);
      }
      row.classList.add("is-dragging");
    });
    list.addEventListener("dragover", event => {
      if (!dragged) return;
      const over = event.target.closest("[data-mailbox-id]");
      if (!over || over === dragged) return;
      event.preventDefault();
      const {top,height}=over.getBoundingClientRect();
      list.insertBefore(dragged,event.clientY < top+height/2 ? over : over.nextSibling);
    });
    list.addEventListener("drop", event => {
      if (!dragged) return;
      event.preventDefault();
      dragged.classList.remove("is-dragging"); dragged=null;
      void save();
    });
    list.addEventListener("dragend", () => {
      if (dragged) {dragged.classList.remove("is-dragging");dragged=null;}
    });
    list.addEventListener("keydown", event => {
      if (!["ArrowUp","ArrowDown"].includes(event.key) ||
          !event.target.matches(".ema-mail-draghandle")) return;
      const row = event.target.closest("[data-mailbox-id]");
      const sibling = event.key === "ArrowUp" ?
        row?.previousElementSibling : row?.nextElementSibling;
      if (!sibling?.matches("[data-mailbox-id]")) return;
      event.preventDefault();
      if (event.key === "ArrowUp") list.insertBefore(row,sibling);
      else list.insertBefore(row,sibling.nextSibling);
      event.target.focus();
      void save();
    });
  }

  const hub = document.querySelector(".ema-mail-hub");
  const separator = document.getElementById("ema-mail-pane-resizer");
  if (!hub || !separator) return;
  const key = "ema.mail.sidebar-width.v13:" + (hub.dataset.userId || "anonymous");
  const minWidth = 205;
  const maxWidth = () => Math.max(minWidth,Math.min(600,Math.round(hub.clientWidth * .48)));
  function applied(width) {
    return Math.min(maxWidth(),Math.max(minWidth,Math.round(width)));
  }
  function setWidth(width,persist=false) {
    const fixed = applied(width);
    hub.style.setProperty("--ema-mail-pane-width",fixed+"px");
    separator.setAttribute("aria-valuenow",String(fixed));
    if (persist) {
      try {localStorage.setItem(key,String(fixed));} catch(_) { /* optional */ }
    }
  }
  let stored = 255;
  try { stored=Number(localStorage.getItem(key)) || 255; } catch(_) {}
  setWidth(stored);
  let start = null;
  separator.addEventListener("pointerdown", event => {
    if (event.pointerType === "touch" || window.matchMedia("(max-width:760px)").matches) return;
    event.preventDefault();
    start = {x:event.clientX,width:separator.getBoundingClientRect().left -
      hub.getBoundingClientRect().left};
    separator.setPointerCapture(event.pointerId);
    separator.classList.add("is-resizing");
  });
  separator.addEventListener("pointermove", event => {
    if (!start) return;
    setWidth(start.width + event.clientX-start.x);
  });
  function stop() {
    if (!start) return;
    const width=parseInt(getComputedStyle(hub).getPropertyValue("--ema-mail-pane-width"),10);
    start=null;
    separator.classList.remove("is-resizing");
    if (Number.isFinite(width)) setWidth(width,true);
  }
  separator.addEventListener("pointerup",stop);
  separator.addEventListener("pointercancel",stop);
  separator.addEventListener("keydown",event => {
    if (!["ArrowLeft","ArrowRight","Home"].includes(event.key)) return;
    event.preventDefault();
    const width=parseInt(getComputedStyle(hub).getPropertyValue("--ema-mail-pane-width"),10)||255;
    setWidth(event.key==="Home" ? 255 : width+(event.key==="ArrowRight"?20:-20),true);
  });
  separator.addEventListener("dblclick",()=>setWidth(255,true));
  window.addEventListener("resize",()=>{
    const width=parseInt(getComputedStyle(hub).getPropertyValue("--ema-mail-pane-width"),10)||255;
    setWidth(width);
  });
})();