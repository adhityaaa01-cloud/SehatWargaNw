/** Progressive directory preview using the existing server-rendered GET endpoint. */
document.addEventListener('DOMContentLoaded', () => {
  const root = document.querySelector('.directory-results');
  const form = document.getElementById('home-directory-form');
  if (!root || !form || !window.fetch || !window.DOMParser) return;
  const cards = document.getElementById('directory-cards');
  const pagination = document.getElementById('directory-pagination');
  const feedback = document.getElementById('directory-feedback');
  const mapSlot = document.getElementById('directory-map-slot');
  let selectedType = '', controller, liveMap;
  function clearMap() { liveMap?.remove(); liveMap = null; mapSlot.replaceChildren(); }
  function offerMap(facilities) {
    if (!facilities.length) return;
    const details = document.createElement('details');
    details.className = 'directory-map-details';
    const summary = document.createElement('summary');
    summary.textContent = 'Lihat peta lokasi fasilitas';
    const canvas = document.createElement('div');
    canvas.className = 'map-container';
    const status = document.createElement('p');
    status.className = 'small muted'; status.setAttribute('role', 'status');
    details.append(summary, canvas, status); mapSlot.append(details);
    let started = false;
    details.addEventListener('toggle', async () => {
      if (!details.open) return;
      if (started) { liveMap?.resize(); return; }
      started = true; status.textContent = 'Memuat peta…';
      try {
        await window.SehatWarga.loadMapLibrary();
        if (!canvas.isConnected) return;
        liveMap = createFacilityMap(canvas, [facilities[0].lat, facilities[0].lng], 11);
        if (liveMap) {
          facilities.forEach(f => addFacilityMarker(liveMap,f));
          fitFacilityMap(liveMap,facilities,24);
        }
        status.textContent = '';
      } catch {
        status.textContent = 'Peta tidak dapat dimuat. Informasi fasilitas tetap tersedia pada kartu.';
      }
    });
  }
  async function load(url) {
    controller?.abort();
    const request = new AbortController(); controller = request;
    root.setAttribute('aria-busy', 'true'); feedback.textContent = 'Memuat fasilitas…';
    const timeout = setTimeout(() => request.abort(), 15000);
    try {
      const response = await fetch(url, { signal: request.signal, credentials: 'same-origin' });
      if (!response.ok) throw new Error('Directory unavailable');
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (controller !== request) return;
      if (!doc.querySelector('#facility-map-data')) throw new Error('Invalid directory response');
      // Same-origin, auto-escaped Jinja cards; scripts in the fetched page never execute.
      const results = [...doc.querySelectorAll('.facility-grid > .facility-card')];
      cards.replaceChildren(...results.map(card => document.importNode(card, true)));
      const pages = doc.querySelector('.pagination');
      pagination.replaceChildren(...(pages ? [document.importNode(pages, true)] : []));
      const params = new URL(url, location.origin).searchParams;
      selectedType = params.get('facility_type') || '';
      root.querySelectorAll('[data-facility-type]').forEach(link => {
        if (link.dataset.facilityType === selectedType) link.setAttribute('aria-current', 'true');
        else link.removeAttribute('aria-current');
      });
      feedback.textContent = results.length ? `Menampilkan ${results.length} fasilitas pada halaman ini.` : 'Tidak ada fasilitas yang sesuai. Coba kata kunci lain atau pilih Semua.';
      clearMap();
      const facilities = JSON.parse(doc.querySelector('#facility-map-data').textContent).filter(validFacilityCoordinates);
      offerMap(facilities);
    } catch {
      if (controller !== request) return;
      cards.replaceChildren(); pagination.replaceChildren(); clearMap();
      feedback.textContent = 'Daftar belum dapat dimuat. Coba cari kembali atau buka direktori lengkap.';
    } finally {
      clearTimeout(timeout);
      if (controller === request) root.removeAttribute('aria-busy');
    }
  }
  function search(type = selectedType) {
    const url = new URL(root.dataset.directoryUrl, location.origin);
    url.searchParams.set('search', form.elements.search.value.trim());
    if (type) url.searchParams.set('facility_type', type);
    load(url);
  }
  form.addEventListener('submit', event => { event.preventDefault(); search(); });
  root.querySelectorAll('[data-facility-type]').forEach(link => link.addEventListener('click', event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); search(link.dataset.facilityType);
  }));
  pagination.addEventListener('click', event => {
    const link = event.target.closest('a');
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); load(link.href);
  });
  window.SehatWarga.whenNearViewport(root, () => search());
});
