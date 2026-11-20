document.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('[data-mapbox-directory]').forEach(root=>{
    const form=root.querySelector('form'),status=root.querySelector('[data-mapbox-status]'),list=root.querySelector('[data-mapbox-results]');
    const canvas=root.querySelector('[data-mapbox-map]'),placeholder=root.querySelector('[data-mapbox-placeholder]');
    let controller,sequence=0,map=null,markers=[],userLocation=null,selectedId=null,initialStarted=false,facilities=[];
    const details = root.querySelector('[data-place-details]');
    const information = details ? initFacilityInformation(details) : null;
    function showDetails(facility) {
      if (!details) return;
      details.querySelector('[data-place-name]').textContent = facility.name;
      details.querySelector('[data-place-type]').textContent = facility.type_label || 'Tidak tercantum di Mapbox';
      details.querySelector('[data-place-address]').textContent = facility.address || 'Tidak tercantum di Mapbox';
      details.querySelector('[data-place-phone]').textContent = facility.phone || 'Tidak tercantum di Mapbox';
      details.querySelector('[data-place-coordinates]').textContent = [facility.lat, facility.lng].join(', ');
      information.select(facility);
      details.hidden = false;
    }
    const router=createFacilityRouter(root,()=>root.querySelector('[data-mapbox-location]').click());
    const icon=()=>{
      const node=document.createElementNS('http://www.w3.org/2000/svg','svg');node.setAttribute('viewBox','0 0 24 24');node.setAttribute('fill','none');node.setAttribute('stroke','currentColor');node.setAttribute('stroke-width','1.6');node.setAttribute('aria-hidden','true');
      const path=document.createElementNS('http://www.w3.org/2000/svg','path');path.setAttribute('d','M7 21V3h10v18M3 21h18M3 21V9h4m10 0h4v12M10 7h4m-2-2v4M10 13h1m2 0h1M10 17h1m2 0h1');node.append(path);return node;
    };
    function select(id,focusMap=false) {
      selectedId=id;
      list.querySelectorAll('.mapbox-result-card').forEach(card=>card.setAttribute('aria-pressed',String(card.dataset.id===id)));
      const marker=markers.find(item=>item.facilityId===id);
      if(marker){markers.forEach(item=>{if(item!==marker&&item.getPopup().isOpen())item.togglePopup();});if(!marker.getPopup().isOpen())marker.togglePopup();if(focusMap){const point=marker.getLngLat();map.flyTo({center:[point.lng,point.lat],zoom:16});}}
      const facility=facilities.find(item=>item.id===id);if(facility){showDetails(facility);router.select(facility);}
      if(focusMap&&innerWidth<768)canvas.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
    }
    function render(rows) {
      list.replaceChildren();
      if(!rows.length){list.append(facilityNode('div','Belum ada hasil. Coba nama fasilitas, kota, atau jenis lainnya.','mapbox-empty'));return;}
      rows.forEach(f=>{
        const card=facilityNode('button','','mapbox-result-card');card.type='button';card.dataset.id=f.id;card.setAttribute('aria-pressed','false');card.setAttribute('aria-label',`Lihat ${f.name} di peta`);
        const badge=facilityNode('span','','mapbox-result-icon');badge.append(icon());
        const copy=facilityNode('span','','mapbox-result-copy');copy.append(facilityNode('strong',f.name),facilityNode('span',f.address||'Alamat belum tersedia'));
        if(userLocation)copy.append(facilityNode('span',`± ${calculateDistanceKm(userLocation.latitude,userLocation.longitude,f.lat,f.lng)} km · garis lurus`));
        const arrow=facilityNode('span','›','mapbox-result-arrow');arrow.setAttribute('aria-hidden','true');card.append(badge,copy,arrow);card.addEventListener('click',()=>select(f.id,true));list.append(card);
      });
    }
    async function updateMap(rows,request) {
      markers.forEach(marker=>marker.remove());markers=[];
      if(!rows.length)return;
      try {
        await window.SehatWarga.loadMapLibrary();if(request!==sequence||!root.isConnected)return;
        placeholder.hidden=true;
        if(!map)map=createFacilityMap(canvas,[rows[0].lat,rows[0].lng],12);
        router.setMap(map);if(!map)return;
        markers=rows.map(f=>{
          const marker=addFacilityMarker(map,f,null,'#147d73');marker.facilityId=f.id;
          marker.getElement().addEventListener('click',()=>{
            select(f.id);list.querySelectorAll('.mapbox-result-card').forEach(card=>{const active=card.dataset.id===f.id;card.setAttribute('aria-pressed',String(active));if(active)card.scrollIntoView({block:'nearest'});});
          });return marker;
        });
        fitFacilityMap(map,rows);map.resize();if(selectedId)select(selectedId);
      } catch {
        if(request!==sequence)return;
        placeholder.hidden=false;placeholder.querySelector('span').textContent='Peta belum dapat dimuat. Daftar fasilitas tetap tersedia.';
      }
    }
    async function search(location=userLocation) {
      initialStarted=true;userLocation=location;router.clear();router.setOrigin(location);const request=++sequence;controller?.abort();controller=new AbortController();const abort=controller;
      const params=new URLSearchParams(new FormData(form));if(location){params.set('lat',location.latitude);params.set('lng',location.longitude);params.delete('city');}
      const timer=setTimeout(()=>abort.abort(),16000);status.textContent='Mencari fasilitas kesehatan…';root.setAttribute('aria-busy','true');
      try {
        const response=await fetch(root.dataset.searchUrl+'?'+params,{signal:abort.signal,cache:'no-store'});
        const data=await response.json();if(request!==sequence)return;
        if(!response.ok)throw new Error(data.error||'Pencarian belum tersedia.');
        const rows=data.facilities||[];facilities=rows;selectedId=null;if(details){details.hidden=true;information.clear();}
        status.textContent=rows.length?`${rows.length} tempat ditemukan · ${location?'di sekitar Anda':form.elements.city.value||'Lamongan'}`:'Tidak ada fasilitas yang sesuai dengan pencarian Anda.';
        root.querySelector('[data-mapbox-attribution]').textContent=data.attribution||'© Mapbox and its suppliers.';
        render(rows);await updateMap(rows,request);
      } catch(error) {
        if(request!==sequence)return;
        status.textContent=error.name==='AbortError'?'Pencarian terlalu lama. Tekan Cari untuk mencoba lagi.':error.message;
        if(!list.querySelector('.mapbox-result-card'))list.replaceChildren(facilityNode('div','Fasilitas belum dapat dimuat. Silakan coba lagi.','mapbox-empty'));
        else status.textContent+=' Hasil sebelumnya masih ditampilkan.';
      } finally {clearTimeout(timer);if(request===sequence)root.removeAttribute('aria-busy');}
    }
    form.addEventListener('submit',event=>{event.preventDefault();search(null);});
    form.querySelectorAll('[name=facility_type]').forEach(input=>input.addEventListener('change',()=>search()));
    root.querySelector('[data-mapbox-location]').addEventListener('click',()=>{
      if(!navigator.geolocation){status.textContent='Lokasi perangkat tidak tersedia. Masukkan kota.';return;}
      status.textContent='Meminta lokasi perangkat…';
      navigator.geolocation.getCurrentPosition(position=>{
        const selected=facilities.find(item=>item.id===selectedId);
        if(selected){userLocation=position.coords;router.clear();router.setOrigin(position.coords);render(facilities);select(selected.id);status.textContent='Lokasi GPS siap. Jalur menuju fasilitas pilihan sedang dihitung.';}
        else search(position.coords);
      },()=>{status.textContent='Lokasi tidak diizinkan. Masukkan kota untuk mencari.';},{timeout:10000,maximumAge:0});
    });
    window.SehatWarga.whenNearViewport(root,()=>{if(!initialStarted)search(null);});
  });
});
