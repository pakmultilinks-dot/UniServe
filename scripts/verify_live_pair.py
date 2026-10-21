#!/usr/bin/env python3
"""Read-only smoke check of the user's *actual* web URL and public API.

Never logs in, places orders, changes settings, or touches the database.
GitHub Actions runs this from outside the user's local network.
"""
from __future__ import annotations

import json
import os
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


class JsScripts(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.src: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            values = dict(attrs)
            if values.get("src"):
                self.src.append(values["src"] or "")


def request(url: str, *, method: str = "GET", headers: dict[str, str] | None = None) -> tuple[int, bytes, object]:
    req = Request(
        url,
        method=method,
        headers={"User-Agent": "UniServe-live-pair-check/1.0", **(headers or {})},
    )
    try:
        with urlopen(req, timeout=115) as resp:
            return resp.status, resp.read(2_000_000), resp.headers
    except HTTPError as exc:
        return exc.code, exc.read(10_000), exc.headers


def run() -> int:
    web = os.environ.get(
        "UNISERVE_WEB_URL",
        "https://uniserve-web-dashboard-mo5nzfure-pakmultilinks-dot.vercel.app",
    ).rstrip("/")
    api = os.environ.get("UNISERVE_API_URL", "https://uniserve-api.onrender.com").rstrip("/")
    issues: list[str] = []
    print(f"Web target: {web}", flush=True)
    print(f"API target: {api}", flush=True)

    try:
        code, html, _ = request(f"{web}/dashboard/orders")
        print(f"Web /dashboard/orders: HTTP {code}", flush=True)
        if code != 200:
            issues.append(f"Web route returned HTTP {code}")
        else:
            parser = JsScripts()
            parser.feed(html.decode("utf-8", errors="replace"))
            scripts = [
                urljoin(web + "/", src)
                for src in parser.src
                if urlparse(urljoin(web + "/", src)).netloc == urlparse(web).netloc
            ]
            print(f"Web Next.js script assets: {len(scripts)}", flush=True)
            has_new_queue_marker = False
            has_ready_control = False
            for script in scripts[:35]:
                status, body, _ = request(script)
                if status != 200:
                    continue
                has_new_queue_marker |= b"Order workflow:" in body or b"Web build:" in body
                has_ready_control |= b"Ready for pickup" in body or b"Collect" in body
            print(f"New web queue build marker found: {has_new_queue_marker}", flush=True)
            print(f"Order-action strings found in fetched JS: {has_ready_control}", flush=True)
            if not has_new_queue_marker:
                issues.append(
                    "The deployed URL does not expose the new web build marker. "
                    "It may still be an outdated Vercel deployment-specific URL."
                )
    except (URLError, OSError, ValueError) as exc:
        issues.append(f"Web fetch: {type(exc).__name__}: {exc}")

    # Diagnostic discovery only: never tell users a guessed alias works unless
    # the remote server actually replies and its JS carries our new marker.
    for candidate in [
        "https://uniserve-web-dashboard-pakmultilinks-dot.vercel.app",
        "https://uniserve-web-dashboard.vercel.app",
        "https://uniserve-web-dashboard-git-main-pakmultilinks-dot.vercel.app",
    ]:
        try:
            c_status, c_html, _ = request(candidate + "/dashboard/orders")
            print(f"Candidate production domain {candidate}: HTTP {c_status}", flush=True)
            if c_status != 200:
                continue
            probe = JsScripts()
            probe.feed(c_html.decode("utf-8", errors="replace"))
            found = False
            for path in probe.src[:35]:
                address = urljoin(candidate + "/", path)
                if urlparse(address).netloc != urlparse(candidate).netloc:
                    continue
                script_status, script_body, _ = request(address)
                if script_status == 200 and (b"Order workflow:" in script_body or b"Web build:" in script_body):
                    found = True
                    break
            print(f"Candidate carries current queue marker: {found}", flush=True)
            if found:
                print(f"CONFIRMED UP-TO-DATE CANDIDATE: {candidate}", flush=True)
        except (URLError, OSError, ValueError) as exc:
            print(f"Candidate not usable: {candidate}: {type(exc).__name__}", flush=True)

    for label, path in [
        ("API liveness", "/api/v1/health"),
        ("API readiness", "/api/v1/health/ready"),
    ]:
        try:
            status, body, _ = request(api + path)
            data = json.loads(body.decode("utf-8"))
            print(f"{label}: HTTP {status}; status={data.get('status')}; database={data.get('database')}; schema={data.get('schema')}", flush=True)
            if status != 200 or data.get("status") not in ("healthy", "ready"):
                issues.append(f"{label}: HTTP {status} with status={data.get('status')}")
        except (URLError, OSError, ValueError) as exc:
            issues.append(f"{label}: {type(exc).__name__}: {exc}")

    try:
        status, _, headers = request(
            api + "/api/v1/auth/login",
            method="OPTIONS",
            headers={
                "Origin": web,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        allowed = headers.get("Access-Control-Allow-Origin")
        print(f"Web-to-API browser CORS: HTTP {status}; allowed origin={allowed}", flush=True)
        if status not in (200, 204) or allowed != web:
            issues.append("Browser CORS does not allow the exact web URL")
    except (URLError, OSError, ValueError) as exc:
        issues.append(f"Browser CORS: {type(exc).__name__}: {exc}")

    if issues:
        print("LIVE SYSTEM DOES NOT YET PASS:", flush=True)
        for problem in issues:
            print(f"  - {problem}", flush=True)
        return 1
    print("Public route, current web marker, API and browser CORS verified. Authenticated E2E still requires device/browser testing.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
