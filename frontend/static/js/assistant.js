/** Read-only assistant: transient conversation, safe DOM, explicit location consent. */
document.addEventListener('DOMContentLoaded', () => {
  const messages=document.getElementById('chat-messages');
  const form=document.getElementById('chat-form');
  const input=document.getElementById('chat-input');
  const submit=document.getElementById('chat-submit');
  if(!form || form.dataset.chatInitialized) return;
  form.dataset.chatInitialized='true';
  const csrf=document.getElementById('csrf_token').value;
  const workspace=document.querySelector('.assistant-container');
  const welcome=document.getElementById('assistant-welcome');
  const currentTitle=document.getElementById('current-chat-title');
  const statusLabel=document.getElementById('assistant-status');
  let readyStatus='MEMERIKSA';
  const history=[];
  let locationContext=null;
  function updateStatus(data) {if(data?.label){readyStatus=data.label;if(statusLabel)statusLabel.textContent=readyStatus;}}
  async function refreshStatus(){try{const r=await fetch('/assistant/status');if(r.ok)updateStatus(await r.json());}catch{readyStatus='Status AI belum dapat diperiksa';if(statusLabel)statusLabel.textContent=readyStatus;}}
  refreshStatus();
  window.addEventListener('pagehide',()=>{history.length=0;locationContext=null;});
  const mobile=window.matchMedia('(max-width:1023px)');
  function syncPanels() {
    document.querySelectorAll('.assistant-panel-details').forEach(panel=>{panel.open=!mobile.matches;});
  }
  syncPanels(); mobile.addEventListener('change',syncPanels);
  function fitViewport() {
    if (!mobile.matches || !window.visualViewport) return;
    const top=document.querySelector('.navbar').getBoundingClientRect().bottom;
    workspace.style.setProperty('--assistant-viewport-height',`${Math.max(240,window.visualViewport.height-top)}px`);
  }
  window.visualViewport?.addEventListener('resize',fitViewport); fitViewport();
  let busy=false;
  const maps=[];
  const pendingMaps=new Map();
  function el(tag, cls, text) { const n=document.createElement(tag); if(cls) n.className=cls; if(text) n.textContent=text; return n; }
  function row(text, user=false) {
    const follow = user || messages.scrollHeight-messages.scrollTop-messages.clientHeight < 80;
    if(welcome) welcome.hidden=true;
    workspace.classList.add('has-conversation');
    const r=el('div',`message-row ${user?'user-row':'assistant-row'}`);
    r.append(el('div','message-avatar',user?'Anda':'SW'));
    const bubble=el('div','message-bubble'); bubble.append(el('div','message-text',text)); r.append(bubble); messages.append(r);
    // Bound DOM and map resources; no durable chat storage.
    while(messages.children.length>40) {
      const first=messages.firstElementChild;
      pendingMaps.forEach((job,element)=>{if(first.contains(element)){job.cancel();pendingMaps.delete(element);}});
      maps.filter(m=>first.contains(m.getContainer())).forEach(m=>{m.remove();maps.splice(maps.indexOf(m),1);}); first.remove();
    }
    if (follow) messages.scrollTop=messages.scrollHeight;
    return bubble;
  }
  function setBusy(value) {busy=value;submit.disabled=value;if(statusLabel)statusLabel.textContent=value?'Asisten sedang menyiapkan jawaban...':readyStatus;form.setAttribute('aria-busy',String(value));document.querySelectorAll('.suggested-pill,.btn-location-action').forEach(b=>b.disabled=value);}
  async function request(url,payload,retry) {
    if(busy) return;
    setBusy(true);
    const typing=row('Asisten sedang menyiapkan jawaban...'); typing.classList.add('typing-indicator'); typing.prepend(el('span','spinner'));
    const controller=new AbortController(); const timeout=setTimeout(()=>controller.abort(),125000);
    try {
      const res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify(payload),signal:controller.signal});
      let data;
      try {data=await res.json();} catch {throw new Error('Respons server tidak tersedia. Muat ulang halaman jika sesi telah berakhir.');}
      if(!res.ok || !data.success) throw new Error(data.message || 'Permintaan gagal. Silakan coba kembali.');
      if(payload.message) {
        history.push({role:'user',content:payload.message},{role:'assistant',content:(data.intent==='MEMBERSHIP_SUMMARY'?'Lihat kepesertaan melalui akun warga.':data.message).slice(0,2000)});
        while(history.length>10 || history.reduce((n,m)=>n+m.content.length,0)>10000)history.shift();
        if(input.value.trim()===payload.message) {input.value='';input.style.height='';}
      }
      render(data);updateStatus(data.ai_status);
    } catch(error) {
      const b=row(error.name==='AbortError'?'Waktu permintaan habis. Silakan coba kembali.':error.message);
      b.classList.add('message-error'); b.setAttribute('role','alert');
      const button=el('button','btn btn-outline-primary','Coba lagi');button.type='button';button.addEventListener('click',()=>{if(!busy){b.parentElement.remove();retry();}});b.append(button);
    } finally {clearTimeout(timeout);typing.parentElement.remove();setBusy(false);}
  }
  function send(message) {
    if(busy || !message.trim()) return;
    message=message.trim().slice(0,2000);
    if(!workspace.classList.contains('has-conversation') && currentTitle) currentTitle.textContent=message.slice(0,60);
    row(message,true);
    const payload={message,conversation_history:history.slice()};
    if(locationContext && Date.now()-locationContext.time<300000 && /^(kalau|kalo|bagaimana dengan)/i.test(message)) payload.user_location=locationContext.coords;
    function retry(){request(form.dataset.chatUrl,payload,retry);}
    retry();
  }
  function hasCoords(f) {return typeof f.latitude==='number' && Number.isFinite(f.latitude) && Math.abs(f.latitude)<=90 && typeof f.longitude==='number' && Number.isFinite(f.longitude) && Math.abs(f.longitude)<=180;}
  function facilityCard(f) {
    const card=el('article','facility-result-item');
    card.append(el('h2','facility-result-name',f.name),el('p','facility-result-meta',`${f.facility_type_label || f.facility_type} · ${f.city || ''}`),el('p','facility-result-meta',f.address || 'Alamat belum tersedia'));
    if(f.phone && f.phone!=='-') card.append(el('p','facility-result-meta',`Telepon: ${f.phone}`));
    if(hasCoords(f)) card.append(el('p','facility-result-meta',`${f.latitude}, ${f.longitude}`));
    if(typeof f.distance_km==='number') card.append(el('p','facility-result-distance',`± ${f.distance_km} km (perkiraan garis lurus)`));
    if(Number.isInteger(f.id) && f.id>0) {const link=el('a','facility-result-link','Lihat Detail Fasilitas →');link.href=`/facilities/${f.id}`;card.append(link);}
    return card;
  }
  function render(data) {
    const follow = messages.scrollHeight-messages.scrollTop-messages.clientHeight < 80;
    const bubble=row(data.message || 'Tidak ada informasi yang tersedia.');
    bubble.append(el('small','muted',data.response_source==='ai'?'Jawaban AI':'Panduan dasar SehatWarga'));
    if(data.requires_location) {
      const card=el('div','location-request-card');card.append(el('p','location-request-text','Bagikan lokasi untuk pencarian ini saja. Koordinat tidak disimpan.'));
      const button=el('button','btn-location-action','Gunakan Lokasi Saya');button.type='button';
      button.addEventListener('click',()=>{
        if(busy) return;
        if(!navigator.geolocation) {row('Geolokasi tidak tersedia. Sebutkan kota melalui pesan.');return;}
        setBusy(true);button.textContent='Meminta lokasi…';
        navigator.geolocation.getCurrentPosition(pos=>{
          setBusy(false);button.textContent='Gunakan Lokasi Saya';
          locationContext={time:Date.now(),coords:{latitude:pos.coords.latitude,longitude:pos.coords.longitude}};
          const payload={latitude:pos.coords.latitude,longitude:pos.coords.longitude,facility_type:data.facility_type || null};
          request(form.dataset.locationUrl,payload,()=>button.click());
        },()=>{setBusy(false);button.textContent='Gunakan Lokasi Saya';row('Lokasi tidak dapat diakses. Anda tetap dapat mencari berdasarkan kota.');},{timeout:10000,enableHighAccuracy:false,maximumAge:0});
      });card.append(button);bubble.append(card);
    }
    if(Array.isArray(data.facilities) && data.facilities.length) {
      const list=el('div','facility-results-list');data.facilities.slice(0,5).forEach(f=>list.append(facilityCard(f)));bubble.append(list);
      const facilities=data.facilities.filter(hasCoords);
      if(facilities.length) {
        const mapElement=el('div','assistant-map');mapElement.setAttribute('aria-label','Peta fasilitas hasil pencarian');bubble.append(mapElement);
        const job=window.SehatWarga.whenNearViewport(mapElement,async()=>{
        pendingMaps.delete(mapElement);
        try {await window.SehatWarga.loadMapLibrary();} catch { /* Preserve the existing failure text. */ }
        if(!mapElement.isConnected) return;
        const wasAtBottom=messages.scrollHeight-messages.scrollTop-messages.clientHeight<40;
        const map=createFacilityMap(mapElement,[facilities[0].latitude,facilities[0].longitude],12);
        if(map) {
          maps.push(map);
          const points=facilities.map(f=>({...f,lat:f.latitude,lng:f.longitude,type_label:f.facility_type_label}));
          points.forEach((f,i)=>addFacilityMarker(map,f,facilityCard(facilities[i])));
          if(data.user_location && hasCoords(data.user_location)) {
            const user={lat:data.user_location.latitude,lng:data.user_location.longitude};
            addFacilityMarker(map,user,el('strong','','Lokasi Anda'),'#0B8179');points.push(user);
          }
          fitFacilityMap(map,points,24,15);
        }
        if(wasAtBottom) messages.scrollTop=messages.scrollHeight;
        });
        pendingMaps.set(mapElement,job);
      }
    }
    if (follow) messages.scrollTop=messages.scrollHeight;
  }
  form.addEventListener('submit',e=>{e.preventDefault();send(input.value);});
  input.addEventListener('input',()=>{input.style.height='auto';input.style.height=`${Math.min(input.scrollHeight,140)}px`;});
  input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send(input.value);}});
  document.querySelectorAll('.suggested-pill').forEach(b=>b.addEventListener('click',()=>send(b.dataset.query)));
});
