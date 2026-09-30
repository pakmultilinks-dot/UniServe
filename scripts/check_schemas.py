import httpx

r = httpx.get("http://localhost:8000/api/openapi.json")
spec = r.json()
schemas = spec.get("components", {}).get("schemas", {})

for name in ["CafeteriaCreate", "MenuItemCreate", "DailyMenuCreate", "DailyMenuItemCreate", "InventoryItemCreate", "RegistrationRequest"]:
    if name not in schemas:
        print(f"=== {name} NOT FOUND ===")
        continue
    s = schemas[name]
    print(f"=== {name} ===")
    props = s.get("properties", {})
    required = s.get("required", [])
    for k, v in props.items():
        t = v.get("type", v.get("anyOf", "?"))
        if isinstance(t, list):
            t = str(t)
        req = " *" if k in required else ""
        default = v.get("default", "")
        print(f"  {k}: {t}{req}  {default}")
    print()

# Also print auth registration endpoint body
paths = spec.get("paths", {})
for p in ["/api/v1/auth/register", "/api/v1/auth/login"]:
    if p in paths:
        for method, detail in paths[p].items():
            rb = detail.get("requestBody", {})
            content = rb.get("content", {})
            for ct, ct_detail in content.items():
                ref = ct_detail.get("schema", {}).get("$ref", "")
                print(f"{method.upper()} {p} -> {ref}")
