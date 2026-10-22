"""Disposable emulator QA: only demo cash orders, never an online payment."""
import json
import re
import subprocess
import time
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path('native-evidence')
OUT.mkdir(exist_ok=True)
PACKAGE = 'com.uniserve.mobile'
BASE = 'https://uniserve-api.onrender.com/api/v1'
qa_note = 'deployment-qa-native-' + str(uuid.uuid4())
student = staff = None
order_id = None
owns_cart = False
completed = False
pw = browser = page = None
cid = '83543334-2688-4c5d-9c83-ee201fac02bd'

def api(method, path, token=None, body=None):
    headers = {'Content-Type': 'application/json'}
    if token: headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(BASE + path, method=method, headers=headers,
        data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read()
        print('API', method, path, response.status, flush=True)
        return json.loads(raw) if raw else None

def login_api(role):
    return api('POST', '/auth/login', body={'university_email': role + '@demo.uniserve.pk', 'password': 'UniServe2026!'})['tokens']['access_token']

def wait_order_status(expected):
    for _ in range(15):
        order = api('GET', '/orders/' + order_id, student)
        if order['status'] == expected: return order
        time.sleep(2)
    raise AssertionError('Order did not reach expected status: ' + expected)

def adb(*args, binary=False):
    return subprocess.check_output(['adb', *args], text=not binary)

def dump():
    adb('shell', 'uiautomator', 'dump', '/sdcard/qa-window.xml')
    raw = adb('exec-out', 'cat', '/sdcard/qa-window.xml')
    return raw, ET.fromstring(raw)

def snap(name):
    (OUT / (name + '.png')).write_bytes(adb('exec-out', 'screencap', '-p', binary=True))
    raw, root = dump()
    (OUT / (name + '.xml')).write_text(raw)
    return root

def tap(node):
    bounds = list(map(int, re.findall(r'\d+', node.attrib['bounds'])))
    x1, y1, x2, y2 = bounds
    adb('shell', 'input', 'tap', str((x1+x2)//2), str((y1+y2)//2))

def wait_text(text, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        raw, root = dump()
        if text.lower() in raw.lower(): return root
        time.sleep(3)
    snap('failure-' + text.replace(' ', '-'))
    raise AssertionError('Screen text not reached: ' + text)

def link(path):
    adb('shell', 'am', 'start', '-W', '-a', 'android.intent.action.VIEW', '-d', 'uniserve:///' + path, PACKAGE)
    time.sleep(4)

try:
    adb('shell', 'svc', 'power', 'stayon', 'true')
    adb('shell', 'input', 'keyevent', '224')
    adb('shell', 'wm', 'dismiss-keyguard')
    adb('install', '-r', 'native-apk/app-release.apk')
    package_info = adb('shell', 'dumpsys', 'package', PACKAGE)
    assert re.search(r'\bversionCode=7\b', package_info) and 'versionName=0.1.6' in package_info, 'Expected fresh 0.1.6 / code 7 binary'
    adb('shell', 'monkey', '-p', PACKAGE, '-c', 'android.intent.category.LAUNCHER', '1')
    root = wait_text('Get Started', 90)
    snap('00-startup-welcome')
    entry = [n for n in root.iter('node') if n.attrib.get('content-desc', '').lower() == 'log in']
    assert entry, 'Welcome login navigation missing'
    tap(entry[0])
    wait_text('Welcome Back', 30)
    snap('01-startup-login')
    print('PASS native APK installs and startup reaches visible login', flush=True)
    link('register')
    wait_text('Create', 30)
    snap('02-registration-top')
    for _ in range(3):
        adb('shell', 'input', 'swipe', '500', '1500', '500', '400', '450')
        time.sleep(1)
    root = snap('03-registration-scrolled')
    sign_in = [n for n in root.iter('node') if n.attrib.get('text', '').lower() == 'sign in']
    assert sign_in, 'Registration sign-in link must be reachable after scrolling'
    print('PASS native registration bottom sign-in link reachable', flush=True)
    link('login')
    root = wait_text('Welcome Back', 30)
    fields = [n for n in root.iter('node') if n.attrib.get('class') == 'android.widget.EditText']
    assert len(fields) == 2, 'Expected email/password inputs'
    tap(fields[0]); adb('shell', 'input', 'text', 'student@demo.uniserve.pk')
    _, root = dump()
    fields = [n for n in root.iter('node') if n.attrib.get('class') == 'android.widget.EditText']
    tap(fields[1]); adb('shell', 'input', 'text', 'UniServe2026!')
    adb('shell', 'input', 'keyevent', '4')
    _, root = dump()
    buttons = [n for n in root.iter('node') if n.attrib.get('text', '').lower() == 'log in']
    assert buttons, 'Login action missing'
    tap(buttons[0])
    root = wait_text('Cafeteria', 90)
    time.sleep(8)
    _, root = dump()
    cafe = [n for n in root.iter('node') if n.attrib.get('text') == 'Student Cafeteria']
    if cafe: tap(cafe[0]); time.sleep(8)
    root = wait_text('Current cafeteria: Student Cafeteria', 30)
    labels = [n for n in root.iter('node') if n.attrib.get('content-desc', '').startswith('Current cafeteria: Student Cafeteria')]
    assert labels, 'Selected cafeteria must expose its visible label'
    bounds = list(map(int, re.findall(r'\d+', labels[0].attrib['bounds'])))
    assert bounds[3] - bounds[1] >= 80, 'Cafeteria selector must not collapse to a dot'
    snap('04-authenticated-menu')
    adb('shell', 'input', 'swipe', '500', '1500', '500', '400', '450')
    time.sleep(3)
    snap('05-menu-scrolled')
    print('PASS native demo login and menu screen capture', flush=True)
    student, staff = login_api('student'), login_api('staff')
    cart = api('GET', f'/cafeterias/{cid}/cart/', student)
    assert not cart['items'], 'Preserve pre-existing demo cart contents'
    owns_cart = True
    _, root = dump()
    plus = [n for n in root.iter('node') if n.attrib.get('content-desc') == '\uf103' and n.attrib.get('clickable') == 'true' and n.attrib.get('enabled') == 'true']
    assert plus, 'Available native add-to-cart action missing'
    tap(plus[0]); time.sleep(5)
    cart = api('GET', f'/cafeterias/{cid}/cart/', student)
    assert len(cart['items']) == 1, 'Native add-to-cart did not persist exactly one item'
    print('PASS native add-to-cart persists to API', flush=True)
    link('checkout')
    wait_text('Payment Method', 30)
    snap('06-checkout-top')
    fields = []
    for _ in range(4):
        _, root = dump()
        fields = [n for n in root.iter('node') if n.attrib.get('class') == 'android.widget.EditText']
        if fields: break
        adb('shell', 'input', 'swipe', '500', '1500', '500', '500', '400')
        time.sleep(1)
    assert fields, 'Checkout order-note input missing'
    tap(fields[0]); adb('shell', 'input', 'text', qa_note)
    adb('shell', 'input', 'keyevent', '4')
    root = snap('07-checkout-submit-visible')
    place = [n for n in root.iter('node') if n.attrib.get('text', '').lower().startswith('place order')]
    assert place, 'Cash checkout action must have a visible text label'
    tap(place[0])
    snap('08-checkout-after-submit')
    wait_text('Order Details', 90)
    orders = api('GET', '/orders/?limit=100', student)['orders']
    order = next(o for o in orders if o.get('note') == qa_note)
    order_id = order['id']
    assert order['payment_method'] == 'cash', 'QA must never use an online payment'
    queue = api('GET', f'/orders/cafeteria/{cid}?limit=100', staff)['orders']
    assert any(o['id'] == order_id for o in queue), 'Native order missing from staff queue'
    print('PASS native checkout -> staff queue; QA order:', order_id, flush=True)
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    web = 'https://uniserve-web-dashboard-pakmultilinks-dot.vercel.app'
    page.goto(web + '/login', wait_until='domcontentloaded', timeout=120000)
    page.get_by_placeholder('your.name@lgu.edu.pk').fill('staff@demo.uniserve.pk')
    page.get_by_placeholder('Enter your password').fill('UniServe2026!')
    page.get_by_role('button', name='Sign In', exact=True).click()
    page.wait_for_url('**/dashboard**', timeout=60000)
    page.goto(web + '/dashboard/orders?cafeteria=' + cid, wait_until='domcontentloaded', timeout=60000)
    card = page.get_by_text('#' + str(order['order_number']), exact=True).locator('xpath=ancestor::div[contains(@class,"shadow-card")][1]')
    card.wait_for(state='visible', timeout=60000)
    card.screenshot(path=str(OUT / 'web-01-new-native-order.png'))
    if order['status'] == 'pending':
        if not order.get('confirmed_at'):
            card.get_by_role('button', name='Confirm', exact=True).click()
            time.sleep(2)
        card.get_by_role('button', name='Prepare', exact=True).click()
        order = wait_order_status('preparing')
    if order['status'] == 'preparing':
        card.get_by_role('button', name='Ready', exact=True).click()
    order = wait_order_status('ready')
    card.get_by_role('button', name='Collect', exact=True).wait_for(state='visible', timeout=30000)
    card.screenshot(path=str(OUT / 'web-02-ready.png'))
    print('PASS real staff dashboard login, queue visibility and Ready action', flush=True)
    time.sleep(17)
    snap('09-order-ready')
    notifications = api('GET', '/notifications?limit=100', student)['items']
    assert any(n.get('order_id') == order_id and 'ready' in (n['title'] + n['body']).lower() for n in notifications)
    link('notifications')
    wait_text('ready', 30)
    snap('10-native-ready-notification')
    print('PASS ready notification correlated by exact new order ID', flush=True)
    card.get_by_role('button', name='Collect', exact=True).click()
    page.get_by_role('button', name='Confirm Collect', exact=True).click()
    order = wait_order_status('completed')
    card.screenshot(path=str(OUT / 'web-03-collected.png'))
    print('PASS real staff dashboard collection action', flush=True)
    completed = True
    link('order/' + order_id)
    wait_text('Completed', 60)
    snap('11-completed-order')
    adb('shell', 'input', 'swipe', '500', '1500', '500', '400', '450')
    time.sleep(2)
    snap('12-order-scrolled')
    print('PASS native flow through collection; no money transferred', flush=True)
finally:
    if page and not completed:
        try: page.screenshot(path=str(OUT / 'web-failure.png'), full_page=True)
        except Exception: pass
    if browser: browser.close()
    if pw: pw.stop()
    (OUT / 'crash-log.txt').write_text(adb('logcat', '-b', 'crash', '-d'))
    if order_id and not completed:
        try:
            manager = login_api('manager')
            api('POST', f'/orders/{order_id}/manager-cancel', manager, {'reason': 'Deployment QA interrupted; no real food or payment'})
        except Exception as exc: print('QA order cleanup requires review:', type(exc).__name__, flush=True)
    if owns_cart and student:
        try:
            cart = api('GET', f'/cafeterias/{cid}/cart/', student)
            for item in cart['items']: api('DELETE', f'/cafeterias/{cid}/cart/items/{item["id"]}', student)
        except Exception as exc: print('QA cart cleanup requires review:', type(exc).__name__, flush=True)
