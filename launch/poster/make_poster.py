"""The myGeeKy wall poster: A3 portrait at 300 dpi (prints sharp at A2 too).

    python launch/poster/make_poster.py   ->  launch/poster/mygeeky-poster.png and .pdf

Drawn from the repo's own screenshots and icon, so it can be re-made whenever
the app changes (run docs/make_screenshots.py first for fresh screenshots).
Two QR codes: Google Play for the phone app, and the GitHub page for the computer
(it opens everywhere, including networks that block young domains).
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "screenshots"
OUT = Path(__file__).parent
W, H = 3508, 4961                      # A3 at 300 dpi
QR_URL = "https://github.com/mygeeky/myGeeKy"
PLAY_URL = "https://play.google.com/store/apps/details?id=org.mygeeky.app"
PHONE_SHOTS = SHOTS / "phone"

TEXT = (244, 244, 250)
MUTED = (182, 184, 204)
PINK, VIOLET, CYAN = (255, 111, 216), (122, 92, 255), (127, 216, 255)
GREEN, AMBER = (52, 211, 153), (255, 196, 87)


WEB_FONTS = ROOT / "website" / "fonts"
WEIGHTS = {"regular": 400, "semi": 600, "bold": 700, "black": 900, "light": 300}


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    """Segoe UI on Windows; elsewhere the website's own fonts (Inter, JetBrains Mono), so it looks the same anywhere."""
    name = {"regular": "segoeui.ttf", "bold": "segoeuib.ttf", "semi": "seguisb.ttf", "black": "seguibl.ttf",
            "light": "segoeuil.ttf", "mono": "consola.ttf"}[weight]
    try:
        return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
    except OSError:
        pass
    if weight == "mono":
        return ImageFont.truetype(str(WEB_FONTS / "JetBrainsMono-latin.woff2"), size)
    f = ImageFont.truetype(str(WEB_FONTS / "Inter-latin.woff2"), size)
    try:
        f.set_variation_by_axes([WEIGHTS[weight]])
    except OSError:
        pass
    return f


def _emoji_font() -> ImageFont.FreeTypeFont:
    for path in ("C:/Windows/Fonts/seguiemj.ttf", "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
                 "/System/Library/Fonts/Apple Color Emoji.ttc"):
        try:
            return ImageFont.truetype(path, 109)      # 109: the one size a colour-bitmap emoji font takes
        except OSError:
            continue
    raise SystemExit("no colour emoji font found")


EMOJI = _emoji_font()


def emoji(im: Image.Image, chars: str, xy, size: int) -> None:
    tmp = Image.new("RGBA", (int(EMOJI.size * 1.4) * len(chars), int(EMOJI.size * 1.4)), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((0, 0), chars.replace(chr(0xFE0F), ""), font=EMOJI, embedded_color=True)
    tmp = tmp.crop(tmp.getbbox())
    k = size / tmp.height
    tmp = tmp.resize((int(tmp.width * k), int(tmp.height * k)), Image.LANCZOS)
    im.alpha_composite(tmp, (int(xy[0]), int(xy[1])))


def gradient_text(im: Image.Image, text: str, xy, fnt, colors=(PINK, VIOLET, CYAN), center=False) -> int:
    d = ImageDraw.Draw(im)
    l, t, r, b = d.textbbox((0, 0), text, font=fnt)
    w, h = r - l, b - t
    x = xy[0] - w // 2 if center else xy[0]
    mask = Image.new("L", (w + 20, h + 40), 0)
    ImageDraw.Draw(mask).text((-l + 10, -t + 10), text, font=fnt, fill=255)
    grad = Image.new("RGBA", mask.size)
    gd = ImageDraw.Draw(grad)
    for i in range(mask.width):
        k = i / max(mask.width - 1, 1)
        if k < 0.5:
            c = [int(colors[0][j] + (colors[1][j] - colors[0][j]) * k * 2) for j in range(3)]
        else:
            c = [int(colors[1][j] + (colors[2][j] - colors[1][j]) * (k - 0.5) * 2) for j in range(3)]
        gd.line([(i, 0), (i, mask.height)], fill=(*c, 255))
    grad.putalpha(mask)
    im.alpha_composite(grad, (int(x - 10), int(xy[1] - 10)))
    return h


def text(im, s, xy, fnt, fill=TEXT, center=False, anchor_w=None):
    d = ImageDraw.Draw(im)
    if center:
        l, _, r, _ = d.textbbox((0, 0), s, font=fnt)
        xy = (xy[0] - (r - l) // 2 - l, xy[1])
    d.text(xy, s, font=fnt, fill=fill)


def wrap(s: str, fnt, width: int) -> list[str]:
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    lines, cur = [], ""
    for word in s.split():
        test = (cur + " " + word).strip()
        if d.textlength(test, font=fnt) > width and cur:
            lines.append(cur)
            cur = word
        else:
            cur = test
    return lines + [cur]


def background() -> Image.Image:
    bg = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=(int(34 - 20 * k), int(20 - 6 * k), int(64 - 38 * k), 255))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    for (cx, cy, r, col) in ((0.15, 0.10, 1300, (*PINK, 95)), (0.92, 0.18, 1200, (*VIOLET, 110)),
                             (0.80, 0.58, 1300, (*CYAN, 60)), (0.10, 0.70, 1100, (*VIOLET, 70))):
        g.ellipse([W * cx - r, H * cy - r, W * cx + r, H * cy + r], fill=col)
    bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(320)))
    stars = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    s = ImageDraw.Draw(stars)
    rnd = random.Random(7)
    for _ in range(420):
        x, y, r = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(1.2, 4.2)
        s.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rnd.randint(40, 150)))
    bg.alpha_composite(stars)
    return bg


def shot(im: Image.Image, path: Path, center, height: int, angle: float = 0.0) -> None:
    src = Image.open(path).convert("RGBA")
    k = height / src.height
    src = src.resize((int(src.width * k), height), Image.LANCZOS)
    mask = Image.new("L", src.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, src.width - 1, src.height - 1], 54, fill=255)
    src.putalpha(mask)
    pad = 160
    layer = Image.new("RGBA", (src.width + pad * 2, src.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([pad, pad + 40, pad + src.width, pad + src.height + 40], 60,
                                         fill=(0, 0, 0, 170))
    layer.alpha_composite(sh.filter(ImageFilter.GaussianBlur(50)))
    layer.alpha_composite(src, (pad, pad))
    if angle:
        layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    im.alpha_composite(layer, (int(center[0] - layer.width / 2), int(center[1] - layer.height / 2)))


def card(im, box, radius=56, fill=(255, 255, 255, 18), outline=(255, 255, 255, 46)):
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius, fill=fill, outline=outline, width=4)
    im.alpha_composite(layer)


def qr(url: str, size: int) -> Image.Image:
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=20, border=2)
    q.add_data(url)
    q.make(fit=True)
    img = q.make_image(fill_color="#12121c", back_color="white").convert("RGBA")
    return img.resize((size, size), Image.NEAREST)


FEATURES = [
    ("📈", "Rising skills", "what your field is starting to use, before everyone else", GREEN),
    ("🧭", "Protocols", "a step-by-step road map for any skill, reviewed for your field", CYAN),
    ("🏆", "Quiz", "every answer quotes the source that proves it", AMBER),
    ("💼", "Jobs and scholarships", "verified positions and funding, checked by hand", PINK),
    ("🗓️", "Seasons", "the yearly calls: conferences, scholarships, schools", VIOLET),
    ("🎮", "Play with GeeKOc", "fourteen short games made from your own field", PINK),
]


def main() -> None:
    im = background()
    M = 230                                  # side margin

    # ---- header: the character on the left; the name and the promise on the right
    top = 200
    art = Image.open(OUT / "character-full.jpg").convert("RGBA")
    art = art.crop((90, 470, art.width - 90, art.height - 40))          # its own title is on the right instead
    art_w = 1480
    art = art.resize((art_w, round(art.height * art_w / art.width)), Image.LANCZOS)
    rounded = Image.new("L", art.size, 0)
    ImageDraw.Draw(rounded).rounded_rectangle([0, 0, art.width - 1, art.height - 1], 70, fill=255)
    art.putalpha(rounded)
    im.alpha_composite(art, (M - 40, top))

    rx = M - 40 + art_w + 120                                            # the right column
    icon = Image.open(ROOT / "src/mygeeky/gui/assets/icon.png").convert("RGBA").resize((330, 330), Image.LANCZOS)
    glow = Image.new("RGBA", (700, 700), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([120, 120, 580, 580], fill=(*PINK, 90))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(70)), (rx - 185, top - 170))
    im.alpha_composite(icon, (rx, top + 10))
    y = top + 390
    gradient_text(im, "myGeeKy", (rx, y), font(250, "black"))
    y += 360
    for line in ("Your geeky friend", "who helps you"):
        text(im, line, (rx, y), font(132, "black"), TEXT)
        y += 165
    gradient_text(im, "grow, quietly.", (rx, y), font(132, "black"))
    y += 195
    for line in wrap("On your phone and as a small panel on your computer. It reads your field, shows you what "
                     "matters, and only suggests: it never acts for you.", font(62), W - M - rx):
        text(im, line, (rx, y), font(62), MUTED)
        y += 86
    y = max(y, top + art.height) + 80

    # ---- the phone on each side, the computer's panel in the middle
    y_shots = y + 760
    shot(im, PHONE_SHOTS / "protocols.png", (W * 0.165, y_shots + 70), 1420, angle=6)
    shot(im, PHONE_SHOTS / "chances.png", (W * 0.835, y_shots + 70), 1420, angle=-6)
    shot(im, SHOTS / "grow-skills.png", (W * 0.5, y_shots), 1300)

    # ---- what you get, every day
    y = y_shots + 820
    cols, gap = 3, 50
    cw = (W - 2 * M - gap * (cols - 1)) // cols
    ch = 300
    for i, (em, title, sub, col) in enumerate(FEATURES):
        cx = M + (i % cols) * (cw + gap)
        cy = y + (i // cols) * (ch + 40)
        card(im, [cx, cy, cx + cw, cy + ch], radius=48)
        ImageDraw.Draw(im).rounded_rectangle([cx + 50, cy + 46, cx + 150, cy + 58], 6, fill=(*col, 255))
        emoji(im, em, (cx + cw - 160, cy + 36), 100)
        tl = wrap(title, font(62, "bold"), cw - 230)[:2]
        for j, line in enumerate(tl):
            text(im, line, (cx + 50, cy + 84 + j * 74), font(62, "bold"), TEXT)
        sy = cy + 84 + len(tl) * 74 + 14
        for j, line in enumerate(wrap(sub, font(46), cw - 100)[:4 - len(tl)]):
            text(im, line, (cx + 50, sy + j * 58), font(46), MUTED)
    y += 2 * (ch + 40) + 20

    # ---- get it
    band_top = y
    card(im, [M, band_top, W - M, H - 200], radius=70, fill=(255, 255, 255, 26), outline=(255, 255, 255, 70))
    qs = 400
    band_bottom = H - 200
    qx = W - M - 100
    for url, label in ((QR_URL, "Computer"), (PLAY_URL, "Android")):   # right to left: GitHub, then Google Play
        q = qr(url, qs)
        frame = Image.new("RGBA", (q.width + 50, q.height + 50), (255, 255, 255, 255))
        fm = Image.new("L", frame.size, 0)
        ImageDraw.Draw(fm).rounded_rectangle([0, 0, frame.width - 1, frame.height - 1], 36, fill=255)
        frame.putalpha(fm)
        frame.alpha_composite(q, (25, 25))
        qx -= frame.width
        qy = band_top + (band_bottom - band_top - frame.height - 90) // 2
        im.alpha_composite(frame, (qx, qy))
        text(im, label, (qx + frame.width // 2, qy + frame.height + 22), font(56, "bold"), CYAN, center=True)
        qx -= 70
    tx = M + 110
    ty = band_top + 70
    gradient_text(im, "Scan me to get it", (tx, ty), font(112, "black"))
    ty += 165
    text(im, "Free and open source.", (tx, ty), font(60, "semi"), TEXT)
    ty += 100
    for label, value in (("Android", "myGeeKy on Google Play"),
                         ("Windows", "the installer: Next, Next, Finish"),
                         ("Anywhere", "pip install mygeeky"),
                         ("Website", "mygeeky.org")):
        text(im, label, (tx, ty), font(52, "bold"), CYAN)
        text(im, value, (tx + 290, ty), font(52, "mono" if value.startswith("pip") else "regular"), TEXT)
        ty += 78

    text(im, "Free, no ads, no account needed. Your data stays yours.   \u00b7   mygeeky.org",
         (W // 2, H - 150), font(50, "semi"), MUTED, center=True)

    rgb = im.convert("RGB")
    for name in ("mygeeky-poster", "mygeeky-poster-v2"):     # the first may be open in a viewer
        try:
            rgb.save(OUT / f"{name}.png", dpi=(300, 300), optimize=True)
            rgb.save(OUT / f"{name}.pdf", resolution=300)
            break
        except OSError:
            continue
    try:
        rgb.resize((W // 4, H // 4), Image.LANCZOS).save(OUT / "mygeeky-poster-preview.png")
    except OSError:
        pass                                                   # open in a viewer: keep the old preview
    print("wrote", OUT / "mygeeky-poster.png", "and .pdf")


if __name__ == "__main__":
    main()
