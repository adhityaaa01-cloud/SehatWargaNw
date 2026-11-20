"""Browser regression for landing directory; uses disposable SQLite only.
Run with BROWSER_EXECUTABLE pointing to an installed Chromium if needed.
"""
import os
import sys,threading,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from preview import preview_app
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright,expect
server=make_server('127.0.0.1',0,preview_app(),threaded=True)
threading.Thread(target=server.serve_forever,daemon=True).start()
out=ROOT/'qa'/'landing-directory';out.mkdir(exist_ok=True)
base=f'http://127.0.0.1:{server.server_port}'
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('BROWSER_EXECUTABLE') or None,args=['--no-sandbox'])
 page=b.new_page(reduced_motion='reduce');errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 for width,height in [(1366,768),(1440,900),(1728,900),(1920,1080),(1024,768),(768,1024),(640,960),(375,812),(360,800)]:
  page.set_viewport_size({'width':width,'height':height})
  page.goto(base,wait_until='networkidle')
  page.locator('#direktori').scroll_into_view_if_needed()
  expect(page.locator('#directory-cards .facility-card').first).to_be_visible()
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  expected=4 if width>=1440 else 3 if width>=1024 else 2 if width>=640 else 1
  columns=page.locator('#directory-cards').evaluate('e=>getComputedStyle(e).gridTemplateColumns.split(" ").length')
  assert columns==expected, (width,columns)
  container=page.locator('.directory-container').bounding_box()
  assert abs(container['x']-(width-container['x']-container['width']))<1
  assert container['width']==min(width,1680)
  heights=page.locator('#directory-cards .facility-card').evaluate_all('els=>els.map(e=>e.getBoundingClientRect().height)')
  assert max(heights)-min(heights)<1

  assert page.request.get(base+'/static/images/sehatwarga-direktori-map-bg.png').status==200
  page.evaluate("window.scrollTo(0,document.querySelector('#direktori').offsetTop-160)")
  page.screenshot(path=str(out/f'transition-{width}.png'))
  page.locator('.directory-results').scroll_into_view_if_needed()
  page.screenshot(path=str(out/f'cards-{width}.png'))
  print(width,'layout OK',flush=True)
 page.set_viewport_size({'width':1440,'height':900})
 for code,label in [('HOSPITAL','Rumah Sakit'),('PUSKESMAS','Puskesmas'),('CLINIC','Klinik')]:
  page.locator(f'[data-facility-type="{code}"]').click()
  expect(page.locator(f'[data-facility-type="{code}"]')).to_have_attribute('aria-current','true')
  badges=page.locator('#directory-cards .badge').all_text_contents()
  assert badges and all(x.strip()==label for x in badges),badges
 print('actual category filters OK',flush=True)
 page.locator('[data-facility-type=""]').click()
 expect(page.locator('[data-facility-type=""]')).to_have_attribute('aria-current','true')
 name=page.locator('#directory-cards .facility-name').first.inner_text()
 href=page.locator('#directory-cards a').first.get_attribute('href')
 assert page.request.get(base+href).status==200
 page.locator('#home-search').fill(name)
 page.locator('#home-directory-form button').click()
 expect(page.locator('#directory-feedback')).not_to_have_text('Memuat fasilitas…')
 expect(page.locator('#directory-cards .facility-name').first).to_have_text(name)
 # Fetch source of truth and compare rendered result names.
 source=page.request.get(base+'/facilities',params={'search':name}).text()
 assert name in source
 page.locator('#home-search').fill('zz-no-facility-123456')
 page.locator('#home-directory-form button').click()
 expect(page.locator('#directory-feedback')).to_contain_text('Tidak ada fasilitas')
 assert page.locator('#directory-cards .facility-card').count()==0
 page.locator('#home-search').fill('');page.locator('#home-directory-form button').click()
 expect(page.locator('#directory-cards .facility-card').first).to_be_visible()
 if page.locator('.directory-map-details').count():
  page.route('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',lambda r:r.abort())
  page.locator('.directory-map-details summary').click()
  expect(page.locator('.directory-map-details')).to_contain_text('Peta tidak dapat dimuat',timeout=20000)
  assert page.locator('#directory-cards .facility-card').count()>0
 print('search, empty, detail, map failure fallback OK',flush=True)
 page.route('**/facilities?*',lambda r:r.fulfill(status=503,body='Unavailable'))
 page.locator('#home-directory-form button').click()
 expect(page.locator('#directory-feedback')).to_contain_text('Daftar belum dapat dimuat')
 assert not errors,errors
 print('error state and no JavaScript exceptions OK',flush=True)
 context=b.new_context(java_script_enabled=False)
 plain=context.new_page();plain.goto(base)
 assert plain.locator('#home-directory-form').get_attribute('action')=='/facilities'
 assert plain.locator('.directory-types a').count()==4
 print('no-JS directory navigation OK',flush=True)
 b.close()
