"""Browser QA for shared containers, branding and existing navigation.
Uses the disposable preview database; never reads .env or writes application data.
Optional BROWSER_EXECUTABLE selects an already installed Chromium.
"""
import json
import os
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server
from preview import preview_app

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'qa' / 'layout-navbar'
OUT.mkdir(parents=True, exist_ok=True)
checks = []
errors = []


def check(name, passed, details=None):
    checks.append({'check': name, 'pass': bool(passed), 'details': details})


server = make_server('127.0.0.1', 5057, preview_app(), threaded=True)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = 'http://127.0.0.1:5057'
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, executable_path=os.environ.get('BROWSER_EXECUTABLE') or None,
            args=['--no-sandbox'],
        )
        for role in ['public', 'citizen', 'admin']:
            context = browser.new_context(reduced_motion='reduce')
            # Navigation and local branding do not depend on the map CDN.
            context.route('https://unpkg.com/**', lambda route: route.abort())
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            if role != 'public':
                page.goto(base + '/login')
                page.locator('#email').fill(('warga' if role == 'citizen' else 'admin') + '.demo@sehatwarga.test')
                page.locator('#password').fill('WargaDemo123!' if role == 'citizen' else 'AdminDemo123!')
                page.locator('button[type=submit]').last.click()
                page.wait_for_url('**/dashboard')
            for width, height in [(1366,768), (1440,900), (1920,1080), (1024,768), (768,1024), (375,812), (320,740)]:
                label = f'{role} {width}x{height}'
                page.set_viewport_size({'width': width, 'height': height})
                page.goto(base + '/', wait_until='domcontentloaded')
                page.evaluate('document.fonts.ready')
                metrics = page.evaluate('''() => {
                  const content = selector => {
                    const el = document.querySelector(selector), r = el.getBoundingClientRect(), s = getComputedStyle(el);
                    return [r.left + parseFloat(s.paddingLeft), r.right - parseFloat(s.paddingRight)];
                  };
                  const logo = document.querySelector('.navbar-brand img');
                  const slides = [...document.querySelectorAll('.service-slide')];
                  return {
                    containers: ['.navbar-container','.quick-services-layout','.directory-container','.journey-container','.about-layout','.footer-content'].map(content),
                    overflow: document.documentElement.scrollWidth > innerWidth,
                    navbarHeight: document.querySelector('.navbar').getBoundingClientRect().height,
                    serviceCount: slides.length,
                    visibleServices: slides.filter(el => !el.hidden).length,
                    logoLoaded: logo.complete && logo.naturalWidth > 0,
                    logoRatio: logo.width / logo.height,
                    logoWidth: logo.getBoundingClientRect().width,
                    mobileCollision: innerWidth < 1024 && document.querySelector('.navbar-brand').getBoundingClientRect().right > document.querySelector('#nav-toggle').getBoundingClientRect().left,
                    collision: innerWidth >= 1024 && !document.body.classList.contains('admin-shell') && document.querySelector('.navbar-brand').getBoundingClientRect().right > document.querySelector('.site-navigation').getBoundingClientRect().left
                  };
                }''')
                check(label + ' no overflow or navbar collision', not metrics['overflow'] and not metrics['collision'], metrics)
                check(label + ' mobile logo and menu do not overlap', not metrics['mobileCollision'])
                if width in [320, 375, 1440, 1920]:
                    page.screenshot(path=str(OUT / f'{role}-navbar-{width}.png'))
                if role != 'admin':
                    check(label + ' shared container edges', all(abs(v[0]-metrics['containers'][0][0]) < 1 and abs(v[1]-metrics['containers'][0][1]) < 1 for v in metrics['containers']))
                check(label + ' navbar 70px', metrics['navbarHeight'] == 70)
                check(label + ' proportional loaded logo', metrics['logoLoaded'] and abs(metrics['logoRatio']-3) < .06)
                if width >= 1024:
                    check(label + ' one service panel from four services', metrics['serviceCount'] == 4 and metrics['visibleServices'] == 1)
                    check(label + ' desktop logo width', 180 <= metrics['logoWidth'] <= 210)
                else:
                    page.locator('#nav-toggle').click()
                    expect(page.locator('#nav-close')).to_be_focused()
                    check(label + ' drawer opens without overflow', page.locator('#nav-toggle').get_attribute('aria-expanded') == 'true' and page.locator('#site-navigation').evaluate('el => el.scrollWidth <= el.clientWidth'))
                    page.keyboard.press('Shift+Tab')
                    check(label + ' drawer focus trap', page.locator('#site-navigation').evaluate('el => el.contains(document.activeElement)'))
                    if role != 'public':
                        page.locator('.user-menu > summary').click()
                        expect(page.locator('.user-menu button[type=submit]')).to_be_visible()
                        page.screenshot(path=str(OUT / f'{role}-drawer-{width}.png'))
                        page.locator('.user-menu > summary').click()
                    page.keyboard.press('Escape')
                    check(label + ' escape closes and restores focus', page.locator('#nav-toggle').get_attribute('aria-expanded') == 'false' and page.locator('#nav-toggle').evaluate('el => el === document.activeElement'))
                if role == 'citizen' and width >= 1024:
                    page.locator('.nav-dropdown:not(.user-menu) > summary').click()
                    expect(page.get_by_role('link', name='Keluarga', exact=True)).to_be_visible()
                    page.locator('.user-menu > summary').click()
                    check(label + ' opening profile closes administration', not page.locator('.nav-dropdown:not(.user-menu)').evaluate('el => el.open'))
                    expect(page.get_by_role('link', name='Profil Saya')).to_be_visible()
                    page.screenshot(path=str(OUT / f'citizen-profile-{width}.png'))
                    page.keyboard.press('Escape')
                    check(label + ' escape closes dropdown', not page.locator('.user-menu').evaluate('el => el.open'))
                    page.locator('.user-menu > summary').click()
                    page.locator('.services-intro-label').click()
                    check(label + ' outside click closes dropdown', not page.locator('.user-menu').evaluate('el => el.open'))
                # All existing navbar destinations, including closed dropdown links, resolve.
                links = page.locator('#site-navigation a').evaluate_all('els => els.map(el => el.href)')
                check(label + ' navigation destinations resolve', all(page.request.get(link).status == 200 for link in links))
            paths = ['/login', '/assistant'] if role == 'public' else (['/citizen/dashboard', '/citizen/profile', '/citizen/card', '/citizen/family'] if role == 'citizen' else ['/admin/dashboard'])
            for width in [375, 1440]:
                page.set_viewport_size({'width': width, 'height': 900})
                for path in paths:
                    response = page.goto(base + path, wait_until='domcontentloaded')
                    check(f'{role} {path} {width} renders with shared logo', response.status == 200 and page.locator('.navbar-brand .site-logo').evaluate('el => el.complete && el.naturalWidth > 0'))
                    check(f'{role} {path} {width} no overflow', page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                    page.screenshot(path=str(OUT / f'{role}-{path.strip("/").replace("/", "-")}-{width}.png'), full_page=True)
            if role == 'citizen':
                page.goto(base + '/citizen/family')
                check('administration active indicator follows submenu route', page.locator('.nav-dropdown:not(.user-menu) .active').count() == 1)
            if role != 'public':
                if width < 1024:
                    page.locator('#nav-toggle').click()
                page.locator('.user-menu > summary').click()
                page.locator('.user-menu button[type=submit]').click()
                check(role + ' existing logout form succeeds', page.locator('.nav-actions a[href="/login"]').count() == 1)
            context.close()
        browser.close()
finally:
    server.shutdown()
check('no JavaScript exceptions', not errors, errors)
(OUT / 'checks.json').write_text(json.dumps(checks, indent=2))
failures = [item for item in checks if not item['pass']]
print(json.dumps({'checks': len(checks), 'failures': failures}, indent=2))
raise SystemExit(bool(failures))
