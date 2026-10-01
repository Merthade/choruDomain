#!/usr/bin/env python3
"""Build every image getchoru.com serves, from the app repo's own sources.

- Icons (favicon.ico, favicon-32, apple-touch-icon, icon-512) from the app icon.
- Screenshots: the App Store raws (Marketing/screenshots/raw/en, the store seed) framed
  in AlarmPlanner's web shell (side buttons that protrude) plus the store set's Dynamic
  Island, exported as WebP at one uniform size.
- Mascot cut-outs from the asset catalog, as WebP.
- og-image.png (1200x630): the store set's violet gradient, the name, one line, a dragon.

Needs Pillow. Run from anywhere: python3 _gen/make_assets.py
"""
import io
import os
from PIL import Image, ImageDraw, ImageFont

GEN = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(GEN)
APP = os.path.dirname(SITE)                      # the Choru app repo this site sits in
OUT = os.path.join(SITE, "assets")
RAW = os.path.join(APP, "Marketing", "screenshots", "raw", "en")
XCASSETS = os.path.join(APP, "Choru", "Assets.xcassets")
ICON = os.path.join(XCASSETS, "AppIcon.appiconset", "AppIcon.png")
FONT_BLACK = "/Library/Fonts/SF-Pro-Display-Black.otf"
FONT_BOLD = "/Library/Fonts/SF-Pro-Display-Bold.otf"

# The store set's shell (Marketing/screenshots/config.json) and violet gradient.
SCREEN_R_RATIO = 0.145
BEZEL_RATIO = 0.030
RIM_RATIO = 0.011
RIM_COLOR = (0x2C, 0x2C, 0x2D, 255)
ISLAND = dict(w_ratio=0.286, h_ratio=0.0855, top_ratio=0.0318)
VIOLET_TOP = (0xB4, 0x8B, 0xFF)
VIOLET_BOTTOM = (0x15, 0x0E, 0x26)
WEB_W = 640                                      # every framed shot is this wide

SHOTS = {
    "shot-mess.webp":     "calendar_mess.png",
    "shot-done.webp":     "calendar_done.png",
    "shot-chores.webp":   "chores.png",
    "shot-editor.webp":   "editor.png",
    "shot-family.webp":   "family_qr.png",      # its QR is the preview placeholder (0preview)
    "shot-kids.webp":     "kids.png",
    "shot-kidphone.webp": "kid_phone.png",
    "shot-rewards.webp":  "rewards.png",
    "shot-stats.webp":    "stats.png",
    "shot-widgets.webp":  "widgets.png",
}

MASCOTS = {
    "mascot-looking.webp": "ChoruLooking",       # 404
    "mascot-ready.webp":   "ChoruReady",         # og-image, guides hub
}


def shell(img):
    """AlarmPlanner's frame_web.py shell (buttons protrude) plus the store Dynamic Island."""
    img = img.convert("RGBA")
    sw, height = img.size
    scr_r = int(sw * SCREEN_R_RATIO)
    bez = max(6, int(sw * BEZEL_RATIO))
    rimw = max(2, int(sw * RIM_RATIO))
    bwid = max(3, rimw * 2)

    fw, fh = sw + (bez + rimw) * 2, height + (bez + rimw) * 2
    W, H = fw + bwid * 2, fh
    ox = bwid
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)

    unit = fh / 100
    for y0, y1 in [(20, 26), (30, 40), (42, 52)]:                     # action, vol up, vol down
        d.rounded_rectangle([2, int(unit * y0), ox + 2, int(unit * y1)],
                            radius=bwid // 2, fill=RIM_COLOR)
    d.rounded_rectangle([ox + fw - 2, int(unit * 33), W - 2, int(unit * 50)],   # power
                        radius=bwid // 2, fill=RIM_COLOR)

    d.rounded_rectangle([(ox, 0), (ox + fw - 1, fh - 1)], radius=scr_r + bez + rimw, fill=RIM_COLOR)
    d.rounded_rectangle([(ox + rimw, rimw), (ox + fw - rimw - 1, fh - rimw - 1)],
                        radius=scr_r + bez, fill=(8, 8, 10, 255))

    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([(0, 0), img.size], radius=scr_r, fill=255)
    img.putalpha(m)
    out.paste(img, (ox + bez + rimw, bez + rimw), img)

    iw, ih = round(sw * ISLAND["w_ratio"]), round(sw * ISLAND["h_ratio"])
    top = bez + rimw + round(sw * ISLAND["top_ratio"])
    ix = ox + bez + rimw + (sw - iw) // 2
    d.rounded_rectangle([ix, top, ix + iw, top + ih], radius=ih // 2, fill=(0, 0, 0, 255))
    out.alpha_composite(camera_lens(ih), (ix + iw - ih, top))
    return out


def camera_lens(ih):
    """The front camera at the island's right end (a plain black pill reads as fake):
    concentric with the right cap, a dark ring, a navy glass, one small glint.
    Drawn at 4x and scaled down, so the edges are smooth."""
    s = 4
    size = ih * s
    lens = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lens)
    c, r = size / 2, size * 0.19
    d.ellipse([c - r, c - r, c + r, c + r], fill=(26, 26, 32, 255))
    g = r * 0.68
    d.ellipse([c - g, c - g, c + g, c + g], fill=(12, 17, 34, 255))
    h, hx, hy = r * 0.2, c - r * 0.3, c - r * 0.32
    d.ellipse([hx - h, hy - h, hx + h, hy + h], fill=(70, 78, 112, 200))
    return lens.resize((ih, ih), Image.LANCZOS)


def save_webp(img, name, quality=82):
    path = os.path.join(OUT, name)
    img.save(path, "WEBP", quality=quality, method=6)
    print(f"{name:22s} {img.size[0]}x{img.size[1]}  {os.path.getsize(path) // 1024}KB")


def largest_png(imageset):
    folder = os.path.join(XCASSETS, f"{imageset}.imageset")
    pngs = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".png")]
    return max(pngs, key=os.path.getsize)


def gradient(w, h):
    """The store's 'violet': top colour at (0,0), bottom colour at (0.72w, h)."""
    g = Image.new("RGB", (w, h))
    px = g.load()
    vx, vy = 0.72 * w, 1.0 * h
    norm = vx * vx + vy * vy
    for y in range(h):
        for x in range(w):
            t = max(0.0, min(1.0, (x * vx + y * vy) / norm))
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(VIOLET_TOP, VIOLET_BOTTOM))
    return g


def og_image():
    W, H = 1200, 630
    img = gradient(W, H).convert("RGBA")
    d = ImageDraw.Draw(img)

    icon = Image.open(ICON).convert("RGBA").resize((96, 96), Image.LANCZOS)
    mask = Image.new("L", icon.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), icon.size], radius=22, fill=255)
    icon.putalpha(mask)
    img.alpha_composite(icon, (72, 96))

    d.text((72, 214), "Choru", font=ImageFont.truetype(FONT_BLACK, 112), fill="white")
    sub = ImageFont.truetype(FONT_BOLD, 46)
    d.text((72, 352), "Every chore comes back", font=sub, fill=(255, 255, 255, 235))
    d.text((72, 406), "when it’s due.", font=sub, fill=(255, 255, 255, 235))
    d.text((72, 500), "Family chore chart for iPhone", font=ImageFont.truetype(FONT_BOLD, 30),
           fill=(0xE4, 0xD4, 0xFF, 255))

    dragon = Image.open(largest_png("ChoruReady")).convert("RGBA")
    dragon.thumbnail((470, 470), Image.LANCZOS)
    img.alpha_composite(dragon, (W - dragon.width - 60, H - dragon.height - 50))

    path = os.path.join(OUT, "og-image.png")
    img.convert("RGB").save(path, "PNG", optimize=True)
    print(f"og-image.png           {W}x{H}  {os.path.getsize(path) // 1024}KB")


def icons():
    src = Image.open(ICON).convert("RGBA")
    src.resize((180, 180), Image.LANCZOS).save(os.path.join(OUT, "apple-touch-icon.png"), optimize=True)
    src.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, "icon-512.png"), optimize=True)
    src.resize((32, 32), Image.LANCZOS).save(os.path.join(OUT, "favicon-32.png"), optimize=True)
    src.save(os.path.join(SITE, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    print("icons: apple-touch-icon 180, icon-512, favicon-32, favicon.ico 16/32/48")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    icons()
    for name, raw in SHOTS.items():
        framed = shell(Image.open(os.path.join(RAW, raw)))
        height = round(WEB_W * framed.height / framed.width)
        save_webp(framed.resize((WEB_W, height), Image.LANCZOS), name)
    for name, imageset in MASCOTS.items():
        m = Image.open(largest_png(imageset)).convert("RGBA")
        m.thumbnail((440, 440), Image.LANCZOS)
        save_webp(m, name, quality=88)
    og_image()
