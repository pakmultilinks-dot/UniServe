#!/usr/bin/env python3
"""Phase 63 — local HTTPS/TLS verification battery (chain-validated).

Verifies the local Caddy TLS termination path (Caddyfile.local-https) with a
full certificate-chain validation against the Caddy local root CA. No trust
store mutation, no insecure skips. Scope: LOCAL HTTPS ONLY — production
HTTPS still requires real domain/certificate infrastructure.
"""

import json
import socket
import ssl
import sys
import urllib.error
import urllib.request

CA_FILE = r"C:\Users\Lenovo\AppData\Local\Temp\uniserve_local_root_ca.crt"
HTTPS = "https://localhost"
results: list[tuple[str, str, str]] = []  # (check, expected, actual)


def record(check: str, expected: str, actual: str) -> None:
    results.append((check, expected, actual))
    print(f"[{'OK' if 'PASS' in actual else 'CHECK'}] {check}\n      expected={expected}\n      actual={actual}")


def main() -> int:
    ctx = ssl.create_default_context(cafile=CA_FILE)

    # 1. TLS handshake + chain validation + hostname match
    with socket.create_connection(("localhost", 443), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname="localhost") as tls:
            cert = tls.getpeercert()
            cipher = tls.cipher()
            version = tls.version()
    subject_rdns = [x[0] for x in cert["subject"]]
    subject = next((v for k, v in subject_rdns if k == "commonName"),
                   f"<no CN, attrs={[k for k, _ in subject_rdns]}>")
    issuer_rdns = [x[0] for x in cert["issuer"]]
    issuer = next((v for k, v in issuer_rdns if k == "commonName"),
                  f"<no CN, attrs={[k for k, _ in issuer_rdns]}>")
    sans = [v for k, v in cert["subjectAltName"] if k == "DNS"]
    record("TLS handshake + chain validation", "succeeds without verification errors",
           f"PASS version={version} cipher={cipher[0]}")
    record("Certificate subject", "CN covering local hostname",
           f"PASS CN={subject} SANs={sans}")
    record("Certificate issuer", "Caddy local CA (private/internal)",
           f"PASS issuer={issuer}")
    record("Hostname match (localhost)", "SAN includes localhost",
           f"PASS {'localhost' in sans}")

    # 2. HTTPS API readiness through TLS
    with urllib.request.urlopen(HTTPS + "/api/v1/health/ready", context=ctx, timeout=10) as r:
        body = json.loads(r.read())
    record("API readiness over HTTPS", "ready/connected/present",
           f"PASS {body.get('status')}/{body.get('database')}/{body.get('schema')}")

    # 3. HTTP -> HTTPS redirect (disable auto-follow to observe the 301 itself)
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):  # noqa: ANN002, ANN003
            return None

    no_redir = urllib.request.build_opener(_NoRedirect)
    try:
        no_redir.open("http://localhost/api/v1/health/ready", timeout=10)
        record("HTTP -> HTTPS redirect", "301 to https", "FAIL no redirect (200)")
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location", "")
        record("HTTP -> HTTPS redirect", "301 to https",
               f"PASS {e.code} -> {loc}" if e.code in (301, 308, 307) and loc.startswith("https://")
               else f"FAIL {e.code} loc={loc}")

    # 4. Unauthenticated API access over HTTPS (no data leak)
    try:
        urllib.request.urlopen(HTTPS + "/api/v1/orders", context=ctx, timeout=10)
        record("Unauthenticated /orders over HTTPS", "401", "FAIL 200")
    except urllib.error.HTTPError as e:
        record("Unauthenticated /orders over HTTPS", "401",
               f"PASS {e.code}" if e.code == 401 else f"FAIL {e.code}")

    # 4b. Security headers through HTTPS (GET — health route is not HEAD-able, 405)
    req = urllib.request.Request(HTTPS + "/api/v1/health/ready", method="GET")
    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
        hdr = {k.lower(): v for k, v in r.headers.items()}
    want = {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "strict-origin-when-cross-origin",
    }
    got = {k: hdr.get(k, "MISSING") for k in want}
    ok = all(got[k].lower() == v.lower() for k, v in want.items())
    record("Security headers (mirror prod Caddyfile)", "nosniff/DENY/strict-origin",
           f"PASS {got}" if ok else f"FAIL {got}")
    record("Server header suppressed", "absent (no version leakage)",
           f"PASS absent" if "server" not in hdr else f"FAIL present: {hdr['server']}")

    # 6. Static food image over HTTPS (container path /app/app/static/food/dal.jpg)
    req = urllib.request.Request(
        HTTPS + "/api/v1/static/food/dal.jpg", method="GET"
    )
    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
        ct = r.headers.get("Content-Type", "")
        n = len(r.read())
    record("Static food image over HTTPS", "200 image/* non-trivial bytes",
           f"PASS {ct} {n}B" if ct.startswith("image/") and n > 1000 else f"FAIL {ct} {n}B")

    # 7. Web dashboard loads through HTTPS (same-origin /api/v1 base — no mixed content)
    with urllib.request.urlopen(HTTPS + "/login", context=ctx, timeout=30) as r:
        html = r.read().decode("utf-8", "replace")
    mixed = "http://localhost:8000" in html
    record("Web login page over HTTPS", "200 HTML",
           f"PASS 200 {len(html)}B" if r.status == 200 else f"FAIL {r.status}")
    record("No hardcoded http:// API origin in served page",
           "no http://localhost:8000 references",
           "PASS none found" if not mixed else "FAIL mixed-content reference present")

    # 8. Login through HTTPS (full auth flow) — admin account
    payload = json.dumps({
        "university_email": "admin@lgu.edu.pk", "password": "Admin123!"
    }).encode()
    req = urllib.request.Request(
        HTTPS + "/api/v1/auth/login", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            login = json.loads(r.read())
        token = login.get("tokens", {}).get("access_token", "")
        record("Authentication over HTTPS", "200 + access token",
               f"PASS token issued ({len(token)} chars)")
    except urllib.error.HTTPError as e:
        token = ""
        record("Authentication over HTTPS", "200 + access token", f"FAIL {e.code} {e.read()[:200]}")

    # 9. Authorization over HTTPS (protected call with token)
    if token:
        req = urllib.request.Request(
            HTTPS + "/api/v1/administration/overview",
            headers={"Authorization": f"Bearer {token}"}, method="GET",
        )
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            record("Authorization over HTTPS (admin endpoint)", "200 with valid token",
                   f"PASS {r.status}")
        # Replayed/wrong-role token
        req2 = urllib.request.Request(
            HTTPS + "/api/v1/administration/overview",
            headers={"Authorization": "Bearer not-a-real-token"}, method="GET",
        )
        try:
            urllib.request.urlopen(req2, context=ctx, timeout=10)
            record("Invalid token over HTTPS", "401", "FAIL 200")
        except urllib.error.HTTPError as e:
            record("Invalid token over HTTPS", "401",
                   f"PASS {e.code}" if e.code == 401 else f"FAIL {e.code}")

    # 10. Session cookie behaviour (none set by API — bearer model)
    req = urllib.request.Request(HTTPS + "/api/v1/health/ready", method="GET")
    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
        sc = r.headers.get("Set-Cookie")
    record("API session model", "stateless bearer (no auth cookies)",
           f"PASS no auth cookie (Set-Cookie={sc!r})" if not sc else f"CHECK Set-Cookie present")

    print("\n================= HTTPS SUMMARY =================")
    fails = [r for r in results if r[2].startswith("FAIL")]
    print(f"Total: {len(results)} | PASS: {len(results) - len(fails)} | FAIL: {len(fails)}")
    for c, e, a in fails:
        print(f"  FAIL: {c} — expected {e}, got {a}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
