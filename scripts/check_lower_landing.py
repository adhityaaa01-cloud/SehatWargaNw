"""Lower landing page browser QA using disposable SQLite. Set BROWSER_EXECUTABLE for installed Chromium."""
import os
import sys,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from preview import preview_app
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright,expect
server=make_server('127.0.0.1',0,preview_app(),threaded=True)
threading.Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}'
out=ROOT/'qa'/'lower-landing';out.mkdir(exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('BROWSER_EXECUTABLE') or None,args=['--no-sandbox'])
 page=b.new_page(reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 for width,height in [(1366,768),(1440,900),(1920,1080),(768,1024),(375,812),(360,800)]:
  page.set_viewport_size({'width':width,'height':height});page.goto(base,wait_until='networkidle')
  page.locator('.directory-results').scroll_into_view_if_needed();expect(page.locator('#directory-cards .facility-card').first).to_be_visible()
  assert page.request.get(base+'/static/images/healthcare-journey.png').status==200
  assert page.locator('.journey-steps li').count()==3
  assert page.locator('.about-details li').count()==6
  assert page.locator('.journey-help').count()==0
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  steps=page.locator('.journey-steps').evaluate('e=>getComputedStyle(e).gridTemplateColumns.split(" ").length')
  assert steps==(3 if width>=768 else 1),steps
  for cls,label in [('.healthcare-journey','journey'),('.about-section','about'),('.footer','footer')]:
   page.evaluate('(selector)=>{document.activeElement.blur();window.scrollTo(0,document.querySelector(selector).getBoundingClientRect().top+scrollY-88)}',cls)
   page.screenshot(path=str(out/f'{label}-{width}.png'))
  page.evaluate("scrollTo(0,document.querySelector('.healthcare-journey').offsetTop-160)")
  page.screenshot(path=str(out/f'transition-{width}.png'))
  print(width,'layout OK',flush=True)
 for link in page.locator('.footer a').all():
  url=link.get_attribute('href')
  assert page.request.get(base+url).status==200,url
 assert not errors,errors
 print('footer links, content, help action, asset, no JS exceptions OK',flush=True)
 b.close()
