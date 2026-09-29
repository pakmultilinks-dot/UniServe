"""Assign staff/manager to cafeteria for E2E verification."""
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000/api/v1"

def api(method, path, token, body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        return urllib.request.urlopen(req).read().decode()
    except urllib.error.HTTPError as e:
        return f"ERROR {e.code}: {e.read().decode()[:200]}"

def login(email):
    data = json.dumps({"university_email": email, "password": "TestPass123!"}).encode()
    req = urllib.request.Request(f"{BASE}/auth/login", data=data, headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req).read())["tokens"]["access_token"]

# Login as admin
adm = login("live.admin@lgu.edu.pk")

# Get all users to find staff and manager user IDs
users_raw = api("GET", "/users/", adm)
users = json.loads(users_raw) if not users_raw.startswith("ERROR") else []

staff_emails = [
    "live.stf.student@lgu.edu.pk",
    "live.stf.faculty@lgu.edu.pk",
]
manager_emails = [
    "live.mgr.student@lgu.edu.pk",
    "live.mgr.faculty@lgu.edu.pk",
]

# Get cafeteria IDs
cfs_raw = api("GET", "/cafeterias/", adm)
cfs = json.loads(cfs_raw) if not cfs_raw.startswith("ERROR") else {}
cafeteria_list = cfs.get("cafeterias", [])
caf_ids = {c["name"]: c["id"] for c in cafeteria_list}
print(f"Cafeterias: {list(caf_ids.keys())}")

# Get existing assignments
assigns_raw = api("GET", "/cafeteria-assignments/", adm)
print(f"Current assignments: {assigns_raw[:500]}")

# Assign each staff and manager to their corresponding cafeteria
for email in staff_emails:
    user = [u for u in users if u.get("email") == email]
    if not user:
        print(f"User {email} not found!")
        continue
    user_id = user[0]["id"]
    # Determine cafeteria: student cafeteria for student staff, faculty cafeteria for faculty staff
    caf_name = "Student Cafeteria" if "student" in email else "Faculty Cafeteria"
    caf_id = caf_ids.get(caf_name)
    if not caf_id:
        print(f"Cafeteria {caf_name} not found!")
        continue
    
    body = {"user_id": user_id, "cafeteria_id": caf_id, "role": "cafeteria_staff"}
    result = api("POST", "/cafeteria-assignments/", adm, body)
    print(f"Assign {email} -> {caf_name}: {result[:300]}")

for email in manager_emails:
    user = [u for u in users if u.get("email") == email]
    if not user:
        print(f"User {email} not found!")
        continue
    user_id = user[0]["id"]
    caf_name = "Student Cafeteria" if "student" in email else "Faculty Cafeteria"
    caf_id = caf_ids.get(caf_name)
    if not caf_id:
        print(f"Cafeteria {caf_name} not found!")
        continue
    
    body = {"user_id": user_id, "cafeteria_id": caf_id, "role": "cafeteria_manager"}
    result = api("POST", "/cafeteria-assignments/", adm, body)
    print(f"Assign {email} -> {caf_name}: {result[:300]}")
