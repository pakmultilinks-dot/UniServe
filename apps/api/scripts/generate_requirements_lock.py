"""Generate a fully-pinned production requirements lock for the UniServe API.

Computes the exact transitive closure of ``[project.dependencies]`` from
``pyproject.toml`` using the versions **currently installed** in the
environment where this script runs (the known-good, fully-tested set).
Markers are evaluated for the Linux production target so Windows-only
packages (e.g. ``tzdata``) are excluded. Development/test-only packages are
never included because only ``[project.dependencies]`` is traversed.

Usage (from apps/api/):

    ../../.venv/Scripts/python.exe scripts/generate_requirements_lock.py

The resulting ``requirements.lock.txt`` is consumed by ``apps/api/Dockerfile``
(``pip install -r`` then ``pip install --no-deps .``). Revalidate any
regenerated lock against the production interpreter before committing:

    docker run --rm -v "$PWD/requirements.lock.txt:/tmp/l.txt:ro" \
        python:3.11-slim-bookworm sh -c "pip install --dry-run -r /tmp/l.txt"
"""

from __future__ import annotations

import sys
import tomllib
from importlib import metadata
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

# Marker environment for the production target (linux container, py3.11).
LINUX_TARGET = default_environment() | {
    "sys_platform": "linux",
    "platform_system": "Linux",
    "platform_machine": "x86_64",
    "os_name": "posix",
    "python_version": "3.11",
    "python_full_version": "3.11.9",
    "platform_python_implementation": "CPython",
    "implementation_name": "cpython",
    "platform_release": "",
    "platform_version": "",
}


def installed_versions() -> dict[str, str]:
    return {canonicalize_name(d.metadata["Name"]): d.version for d in metadata.distributions() if d.metadata["Name"]}


def installed_requires(name: str) -> list[str]:
    dist = None
    for d in metadata.distributions():
        if d.metadata["Name"] and canonicalize_name(d.metadata["Name"]) == name:
            dist = d
            break
    if dist is None:
        return []
    return list(dist.requires or [])


def main() -> int:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    direct = data["project"]["dependencies"]

    versions = installed_versions()
    platform_overrides: dict[str, str] = {}
    if len(sys.argv) > 2 and sys.argv[1] == "--image-freeze":
        for line in Path(sys.argv[2]).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "==" in line and "@" not in line:
                name, ver = line.split("==", 1)
                platform_overrides[canonicalize_name(name)] = ver

    pinned: dict[str, str] = {}
    skipped: list[str] = []
    platform_used: list[str] = []
    queue: list[tuple[Requirement, frozenset[str]]] = []

    for raw in direct:
        req = Requirement(raw)
        if req.marker and not req.marker.evaluate(LINUX_TARGET):
            skipped.append(f"{req.name} (marker excluded on linux)")
            continue
        name = canonicalize_name(req.name)
        if name not in versions:
            print(f"ERROR: direct dependency {req.name!r} not installed", file=sys.stderr)
            return 1
        pinned[name] = versions[name]
        queue.append((req, frozenset(req.extras)))

    while queue:
        req, extras = queue.pop()
        name = canonicalize_name(req.name)
        for raw_dep in installed_requires(name):
            dep = Requirement(raw_dep)
            applicable = False
            if dep.marker is None:
                applicable = True
            else:
                for extra in extras | {""}:
                    try:
                        if dep.marker.evaluate(LINUX_TARGET | {"extra": extra}):
                            applicable = True
                            break
                    except Exception:  # noqa: BLE001 - unevaluable marker: skip conservatively
                        continue
            if not applicable:
                skipped.append(f"{dep.name} (of {name}, extra={extra or '-'}: {dep.marker})")
                continue
            dep_name = canonicalize_name(dep.name)
            if dep_name not in versions:
                if dep_name in platform_overrides:
                    pinned[dep_name] = platform_overrides[dep_name]
                    platform_used.append(f"{dep_name}=={platform_overrides[dep_name]} (from image: not installable on this host)")
                    queue.append((dep, frozenset(dep.extras)))
                    continue
                print(f"ERROR: transitive dependency {dep.name!r} not installed and not in --image-freeze", file=sys.stderr)
                return 1
            if dep_name not in pinned:
                pinned[dep_name] = versions[dep_name]
                queue.append((dep, frozenset(dep.extras)))

    out = pyproject.parent / "requirements.lock.txt"
    header = (
        "# UniServe API — PRODUCTION dependency lock (AUTO-GENERATED — do not edit by hand).\n"
        "#\n"
        "# Exact transitive closure of [project.dependencies] in pyproject.toml at the\n"
        "# versions of the known-good tested environment. Consumed by apps/api/Dockerfile:\n"
        "#   pip install --no-deps -r requirements.lock.txt && pip check\n"
        "#   && pip install --no-deps . && pip check\n"
        "#\n"
        "# Regenerate: ../../.venv/Scripts/python.exe scripts/generate_requirements_lock.py\n"
        "# (from apps/api/), then validate against the production interpreter:\n"
        "#   docker run --rm -v \"$PWD/requirements.lock.txt:/tmp/l.txt:ro\" \\\n"
        "#       python:3.11-slim-bookworm sh -c \"pip install --dry-run -r /tmp/l.txt\"\n"
        "#\n"
    )
    lines = [header] + [f"{name}=={pinned[name]}" for name in sorted(pinned)]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {out} with {len(pinned)} pinned packages:")
    for name in sorted(pinned):
        print(f"  {name}=={pinned[name]}")
    if platform_used:
        print("\nPlatform-only packages sourced from the production image freeze:")
        for s in sorted(platform_used):
            print(f"  - {s}")
    if skipped:
        print(f"\nMarker-excluded on linux ({len(skipped)}):")
        for s in sorted(skipped):
            print(f"  - {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
