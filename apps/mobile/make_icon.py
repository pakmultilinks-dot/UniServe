"""Generate the UniServe app icon from the Lahore Garrison University seal.

Produces:
  assets/icon.png          1024x1024, seal on brand background (#f6efdf)
  assets/adaptive-icon.png 1024x1024, seal with safe-zone padding (Android)
  assets/splash-icon.png   1024x1024, seal for splash screen
"""
from PIL import Image, ImageDraw

BG = (246, 239, 223)  # #f6efdf — matches app.json adaptiveIcon.backgroundColor
SIZE = 1024

seal = Image.open("assets/lgu-logo.jpg").convert("RGBA")

# The seal is a circle inside a near-white square photo. Circular-crop it so
# only the seal (not the white corners) is composited. Do NOT key out white
# pixels — the seal interior is white too and keying would punch holes.
w, h = seal.size
diameter = int(min(w, h) * 0.98)
left = (w - diameter) // 2
top = (h - diameter) // 2
seal = seal.crop((left, top, left + diameter, top + diameter))

mask = Image.new("L", (diameter, diameter), 0)
ImageDraw.Draw(mask).ellipse((0, 0, diameter - 1, diameter - 1), fill=255)
seal.putalpha(mask)


def make_icon(canvas_size, seal_frac, bg=BG):
    canvas = Image.new("RGBA", (canvas_size, canvas_size), bg)
    target = int(canvas_size * seal_frac)
    resized = seal.resize((target, target), Image.LANCZOS)
    pos = ((canvas_size - target) // 2, (canvas_size - target) // 2)
    canvas.alpha_composite(resized, pos)
    return canvas

# App icon: seal fills most of the tile
make_icon(SIZE, 0.94).save("assets/icon.png")

# Android adaptive foreground: keep inside the ~66% safe zone, transparent bg
make_icon(SIZE, 0.62, bg=(0, 0, 0, 0)).save("assets/adaptive-icon.png")

# Splash: seal on transparent (splash bg color set in app.json)
make_icon(SIZE, 0.55, bg=(0, 0, 0, 0)).save("assets/splash-icon.png")

print("icon.png, adaptive-icon.png, splash-icon.png written")