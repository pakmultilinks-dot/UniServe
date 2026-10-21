"""Disposable CI emulator test; uses demo login, never submits checkout/payment."""
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path('native-evidence')
OUT.mkdir(exist_ok=True)
PACKAGE = 'com.uniserve.mobile'

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
    adb('install', '-r', 'native-apk/app-release.apk')
    adb('shell', 'monkey', '-p', PACKAGE, '-c', 'android.intent.category.LAUNCHER', '1')
    wait_text('Welcome Back', 90)
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
    snap('04-authenticated-menu')
    adb('shell', 'input', 'swipe', '500', '1500', '500', '400', '450')
    time.sleep(3)
    snap('05-menu-scrolled')
    print('PASS native demo login and menu screen capture', flush=True)
    link('order/553b9691-5e4a-4d60-910a-a3ed8194e747')
    wait_text('completed', 60)
    snap('06-completed-order')
    adb('shell', 'input', 'swipe', '500', '1500', '500', '400', '450')
    time.sleep(2)
    snap('07-order-scrolled')
    print('PASS native order detail loads; scroll evidence captured', flush=True)
finally:
    (OUT / 'crash-log.txt').write_text(adb('logcat', '-b', 'crash', '-d'))
