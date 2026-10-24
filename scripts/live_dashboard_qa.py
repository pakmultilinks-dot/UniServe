"""Live dashboard QA: isolated unpublished catalog item; no payments or real-menu edits."""
import base64
import json
import os
from pathlib import Path
import time
import urllib.request
from urllib.error import HTTPError
import uuid
from playwright.sync_api import sync_playwright

BASE='https://uniserve-api.onrender.com/api/v1'
WEB='https://uniserve-web-dashboard-git-main-pakmultilinks-dot.vercel.app'
OUT=Path('dashboard-evidence'); OUT.mkdir(exist_ok=True)
CID='83543334-2688-4c5d-9c83-ee201fac02bd'
name='QA-unpublished-'+str(uuid.uuid4())[:8]
item=None
manager=None

def api(method,path,token=None,body=None,expected=200):
    req=urllib.request.Request(BASE+path,method=method,
        headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})},
        data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req,timeout=115) as r: status,raw=r.status,r.read()
    except HTTPError as e: status,raw=e.code,e.read()
    assert status==expected, f'{method} {path} returned {status}, expected {expected}'
    print('PASS',method,path,status,flush=True)
    return json.loads(raw) if raw else None

def login(role):
    return api('POST','/auth/login',body={'university_email':role+'@demo.uniserve.pk',
        'password':os.environ['QA_DEMO_PASSWORD']})['tokens']['access_token']

def browser_login(page,role):
    page.goto(WEB+'/login',wait_until='networkidle',timeout=120000)
    page.get_by_placeholder('your.name@lgu.edu.pk').fill(role+'@demo.uniserve.pk')
    page.get_by_placeholder('Enter your password').fill(os.environ['QA_DEMO_PASSWORD'])
    with page.expect_response(lambda r:r.url.startswith(BASE+'/auth/login') and r.request.method=='POST',timeout=120000) as response:
        page.get_by_role('button',name='Sign In',exact=True).click()
    assert response.value.status==200
    page.wait_for_url('**/dashboard**',timeout=60000)

try:
    api('GET','/health/ready')
    student,staff,manager,admin=(login(role) for role in ('student','staff','manager','admin'))
    for token in (student,staff,manager): api('GET','/administration/overview',token,expected=403)
    overview=api('GET','/administration/overview',admin)
    assert 'users' in overview and 'orders' in overview
    api('GET',f'/cafeterias/{CID}/menu-items',staff)
    today=api('GET',f'/cafeterias/{CID}/daily-menus/today',student)
    assert today and today['status']=='published' and today['items'], 'No published menu today'
    print('PASS published daily menu available for real native ordering',flush=True)
    item=api('POST',f'/cafeterias/{CID}/menu-items/',manager,
        {'name':name,'description':'Isolated unpublished QA item; not for sale','category':'snack',
         'price':12300,'preparation_time_minutes':1,'initial_quantity':0},expected=201)
    api('PUT',f'/cafeterias/{CID}/menu-items/'+item['id'],staff,{'price':12400},expected=403)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000})
        page=context.new_page()
        browser_login(page,'manager')
        page.goto(WEB+'/dashboard/menu',wait_until='networkidle',timeout=60000)
        card=page.get_by_role('heading',name=name,exact=True).locator('xpath=ancestor::div[contains(@class,"shadow-card")][1]')
        card.wait_for(timeout=60000)
        card.get_by_role('button',name='Edit',exact=True).click()
        modal=page.locator('form').filter(has=page.get_by_role('button',name='Save Changes',exact=True))
        modal.locator('input[type=number]').first.fill('124')
        with page.expect_response(lambda r:r.url.endswith('/menu-items/'+item['id']) and r.request.method=='PUT') as response:
            modal.get_by_role('button',name='Save Changes',exact=True).click()
        assert response.value.status==200
        assert api('GET',f'/cafeterias/{CID}/menu-items/'+item['id'],manager)['price']==12400
        with page.expect_response(lambda r:r.url.endswith('/menu-items/'+item['id']) and r.request.method=='PUT') as response:
            card.get_by_role('button',name='Mark Unavailable',exact=True).click()
        assert response.value.status==200
        assert api('GET',f'/cafeterias/{CID}/menu-items/'+item['id'],manager)['is_available'] is False
        card.screenshot(path=str(OUT/'01-manager-price-and-availability.png'))
        # Test the image picker/upload against only the unpublished QA item.
        png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jvX8AAAAASUVORK5CYII=')
        card.get_by_role('button',name='Add Image',exact=True).click()
        page.locator('input[type=file]').set_input_files({'name':'qa.png','mimeType':'image/png','buffer':png})
        button=page.get_by_role('button',name='Upload Image',exact=True)
        button.wait_for(timeout=10000)
        with page.expect_response(lambda r:'/image' in r.url and r.request.method=='POST') as response:
            button.click()
        assert response.value.status in (200,201)
        image=card.get_by_role('img',name=name,exact=True)
        image.wait_for(timeout=30000)
        # Visibility is not evidence that the image bytes have decoded.
        page.wait_for_function('(img)=>img.complete && img.naturalWidth>0',
            arg=image.element_handle(), timeout=30000)
        assert image.evaluate('(img)=>img.complete && img.naturalWidth>0')
        card.screenshot(path=str(OUT/'02-manager-uploaded-image.png'))
        # Staff view must expose real catalog but no manager editing controls.
        context.close(); context=browser.new_context(viewport={'width':390,'height':844}); page=context.new_page()
        browser_login(page,'staff')
        responses=[]
        page.on('response',lambda r:responses.append((r.url,r.status)))
        page.goto(WEB+'/dashboard/menu',wait_until='networkidle',timeout=60000)
        page.get_by_role('heading',name='Menu Management',exact=True).wait_for(timeout=30000)
        assert page.get_by_role('button',name='Edit',exact=True).count()==0
        assert any('/menu-items' in url and status==200 for url,status in responses)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Dashboard overflows narrow viewport'
        page.screenshot(path=str(OUT/'03-staff-mobile-menu.png'),full_page=True)
        context.close(); context=browser.new_context();page=context.new_page()
        browser_login(page,'admin')
        page.goto(WEB+'/dashboard/admin/overview',wait_until='networkidle',timeout=60000)
        page.screenshot(path=str(OUT/'04-admin-overview.png'),full_page=True)
        assert 'Access restricted' not in page.inner_text('body')
        browser.close()
    print('PASS actual browser manager price, availability, image upload, staff permissions and admin overview',flush=True)
finally:
    if item and manager:
        api('PUT',f'/cafeterias/{CID}/menu-items/'+item['id'],manager,{'is_active':False,'is_available':False})
        print('QA item deactivated; it was never added to any daily menu',flush=True)
