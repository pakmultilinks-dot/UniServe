#!/usr/bin/env python3
"""Restore the 6 missing runtime-uploaded menu images (D1).

The production DB (read-only inspected) references 6 hash-named images that
were uploaded at runtime and lost when the API container was recreated,
because /app/app/static/food was NOT a named volume. This script replaces
those exact filenames with fresh free-licensed Unsplash photos matching each
dish, so every active menu-image URL resolves again WITHOUT touching the DB.

Writes only into apps/api/app/static/food (baked image content). The real
fix that prevents recurrence is the `menu_images_data` named volume in
docker-compose.prod.yml.
"""
import urllib.request
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "apps" / "api" / "app" / "static" / "food"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# (exact DB-referenced filename, unsplash_photo_id, dish label)
MISSING = [
    ("1a107b9f8a1a4dbdbed6e419231069c6.jpg", "1621996346565-e3dbc646d9a9", "Chicken Pasta Alfredo"),
    ("341d2569f8034b0c8261cb619367a261.jpg", "1621506289937-a8e4df240d0b", "Fresh Lime Juice"),
    ("7eff44d8f35244f8a0bd4bfe264d0906.jpg", "1461023058943-07fcbe16d735", "Cold Coffee"),
    ("957fdd11357e479d9b8ca77e2a63312e.png", "1589302168068-964664d93dc0", "Phase63Up-59b96c (biryani, disabled)"),
    ("b2f952032a3b4ee8ae641d2d27f5c9a2.jpg", "1563379091339-03b21ab4a4f8", "Chicken Biryani (Student Special)"),
    ("ef2d15aab9e64032a956851e1e9296cf.png", "1601050690597-df0568f70950", "Phase63Up-bf00d9 (samosa, disabled)"),
]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def main() -> None:
    print(f"Restoring 6 missing images -> {OUTPUT_DIR}\n" + "=" * 55)
    ok = fail = 0
    for filename, photo_id, label in MISSING:
        ext = filename.rsplit(".", 1)[1]
        # Always fetch as high-quality; keep the exact DB-referenced extension.
        url = f"https://images.unsplash.com/photo-{photo_id}?auto=format&fit=crop&w=800&q=85"
        try:
            data = fetch(url)
            if len(data) < 10000:
                print(f"  WARN {filename} too small ({len(data)}B) — skipping")
                fail += 1
                continue
            if ext == "png":
                # Unsplash serves jpeg/webp; convert to PNG so the on-disk
                # format matches the .png filename the DB references.
                import io
                from PIL import Image
                img = Image.open(io.BytesIO(data)).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                data = buf.getvalue()
            (OUTPUT_DIR / filename).write_bytes(data)
            print(f"  OK   {filename} ({len(data)//1024}KB)  <- {label}")
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {filename} ({label}): {e}")
            fail += 1
    print("=" * 55)
    print(f"Restored: {ok}   Failed: {fail}")


if __name__ == "__main__":
    main()
