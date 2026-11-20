/** Mapbox. Device coordinates stay in this page's memory. */
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
  const showLocation = () => {
    if(!map || !location) return;
    if(userMarker) userMarker.remove();
    userMarker=addFacilityMarker(map,{lat:location[0],lng:location[1]},facilityNode('strong','Posisi Anda'),'#0B8179');
    map.flyTo({center:[location[1],location[0]],zoom:12});
  };
  const lazyMap=element&&facilities.length?window.SehatWarga.whenNearViewport(element,async()=>{
    try {await window.SehatWarga.loadMapLibrary();} catch { /* Existing unavailable-map response below. */ }
    if(!element.isConnected) return;
    map=createFacilityMap(element,[facilities[0].lat,facilities[0].lng],11);
    if(map){
      facilities.forEach(f=>addFacilityMarker(map,f));
      fitFacilityMap(map,facilities);
      showLocation();
    }
  }):null;
  if(element&&!facilities.length)element.textContent='Belum ada koordinat fasilitas untuk hasil pencarian ini.';
  const button=document.getElementById('btn-use-location'),feedback=document.getElementById('location-feedback');
  let userMarker=null;
  const status=(text,type='info')=>{if(feedback){feedback.style.display='block';feedback.className=`alert alert-${type}`;feedback.setAttribute('role','status');feedback.textContent=text;}};
  if(button)button.addEventListener('click',()=>{
    if(!navigator.geolocation){status('Geolokasi tidak didukung. Cari berdasarkan nama atau kota.','warning');return;}
    button.disabled=true;button.textContent='Mencari lokasi…';
    navigator.geolocation.getCurrentPosition(position=>{
      const lat=position.coords.latitude,lon=position.coords.longitude;
      location=[lat,lon];lazyMap?.start();showLocation();
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
  window.SehatWarga.whenNearViewport(element,async()=>{
    try {await window.SehatWarga.loadMapLibrary();} catch { /* Existing unavailable-map response below. */ }
    if(!element.isConnected) return;
    const map=createFacilityMap(element,[facility.lat,facility.lng],15);
    if(map)addFacilityMarker(map,facility).togglePopup();
  });
}
