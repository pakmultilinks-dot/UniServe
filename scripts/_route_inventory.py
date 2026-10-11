#!/usr/bin/env python3
"""Phase 63 — route inventory helper (read-only, no side effects).

Enumerates FastAPI routes from the API source tree so the E2E coverage
matrix can be built and cross-checked against the running container.
"""

import pathlib
import re

root = pathlib.Path("apps/api/app/modules")
total = 0
for router_file in sorted(root.glob("*/router.py")):
    txt = router_file.read_text(encoding="utf-8")
    prefix = re.search(r'APIRouter\([^)]*prefix="([^"]*)"', txt)
    routes = re.findall(r'@router\.(get|post|put|patch|delete)\(\s*"([^"]*)"', txt)
    print(f'-- {router_file.parent.name} prefix={prefix.group(1) if prefix else ""}')
    for m, p in routes:
        print(f"   {m.upper():6s} {p}")
        total += 1
print(f"TOTAL source routes: {total}")
