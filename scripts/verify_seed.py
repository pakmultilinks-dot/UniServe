import httpx

BASE = "http://localhost:8000/api/v1"

# Login as student
r = httpx.post(f"{BASE}/auth/login", json={"university_email": "ayesha.khan@student.lgu.edu.pk", "password": "TestPass123!"})
token = r.json()["tokens"]["access_token"]
h = {"Authorization": f"Bearer {token}"}

# Get cafeterias
r = httpx.get(f"{BASE}/cafeterias/", headers=h)
cids = [c["id"] for c in r.json()["cafeterias"]]
print(f"Cafeterias: {len(cids)}")

# Get today's menu for Student Cafeteria
r = httpx.get(f"{BASE}/cafeterias/{cids[0]}/daily-menus/today", headers=h)
menu = r.json()
status = menu.get("status", "?")
items = menu.get("items", [])
print(f"Daily menu status: {status}")
print(f"Items on menu: {len(items)}")

# Check first items have image URLs
for item in items[:3]:
    mi = item.get("menu_item", {})
    name = mi.get("name", "?")
    price = mi.get("price", 0) / 100
    img = mi.get("image_url", "NO IMAGE")
    print(f"  {name}: Rs {price} | {img}")

# Verify image URL works
if items:
    img_url = items[0].get("menu_item", {}).get("image_url", "")
    if img_url:
        r2 = httpx.get(img_url)
        print(f"Image check: {r2.status_code} {len(r2.content)} bytes")

# Also check Faculty Cafeteria
r = httpx.get(f"{BASE}/cafeterias/{cids[1]}/daily-menus/today", headers=h)
menu2 = r.json()
items2 = menu2.get("items", [])
print(f"\nFaculty Cafeteria menu: {menu2.get('status')} ({len(items2)} items)")
for item in items2[:3]:
    mi = item.get("menu_item", {})
    name = mi.get("name", "?")
    price = mi.get("price", 0) / 100
    img = mi.get("image_url", "NO IMAGE")
    print(f"  {name}: Rs {price} | {img}")
