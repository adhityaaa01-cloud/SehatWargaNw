"""Hero typography and motion QA against disposable SQLite preview.
Set BROWSER_EXECUTABLE to use an installed Chromium.
"""
import os
import sys,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from preview import preview_app
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright
server=make_server('127.0.0.1',0,preview_app(),threaded=True)
threading.Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}'
out=ROOT/'qa'/'hero-typography';out.mkdir(exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('BROWSER_EXECUTABLE') or None,args=['--no-sandbox'])
 page=b.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script("""(()=>{window.heroRuns=[];window.heroFinishes=[];const run=Element.prototype.animate;Element.prototype.animate=function(f,o){const a=run.call(this,f,o);if(this.closest('.hero-section')){heroRuns.push({cls:this.className,tag:this.tagName,frames:f,options:o});a.addEventListener('finish',()=>heroFinishes.push(this.tagName));}return a;};})();""")
 for width,height in [(1366,768),(1440,900),(1920,1080),(1024,768),(768,1024),(375,812),(360,800)]:
  page.set_viewport_size({'width':width,'height':height});page.goto(base,wait_until='networkidle');page.evaluate('document.fonts.ready');page.wait_for_timeout(1150)
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  heading=page.locator('.hero-section h1')
  metrics=heading.evaluate('e=>({size:parseFloat(getComputedStyle(e).fontSize),lines:e.getBoundingClientRect().height/parseFloat(getComputedStyle(e).lineHeight),font:getComputedStyle(e).fontFamily})')
  assert 'Source Sans 3' in metrics['font']
  assert page.evaluate("document.fonts.check('700 56px \"Source Sans 3\"')")
  if width>=1024: assert 56<=metrics['size']<=64
  if width>=1366: assert metrics['lines']<2.1, metrics
  positions=page.locator('.hero-content > *').evaluate_all('els=>els.map(e=>e.getBoundingClientRect().x)')
  assert len(positions)==5 and max(positions)-min(positions)<1, positions
  assert page.locator('.hero-content > *').evaluate_all('els=>els.every(e=>getComputedStyle(e).textAlign==="left")')
  assert page.locator('.hero-actions a').count()==2
  assert page.locator('.hero-actions a').evaluate_all("els=>els.map(e=>new URL(e.href).pathname).join(',')")== '/facilities,/login'
  page.screenshot(path=str(out/f'hero-{width}.png'))
  if width==1440:
   runs=page.evaluate('heroRuns');assert len(runs)==6
   assert runs[0]['cls']=='hero-content' and runs[0]['frames'][0]['transform']=='translateX(-32px)'
   assert [r['options']['delay'] for r in runs[1:]]==[0,110,220,330,440]
   assert all('transform' not in r['frames'][0] and r['options']['duration']==650 for r in runs[1:])
   assert page.evaluate('heroFinishes')==['DIV','P','H1','P','DIV','P']
   page.evaluate('scrollTo(0,document.body.scrollHeight)');page.wait_for_timeout(100);page.evaluate('scrollTo(0,0)');page.wait_for_timeout(200)
   assert page.evaluate('heroRuns.length')==6
  print(width,'OK',metrics,flush=True)
 for mode in ['reduced','no-js']:
  context=b.new_context(java_script_enabled=mode!='no-js',reduced_motion='reduce' if mode=='reduced' else 'no-preference')
  test=context.new_page();test.goto(base,wait_until='networkidle')
  assert test.locator('.hero-section h1').evaluate("e=>getComputedStyle(e).opacity==='1' && e.getAnimations().length===0")
  context.close()
 assert not errors, errors
 print('PASS animations once, order, local font, reduced motion, no-JS, original links, no JS exceptions',flush=True)
 b.close()
