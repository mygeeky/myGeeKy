"""Render the myGeeKy intro / installation video (1080p, ~2.75 min) with an
original synthesized soundtrack. It opens with intro/intro-source.mp4 (the character opening the laptop,
made with Gemini) from its 4th second to its end, then the story.

    pip install pillow numpy imageio-ffmpeg
    python launch/video/make_video.py            ->  launch/video/mygeeky-intro.mp4
    python launch/video/make_video.py --preview  ->  a few still frames only (fast)

Everything is drawn from the repo's own screenshots and icons, so the video
can be re-rendered whenever the app changes.
"""

from __future__ import annotations

import math
import os
import random
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "screenshots"
ASSETS = ROOT / "src" / "mygeeky" / "gui" / "assets"
OUT = Path(__file__).parent
W, H, FPS = 1920, 1080, 30

BG = (18, 18, 28)
TEXT = (240, 240, 245)
MUTED = (170, 172, 190)
PINK = (255, 111, 216)
VIOLET = (122, 92, 255)
CYAN = (127, 216, 255)
GREEN = (52, 211, 153)
AMBER = (255, 196, 87)
RED = (248, 113, 113)


# --------------------------------------------------------------------------- helpers
def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    name = "consola.ttf" if mono else ("segoeuib.ttf" if bold else "segoeui.ttf")
    return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)


EMOJI = ImageFont.truetype("C:/Windows/Fonts/seguiemj.ttf", 109)   # bitmap strikes: draw at 109, scale


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def fade(t: float, start: float, end: float, f: float = 0.6) -> float:
    """0 -> 1 over `f` s after start, 1 -> 0 over `f` s before end."""
    return ease((t - start) / f) * ease((end - t) / f)


_cache: dict[str, Image.Image] = {}


def img(path: Path) -> Image.Image:
    key = str(path)
    if key not in _cache:
        _cache[key] = Image.open(path).convert("RGBA")
    return _cache[key]


def background(t: float) -> Image.Image:
    """Dark gradient with two slowly drifting glows (pink, violet)."""
    base = Image.new("RGB", (W, H), BG)
    glow = Image.new("RGB", (W // 8, H // 8), (0, 0, 0))
    g = ImageDraw.Draw(glow)
    for cx, cy, r, col in ((0.78 + 0.05 * math.sin(t / 7), 0.15, 70, VIOLET),
                           (0.12, 0.35 + 0.05 * math.cos(t / 9), 55, PINK)):
        g.ellipse((cx * W / 8 - r, cy * H / 8 - r, cx * W / 8 + r, cy * H / 8 + r), fill=col)
    glow = glow.filter(ImageFilter.GaussianBlur(30)).resize((W, H), Image.BILINEAR)
    return Image.blend(base, glow, 0.22)


def text_center(im: Image.Image, txt: str, y: int, fnt, color, alpha: float = 1.0) -> None:
    if alpha <= 0:
        return
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w = d.textlength(txt, font=fnt)
    d.text(((W - w) / 2, y), txt, font=fnt, fill=color + (int(255 * alpha),))
    im.alpha_composite(layer)


def text_at(im: Image.Image, txt: str, xy, fnt, color, alpha: float = 1.0) -> None:
    if alpha <= 0:
        return
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(xy, txt, font=fnt, fill=color + (int(255 * alpha),))
    im.alpha_composite(layer)


def gradient_text(im: Image.Image, txt: str, y: int, fnt, alpha: float = 1.0) -> None:
    if alpha <= 0:
        return
    d = ImageDraw.Draw(im)
    w = int(d.textlength(txt, font=fnt))
    h = fnt.size + 20
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((0, 0), txt, font=fnt, fill=int(255 * alpha))
    grad = Image.new("RGBA", (w, h))
    gd = ImageDraw.Draw(grad)
    for x in range(w):
        k = x / max(w - 1, 1)
        gd.line([(x, 0), (x, h)], fill=tuple(int(PINK[i] + (VIOLET[i] - PINK[i]) * k) for i in range(3)) + (255,))
    grad.putalpha(mask)
    im.alpha_composite(grad, (int((W - w) / 2), y))


def emoji_raw(chars: str) -> Image.Image:
    """Emoji drawn whole: the font draws some glyphs above and left of where they're placed, so they get
    room on every side before being cropped to what was actually drawn."""
    chars = chars.replace(chr(0xFE0F), "")   # the emoji-style selector draws as an empty gap
    pad = EMOJI.size
    tmp = Image.new("RGBA", (2 * pad + int(EMOJI.size * 1.4) * len(chars), 2 * pad + int(EMOJI.size * 1.4)), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((pad, pad), chars, font=EMOJI, embedded_color=True)
    return tmp.crop(tmp.getbbox())


def emoji(im: Image.Image, chars: str, xy, size: int, alpha: float = 1.0) -> None:
    if alpha <= 0:
        return
    tmp = emoji_raw(chars)
    k = size / EMOJI.size
    tmp = tmp.resize((max(1, int(tmp.width * k)), max(1, int(tmp.height * k))), Image.LANCZOS)
    if alpha < 1:
        tmp.putalpha(tmp.getchannel("A").point(lambda a: int(a * alpha)))
    im.alpha_composite(tmp, (int(xy[0]), int(xy[1])))


def paste(im: Image.Image, src: Image.Image, center, height: int, alpha: float = 1.0, radius: int = 0,
          shadow: bool = True) -> None:
    if alpha <= 0:
        return
    k = height / src.height
    pic = src.resize((int(src.width * k), height), Image.LANCZOS)
    if radius:
        m = Image.new("L", pic.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, pic.width, pic.height), radius, fill=255)
        pic.putalpha(Image.fromarray(np.minimum(np.array(pic.getchannel("A")), np.array(m))))
    x, y = int(center[0] - pic.width / 2), int(center[1] - pic.height / 2)
    if shadow:
        sh = Image.new("RGBA", (pic.width + 120, pic.height + 120), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((60, 75, pic.width + 60, pic.height + 75), max(radius, 12),
                                             fill=(0, 0, 0, int(150 * alpha)))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(28)), (x - 60, y - 60))
    if alpha < 1:
        pic.putalpha(pic.getchannel("A").point(lambda a: int(a * alpha)))
    im.alpha_composite(pic, (x, y))


def heart(d: ImageDraw.ImageDraw, x: float, y: float, s: float, color) -> None:
    pts = []
    for i in range(40):
        a = math.tau * i / 40
        hx = 16 * math.sin(a) ** 3
        hy = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((x + hx * s / 32, y + hy * s / 32))
    d.polygon(pts, fill=color)


def hearts(im: Image.Image, t: float, origin, start: float, n: int = 7, rise: float = 330) -> None:
    rnd = random.Random(int(start * 100))
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(n):
        born = start + i * 0.35 + rnd.uniform(0, 0.2)
        life = rnd.uniform(2.6, 3.4)
        age = t - born
        if not 0 <= age <= life:
            continue
        k = age / life
        x = origin[0] + rnd.uniform(-30, 30) + rnd.choice((-1, 1)) * rnd.uniform(20, 70) * k \
            + math.sin(i + age * 4) * 10
        y = origin[1] - ease(k) * rise
        s = rnd.uniform(26, 40) * (1 - 0.6 * k)
        col = rnd.choice((PINK, (255, 143, 192), (255, 92, 138), (232, 111, 216)))
        heart(d, x, y, s, col + (int(230 * min(1, age / 0.25) * (1 - k) ** 1.3),))
    im.alpha_composite(layer.filter(ImageFilter.GaussianBlur(0.6)))


def caption(im: Image.Image, title: str, sub: str, alpha: float, y: int = 860) -> None:
    text_center(im, title, y, font(56, bold=True), TEXT, alpha)
    if sub:
        text_center(im, sub, y + 78, font(32), MUTED, alpha)


def section_title(im: Image.Image, t: float, number: str, title: str, sub: str) -> None:
    a = ease(t / 0.6) * ease((3.6 - t) / 0.5)
    text_center(im, number, 330, font(40, bold=True), PINK, a)
    gradient_text(im, title, 390, font(110, bold=True), a)
    text_center(im, sub, 560, font(38), MUTED, a)


# --------------------------------------------------------------------------- terminal
class Terminal:
    """A typed-out terminal session: [(at, kind, text)], kind in
    'cmd' (typed after a $ prompt), 'out' (printed), 'ask' (prompt + typed answer after '|')."""

    def __init__(self, script, title="Terminal", width=1500, height=700, cps=22):
        self.script, self.title, self.w, self.h, self.cps = script, title, width, height, cps

    def draw(self, im: Image.Image, t: float, center=(W // 2, 470), alpha: float = 1.0) -> None:
        if alpha <= 0:
            return
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((0, 0, self.w, self.h), 22, fill=(13, 13, 20, 245), outline=(255, 255, 255, 40))
        d.rounded_rectangle((0, 0, self.w, 54), 22, fill=(32, 32, 46, 255))
        d.rectangle((0, 30, self.w, 54), fill=(32, 32, 46, 255))
        for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
            d.ellipse((24 + i * 34, 17, 44 + i * 34, 37), fill=c + (255,))
        tw = d.textlength(self.title, font=font(24))
        d.text(((self.w - tw) / 2, 12), self.title, font=font(24), fill=MUTED + (255,))
        mono = font(30, mono=True)
        lines: list[tuple[str, tuple]] = []
        for at, kind, txt in self.script:
            if t < at:
                break
            typed = int((t - at) * self.cps)
            if kind == "cmd":
                lines.append(("$ " + txt[:typed], CYAN))
            elif kind == "out":
                for ln in txt.split("\n"):
                    color = GREEN if ln.strip().startswith("✓") else (RED if ln.strip().startswith("✗") else TEXT)
                    lines.append((ln, color))
            elif kind == "ask":
                q, a = txt.split("|", 1)
                lines.append((q + a[:typed], TEXT))
        lines = lines[-int((self.h - 90) / 42):]
        sym = ImageFont.truetype("C:/Windows/Fonts/seguisym.ttf", 30)
        for i, (ln, col) in enumerate(lines):
            x, y = 34, 78 + i * 42
            for part_i, part in enumerate(ln.split("✓")):   # Consolas has no check mark
                if part_i:
                    d.text((x, y), "✓", font=sym, fill=GREEN + (255,))
                    x += d.textlength("✓", font=sym)
                d.text((x, y), part, font=mono, fill=col + (255,))
                x += d.textlength(part, font=mono)
        if lines and int(t * 2) % 2 == 0:
            last = lines[-1][0]
            x = 34 + d.textlength(last, font=mono)
            y = 78 + (len(lines) - 1) * 42
            d.rectangle((x + 4, y + 4, x + 20, y + 36), fill=TEXT + (200,))
        if alpha < 1:
            layer.putalpha(layer.getchannel("A").point(lambda a: int(a * alpha)))
        sh = Image.new("RGBA", (self.w + 120, self.h + 120), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((60, 80, self.w + 60, self.h + 80), 22, fill=(0, 0, 0, int(160 * alpha)))
        x0, y0 = center[0] - self.w // 2, center[1] - self.h // 2
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(30)), (x0 - 60, y0 - 60))
        im.alpha_composite(layer, (x0, y0))


PIP = Terminal([
    (0.3, "cmd", "pip install mygeeky"),
    (1.6, "out", "Collecting mygeeky\n  Downloading mygeeky-0.4.2-py3-none-any.whl (635 kB)"),
    (2.6, "out", "Successfully installed mygeeky-0.4.2"),
], title="Any OS: one pip command", height=330)

INIT = Terminal([
    (0.3, "cmd", "mygeeky init"),
    (1.4, "ask", "Your GitHub username: |your-name"),
    (2.9, "ask", "CV: (p)ath to a .txt/.md/.pdf file, (t)ype, or (s)kip: |p"),
    (3.8, "ask", "Path to your CV file: |my_cv.pdf"),
    (5.0, "out", "Saved CV text (8,412 chars)"),
    (5.6, "ask", "ORCID iD: |0000-0002-1825-0097"),
    (7.2, "out", "Fetching your publications...\n  OpenAlex: 48 works, topics: GWAS, fine-mapping, genomics"),
    (8.8, "ask", "Topics/interests: |gwas, single-cell, bioinformatics"),
    (10.8, "ask", "Paste your GitHub token (input hidden): |********"),
    (12.0, "out", "Token stored securely in your OS keyring."),
    (13.0, "cmd", "mygeeky gui"),
    (14.2, "out", "Installing Qt for the myGeeKy panel (one time only)...\n✓ Qt is ready. The panel opens."),
], title="mygeeky init: tell it who you are")

BEACON = Terminal([
    (0.3, "cmd", "mygeeky beacon init"),
    (1.3, "out", "Step 1 of 3: your public beacon repo\n  1. Open github.com/new?name=mygeeky-beacon\n"
                 "  2. Check the owner, then click 'Create repository'"),
    (3.6, "out", "  ✓ your-name/mygeeky-beacon exists and is public."),
    (4.6, "out", "Step 2 of 3: a token that can write to that repo only\n"
                 "  Only select repositories -> mygeeky-beacon\n  Contents -> Read and write"),
    (7.0, "ask", "Paste the token (input hidden): |********"),
    (8.2, "out", "  ✓ The token works. It's stored in your OS keyring."),
    (9.0, "out", "Step 3 of 3: checking that others can see you\n  ✓ beacon.json is published"),
    (10.4, "out", "Your beacon is live. Signals are private: only the person you\n"
                  "  send one to can read it, and no reply is ever expected."),
], title="mygeeky beacon init: join Signals (optional)")


# --------------------------------------------------------------------------- scenes
def s_reveal(t: float) -> Image.Image:
    im = background(t + 12).convert("RGBA")
    k = ease(t / 1.4)
    size = int(150 + 130 * k)
    halo = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse((W / 2 - size, 380 - size, W / 2 + size, 380 + size), fill=PINK + (int(70 * k),))
    im.alpha_composite(halo.filter(ImageFilter.GaussianBlur(60)))
    hearts(im, t, (W / 2, 380 - size / 2.4), 0.9, n=9, rise=300)
    paste(im, img(ASSETS / "icon_256.png"), (W / 2, 380), size, alpha=k, shadow=False)
    text_center(im, "myGeeKy", 560, font(130, bold=True), TEXT, ease((t - 1.0) / 0.7))
    gradient_text(im, "a quiet companion that helps you grow", 730, font(54, bold=True), ease((t - 1.8) / 0.7))
    return im


FEATURES = [
    ("🫂", "People", "who share your research and will follow you back", CYAN),
    ("🛠️", "Projects", "repos in your field that welcome your pull requests", GREEN),
    ("📈", "Pulse", "what's rising in your field, every day", AMBER),
    ("🔬", "Research", "papers gaining citations fastest, and their code", GREEN),
    ("🗞️", "News", "arXiv, bioRxiv and Hacker News, for your topics", RED),
    ("📰", "Activity", "what your people are building right now", VIOLET),
    ("🙏", "Signals", "private thank-yous; no reply needed", PINK),
    ("🌱", "Rising Skills", "what's growing in your field, and missing from you", GREEN),
    ("🧭", "Protocols", "a road map for any skill: what to learn, in order", CYAN),
    ("📚", "Learn", "hand-picked free courses, books and tutorials", AMBER),
    ("🎉", "Wins", "new stars, forks and citations of your work", PINK),
    ("🤝", "Collaborators", "people whose skills complement yours", VIOLET),
    ("🎯", "Chances", "verified jobs, funding and conferences, before the deadline", PINK),
    ("🧠", "Learning", "learns what you're into, keeps room to explore", VIOLET),
    ("💡", "Ideas", "send ideas and problems straight to the maker", AMBER),
]
FEATURE_SECS = 1.45          # each feature: roll in, show itself, burst
FEATURES_START = 1.6         # after the title
_emoji_cache: dict[tuple[str, int], Image.Image] = {}


def emoji_image(chars: str, size: int) -> Image.Image:
    """An emoji as a picture (to spin and scale), cached."""
    key = (chars, size)
    if key not in _emoji_cache:
        tmp = emoji_raw(chars)
        k = size / max(tmp.width, tmp.height)
        _emoji_cache[key] = tmp.resize((max(1, int(tmp.width * k)), max(1, int(tmp.height * k))), Image.LANCZOS)
    return _emoji_cache[key]


def feature_roll(im: Image.Image, t: float, em: str, name: str, line: str, col, seed: int) -> None:
    """One feature: its logo, in a glowing bubble, rolls in from the left (spinning like a wheel), stops in
    the middle with its name, then bursts like a bubble -- a ring of droplets flies out and it's gone."""
    cx, cy, r = W / 2, 470, 120
    roll_t, hold_t = 0.55, 0.55
    burst_t = FEATURE_SECS - roll_t - hold_t
    if t < roll_t:                                           # rolling in: fast, then settling (ease-out, a small bounce)
        k = t / roll_t
        p = 1 - (1 - k) ** 3
        x = -r + (cx + r) * p + 18 * math.sin(k * math.pi) * (1 - k)
        angle = -(x - cx) / r * 180 / math.pi             # rolls without slipping: angle = distance / radius
        scale, alpha, burst = 1.0, 1.0, 0.0
    elif t < roll_t + hold_t:
        k = (t - roll_t) / hold_t
        x, angle = cx, 0.0
        scale, alpha, burst = 1 + 0.05 * math.sin(k * math.pi), 1.0, 0.0
    else:
        k = min(1.0, (t - roll_t - hold_t) / burst_t)
        x, angle = cx, 0.0
        scale, alpha, burst = 1 + 0.35 * k, max(0.0, 1 - k * 2.2), k
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rr = r * scale
    if alpha > 0:                                            # the bubble: a soft glow, a thin rim and a shine
        glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((x - rr * 1.25, cy - rr * 1.25, x + rr * 1.25, cy + rr * 1.25),
                                     fill=col + (int(70 * alpha),))
        im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(28)))
        d.ellipse((x - rr, cy - rr, x + rr, cy + rr), fill=(255, 255, 255, int(18 * alpha)),
                  outline=col + (int(230 * alpha),), width=4)
        d.arc((x - rr * 0.78, cy - rr * 0.78, x + rr * 0.78, cy + rr * 0.78), 200, 250,
              fill=(255, 255, 255, int(150 * alpha)), width=6)
        im.alpha_composite(layer)
        icon = emoji_image(em, int(r * 1.05))
        if scale != 1:
            icon = icon.resize((max(1, int(icon.width * scale)), max(1, int(icon.height * scale))), Image.LANCZOS)
        icon = icon.rotate(angle, resample=Image.BICUBIC, expand=True)
        if alpha < 1:
            icon.putalpha(icon.getchannel("A").point(lambda a: int(a * alpha)))
        im.alpha_composite(icon, (int(x - icon.width / 2), int(cy - icon.height / 2)))
    if burst > 0:                                            # the pop: a ring that races out, droplets that fly and fade
        layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        ring = r * (1 + 1.6 * burst)
        d.ellipse((cx - ring, cy - ring, cx + ring, cy + ring), outline=col + (int(200 * (1 - burst)),),
                  width=max(1, int(6 * (1 - burst))))
        rnd = random.Random(seed)
        for _ in range(16):
            a = rnd.uniform(0, 2 * math.pi)
            dist = r * (1.0 + rnd.uniform(0.8, 2.2) * burst)
            px, py = cx + math.cos(a) * dist, cy + math.sin(a) * dist + 60 * burst ** 2   # a little gravity
            s = rnd.uniform(5, 13) * (1 - burst * 0.7)
            d.ellipse((px - s, py - s, px + s, py + s), fill=col + (int(230 * (1 - burst)),))
        im.alpha_composite(layer)
    # its name and what it does, under the bubble, while it's there
    ta = ease((t - roll_t + 0.15) / 0.25) * (1 - ease((t - roll_t - hold_t) / 0.25))
    if ta > 0:
        text_center(im, name, cy + r + 50, font(78, bold=True), col, ta)
        text_center(im, line, cy + r + 150, font(40), MUTED, ta)


def s_pillars(t: float) -> Image.Image:
    """Every feature, one by one: each logo rolls in from the left and bursts like a bubble."""
    im = background(t + 20).convert("RGBA")
    total = FEATURES_START + len(FEATURES) * FEATURE_SECS + 0.4
    a = ease(t / 0.6) * ease((total - t) / 0.5)
    text_center(im, "One profile. Your whole field.", 90, font(76, bold=True), TEXT, a)
    text_center(im, "from your CV, your repos, and your ORCID & Google Scholar papers", 195, font(36), MUTED, a)
    i = int((t - FEATURES_START) // FEATURE_SECS)
    if 0 <= i < len(FEATURES):
        em, name, line, col = FEATURES[i]
        feature_roll(im, t - FEATURES_START - i * FEATURE_SECS, em, name, line, col, seed=i)
        # progress: a dot per feature
        n = len(FEATURES)
        x0 = W / 2 - (n - 1) * 14
        dots = ImageDraw.Draw(im)
        for k in range(n):
            c = FEATURES[k][3] if k <= i else (90, 92, 110)
            rr = 6 if k == i else 4
            dots.ellipse((x0 + k * 28 - rr, 1010 - rr, x0 + k * 28 + rr, 1010 + rr), fill=c + (255,))
    return im


PILLARS_SECS = FEATURES_START + len(FEATURES) * FEATURE_SECS + 0.4


def s_install(t: float) -> Image.Image:
    im = background(t + 40).convert("RGBA")
    if t < 3.6:
        section_title(im, t, "STEP 1", "Install", "one minute, no admin rights")
        return im
    t -= 3.6
    pages = ["setup-welcome.png", "setup-github.png", "setup-signals.png", "setup-finish.png"]
    labels = ["Download MyGeeKySetup.exe: it installs Python and Git if needed",
              "Token 1: checked to be truly read-only, kept in your keyring",
              "Signals: token 2 is checked to write to one repo only", "Start menu, startup, and you're done"]
    seg = 3.4
    for i, p in enumerate(pages):
        a = fade(t, i * seg, (i + 1) * seg + 0.4, 0.5)
        if a > 0:
            zoom = 1 + 0.03 * ((t - i * seg) / seg)
            paste(im, img(SHOTS / p), (W / 2, 470), int(720 * zoom), alpha=a, radius=18)
            caption(im, labels[i], "", a, y=890)
    text_center(im, "WINDOWS: Next  →  Next  →  Finish", 40, font(40, bold=True), PINK, fade(t, 0, 4 * seg + 0.4))
    if t > 4 * seg + 0.4:
        tt = t - (4 * seg + 0.4)
        PIP.draw(im, tt, center=(W // 2, 480), alpha=ease(tt / 0.5) * ease((5.6 - tt) / 0.5))
        caption(im, "macOS, Linux or Windows: one pip command", "the panel sets up its own GUI library the first time",
                ease(tt / 0.5) * ease((5.6 - tt) / 0.5), y=760)
    return im


def s_configure(t: float) -> Image.Image:
    im = background(t + 60).convert("RGBA")
    if t < 3.6:
        section_title(im, t, "STEP 2", "Configure", "a few answers, and it knows your field")
        return im
    t -= 3.6
    a = ease(t / 0.5) * ease((17.4 - t) / 0.5)
    INIT.draw(im, t, center=(W // 2, 470), alpha=a)
    caption(im, "Your CV and papers become your profile", "only your GitHub username is required", a, y=880)
    return im


def s_signals(t: float) -> Image.Image:
    im = background(t + 80).convert("RGBA")
    if t < 3.6:
        section_title(im, t, "STEP 3 · OPTIONAL", "Join Signals", "private thank-yous between myGeeKy users")
        emoji(im, "🙏📚👀🤝", (W / 2 - 230, 650), 100, ease(t / 0.6) * ease((3.6 - t) / 0.5))
        return im
    t -= 3.6
    a = ease(t / 0.5) * ease((12.6 - t) / 0.5)
    BEACON.draw(im, t, center=(W // 2, 470), alpha=a)
    caption(im, "It walks you through every step", "and checks each one worked", a, y=880)
    return im


TOUR = [
    ("suggestions.png", "People in your field who'll follow you back",
     "and the domain experts a follower count would bury"),
    ("repos.png", "Projects that welcome your pull requests", "starter issues, and maintainers who actually merge"),
    ("market.png", "The pulse of your field", "stars, commits and downloads: who's rising this week"),
    ("signals.png", "Say thanks, privately", "only they can read it, and no reply is expected"),
    ("grow-skills.png", "Rising skills: what to learn next", "growing in your field, missing from your profile"),
    ("grow-protocols.png", "A road map for any skill", "skip what you know; repos, papers and books for each step"),
    ("chances-jobs.png", "Verified jobs, funding and conferences", "checked by hand, matched to you, gone after the deadline"),
    ("activity.png", "What your people are building, live", "one card per person, right on your screen edge"),
    ("research.png", "The papers behind the code", "rising papers, their repos, and the people behind them"),
    ("news.png", "News from your field, not everyone's", "arXiv, bioRxiv and Hacker News, matched to you"),
    ("model.png", "See what myGeeKy knows about you", "your field, what you're into lately, and new territory"),
]


def s_tour(t: float) -> Image.Image:
    im = background(t + 100).convert("RGBA")
    if t < 3.6:
        section_title(im, t, "STEP 4", "Meet your panel", "always on top, on the edge of your screen")
        return im
    t -= 3.6
    seg = 5.0
    for i, (shot, title, sub) in enumerate(TOUR):
        a = fade(t, i * seg, (i + 1) * seg, 0.45)   # no overlap: captions sit where the next shot goes
        if a <= 0:
            continue
        k = (t - i * seg) / seg
        side = -1 if i % 2 == 0 else 1
        px = W / 2 + side * 420 + side * 20 * k
        paste(im, img(SHOTS / shot), (px, 540), int(800 * (1 + 0.04 * k)), alpha=a, radius=26)
        tx = 170 if side == 1 else W / 2 + 110
        lines, cur, words = [], "", title.split()
        for wd in words:
            test = (cur + " " + wd).strip()
            if ImageDraw.Draw(im).textlength(test, font=font(64, bold=True)) > 700:
                lines.append(cur)
                cur = wd
            else:
                cur = test
        lines.append(cur)
        for j, ln in enumerate(lines):
            text_at(im, ln, (tx, 400 + j * 80), font(64, bold=True), TEXT, a)
        y = 400 + len(lines) * 80 + 20
        if "👋" in sub:
            emoji(im, "👋📚🤝", (tx, y), 54, a)
            text_at(im, "(example data)", (tx, y + 80), font(32), MUTED, a)
        else:
            text_at(im, sub, (tx, y), font(34), MUTED, a)
    return im


PHONE = [
    ("live.png", "Spin a ring with your thumb", "your circle inside, the world outside, you in the middle"),
    ("protocols.png", "Your road map, in your pocket", "every step, its check, and what to learn from"),
    ("chances.png", "Chances, wherever you are", "jobs, funding and conferences that fit you"),
]


def s_phone(t: float) -> Image.Image:
    im = background(t + 120).convert("RGBA")
    if t < 3.0:
        section_title(im, t, "ALSO", "On your phone", "your world, in orbit")
        return im
    t -= 3.0
    for i, (shot, _, _) in enumerate(PHONE):
        a = ease((t - i * 2.4) / 0.6)
        if a <= 0:
            continue
        rise = 30 * (1 - a)
        paste(im, img(SHOTS / "phone" / shot), (W / 2 + (i - 1) * 520, 455 + rise), 760, alpha=a, radius=44)
    i = min(int(t // 2.4), len(PHONE) - 1)
    a = fade(t, i * 2.4, i * 2.4 + 2.4 if i < len(PHONE) - 1 else 99, 0.4)
    caption(im, PHONE[i][1], PHONE[i][2], a, y=900)
    return im


def s_close(t: float) -> Image.Image:
    im = background(t + 140).convert("RGBA")
    a = ease(t / 0.8)
    hearts(im, t, (W / 2, 300), 0.4, n=10, rise=260)
    hearts(im, t, (W / 2, 300), 3.6, n=8, rise=260)
    paste(im, img(ASSETS / "icon_256.png"), (W / 2, 300), 230, alpha=a, shadow=False)
    gradient_text(im, "Your corner of GitHub.", 450, font(96, bold=True), ease((t - 0.6) / 0.7))
    text_center(im, "Free and open source. It only suggests; it never acts for you.", 600, font(38), MUTED,
                ease((t - 1.3) / 0.7))
    pill = Image.new("RGBA", im.size, (0, 0, 0, 0))
    pa = ease((t - 2.0) / 0.7)
    ImageDraw.Draw(pill).rounded_rectangle((W / 2 - 330, 700, W / 2 + 330, 790), 20,
                                           fill=(0, 0, 0, int(120 * pa)), outline=(255, 255, 255, int(50 * pa)))
    im.alpha_composite(pill)
    text_center(im, "pip install mygeeky", 718, font(46, mono=True), CYAN, pa)
    text_center(im, "mygeeky.org", 840, font(54, bold=True), TEXT, ease((t - 2.6) / 0.7))
    text_center(im, "github.com/mygeeky/myGeeKy  ·  ideas welcome", 920, font(32), MUTED, ease((t - 3.0) / 0.7))
    return im


# --------------------------------------------------------------------------- the opening
#
# The kid walks in and stops at the far right. Three lines promise him the world; as each one lands, more
# of the world falls out of the sky, until it is a hill burying him and the promise has become the
# problem. Then GeekOc swims in, the hill drains away in his wake, and the noise stops.
#
# The clip is launch/video/intro/walk-in-fixed.mp4 -- already repaired and framed by fix_clip.py, at the
# film's own size, with the left 87% of every frame deliberately empty for the words.
WALK_SRC = OUT / "intro" / "walk-in-fixed.mp4"
WALK_FRAMES = OUT / "intro" / "walk-frames"
GEEK_FRAMES = OUT / "intro" / "geekoc"
ENGINE = ROOT / "website" / "geekoc" / "geekoc.js"

WALK_DUR = 24.0          # the kid, the lines, and the hill
SWIM_DUR = 5.2           # GeekOc crosses and clears it

# Each line arrives, and the sky gets heavier behind it.
LINES = [
    (1.4, 5.6, "Everything you need to grow is out there."),
    (5.9, 10.1, "Everyone you need to know is out there."),
    (10.4, 14.6, "Every chance that fits you is out there."),
]
TURN = (15.0, 18.8, "…and so is everything else.")
ASKS = [(19.2, 21.8, "So how do you find your fit?"),
        (21.9, 24.0, "And how do you stay focused while you look?")]

FALL_FROM, FALL_TO = 1.6, 18.6        # when things start and stop falling
ICONS = 190                            # how many end up in the pile


def extract_walk() -> None:
    """The repaired clip as frames at the film's rate."""
    import imageio_ffmpeg
    WALK_FRAMES.mkdir(parents=True, exist_ok=True)
    if list(WALK_FRAMES.glob("*.jpg")):
        return
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(WALK_SRC),
                    "-vf", f"scale={W}:{H}:flags=lanczos,fps={FPS}", "-q:v", "2",
                    str(WALK_FRAMES / "%04d.jpg")], check=True)


def render_geekoc() -> None:
    """GeekOc swimming, out of the rig that draws him everywhere else.

    He is NOT generated. The rig in website/geekoc/geekoc.js already swims -- it is how the website moves
    him -- so he comes out perfectly on-model, at whatever size we ask for, and can be re-rendered forever.
    A generated octopus would be off-model, 720p, and would need its legs fixing like the kid's did."""
    GEEK_FRAMES.mkdir(parents=True, exist_ok=True)
    if list(GEEK_FRAMES.glob("*.png")):
        return
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    QGuiApplication.instance() or QGuiApplication([])
    n, size = 30, 900
    for i in range(n):
        t = 4.2 * i / n                       # one pass of his breathing and his trailing arms
        js = ("require(process.env.GEEKOC); const G = globalThis.GeekOc;"
              "process.stdout.write(G.svg({pose:'swim', face:'excited', t:Number(process.env.T),"
              " size:Number(process.env.SIZE), id:'g'+process.env.I}));")
        env = {**os.environ, "GEEKOC": str(ENGINE), "T": f"{t:.3f}", "SIZE": str(size), "I": str(i)}
        out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=120, env=env)
        if out.returncode != 0:
            raise SystemExit("node could not draw GeekOc:\n" + (out.stderr or "")[-400:])
        r = QSvgRenderer(QByteArray(out.stdout.encode("utf-8")))
        img = QImage(size, size, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing, True)
        r.render(painter)
        painter.end()
        img.save(str(GEEK_FRAMES / f"{i:03d}.png"))


_walk_cache: dict[int, Image.Image] = {}
_geek_cache: dict[int, Image.Image] = {}


def walk_frame(t: float) -> Image.Image:
    files = sorted(WALK_FRAMES.glob("*.jpg"))
    i = min(int(t * FPS), len(files) - 1)
    if i not in _walk_cache:
        _walk_cache.clear()
        _walk_cache[i] = Image.open(files[i]).convert("RGB")
    return _walk_cache[i].copy().convert("RGBA")


def geek_frame(i: int) -> Image.Image:
    files = sorted(GEEK_FRAMES.glob("*.png"))
    i %= len(files)
    if i not in _geek_cache:
        _geek_cache[i] = Image.open(files[i]).convert("RGBA")
    return _geek_cache[i]


# --------------------------------------------------------------------------- what falls out of the sky
#
# INVENTED, every one of them. The point of this hill is "all the places that are not here", and real
# marks would both imply a relationship myGeeKy does not have and put other people's branding in an advert
# for it. A card with an avatar and two grey bars reads as "a profile" without being anybody's.
CARD_COLOURS = [(92, 96, 128), (120, 100, 150), (88, 112, 140), (140, 104, 112), (104, 120, 108),
                (132, 120, 96), (100, 100, 100), (118, 92, 132)]


def _card(kind: int, w: int, col) -> Image.Image:
    """One piece of the noise: a profile card, a post, a crest, a bell, a chat bubble, a play button."""
    h = int(w * (0.68 if kind in (0, 1) else 1.0))
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pale = tuple(min(255, c + 70) for c in col)
    if kind == 0:                                     # a profile card
        d.rounded_rectangle((0, 0, w - 1, h - 1), w // 9, fill=col + (255,))
        d.ellipse((w * 0.08, h * 0.16, w * 0.38, h * 0.76), fill=pale + (255,))
        d.rounded_rectangle((w * 0.46, h * 0.26, w * 0.9, h * 0.38), 4, fill=pale + (255,))
        d.rounded_rectangle((w * 0.46, h * 0.46, w * 0.78, h * 0.56), 4, fill=pale + (190,))
    elif kind == 1:                                   # a post
        d.rounded_rectangle((0, 0, w - 1, h - 1), w // 9, fill=col + (255,))
        for k, frac in enumerate((0.9, 0.78, 0.55)):
            y = h * (0.26 + k * 0.22)
            d.rounded_rectangle((w * 0.1, y, w * frac, y + h * 0.1), 4, fill=pale + (210,))
    elif kind == 2:                                   # a crest
        d.polygon([(w / 2, 0), (w - 1, h * 0.22), (w - 1, h * 0.62), (w / 2, h - 1), (0, h * 0.62), (0, h * 0.22)],
                  fill=col + (255,))
        d.ellipse((w * 0.3, h * 0.26, w * 0.7, h * 0.66), fill=pale + (255,))
    elif kind == 3:                                   # a bell
        d.pieslice((w * 0.12, h * 0.1, w * 0.88, h * 0.86), 180, 360, fill=col + (255,))
        d.rectangle((w * 0.12, h * 0.48, w * 0.88, h * 0.7), fill=col + (255,))
        d.rounded_rectangle((w * 0.06, h * 0.68, w * 0.94, h * 0.78), 5, fill=pale + (255,))
        d.ellipse((w * 0.4, h * 0.78, w * 0.6, h * 0.96), fill=pale + (255,))
    elif kind == 4:                                   # a chat bubble
        d.rounded_rectangle((0, 0, w - 1, h * 0.76), w // 7, fill=col + (255,))
        d.polygon([(w * 0.26, h * 0.7), (w * 0.46, h * 0.7), (w * 0.3, h - 1)], fill=col + (255,))
        for k in range(3):
            d.ellipse((w * (0.24 + k * 0.2), h * 0.3, w * (0.34 + k * 0.2), h * 0.44), fill=pale + (255,))
    else:                                             # a play button
        d.ellipse((0, 0, w - 1, h - 1), fill=col + (255,))
        d.polygon([(w * 0.4, h * 0.3), (w * 0.72, h * 0.5), (w * 0.4, h * 0.7)], fill=pale + (255,))
    return im


def _pile() -> list[dict]:
    """Where every piece falls, and when.

    They land along a mound: thickest in the middle-left where the words are not, thinning towards the
    kid so he is buried last and least -- a hill, not a wall."""
    rnd = random.Random(11)
    out = []
    for i in range(ICONS):
        u = rnd.random() ** 0.8                         # more of them on the left
        x = 70 + u * (W - 260)
        peak = math.exp(-(((x - W * 0.42) / (W * 0.33)) ** 2))
        depth = rnd.random()
        y = H - 20 - depth * (90 + 300 * peak)
        w = int(74 + 54 * rnd.random() * (0.6 + 0.6 * depth))
        out.append({"x": x, "y": y, "w": w, "kind": rnd.randrange(6),
                    "col": CARD_COLOURS[rnd.randrange(len(CARD_COLOURS))],
                    "spin": rnd.uniform(-26, 26), "at": FALL_FROM + (FALL_TO - FALL_FROM) * (i / ICONS) ** 0.78,
                    "fall": rnd.uniform(0.75, 1.25)})
    return sorted(out, key=lambda p: p["y"])            # the back of the hill drawn first


PILE = _pile()
_piece_cache: dict[tuple, Image.Image] = {}


def _piece(p: dict) -> Image.Image:
    key = (p["kind"], p["w"], p["col"], round(p["spin"]))
    if key not in _piece_cache:
        _piece_cache[key] = _card(p["kind"], p["w"], p["col"]).rotate(p["spin"], Image.BICUBIC, expand=True)
    return _piece_cache[key]


def rain(im: Image.Image, t: float, clear: float = 0.0) -> None:
    """Everything that has fallen by now, and everything still falling.

    `clear` washes the hill away from the left as GeekOc passes through it."""
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    for p in PILE:
        k = (t - p["at"]) / p["fall"]
        if k <= 0:
            continue
        if clear > 0 and p["x"] < clear * (W + 400) - 200:
            continue
        pic = _piece(p)
        if k < 1:                                        # still in the air: falling and turning
            y = -pic.height + (p["y"] - (-pic.height)) * (k * k)
            a = min(1.0, k * 3)
        else:
            y, a = p["y"], 1.0
            if clear > 0:                                # the edge of the wash: fading as it goes
                edge = (p["x"] - (clear * (W + 400) - 200)) / 260
                a = min(1.0, max(0.0, edge))
        if a <= 0:
            continue
        piece = pic
        if a < 1:
            piece = pic.copy()
            piece.putalpha(pic.getchannel("A").point(lambda v: int(v * a)))
        layer.alpha_composite(piece, (int(p["x"] - piece.width / 2), int(y - piece.height / 2)))
    im.alpha_composite(layer)


# The words live in the empty left, NOT in the middle of the frame. The clip was framed to leave 87% of
# it clear for exactly this, and centring on the whole frame put the longest line straight through the
# kid's head.
SAYS_AT = int(W * 0.42)
INK = (40, 36, 60)            # dark enough on the pale wall; the turn is said in the brand pink


def says(im: Image.Image, txt: str, y: int, fnt, color, alpha: float = 1.0) -> None:
    if alpha <= 0:
        return
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text((SAYS_AT - d.textlength(txt, font=fnt) / 2, y), txt, font=fnt, fill=color + (int(255 * alpha),))
    im.alpha_composite(layer)


def s_walk(t: float) -> Image.Image:
    """The kid, the three promises, and the sky filling up."""
    im = walk_frame(t)
    rain(im, t)
    for start, end, line in LINES:
        says(im, line, 150, font(68, bold=True), INK, fade(t, start, end, 0.45))
    says(im, TURN[2], 150, font(68, bold=True), (190, 40, 110), fade(t, TURN[0], TURN[1], 0.45))
    says(im, ASKS[0][2], 258, font(60, bold=True), INK, fade(t, *ASKS[0][:2], 0.4))
    says(im, ASKS[1][2], 346, font(60, bold=True), INK, fade(t, *ASKS[1][:2], 0.4))
    return im


def s_swim(t: float) -> Image.Image:
    """GeekOc crosses, and takes the noise with him.

    He swims in from the left at the height of the hill, and everything he passes is simply gone. The kid
    goes with the last of it: the picture ends empty, which is the only way the quiet reads as an answer
    rather than as nothing happening."""
    im = walk_frame(WALK_DUR)                                  # the clip holds on its last frame
    go = ease(t / (SWIM_DUR * 0.72))
    rain(im, WALK_DUR, clear=go)
    kid = 1 - ease((t - SWIM_DUR * 0.45) / (SWIM_DUR * 0.4))   # the kid fades out with the hill
    if kid < 1:
        white = Image.new("RGBA", im.size, (246, 246, 246, int(255 * (1 - kid))))
        im.alpha_composite(white)
    him = geek_frame(int(t * FPS))
    size = 620
    k = size / him.height
    him = him.resize((int(him.width * k), size), Image.LANCZOS)
    x = -him.width + (W + him.width * 2) * ease(t / (SWIM_DUR * 0.8))
    y = H * 0.52 + math.sin(t * 2.2) * 40 - him.height / 2
    im.alpha_composite(him, (int(x - him.width / 2), int(y)))
    return im


def after_flash(im: Image.Image, t: float) -> Image.Image:
    """The white flash from the intro fades out over the first moment of the next scene."""
    k = 1 - ease(t / 0.45)
    if k > 0:
        im.alpha_composite(Image.new("RGBA", im.size, (255, 255, 255, int(235 * k))))
    return im



SCENES = [(s_walk, WALK_DUR), (s_swim, SWIM_DUR), (s_reveal, 6.0), (s_pillars, PILLARS_SECS), (s_install, 23.6),
          (s_configure, 21.0), (s_signals, 16.2), (s_tour, 3.6 + len(TOUR) * 5.0 + 0.4), (s_phone, 11.0),
          (s_close, 8.0)]


def frame_at(t: float) -> Image.Image:
    start = 0.0
    for scene, dur in SCENES:
        if t < start + dur:
            im = scene(t - start)
            break
        start += dur
    else:
        im = s_close(SCENES[-1][1])
    total = sum(d for _, d in SCENES)
    if t > total - 1.2:   # fade to black at the very end
        im.alpha_composite(Image.new("RGBA", im.size, (0, 0, 0, int(255 * ease((t - total + 1.2) / 1.2)))))
    return im.convert("RGB")


# --------------------------------------------------------------------------- soundtrack
def soundtrack(path: Path, seconds: float, sr: int = 44100) -> None:
    """An original, dramatic synthwave/chiptune score (120 bpm, A minor: Am F C G), written here, so it's free to
    use anywhere. It follows the story:
      intro    a heartbeat, a low pad and a rising sweep under the clip; an impact on the cut;
      hook     a muted bass pulse and ticking hats; the tension builds, a snare roll and a riser...
      reveal   ...the drop: four-on-the-floor drums, a pulsing bass, a chiptune arpeggio and a lead melody;
      steps    the groove carries on, lighter while things are explained;
      signals  a breakdown (pad and arpeggio only), then a riser back in;
      tour     everything again; close: a last big chord that rings out."""
    from scipy.signal import butter, lfilter
    n = int(seconds * sr)
    t = np.arange(n) / sr
    L = np.zeros(n)
    R = np.zeros(n)
    bpm = 120
    beat = 60 / bpm
    bar = 4 * beat
    starts, s = [], 0.0
    for scene, dur in SCENES:
        starts.append((scene.__name__, s))
        s += dur
    at = dict(starts)
    # The music holds back while the kid is walking and the sky fills, then everything stops dead the
    # moment GeekOc arrives, and the drop lands on the logo. The silence is the point of the whole
    # opening: the viewer should feel the noise go away before reading a word about it.
    t_cut, t_drop = at["s_swim"], at["s_reveal"]
    t_break, t_back, t_close = at["s_signals"], at["s_tour"], at["s_close"]

    def note(m):
        return 440.0 * 2 ** ((m - 69) / 12)

    def add(start, sig, gain=1.0, pan=0.0):
        i0 = int(start * sr)
        if i0 >= n or i0 + len(sig) <= 0:
            return
        sig = sig[: n - i0]
        L[i0:i0 + len(sig)] += sig * gain * (1 - max(pan, 0))
        R[i0:i0 + len(sig)] += sig * gain * (1 + min(pan, 0))

    def square(f, dur, duty=0.5):
        tt = np.arange(int(dur * sr)) / sr
        return np.where((tt * f) % 1 < duty, 1.0, -1.0), tt

    def lp(sig, cut):
        b, a = butter(2, min(cut / (sr / 2), 0.99))
        return lfilter(b, a, sig)

    def hp(sig, cut):
        b, a = butter(2, min(cut / (sr / 2), 0.99), btype="high")
        return lfilter(b, a, sig)

    rng = np.random.default_rng(3)

    def kick(gain=1.0):
        tt = np.arange(int(0.35 * sr)) / sr
        f = 45 + 110 * np.exp(-tt * 28)
        return gain * np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-tt * 9)

    def snare():
        tt = np.arange(int(0.22 * sr)) / sr
        return (hp(rng.standard_normal(len(tt)), 1200) * 0.7 + np.sin(2 * np.pi * 185 * tt) * 0.5) * np.exp(-tt * 18)

    def hat(open_=False):
        tt = np.arange(int((0.18 if open_ else 0.05) * sr)) / sr
        return hp(rng.standard_normal(len(tt)), 7000) * np.exp(-tt * (14 if open_ else 70))

    def riser(start, dur, gain=0.35):
        tt = np.arange(int(dur * sr)) / sr
        x = tt / dur
        noise = hp(rng.standard_normal(len(tt)), 600) * x ** 2
        sweep = np.sin(2 * np.pi * np.cumsum(220 + 1400 * x ** 2) / sr) * x ** 3 * 0.4
        add(start, (noise * 0.6 + sweep) * gain)

    def impact(start, gain=1.0):
        tt = np.arange(int(3.0 * sr)) / sr
        boom = np.sin(2 * np.pi * np.cumsum(38 + 60 * np.exp(-tt * 6)) / sr) * np.exp(-tt * 1.6)
        crash = hp(rng.standard_normal(len(tt)), 3000) * np.exp(-tt * 2.2) * 0.35
        add(start, (boom + crash) * gain)

    chords = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62)]          # Am F C G
    roots = [45, 41, 36, 43]

    def chord_at(x):
        return int(x / bar) % 4

    # ---- the pad: detuned saws, low-passed, everywhere (darker in the intro)
    pad = np.zeros(n)
    for k in range(int(seconds / bar) + 1):
        st0 = k * bar
        seg = np.arange(int((bar + 0.6) * sr)) / sr
        e = np.clip(seg / 0.4, 0, 1) * np.clip((bar + 0.6 - seg) / 0.6, 0, 1)
        sig = np.zeros(len(seg))
        for m in chords[k % 4]:
            for det in (0.997, 1.0, 1.004):
                f = note(m) * det
                sig += 2 * ((seg * f) % 1) - 1
        i0 = int(st0 * sr)
        sig = sig[: max(0, n - i0)]
        pad[i0:i0 + len(sig)] += sig * e[: len(sig)] / 9
    cut = np.where(t < t_cut, 500, np.where((t > t_break) & (t < t_back), 1400, 2600))
    pad = lp(pad, 1800) * 0.16 * np.where(t < t_cut, 0.8, 1.0) * (0.6 + 0.4 * (cut / 2600))
    L += pad
    R += np.roll(pad, int(0.009 * sr))

    # ---- intro: a heartbeat under the clip, a riser, an impact on the cut
    k = 0.6
    while k < t_cut - 0.4:
        add(k, kick(0.55))
        add(k + 0.28, kick(0.35))
        k += 1.0
    riser(t_cut - 3.2, 3.2, 0.45)
    impact(t_cut, 1.1)

    # ---- the hook: a muted bass pulse, hats, then the build to the drop
    for i in range(int((t_drop - t_cut) / (beat / 2))):
        st0 = t_cut + i * beat / 2
        sq, tt = square(note(roots[chord_at(st0)] - 12) * 2, beat / 2 * 0.9, 0.5)
        add(st0, lp(sq, 380) * np.exp(-tt * 6) * 0.22)
        if st0 > t_cut + 4:
            add(st0, hat(), 0.10, pan=0.3)
    roll_from = t_drop - 2.0
    for i in range(16):
        add(roll_from + i * 0.125, snare(), 0.12 + 0.03 * i)
    riser(t_drop - 4.0, 4.0, 0.5)
    impact(t_drop, 1.0)

    # ---- from the drop on: drums, bass, arpeggio, lead (lighter in the middle, a breakdown at signals)
    def level(x):
        if x < t_drop or x >= t_close:
            return 0.0
        if t_break <= x < t_back:
            return 0.0
        return 1.0

    lead_on = lambda x: (t_drop + 2 * bar <= x < at["s_install"] + 4 * bar) or (t_back + 2 * bar <= x < t_close)  # noqa: E731
    melody = [76, 74, 72, 74, 76, 79, 76, 74, 72, 71, 72, 74, 72, 69, 67, 69]          # a simple hook, two bars
    x = t_drop
    i16 = 0
    while x < t_close:
        lv = level(x)
        c = chord_at(x)
        pos = i16 % 16
        if lv:
            if pos % 4 == 0:
                add(x, kick(0.9))
            if pos in (4, 12):
                add(x, snare(), 0.45)
            add(x, hat(open_=pos % 4 == 2), 0.16 if pos % 2 == 0 else 0.09, pan=0.25)
            if pos % 2 == 0:                                       # the bass: 8th notes, octave jumps
                sq, tt = square(note(roots[c] - 12 + (12 if pos % 4 == 2 else 0)), beat / 2 * 0.85, 0.5)
                add(x, lp(sq, 900) * np.exp(-tt * 5) * 0.20)
        if lv or (t_break <= x < t_back):                          # the chiptune arpeggio (also in the breakdown)
            m = chords[c][pos % 3] + 12 + (12 if pos % 8 >= 6 else 0)
            sq, tt = square(note(m), beat / 4 * 0.9, 0.25)
            add(x, sq * np.exp(-tt * 14) * (0.055 if lv else 0.045), pan=-0.35 if pos % 2 else 0.35)
        if lv and lead_on(x) and pos % 2 == 0:                    # the lead melody, 8th notes
            m = melody[(i16 // 2) % len(melody)]
            tt = np.arange(int(beat / 2 * 0.95 * sr)) / sr
            phase = np.cumsum(note(m) * (1 + 0.006 * np.sin(2 * np.pi * 5.5 * tt))) / sr       # a little vibrato
            tone = np.where(phase % 1 < 0.5, 1.0, -1.0)
            add(x, lp(tone, 3500) * np.clip(tt / 0.01, 0, 1) * np.exp(-tt * 2.5) * 0.07)
        x += beat / 4
        i16 += 1
    riser(t_back - 4.0, 4.0, 0.45)
    impact(t_back, 0.8)

    # ---- the close: one big chord that rings out
    tt = np.arange(int((seconds - t_close) * sr)) / sr
    big = np.zeros(len(tt))
    for m in (45, 57, 60, 64, 69, 72):
        big += np.sin(2 * np.pi * note(m) * tt) + 0.3 * np.sin(2 * np.pi * note(m) * 2.003 * tt)
    add(t_close, big * np.exp(-tt * 0.45) * 0.07)
    impact(t_close, 0.7)

    # The opening used to borrow the generated clip's own sound. It does not any more: the walk is silent
    # wall and falling paper, and what that beat needs is the film's own noise building and then being cut
    # off dead when GeekOc arrives. The riser and the impact above do that.

    # ---- a room, a gentle squash, and out
    for buf in (L, R):
        wet = np.zeros(n)
        for delay, g in ((0.083, 0.22), (0.161, 0.15), (0.297, 0.09)):
            d = int(delay * sr)
            wet[d:] += g * buf[:-d]
        buf += wet
    stereo = np.stack([L, R], axis=1)
    stereo *= np.clip((seconds - t) / 2.5, 0, 1)[:, None]
    stereo /= max(1e-9, np.abs(stereo).max()) / 1.6
    stereo = np.tanh(stereo) * 0.92                                   # soft limiting: louder without clipping
    data = (stereo * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data.tobytes())


# --------------------------------------------------------------------------- render
def main() -> None:
    import imageio_ffmpeg
    total = sum(d for _, d in SCENES)
    extract_walk()
    render_geekoc()
    if "--preview" in sys.argv:
        for sec in (2, 6, 11, 16, 20, 23.5, 25, 26.5, 28.5, 31, 40, 90):
            frame_at(sec).save(OUT / f"preview_{sec:05.1f}.png")
        print("preview frames written")
        return
    audio = OUT / "soundtrack.wav"
    soundtrack(audio, total)
    video = OUT / "mygeeky-intro.mp4"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.Popen([
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(audio),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(video)],
        stdin=subprocess.PIPE)
    frames = int(total * FPS)
    for i in range(frames):
        proc.stdin.write(frame_at(i / FPS).tobytes())
        if i % (FPS * 10) == 0:
            print(f"  {i / FPS:5.0f}s / {total:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    frame_at(total * 0.18).save(OUT / "thumbnail.png")
    print(f"Wrote {video} ({video.stat().st_size / 1e6:.1f} MB, {total:.0f} s)")


if __name__ == "__main__":
    main()
