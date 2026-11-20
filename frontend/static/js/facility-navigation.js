// Project a GPS fix onto the road geometry. Segment lengths and offsets are in meters.
function navigationOffset(a, b) {
  const scale = Math.cos((a[1] + b[1]) * Math.PI / 360);
  return [(b[0] - a[0]) * 111320 * scale, (b[1] - a[1]) * 111320];
}

function navigationPath(route) {
  const segments = [], turns = [];
  let length = 0;
  for (const step of route.legs?.flatMap(leg => leg.steps || []) || []) {
    const points = step.geometry?.coordinates;
    if (!points?.length || !step.maneuver) return null;
    turns.push({at: length, step});
    for (let i = 1; i < points.length; i++) {
      const start = points[i - 1], end = points[i];
      const [x, y] = navigationOffset(start, end);
      const meters = Math.hypot(x, y);
      if (meters) segments.push({start, x, y, meters, at: length});
      length += meters;
    }
  }
  return segments.length && turns.length >= 2 ? {segments, turns, length} : null;
}

function nearestNavigationPoint(path, point, previous) {
  let best = null;
  for (const segment of path.segments) {
    const [dx, dy] = navigationOffset(segment.start, point);
    const t = Math.max(0, Math.min(1, (dx * segment.x + dy * segment.y) / segment.meters ** 2));
    const offset = segment.at + t * segment.meters;
    const distance = Math.hypot(dx - t * segment.x, dy - t * segment.y);
    // At overlapping roads prefer the occurrence closest to the last known progress.
    const score = distance + Math.min(10, Math.abs(offset - previous) * 0.005);
    if (!best || score < best.score) best = {offset, distance, score};
  }
  return best;
}

function navigationInstruction(step) {
  const {type, modifier, exit} = step.maneuver;
  const direction = {'left':'kiri','right':'kanan','slight left':'sedikit ke kiri',
    'slight right':'sedikit ke kanan','sharp left':'tajam ke kiri','sharp right':'tajam ke kanan'}[modifier];
  let action = 'Lanjutkan perjalanan';
  if (type === 'arrive') return 'tiba di tujuan';
  if (modifier === 'uturn') action = 'Putar balik';
  else if (['roundabout','rotary','roundabout turn'].includes(type)) action = exit ? 'Di bundaran, ambil jalan keluar ke-' + exit : 'Masuki bundaran';
  else if (type.startsWith('exit ')) action = 'Keluar dari bundaran';
  else if (type === 'fork') action = direction ? 'Ambil cabang ' + direction : 'Ikuti percabangan';
  else if (type === 'merge') action = 'Bergabung ke jalur' + (direction ? ' ' + direction : ' utama');
  else if (type === 'off ramp') action = 'Ambil jalan keluar' + (direction ? ' di ' + direction : '');
  else if (direction) action = 'Belok ' + direction;
  else if (modifier === 'straight') action = 'Terus lurus';
  return action.toLowerCase() + (step.name ? ' menuju ' + step.name : '');
}

function createFacilityNavigation(panel, hooks) {
  const box = facilityNode('div', '','facility-guidance');
  const note = facilityNode('p','','facility-guidance-text');
  note.setAttribute('role','status');
  const buttons = facilityNode('div','','facility-route-controls');
  function button(text, action) {
    const node = facilityNode('button',text,'btn btn-outline-primary');
    node.type = 'button';
    node.addEventListener('click',action);
    buttons.append(node);
    return node;
  }
  const start = button('Mulai Rute', begin);
  const sound = button('Matikan suara', () => {
    muted = !muted;
    refreshControls();
    if (muted) synth?.cancel(); else speak(note.textContent);
  });
  const repeat = button('Ulangi petunjuk', () => speak(note.textContent));
  const end = button('Akhiri Rute', () => stop('Navigasi diakhiri.'));
  const voiceNote = facilityNode('small','Suara bahasa Indonesia belum tersedia di perangkat ini. Ikuti petunjuk teks.','facility-route-note');
  const itinerary = document.createElement('details');
  const steps = document.createElement('ol');
  itinerary.append(facilityNode('summary','Lihat urutan petunjuk rute'), steps);
  box.append(note, buttons, voiceNote, itinerary);
  panel.append(box);
  const synth = window.speechSynthesis;
  let voice, muted = false, watch = null, generation = 0, path, name;
  let progress = 0, misses = 0, lastReroute = 0, lastCue = '', recalculating = false;
  let waitingTimer, showingFallback = false;
  function fallback(reason) {
    clearTimeout(waitingTimer);
    misses = 0;
    note.textContent = reason + ' Ikuti daftar petunjuk atau aktifkan lokasi presisi di perangkat.';
    if (!showingFallback) itinerary.open = true;
    showingFallback = true;
  }
  function refreshControls() {
    voice = synth?.getVoices().find(v => /^id(?:[-_]|$)/i.test(v.lang));
    voiceNote.hidden = !!voice || watch === null;
    start.hidden = !path || watch !== null;
    end.hidden = watch === null;
    sound.hidden = repeat.hidden = watch === null || !voice;
    sound.textContent = muted ? 'Aktifkan suara' : 'Matikan suara';
    repeat.disabled = muted;
  }
  synth?.addEventListener('voiceschanged',refreshControls);
  function speak(text) {
    if (!voice || muted || !window.SpeechSynthesisUtterance) return;
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'id-ID';
    utterance.voice = voice;
    synth.speak(utterance);
  }
  function stop(message = '') {
    generation++;
    clearTimeout(waitingTimer);
    showingFallback = false;
    if (watch !== null) {
      navigator.geolocation.clearWatch(watch);
      synth?.cancel();
    }
    watch = null;
    recalculating = false;
    lastCue = '';
    misses = progress = lastReroute = 0;
    note.textContent = message;
    refreshControls();
  }
  function reset() { path = null; stop(); box.hidden = true; }
  function begin() {
    if (!path || watch !== null) return;
    if (!navigator.geolocation) {note.textContent = 'GPS tidak tersedia.'; return;}
    const session = ++generation;
    note.textContent = 'Mencari posisi GPS. Urutan petunjuk rute sudah tersedia.';
    waitingTimer = setTimeout(() => fallback('Posisi GPS belum tersedia.'), 8000);
    watch = navigator.geolocation.watchPosition(
      pos => {if (session === generation) advance(pos.coords);},
      err => {
        if (session !== generation) return;
        if (err.code === 1) stop('Akses GPS ditolak. Izinkan lokasi untuk memulai kembali.');
        else fallback(err.code === 3 ? 'Waktu pencarian GPS habis.' : 'Perangkat belum dapat menentukan posisi.');
      },
      {enableHighAccuracy:true, maximumAge:0, timeout:15000}
    );
    refreshControls();
  }
  function advance(coords) {
    clearTimeout(waitingTimer);
    if (!Number.isFinite(coords.accuracy) || coords.accuracy > 50) {
      const radius = Number.isFinite(coords.accuracy) ? ' (±' + Math.round(coords.accuracy) + ' m)' : '';
      fallback('Lokasi masih berupa perkiraan' + radius + '.');
      return;
    }
    showingFallback = false;
    hooks.move(coords);
    if (recalculating || !path) return;
    const point = nearestNavigationPoint(path,[coords.longitude,coords.latitude],progress);
    if (point.distance > Math.max(35,coords.accuracy * 1.5)) {
      note.textContent = 'Memeriksa posisi terhadap jalur…';
      if (++misses >= 3 && Date.now() - lastReroute > 15000) {
        lastReroute = Date.now();
        recalculating = true;
        note.textContent = 'Menghitung jalur baru dari posisi Anda…';
        speak(note.textContent);
        hooks.reroute();
      }
      return;
    }
    misses = 0;
    progress = point.offset;
    if (path.length - progress <= 20 && point.distance <= 25) {
      stop('Anda sudah dekat dengan ' + name + '.');
      speak(note.textContent);
      return;
    }
    const next = path.turns.slice(1).find(turn => turn.at >= progress - 3) || path.turns.at(-1);
    const remaining = Math.max(0, next.at - progress);
    const meters = Math.max(10,Math.round(remaining / 10) * 10);
    const distance = meters >= 1000 ? (meters / 1000).toLocaleString('id-ID',{maximumFractionDigits:1}) + ' kilometer' : meters + ' meter';
    note.textContent = (remaining < 12 ? 'Sekarang, ' : 'Dalam ' + distance + ', ') + navigationInstruction(next.step) + '.';
    const cue = next.at + '/' + (remaining < 30 ? 'now' : remaining < 150 ? 'near' : 'ahead');
    if (cue !== lastCue) {lastCue = cue; speak(note.textContent);}
  }
  reset();
  window.addEventListener('pagehide',reset);
  return {reset, prepare(result, destinationName) {
    path = navigationPath(result);
    name = destinationName;
    steps.replaceChildren();
    itinerary.open = false;
    itinerary.hidden = !path;
    for (const turn of path?.turns || []) {
      steps.append(facilityNode('li', navigationInstruction(turn.step)));
    }
    recalculating = false;
    progress = misses = 0;
    lastCue = '';
    box.hidden = false;
    if (!path) stop('Petunjuk per belokan belum tersedia untuk jalur ini.');
    else note.textContent = watch !== null ? 'Jalur diperbarui. Menunggu posisi GPS…' : '';
    refreshControls();
  }};
}
