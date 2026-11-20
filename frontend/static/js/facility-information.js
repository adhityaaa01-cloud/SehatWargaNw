// Official schedules are linked at the source so a changed roster stays current.
function initFacilityInformation(panel) {
  const clinic = panel.querySelector('[data-clinic-info]');
  const google = panel.querySelector('[data-google-info]');
  const reference = panel.querySelector('[data-google-reference]');
  let selected, library, generation = 0;

  function link(label, url) {
    const a = document.createElement('a');
    a.textContent = label;
    a.href = url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    return a;
  }
  function loadPlaces() {
    if (!library) library = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      const params = new URLSearchParams({key:google.dataset.key, libraries:'places', language:'id', v:'weekly'});
      script.src = 'https://maps.googleapis.com/maps/api/js?' + params;
      script.onload = () => window.google?.maps?.importLibrary
        ? resolve(window.google.maps.importLibrary('places')) : reject(new Error());
      script.onerror = reject;
      document.head.append(script);
    }).catch(error => {library = null; throw error;});
    return library;
  }
  function normalized(name) {
    return name.toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim();
  }
  async function displayGoogle(f, version) {
    google.textContent = 'Mencari profil fasilitas di Google Maps…';
    try {
      const {Place} = await loadPlaces();
      if (version !== generation) return;
      const {places} = await Place.searchByText({
        textQuery:[f.name, f.address].filter(Boolean).join(', '),
        fields:['id','displayName','location'], language:'id', region:'id',
        locationBias:{center:{lat:f.lat,lng:f.lng},radius:500}, maxResultCount:5
      });
      if (version !== generation) return;
      // Nearby departments can have different schedules and reviews from the hospital.
      const matches = places.filter(p => p.location && normalized(p.displayName || '') === normalized(f.name) &&
        Number(calculateDistanceKm(f.lat,f.lng,p.location.lat(),p.location.lng())) <= 0.3);
      if (matches.length !== 1) {
        google.textContent = 'Profil belum dapat dicocokkan dengan pasti. Pilih lokasi yang sesuai melalui tautan Google Maps.';
        return;
      }
      reference.href += '&query_place_id=' + encodeURIComponent(matches[0].id);
      const widget = document.createElement('gmp-place-details');
      const request = document.createElement('gmp-place-details-place-request');
      request.setAttribute('place',matches[0].id);
      widget.append(request);
      for (const field of ['name','address','rating','opening-hours','website','reviews']) {
        widget.append(document.createElement('gmp-place-' + field));
      }
      widget.addEventListener('gmp-error', () => {
        if (version === generation) google.textContent = 'Detail Google belum tersedia. Buka profil melalui tautan Google Maps.';
      });
      google.replaceChildren(widget);
    } catch {
      if (version === generation) google.textContent = 'Detail Google belum dapat dimuat. Gunakan tautan Google Maps.';
    }
  }
  function clear() {
    generation++;
    selected = null;
    google.replaceChildren();
    clinic.replaceChildren();
  }
  return {clear, select(f) {
    if (selected === f.id) return;
    clear();
    selected = f.id;
    const name = normalized(f.name);
    const local = /lamongan/i.test(f.address || '') && Math.abs(f.lat + 7.12) < 0.08 && Math.abs(f.lng - 112.41) < 0.08;
    if (local && /\b(rsud|rumah sakit umum daerah) (dr )?soegiri\b/.test(name)) {
      clinic.append('RSUD Dr. Soegiri menyediakan layanan rawat jalan dan rawat inap. Untuk kunjungan poli, periksa hari praktik dokter melalui ',
        link('jadwal dokter dan poliklinik RSUD Dr. Soegiri','https://rsud-soegiri.lamongankab.go.id/layanan/149'),'.');
    } else if (local && /\b(rs|rumah sakit) muhammadiyah lamongan\b/.test(name)) {
      clinic.append(link('IGD RS Muhammadiyah Lamongan','https://rsmlamongan.com/layanan/igd'),' melayani 24 jam. Untuk rawat jalan, lihat ',
        link('jadwal dokter per hari','https://rsmlamongan.com/dokter/jadwal'),'.');
    } else {
      clinic.textContent = 'Jadwal layanan khusus belum tersedia. Konfirmasi jam pendaftaran langsung ke fasilitas sebelum berkunjung.';
    }
    reference.href = 'https://www.google.com/maps/search/?' + new URLSearchParams({api:'1',query:[f.name,f.address || [f.lat,f.lng].join(',')].join(', ')});
    if (google.dataset.key) {
      const button = facilityNode('button','Tampilkan detail Google Maps','btn btn-outline-primary');
      button.type = 'button';
      button.addEventListener('click',() => displayGoogle(f,generation),{once:true});
      google.append(button);
    }
  }};
}
