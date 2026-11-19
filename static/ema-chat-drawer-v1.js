/* EMA – one server-backed conversation across dashboard and every page.
 * Text-only rendering, scoped to signed-in user; no credentials in JS.
 */
(() => {
  "use strict";
  const drawer = document.querySelector("[data-ema-chat-drawer]");
  if (!drawer) return;
  const toggle = document.querySelector("[data-ema-chat-open]");
  const closeButton = drawer.querySelector("[data-ema-chat-close]");
  const backdrop = document.querySelector("[data-ema-chat-backdrop]");
  const picker = drawer.querySelector("[data-ema-chat-threads]");
  const list = drawer.querySelector("[data-ema-chat-messages]");
  const form = drawer.querySelector("[data-ema-chat-form]");
  const input = drawer.querySelector("[data-ema-chat-input]");
  const sendButton = drawer.querySelector("[data-ema-chat-send]");
  const status = drawer.querySelector("[data-ema-chat-status]");
  const newButton = drawer.querySelector("[data-ema-chat-new]");
  const csrf = drawer.dataset.csrf;
  let current = null;
  let busy = false;
  let engineReady = false;
  const storedDraft = "ema:assistant:unsent";
  try { input.value = sessionStorage.getItem(storedDraft) || ""; } catch (_) {}
  input.addEventListener("input", () => {
    try { sessionStorage.setItem(storedDraft, input.value); } catch (_) {}
  });
  function setBusy(value) {
    busy = value;
    sendButton.disabled = value || !engineReady;
    newButton.disabled = value;
    picker.disabled = value;
    input.disabled = value;
  }
  function notice(message) { status.textContent = message || ""; }
  function bubble(role, text, date) {
    const article = document.createElement("article");
    article.className = "ema-global-chat-bubble " + (role === "user" ? "user" : "assistant");
    const header = document.createElement("small");
    header.textContent = (role === "user" ? "Ty" : "Ema") + (date ? " · " + new Date(date).toLocaleString("cs-CZ") : "");
    const content = document.createElement("div");
    content.textContent = text || "";
    article.append(header, content);
    list.append(article);
    list.scrollTop = list.scrollHeight;
  }
  async function server(url, formData) {
    const options = {credentials: "same-origin", headers: {"Accept": "application/json"}};
    if (formData) {
      options.method = "POST";
      options.headers["X-CSRF-Token"] = csrf;
      options.body = formData;
    }
    const response = await fetch(url, options);
    let payload = null;
    try { payload = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(payload?.error || "Požadavek se nepodařilo dokončit (HTTP " + response.status + ").");
    return payload;
  }
  async function loadThread(id) {
    if (!id) { current = null; list.textContent = "Začni novým rozhovorem."; return; }
    const value = await server("/assistant/threads/" + encodeURIComponent(id));
    current = value.thread.id;
    list.replaceChildren();
    value.messages.forEach(item => bubble(item.role, item.text, item.created_at));
    if (!value.messages.length) list.textContent = "Nový rozhovor. Na čem budeme pracovat?";
  }
  async function loadHistory(preferred = null) {
    const data = await server("/assistant/threads");
    picker.replaceChildren();
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "Nový rozhovor";
    picker.append(blank);
    for (const item of data.threads) {
      const opt = document.createElement("option");
      opt.value = String(item.id);
      opt.textContent = item.title.slice(0, 120) + (item.project_id ? " · projekt" : "");
      picker.append(opt);
    }
    const chosen = preferred || current || data.threads[0]?.id || null;
    picker.value = chosen ? String(chosen) : "";
    engineReady = Boolean(data.ready);
    if (!engineReady) {
      notice("AI Engine zatím není ověřen v Superadminu.");
    } else {
      notice("");
    }
    sendButton.disabled = busy || !engineReady;
    await loadThread(chosen);
  }
  function close() {
    drawer.classList.remove("open");
    drawer.setAttribute("aria-hidden", "true");
    toggle.setAttribute("aria-expanded", "false");
    backdrop.hidden = true;
    document.body.classList.remove("ema-chat-drawer-open");
    toggle.focus();
  }
  async function open() {
    drawer.classList.add("open");
    drawer.setAttribute("aria-hidden", "false");
    toggle.setAttribute("aria-expanded", "true");
    backdrop.hidden = false;
    document.body.classList.add("ema-chat-drawer-open");
    notice("Načítám...");
    try { await loadHistory(); } catch (_) { notice("Historii nyní nelze načíst."); }
    input.focus();
  }
  toggle.addEventListener("click", () => drawer.classList.contains("open") ? close() : open());
  closeButton.addEventListener("click", close);
  backdrop.addEventListener("click", close);
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && drawer.classList.contains("open")) close();
  });
  picker.addEventListener("change", async () => {
    if (busy) return;
    notice("");
    try { await loadThread(picker.value); } catch (_) { notice("Rozhovor není dostupný."); }
  });
  newButton.addEventListener("click", async () => {
    if (busy) return;
    setBusy(true);
    notice("Zakládám rozhovor...");
    const form = new FormData();
    // Current project is used only when page is explicitly in that context.
    form.append("project_id", drawer.dataset.project || "");
    try {
      const data = await server("/assistant/threads", form);
      current = data.id;
      await loadHistory(current);
      input.focus();
    } catch (error) { notice(error.message); }
    finally { setBusy(false); }
  });
  form.addEventListener("submit", async e => {
    e.preventDefault();
    if (busy || !input.value.trim()) return;
    const question = input.value.trim();
    setBusy(true);
    notice("Ema připravuje odpověď...");
    const nonce = "ema-" + (crypto.randomUUID ? crypto.randomUUID() : Date.now() + "-" + Math.random().toString(36).slice(2));
    try {
      if (!current) {
        const fresh = new FormData();
        fresh.append("project_id", drawer.dataset.project || "");
        const created = await server("/assistant/threads", fresh);
        current = created.id;
      }
      const formData = new FormData();
      formData.append("thread_id", current);
      formData.append("body", question);
      formData.append("nonce", nonce);
      const answer = await server("/assistant/api/message", formData);
      bubble("user", question, new Date().toISOString());
      bubble("assistant", answer.answer, new Date().toISOString());
      input.value = "";
      try { sessionStorage.removeItem(storedDraft); } catch (_) {}
      await loadHistory(current);
      notice("Odpověď je uložená v historii.");
    } catch (error) {
      notice(error.message + " Při nejistém výsledku neposílej stejný požadavek automaticky znovu.");
    } finally { setBusy(false); }
  });
})();
