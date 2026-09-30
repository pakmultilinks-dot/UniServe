#!/usr/bin/env python3
"""UniServe — Production Health Check Script

Verifies all services are running and responding.
No secrets are hardcoded — all URLs come from environment or arguments.

Usage:
    python scripts/production_health_check.py
    python scripts/production_health_check.py --api-url https://api.example.com
"""

import argparse
import sys
import time

import httpx


def check_endpoint(name: str, url: str, timeout: int = 10) -> bool:
    """Check if an endpoint responds with HTTP 200."""
    try:
        r = httpx.get(url, timeout=timeout)
        ok = r.status_code == 200
        status = "✅" if ok else "❌"
        print(f"  {status} {name}: HTTP {r.status_code}")
        if ok and "status" in r.text:
            try:
                data = r.json()
                print(f"       → {data.get('status', 'unknown')}")
            except Exception:
                pass
        return ok
    except httpx.ConnectError:
        print(f"  ❌ {name}: Connection refused")
        return False
    except httpx.TimeoutException:
        print(f"  ❌ {name}: Timeout ({timeout}s)")
        return False
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="UniServe production health check")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    base = args.api_url.rstrip("/")
    print(f"\n{'='*50}")
    print(f"  UniServe Production Health Check")
    print(f"  API: {base}")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    results = []

    # API Health
    print("API Health:")
    results.append(check_endpoint("Health endpoint", f"{base}/api/v1/health"))
    results.append(check_endpoint("Readiness endpoint", f"{base}/api/v1/health/ready"))

    # OpenAPI (only in debug mode — skip in production if disabled)
    try:
        r = httpx.get(f"{base}/api/openapi.json", timeout=5)
        if r.status_code == 200:
            results.append(True)
            print(f"  ✅ OpenAPI spec: Available")
        else:
            print(f"  ℹ️  OpenAPI spec: Not available (expected in production)")
    except Exception:
        print(f"  ℹ️  OpenAPI spec: Not available (expected in production)")

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*50}")
    if all(results):
        print(f"  ✅ ALL CHECKS PASSED ({passed}/{total})")
    else:
        print(f"  ❌ SOME CHECKS FAILED ({passed}/{total})")
    print(f"{'='*50}\n")

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
