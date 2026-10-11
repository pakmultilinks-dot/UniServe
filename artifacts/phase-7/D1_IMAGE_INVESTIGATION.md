# Phase 7 — D1 Menu-Image 404s: Investigation

## Finding (matches Phase 6: 6 of 33 local images 404)

Production `menu_items.image_url` breakdown (55 items):

| Kind | Count |
|---|---|
| local `/api/v1/static/food/<file>` | 33 |
| empty/null | 22 |

All 33 local references resolve under `/api/v1/static/food/`. They split into:
- **27 named files** (`chai.jpg`, `chicken-biryani.jpg`, …) — present in both the running container
  (`/app/app/static/food/`, 27 files) and the host source (`apps/api/app/static/food/`, 27 files).
- **6 UUID-named files** — **MISSING in both the container and the host** → HTTP 404:

```
1a107b9f8a1a4dbdbed6e419231069c6.jpg
341d2569f8034b0c8261cb619367a261.jpg
7eff44d8f35244f8a0bd4bfe264d0906.jpg
957fdd11357e479d9b8ca77e2a63312e.png
b2f952032a3b4ee8ae641d2d27f5c9a2.jpg
ef2d15aab9e64032a956851e1e9296cf.png
```

## How images are served and stored

- **Serve** — `apps/api/app/main.py:192-196`: `StaticFiles(directory=<app>/static)` mounted at
  `/api/v1/static`. In the container that directory is `/app/app/static`.
- **Upload** — `apps/api/app/modules/menus/service.py`: `MENU_IMAGE_DIR = app/static/food`;
  uploads write a server-generated filename there and persist the host-independent reference
  `/api/v1/static/food/<file>`.
- **Migration 0011** (`0011_normalize_menu_image_urls.py`) — **data-only**, no schema change. It
  rewrote environment-specific URLs (`http://api.localhost/api/v1/static/food/x.jpg`,
  `http://localhost:8000/...`) into the relative form `/api/v1/static/food/x.jpg`. It changed URL
  **strings only**; it did not and could not restore missing files.

## Root cause

`apps/api/Dockerfile` bakes the seed images in via `COPY . .` (so the 27 named files are part of the
image). The **`api` service in `docker-compose.prod.yml` has NO `volumes:` block**, so
`/app/app/static/food` lives in the container's **writable layer — ephemeral**. Any image uploaded at
runtime (admin upload) exists only in that layer and is **discarded whenever the container is
rebuilt or recreated**. Only the 27 baked-in images survive; the 6 runtime-uploaded UUID files were
lost on the last redeploy, while their `menu_items` rows still point at them → 404.

So: the **missing compose volume is the durability root cause**; the 6 lost files are the *symptom*
already baked into the data. The bytes for those 6 files are **gone** (not recoverable from the host,
the volume, or the image).

## Proposed durable fix (NOT YET APPLIED — awaiting review; touches Compose)

Add a named volume for the upload directory on the `api` service in `docker-compose.prod.yml`:

```yaml
  api:
    # ...
    volumes:
      - menu_images_data:/app/app/static/food
```

(and declare `menu_images_data:` under top-level `volumes:`).

Why this is safe: when a **fresh named volume** is first mounted at a path that already has content
in the image, Docker **copies the image's content into the volume**. So the 27 baked-in images are
seeded into `menu_images_data` on first run, and every subsequent upload persists across rebuilds /
recreates. This closes the durability gap without re-baking or reseeding anything.

## The 6 already-lost files (data-repair decision — NOT autonomous)

The 6 UUID files cannot be restored (bytes are gone). Repair options, for your decision — I did **not**
touch menu records (per the constraint "do not delete/overwrite/reseed menu records or image files"):
1. Re-upload the 6 items' photos via the admin menu UI (restores real images, keeps rows intact), or
2. Point those 6 rows at an existing valid image / clear `image_url` to `NULL` (data edit), or
3. Leave them 404 until re-uploaded.

Recommendation: option 1 (admin re-upload) once the volume fix is in, so the new uploads persist.

## Change-safety audit

- No schema change, no data change, no Compose change applied. Production DB counts and the
  running container are untouched. This document is diagnosis + proposal only.