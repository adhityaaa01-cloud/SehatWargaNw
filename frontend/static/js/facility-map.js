/** Mapbox. Device coordinates are temporary and are not stored by this app. */
function calculateDistanceKm(lat1,lon1,lat2,lon2) {
  const rad=n=>n*Math.PI/180;
  const a=Math.sin(rad(lat2-lat1)/2)**2+Math.cos(rad(lat1))*Math.cos(rad(lat2))*Math.sin(rad(lon2-lon1)/2)**2;
  return (6371*2*Math.atan2(Math.sqrt(a),Math.sqrt(Math.max(0,1-a)))).toFixed(1);
}
function facilityNode(tag,text,cls) {const node=document.createElement(tag);node.textContent=text || '';if(cls)node.className=cls;return node;}
function validFacilityCoordinates(f) {return Number.isFinite(f.lat)&&Number.isFinite(f.lng)&&Math.abs(f.lat)<=90&&Math.abs(f.lng)<=180;}
function facilityPopup(f) {
  const node=facilityNode('div','','facility-popup');
  node.append(facilityNode('strong',f.name),facilityNode('p',f.type_label,'small'),facilityNode('p',`${f.address || ''}, ${f.city || ''}`,'small muted'),facilityNode('p',`Telp: ${f.phone || '—'}`,'small muted'));
  const distance=facilityNode('p','','facility-result-distance');distance.id=`distance-marker-${f.id}`;node.append(distance);
  if(Number.isInteger(f.id)&&f.id>0){const link=facilityNode('a','Lihat Detail →','facility-result-link');link.href=`/facilities/${f.id}`;node.append(link);}
  return node;
}
function createFacilityMap(element,center,zoom) {
  if(!element || !element.isConnected) return null;
  const settings=JSON.parse(document.getElementById('map-settings')?.textContent||'{}');
  if(!settings.configured || !window.mapboxgl || !mapboxgl.supported()) {
    element.textContent='Peta Mapbox tidak tersedia. Informasi fasilitas tetap dapat dibaca pada daftar.';
    element.setAttribute('role','status');return null;
  }
  const status=facilityNode('p','Memuat peta Mapbox…','small muted');status.setAttribute('role','status');element.after(status);
  try {
    const map=new mapboxgl.Map({container:element,accessToken:settings.token,style:settings.style,center:[center[1],center[0]],zoom});
    map.addControl(new mapboxgl.NavigationControl(),'top-right');
    const timeout=setTimeout(()=>{status.textContent='Peta belum dapat dimuat. Daftar fasilitas tetap tersedia.';},15000);
    map.on('load',()=>{clearTimeout(timeout);status.textContent='';element.dataset.mapLoaded='true';});
    map.on('error',()=>{clearTimeout(timeout);status.textContent='Peta Mapbox gagal dimuat. Daftar fasilitas tetap tersedia.';});
    map.on('remove',()=>{clearTimeout(timeout);status.remove();});
    return map;
  } catch {status.textContent='Peta Mapbox tidak tersedia pada perangkat ini.';return null;}
}
function addFacilityMarker(map,facility,content,color='#102F46') {
  return new mapboxgl.Marker({color}).setLngLat([facility.lng,facility.lat])
    .setPopup(new mapboxgl.Popup({offset:24}).setDOMContent(content||facilityPopup(facility))).addTo(map);
}
function fitFacilityMap(map,facilities,padding=32,maxZoom=14) {
  const points=facilities.filter(validFacilityCoordinates);if(!points.length)return;
  const bounds=new mapboxgl.LngLatBounds();points.forEach(f=>bounds.extend([f.lng,f.lat]));
  map.fitBounds(bounds,{padding,maxZoom,duration:0});
}
function initFacilityListMap(mapId,facilitiesData) {
  const element=document.getElementById(mapId);
  if(element?.dataset.facilityMapInitialized) return;
  if(element) element.dataset.facilityMapInitialized='true';
  const facilities=(facilitiesData || []).filter(validFacilityCoordinates);
  let map=null;
  let location=null;
  const router=element?createFacilityRouter(element.parentElement,()=>document.getElementById('btn-use-location')?.click()):null;
  const showLocation = () => {
    if(!map || !location) return;
    map.flyTo({center:[location[1],location[0]],zoom:12});
  };
  const lazyMap=element&&facilities.length?window.SehatWarga.whenNearViewport(element,async()=>{
    try {await window.SehatWarga.loadMapLibrary();} catch { /* Existing unavailable-map response below. */ }
    if(!element.isConnected) return;
    map=createFacilityMap(element,[facilities[0].lat,facilities[0].lng],11);
    if(map){
      facilities.forEach(f=>{const popup=facilityPopup(f),directions=facilityNode('button','Lihat rute','btn btn-primary');directions.type='button';directions.addEventListener('click',()=>router.select(f));popup.append(directions);addFacilityMarker(map,f,popup);});
      fitFacilityMap(map,facilities);
      showLocation();router?.setMap(map);
    }
  }):null;
  if(element&&!facilities.length)element.textContent='Belum ada koordinat fasilitas untuk hasil pencarian ini.';
  const button=document.getElementById('btn-use-location'),feedback=document.getElementById('location-feedback');
  const status=(text,type='info')=>{if(feedback){feedback.style.display='block';feedback.className=`alert alert-${type}`;feedback.setAttribute('role','status');feedback.textContent=text;}};
  if(button)button.addEventListener('click',()=>{
    if(!navigator.geolocation){status('Geolokasi tidak didukung. Cari berdasarkan nama atau kota.','warning');return;}
    button.disabled=true;button.textContent='Mencari lokasi…';
    navigator.geolocation.getCurrentPosition(position=>{
      const lat=position.coords.latitude,lon=position.coords.longitude;
      location=[lat,lon];router?.setOrigin(position.coords);lazyMap?.start();showLocation();
      facilities.forEach(f=>{const text=`± ${calculateDistanceKm(lat,lon,f.lat,f.lng)} km (perkiraan garis lurus)`;for(const prefix of ['distance-card-','distance-marker-']){const n=document.getElementById(prefix+f.id);if(n){n.textContent=text;n.style.display='inline-block';}}});
      status(facilities.length?'Lokasi digunakan untuk menghitung jarak fasilitas pada halaman ini. Koordinat tidak disimpan.':'Tidak ada fasilitas berkoordinat pada hasil ini. Ubah filter pencarian.','info');button.disabled=false;button.textContent='Gunakan Lokasi Saya';
    },()=>{button.disabled=false;button.textContent='Gunakan Lokasi Saya';status('Lokasi tidak dapat diakses. Anda tetap dapat mencari fasilitas secara manual.','warning');},{timeout:10000,enableHighAccuracy:false,maximumAge:0});
  });
}
function initFacilityDetailMap(mapId,facility) {
  const element=document.getElementById(mapId);if(!element)return;
  if(element.dataset.facilityMapInitialized) return;
  element.dataset.facilityMapInitialized='true';
  if(!validFacilityCoordinates(facility)){element.textContent='Lokasi peta belum tersedia untuk fasilitas ini.';return;}
  const locate=facilityNode('button','Lihat rute dari lokasi saya','btn btn-primary');locate.type='button';element.after(locate);
  const feedback=facilityNode('p','','small muted');feedback.setAttribute('role','status');locate.after(feedback);
  const router=createFacilityRouter(element.parentElement,()=>locate.click());
  locate.addEventListener('click',()=>{
    if(!navigator.geolocation){feedback.textContent='Lokasi perangkat tidak tersedia.';return;}
    locate.disabled=true;feedback.textContent='Meminta lokasi GPS…';
    navigator.geolocation.getCurrentPosition(position=>{locate.disabled=false;feedback.textContent='';router.setOrigin(position.coords);router.select(facility);},()=>{locate.disabled=false;feedback.textContent='Lokasi tidak dapat diakses. Izinkan GPS lalu coba lagi.';},{timeout:10000,maximumAge:0});
  });
  window.SehatWarga.whenNearViewport(element,async()=>{
    try {await window.SehatWarga.loadMapLibrary();} catch { /* Existing unavailable-map response below. */ }
    if(!element.isConnected) return;
    const map=createFacilityMap(element,[facility.lat,facility.lng],15);
    router.setMap(map);if(map)addFacilityMarker(map,facility).togglePopup();
  });
}

/** Temporary directions: GPS coordinates are sent to Mapbox, never persisted. */
function createFacilityRouter(host, onLocate) {
  const panel=facilityNode('section','','facility-route');panel.hidden=true;panel.setAttribute('aria-label','Rute menuju fasilitas');
  const title=facilityNode('h3','Rute menuju fasilitas');
  const summary=facilityNode('p','','facility-route-summary');summary.setAttribute('role','status');summary.setAttribute('aria-live','polite');
  const controls=facilityNode('div','','facility-route-controls');
  const label=facilityNode('label','Cara perjalanan '),mode=document.createElement('select');mode.setAttribute('aria-label','Cara perjalanan');
  for(const [value,text] of [['driving','Mobil'],['walking','Jalan kaki'],['cycling','Sepeda']]){const option=facilityNode('option',text);option.value=value;mode.append(option);}label.append(mode);
  const locate=facilityNode('button','Gunakan Lokasi Saya','btn btn-primary');locate.type='button';locate.addEventListener('click',onLocate);
  const external=facilityNode('a','Buka navigasi Google Maps ↗','btn btn-outline-primary');external.target='_blank';external.rel='noopener noreferrer';external.referrerPolicy='no-referrer';external.hidden=true;
  const close=facilityNode('button','Hapus rute','btn btn-outline-primary');close.type='button';
  const retry=facilityNode('button','Hitung ulang','btn btn-outline-primary');retry.type='button';retry.addEventListener('click',route);
  controls.append(label,locate,retry,external,close);
  panel.append(title,summary,controls,facilityNode('p','Perkiraan mengikuti jalan sesuai moda perjalanan. Lokasi dikirim ke Mapbox untuk menghitung rute. Gunakan Google Maps untuk panduan selama perjalanan.','facility-route-note'));
  host.insertBefore(panel,host.querySelector(':scope > .mapbox-directory-footnote'));
  let map=null,origin=null,destination=null,geometry=null,controller=null,version=0,userMarker=null,routeReady=false;
  const navigation = host.querySelector('[data-place-details]') ? createFacilityNavigation(panel, {
    move(coords) {
      origin = coords;
      if (userMarker) userMarker.setLngLat([coords.longitude, coords.latitude]);
      else showOrigin();
      updateExternal();
    },
    reroute: () => route(true),
  }) : null;
  const sourceId='facility-directions',layers=['facility-directions-outline','facility-directions-line'];
  function removeLine() {
    if(!map)return;
    for(const id of [...layers].reverse())if(map.getLayer(id))map.removeLayer(id);
    if(map.getSource(sourceId))map.removeSource(sourceId);
  }
  function draw() {
    if(!map||!map.isStyleLoaded())return;
    removeLine();
    if(!geometry)return;
    map.addSource(sourceId,{type:'geojson',data:{type:'Feature',properties:{},geometry}});
    map.addLayer({id:layers[0],type:'line',source:sourceId,layout:{'line-join':'round','line-cap':'round'},paint:{'line-color':'#ffffff','line-width':9}});
    map.addLayer({id:layers[1],type:'line',source:sourceId,layout:{'line-join':'round','line-cap':'round'},paint:{'line-color':'#2563eb','line-width':5}});
    const bounds=new mapboxgl.LngLatBounds();geometry.coordinates.forEach(point=>bounds.extend(point));
    bounds.extend([origin.longitude,origin.latitude]);bounds.extend([destination.lng,destination.lat]);
    map.fitBounds(bounds,{padding:48,maxZoom:16,duration:0});
  }
  function showOrigin() {
    userMarker?.remove();userMarker=null;
    if(map&&origin)userMarker=addFacilityMarker(map,{lat:origin.latitude,lng:origin.longitude},facilityNode('strong','Lokasi Anda'),'#2563eb');
  }
  function cancel() {version++;controller?.abort();geometry=null;routeReady=false;panel.removeAttribute('aria-busy');removeLine();}
  function updateExternal() {
    external.hidden=!origin||!destination;
    if(external.hidden){external.removeAttribute('href');return;}
    const params=new URLSearchParams({api:'1',origin:`${origin.latitude},${origin.longitude}`,destination:`${destination.lat},${destination.lng}`,travelmode:mode.value==='cycling'?'bicycling':mode.value});
    external.href='https://www.google.com/maps/dir/?'+params;
  }
  async function route(continuing = false) {
    if (continuing !== true) navigation?.reset();
    cancel();updateExternal();
    if(!destination)return;
    panel.hidden=false;title.textContent=`Rute ke ${destination.name}`;locate.hidden=!!origin;retry.hidden=!origin;
    if(!origin){summary.textContent='Aktifkan lokasi GPS untuk melihat jalur dari posisi Anda ke fasilitas ini.';return;}
    const settings=JSON.parse(document.getElementById('map-settings')?.textContent||'{}');
    if(!settings.configured){summary.textContent='Rute Mapbox belum tersedia. Gunakan tombol Google Maps untuk melihat jalur.';return;}
    const request=version,abort=new AbortController();controller=abort;
    summary.textContent='Menghitung jalur perjalanan…';panel.setAttribute('aria-busy','true');
    const timer=setTimeout(()=>abort.abort(),15000);
    try {
      const coordinates=`${origin.longitude},${origin.latitude};${destination.lng},${destination.lat}`;
      const params=new URLSearchParams({access_token:settings.token,geometries:'geojson',overview:'full',steps:navigation ? 'true' : 'false'});
      const response=await fetch(`https://api.mapbox.com/directions/v5/mapbox/${mode.value}/${coordinates}?${params}`,{signal:abort.signal,cache:'no-store',referrerPolicy:'no-referrer'});
      const data=await response.json();if(request!==version)return;
      if(!response.ok)throw new Error(response.status===429?'Batas permintaan rute tercapai. Coba lagi nanti atau buka Google Maps.':'Rute belum dapat dimuat. Coba lagi atau buka Google Maps.');
      const result=data.routes?.[0];
      if(data.code==='NoRoute'||data.code==='NoSegment'||!result){summary.textContent='Jalur tidak ditemukan untuk moda ini. Pilih moda lain atau buka Google Maps.';return;}
      if(result.geometry?.type!=='LineString'||!Array.isArray(result.geometry.coordinates)||result.geometry.coordinates.length<2||!result.geometry.coordinates.every(p=>Array.isArray(p)&&validFacilityCoordinates({lng:p[0],lat:p[1]}))||!Number.isFinite(result.distance)||result.distance<0||!Number.isFinite(result.duration)||result.duration<0)throw new Error('Data rute belum tersedia. Coba lagi atau buka Google Maps.');
      geometry=result.geometry;routeReady=true;
      const km=result.distance>=1000?`${(result.distance/1000).toLocaleString('id-ID',{maximumFractionDigits:1})} km`:`${Math.round(result.distance)} m`;
      const minutes=Math.max(1,Math.ceil(result.duration/60)),time=minutes>=60?`${Math.floor(minutes/60)} jam${minutes%60?` ${minutes%60} menit`:''}`:`${minutes} menit`;
      summary.textContent=`${km} · sekitar ${time} · ${mode.options[mode.selectedIndex].text}${map?'':' · Peta belum tersedia; buka Google Maps untuk melihat jalur.'}`;
      draw();
      navigation?.prepare(result, destination.name);
    } catch(error) {
      if(request!==version)return;
      summary.textContent=error.name==='AbortError'?'Perhitungan rute terlalu lama. Pilih moda lagi untuk mencoba atau buka Google Maps.':error instanceof TypeError?'Koneksi rute terganggu. Coba lagi atau buka Google Maps.':error.message;
    } finally {clearTimeout(timer);if(request===version){panel.removeAttribute('aria-busy');if(!routeReady)navigation?.reset();}}
  }
  function clear() {navigation?.reset();cancel();destination=null;panel.hidden=true;panel.removeAttribute('aria-busy');external.removeAttribute('href');}
  close.addEventListener('click',clear);mode.addEventListener('change',route);
  return {
    setMap(value) {if(map===value)return;map=value;showOrigin();if(map){map.on('load',()=>{if(routeReady)draw();});if(routeReady)draw();}},
    setOrigin(value) {origin=value;showOrigin();if(destination)route();},
    select(value) {if(!validFacilityCoordinates(value))return;destination=value;route();},
    clear,
  };
}
