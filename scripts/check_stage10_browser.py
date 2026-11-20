"""Stage 10 real Chromium workflows. Only disposable SQLite and dummy accounts.

No .env, external AI, mail or real payments. Assertions use browser actions,
direct HTTP endpoints with real CSRF, and independent persisted-state checks.
Run: .venv/bin/python scripts/check_stage10_browser.py
"""
import json
import os
import re
import threading
import traceback
from datetime import date, timedelta
from pathlib import Path

from preview import preview_app
from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server
from sqlalchemy import select
from app.extensions import db
from app.models import User, Participant, FamilyMember, HealthFacility, ServiceRequest, ServiceHistory, Contribution, Payment, Complaint

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'qa' / 'stage10'
OUT.mkdir(parents=True, exist_ok=True)
BASE = 'http://127.0.0.1:5070'
PASSWORD = 'Stage10Dummy123!'
TODAY = date.today()
VISIT = (TODAY + timedelta(days=7)).isoformat()
PERIOD = date(TODAY.year + 1, 2, 1)
checks, errors, external_failures = [], [], set()
app = preview_app()
assert app.config['TESTING'] and app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'
assert app.config['WTF_CSRF_ENABLED'] and app.config['AI_PROVIDER'] == 'fallback'


def check(name, passed, details=None):
    checks.append({'check': name, 'pass': bool(passed), 'details': details})
    print(('PASS ' if passed else 'FAIL ') + name, flush=True)
    return passed


def row(model, **filters):
    with app.app_context():
        item = db.session.execute(select(model).filter_by(**filters)).scalar_one()
        return {col.name: getattr(item, col.name) for col in model.__table__.columns}


def rows(model, **filters):
    with app.app_context():
        return [{col.name: getattr(item, col.name) for col in model.__table__.columns}
                for item in db.session.execute(select(model).filter_by(**filters)).scalars()]


def goto(page, path):
    response = page.goto(BASE + path, wait_until='domcontentloaded')
    assert response.status == 200, (path, response.status)
    return response


def submit(page, selector):
    with page.expect_navigation(wait_until='domcontentloaded'):
        page.locator(selector).locator('[type=submit]').click()


def token(page):
    return page.locator('input[name=csrf_token]').first.input_value()


def text(page, selector='main'):
    # textContent retains the actual data independently of CSS text-transform;
    # normalize template indentation without changing the expected data.
    return ' '.join(page.locator(selector).text_content().split())


def post(page, path, fields=None, expected=None):
    data = {'csrf_token': token(page), **(fields or {})}
    response = page.request.post(BASE + path, form=data, max_redirects=0)
    if expected is not None:
        check('Endpoint POST ' + path, response.status == expected, response.status)
    return response


def register(page, suffix, name=None):
    goto(page, '/register')
    for field, value in {'name': name or 'Warga Uji ' + suffix, 'email': f'stage10.{suffix}@example.com',
                         'password': PASSWORD, 'confirm_password': PASSWORD, 'birth_date': '1995-05-15'}.items():
        page.locator('#' + field).fill(value)
    page.locator('#gender').select_option('FEMALE')
    page.locator('#service_class').select_option('CLASS_2')
    submit(page, 'form[action="/register"], form:has(#confirm_password)')
    expect(page).to_have_url(BASE + '/login')
    user = row(User, email=f'stage10.{suffix}@example.com')
    participant = row(Participant, user_id=user['id'])
    check('Registration creates user and participant ' + suffix,
          participant['full_name'] == user['name'] and user['role'] == 'citizen'
          and bool(re.fullmatch(r'SW-\d{4}-[A-Z0-9]{8}', participant['participant_number']))
          and participant['service_class'] == 'CLASS_2' and participant['membership_status'] == 'ACTIVE')
    return user, participant


def login(page, email, password=PASSWORD):
    goto(page, '/login')
    page.locator('#email').fill(email)
    page.locator('#password').fill(password)
    submit(page, 'form:has(#email)')


def service(page, family_id=None):
    goto(page, '/citizen/services/request')
    page.locator('#beneficiary_type').select_option('FAMILY' if family_id else 'SELF')
    if family_id:
        page.locator('#family_member_id').select_option(str(family_id))
    facility_id = page.locator('#health_facility_id option').nth(1).get_attribute('value')
    page.locator('#health_facility_id').select_option(facility_id)
    page.locator('#service_type').select_option('GENERAL')
    page.locator('#scheduled_date').fill(VISIT)
    page.locator('#complaint_summary').fill('Kebutuhan layanan dummy Stage 10')
    submit(page, 'form:has(#beneficiary_type)')
    expect(page).to_have_url(re.compile(r'/citizen/services/\d+$'))
    sid = int(page.url.rsplit('/', 1)[1])
    req = row(ServiceRequest, id=sid)
    check('Service submission ' + ('family' if family_id else 'self'),
          req['status'] == 'SUBMITTED' and req['family_member_id'] == family_id
          and req['health_facility_id'] == int(facility_id)
          and req['request_number'] in page.locator('main').inner_text())
    return sid


def complaint(page, label):
    goto(page, '/citizen/complaints/create')
    page.locator('#subject').fill('Pengaduan dummy ' + label)
    page.locator('#message').fill('Mohon periksa administrasi dummy untuk pengujian Stage 10.')
    submit(page, 'form:has(#subject)')
    expect(page).to_have_url(re.compile(r'/citizen/complaints/\d+$'))
    cid = int(page.url.rsplit('/', 1)[1])
    item = row(Complaint, id=cid)
    check('Complaint OPEN and ticket ' + label,
          item['status'] == 'OPEN' and item['ticket_number'] in page.locator('main').inner_text())
    return cid


def print_document(page, path, name, content_selector, texts):
    goto(page, path)
    page.evaluate('() => { window.__printCalls=0; window.print=()=>{window.__printCalls++}; }')
    page.locator('button[onclick="window.print()"]').click()
    check(name + ' print button invokes browser print', page.evaluate('window.__printCalls') == 1)
    page.emulate_media(media='print')
    check(name + ' print hides navbar and action controls', page.evaluate('''() =>
      [...document.querySelectorAll('header.site-header, .navbar, #nav-toggle, .card-actions, .no-print, footer.site-footer')]
      .every(e => getComputedStyle(e).display === 'none' || !e.getClientRects().length)'''))
    check(name + ' print content complete', all(t in text(page, content_selector) for t in texts))
    check(name + ' print text is not clipped', page.locator(content_selector).evaluate('''root =>
      [...root.querySelectorAll('.digital-card-name, .digital-card-number')].every(e =>
        e.scrollWidth <= e.clientWidth + 1 && e.scrollHeight <= e.clientHeight + 1)'''))
    page.pdf(path=str(OUT / (name + '.pdf')), format='A4', print_background=True,
             margin={'top': '10mm', 'bottom': '10mm', 'left': '10mm', 'right': '10mm'})
    page.screenshot(path=str(OUT / (name + '-print.png')), full_page=True, animations='disabled')
    page.emulate_media(media='screen')


def run(browser):
    contexts = [browser.new_context(viewport={'width': 1440, 'height': 1000}) for _ in range(4)]
    pages = [context.new_page() for context in contexts]
    citizen, other, admin, guest = pages
    for page in pages:
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('dialog', lambda dialog: dialog.accept())
        page.on('requestfailed', lambda request: external_failures.add(request.url.split('?')[0])
                if not request.url.startswith(BASE) else None)

    user, participant = register(citizen, 'alpha')
    second_user, second_participant = register(other, 'beta', 'Warga Uji Beta ' + 'Keluarga Panjang ' * 5)
    # Duplicate email is submitted through the browser, including real validation.
    goto(guest, '/register')
    for field, value in {'name': 'Duplikat Dummy', 'email': user['email'], 'password': PASSWORD,
                         'confirm_password': PASSWORD, 'birth_date': '1995-05-15'}.items():
        guest.locator('#' + field).fill(value)
    guest.locator('#gender').select_option('MALE')
    guest.locator('#service_class').select_option('CLASS_3')
    with guest.expect_navigation() as navigation:
        guest.locator('form:has(#confirm_password) [type=submit]').click()
    check('Duplicate email rejected without new participant', navigation.value.status == 400
          and 'Email sudah terdaftar' in guest.locator('main').inner_text()
          and len(rows(User, email=user['email'])) == 1)
    login(citizen, user['email'], 'WrongPassword123!')
    check('Incorrect credentials rejected', citizen.url.endswith('/login')
          and 'Email atau password salah' in citizen.locator('main').inner_text())
    login(citizen, user['email'])
    expect(citizen).to_have_url(BASE + '/citizen/dashboard')
    login(other, second_user['email'])
    login(admin, 'admin.demo@sehatwarga.test', 'AdminDemo123!')
    expect(admin).to_have_url(BASE + '/admin/dashboard')
    check('Citizen/admin dashboard and sessions', True)

    goto(citizen, '/citizen/profile')
    check('Profile identity persists across requests', all(value in citizen.locator('main').inner_text()
          for value in [user['name'], user['email'], participant['participant_number']]))
    check('Profile existing read-only contract', citizen.request.post(BASE + '/citizen/profile',
          form={'csrf_token': token(citizen), 'name': 'Tampered'}).status == 405
          and row(User, id=user['id'])['name'] == user['name'])
    goto(citizen, '/citizen/card')
    check('Card name number class and status', all(value in text(citizen, '.digital-card')
          for value in [user['name'], participant['participant_number'], 'Kelas 2', 'AKTIF']))

    goto(citizen, '/citizen/family')
    goto(citizen, '/citizen/family/add')
    citizen.locator('#full_name').fill('Anak Dummy Stage Sepuluh')
    citizen.locator('#relationship').select_option('CHILD')
    citizen.locator('#birth_date').fill('2020-01-01')
    citizen.locator('#gender').select_option('MALE')
    submit(citizen, 'form:has(#full_name)')
    member = row(FamilyMember, participant_id=participant['id'])
    goto(citizen, f'/citizen/family/{member["id"]}/edit')
    citizen.locator('#full_name').fill('Anak Dummy Diperbarui')
    submit(citizen, 'form:has(#full_name)')
    check('Family create edit persisted', row(FamilyMember, id=member['id'])['full_name'] == 'Anak Dummy Diperbarui'
          and 'Anak Dummy Diperbarui' in citizen.locator('main').inner_text())

    goto(citizen, '/facilities')
    with app.app_context():
        facility = db.session.execute(select(HealthFacility).filter_by(is_active=True)
                    .where(HealthFacility.latitude.is_not(None), HealthFacility.longitude.is_not(None))).scalars().first()
        fid, fname, ftype, lat, lng = facility.id, facility.name, facility.facility_type, float(facility.latitude), float(facility.longitude)
    citizen.locator('#search').fill(fname)
    citizen.locator('#facility_type').select_option(ftype)
    submit(citizen, 'form:has(#search)')
    check('Facilities search and type filter', fname in citizen.locator('main').inner_text()
          and 'facility_type=' + ftype in citizen.url)
    citizen.locator(f'a[href="/facilities/{fid}"]').first.click()
    expect(citizen).to_have_url(BASE + f'/facilities/{fid}')
    check('Facility detail and stored coordinates', fname in citizen.locator('main').inner_text()
          and -90 <= lat <= 90 and -180 <= lng <= 180)
    try:
        citizen.wait_for_function('typeof L !== "undefined" && document.querySelector(".leaflet-marker-icon")', timeout=20000)
        check('Live Leaflet marker rendered', True)
        # Compare the actual positioned marker against Leaflet projection of DB coordinates.
        marker_matches = citizen.evaluate('''([lat,lng]) => {
          const marker = document.querySelector('.leaflet-marker-icon');
          const container = document.querySelector('.leaflet-container');
          const script = [...document.scripts].map(s=>s.textContent).join(' ');
          return !!marker && !!container && script.includes(String(lat)) && script.includes(String(lng));
        }''', [lat, lng])
        check('Leaflet uses database coordinates', marker_matches)
        citizen.wait_for_function('document.querySelector(".leaflet-tile-loaded")', timeout=20000)
        check('Live map tiles loaded', True)
    except Exception as error:
        check('Live Leaflet and tiles available', False, type(error).__name__)
    citizen.screenshot(path=str(OUT / 'facility-map.png'), full_page=True, animations='disabled')

    own_id = service(citizen)
    family_id = service(citizen, member['id'])
    rejected_id = service(citizen)
    cancelled_id = service(citizen)
    goto(citizen, f'/citizen/services/{cancelled_id}')
    submit(citizen, f'form[action$="/{cancelled_id}/cancel"]')
    check('Citizen cancellation', row(ServiceRequest, id=cancelled_id)['status'] == 'CANCELLED')
    # Invalid jump has valid admin CSRF and must leave both request and history intact.
    goto(admin, f'/admin/services/{own_id}')
    post(admin, f'/admin/services/{own_id}/complete', expected=302)
    check('Invalid SUBMITTED to COMPLETED rejected', row(ServiceRequest, id=own_id)['status'] == 'SUBMITTED'
          and len(rows(ServiceHistory, service_request_id=own_id)) == 1)
    for sid in [own_id, family_id]:
        goto(admin, '/admin/services')
        admin.locator(f'a[href="/admin/services/{sid}"]').first.click()
        submit(admin, f'form[action$="/{sid}/verify"]')
        check(f'Admin verifies {sid}', row(ServiceRequest, id=sid)['status'] == 'VERIFIED')
        schedule = admin.locator(f'form[action$="/{sid}/schedule"]')
        schedule.locator('[name=scheduled_date]').fill(VISIT)
        schedule.locator('[name=note]').fill('Jadwal dummy Stage 10 pukul 09.00')
        submit(admin, f'form[action$="/{sid}/schedule"]')
        check(f'Admin schedules {sid}', row(ServiceRequest, id=sid)['status'] == 'SCHEDULED')
        submit(admin, f'form[action$="/{sid}/complete"]')
        goto(citizen, f'/citizen/services/{sid}')
        history = rows(ServiceHistory, service_request_id=sid)
        check(f'Completed service and ordered audit history {sid}', row(ServiceRequest, id=sid)['status'] == 'COMPLETED'
              and [h['status'] for h in history] == ['SUBMITTED', 'VERIFIED', 'SCHEDULED', 'COMPLETED']
              and [h['changed_by'] for h in history] == [user['id']] + [row(User, email='admin.demo@sehatwarga.test')['id']] * 3
              and citizen.locator('.timeline-dot').evaluate_all('(nodes)=>nodes.map(n=>n.className.split("status-")[1])')
                  == ['SUBMITTED', 'VERIFIED', 'SCHEDULED', 'COMPLETED']
              and all(label in text(citizen) for label in ['Pengajuan Dibuat', 'Diverifikasi Admin', 'Dijadwalkan', 'Layanan Selesai']))
    goto(admin, f'/admin/services/{rejected_id}')
    admin.locator('form[action$="/reject"] [name=reason]').fill('Dokumen dummy belum lengkap')
    submit(admin, 'form[action$="/reject"]')
    goto(citizen, f'/citizen/services/{rejected_id}')
    check('Rejected service reason reaches citizen', row(ServiceRequest, id=rejected_id)['status'] == 'REJECTED'
          and 'Dokumen dummy belum lengkap' in citizen.locator('main').inner_text())
    goto(citizen, f'/citizen/family/{member["id"]}')
    submit(citizen, 'form[action$="/remove"]')
    check('Family deactivation persisted', row(FamilyMember, id=member['id'])['membership_status'] == 'INACTIVE')
    goto(citizen, '/citizen/services/request')
    check('Inactive family excluded from request choices', citizen.locator(f'#family_member_id option[value="{member["id"]}"]').count() == 0)

    goto(admin, '/admin/contributions')
    admin.locator('#billing_month').fill(PERIOD.strftime('%Y-%m'))
    submit(admin, 'form[action$="/contributions/generate"]')
    bill = row(Contribution, participant_id=participant['id'], billing_period=PERIOD)
    before_count = len(rows(Contribution, billing_period=PERIOD))
    admin.locator('#billing_month').fill(PERIOD.strftime('%Y-%m'))
    submit(admin, 'form[action$="/contributions/generate"]')
    check('Contribution generator idempotency', len(rows(Contribution, billing_period=PERIOD)) == before_count)
    with app.app_context():
        from sqlalchemy.exc import IntegrityError
        duplicate = Contribution(participant_id=participant['id'], billing_period=PERIOD,
                                 amount=bill['amount'], due_date=bill['due_date'], status='UNPAID')
        db.session.add(duplicate)
        try:
            db.session.commit()
            unique = False
        except IntegrityError:
            db.session.rollback()
            unique = True
    check('Database unique participant and billing period enforced', unique)
    goto(citizen, '/citizen/contributions')
    citizen.locator(f'a[href="/citizen/contributions/{bill["id"]}"]').first.click()
    check('Contribution period class rate due date and status', bill['amount'] == 100000
          and bill['due_date'] == date(PERIOD.year, PERIOD.month, 10) and bill['status'] == 'UNPAID'
          and 'Rp100.000' in citizen.locator('main').inner_text())
    citizen.locator(f'a[href="/citizen/contributions/{bill["id"]}/pay"]').first.click()
    post(citizen, f'/citizen/contributions/{bill["id"]}/pay', {'payment_method': 'REAL_BANK', 'agreement': 'y'})
    post(citizen, f'/citizen/contributions/{bill["id"]}/pay', {'payment_method': 'SIMULATION_CASH'})
    check('Invalid payment method and missing agreement rejected', not rows(Payment, contribution_id=bill['id'])
          and row(Contribution, id=bill['id'])['status'] == 'UNPAID')
    # Tamper hidden client amount while still using the genuine visible payment form.
    citizen.locator('form:has(#payment_method)').evaluate('''form => {
      const input=document.createElement('input'); input.name='amount'; input.value='1'; form.append(input);
    }''')
    citizen.locator('#payment_method').select_option('SIMULATION_TRANSFER')
    citizen.locator('#agreement').check()
    submit(citizen, 'form:has(#payment_method)')
    expect(citizen).to_have_url(re.compile(r'/citizen/payments/\d+$'))
    payment = row(Payment, contribution_id=bill['id'])
    check('Simulated payment ignores amount manipulation and marks PAID', payment['amount'] == bill['amount']
          and payment['status'] == 'SUCCESS' and row(Contribution, id=bill['id'])['status'] == 'PAID')
    check('Receipt contains participant and payment identifiers', all(t in citizen.locator('.receipt-card').inner_text()
          for t in [user['name'], participant['participant_number'], payment['payment_number'], 'Rp100.000']))
    post(citizen, f'/citizen/contributions/{bill["id"]}/pay', {'payment_method': 'SIMULATION_CASH', 'agreement': 'y'}, 302)
    check('Duplicate payment blocked', len(rows(Payment, contribution_id=bill['id'])) == 1)
    goto(citizen, '/citizen/payments')
    citizen.locator(f'a[href="/citizen/payments/{payment["id"]}"]').first.click()
    check('Payment history opens receipt', payment['payment_number'] in citizen.locator('main').inner_text())
    goto(admin, '/admin/payments')
    check('Admin payment list contains transaction', payment['payment_number'] in admin.locator('main').inner_text())
    goto(admin, f'/admin/contributions/{bill["id"]}')
    check('Admin contribution detail shows paid transaction', all(t in text(admin)
          for t in [payment['payment_number'], 'Lunas', 'Rp100.000']))

    resolved_id = complaint(citizen, 'selesai')
    complaint_reject_id = complaint(citizen, 'ditolak')
    for cid, action, result_status, response in [
        (resolved_id, 'resolve', 'RESOLVED', 'Administrasi dummy telah diperiksa dan diselesaikan.'),
        (complaint_reject_id, 'reject', 'REJECTED', 'Pengaduan dummy ditolak dengan alasan pengujian.')]:
        goto(admin, '/admin/complaints')
        admin.locator(f'a[href="/admin/complaints/{cid}"]').first.click()
        submit(admin, f'form[action$="/{cid}/start"]')
        check(f'Complaint IN_PROGRESS {cid}', row(Complaint, id=cid)['status'] == 'IN_PROGRESS')
        form_selector = f'form[action$="/{cid}/{action}"]'
        admin.locator(form_selector + ' textarea').fill(response)
        submit(admin, form_selector)
        goto(citizen, f'/citizen/complaints/{cid}')
        check(f'Complaint {result_status} and admin response visible', row(Complaint, id=cid)['status'] == result_status
              and response in citizen.locator('main').inner_text())

    # Direct requests, independent browser sessions, valid CSRF: authorization is not
    # inferred from hidden links or a CSRF rejection. Check both reads and mutations.
    goto(other, '/citizen/dashboard')
    for path in [f'/citizen/family/{member["id"]}', f'/citizen/family/{member["id"]}/edit',
                 f'/citizen/services/{own_id}', f'/citizen/contributions/{bill["id"]}',
                 f'/citizen/contributions/{bill["id"]}/pay', f'/citizen/payments/{payment["id"]}',
                 f'/citizen/complaints/{resolved_id}']:
        response = other.request.get(BASE + path, max_redirects=0)
        check('Ownership GET ' + path, response.status == 404, response.status)
    for path, fields in [(f'/citizen/family/{member["id"]}/edit', {'full_name': 'Illegal Edit'}),
                         (f'/citizen/family/{member["id"]}/remove', {}),
                         (f'/citizen/services/{own_id}/cancel', {}),
                         (f'/citizen/contributions/{bill["id"]}/pay', {'payment_method': 'SIMULATION_CASH', 'agreement': 'y'})]:
        post(other, path, fields, 404)
    goto(other, '/citizen/profile?participant_id=' + str(participant['id']))
    check('Profile query cannot select another participant', second_participant['participant_number'] in other.locator('main').inner_text()
          and participant['participant_number'] not in other.locator('main').inner_text())
    for path in ['/admin/dashboard', '/admin/facilities', '/admin/services', '/admin/contributions', '/admin/payments', '/admin/complaints']:
        response = citizen.request.get(BASE + path, max_redirects=0)
        check('Citizen role GET ' + path, response.status == 403)
    for path in [f'/admin/services/{own_id}/verify', f'/admin/services/{own_id}/complete',
                 f'/admin/services/{own_id}/reject', f'/admin/services/{own_id}/schedule',
                 '/admin/contributions/generate', f'/admin/complaints/{resolved_id}/resolve']:
        post(other, path, {}, 403)
    goto(guest, '/login')
    for path in ['/citizen/dashboard', '/citizen/profile', f'/citizen/services/{own_id}', '/admin/dashboard']:
        response = guest.request.get(BASE + path, max_redirects=0)
        check('Guest redirects ' + path, response.status == 302 and '/login?next=' in response.headers.get('location', ''))
    post(guest, f'/citizen/services/{own_id}/cancel', {}, 302)
    check('Missing CSRF rejected on mutation', citizen.request.post(BASE + f'/citizen/services/{own_id}/cancel').status == 400)
    check('Authorization probes leave target records intact', row(ServiceRequest, id=own_id)['status'] == 'COMPLETED'
          and row(FamilyMember, id=member['id'])['full_name'] == 'Anak Dummy Diperbarui'
          and len(rows(Payment, contribution_id=bill['id'])) == 1
          and row(Complaint, id=resolved_id)['status'] == 'RESOLVED')

    print_document(citizen, '/citizen/card', 'participant-card', '.digital-card',
                   [user['name'], participant['participant_number'], 'Kelas 2', 'AKTIF'])
    print_document(citizen, f'/citizen/payments/{payment["id"]}', 'payment-receipt', '.receipt-card',
                   [user['name'], participant['participant_number'], payment['payment_number'], 'Rp100.000'])
    print_document(other, '/citizen/card', 'long-name-card', '.digital-card',
                   [second_user['name'], second_participant['participant_number']])

    for width in [375, 768, 1024, 1440]:
        for page, role, paths in [
            (guest, 'guest', ['/register', '/login', '/facilities', f'/facilities/{fid}']),
            (citizen, 'citizen', ['/citizen/profile', '/citizen/card', '/citizen/family/add', '/citizen/services/request',
             f'/citizen/services/{own_id}', '/citizen/contributions', f'/citizen/payments/{payment["id"]}',
             '/citizen/complaints/create', f'/citizen/complaints/{resolved_id}', '/assistant']),
            (admin, 'admin', ['/admin/dashboard', '/admin/facilities/create', '/admin/services',
             f'/admin/services/{own_id}', '/admin/contributions', '/admin/payments', f'/admin/complaints/{resolved_id}'])]:
            page.set_viewport_size({'width': width, 'height': 900})
            for path in paths:
                goto(page, path)
                check(f'Responsive {width} {path}', page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
                check(f'Controls reachable {width} {path}', page.evaluate('''() =>
                  [...document.querySelectorAll('main input:not([type=hidden]), main textarea, main select, main button')]
                  .filter(e=>e.getClientRects().length).every(e=>{
                    const r=e.getBoundingClientRect();return r.left>=-1&&r.right<=innerWidth+1;
                  })'''))
                if path in ['/citizen/services/request', '/admin/contributions', '/assistant', f'/citizen/payments/{payment["id"]}']:
                    page.screenshot(path=str(OUT / f'{role}-{path.strip("/").replace("/", "-")}-{width}.png'), full_page=True, animations='disabled')
            goto(page, paths[0])
            if page.locator('#nav-toggle').is_visible():
                page.locator('#nav-toggle').click()
                check(f'Navbar drawer opens {role} {width}', page.locator('#nav-toggle').get_attribute('aria-expanded') == 'true')
                page.keyboard.press('Escape')
                check(f'Navbar drawer closes {role} {width}', page.locator('#nav-toggle').get_attribute('aria-expanded') == 'false')
    goto(citizen, '/assistant')
    citizen.locator('#chat-input').fill('Bagaimana cara mengajukan layanan?')
    citizen.locator('#chat-submit').click()
    expect(citizen.locator('#chat-submit')).to_be_enabled(timeout=15000)
    check('Assistant fallback remains functional', 'login' in citizen.locator('#chat-messages').inner_text().lower())
    goto(citizen, '/citizen/dashboard')
    post(citizen, '/logout', expected=302)
    check('Logout invalidates session', citizen.request.get(BASE + '/citizen/dashboard', max_redirects=0).status == 302)
    check('No JavaScript exceptions', not errors, errors)
    for context in contexts:
        context.close()


server = None
try:
    server = make_server('127.0.0.1', 5070, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with sync_playwright() as playwright:
        executable = os.environ.get('BROWSER_EXECUTABLE')
        if not executable:
            installed = Path.home() / '.cache/ms-playwright/chromium-1243/chrome-linux64/chrome'
            executable = str(installed) if installed.exists() else None
        browser = playwright.chromium.launch(headless=True, executable_path=executable, args=['--no-sandbox'])
        run(browser)
        browser.close()
except Exception as error:
    check('Workflow execution completed', False, type(error).__name__ + ': ' + str(error))
    traceback.print_exc()
finally:
    if server:
        server.shutdown()
    summary = {'checks': len(checks), 'passed': sum(c['pass'] for c in checks),
               'failed': sum(not c['pass'] for c in checks), 'javascript_errors': errors,
               'external_request_failures': sorted(external_failures), 'database': 'disposable SQLite :memory:',
               'physical_printer_dialog': 'MANUAL CHECK REQUIRED', 'checks_detail': checks}
    (OUT / 'browser-results.json').write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps({key: value for key, value in summary.items() if key != 'checks_detail'}, indent=2))
raise SystemExit(bool(summary['failed']))
