"""Browser checks for GPS routing, using isolated SQLite and mocked Mapbox."""
import json
import logging
import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from preview import preview_app
from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server

logging.getLogger('werkzeug').setLevel(logging.ERROR)
app = preview_app()
app.config['MAPBOX_PUBLIC_TOKEN'] = 'pk.fixture'
server = make_server('127.0.0.1', 0, app, threaded=True)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{server.server_port}'
FACILITIES = [
    dict(id='poi-a', name='Klinik Uji', lat=-7.12, lng=112.42, address='Jalan Uji 1'),
    dict(id='poi-b', name='Rumah Sakit Uji', lat=-7.13, lng=112.43, address='Jalan Uji 2'),
]
ROUTE = dict(code='Ok', routes=[dict(distance=2400, duration=480, geometry=dict(type='LineString', coordinates=[[112.4, -7.1], [112.41, -7.11], [112.42, -7.12]]))])
STUB = r"""
window.__maps=[];window.__markers=[];
class FakeMap {
  constructor(options){this.container=options.container;this.sources={};this.layers={};this.events={};window.__maps.push(this);}
  addControl(){} on(event,fn){(this.events[event] ||= []).push(fn);if(event==='load')setTimeout(fn,10);}
  isStyleLoaded(){return true;} getSource(id){return this.sources[id];} getLayer(id){return this.layers[id];}
  addSource(id,data){this.sources[id]=data;} removeSource(id){delete this.sources[id];}
  addLayer(layer){this.layers[layer.id]=layer;} removeLayer(id){delete this.layers[id];}
  fitBounds(bounds){this.bounds=bounds;} flyTo(){} resize(){}
}
class FakeMarker {
  constructor(){this.element=document.createElement('button');this.element.className='fixture-marker';window.__markers.push(this);}
  setLngLat(point){this.point=point;return this;} setPopup(popup){this.popup=popup;return this;}
  addTo(map){this.map=map;map.container.append(this.element);return this;}
  getElement(){return this.element;} getPopup(){return this.popup;}
  getLngLat(){return {lng:this.point[0],lat:this.point[1]};}
  togglePopup(){this.popup.open=!this.popup.open;if(this.popup.open)this.map.container.append(this.popup.node);else this.popup.node.remove();return this;}
  remove(){this.element.remove();this.popup?.node.remove();}
}
class FakePopup {
  setDOMContent(node){this.node=node;return this;} isOpen(){return !!this.open;}
}
class Bounds {constructor(){this.points=[];}extend(p){this.points.push(p);return this;}}
window.mapboxgl={supported:()=>true,Map:FakeMap,Marker:FakeMarker,Popup:FakePopup,NavigationControl:class{},LngLatBounds:Bounds};
"""

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('BROWSER_EXECUTABLE') or None, args=['--no-sandbox'])
    context = browser.new_context(permissions=['geolocation'], geolocation={'latitude': -7.1, 'longitude': 112.4}, reduced_motion='reduce')
    context.add_init_script(STUB)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/facilities/mapbox-search?*', lambda route: route.fulfill(json={'facilities': FACILITIES}))
    directions = []
    reply = {'status': 200, 'json': ROUTE}
    def respond(route):
        directions.append(route.request.url)
        route.fulfill(**reply)
    page.route('https://api.mapbox.com/directions/**', respond)
    page.route('https://api.mapbox.com/mapbox-gl-js/**', lambda route: route.abort())
    try:
        page.goto(base)
        page.locator('[data-mapbox-directory]').scroll_into_view_if_needed()
        cards = page.locator('.mapbox-result-card')
        expect(cards).to_have_count(2)
        cards.first.click()
        expect(page.locator('.facility-route-summary')).to_contain_text('Aktifkan lokasi GPS')
        assert not directions, 'Routing requested before GPS consent'
        page.locator('.facility-route').get_by_role('button', name='Gunakan Lokasi Saya').click()
        expect(page.locator('.facility-route-summary')).to_contain_text('2,4 km · sekitar 8 menit · Mobil')
        assert '/driving/112.4,-7.1;112.42,-7.12?' in directions[-1]
        assert page.evaluate("!!window.__maps[0].layers['facility-directions-line']")
        assert page.evaluate("window.__maps[0].sources['facility-directions'].data.geometry.coordinates.length") == 3
        assert 'origin=-7.1%2C112.4' in page.get_by_role('link', name='Buka navigasi Google Maps').get_attribute('href')
        page.get_by_label('Cara perjalanan', exact=True).select_option('walking')
        expect(page.locator('.facility-route-summary')).to_contain_text('Jalan kaki')
        assert '/walking/' in directions[-1]
        cards.nth(1).click()
        expect(page.locator('.facility-route h3')).to_have_text('Rute ke Rumah Sakit Uji')
        expect(page.locator('.facility-route-summary')).to_contain_text('2,4 km')
        assert ';112.43,-7.13?' in directions[-1]
        # Selecting a map marker also changes the route destination.
        page.evaluate("window.__markers.find(m=>m.facilityId==='poi-a').getElement().click()")
        expect(page.locator('.facility-route h3')).to_have_text('Rute ke Klinik Uji')
        expect(page.locator('.facility-route-summary')).to_contain_text('2,4 km')
        for width in [1920, 768, 390, 360]:
            page.set_viewport_size({'width': width, 'height': 950})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), width
            panel = page.locator('.facility-route').bounding_box()
            assert panel['x'] >= 0 and panel['x'] + panel['width'] <= width, width
        print('GPS, road geometry, duration, modes, selection and responsive layout: OK')
        reply['json'] = {'code': 'NoRoute', 'routes': []}
        page.get_by_label('Cara perjalanan', exact=True).select_option('cycling')
        expect(page.locator('.facility-route-summary')).to_contain_text('Jalur tidak ditemukan')
        assert page.evaluate("!window.__maps[0].sources['facility-directions']")
        assert 'travelmode=bicycling' in page.get_by_role('link', name='Buka navigasi Google Maps').get_attribute('href')
        reply.update(status=403, json={'message': 'Denied'})
        page.get_by_role('button', name='Hitung ulang').click()
        expect(page.locator('.facility-route-summary')).to_contain_text('Rute belum dapat dimuat')
        reply.update(status=200, json=ROUTE)
        page.get_by_role('button', name='Hitung ulang').click()
        expect(page.locator('.facility-route-summary')).to_contain_text('2,4 km')
        # A late response must not restore a route after it was cleared.
        page.evaluate("""()=>{window.__fetch=window.fetch;window.fetch=(url,opts)=>String(url).includes('/directions/')?new Promise(resolve=>window.__finishRoute=()=>resolve(new Response(JSON.stringify(%s),{status:200}))):window.__fetch(url,opts);}""" % json.dumps(ROUTE))
        page.get_by_role('button', name='Hitung ulang').click()
        expect(page.locator('.facility-route-summary')).to_contain_text('Menghitung')
        page.get_by_role('button', name='Hapus rute').click()
        page.evaluate('window.__finishRoute()')
        expect(page.locator('.facility-route')).to_be_hidden()
        assert page.evaluate("!window.__maps[0].sources['facility-directions']")
        print('No route, failed API, retry, clear and stale response: OK')
        page.reload()
        page.locator('[data-mapbox-directory]').scroll_into_view_if_needed()
        expect(page.locator('.mapbox-result-card')).to_have_count(2)
        page.evaluate("Object.defineProperty(navigator,'geolocation',{configurable:true,value:{getCurrentPosition:(ok,fail)=>fail({code:1})}})")
        before = len(directions)
        page.locator('[data-mapbox-location]').click()
        expect(page.locator('[data-mapbox-status]')).to_contain_text('Lokasi tidak diizinkan')
        assert len(directions) == before
        print('Denied GPS: OK')
        # Internal directory and facility details use the same router.
        page.goto(base + '/facilities/1')
        page.get_by_role('button', name='Lihat rute dari lokasi saya').click()
        expect(page.locator('.facility-route-summary')).to_contain_text('2,4 km')
        a, b, c = [[112.4,-7.1], [112.41,-7.11], [112.42,-7.12]]
        ROUTE['routes'][0]['legs'] = [{'steps': [
            {'geometry': {'coordinates': points}, 'maneuver': {'type': kind, 'modifier': 'left'}, 'name': name}
            for points, kind, name in [([a,b], 'depart', ''), ([b,c], 'turn', 'Jalan Veteran'), ([c,c], 'arrive', '')]
        ]}]
        page.add_init_script("""window.spoken=[];
            Object.defineProperty(window,'speechSynthesis',{value:{getVoices:()=>[{lang:'id-ID'}],
                speak:u=>spoken.push(u.text),cancel:()=>{},addEventListener:()=>{}}});
            window.SpeechSynthesisUtterance=class {constructor(text){this.text=text}};
            navigator.geolocation.watchPosition=(fn,fail)=>{window.gpsError=fail;window.fix=(longitude,latitude,accuracy=5)=>fn({coords:{latitude,longitude,accuracy}});return 7};
            navigator.geolocation.clearWatch=id=>window.cleared=id;""")
        page.goto(base + '/facilities')
        expect(cards).to_have_count(2)
        cards.first.click()
        expect(page.locator('[data-place-name]')).to_have_text('Klinik Uji')
        expect(page.locator('[data-place-address]')).to_have_text('Jalan Uji 1')
        page.locator('.facility-route').get_by_role('button', name='Gunakan Lokasi Saya').click()
        expect(page.locator('.facility-route-summary')).to_contain_text('2,4 km')
        print('Internal facilities and detail page GPS routing: OK')
        page.get_by_role('button',name='Mulai Rute').click()
        guidance = page.locator('.facility-guidance-text')
        page.evaluate('gpsError({code:3})')
        expect(guidance).to_contain_text('Waktu pencarian GPS habis')
        expect(page.locator('.facility-guidance ol')).to_be_visible()
        page.evaluate('fix(112.4,-7.1,100)')
        expect(guidance).to_contain_text('±100 m')
        expect(page.locator('.facility-guidance ol')).to_contain_text('Jalan Veteran')
        page.evaluate('fix(112.4,-7.1)')
        expect(guidance).to_contain_text('belok kiri menuju Jalan Veteran')
        assert page.evaluate('spoken.at(-1)') == guidance.inner_text()
        page.get_by_role('button',name='Matikan suara').click()
        count = page.evaluate('spoken.length')
        page.evaluate('fix(112.411,-7.111)')
        expect(guidance).to_contain_text('tiba di tujuan')
        assert page.evaluate('spoken.length') == count
        page.get_by_role('button',name='Aktifkan suara').click()
        page.get_by_role('button',name='Ulangi petunjuk').click()
        assert page.evaluate('spoken.length') == count + 2
        before = len(directions)
        page.evaluate('for(let i=0;i<3;i++)fix(112.39,-7.13)')
        expect(guidance).to_contain_text('Jalur diperbarui')
        assert len(directions) == before + 1 and '112.39,-7.13;' in directions[-1]
        page.evaluate('fix(112.42,-7.12)')
        expect(guidance).to_contain_text('sudah dekat dengan Klinik Uji')
        assert page.evaluate('cleared') == 7
        page.get_by_role('button',name='Mulai Rute').click()
        page.get_by_role('button',name='Akhiri Rute').click()
        page.evaluate('fix(112.4,-7.1)')
        expect(guidance).to_have_text('Navigasi diakhiri.')
        print('Guidance progression, voice controls, low accuracy, reroute, arrival and stop: OK')
        assert 'Klinik+Uji' in page.locator('[data-google-reference]').get_attribute('href')
        expect(page.locator('[data-clinic-info]')).to_contain_text('belum tersedia')
        FACILITIES[1].update(name='UGD RSUD Dr Soegiri',address='Lamongan, 62214, Indonesia')
        page.reload()
        cards.nth(1).click()
        expect(page.locator('[data-clinic-info] a')).to_have_attribute('href','https://rsud-soegiri.lamongankab.go.id/layanan/149')
        app.config['GOOGLE_PLACES_BROWSER_KEY'] = 'test-browser-key'
        page.route('https://maps.googleapis.com/maps/api/js?*', lambda route: route.fulfill(
            content_type='application/javascript',body="""window.google={maps:{importLibrary:async()=>({
              Place:{searchByText:async()=>({places:[{id:'test-id',displayName:'Klinik Uji',location:{lat:()=>-7.12,lng:()=>112.42}}]})}
            })}};"""))
        page.reload()
        cards.first.click()
        page.get_by_role('button',name='Tampilkan detail Google Maps').click()
        expect(page.locator('gmp-place-details-place-request')).to_have_attribute('place','test-id')
        assert page.locator('gmp-place-reviews,gmp-place-rating,gmp-place-opening-hours').count()==3
        cards.nth(1).click()
        page.get_by_role('button',name='Tampilkan detail Google Maps').click()
        expect(page.locator('[data-google-info]')).to_contain_text('belum dapat dicocokkan')
        assert page.locator('gmp-place-details').count()==0
        print('Official clinic schedule, external fallback and mocked Google profile matching: OK')
        assert not errors, errors
    finally:
        browser.close()
        server.shutdown()
