"""Bounded, transient label OCR. No image, OCR, or provider calls leave the server."""
import copy
import io
import json
import re
import secrets
import threading
import time
import unicodedata
import warnings
from difflib import SequenceMatcher
from pathlib import Path

from flask import current_app, session
from PIL import Image, ImageOps, ImageFilter, UnidentifiedImageError
import pytesseract


class ScanError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


class Store:
    def __init__(self):
        self.items = {}
        self.lock = threading.RLock()
        self.ocr = threading.BoundedSemaphore(2)


def store():
    # Installed at app creation, not a module global shared across applications.
    return current_app.extensions['medicine_scans']


def catalog():
    path = current_app.config.get('MEDICINE_CATALOG_PATH') or Path(__file__).resolve().parents[1] / 'data/medicines.json'
    return json.loads(Path(path).read_text())['products']


def normalize(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text).lower()).strip()


def strength_matches(evidence, reference):
    value, unit, denominator, basis_unit = evidence
    ref_value, ref_unit, ref_basis = reference
    if value.replace(',', '.') != ref_value or unit != ref_unit:
        return False
    if not basis_unit:
        return True
    number = re.search(r'\d+(?:[.,]\d+)?', ref_basis)
    return basis_unit in ref_basis and (denominator or '1') == (number[0] if number else '1')


def read_image(upload):
    maximum = min(current_app.config.get('MAX_CONTENT_LENGTH') or 5*1024*1024, 5*1024*1024)
    data = upload.stream.read(maximum + 1)
    if len(data) > maximum:
        raise ScanError('Berkas terlalu besar. Pilih gambar di bawah 5 MB.', 413)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as original:
                if original.format not in {'PNG', 'JPEG', 'WEBP'}:
                    raise ScanError('Gunakan gambar JPEG, PNG, atau WebP.')
                if original.width * original.height > 20_000_000:
                    raise ScanError('Gambar melebihi 20 juta piksel. Kecilkan resolusinya.')
                original.load()
                image = ImageOps.exif_transpose(original).convert('RGB')
        # Small labels benefit from limited enlargement; large photos are reduced.
        scale = min(3, 1800 / max(image.size))
        image = image.resize(tuple(max(1, round(x*scale)) for x in image.size))
        image = ImageOps.autocontrast(ImageOps.grayscale(image)).filter(ImageFilter.SHARPEN)
    except ScanError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ScanError('Gambar rusak atau tidak dapat dibaca. Pilih foto lain.') from None
    if not store().ocr.acquire(blocking=False):
        raise ScanError('OCR sedang sibuk. Coba lagi sebentar.', 429)
    try:
        return pytesseract.image_to_string(image, lang='ind+eng', config='--psm 11', timeout=12)[:6000].strip()
    except pytesseract.TesseractNotFoundError:
        raise ScanError('Tesseract belum tersedia di server. Hubungi pengelola.', 503) from None
    except (RuntimeError, pytesseract.TesseractError):
        raise ScanError('OCR gagal atau melewati batas waktu. Coba foto lebih jelas; pastikan bahasa ind+eng tersedia.', 503) from None
    finally:
        image.close()
        store().ocr.release()


def match(text, products):
    normalized = normalize(text)
    tokens = re.findall(r'[a-z]+', normalized)
    nies = set(re.findall(r'\b[dg][a-z]{2}\d{8,14}[a-z]\d\b', normalized))
    strengths = re.findall(r'(\d+(?:[.,]\d+)?)\s*(mcg|mg|ml|g)\b(?:\s*(?:/|per)\s*(\d+(?:[.,]\d+)?)?\s*(ml|tablet|kaplet))?', normalized)
    results = []
    for p in products:
        aliases = p.get('aliases', []) + [p['name']]
        exact = any(re.search(r'\b'+re.escape(normalize(a))+r'\b', normalized) for a in aliases)
        similar = max((SequenceMatcher(None, t, normalize(a).split()[0]).ratio() for t in tokens for a in aliases), default=0) >= .76
        nie = bool(p.get('nie') and p['nie'].lower() in nies)
        if not (exact or similar or nie):
            continue
        conflicts = []
        for qualifier in ['extra', 'sp', 'neuro', 'migra', 'anak', 'flu', 'batuk', 'soluble', 'syrup']:
            if qualifier in tokens and qualifier not in normalize(p['name']+' '+p['variant']).split():
                conflicts.append('Varian lain terbaca; belum dapat dikonfirmasi')
        if nies and not nie:
            conflicts.append('NIE berbeda dari rujukan')
        if nie and not (exact or similar) and len(tokens) > 1:
            conflicts.append('Nama pada kemasan belum sesuai NIE')
        # Any other known brand or variant explicitly printed is a contradiction.
        for other in products:
            if other['id'] != p['id'] and normalize(other['name']) in normalized:
                if normalize(other['name']) != normalize(p['name']) and len(other['name']) >= len(p['name']):
                    conflicts.append('Nama/varian lain terbaca')
        known = [(str(a['value']).replace(',', '.'), a['unit'].lower(), normalize(a.get('basis') or '')) for a in p['active'] if a.get('value') is not None]
        if strengths and not known:
            conflicts.append('Kekuatan belum dapat diperiksa terhadap rujukan')
        for value, unit, denominator, basis_unit in strengths:
            if known and not any(strength_matches((value, unit, denominator, basis_unit), ref) for ref in known):
                conflicts.append('Kekuatan atau basis satuan berbeda dari rujukan')
        for form in ['sirup','kapsul','tablet','kaplet']:
            if form in tokens and form not in normalize(p['form']):
                conflicts.append('Bentuk sediaan berbeda')
        active_names = {normalize(a['name']) for a in p['active']}
        ingredient_aliases = {'parasetamol': 'paracetamol', 'kafein': 'caffeine'}
        observed_ingredients = {ingredient_aliases.get(t, t) for t in tokens} & {'paracetamol', 'caffeine', 'ibuprofen'}
        canonical_active = {ingredient_aliases.get(a, a) for a in active_names}
        if observed_ingredients - canonical_active:
            conflicts.append('Zat aktif berbeda dari rujukan')
        for other in products:
            manufacturer = normalize(other.get('manufacturer') or '')
            if manufacturer and manufacturer in normalized and manufacturer != normalize(p.get('manufacturer') or ''):
                conflicts.append('Produsen lain terbaca')
        if p.get('source_conflict'):
            conflicts.append('Sumber identitas bertentangan')
        reason = '; '.join(dict.fromkeys(conflicts)) if conflicts else ('NIE cocok; periksa nama dan bentuk' if nie else 'Nama cocok; periksa NIE atau kekuatan' if exact else 'Nama mirip, kekuatan/NIE belum terbaca')
        strength_ok = bool(known and strengths and not conflicts and all(
            any(v == value.replace(',', '.') and u == unit and (not re.search(r'\d+\s*ml', b) or (basis_unit == 'ml' and denominator and denominator in b))
                for value, unit, denominator, basis_unit in strengths) for v,u,b in known))
        results.append(dict(id=p['id'], name=p['name'], variant=p['variant'], form=p['form'], nie=p.get('nie'), active=p['active'], state='conflict' if conflicts else 'strong' if nie or (exact and strength_ok) else 'ambiguous', reason=reason, eligible=not conflicts and (nie or (exact and strength_ok)) and p.get('detail_ready', False)))
    if sum(c['eligible'] for c in results) > 1:
        for candidate in results:
            if candidate['eligible']:
                candidate.update(eligible=False, state='ambiguous', reason='Beberapa varian sesuai; periksa NIE atau pembeda tambahan')
    return results[:8]


def owner():
    if 'medicine_owner' not in session:
        session['medicine_owner'] = secrets.token_urlsafe(24)
    return session['medicine_owner']


def cleanup():
    now = time.monotonic()
    for key, value in list(store().items.items()):
        if now - value['created'] > 900:
            del store().items[key]


def active(scan_id):
    cleanup()
    item = store().items.get(scan_id) if isinstance(scan_id, str) else None
    if not item or item['owner'] != owner():
        raise ScanError('Scan tidak tersedia atau kedaluwarsa. Kirim foto kembali.', 410)
    return item


def response(scan_id, item):
    candidates = match(item['text'], item['products'])
    return dict(success=True, scan_id=scan_id, raw_text=item['raw'], text=item['text'], candidates=candidates, message=('Teks belum terbaca. Coba foto lebih terang atau koreksi bacaan.' if not item['text'].strip() else 'Periksa bacaan dan pembeda pada kemasan sebelum konfirmasi.' if candidates else 'Produk belum ditemukan dalam katalog. Masukkan NIE atau kirim foto sisi lain.'))


def start(upload, previous_scan_id=None):
    previous = None
    if previous_scan_id:
        with store().lock:
            previous = copy.deepcopy(active(previous_scan_id))
            if previous['confirmed']:
                raise ScanError('Scan sudah dikonfirmasi. Mulai scan baru.', 409)
    raw = read_image(upload)
    text = raw
    products = copy.deepcopy(catalog())
    if previous:
        text = previous['text'] + '\nFoto tambahan:\n' + raw
        raw = previous['raw'] + '\nFoto tambahan:\n' + raw
        products = previous['products']
        if max(len(text), len(raw)) > 6000:
            raise ScanError('Bacaan gabungan terlalu panjang. Mulai scan baru atau koreksi bacaan.')
    with store().lock:
        cleanup()
        if len(store().items) >= 128:
            raise ScanError('Layanan scan sedang penuh. Coba lagi nanti.', 429)
        scan_id = secrets.token_urlsafe(24)
        item = dict(owner=owner(), raw=raw, text=text, created=time.monotonic(), products=products, confirmed=None, revision=0)
        store().items[scan_id] = item
        return response(scan_id, item)


def update(data):
    with store().lock:
        item = active(data.get('scan_id'))
        if item['confirmed']:
            raise ScanError('Scan sudah dikonfirmasi. Mulai scan baru.', 409)
        text = data.get('text')
        if not isinstance(text, str) or len(text) > 6000:
            raise ScanError('Koreksi maksimal 6000 karakter.')
        item['text'] = text
        item['revision'] += 1
        return response(data['scan_id'], item)


def confirm(data):
    with store().lock:
        item = active(data.get('scan_id'))
        product_id = data.get('product_id')
        candidates = match(item['text'], item['products'])
        if not any(c['id'] == product_id and c['eligible'] for c in candidates):
            raise ScanError('Identitas belum cukup atau pilihan tidak sah. Periksa NIE/kekuatan lalu koreksi bacaan.', 409)
        if item['confirmed'] and item['confirmed'] != product_id:
            raise ScanError('Scan telah dikonfirmasi untuk produk lain.', 409)
        p = next(p for p in item['products'] if p['id'] == product_id)
        item['confirmed'] = product_id
        # Deterministic facts only. The existing free-form provider cannot enforce
        # preservation of every warning/number, so this path always uses template.
        return dict(success=True, card=p, message='Informasi rujukan produk; bukan diagnosis atau dosis pribadi.')
