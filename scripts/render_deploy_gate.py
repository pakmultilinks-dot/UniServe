#!/usr/bin/env python3
"""Verify current UniServe Render deployment; optionally deploy with preexisting GitHub secrets.

No credentials are ever logged. This diagnostic does not mutate database records.
A missing secret is a clear BLOCKED result, not a claimed successful deployment.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


def fetch(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, payload: bytes | None = None):
    req = urllib.request.Request(
        url, method=method, headers={"User-Agent": "UniServe-Deployment-Gate/1.0", **(headers or {})}, data=payload
    )
    try:
        with urllib.request.urlopen(req, timeout=100) as response:
            return response.status, response.read(64000), response.headers
    except urllib.error.HTTPError as error:
        return error.code, error.read(64000), error.headers


def verify(api: str, origin: str) -> bool:
    status, body, _ = fetch(api + "/")
    try:
        root = json.loads(body)
    except (ValueError, UnicodeError):
        root = {}
    print(f"API root: HTTP {status}; advertised dashboard: {root.get('dashboard', 'unknown')}", flush=True)
    status, body, _ = fetch(api + "/api/v1/health/ready")
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        data = {}
    print(f"Database readiness: HTTP {status}; status={data.get('status')}; database={data.get('database')}; schema={data.get('schema')}", flush=True)
    try:
        code, _, head = fetch(api + "/api/v1/auth/login", method="OPTIONS", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        allowed = head.get("Access-Control-Allow-Origin")
        print(f"Current Vercel -> Render CORS: HTTP {code}; allow-origin={allowed}", flush=True)
    except urllib.error.URLError as exc:
        print(f"CORS request failed: {type(exc).__name__}", flush=True)
        return False
    return status == 200 and data.get("status") == "ready" and code == 200 and allowed == origin


def trigger_render() -> bool:
    hook = os.environ.get("RENDER_DEPLOY_HOOK_URL", "").strip()
    api_key = os.environ.get("RENDER_API_KEY", "").strip()
    service_id = os.environ.get("RENDER_SERVICE_ID", "").strip()
    if hook:
        parsed = urllib.parse.urlparse(hook)
        if parsed.scheme != "https" or parsed.hostname not in ("api.render.com", "dashboard.render.com"):
            raise RuntimeError("Configured deploy hook URL must use HTTPS on an official Render hostname")
        code, _, _ = fetch(hook, method="POST")
        print(f"Render deploy-hook response HTTP {code}", flush=True)
        if code < 200 or code >= 300:
            raise RuntimeError("Render deploy hook did not accept deployment request")
        return True
    if api_key and service_id:
        if not service_id.startswith("srv-") or not all(c.isalnum() or c == "-" for c in service_id):
            raise RuntimeError("RENDER_SERVICE_ID is invalid")
        code, _, _ = fetch(
            f"https://api.render.com/v1/services/{service_id}/deploys",
            method="POST",
            payload=b'{"clearCache":"do_not_clear"}',
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        )
        print(f"Render API deployment response HTTP {code}", flush=True)
        if code < 200 or code >= 300:
            raise RuntimeError("Render API rejected deployment request")
        return True
    print("BLOCKED: neither GitHub Actions RENDER_DEPLOY_HOOK_URL nor both RENDER_API_KEY and RENDER_SERVICE_ID are configured.", flush=True)
    print("The Render account owner must connect Render or deploy the latest main commit from Render Dashboard.", flush=True)
    return False


def main() -> int:
    api = os.environ["RENDER_ORIGIN"].rstrip("/")
    web = os.environ["CURRENT_WEB_ORIGIN"].rstrip("/")
    if verify(api, web):
        print("SUCCESS: live Render allows current Vercel origin and database is ready.", flush=True)
        return 0
    print("Live pair is not ready; checking preconfigured GitHub deployment credentials.", flush=True)
    if not trigger_render():
        return 2
    print("Render deploy requested. Rechecking public readiness and CORS.", flush=True)
    for attempt in range(1, 21):
        time.sleep(20)
        try:
            if verify(api, web):
                print("SUCCESS: live Render now allows current Vercel origin.", flush=True)
                return 0
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"Probe {attempt}: {type(exc).__name__} while Render may restart", flush=True)
    print("BLOCKED: Render deployed/requested but current CORS not verified after checks.", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
