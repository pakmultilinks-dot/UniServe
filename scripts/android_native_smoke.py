"""Disposable emulator QA: only demo cash orders, never an online payment."""
import json
import os
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
extra_orders = []
pw = browser = page = None
qa_student_id = None
qa_student_email = None
qa_student_password = None
admin = None
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
    email = qa_student_email if role == 'student' and qa_student_email else role + '@demo.uniserve.pk'
    password = qa_student_password if role == 'student' and qa_student_password else os.environ['QA_DEMO_PASSWORD']
    return api('POST', '/auth/login', body={'university_email': email, 'password': password})['tokens']['access_token']

def backend_ready():
    started = time.monotonic()
    with urllib.request.urlopen(BASE + '/health/ready', timeout=115) as response:
        result = json.loads(response.read())
        assert response.status == 200 and result['status'] == 'ready'
    print('Backend readiness preflight seconds:', round(time.monotonic() - started, 2), flush=True)

def wait_order_status(expected):
    for _ in range(15):
        order = api('GET', '/orders/' + order_id, student)
        if order['status'] == expected: return order
        time.sleep(2)
    raise AssertionError('Order did not reach expected status: ' + expected)

def adb(*args, binary=False):
    return subprocess.check_output(['adb', *args], text=not binary)

def type_text(value):
    # Controlled native inputs must settle between key events; bulk adb text
    # injection transposed the first two letters of the generated QA email.
    for char in value:
        adb('shell','input','text',char)
        time.sleep(0.12)


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

def labelled_nodes(root, label):
    label = label.casefold()
    nodes = [n for n in root.iter('node')
        if n.attrib.get('text', '').casefold() == label
        or n.attrib.get('content-desc', '').casefold().endswith(label)]
    # Native Pressables with an icon group their text into content-desc.
    # Prefer the actual clickable container; require a visible nonzero box.
    nodes = [n for n in nodes if len(set(re.findall(r'\d+', n.attrib.get('bounds','')))) > 1]
    return sorted(nodes, key=lambda n: n.attrib.get('clickable') != 'true')


def wait_text(text, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        raw, root = dump()
        if "Pixel Launcher isn't responding" in raw:
            # Handle only the disposable system launcher's ANR, never an
            # application ANR or crash. Keep those as genuine test failures.
            wait_buttons = [n for n in root.iter('node') if n.attrib.get('text') == 'Wait']
            if wait_buttons:
                print('CI environment: waiting for Pixel Launcher recovery', flush=True)
                tap(wait_buttons[0])
                time.sleep(3)
                continue
        if text.lower() in raw.lower(): return root
        time.sleep(3)
    snap('failure-' + re.sub(r'[^A-Za-z0-9_-]+','-',text))
    raise AssertionError('Screen text not reached: ' + text)

def link(path):
    adb('shell', 'am', 'start', '-W', '-a', 'android.intent.action.VIEW', '-d', 'uniserve:///' + path, PACKAGE)
    time.sleep(4)

try:
    backend_ready()
    admin = login_api('admin')
    qa_student_email = 'qa-native-' + uuid.uuid4().hex[:12] + '@demo.uniserve.pk'
    created_user = api('POST', '/users/', admin, {'first_name':'QA', 'last_name':'Native',
        'university_id':'QA-'+uuid.uuid4().hex[:16], 'university_email':qa_student_email, 'role':'student'})
    qa_student_id = created_user['user']['id']
    qa_student_password = created_user['temporary_password']
    print('::add-mask::'+qa_student_password, flush=True)
    student = login_api('student')
    print('Isolated native QA credentials verified through API; existing demo carts remain untouched', flush=True)
    adb('shell', 'svc', 'power', 'stayon', 'true')
    adb('shell', 'input', 'keyevent', '224')
    adb('shell', 'wm', 'dismiss-keyguard')
    adb('install', '-r', 'native-apk/app-release.apk')
    package_info = adb('shell', 'dumpsys', 'package', PACKAGE)
    assert re.search(r'\bversionCode=12\b', package_info) and 'versionName=0.1.11' in package_info, 'Expected fresh 0.1.11 / code 12 binary'
    component = adb('shell', 'cmd', 'package', 'resolve-activity', '--brief', PACKAGE).strip().splitlines()[-1]
    assert component.startswith(PACKAGE + '/'), 'Unexpected resolved app component'
    adb('shell', 'am', 'start', '-W', '-n', component)
    root = wait_text('Get Started', 90)
    snap('00-startup-welcome')
    entry = [n for n in root.iter('node') if n.attrib.get('content-desc', '').lower() == 'log in']
    assert entry, 'Welcome login navigation missing'
    tap(entry[0])
    wait_text('Welcome Back', 30)
    root = snap('01-startup-login')
    assert any(n.attrib.get('content-desc') == 'UniServe — Lahore Garrison University' for n in root.iter('node')), 'Actual UniServe identity must be accessible on login'
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
    tap(fields[0]); type_text(qa_student_email)
    _, entered = dump()
    email_input = next(n for n in entered.iter('node') if n.attrib.get('class') == 'android.widget.EditText')
    assert email_input.attrib.get('text') == qa_student_email, 'Native email entry must exactly match generated QA account'
    _, root = dump()
    fields = [n for n in root.iter('node') if n.attrib.get('class') == 'android.widget.EditText']
    tap(fields[1]); type_text(qa_student_password)
    adb('shell', 'input', 'keyevent', '4')
    _, root = dump()
    buttons = [n for n in root.iter('node') if n.attrib.get('text', '').lower() == 'log in']
    assert buttons, 'Login action missing'
    tap(buttons[0])
    try:
        root = wait_text('Cafeteria', 160)
    except AssertionError:
        raw, root = dump()
        if 'Request timed out' not in raw: raise
        print('CI NETWORK RECOVERY: first native login timed out; retrying once after readiness check', flush=True)
        backend_ready()
        fields = [n for n in root.iter('node') if n.attrib.get('class') == 'android.widget.EditText']
        assert len(fields) == 2
        tap(fields[1]); type_text(qa_student_password)
        adb('shell', 'input', 'keyevent', '4')
        _, root = dump()
        buttons = [n for n in root.iter('node') if n.attrib.get('text', '').lower() == 'log in']
        tap(buttons[0])
        root = wait_text('Cafeteria', 160)
    # Shared cafeteria state auto-selects the remembered/first valid location.
    # Only choose a row if a real selector sheet is already open; tapping the
    # current header would open it and hide the header from accessibility.
    time.sleep(3)
    raw, root = dump()
    snap('03a-authenticated-cafeteria-state')
    if any(n.attrib.get('text') == 'Select Cafeteria' for n in root.iter('node')):
        tap(labelled_nodes(root,'Student Cafeteria')[0])
    root = wait_text('Current cafeteria: Student Cafeteria',120)
    labels = [n for n in root.iter('node') if n.attrib.get('content-desc', '').startswith('Current cafeteria: Student Cafeteria')]
    assert labels, 'Selected cafeteria must expose its visible label'
    bounds = list(map(int, re.findall(r'\d+', labels[0].attrib['bounds'])))
    assert bounds[3] - bounds[1] >= 80, 'Cafeteria selector must not collapse to a dot'
    snap('04-authenticated-menu')
    # Reproduce the screenshot's failed refresh, then recover on the exact APK.
    # Network controls affect only this disposable emulator.
    adb('shell','svc','wifi','disable'); adb('shell','svc','data','disable')
    adb('shell','input','keyevent','3'); time.sleep(2)
    adb('shell','am','start','-W','-n',component); time.sleep(3)
    _, root = dump()
    selector = next(n for n in root.iter('node') if n.attrib.get('content-desc','').startswith('Current cafeteria:'))
    tap(selector)
    wait_text('Unable to refresh',160)
    snap('04c-offline-cafeteria-refresh')
    adb('shell','svc','wifi','enable'); adb('shell','svc','data','enable'); time.sleep(8)
    _, root = dump()
    tap(labelled_nodes(root,'Try Again')[0])
    for _ in range(45):
        raw, root = dump()
        if 'Unable to refresh' not in raw and 'Loading cafeterias' not in raw: break
        time.sleep(3)
    assert 'Unable to refresh' not in raw and 'Loading cafeterias' not in raw, 'Catalog retry must clear stale failure/loading'
    tap(labelled_nodes(root,'Student Cafeteria')[0])
    root = wait_text('Chicken Biryani',150)
    assert 'Unable to connect' not in ET.tostring(root,encoding='unicode')
    snap('04d-restored-menu-no-stale-error')
    print('PASS actual native offline catalog refresh and restored-network retry; cached selection preserved and error cleared',flush=True)

    # Exercise category and search in the actual native UI, including empty results.
    categories = [n for n in root.iter('node') if n.attrib.get('text') == 'Breakfast']
    assert categories, 'Breakfast category not visible'
    tap(categories[0]); time.sleep(3)
    snap('04a-category-breakfast')
    _, root = dump()
    tap(next(n for n in root.iter('node') if n.attrib.get('text') == 'All'))
    time.sleep(3)
    _, root = dump()
    search = next(n for n in root.iter('node') if n.attrib.get('class') == 'android.widget.EditText')
    tap(search); type_text('chicken')
    adb('shell', 'input', 'keyevent', '4')
    wait_text('Chicken Biryani', 30)
    snap('04b-search-matching-products')
    _, root = dump()
    tap(next(n for n in root.iter('node') if n.attrib.get('content-desc') == chr(62027)))
    time.sleep(3)
    _, root = dump()
    search = next(n for n in root.iter('node') if n.attrib.get('class') == 'android.widget.EditText')
    tap(search); type_text('zzqa-nomatch')
    adb('shell', 'input', 'keyevent', '4')
    wait_text('No items found', 30)
    snap('04b-search-empty-results')
    _, root = dump()
    clear = next(n for n in root.iter('node') if n.attrib.get('content-desc') == chr(62027))
    tap(clear); time.sleep(3)
    _, root = dump()
    assert 'No items found' not in ET.tostring(root, encoding='unicode')
    print('PASS native category selection, search empty state and clearing search', flush=True)
    adb('shell', 'input', 'swipe', '500', '1500', '500', '400', '450')
    time.sleep(3)
    snap('05-menu-scrolled')
    print('PASS native demo login and menu screen capture', flush=True)
    student, staff = login_api('student'), login_api('staff')
    cart = api('GET', f'/cafeterias/{cid}/cart/', student)
    assert not cart['items'], 'Preserve pre-existing demo cart contents'
    owns_cart = True
    _, root = dump()
    plus = [n for n in root.iter('node') if n.attrib.get('content-desc','').startswith('Add ') and n.attrib.get('content-desc','').endswith(' to cart') and n.attrib.get('clickable') == 'true' and n.attrib.get('enabled') == 'true']
    assert plus, 'Available native add-to-cart action missing'
    tap(plus[0]); time.sleep(5)
    cart = api('GET', f'/cafeterias/{cid}/cart/', student)
    assert len(cart['items']) == 1, 'Native add-to-cart did not persist exactly one item'
    print('PASS native add-to-cart persists to API', flush=True)
    link('cart')
    root = wait_text('Checkout', 30)
    tap(labelled_nodes(root,'Increase '+cart['items'][0]['item_name']+' quantity')[0])
    time.sleep(4)
    changed = api('GET', f'/cafeterias/{cid}/cart/', student)
    assert changed['items'][0]['quantity'] == 2, 'Native cart increment did not persist'
    _, root = dump()
    tap(labelled_nodes(root,'Decrease '+cart['items'][0]['item_name']+' quantity')[0])
    time.sleep(4)
    changed = api('GET', f'/cafeterias/{cid}/cart/', student)
    assert changed['items'][0]['quantity'] == 1, 'Native cart decrement did not persist'
    snap('05a-cart-quantity-controls')
    print('PASS native quantity increment/decrement persisted to backend', flush=True)
    # Reproduce the two-item cart shown in the user's phone screenshots.
    link('')
    root = wait_text('Current cafeteria: Student Cafeteria',45)
    time.sleep(3); _, root = dump()
    second_add = [n for n in root.iter('node') if n.attrib.get('content-desc','').startswith('Add ')
        and n.attrib.get('content-desc','').endswith(' to cart') and n.attrib.get('enabled') == 'true']
    assert second_add, 'Second distinct product must have a native Add action'
    tap(second_add[0]); time.sleep(5)
    cart = api('GET',f'/cafeterias/{cid}/cart/',student)
    assert len(cart['items']) == 2 and all(item['quantity']==1 for item in cart['items'])
    assert cart['total_amount'] == sum(item['subtotal'] for item in cart['items'])
    link('cart'); wait_text('Checkout',30); snap('05b-two-item-cart-total')
    print('PASS actual native second product and two-item cart total',flush=True)

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
    tap(fields[0]); type_text(qa_note)
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
    assert len(order['items']) == 2, 'Two-item native checkout must persist both products'
    assert order['payment_method'] == 'cash', 'QA must never use an online payment'
    queue = api('GET', f'/orders/cafeteria/{cid}?limit=100', staff)['orders']
    assert any(o['id'] == order_id for o in queue), 'Native order missing from staff queue'
    print('PASS native checkout -> staff queue; QA order:', order_id, flush=True)
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    web = 'https://uniserve-web-dashboard-git-main-pakmultilinks-dot.vercel.app'
    page.goto(web + '/login', wait_until='domcontentloaded', timeout=120000)
    # Static HTML can be visible before Next hydrates controlled inputs.
    # Wait for initial scripts, then prove an actual API login occurred.
    page.wait_for_load_state('networkidle', timeout=60000)
    email_field = page.get_by_placeholder('your.name@lgu.edu.pk')
    password_field = page.get_by_placeholder('Enter your password')
    email_field.fill('staff@demo.uniserve.pk')
    password_field.fill(os.environ['QA_DEMO_PASSWORD'])
    assert email_field.input_value() == 'staff@demo.uniserve.pk', 'Staff email field lost its value'
    assert password_field.input_value() == os.environ['QA_DEMO_PASSWORD'], 'Staff password field lost its value'
    with page.expect_response(lambda r: r.url.startswith(BASE + '/auth/login') and r.request.method == 'POST', timeout=30000) as login_response:
        page.get_by_role('button', name='Sign In', exact=True).click()
    assert login_response.value.status == 200, 'Staff browser login API did not succeed'
    print('PASS staff browser login POST HTTP 200', flush=True)
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
    # "Completed" also exists as a future timeline label while READY.
    # Wait beyond the documented 15s poll, then require READY-only QR UI
    # to disappear; a text-only match would be a false positive.
    time.sleep(17)
    terminal_deadline = time.monotonic() + 45
    while time.monotonic() < terminal_deadline:
        raw, root = dump()
        if 'completed' in raw.lower() and 'show pickup qr code' not in raw.lower():
            break
        time.sleep(3)
    else:
        snap('failure-completion-refresh')
        raise AssertionError('Native order did not refresh from ready to completed')
    snap('11-completed-order')
    adb('shell', 'input', 'swipe', '500', '1500', '500', '400', '450')
    time.sleep(2)
    snap('12-order-scrolled')
    print('PASS native flow through collection; no money transferred', flush=True)
    link('orders')
    wait_text('Orders', 30)
    # History must include the exact completed order, not an arbitrary old label.
    raw, _ = dump()
    assert '#' + str(order['order_number']) in raw, 'New completed order absent from native history'
    snap('13-order-history')
    print('PASS native history contains exact completed QA order', flush=True)

    def seed_test_order(label):
        api('POST', f'/cafeterias/{cid}/cart/items', student,
            {'menu_item_id': cart['items'][0]['menu_item_id'], 'quantity': 1})
        # Unpaid online immediate orders legitimately remain Pending. Only
        # create the order; NEVER initiate a payment/provider request. This
        # exercises cancellation/rejection even outside same-day slot hours.
        result = api('POST', f'/cafeterias/{cid}/cart/checkout', student,
            {'payment_method':'online','order_type':'immediate',
             'note':qa_note+'-'+label,'idempotency_key':str(uuid.uuid4())})
        assert result['status'] == 'pending', 'Unpaid QA order must remain pending'
        print('Created unpaid Pending QA order; no payment initiation:',result['id'],flush=True)
        extra_orders.append(result['id'])
        return result

    cancelled = seed_test_order('student-cancel')
    link('order/' + cancelled['id'])
    wait_text('Order #' + str(cancelled['order_number']), 45)
    snap('14-cancel-before-scroll')
    for _ in range(5):
        raw, root = dump()
        buttons = labelled_nodes(root, 'Cancel Order')
        if buttons: break
        adb('shell','input','swipe','500','1500','500','500','400'); time.sleep(1)
    assert buttons, 'Pending student cancellation missing'
    tap(buttons[0]); root = wait_text('Yes, cancel',30)
    tap(labelled_nodes(root, 'Yes, cancel')[0])
    wait_text('This order was cancelled',45)
    assert api('GET','/orders/'+cancelled['id'],student)['status'] == 'cancelled'
    snap('14-student-cancelled-order')
    print('PASS actual native student cancellation saved; QA order:',cancelled['id'],flush=True)

    rejected = seed_test_order('manager-reject')
    # Rejection is intentionally a manager-only dashboard action. Do not
    # change RBAC or disable production auto-acceptance to satisfy QA.
    page.context.close()
    page = browser.new_page(viewport={'width':1440,'height':1000})
    page.goto(web+'/login',wait_until='networkidle',timeout=120000)
    page.get_by_placeholder('your.name@lgu.edu.pk').fill('manager@demo.uniserve.pk')
    page.get_by_placeholder('Enter your password').fill(os.environ['QA_DEMO_PASSWORD'])
    with page.expect_response(lambda r:r.url.startswith(BASE+'/auth/login') and r.request.method=='POST',timeout=120000) as manager_response:
        page.get_by_role('button',name='Sign In',exact=True).click()
    assert manager_response.value.status==200
    page.wait_for_url('**/dashboard**',timeout=60000)
    page.goto(web+'/dashboard/orders?cafeteria='+cid,wait_until='networkidle',timeout=60000)
    rejected_card = page.get_by_text('#'+str(rejected['order_number']),exact=True).locator('xpath=ancestor::div[contains(@class,"shadow-card")][1]')
    rejected_card.get_by_role('button',name='Confirm',exact=True).click(timeout=60000)
    for _ in range(15):
        confirmed = api('GET','/orders/'+rejected['id'],student)
        if confirmed.get('confirmed_at'): break
        time.sleep(2)
    assert confirmed.get('confirmed_at') and confirmed['status']=='pending' and not confirmed.get('preparation_started_at')
    print('PASS real manager dashboard manually confirms an unpaid Pending order without preparation',flush=True)
    rejected_card.get_by_role('button',name='Reject',exact=True).click(timeout=60000)
    modal = page.locator('div').filter(has=page.get_by_role('heading',name='Reject Order #'+str(rejected['order_number']),exact=True)).last
    modal.locator('select').select_option('other')
    modal.locator('textarea').fill('Automated QA rejection; no food or payment')
    modal.get_by_role('button',name='Confirm Reject',exact=True).click()
    for _ in range(15):
        rejected_state = api('GET','/orders/'+rejected['id'],student)
        if rejected_state['status']=='cancelled': break
        time.sleep(2)
    assert rejected_state['status']=='cancelled' and rejected_state['rejection_reason']=='other'
    rejected_card.screenshot(path=str(OUT/'web-04-staff-rejected.png'))
    link('order/'+rejected['id']); wait_text('This order was cancelled',45)
    root = snap('15-staff-rejection-on-student')
    assert not any(n.attrib.get('text') == 'Preparing' for n in root.iter('node')), 'Rejected-before-preparation order must not claim Preparing'
    assert any(n.attrib.get('text') == 'Cancelled' for n in root.iter('node')), 'Cancelled must be the primary terminal status'
    print('PASS actual manager dashboard rejection synchronizes to native student',flush=True)

    # Read actual staff statistics and menu, without changing live catalog data.
    responses=[]
    page.on('response',lambda response: responses.append((response.url,response.status)))
    page.goto(web+'/dashboard',wait_until='networkidle',timeout=60000)
    page.get_by_text('Active Orders',exact=True).first.wait_for(timeout=30000)
    page.screenshot(path=str(OUT/'web-05-staff-statistics.png'),full_page=True)
    assert any('/orders/cafeteria/' in url and status==200 for url,status in responses)
    page.goto(web+'/dashboard/menu',wait_until='networkidle',timeout=60000)
    page.get_by_role('heading',name='Menu Management',exact=True).wait_for(timeout=30000)
    assert any('/menu-items' in url and status==200 for url,status in responses)
    page.screenshot(path=str(OUT/'web-06-real-menu.png'),full_page=True)
    print('PASS dashboard statistics and menu loaded from actual API responses',flush=True)
    link('profile')
    for _ in range(4):
        raw, root = dump()
        if 'v0.1.11' in raw: break
        adb('shell','input','swipe','500','1500','500','400','450'); time.sleep(1)
    wait_text('v0.1.11',30); snap('16-profile-actual-build-version')
    print('PASS native profile displays actual build version v0.1.11',flush=True)

except BaseException:
    try: snap('failure-last-screen')
    except Exception: pass
    if page:
        try: page.screenshot(path=str(OUT/'web-failure.png'),full_page=True)
        except Exception: pass
    raise
finally:
    try:
        adb('shell','svc','wifi','enable'); adb('shell','svc','data','enable')
    except Exception: pass
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
    for extra_id in extra_orders:
        try:
            state = api('GET','/orders/'+extra_id,student)
            if state['status'] not in ('completed','cancelled'):
                manager = login_api('manager')
                api('POST',f'/orders/{extra_id}/manager-cancel',manager,
                    {'reason':'Interrupted automated QA; no food or payment'})
        except Exception as exc: print('Extra QA order cleanup requires review:',type(exc).__name__,flush=True)
    if owns_cart and student:
        try:
            cart = api('GET', f'/cafeterias/{cid}/cart/', student)
            for item in cart['items']: api('DELETE', f'/cafeterias/{cid}/cart/items/{item["id"]}', student)
        except Exception as exc: print('QA cart cleanup requires review:', type(exc).__name__, flush=True)

    if qa_student_id and admin:
        try:
            api('POST',f'/users/{qa_student_id}/suspend',admin,{'reason':'Isolated automated QA completed; no real food or payment'})
            print('Isolated QA student suspended after cleanup',flush=True)
        except Exception as exc: print('QA account cleanup requires review:',type(exc).__name__,flush=True)
