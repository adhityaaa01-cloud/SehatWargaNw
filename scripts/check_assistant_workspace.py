"""Assistant UI regression on disposable SQLite; set BROWSER_EXECUTABLE for an installed Chromium."""
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
base=f'http://127.0.0.1:{server.server_port}'
out=ROOT/'qa'/'assistant-workspace';out.mkdir(exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('BROWSER_EXECUTABLE') or None,args=['--no-sandbox'])
 page=b.new_page(reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 for width,height in [(1440,900),(1366,768),(1920,1080),(1024,768),(768,1024),(375,812),(360,800),(375,500)]:
  page.set_viewport_size({'width':width,'height':height});page.goto(base+'/assistant',wait_until='networkidle')
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
  assert page.locator('h1').count()==1
  composer=page.locator('#chat-form').bounding_box();assert composer['y']+composer['height']<=height,composer
  assert page.locator('#assistant-welcome .suggested-pill').count()==5
  if width==375:
   page.locator('#scan-file').set_input_files(str(ROOT/'image'/'oskadon.png'))
   expect(page.locator('#scan-preview')).to_be_visible()
   page.locator('#scan-cancel').click()
  if width>=1024:
   boxes=[page.locator(x).bounding_box() for x in ['.assistant-sidebar','.assistant-card','.assistant-info']]
   assert boxes[0]['x']+boxes[0]['width']<boxes[1]['x'] and boxes[1]['x']+boxes[1]['width']<boxes[2]['x']
  else:
   assert not page.locator('.assistant-sidebar details').get_attribute('open')
  page.screenshot(path=str(out/f'welcome-{width}-{height}.png'))
  page.locator('#chat-input').fill('Bagaimana cara melihat informasi iuran?');page.locator('#chat-submit').click()
  expect(page.locator('#chat-submit')).to_be_enabled(timeout=25000)
  expect(page.locator('.assistant-row .message-bubble').first).to_be_visible()
  assert page.locator('#assistant-welcome').is_hidden()
  assert page.locator('.conversation-suggestions').is_visible()
  page.screenshot(path=str(out/f'conversation-{width}-{height}.png'))
  print(width,'welcome/conversation/composer/columns OK',flush=True)
 page.set_viewport_size({'width':1440,'height':900})
 for index,intent in enumerate(['FACILITY_NEARBY','SERVICE_GUIDE','SERVICE_GUIDE','SERVICE_GUIDE','CONTRIBUTION_GUIDE']):
  page.goto(base+'/assistant')
  with page.expect_response(lambda response:response.url.endswith('/assistant/chat')) as answer:
   page.locator('#assistant-welcome .suggested-pill').nth(index).click()
  result=answer.value.json()
  assert result['success'] and result['intent']==intent, (index,result)
  expect(page.locator('#chat-submit')).to_be_enabled(timeout=25000)
 print('all five suggestions use existing functional intents OK',flush=True)
 page.goto(base+'/assistant')
 page.locator('#assistant-welcome .suggested-pill').first.click()
 expect(page.locator('.btn-location-action')).to_be_visible(timeout=25000)
 assert page.locator('.user-row').count()==1
 page.locator('.assistant-new-chat').click();expect(page.locator('#assistant-welcome')).to_be_visible()
 assert page.locator('.user-row').count()==0
 page.locator('#attachment-toggle').click();expect(page.locator('#attachment-options')).to_be_visible()
 assert page.locator('#scan-capture').get_attribute('capture')=='environment'
 page.locator('#scan-file').set_input_files(str(ROOT/'image'/'oskadon.png'))
 expect(page.locator('#scan-preview')).to_be_visible();assert page.locator('#scan-image').evaluate('e=>e.complete && e.naturalWidth>0')
 page.route('**/assistant/scan',lambda r:r.fulfill(json={'success':True,'message':'Bacaan foto untuk pengujian antarmuka','scan_id':'qa','raw_text':'TEKS FOTO QA','text':'TEKS FOTO QA','candidates':[]}))
 page.locator('#scan-send').click();expect(page.locator('.scan-ocr-details')).to_be_visible();page.locator('.scan-ocr-details summary').click();expect(page.locator('.scan-raw')).to_contain_text('TEKS FOTO QA')
 print('new chat, suggestion send, explicit location, upload preview, scan response disclosure OK',flush=True)
 page.route('**/assistant/chat',lambda r:r.fulfill(status=503,json={'success':False,'message':'Gangguan pengujian'}))
 page.locator('#chat-input').fill('Pertanyaan uji');page.locator('#chat-submit').click();expect(page.get_by_role('button',name='Coba lagi')).to_be_visible()
 page.unroute('**/assistant/chat');page.get_by_role('button',name='Coba lagi').click();expect(page.locator('#chat-submit')).to_be_enabled(timeout=25000)
 page.locator('#chat-input').fill('<script>alert(1)</script>');page.locator('#chat-submit').click();expect(page.locator('#chat-submit')).to_be_enabled(timeout=25000)
 assert page.locator('#chat-messages script').count()==0
 # Simulate a long conversation then read older content while a response is pending.
 page.evaluate("""()=>{const m=document.querySelector('#chat-messages');for(let i=0;i<15;i++){const r=document.createElement('p');r.textContent='Pesan lama untuk uji scroll '.repeat(30);m.append(r);} const original=window.fetch;window.fetch=async(...a)=>{if(String(a[0]).includes('/assistant/chat'))await new Promise(r=>setTimeout(r,1000));return original(...a);};}""")
 page.locator('#chat-input').fill('Bagaimana mengajukan layanan?');page.locator('#chat-submit').click();page.locator('#chat-messages').evaluate('e=>e.scrollTop=0')
 expect(page.locator('#chat-submit')).to_be_enabled(timeout=25000)
 assert page.locator('#chat-messages').evaluate('e=>e.scrollTop')<20
 for link in page.locator('.assistant-quick-links a').all():assert page.request.get(base+link.get_attribute('href')).status==200
 assert not errors,errors
 print('error/retry, escaping, scroll preservation, quick-link destinations, no JS exceptions OK',flush=True)
 b.close()
