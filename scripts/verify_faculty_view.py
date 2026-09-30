import httpx

BASE = "http://localhost:8000/api/v1"

# Login as faculty (can see both cafeterias)
r = httpx.post(f"{BASE}/auth/login", json={"university_email": "dr.sana.malik@lgu.edu.pk", "password": "TestPass123!"})
token = r.json()["tokens"]["access_token"]
h = {"Authorization": f"Bearer {token}"}

# Get cafeterias
r = httpx.get(f"{BASE}/cafeterias/", headers=h)
cafeterias = r.json()["cafeterias"]
print(f"Cafeterias visible to faculty: {len(cafeterias)}")
for c in cafeterias:
    print(f"  {c['name']} ({c['id'][:8]}...) status={c.get('operational_status', '?')}")

# Check both daily menus
for c in cafeterias:
    cid = c["id"]
    r = httpx.get(f"{BASE}/cafeterias/{cid}/daily-menus/today", headers=h)
    menu = r.json()
    items = menu.get("items", [])
    print(f"\n{c['name']}: {menu.get('status')} ({len(items)} items)")
    for item in items[:5]:
        mi = item.get("menu_item", {})
        name = mi.get("name", "?")
        price = mi.get("price", 0) / 100
        cat = mi.get("category", "?")
        print(f"  {name}: Rs {price} [{cat}]")
    if len(items) > 5:
        print(f"  ... and {len(items) - 5} more")

# Verify image URLs
print("\nImage URL checks:")
for c in cafeterias:
    cid = c["id"]
    r = httpx.get(f"{BASE}/cafeterias/{cid}/daily-menus/today", headers=h)
    items = r.json().get("items", [])
    if items:
        img_url = items[0].get("menu_item", {}).get("image_url", "")
        if img_url:
            r2 = httpx.get(img_url)
            name = items[0].get("menu_item", {}).get("name", "?")
            print(f"  {c['name']} / {name}: {r2.status_code} ({len(r2.content)} bytes)")
