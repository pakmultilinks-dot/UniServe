#!/usr/bin/env python3
"""Generate realistic food images for UniServe menu items.

Downloads free-licensed food photos from Unsplash and saves them locally.
Falls back to generating SVG food illustrations for any items that fail.

Run from repo root:
    python scripts/generate_food_images.py
"""

import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "apps" / "api" / "app" / "static" / "food"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Menu items with Unsplash photo IDs (free license)
# Format: (filename, unsplash_photo_id, fallback_color, food_label)
MENU_IMAGES = [
    # Student Cafeteria
    ("chicken-burger", "1568901346375-23c9450c58cd", "#c4843e", "Chicken Burger"),
    ("zinger-burger", "1572802419224-296b0aeee0d9", "#d4923a", "Zinger Burger"),
    ("chicken-shawarma", "1529006557810-274b9b2fc783", "#c4956a", "Shawarma"),
    ("chicken-roll", "1628294895950-9805252327bc", "#c4a35a", "Chicken Roll"),
    ("fries", "1573080496219-bb080dd4f877", "#e8c547", "Fries"),
    ("club-sandwich", "1528735602780-2552fd46c7af", "#d4a574", "Club Sandwich"),
    ("chai", "1544787219-7f47ccb76574", "#8B6914", "Chai"),
    ("cold-drink", "1622483767028-3f66f32aef97", "#3b82c4", "Cold Drink"),
    ("water", "1548839140-29a749e1cf4d", "#6eb5e8", "Water"),
    ("samosa", "1601050690597-df0568f70950", "#c4953a", "Samosa"),
    ("paratha", "1567337710282-00832b415979", "#d4a854", "Paratha"),
    ("omelette", "1525351484163-7529414344d8", "#e8c84a", "Omelette"),
    ("pizza-slice", "1513104890138-7c749659a591", "#d4653a", "Pizza Slice"),
    ("chicken-pakora", "1626074353765-517a681e40be", "#c4843a", "Chicken Pakora"),
    ("gulab-jamun", "1601303516534-bf0b1eb70a4c", "#8B4513", "Gulab Jamun"),

    # Faculty Cafeteria
    ("chicken-biryani", "1589302168068-964664d93dc0", "#d4a04a", "Biryani"),
    ("chicken-pulao", "1563379091339-03b21ab4a4f8", "#e8d5a0", "Pulao"),
    ("chicken-karahi", "1601050690117-94f5f6fa8bd7", "#b84a28", "Karahi"),
    ("chicken-korma", "1588166524941-3bf61a9c41db", "#c4783a", "Korma"),
    ("naan", "1565557623262-b51c2513a641", "#d4b87a", "Naan"),
    ("raita", "1631452180519-c014fe946bc7", "#e8e0d0", "Raita"),
    ("fresh-juice", "1621506289937-a8e4df240d0b", "#e87820", "Juice"),
    ("chocolate-cake", "1578985545062-69928b1d9587", "#5c2d0e", "Cake"),
    ("green-tea", "1556679343-c7306c1976bc", "#5a8a3c", "Green Tea"),
    ("chicken-shami-kebab", "1606491956689-2ea866880c84", "#a0724a", "Shami Kebab"),
    ("dal", "1546833999-b9f581a1996d", "#c4953a", "Daal"),
    ("mixed-veg", "1512621776951-a57141f2eefd", "#4a8a3c", "Mixed Veg"),
]


def download_unsplash(photo_id: str, filename: str) -> bool:
    """Download a food photo from Unsplash."""
    url = f"https://images.unsplash.com/photo-{photo_id}?auto=format&fit=crop&w=800&q=85"
    filepath = OUTPUT_DIR / f"{filename}.jpg"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            if len(data) > 10000:  # Sanity check — real images are >10KB
                filepath.write_bytes(data)
                print(f"  OK   {filename}.jpg ({len(data)//1024}KB)")
                return True
            else:
                print(f"  WARN {filename}.jpg too small ({len(data)}B)")
                return False
    except Exception as e:
        print(f"  FAIL {filename}.jpg: {e}")
        return False


def generate_svg_fallback(filename: str, color: str, label: str) -> None:
    """Generate a simple SVG food illustration as fallback."""
    # SVG with food-themed illustration
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400">
  <defs>
    <radialGradient id="bg" cx="50%" cy="40%" r="60%">
      <stop offset="0%" stop-color="{color}" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="{color}" stop-opacity="0.6"/>
    </radialGradient>
  </defs>
  <rect width="400" height="400" fill="#f5f0e8"/>
  <rect width="400" height="400" fill="url(#bg)"/>
  <!-- Plate -->
  <ellipse cx="200" cy="210" rx="140" ry="130" fill="white" opacity="0.9"/>
  <ellipse cx="200" cy="210" rx="120" ry="110" fill="#fafafa"/>
  <!-- Food representation -->
  <circle cx="200" cy="200" r="70" fill="{color}" opacity="0.7"/>
  <circle cx="180" cy="185" r="25" fill="{color}" opacity="0.5"/>
  <circle cx="220" cy="190" r="20" fill="{color}" opacity="0.5"/>
  <circle cx="200" cy="220" r="22" fill="{color}" opacity="0.5"/>
  <!-- Label -->
  <rect x="50" y="340" width="300" height="40" rx="8" fill="rgba(0,0,0,0.6)"/>
  <text x="200" y="366" text-anchor="middle" font-family="Arial,sans-serif" font-size="20" font-weight="bold" fill="white">{label}</text>
</svg>'''
    filepath = OUTPUT_DIR / f"{filename}.svg"
    filepath.write_text(svg)
    print(f"  SVG  {filename}.svg (fallback)")


def main():
    print(f"Generating food images in {OUTPUT_DIR}")
    print(f"{'='*50}")

    ok_count = 0
    fail_count = 0

    for filename, photo_id, color, label in MENU_IMAGES:
        jpg_path = OUTPUT_DIR / f"{filename}.jpg"
        svg_path = OUTPUT_DIR / f"{filename}.svg"

        # Skip if already downloaded
        if jpg_path.exists() and jpg_path.stat().st_size > 10000:
            print(f"  SKIP {filename}.jpg (exists)")
            ok_count += 1
            continue

        success = download_unsplash(photo_id, filename)
        if success:
            ok_count += 1
        else:
            generate_svg_fallback(filename, color, label)
            fail_count += 1

    print(f"\n{'='*50}")
    print(f"Results: {ok_count} downloaded, {fail_count} fallback SVGs")
    print(f"Total: {len(MENU_IMAGES)} items")


if __name__ == "__main__":
    main()
