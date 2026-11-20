"""Service showcase browser QA using an isolated, disposable Flask preview."""
import hashlib
import json
import os
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server
from preview import preview_app

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'qa' / 'reference-carousel'
OUT.mkdir(parents=True, exist_ok=True)
checks = []
errors = []
BASE = 'http://127.0.0.1:5058'


def check(name, condition, detail=None):
    checks.append({'check': name, 'pass': bool(condition), 'detail': detail})


def current(page):
    return page.locator('[data-slide-count]').inner_text().split(' / ')[0]


def settled(page):
    expect(page.locator('[data-showcase-next]')).not_to_have_attribute('aria-disabled', 'true')


def assert_static(page, name, milliseconds=4250):
    before = current(page)
    page.wait_for_timeout(milliseconds)
    check(name, current(page) == before)


def reveal(page):
    page.locator('.service-showcase').scroll_into_view_if_needed()
    page.mouse.move(0, 0)
    page.wait_for_timeout(100)


from PIL import Image
for asset in (ROOT / 'frontend' / 'static' / 'images' / 'services-3d').glob('*.png'):
    with Image.open(asset) as image:
        check(asset.name + ' independent transparent illustration', image.size == (1536,1024) and image.mode == 'RGBA' and image.getextrema()[3][0] == 0)

server = make_server('127.0.0.1', 5058, preview_app(), threaded=True)
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=os.environ.get('BROWSER_EXECUTABLE') or None, args=['--no-sandbox'])
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        context.route('https://unpkg.com/**', lambda route: route.abort())
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE, wait_until='domcontentloaded')
        page.evaluate('document.fonts.ready')
        reveal(page)
        expect(page.locator('.service-showcase')).to_have_class('service-showcase is-enhanced is-playing')
        # Start a fresh dwell: loading/fonts may already have consumed some of
        # the initial timer before the browser test reaches this point.
        page.locator('.service-viewport').hover()
        page.mouse.move(0, 0)
        started = page.evaluate('performance.now()')
        check('initial slide is family', current(page) == '01')
        page.wait_for_timeout(3500)
        check('first slide remains for approximately four seconds', current(page) == '01')
        expect(page.locator('[data-slide-count]')).to_have_text('02 / 04', timeout=1700)
        elapsed = page.evaluate('performance.now()') - started
        check('autoplay starts the transition after four seconds', 3700 <= elapsed <= 4700, elapsed)
        settled(page)
        for number in ['03', '04', '01']:
            expect(page.locator('[data-slide-count]')).to_have_text(f'{number} / 04', timeout=5200)
            settled(page)
            check('autoplay sequence and wrap to ' + number, True)
        check('automatic changes do not announce each slide', page.locator('[data-showcase-status]').inner_text() == '')
        print('Autoplay sequence verified', flush=True)

        # Pause/play persists after pointer and focus leave the controls.
        page.locator('[data-showcase-play]').click()
        page.locator('[data-showcase-play]').evaluate('el => el.blur()')
        page.mouse.move(0, 0)
        assert_static(page, 'explicit pause stops autoplay')
        page.locator('[data-showcase-play]').click()
        page.locator('[data-showcase-play]').evaluate('el => el.blur()')
        page.mouse.move(0, 0)
        previous_number = current(page)
        expect(page.locator('.service-showcase')).to_have_class('service-showcase is-enhanced is-playing')
        page.wait_for_function('(n) => document.querySelector("[data-slide-count]").textContent.slice(0,2) !== n', arg=previous_number, timeout=5100)
        settled(page)
        check('explicit play resumes autoplay', True)

        page.locator('.service-viewport').hover()
        assert_static(page, 'hover pauses autoplay')
        page.mouse.move(0, 0)
        page.locator('.service-slide.is-current .service-cta').focus()
        focused_href = page.locator('.service-slide.is-current .service-cta').get_attribute('href')
        assert_static(page, 'CTA focus pauses autoplay without moving focus')
        check('CTA keeps keyboard focus', page.evaluate('document.activeElement.getAttribute("href")') == focused_href)
        page.evaluate('document.activeElement.blur()')

        # Exercise visibility handling directly; this simulates the browser event.
        page.evaluate('''() => {
          Object.defineProperty(document, 'hidden', {configurable:true, get: () => true});
          document.dispatchEvent(new Event('visibilitychange'));
        }''')
        assert_static(page, 'hidden document pauses autoplay')
        check('hidden document has no playing progress animation', not page.locator('.service-showcase').evaluate('el => el.classList.contains("is-playing")'))
        page.evaluate('''() => { delete document.hidden; document.dispatchEvent(new Event('visibilitychange')); }''')
        page.locator('#tentang-kami').scroll_into_view_if_needed()
        assert_static(page, 'offscreen showcase pauses autoplay')
        print('Pause, focus, hover and visibility verified', flush=True)

        reveal(page)
        page.locator('[data-showcase-play]').click()
        start = current(page)
        page.locator('[data-showcase-next]').click()
        page.wait_for_timeout(100)
        movement = page.locator('.service-viewport').evaluate('''el => {
          const read = selector => {const s=getComputedStyle(el.querySelector(selector)); return {x:new DOMMatrixReadOnly(s.transform).m41,opacity:Number(s.opacity)}};
          return {out:read('.is-leaving'),incoming:read('.is-current')};
        }''')
        check('outgoing moves left and fades; incoming arrives from right', movement['out']['x'] < 0 < movement['incoming']['x'] and 0 < movement['out']['opacity'] < 1 and 0 < movement['incoming']['opacity'] < 1, movement)
        page.screenshot(path=str(OUT / 'transition.png'))
        settled(page)
        check('one visible slide and one tabbable CTA after transition', page.locator('.service-slide:visible').count() == 1 and page.locator('.service-slide:not([inert]) .service-cta').count() == 1)
        page.locator('[data-showcase-previous]').click()
        settled(page)
        check('previous returns to the prior slide', current(page) == start)
        page.locator('[data-showcase-next]').evaluate('el => {for(let i=0;i<10;i++) el.click()}')
        settled(page)
        check('rapid clicks do not overlap transitions or skip multiple slides', current(page) == str(int(start) % 4 + 1).zfill(2) and page.locator('.is-leaving').count() == 0)

        # All slides and supplied backgrounds across desktop, tablet and mobile.
        for width, height in [(1366,768), (1440,900), (1920,1080), (768,1024), (375,812), (320,740)]:
            page.set_viewport_size({'width': width, 'height': height})
            reveal(page)
            heights = []
            for _ in range(4):
                number = current(page)
                box = page.locator('.service-viewport').bounding_box()
                heights.append(box['height'])
                geometry = page.locator('.service-slide.is-current').evaluate('''el => {
                  const r=el.getBoundingClientRect(),copy=el.querySelector('.service-slide-copy').getBoundingClientRect(),cta=el.querySelector('.service-cta').getBoundingClientRect();
                  const img=el.querySelector('.service-illustration'), ir=img.getBoundingClientRect(), s=getComputedStyle(img);
                  return {fits:copy.left>=r.left && copy.right<=r.right && cta.bottom<=r.bottom,
                    contain:s.objectFit==='contain',uncropped:ir.left>=r.left && ir.right<=r.right && ir.top>=r.top && ir.bottom<=r.bottom,loaded:img.complete && img.naturalWidth>0,
                    source:img.currentSrc,containerLeft:document.querySelector('.directory-container').getBoundingClientRect().left};
                }''')
                check(f'{width} slide {number} fits and contains complete 3D art', geometry['fits'] and geometry['contain'] and geometry['uncropped'] and geometry['loaded'], geometry)
                expected_background = ['01-kepesertaan-keluarga.png', '02-pengajuan-layanan.png', '03-iuran-pembayaran.png', '04-pengaduan.png'][int(number)-1]
                check(f'{width} slide {number} illustration mapping', expected_background in geometry['source'])
                check(f'{width} slide {number} no horizontal overflow', page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                check(f'{width} slide {number} stays aligned with directory', abs(box['x'] - (max(0, (width-1680)/2) + min(48,max(20,width*.03)))) < 1)
                page.locator('.service-showcase').screenshot(path=str(OUT / f'slide-{number}-{width}.png'))
                if width == 1440:
                    page.screenshot(path=str(OUT / f'page-slide-{number}.png'))
                page.locator('[data-showcase-next]').click()
                settled(page)
            check(f'{width} no height shift between slides', len(set(heights)) == 1, heights)
            if width >= 1024:
                check(f'{width} desktop panel height 270–300px', 270 <= heights[0] <= 300)

        # All original service URLs still resolve through the existing login flow.
        paths = page.locator('.service-cta').evaluate_all('els => els.map(el => new URL(el.href).pathname)')
        check('service destinations preserved', paths == ['/citizen/family','/citizen/services','/citizen/contributions','/citizen/complaints'], paths)
        check('all service destinations resolve', all(page.request.get(BASE + path).status == 200 for path in paths))
        page.set_viewport_size({'width':1440,'height':900})
        reveal(page)
        page.locator('.service-slide.is-current .service-cta').focus()
        page.keyboard.press('Enter')
        expect(page).to_have_url(__import__('re').compile('/login'))
        check('keyboard Enter opens the original service login flow', True)
        context.close()

        reduced = browser.new_context(viewport={'width':1440,'height':900}, reduced_motion='reduce')
        reduced.route('https://unpkg.com/**', lambda route: route.abort())
        page = reduced.new_page()
        page.goto(BASE, wait_until='domcontentloaded')
        reveal(page)
        assert_static(page, 'reduced motion starts with autoplay paused')
        check('reduced motion exposes play control', page.locator('[data-showcase-play]').get_attribute('aria-label') == 'Putar otomatis')
        page.locator('[data-showcase-next]').click()
        check('reduced motion manual navigation has no animated transition', current(page) == '02' and page.locator('.is-leaving').count() == 0)
        reduced.close()

        no_js = browser.new_context(viewport={'width':375,'height':812}, java_script_enabled=False)
        no_js.route('https://unpkg.com/**', lambda route: route.abort())
        page = no_js.new_page()
        page.goto(BASE, wait_until='domcontentloaded')
        check('without JS all four service links are visible', page.locator('.service-cta:visible').count() == 4)
        check('without JS inactive controls remain hidden', not page.locator('.showcase-controls').is_visible())
        no_js.close()
        browser.close()
finally:
    server.shutdown()
check('no JavaScript errors', not errors, errors)
(OUT / 'checks.json').write_text(json.dumps(checks, indent=2))
failures = [c for c in checks if not c['pass']]
print(json.dumps({'checks':len(checks), 'failures':failures}, indent=2))
raise SystemExit(bool(failures))
