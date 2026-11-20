"""Read-only Mapbox search. Results are temporary and never stored in the DB."""
import json
import math
import threading
import time
from collections import deque
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from flask import current_app

API = 'https://api.mapbox.com/search/searchbox/v1/'
CATEGORIES = {'HOSPITAL': 'hospital', 'CLINIC': 'medical_clinic', 'DENTAL_CLINIC': 'dentist', 'PHARMACY': 'pharmacy', 'OTHER': 'medical_practice', '': 'health_services'}
_gate = threading.BoundedSemaphore(3)
_lock = threading.Lock()
_requests = deque()


class MapboxError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


def public_settings():
    token = str(current_app.config.get('MAPBOX_PUBLIC_TOKEN', '')).strip()
    if not token.startswith('pk.'):
        token = ''
    return {'token': token, 'configured': bool(token), 'style': 'mapbox://styles/mapbox/streets-v12'}


def _request(endpoint, params):
    token = public_settings()['token']
    if not token:
        raise MapboxError('Token publik Mapbox belum dikonfigurasi.')
    url = API + endpoint + '?' + urlencode(dict(params, access_token=token))
    try:
        with urlopen(Request(url, headers={'Accept': 'application/json'}), timeout=12) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise MapboxError('Respons Mapbox terlalu besar. Persempit pencarian.')
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get('features'), list):
            raise ValueError('Invalid response')
        return data
    except HTTPError as error:
        status = error.code
        error.close()
        if status == 429:
            raise MapboxError('Batas pencarian Mapbox tercapai. Coba lagi nanti.', 429) from None
        if status in (401, 403):
            raise MapboxError('Akses Mapbox ditolak. Periksa token dan pengaturan akun.') from None
        raise MapboxError('Pencarian Mapbox belum tersedia. Coba lagi nanti.') from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise MapboxError('Mapbox tidak dapat dihubungi. Coba lagi nanti.') from None


def normalize(features):
    rows, seen = [], set()
    for feature in features[:25]:
        if not isinstance(feature, dict):
            continue
        props = feature.get('properties') or {}
        geometry = feature.get('geometry') or {}
        if not isinstance(geometry, dict):
            continue
        coords = geometry.get('coordinates') or []
        if not isinstance(props, dict) or not isinstance(coords, list) or len(coords) < 2:
            continue
        lng, lat = coords[:2]
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in (lat, lng)):
            continue
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            continue
        identifier = props.get('mapbox_id')
        name = props.get('name')
        if not isinstance(identifier, str) or not isinstance(name, str) or not name.strip() or identifier in seen:
            continue
        context = props.get('context') or {}
        country_context = context.get('country', {}) if isinstance(context, dict) else {}
        country = country_context.get('country_code', '') if isinstance(country_context, dict) else ''
        if country and (not isinstance(country, str) or country.upper() != 'ID'):
            continue
        seen.add(identifier)
        labels = props.get('poi_category') or []
        rows.append({'id': identifier, 'name': name[:200], 'lat': lat, 'lng': lng,
                     'address': str(props.get('full_address') or props.get('address') or '')[:500],
                     'type_label': ', '.join(str(x) for x in labels[:3]) if isinstance(labels, list) else '',
                     'source': 'Mapbox', 'phone': '', 'city': ''})
    return rows


def search(query='', city='Lamongan', facility_type='HOSPITAL', lat=None, lng=None):
    if len(query) > 150 or len(city) > 100 or facility_type not in {*CATEGORIES, 'PUSKESMAS', ''}:
        raise MapboxError('Kata pencarian, kota, atau jenis fasilitas tidak valid.', 400)
    params = {'country': 'ID', 'limit': 25}
    if lat is not None or lng is not None:
        try:
            lat, lng = float(lat), float(lng)
            if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValueError()
        except (TypeError, ValueError):
            raise MapboxError('Koordinat tidak valid.', 400) from None
        params.update(proximity=f'{lng},{lat}', radius=0.25)
    else:
        params['near'] = (city or 'Lamongan') + ', Indonesia'
    category = CATEGORIES.get(facility_type, 'hospital')
    if query or facility_type == 'PUSKESMAS':
        params.update(q=' '.join(x for x in [query, 'Puskesmas' if facility_type == 'PUSKESMAS' else '', city if lat is None else ''] if x),
                      types='poi', limit=10, poi_category=category if facility_type != 'PUSKESMAS' else 'health_services')
        endpoint = 'forward'
    else:
        endpoint = 'category/' + category
    with _lock:
        now = time.monotonic()
        while _requests and _requests[0] < now - 60:
            _requests.popleft()
        if len(_requests) >= 45:
            raise MapboxError('Pencarian sedang sibuk. Coba lagi sebentar.', 429)
        _requests.append(now)
    if not _gate.acquire(blocking=False):
        raise MapboxError('Pencarian sedang sibuk. Coba lagi sebentar.', 429)
    try:
        data = _request(endpoint, params)
    finally:
        _gate.release()
    rows = normalize(data['features'])
    return {'facilities': rows, 'count': len(rows), 'limit': params['limit'], 'source': 'Mapbox',
            'attribution': str(data.get('attribution') or '© Mapbox and its suppliers.'),
            'notice': 'Hasil pencarian tempat, bukan daftar rumah sakit terverifikasi. Unit dalam rumah sakit dapat muncul terpisah. Konfirmasi alamat dan layanan ke fasilitas.'}
