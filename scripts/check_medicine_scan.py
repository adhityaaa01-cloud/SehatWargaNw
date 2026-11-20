"""Optional browser check: real Tesseract + isolated SQLite; no provider or live API.
PYTHONPATH=/tmp/sehatwarga-browser-tools .venv/bin/python scripts/check_medicine_scan.py
BROWSER_EXECUTABLE may point to an installed Chromium. Screenshots go to /tmp.
"""
import io
import json
import os
import sys
import threading
from pathlib import Path
os.environ.setdefault('OMP_THREAD_LIMIT', '1')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tests
from tests import create_test_app
from app.extensions import db
from PIL import Image,ImageDraw,ImageFont
from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server


def main():
    app=create_test_app()
    server=make_server('127.0.0.1',5056,app,threaded=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    # A generated text image is explicitly an OCR test chart, not a real package.
    chart=Image.new('RGB',(1200,400),'white');draw=ImageDraw.Draw(chart)
    font=ImageFont.load_default(size=46)
    draw.multiline_text((35,30),'OCR TEST CHART - NOT A PACKAGE\nPANADOL\nParacetamol 500 mg per kaplet\nDBL9624502804A1',font=font,fill='black',spacing=12)
    chart.save('/tmp/sehatwarga-scan-chart.png')
    results=[];errors=[]
    try:
        with sync_playwright() as p:
            executable=os.environ.get('BROWSER_EXECUTABLE')
            browser=p.chromium.launch(headless=True,executable_path=executable,args=['--no-sandbox'])
            for width in [1440,375]:
                context=browser.new_context(viewport={'width':width,'height':1000})
                page=context.new_page();page.on('pageerror',lambda e: errors.append(str(e)))
                requests=[];page.on('request',lambda r:requests.append(r.url) if '/assistant/scan' in r.url else None)
                page.goto('http://127.0.0.1:5056/assistant')
                page.get_by_role('button',name='Tambah lampiran').focus();page.keyboard.press('Enter')
                expect(page.get_by_role('button',name='Unggah Gambar',exact=True)).to_be_visible()
                expect(page.locator('#scan-capture')).to_have_attribute('capture','environment')
                page.locator('#scan-file').set_input_files('/tmp/sehatwarga-scan-chart.png')
                expect(page.locator('#scan-preview')).to_be_visible();assert requests==[]
                page.get_by_role('button',name='Batal',exact=True).click();expect(page.locator('#scan-preview')).to_be_hidden()
                page.locator('#scan-file').set_input_files('/tmp/sehatwarga-scan-chart.png')
                page.get_by_role('button',name='Ganti',exact=True).click(no_wait_after=True)
                page.locator('#scan-file').set_input_files('/tmp/sehatwarga-scan-chart.png')
                page.get_by_role('button',name='Kirim gambar',exact=True).click()
                confirm=page.get_by_role('button',name='Konfirmasi produk ini',exact=True)
                expect(confirm).to_be_visible(timeout=20000)
                assert len(requests)==1
                page.screenshot(path=f'/tmp/scan-candidates-{width}.png',full_page=True)
                confirm.click();expect(page.locator('.medicine-card')).to_be_visible()
                expect(page.locator('.medicine-card')).to_contain_text('500 mg per kaplet')
                expect(page.locator('.medicine-card')).to_contain_text('Warfarin')
                assert page.locator('.medicine-card a').count()==2
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=f'/tmp/scan-card-{width}.png',full_page=True)
                page.locator('#chat-input').fill('Berapa tarif iuran?');page.locator('#chat-submit').click()
                expect(page.get_by_text('Rp50.000',exact=False).last).to_be_visible(timeout=15000)
                page.locator('#scan-file').set_input_files(str(Path('image/oskadon.png').resolve()))
                page.get_by_role('button',name='Kirim gambar',exact=True).click()
                expect(page.locator('.scan-result').last).to_contain_text('Orkadon',timeout=20000)
                expect(page.locator('.scan-result').last).to_contain_text('Nama mirip')
                assert page.locator('.scan-result').last.get_by_role('button',name='Konfirmasi produk ini').count()==0
                correction=page.locator('.scan-correction').last
                correction.fill(correction.input_value()+'\nDBL8730700110A1')
                before=page.locator('.scan-result').count()
                page.get_by_role('button',name='Cocokkan ulang',exact=True).last.click()
                expect(page.locator('.scan-result')).to_have_count(before+1)
                page.locator('.scan-result').last.get_by_role('button',name='Konfirmasi produk ini',exact=True).click()
                expect(page.locator('.medicine-card').last).to_contain_text('OSKADON')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                # Untrusted markup is rendered as text and re-matched on server.
                page.locator('#scan-file').set_input_files('/tmp/sehatwarga-scan-chart.png')
                page.get_by_role('button',name='Kirim gambar',exact=True).click()
                expect(page.locator('.scan-result')).to_have_count(before+2,timeout=20000)
                expect(page.locator('.scan-correction').last).to_be_enabled()
                page.locator('.scan-correction').last.fill('<img src=x onerror=alert(1)> unknown product')
                page.get_by_role('button',name='Cocokkan ulang',exact=True).last.click()
                expect(page.locator('.scan-result').last).to_contain_text('Produk belum ditemukan dalam katalog')
                assert page.locator('#chat-messages img').count()==0
                page.get_by_role('button',name='Tidak ada yang sesuai',exact=True).last.click()
                expect(page.locator('.scan-result').last).to_contain_text('Teks belum terbaca')
                page.get_by_role('button',name='Foto sisi lain',exact=True).last.click()
                expect(page.get_by_role('button',name='Unggah Gambar',exact=True)).to_be_visible()
                before=page.locator('.scan-result').count()
                page.locator('#scan-file').set_input_files('/tmp/sehatwarga-scan-chart.png')
                expect(page.locator('#scan-preview')).to_contain_text('digabung')
                page.get_by_role('button',name='Kirim gambar',exact=True).click()
                expect(page.locator('.scan-result')).to_have_count(before+1,timeout=20000)
                expect(page.locator('.scan-result').last).to_contain_text('Foto tambahan:')
                page.locator('.scan-result').last.get_by_role('button',name='Konfirmasi produk ini',exact=True).click()
                expect(page.locator('.medicine-card').last).to_contain_text('PANADOL')
                results.append(dict(width=width,passed=True,real_ocr=True,scan_requests=len(requests)))
                context.close()
            browser.close()
        assert not errors,errors
        print(json.dumps(dict(results=results,js_errors=errors),indent=2))
    finally:
        server.shutdown()
        with app.app_context():db.session.remove();db.drop_all()

if __name__=='__main__':main()
