"""The phone pictures for the README, the website and the video, from emulator screenshots.

    adb exec-out screencap -p > home.png        # Home, the orbit open (README, video)
    adb exec-out screencap -p > protocols.png   # Grow -> Protocols
    adb exec-out screencap -p > chances.png     # Chances -> Jobs
    python docs/make_phone_hero.py home.png protocols.png chances.png

Writes docs/screenshots/phone/{hint,protocols,chances}.png (the status bar cut off, 780 px wide) and
docs/screenshots/phone/hero-phone-grow.png (the three side by side, Home in front, for the website).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots" / "phone"
STATUS = 120          # px of a 1080x2400 screenshot: the status bar and the band under it
WIDTH = 780


def phone(src: Path) -> Image.Image:
    im = Image.open(src).convert("RGB")
    im = im.crop((0, round(STATUS * im.width / 1080), im.width, im.height))
    return im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)


def rounded(im: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius, fill=255)
    out = im.convert("RGBA")
    out.putalpha(mask)
    return out


def hero(home: Image.Image, left: Image.Image, right: Image.Image) -> Image.Image:
    W, H = 2400, 1700
    bg = Image.new("RGB", (W, H))
    top, bottom = (36, 20, 64), (14, 12, 28)          # the website's dark violet, fading down
    px = ImageDraw.Draw(bg)
    for y in range(H):
        k = y / (H - 1)
        px.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * k) for a, b in zip(top, bottom)))
    canvas = bg.convert("RGBA")
    for im, h, cx in ((left, 1300, 640), (right, 1300, W - 640), (home, 1560, W // 2)):
        shot = rounded(im.resize((round(im.width * h / im.height), h), Image.LANCZOS), 48)
        x, y = cx - shot.width // 2, (H - h) // 2
        shadow = Image.new("RGBA", (shot.width + 120, shot.height + 120), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle([60, 60, shot.width + 60, shot.height + 60], 60, fill=(0, 0, 0, 170))
        canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(30)), (x - 60, y - 40))
        canvas.alpha_composite(shot, (x, y))
    return canvas.convert("RGB")


def main(home: str, protocols: str, chances: str) -> None:
    shots = {"hint": phone(Path(home)), "protocols": phone(Path(protocols)), "chances": phone(Path(chances))}
    for name, im in shots.items():
        im.save(OUT / f"{name}.png", optimize=True)
        print("  ", f"phone/{name}.png", im.size)
    hero(shots["hint"], shots["chances"], shots["protocols"]).save(OUT / "hero-phone-grow.png", optimize=True)
    print("   phone/hero-phone-grow.png")


if __name__ == "__main__":
    main(*sys.argv[1:4])
