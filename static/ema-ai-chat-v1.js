/* EMA shared chat: one server-owned history for home and every page.
   No API key or customer data ever persists in localStorage. */
(() => {
  'use strict';
  const widget = document.querySelector('[data-ema-ai-widget]');
  if (!widget) return;
  const openBtn = widget.querySelector('[data-ema-chat-open]');
  const drawer = widget.querySelector('[data-ema-chat-drawer]');
  const closeBtn = widget.querySelector('[data-ema-chat-close]');
  const selector = widget.querySelector('[data-ema-chat-project]');
  const historyList = widget.querySelector('[data-ema-chat-thread-list]');
  const messages = widget.querySelector('[data-ema-chat-messages]');
  const form = widget.querySelector('[data-ema-chat-form]');
  const input = form.querySelector('textarea');
  const submit = form.querySelector('[type="submit"]');
  const archiveBtn = widget.querySelector('[data-ema-chat-archive]');
  const newBtn = widget.querySelector('[data-ema-chat-new]');
  const status = widget.querySelector('[data-ema-chat-status]');
  const csrf = drawer.dataset.csrf || '';
  let activeThread = null, busy = false, started = false;

  const urlFor = (path) => path;
  async function api(path, options = {}) {
    const headers = {'Accept': 'application/json', ...options.headers};
    if (options.method === 'POST') headers['X-CSRF-Token'] = csrf;
    const response = await fetch(urlFor(path), {
      credentials: 'same-origin', cache: 'no-store',
      ...options, headers
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(data?.error || 'Spojení se serverem selhalo. Zkontroluj historii před opakováním.');
    }
    return data;
  }
  function tell(text, error=false) {
    status.textContent = text || '';
    status.classList.toggle('error', !!error);
  }
  function bubble(role, content, time) {
    const item = document.createElement('article');
    item.className = 'ema-ai-bubble '+(role==='user'?'from-me':'from-ema');
    const name = document.createElement('strong');
    name.textContent = role === 'user' ? 'Ty' : 'Ema';
    const body = document.createElement('div');
    body.textContent = String(content||'');
    item.append(name, body);
    if (time) {
      const date = document.createElement('small');
      const d = new Date(time);
      date.textContent = Number.isNaN(d.getTime()) ? '' : d.toLocaleString('cs-CZ');
      item.append(date);
    }
    messages.append(item);
    messages.scrollTop = messages.scrollHeight;
  }
  function clearMessages() {
    messages.replaceChildren();
    const greet=document.createElement('p');
    greet.className='small muted';
    greet.textContent='Nová konverzace. Ema nic sama neodešle ani nezmění bez tvého schválení.';
    messages.append(greet);
  }
  async function chooseThread(id) {
    if (busy) return;
    tell('');
    try {
      const data=await api('/assistant/threads/'+id);
      activeThread=data.thread.id;
      messages.replaceChildren();
      for(const msg of data.messages) bubble(msg.role,msg.body,msg.created_at);
      archiveBtn.hidden=false;
      for(const b of historyList.querySelectorAll('button[data-id]')){
        b.classList.toggle('active', Number(b.dataset.id)===activeThread);
      }
    }catch(err){tell(err.message,true);}
  }
  async function loadThreads(selectLatest=true) {
    const params=new URLSearchParams();
    if(selector.value)params.set('project_id',selector.value);
    try {
      const data=await api('/assistant/threads?'+params.toString());
      historyList.replaceChildren();
      for (const thread of data.threads){
        const btn=document.createElement('button');
        btn.type='button';btn.dataset.id=String(thread.id);btn.textContent=thread.title;
        btn.title=thread.title;
        btn.addEventListener('click',()=>chooseThread(thread.id));
        historyList.append(btn);
      }
      if(selectLatest && data.threads.length)await chooseThread(data.threads[0].id);
      else if (!data.threads.length) {activeThread=null;archiveBtn.hidden=true;clearMessages();}
    }catch(err){tell(err.message,true);}
  }
  function newThread(){
    activeThread=null;
    archiveBtn.hidden=true;
    clearMessages();
    tell('');
    historyList.querySelectorAll('button').forEach(b=>b.classList.remove('active'));
    input.focus();
  }
  async function open() {
    drawer.hidden=false;
    widget.classList.add('open');
    openBtn.setAttribute('aria-expanded','true');
    if(!started){started=true;await loadThreads();}
    input.focus();
  }
  function close(){
    drawer.hidden=true;
    widget.classList.remove('open');
    openBtn.setAttribute('aria-expanded','false');
    openBtn.focus();
  }
  openBtn.addEventListener('click',()=>drawer.hidden?open():close());
  closeBtn.addEventListener('click',close);
  newBtn.addEventListener('click',newThread);
  selector.addEventListener('change',()=>{activeThread=null;loadThreads();});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!drawer.hidden){e.preventDefault();close();}});
  input.addEventListener('keydown',e=>{
    if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();form.requestSubmit();}
  });
  form.addEventListener('submit',async e=>{
    e.preventDefault();
    if(busy) return;
    const question=input.value.trim();
    if(!question) return;
    busy=true;submit.disabled=true;
    tell('Ema přemýšlí…');
    // Every click creates ONE unique request. On uncertain timeout never re-send.
    const nonce = (window.crypto?.randomUUID?.() || (
      Date.now().toString(36) + Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2)
    )).replace(/[^A-Za-z0-9_-]/g,'');
    const payload=new FormData();
    payload.set('body',question);
    payload.set('project_id',selector.value);
    payload.set('thread_id',activeThread==null?'':String(activeThread));
    payload.set('nonce',nonce);
    try {
      const result=await api('/assistant',{method:'POST',body:payload});
      input.value='';
      activeThread=result.thread.id;
      if(messages.querySelector('.muted')) messages.replaceChildren();
      bubble('user',question);
      bubble('assistant',result.answer);
      tell('Odpověď uložena do historie.');
      await loadThreads(false);
      archiveBtn.hidden=false;
    }catch(err){
      // Preserve typed question. If request reached the server, attempt is recorded;
      // the same request must not be retried automatically after failure.
      tell(err.message + ' Neodesílej automaticky znovu.',true);
      await loadThreads(false).catch(()=>{});
    }finally{busy=false;submit.disabled=false;}
  });
  archiveBtn.addEventListener('click',async ()=>{
    if(!activeThread||busy) return;
    if(!window.confirm('Archivovat tuto konverzaci? Zprávy se nemažou.'))return;
    try {
      await api('/assistant/threads/'+activeThread+'/archive',{method:'POST'});
      newThread();
      await loadThreads(false);
      tell('Konverzace byla archivována.');
    }catch(err){tell(err.message,true);}
  });
  const homeArchive=document.querySelector('[data-ema-archive-thread]');
  if(homeArchive) homeArchive.addEventListener('click',async ()=>{
    if(!window.confirm('Archivovat tuto konverzaci?')) return;
    const id=homeArchive.dataset.emaArchiveThread;
    try{
      await api('/assistant/threads/'+id+'/archive',{method:'POST'});
      window.location.href='/';
    }catch(err){window.alert(err.message);}
  });
})();
