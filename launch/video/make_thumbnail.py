"""YouTube thumbnail (1280x720), and the same picture for the website's video (which draws its own play
button, in the corner, so GeekOc's face stays clear).

    python launch/video/make_thumbnail.py

It looks like the video: the pale wall, the myGeeKy badge, the tagline in Playfair Display with the words
that matter in pink italic, See · Learn · Meet · Catch in dark gold, and GeekOc waving, drawn by the rig
in website/geekoc/geekoc.js (node and PySide6, as for the video).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
LOGO = ROOT / "src" / "mygeeky" / "gui" / "assets" / "icon_256.png"
ENGINE = ROOT / "website" / "geekoc" / "geekoc.js"
FONTS = HERE / "fonts"
WALL = HERE / "intro" / "walk-frames"          # the video's wall, if its frames have been extracted
W, H = 1920, 1080                               # drawn at video size, saved at 1280x720
INK, PINK, GOLD, SUBTLE = (40, 36, 60), (190, 40, 110), (156, 112, 24), (92, 86, 112)


def font(name: str, size: int, weight: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / name), size)
    f.set_variation_by_axes([weight])
    return f


def wall() -> Image.Image:
    """The empty wall from the video (the kid's last frame, with his spot taken from his first), or a
    pale gradient in its colours when those frames aren't on this machine."""
    frames = sorted(WALL.glob("*.jpg"))
    if frames:
        last = Image.open(frames[-1]).convert("RGB").resize((W, H))
        first = Image.open(frames[0]).convert("RGB").resize((W, H))
        last.paste(first.crop((1540, 0, W, H)), (1540, 0))
        return last.convert("RGBA")
    g = np.linspace(0, 1, H)[:, None, None]
    a = (np.array((250, 249, 252)) * (1 - g) + np.array((234, 232, 240)) * g).repeat(W, axis=1)
    return Image.fromarray(a.astype(np.uint8), "RGB").convert("RGBA")


def geekoc(size: int) -> Image.Image:
    """GeekOc waving, happy, as one still from the rig."""
    js = ("require(process.env.GEEKOC); const G = globalThis.GeekOc;"
          "process.stdout.write(G.svg({pose:'wave', face:'happy', t:1.2, size:Number(process.env.SIZE), id:'thumb'}));")
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True,
                         env={**os.environ, "GEEKOC": str(ENGINE), "SIZE": str(size)})
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    QGuiApplication.instance() or QGuiApplication([])
    r = QSvgRenderer(QByteArray(out.stdout.encode("utf-8")))
    q = QImage(size, size, QImage.Format_ARGB32)
    q.fill(Qt.transparent)
    p = QPainter(q)
    p.setRenderHint(QPainter.Antialiasing, True)
    r.render(p)
    p.end()
    tmp = HERE / "intro" / "_thumb_geekoc.png"
    q.save(str(tmp))
    im = Image.open(tmp).convert("RGBA")
    tmp.unlink()
    return im


def words(d: ImageDraw.ImageDraw, x: float, y: float, runs, gap: float) -> float:
    """Draw (text, font, colour) runs on one line; return where it ended."""
    for text, f, col in runs:
        d.text((x, y), text, font=f, fill=col)
        x += d.textlength(text, font=f) + gap
    return x


def thumbnail() -> Image.Image:
    im = wall()
    # a soft violet-to-pink glow behind GeekOc, so he stands off the wall
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((1150, 180, 1850, 880), fill=(170, 110, 255, 70))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(90)))
    g = geekoc(820)
    im.alpha_composite(g, (1500 - g.width // 2, 560 - g.height // 2))

    logo = Image.open(LOGO).convert("RGBA").resize((170, 170), Image.LANCZOS)
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((110, 112, 290, 292), fill=(60, 30, 90, 90))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16)))
    im.alpha_composite(logo, (115, 100))
    d = ImageDraw.Draw(im)
    d.text((310, 128), "myGeeKy", font=font("PlayfairDisplay.ttf", 104, 800), fill=INK)

    plain = font("PlayfairDisplay.ttf", 118, 750)
    fancy = font("PlayfairDisplay-Italic.ttf", 124, 850)
    sp = d.textlength(" ", font=plain)
    words(d, 110, 360, [("Your geeky friend", plain, INK)], sp)
    words(d, 110, 500, [("who helps you", plain, INK)], sp)
    words(d, 110, 640, [("grow, quietly.", fancy, PINK)], sp)

    tag = font("PlayfairDisplay.ttf", 54, 750)
    dot = font("PlayfairDisplay.ttf", 54, 500)
    x = 116
    for i, w in enumerate(("See", "Learn", "Meet", "Catch")):
        if i:
            x = words(d, x, 850, [("·", dot, SUBTLE)], 18)
        x = words(d, x, 850, [(w, tag, GOLD)], 18)

    return im.convert("RGB").resize((1280, 720), Image.LANCZOS)


if __name__ == "__main__":
    pic = thumbnail()
    pic.save(HERE / "youtube-thumbnail.png")
    pic.save(ROOT / "docs" / "video-thumbnail.png")
    print("thumbnails written")
