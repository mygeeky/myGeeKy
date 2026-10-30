"""The opening, on its own. The kid walks in and stops at the right. GeekOc swims in from the left and
floats there while icons rain into the middle and stack up like bricks into a mountain, bouncing as they
land, and the lines are said one by one; he wonders at it, then turns sad. Then the kid and the mountain
fade, GeekOc swims across to the right, cheering up, the myGeeKy icon drops out of the sky on the left,
and the phone app's screens follow one at a time in the middle, each under its name (in dark gold) and
what it offers. Each screen then shrinks aside while one to three of its details come one after another
beside it, big and captioned, and grows back before the next. Then "On your desktop" and the desktop's main
screens, the same way; then how to install it there (the installer's pages, then one pip command in a
terminal), GeekOc swims away, the five promises one at a time, each with its icon, and last the myGeeKy icon
over "Your geeky friend who helps you grow, quietly." and the three places it runs: Google Play, Windows,
macOS. About three minutes in all.

The phone screens are taken for this video on the emulator with the app's dock folded, into
launch/video/intro/phone/ (git-ignored; how, in the comment above TOUR). The desktop screens are retaken
taller than docs/screenshots (`python docs/make_screenshots.py --tall`, into launch/video/intro/shots/, also
git-ignored) so each one shows its content, not just the panel's header.

    python launch/video/make_falling.py            ->  launch/video/falling.mp4
    python launch/video/make_falling.py --preview  ->  a few still frames only (fast)

The icons come from a folder of raw downloads (default ~/Desktop/assets, or pass --assets DIR). Each one
is cleaned up first -- white backgrounds cut away, cropped to what is drawn, scaled to one size and given
a white sticker edge and a soft shadow -- so pieces from different sources read as one set. The cleaned
icons are written to launch/video/intro/icons/ (git-ignored) and reused on the next run.
"""

from __future__ import annotations

import math
import os
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
ICON_DIR = OUT / "intro" / "icons"
GEEK_DIR = OUT / "intro" / "geekoc-sad"
ENGINE = ROOT / "website" / "geekoc" / "geekoc.js"
W, H, FPS = 1920, 1080, 30

KID_LEAD = 4.0                 # the kid walks in first; everything below starts this much later
SWIM_IN = 5.0                  # GeekOc swims in from the left; nothing falls until he is in place
OUTRO = SWIM_IN + 22.5         # the kid, the mountain and the last line fade...
CLEAR = 1.2                    # ...over this long
SWIM_OUT_AT, SWIM_OUT = OUTRO + 0.6, 4.5   # GeekOc swims across to the right
HAPPY_FROM = OUTRO + 0.3       # ...cheering up as he goes
LOGO_AT, LOGO_FALL = OUTRO + 2.0, 1.1      # the myGeeKy icon drops out of the sky on the left
TOUR_AT = OUTRO + 5.0         # then the screens, one at a time
# (TOUR_END and everything after it is worked out from the TOUR and DESK lists, further down)
FALL_FROM, FALL_TO = SWIM_IN + 0.8, SWIM_IN + 15.0  # when pieces start and stop leaving the sky
ICON_PX = 220                  # the cleaned icon's canvas, before it is scaled per piece


# Where GeekOc floats, and how big he is.
GEEK_SIZE = 640                # his box, with its margin
GEEK_X, GEEK_Y = 300, 580      # centre of his frame, once he has arrived
GEEK_FROM_X = -420             # ...and where he starts, off the left edge
GEEK_END_X = 1580              # ...and where he swims to for the end
GEEK_GONE_X = 2400             # ...and off the right edge, before the promises


# --------------------------------------------------------------------------- the icons
def _arg(name: str, default: str) -> str:
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def _render_svg(path: Path, size: int) -> Image.Image | None:
    """An SVG drawn with Qt (already a dependency of the app). None if it is not really an SVG."""
    text = path.read_text("utf-8", errors="ignore")
    if "<svg" not in text[:2000] or "<html" in text[:2000].lower():
        return None
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    QGuiApplication.instance() or QGuiApplication([])
    r = QSvgRenderer(QByteArray(text.encode("utf-8")))
    if not r.isValid():
        return None
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    r.render(p)
    p.end()
    tmp = ICON_DIR / "_svg.png"
    img.save(str(tmp))
    out = Image.open(tmp).convert("RGBA")
    tmp.unlink()
    return out


def _cut_white(im: Image.Image) -> Image.Image:
    """Make a flat white (or near-white) background transparent -- only where it touches the edge, so
    white INSIDE the drawing (a page, a face, a speech bubble) is kept."""
    a = np.array(im.convert("RGBA"))
    if (a[..., 3] < 250).mean() > 0.05:         # it already has transparency: leave it alone
        return im.convert("RGBA")
    rgb = a[..., :3].astype(int)
    near_white = (rgb.min(axis=2) > 232) & (rgb.max(axis=2) - rgb.min(axis=2) < 18)
    # flood the near-white region from every border pixel
    h, w = near_white.shape
    seen = np.zeros_like(near_white)
    stack = [(y, x) for x in range(w) for y in (0, h - 1) if near_white[y, x]]
    stack += [(y, x) for y in range(h) for x in (0, w - 1) if near_white[y, x]]
    while stack:
        y, x = stack.pop()
        if seen[y, x]:
            continue
        seen[y, x] = True
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and near_white[ny, nx] and not seen[ny, nx]:
                stack.append((ny, nx))
    alpha = np.where(seen, 0, 255).astype(np.uint8)
    out = Image.fromarray(np.dstack([a[..., :3], alpha]), "RGBA")
    # soften the cut edge a touch so it is not jagged
    out.putalpha(out.getchannel("A").filter(ImageFilter.GaussianBlur(0.8)))
    return out


def _stickerise(im: Image.Image) -> Image.Image:
    """Crop to the drawing, fit it to one size, and give it a white edge and a soft shadow."""
    bbox = im.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
    if bbox:
        im = im.crop(bbox)
    inner = ICON_PX - 44
    im.thumbnail((inner, inner), Image.LANCZOS)
    canvas = Image.new("RGBA", (ICON_PX, ICON_PX), (0, 0, 0, 0))
    ox, oy = (ICON_PX - im.width) // 2, (ICON_PX - im.height) // 2
    shape = Image.new("L", canvas.size, 0)
    shape.paste(im.getchannel("A"), (ox, oy))
    edge = shape.filter(ImageFilter.MaxFilter(13)).filter(ImageFilter.GaussianBlur(1.2))
    shadow = edge.filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * 0.35))
    sh = Image.new("RGBA", canvas.size, (40, 30, 70, 0))
    sh.putalpha(shadow)
    canvas.alpha_composite(sh, (4, 7))
    white = Image.new("RGBA", canvas.size, (255, 255, 255, 0))
    white.putalpha(edge)
    canvas.alpha_composite(white)
    canvas.alpha_composite(im, (ox, oy))
    return canvas


def prepare_icons() -> list[Image.Image]:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    done = sorted(ICON_DIR.glob("*.png"))
    if done and "--fresh" not in sys.argv:
        return [Image.open(p).convert("RGBA") for p in done]
    for p in done:
        p.unlink()
    src = Path(os.path.expanduser(_arg("--assets", "~/Desktop/assets")))
    files = sorted(f for f in src.rglob("*") if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".svg"))
    icons = []
    for i, f in enumerate(files):
        if f.suffix.lower() == ".svg":
            raw = _render_svg(f, 600)
            if raw is None:
                print(f"  skipped {f.relative_to(src)} (not a real SVG)")
                continue
        else:
            raw = Image.open(f)
        icon = _stickerise(_cut_white(raw))
        icon.save(ICON_DIR / f"{i:02d}-{f.stem[:24].replace(' ', '_')}.png")
        icons.append(icon)
    print(f"  {len(icons)} icons cleaned into {ICON_DIR}")
    return icons


# --------------------------------------------------------------------------- GeekOc
# He is not a loop of stills. The rig's own arm physics (`Life`, the same simulation the website runs) is
# stepped through the whole scene once: his body bobs, drifts and slowly sinks, each arm carries a slow
# wave travelling from root to tip, out of step with its neighbours, and the arms -- weighted chains --
# trail, overshoot and settle on their own, the way they move in water. No gesture, no pointing: all eight
# hang loose. The mood is in the face: he WONDERS at the sky first (eyes up, the "hmm" mouth), then SAD as the mountain grows (eyes down on it, the worried mouth, heavy lids).
WONDER = {"mouth": "hmm", "brow": 0.7, "lids": 0.05, "look": [0.55, -0.6]}
SAD = {"mouth": "worried", "brow": 0.85, "lids": 0.45, "look": [0.45, 0.45]}
SAD_FROM, SAD_OVER = SWIM_IN + 9.0, 2.5   # as the turn is said
HAPPY = {"mouth": "smile", "brow": 0.35, "lids": 0.0, "look": [-0.45, -0.1]}

SIM_JS = r"""
require(process.env.GEEKOC);
const G = globalThis.GeekOc;
const cfg = JSON.parse(process.env.CFG);
const ease = x => { x = Math.min(Math.max(x, 0), 1); return x * x * (3 - 2 * x); };
const lerp = (a, b, k) => a + (b - a) * k;
const rad = d => d * Math.PI / 180;

// No gesture: every arm hangs loose from the skirt, curled less than standing so they have room to move.
const idle = G.POSES.idle;
const pose = Object.assign({}, idle, { curl: idle.curl.map(c => c * 0.6), len: 1.05 });

/* The arms in water. The rig's own sway is a few degrees, built for a landing page; in water a tentacle
 * is a wave travelling from root to tip. So each arm's resting shape is drawn here: its heading turns
 * gradually along its length (the pose's curl), and on top of that a wave runs outwards, growing towards
 * the tip, each arm on its own beat. A slower second wave keeps any two moments from repeating. */
function target(root, heading, len, curl, i, t, calm) {
  const N = 24, step = len / N, out = [[root[0], root[1]]];
  let a = rad(heading), x = root[0], y = root[1];
  const amp = (1 - 0.45 * calm), beat = 1.5 + 0.17 * i, ph = i * 2.1;
  for (let s = 1; s <= N; s++) {
    const k = s / N;
    a += rad(curl) * (0.25 + 2.2 * k * k) / 17.0
       + amp * (0.075 * k * Math.sin(beat * t - 5.2 * k + ph)
                + 0.04 * k * Math.sin(0.63 * beat * t - 3.1 * k + ph * 1.7));
    x += step * Math.cos(a);
    y += step * Math.sin(a);
    out.push([x, y]);
  }
  return out;
}

// Weighted chains chasing those shapes: the same Verlet scheme as the rig's `Life`, looser.
const STIFF = 0.09, DAMP = 0.9, BEND = 0.5, DROOP = 0.06;
let chains = null;

/* The swim in: a slow, even glide from off the left edge to his place, easing in and out, carried by
 * WING BEATS -- all eight arms open wide together, then sweep in and down together, like a bird's wings,
 * and he lifts a little on every down-stroke. The beats fade out as he arrives, and the arms settle into
 * floating. */
const OPEN = { swing: [62, 40, 20, 6, -6, -20, -40, -62], curl: [34, 44, 44, 34, -34, -44, -44, -34], len: 1.08 };
const SHUT = G.POSES.jet;
const BEAT = 0.85;                                     // strokes a second: slow and deliberate
const stroke = t => 0.5 - 0.5 * Math.cos(2 * Math.PI * BEAT * t);   // 0 shut .. 1 open
// How much he is swimming at t: the swim in starts at full stroke; any later swim eases into it. Each
// one's beats fade out over its last stretch.
const swimK = t => Math.max(...cfg.swims.map(([a, d, first]) =>
  (first ? 1 : ease((t - a) / 0.6)) * (1 - ease((t - (a + 0.75 * d)) / (0.4 * d)))));
const sub = 2, dt = 1 / (cfg.fps * sub), k60 = dt * 60;
let t = 0;
for (let n = 0; n < cfg.frames; n++) {
  for (let s = 0; s < sub; s++) {
    t += dt;
    const happy = ease((t - cfg.happyFrom) / 1.5);     // the sadness lifts for the end
    const sad = ease((t - cfg.sadFrom) / cfg.sadOver) * (1 - happy);
    const arrive = 1 - swimK(t);                        // 0 swimming .. 1 floating in place
    const wing = stroke(t);
    const now = G.mix(G.mix(SHUT, OPEN, wing), pose, arrive);
    // a lift on each down-stroke (as the arms close), riding over the usual slow bob once he is there
    const lift = (1 - arrive) * 18 * Math.sin(2 * Math.PI * BEAT * t);
    const at = [arrive * 10 * Math.sin(t * 0.45), arrive * 14 * Math.sin(t * 1.1) + lift + sad * 26];
    const built = G.build({ pose: now, t, at });
    const targets = built.arms.map((arm, i) => {
      const sp = arm.spine, r = sp[0], nx = sp[1];
      const heading = Math.atan2(nx[1] - r[1], nx[0] - r[0]) * 180 / Math.PI;
      let len = 0;
      for (let j = 1; j < sp.length; j++) len += Math.hypot(sp[j][0] - sp[j - 1][0], sp[j][1] - sp[j - 1][1]);
      // as he gives up the arms fall a little further towards straight down
      const curl = now.curl[i] * (1 - 0.35 * sad);
      // while he swims, the arms hold the wing shape: almost none of the floating ripple
      return target(r, heading, len, curl, i, t, Math.max(sad, 0.85 * (1 - arrive)));
    });
    if (!chains) chains = targets.map(tg => tg.map(p => ({ x: p[0], y: p[1], px: p[0], py: p[1] })));
    chains.forEach((ch, ai) => {
      const tg = targets[ai], m = ch.length;
      for (let i = 1; i < m; i++) {
        const b = ch[i];
        const vx = (b.x - b.px) * DAMP, vy = (b.y - b.py) * DAMP;
        b.px = b.x; b.py = b.y;
        const hold = STIFF * (1 - 0.6 * (i / m)) * k60;
        b.x += vx + (tg[i][0] - b.x) * hold;
        b.y += vy + (tg[i][1] - b.y) * hold + DROOP * (i / m) * k60;
      }
      for (let i = 1; i < m - 1; i++) {
        ch[i].x += ((ch[i - 1].x + ch[i + 1].x) / 2 - ch[i].x) * BEND;
        ch[i].y += ((ch[i - 1].y + ch[i + 1].y) / 2 - ch[i].y) * BEND;
      }
      for (let pass = 0; pass < 2; pass++) {
        ch[0].x = tg[0][0]; ch[0].y = tg[0][1];
        for (let i = 1; i < m; i++) {
          const a0 = ch[i - 1], b0 = ch[i];
          const want = Math.hypot(tg[i][0] - tg[i - 1][0], tg[i][1] - tg[i - 1][1]);
          const dx = b0.x - a0.x, dy = b0.y - a0.y, d = Math.hypot(dx, dy) || 1, f = (d - want) / d;
          b0.x -= dx * f; b0.y -= dy * f;
        }
      }
    });
    if (s === sub - 1) {
      // curious while he swims in, wondering once he is there, sad as the mountain grows
      const c = G.FACES.curious, w0 = cfg.wonder, d = cfg.sad;
      const w = { mouth: arrive < 0.5 ? c.mouth : w0.mouth, brow: lerp(c.brow, w0.brow, arrive),
                  lids: lerp(c.lids, w0.lids, arrive),
                  look: [lerp(c.look[0], w0.look[0], arrive), lerp(c.look[1], w0.look[1], arrive)] };
      const f0 = { mouth: sad < 0.5 ? w.mouth : d.mouth, brow: lerp(w.brow, d.brow, sad),
                   lids: lerp(w.lids, d.lids, sad),
                   look: [lerp(w.look[0], d.look[0], sad), lerp(w.look[1], d.look[1], sad)] };
      // ...and happy at the end, glancing back towards the screens beside him
      const h = cfg.happy;
      const face = { mouth: happy < 0.5 ? f0.mouth : h.mouth, brow: lerp(f0.brow, h.brow, happy),
                     lids: lerp(f0.lids, h.lids, happy),
                     look: [lerp(f0.look[0], h.look[0], happy), lerp(f0.look[1], h.look[1], happy)] };
      const spines = chains.map(c => c.map(b => [b.x, b.y]));
      // a margin round his box, so a tip swinging wide is never cut off at its edge
      const pad = cfg.pad, box = G.BOX;
      const svg = G.svg({ pose: now, face, t, at, spines, size: cfg.size, id: 'g' + n })
        .replace('viewBox="0 0 ' + box + ' ' + box + '"',
                 'viewBox="' + (-pad) + ' ' + (-pad) + ' ' + (box + 2 * pad) + ' ' + (box + 2 * pad) + '"');
      process.stdout.write(JSON.stringify(svg) + "\n");
    }
  }
}
"""


def render_geekoc() -> None:
    import json
    frames = int(DUR * FPS)
    if len(list(GEEK_DIR.glob("*.png"))) == frames and "--fresh" not in sys.argv:
        return
    GEEK_DIR.mkdir(parents=True, exist_ok=True)
    for old in GEEK_DIR.rglob("*.png"):
        old.unlink()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    QGuiApplication.instance() or QGuiApplication([])
    cfg = {"fps": FPS, "frames": frames, "size": GEEK_SIZE, "pad": 70, "sadFrom": SAD_FROM, "sadOver": SAD_OVER,
           "swims": [[0, SWIM_IN, True], [SWIM_OUT_AT, SWIM_OUT, False], [LEAVE_AT, LEAVE, False]],
           "happyFrom": HAPPY_FROM,
           "wonder": WONDER, "sad": SAD, "happy": HAPPY}
    env = {**os.environ, "GEEKOC": str(ENGINE), "CFG": json.dumps(cfg)}
    out = subprocess.run(["node", "-e", SIM_JS], capture_output=True, text=True, timeout=600, env=env)
    if out.returncode != 0:
        raise SystemExit("node could not draw GeekOc:\n" + (out.stderr or "")[-600:])
    for n, line in enumerate(out.stdout.splitlines()):
        r = QSvgRenderer(QByteArray(json.loads(line).encode("utf-8")))
        img = QImage(GEEK_SIZE, GEEK_SIZE, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)
        r.render(p)
        p.end()
        img.save(str(GEEK_DIR / f"{n:04d}.png"))


def geek_x(t: float) -> float:
    """Where his frame is across the screen: swimming in, floating, then swimming across to the right.
    Each crossing starts slowly and stops slowly."""
    if t < SWIM_OUT_AT:
        return GEEK_FROM_X + (GEEK_X - GEEK_FROM_X) * ease(t / SWIM_IN)
    if t < LEAVE_AT:
        return GEEK_X + (GEEK_END_X - GEEK_X) * ease((t - SWIM_OUT_AT) / SWIM_OUT)
    return GEEK_END_X + (GEEK_GONE_X - GEEK_END_X) * ease((t - LEAVE_AT) / LEAVE)


_geek: dict[int, Image.Image] = {}


def geek(n: int) -> Image.Image:
    files = int(DUR * FPS)
    n = min(max(n, 0), files - 1)
    if n not in _geek:
        if len(_geek) > 8:
            _geek.clear()
        _geek[n] = Image.open(GEEK_DIR / f"{n:04d}.png").convert("RGBA")
    return _geek[n]


# --------------------------------------------------------------------------- the pile
# The mountain is laid like a brick wall: every icon the same size and upright, in staggered courses
# that narrow towards the top, so it reads as built, not dumped. Bottom course first.
COURSES = [11, 10, 10, 9, 8, 7, 6, 5, 3, 2]   # bricks in each course, from the ground up
BRICK = 72                                    # an icon's size on screen (its sticker edge included)
PITCH = int(BRICK * 0.80)                     # brick to brick across: the stickers' margins just touch
RISE = int(BRICK * 0.78)                      # course to course upwards
MOUNT_X = W * 0.5
FLOOR_Y = 975                                 # where the bottom course sits: the kid's floor


def plan(n_icons: int) -> list[dict]:
    rnd = random.Random(7)
    slots, shift = [], 0.0
    for r, n in enumerate(COURSES):
        # bricks in a course straddle the joints of the one below: half a brick over, whichever way
        # keeps the course centred
        if r and (n % 2) == (COURSES[r - 1] % 2):
            shift = PITCH / 2 if shift == 0 else 0.0
        x0 = MOUNT_X - (n - 1) * PITCH / 2 + shift
        for c in range(n):
            slots.append((r, x0 + c * PITCH, FLOOR_Y - BRICK / 2 - r * RISE))
    # no brick the same as the one beside it or the ones it rests on
    icons_at: dict[tuple, int] = {}
    for r, x, y in slots:
        near = {v for (r2, x2), v in icons_at.items()
                if (r2 == r and abs(x2 - x) < PITCH * 1.1) or (r2 == r - 1 and abs(x2 - x) < PITCH)}
        choices = [i for i in range(n_icons) if i not in near] or list(range(n_icons))
        icons_at[(r, x)] = rnd.choice(choices)
    # a course is laid in a random order, and a course only starts once most of the one below is down
    order = []
    for r in range(len(COURSES)):
        row = [sl for sl in slots if sl[0] == r]
        rnd.shuffle(row)
        order += row
    out = []
    for i, (r, x, y) in enumerate(order):
        out.append({
            "x": x, "y": y, "r": r, "size": BRICK, "icon": icons_at[(r, x)],
            "spin_air": rnd.uniform(-140, 140), "drift": rnd.uniform(-30, 30),
            "at": FALL_FROM + (FALL_TO - FALL_FROM) * (i / len(order)) ** 0.9,
            "fall": rnd.uniform(1.0, 1.3), "bounce": rnd.uniform(0.85, 1.15),
        })
    return out                                    # drawn in laying order: lower courses behind


_img: dict[tuple, Image.Image] = {}


def piece_img(icons: list[Image.Image], p: dict, angle: float, sx: float = 1.0, sy: float = 1.0) -> Image.Image:
    """The icon at its size, turned and squashed -- rounded so a few hundred cached shapes cover it."""
    a = int(round(angle / 4)) * 4
    w = max(8, int(round(p["size"] * sx / 2)) * 2)
    h = max(8, int(round(p["size"] * sy / 2)) * 2)
    key = (p["icon"], w, h, a)
    if key not in _img:
        if len(_img) > 4000:
            _img.clear()
        im = icons[p["icon"]].resize((w, h), Image.LANCZOS)
        _img[key] = im.rotate(a, Image.BICUBIC, expand=True) if a else im
    return _img[key]


# How a brick lands: it hits, squashes flat, springs up a little smaller each time, and wobbles like jelly
# before it settles. Each bounce is a real parabola; the squash peaks at every contact.
BOUNCES = [(0.0, 0.34, 52), (0.34, 0.56, 20), (0.56, 0.70, 7)]   # (from, to, height px) after impact


def landing(s: float, k: float) -> tuple[float, float, float]:
    """(lift above its slot, x scale, y scale) at s seconds after first touching down."""
    lift = 0.0
    for a, b, h in BOUNCES:
        if a <= s < b:
            u = (s - a) / (b - a)
            lift = 4 * h * k * u * (1 - u)
            break
    # squash at each contact, decaying: strongest on the first hit
    squash = 0.0
    for a, _b, h in BOUNCES:
        d = s - a
        if d >= 0:
            squash += (h / 52) * 0.32 * k * math.exp(-d * 22) * (1 if d < 0.25 else 0)
    # after the last bounce, a jelly wobble that dies away
    end = BOUNCES[-1][1]
    if s > end:
        d = s - end
        squash += 0.07 * math.exp(-d * 6) * math.cos(d * 26)
    # in the air between contacts it stretches a little the other way
    if lift > 0:
        squash -= 0.06 * min(1.0, lift / 20)
    return lift, 1 + squash * 0.85, 1 - squash


# --------------------------------------------------------------------------- the kid
# He comes first: the repaired walk-in clip (fix_clip.py made it; make_video.py opens with it too), with
# its own white wall as the whole scene's room. He walks in, stops at the far right with his hand at his
# chin, and the clip holds on its last frame while everything else happens. Its sound is not used.
KID_SRC = OUT / "intro" / "walk-in-fixed.mp4"
KID_FRAMES = OUT / "intro" / "walk-frames"      # shared with make_video.py


def extract_kid() -> None:
    KID_FRAMES.mkdir(parents=True, exist_ok=True)
    if list(KID_FRAMES.glob("*.jpg")):
        return
    import imageio_ffmpeg
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(KID_SRC),
                    "-vf", f"scale={W}:{H}:flags=lanczos,fps={FPS}", "-q:v", "2",
                    str(KID_FRAMES / "%04d.jpg")], check=True)


_kid_files: list[Path] = []
_kid: dict[int, Image.Image] = {}
_plate: list[Image.Image] = []


def empty_wall() -> Image.Image:
    """The wall with nobody on it, for the kid to fade into: his last frame, with the stretch he stands
    on taken from his first frame, when he was still in the middle."""
    if not _plate:
        kid_frame(0)
        first = Image.open(_kid_files[0]).convert("RGBA")
        last = Image.open(_kid_files[-1]).convert("RGBA")
        last.paste(first.crop((1540, 0, W, H)), (1540, 0))
        _plate.append(last)
    return _plate[0]


def kid_frame(t: float) -> Image.Image:
    if not _kid_files:
        _kid_files.extend(sorted(KID_FRAMES.glob("*.jpg")))
    i = min(int(t * FPS), len(_kid_files) - 1)
    if i not in _kid:
        _kid.clear()
        _kid[i] = Image.open(_kid_files[i]).convert("RGBA")
    return _kid[i].copy()


# --------------------------------------------------------------------------- the words
# The full video's own lines (make_video.py: LINES, TURN, ASKS), minus its first promise, the last
# question cut to "And how do you stay focused?". One at a time, on the left above GeekOc, each held for
# about four seconds so it can be read, then giving way to the next; the last one stays. The turn lands as
# GeekOc turns sad.
#
# Set in Playfair Display (SIL Open Font License, launch/video/fonts/): a display serif, bold, with the
# words that matter -- marked *like this* -- in its italic, in the brand's deep pink.
FONTS = OUT / "fonts"
INK, PINK = (40, 36, 60), (190, 40, 110)
HOLD, GAP = 4.0, 0.5                 # how long a line is up, and the pause before the next
PHRASES = [                          # (text, colour of the plain words)
    ("*Everyone* you need to *know* is out there.", INK),
    ("Every *chance* that *fits you* is out there.", INK),
    ("\u2026and so is *everything else.*", INK),
    ("So how do you find *your fit?*", INK),
    ("And how do you stay *focused?*", INK),     # the last: big, one line, centred (see FINALE)
]
Q_SIZE, Q_WEIGHT, Q_ITALIC_WEIGHT = 64, 700, 800
Q_X, Q_Y, Q_WIDTH = 90, 90, 600      # where a line starts, and how wide it may run
Q_LINE = 80                          # line height
WORD_EVERY, WORD_IN, WORD_RISE = 0.13, 0.5, 22   # stagger, fade time, how far each word rises
FADE_OUT = 0.5
FINALE_SIZE = 104                    # the last line's size...
FINALE_Y = 200                       # ...and its top: centred across, above the mountain's peak


def _font(name: str, size: int, weight: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / name), size)
    f.set_variation_by_axes([weight])
    return f


PLAIN = _font("PlayfairDisplay.ttf", Q_SIZE, Q_WEIGHT)
FANCY = _font("PlayfairDisplay-Italic.ttf", Q_SIZE, Q_ITALIC_WEIGHT)
BIG_PLAIN = _font("PlayfairDisplay.ttf", FINALE_SIZE, Q_WEIGHT)
BIG_FANCY = _font("PlayfairDisplay-Italic.ttf", FINALE_SIZE, Q_ITALIC_WEIGHT)


def _words(text: str) -> list[tuple[str, bool]]:
    """(word, highlighted) for each word; *stars* may span several words."""
    out, on = [], False
    for w in text.split():
        if w.startswith("*"):
            on, w = True, w[1:]
        end = "*" in w                                 # "fit?*", or "courses*," before punctuation
        w = w.replace("*", "")
        out.append((w, on))
        if end:
            on = False
    return out


def _wrap(text: str) -> list[list[tuple[str, bool, float]]]:
    """The phrase in as few lines as fit the column, broken where the lines come out most even -- so no
    word is ever left alone on the last line. Each line is a list of (word, highlighted, x offset)."""
    from itertools import combinations
    words = _words(text)
    space = PLAIN.getlength(" ")

    def width(ws):
        return sum((FANCY if hi else PLAIN).getlength(w) for w, hi in ws) + space * (len(ws) - 1)
    for n in range(1, len(words) + 1):
        best = None
        for cuts in combinations(range(1, len(words)), n - 1):
            edges = (0, *cuts, len(words))
            lines = [words[edges[i]:edges[i + 1]] for i in range(n)]
            widest = max(width(ln) for ln in lines)
            if widest <= Q_WIDTH and (best is None or widest < best[0]):
                best = (widest, lines)
        if best:
            out = []
            for ln in best[1]:
                x, row = 0.0, []
                for w, hi in ln:
                    row.append((w, hi, x))
                    x += (FANCY if hi else PLAIN).getlength(w) + space
                out.append(row)
            return out
    return [[(w, hi, 0.0)] for w, hi in words]


def layout_phrases() -> list[dict]:
    """Every word of every phrase: where it sits, when it arrives and leaves, its font and colour."""
    words, start = [], SWIM_IN + 0.8
    for k, (text, color) in enumerate(PHRASES):
        last = k == len(PHRASES) - 1
        end = OUTRO if last else start + HOLD
        if last:                                       # the finale: one big line, centred
            space = BIG_PLAIN.getlength(" ")
            ws = _words(text)
            total = sum((BIG_FANCY if hi else BIG_PLAIN).getlength(w) for w, hi in ws) + space * (len(ws) - 1)
            x = (W - total) / 2
            for n, (word, hi) in enumerate(ws):
                f = BIG_FANCY if hi else BIG_PLAIN
                words.append({"text": word, "x": x, "y": FINALE_Y, "at": start + n * WORD_EVERY * 1.4,
                              "end": end, "font": f, "color": PINK if hi else color})
                x += f.getlength(word) + space
            break
        n = 0
        for li, line in enumerate(_wrap(text)):
            for word, hi, x in line:
                words.append({"text": word, "x": Q_X + x, "y": Q_Y + li * Q_LINE,
                              "at": start + n * WORD_EVERY, "end": end,
                              "font": FANCY if hi else PLAIN, "color": PINK if hi else color})
                n += 1
        start += HOLD + GAP
    return words


# --------------------------------------------------------------------------- the end: icon and screens
# One screen at a time, under its name in dark gold and what it offers. The phone first, then "On your desktop"
# and the desktop's main screens. Each screen is a PANEL: it comes in full size in the middle, long enough to
# read its line; then it shrinks to about a third of its size, off to the left, and its details come one after
# another beside it, big, each with a short caption under it -- a zoomed crop of the screen itself, or of a
# second screenshot of the same page (scrolled, or with a question answered). After the last detail the screen
# grows back to full size, and the next panel takes its place.
#
# The phone's screens are taken for this, not the Play store's: on those the app's dock covers the lower third of
# the page. Here every page is shot with the dock fully folded (only the small ^ handle showing), so the page
# fills the phone; Home is shown once with the orbit open, as the first screen, because the orbit is how you get
# around. How they were taken: the myGeeKy app (1.23.0) on the Android emulator (Pixel 2 AVD, 1080x2400) with the
# maker's ORCID linked, the status bar in demo mode (12:00, full battery, no notifications); each page opened from a
# mygeeky:///home?sel=<page>&fold=1 link or the dock, left alone until the dock folds by itself, then
# `adb exec-out screencap -p`. My month and Badges are still the 1.17.1 shots (a profile with a full month behind
# it; the pages look the same). They live in launch/video/intro/phone/ (git-ignored). Retake them the same way
# after a big change to the app. (Gene or Pokémon? is left out: Pokémon is another company's brand.)
#
# Pages full of other people's names and faces (People, Live) or other companies' brands (the AI race) are left
# out, and so is the GitHub badges row on Badges (GitHub's artwork): the crop starts below it.
PHONE_SHOTS = OUT / "intro" / "phone"           # the phone's screens, dock folded (see above)
SHOTS = OUT / "intro" / "shots"                 # the desktop's tall retakes
SETUP_SHOTS = ROOT / "docs" / "screenshots"     # the installer's pages already show the whole window
APP_ICON = ROOT / "src" / "mygeeky" / "gui" / "assets" / "icon_256.png"
GOLD = (156, 112, 24)                           # dark gold: readable on the pale wall
# (screen, name, what it offers, [(file, crop box in the file's pixels, caption), ...])
TOUR = [
    ("home-orbit.png", "On your phone", "your world in orbit, learning what you enjoy", [
        ("home.png", (40, 630, 1040, 1490), "Each card says why it's there"),
    ]),
    ("protocols.png", "Protocols", "a step-by-step road map for any skill", [
        ("protocols.png", (40, 960, 1040, 1250), "Road maps reviewed for your field"),
        ("protocols-step.png", (40, 790, 1040, 2080), "Each step: what to read, watch and try"),
    ]),
    ("quiz.png", "Quiz", "every answer quotes the source that proves it", [
        ("quiz-question.png", (50, 580, 1030, 1630), "Ten questions from its own sources"),
        ("quiz.png", (50, 1490, 1030, 2120), "Each answer shows the line that proves it"),
    ]),
    ("jobs.png", "Jobs", "verified positions that match your work", [
        ("jobs.png", (50, 660, 1030, 1420), "Checked by hand, matched to your work"),
        ("seasons.png", (50, 900, 1030, 1960), "Yearly calls, before they open"),
    ]),
    ("skills.png", "Rising Skills", "what to learn next, before everyone else", [
        ("skills.png", (40, 500, 1040, 1400), "Each rocket launches from a skill you have"),
        ("skills-more.png", (60, 990, 1020, 1490), "How far each one is from you"),
        ("skills.png", (60, 1480, 1020, 2080), "Which of your skills leads where"),
    ]),
    ("papers.png", "Papers", "rising in your field, gaining citations fastest", [
        ("papers-open.png", (40, 450, 1040, 1300), "Who wrote it, what it found, and its code"),
    ]),
    ("games.png", "Play with GeeKOc", "short games made from your own field", [
        ("games.png", (40, 315, 1040, 1010), "Fourteen games, each from your field"),
        ("game-rise.png", (50, 1380, 1030, 1880), "A wrong step sinks, and says why"),
    ]),
    ("month.png", "My month", "your month, your rank, your card to share", [
        ("month.png", (30, 390, 1050, 850), "A rank that climbs with what you do"),
        ("month.png", (40, 960, 1040, 2210), "Your month as a card to share"),
        ("badges.png", (40, 720, 1040, 1770), "Badges for the habits that help you grow"),
    ]),
]

# Then the desktop: the panel beside your work, and what it adds. (Live and Pulse are left out: they are
# mostly other people's faces and names.)
DESK = [
    ("grow-protocols.png", "On your desktop", "a panel beside your work, with even more", [
        ("grow-protocols.png", (20, 260, 940, 1180), "The same road maps, beside your code"),
    ]),
    ("grow-learn.png", "Learn", "courses, books and tutorials for your skills", [
        ("grow-learn.png", (20, 400, 940, 960), "What each one teaches, and why it's yours"),
    ]),
    ("research.png", "Research", "the papers behind the code, and who wrote them", [
        ("research.png", (20, 560, 940, 1240), "Rising papers, with the code that uses them"),
    ]),
    ("signals.png", "Signals", "a private thank-you, no reply needed", [
        ("signals.png", (20, 250, 940, 1070), "Your field, and who would welcome a word"),
    ]),
    ("model.png", "Your Model", "see what myGeeKy knows about you", [
        ("model.png", (20, 560, 940, 1340), "Your field, and what you're into lately"),
    ]),
]

# A panel's timing: the screen alone at full size, then each detail, then the screen grown back.
P_LEAD, P_MOVE, EX_EACH, P_BACK = 2.0, 0.6, 2.8, 0.9


def panel_len(panel: tuple) -> float:
    return P_LEAD + P_MOVE + len(panel[3]) * EX_EACH + P_BACK


def _starts(panels: list, at: float) -> list[float]:
    out = []
    for p in panels:
        out.append(at)
        at += panel_len(p)
    return out


TOUR_STARTS = _starts(TOUR, TOUR_AT)
TOUR_END = TOUR_STARTS[-1] + panel_len(TOUR[-1])
DESK_HERO_AT = TOUR_END + 0.4                   # where the desktop part starts (a swish in the soundtrack)
DESK_AT = DESK_HERO_AT
DESK_STARTS = _starts(DESK, DESK_AT)
DESK_END = DESK_STARTS[-1] + panel_len(DESK[-1])
# every detail's start, for the soundtrack
EXAMPLE_TIMES = [s + P_LEAD + P_MOVE + j * EX_EACH for panels, starts in ((TOUR, TOUR_STARTS), (DESK, DESK_STARTS))
                 for p, s in zip(panels, starts) for j in range(len(p[3]))]

# How to install: the installer's pages, then the one command for any OS.
SETUP = [
    ("setup-welcome.png", "Download", "MyGeeKySetup.exe brings Python and Git if needed"),
    ("setup-github.png", "GitHub", "a read-only token, kept in your keyring"),
    ("setup-signals.png", "Signals", "a second token that can write to one repo only"),
    ("setup-finish.png", "Done", "in your Start menu, and running at startup"),
]
INSTALL_AT, INSTALL_EACH = DESK_END + 0.4, 3.4
TERM_AT = INSTALL_AT + len(SETUP) * INSTALL_EACH
TERM_DUR = 5.6
TERM_LINE = ("macOS, Linux or Windows", "one command")
VERSION = next(line.split('"')[1] for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines()
               if line.startswith("version = "))
TERM_SCRIPT = [               # (at, kind, text): typed after a prompt, or printed
    (0.5, "cmd", "pip install mygeeky"),
    (1.9, "out", "Collecting mygeeky"),
    (2.3, "out", f"  Downloading mygeeky-{VERSION}-py3-none-any.whl"),
    (3.1, "ok", f"Successfully installed mygeeky-{VERSION}"),
    (3.9, "cmd", "mygeeky gui"),
]
LEAVE_AT, LEAVE = TERM_AT + TERM_DUR - 0.6, 3.0   # GeekOc swims off to the right

# The promises, one at a time, each with the website's picture for it (website/img/promises/) and its words.
PROMISES = [
    ("acts.webp", "Never acts as you.", "It never follows, stars, posts or comments."),
    ("device.webp", "Never leaves your device.", "The model runs on your computer or phone."),
    ("keys.webp", "Never holds your keys.", "Tokens stay in your system's keyring."),
    ("data.webp", "Never takes your data.", "Only your own Google Drive or a private repo, if you want."),
    ("sends.webp", "Never sends behind your back.", "If it breaks, you read the whole report first."),
]
PROMISE_RING = {"acts.webp": (251, 146, 60), "device.webp": (45, 212, 191), "keys.webp": (198, 230, 58),
                "data.webp": (255, 106, 77), "sends.webp": (217, 70, 239)}   # the website's colour for each
PROMISE_AT, PROMISE_EACH = LEAVE_AT + 1.6, 3.8
FINALE_AT = PROMISE_AT + len(PROMISES) * PROMISE_EACH + 0.4
FINALE_TEXT = "Your geeky friend who helps you *grow, quietly.*"
PLATFORMS_AT = FINALE_AT + 3.4                   # Google Play, Windows, macOS appear under it
DUR = FINALE_AT + 7.5                            # the whole scene

SHOT_H, SHOT_X, SHOT_TOP = 800, W // 2, 245      # a screen's height, centre and top
SMALL = 0.3                                      # ...its size while its details show...
PHONE_SMALL_AT = (330, 895)                      # ...and where it goes: under the icon and its name
DESK_SMALL_AT = (330, 600)                       # (no icon by then: the desktop's goes higher)
EX_X, EX_TOP, EX_W, EX_H = 945, 250, 760, 660    # a detail: centre across, top, and the box it fits in
EX_MAX = 1.25                                    # ...never blown up more than this
SETUP_H, SETUP_X, SETUP_TOP = 760, 900, 270      # an installer page: a little left, clear of GeekOc
LINE_SIZE, LINE_Y = 56, 150                      # a "Name: what it offers" line's size and top
LOGO_SIZE, LOGO_X, LOGO_Y = 250, 330, 470        # the icon's size and where it comes to rest (centre)
L_NAME = _font("PlayfairDisplay.ttf", LINE_SIZE, 800)
L_TEXT = _font("PlayfairDisplay.ttf", LINE_SIZE, 600)
NAME = _font("PlayfairDisplay.ttf", 84, 800)
P_TITLE = _font("PlayfairDisplay.ttf", 80, 750)
P_SUB = _font("PlayfairDisplay-Italic.ttf", 50, 500)
EX_CAP = _font("PlayfairDisplay-Italic.ttf", 42, 600)   # a detail's caption
SUBTLE = (92, 86, 112)
FIN_PLAIN = _font("PlayfairDisplay.ttf", 76, 700)
FIN_FANCY = _font("PlayfairDisplay-Italic.ttf", 76, 800)
MONO = ROOT / "website" / "fonts" / "JetBrainsMono-latin.woff2"


def _line_words(parts: list[tuple[str, ImageFont.FreeTypeFont, tuple]], y: float, cx: float,
                start: float, end: float | None, every: float = WORD_EVERY) -> list[dict]:
    """A centred line from (text, font, colour) runs, as words arriving one after another."""
    words = [(w, f, c) for text, f, c in parts for w in text.split()]
    space = L_TEXT.getlength(" ")
    total = sum(f.getlength(w) for w, f, _ in words) + space * (len(words) - 1)
    x, out = cx - total / 2, []
    for n, (w, f, c) in enumerate(words):
        out.append({"text": w, "x": x, "y": y, "at": start + n * every, "end": end, "font": f, "color": c})
        x += f.getlength(w) + space
    return out


def _name_line(name: str, what: str, start: float, end: float | None) -> list[dict]:
    return _line_words([(name + ":", L_NAME, GOLD), (what, L_TEXT, INK)], LINE_Y, W / 2, start + 0.25, end)


def layout_end() -> list[dict]:
    words = []
    for panels, starts in ((TOUR, TOUR_STARTS), (DESK, DESK_STARTS)):
        for (_shot, name, what, _ex), start in zip(panels, starts):
            words += _name_line(name, what, start, start + panel_len((0, 0, 0, _ex)) - FADE_OUT)
    for i, (_shot, name, what) in enumerate(SETUP):
        start = INSTALL_AT + i * INSTALL_EACH
        words += _name_line(name, what, start, start + INSTALL_EACH - FADE_OUT)
    words += _name_line(*TERM_LINE, TERM_AT, TERM_AT + TERM_DUR - FADE_OUT)
    for i, (_icon, title, sub) in enumerate(PROMISES):
        start = PROMISE_AT + i * PROMISE_EACH
        end = start + PROMISE_EACH - FADE_OUT
        first, rest = title.split(" ", 1)               # "Never" in gold, the rest in ink
        words += _line_words([(first, P_TITLE, GOLD), (rest, P_TITLE, INK)], 520, W / 2, start + 0.35, end)
        words += _line_words([(sub, P_SUB, SUBTLE)], 640, W / 2, start + 1.3, end, every=0.07)
    fin = [(w, FIN_FANCY if hi else FIN_PLAIN, PINK if hi else INK) for w, hi in _words(FINALE_TEXT)]
    runs = [(w, f, c) for w, f, c in fin]
    words += _line_words(runs, 640, W / 2, FINALE_AT + 0.9, None, every=0.16)
    return words


QWORDS = layout_phrases() + layout_end()
_cards: dict[tuple, Image.Image] = {}


def rounded(im: Image.Image) -> Image.Image:
    """A picture with rounded corners and a soft shadow under it."""
    im = im.convert("RGBA")
    r, pad = 22, 40
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), r, fill=255)
    im.putalpha(mask)
    out = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", out.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 12, pad + im.width, pad + im.height + 12), r, fill=90)
    shadow = Image.new("RGBA", out.size, (40, 30, 70, 0))
    shadow.putalpha(sh.filter(ImageFilter.GaussianBlur(18)))
    out.alpha_composite(shadow)
    out.alpha_composite(im, (pad, pad))
    return out


_src: dict[str, Image.Image] = {}


def source(path: Path) -> Image.Image:
    if str(path) not in _src:
        _src[str(path)] = Image.open(path).convert("RGBA")
    return _src[str(path)]


def card(path: Path, height: int) -> Image.Image:
    """A screen at a height, with rounded corners and a soft shadow under it. While a screen shrinks or grows
    it is asked for at every height in between, so the cache is kept small."""
    key = (str(path), height)
    if key not in _cards:
        if len(_cards) > 40:
            _cards.clear()
        im = source(path)
        _cards[key] = rounded(im.resize((max(1, int(im.width * height / im.height)), height), Image.LANCZOS))
    return _cards[key]


def detail(path: Path, box: tuple) -> Image.Image:
    """A detail: that part of a screenshot, as big as fits the detail box (never blown up past EX_MAX)."""
    key = (str(path), box)
    if key not in _cards:
        im = source(path).crop(box)
        k = min(EX_W / im.width, EX_H / im.height, EX_MAX)
        _cards[key] = rounded(im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS))
    return _cards[key]


def faded(im: Image.Image, a: float) -> Image.Image:
    if a >= 1:
        return im
    out = im.copy()
    out.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    return out


def window(t: float, start: float, length: float) -> float:
    """0..1..0: in over half a second from start, out over FADE_OUT before start + length."""
    if t < start or t > start + length:
        return 0.0
    return ease((t - start) / 0.5) * (1 - ease((t - (start + length - FADE_OUT)) / FADE_OUT))


def _caption_lines(text: str) -> list[str]:
    """A caption on one line, or two if it is wider than the detail box."""
    if EX_CAP.getlength(text) <= EX_W + 60:           # a caption may run a little wider than its picture
        return [text]
    words = text.split()
    best = min(range(1, len(words)), key=lambda i: max(EX_CAP.getlength(" ".join(words[:i])),
                                                         EX_CAP.getlength(" ".join(words[i:]))))
    return [" ".join(words[:best]), " ".join(words[best:])]


def panel(im: Image.Image, t: float, p: tuple, folder: Path, start: float, small_at: tuple) -> None:
    """One screen and its details. The screen comes in full size in the middle; after P_LEAD it shrinks to
    SMALL, moving to small_at, and its details come one at a time in the space it left; then it grows back."""
    shot, _name, _what, examples = p
    length = panel_len(p)
    a = window(t, start, length)
    if a <= 0:
        return
    u = t - start
    ex0 = P_LEAD + P_MOVE                              # the details wait until the screen has moved aside
    ex_end = ex0 + len(examples) * EX_EACH
    k = ease((u - P_LEAD) / P_MOVE) * (1 - ease((u - (ex_end - 0.4)) / P_MOVE))   # 0 full size .. 1 small
    h = int(round(SHOT_H * (1 + (SMALL - 1) * k)))
    c = card(folder / shot, h)
    # down first, then across: on the phone a straight line would cut through the icon's name on its way
    cx = SHOT_X + (small_at[0] - SHOT_X) * ease((k - 0.4) / 0.6)
    cy = (SHOT_TOP + SHOT_H / 2) + (small_at[1] - (SHOT_TOP + SHOT_H / 2)) * ease(k / 0.6)
    cy = min(cy, H - 40 - h / 2)                       # ...and never off the bottom while still big
    rise = 34 * (1 - ease(u / 0.6))
    im.alpha_composite(faded(c, a), (int(cx - c.width / 2), int(cy - c.height / 2 + rise)))
    for j, (file, box, caption) in enumerate(examples):
        es = start + ex0 + j * EX_EACH
        if not es <= t <= es + EX_EACH:
            continue
        e = ease((t - es) / 0.35) * (1 - ease((t - (es + EX_EACH - 0.35)) / 0.35))
        if e <= 0:
            continue
        d = detail((PHONE_SHOTS if folder == PHONE_SHOTS else SHOTS) / file, box)
        lines = _caption_lines(caption)
        cap_h = 10 + 54 * len(lines)
        # the picture (d has a 40 px margin for its shadow) and its caption, centred together in the box,
        # rising a little as they come
        group = d.height - 80 + cap_h
        top = EX_TOP + max(0, (EX_H + 64 - group) / 2) + 20 * (1 - ease((t - es) / 0.45))
        im.alpha_composite(faded(d, e), (int(EX_X - d.width / 2), int(top - 40)))
        layer = Image.new("RGBA", (EX_W + 200, cap_h + 20), (0, 0, 0, 0))
        dr = ImageDraw.Draw(layer)
        for n, line in enumerate(lines):
            dr.text(((layer.width - EX_CAP.getlength(line)) / 2, n * 54), line, font=EX_CAP,
                    fill=INK + (int(255 * e),))
        im.alpha_composite(layer, (int(EX_X - layer.width / 2), int(top + d.height - 80 + 14)))


def screens(im: Image.Image, t: float) -> None:
    """The phone's panels, the desktop's, then the installer's pages: one at a time, each rising into place."""
    for panels, starts, small_at, folder in ((TOUR, TOUR_STARTS, PHONE_SMALL_AT, PHONE_SHOTS),
                                             (DESK, DESK_STARTS, DESK_SMALL_AT, SHOTS)):
        for p, start in zip(panels, starts):
            panel(im, t, p, folder, start, small_at)
    for i, (shot, *_rest) in enumerate(SETUP):
        start = INSTALL_AT + i * INSTALL_EACH
        a = window(t, start, INSTALL_EACH)
        if a <= 0:
            continue
        c = card(SETUP_SHOTS / shot, SETUP_H)
        rise = 34 * (1 - ease((t - start) / 0.6))
        im.alpha_composite(faded(c, a), (SETUP_X - c.width // 2, int(SETUP_TOP - 40 + rise)))


def terminal(im: Image.Image, t: float) -> None:
    """A terminal typing the one command, and myGeeKy installing."""
    a = window(t, TERM_AT, TERM_DUR)
    if a <= 0:
        return
    tt = t - TERM_AT
    w, h = 960, 380                                    # clear of GeekOc, on the right
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((0, 0, w - 1, h - 1), 22, fill=(16, 16, 24, 255))
    d.rounded_rectangle((0, 0, w - 1, 54), 22, fill=(34, 34, 48, 255))
    d.rectangle((0, 32, w - 1, 54), fill=(34, 34, 48, 255))
    for i, col in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        d.ellipse((24 + i * 34, 17, 44 + i * 34, 37), fill=col + (255,))
    mono = ImageFont.truetype(str(MONO), 30)
    title = ImageFont.truetype(str(MONO), 22)
    d.text(((w - d.textlength("Terminal", font=title)) / 2, 15), "Terminal", font=title, fill=(150, 150, 170, 255))
    y = 84
    last = None
    for at, kind, text in TERM_SCRIPT:
        if tt < at:
            break
        if kind == "cmd":
            typed = text[:int((tt - at) * 20)]
            d.text((34, y), "$ ", font=mono, fill=(127, 216, 255, 255))
            x = 34 + d.textlength("$ ", font=mono)
            d.text((x, y), typed, font=mono, fill=(240, 240, 245, 255))
            last = (x + d.textlength(typed, font=mono), y)
        else:
            d.text((34, y), text, font=mono, fill=((52, 211, 153) if kind == "ok" else (170, 172, 190)) + (255,))
            last = None
        y += 46
    if last and int(tt * 2) % 2 == 0:
        d.rectangle((last[0] + 4, last[1] + 4, last[0] + 20, last[1] + 36), fill=(240, 240, 245, 200))
    out = Image.new("RGBA", (w + 120, h + 120), (0, 0, 0, 0))
    sh = Image.new("L", out.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((60, 76, w + 60, h + 76), 22, fill=110)
    shadow = Image.new("RGBA", out.size, (40, 30, 70, 0))
    shadow.putalpha(sh.filter(ImageFilter.GaussianBlur(26)))
    out.alpha_composite(shadow)
    out.alpha_composite(layer, (60, 60))
    rise = 34 * (1 - ease(tt / 0.6))
    im.alpha_composite(faded(out, a), (840 - out.width // 2, int(560 - out.height // 2 + rise)))


_badges: dict[str, Image.Image] = {}


def badge(icon: str, size: int = 220) -> Image.Image:
    """A promise's icon: the website's round picture in a ring of its colour, with a soft glow (or, for an old
    .svg line drawing, white on a violet-to-pink badge)."""
    if icon not in _badges and icon.endswith(".webp"):
        pad, ring = 60, PROMISE_RING.get(icon, (214, 72, 170))
        out = Image.new("RGBA", (size + 2 * pad, size + 2 * pad), (0, 0, 0, 0))
        glow = Image.new("RGBA", out.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((pad - 6, pad + 4, pad + size + 6, pad + size + 16), fill=ring + (110,))
        out.alpha_composite(glow.filter(ImageFilter.GaussianBlur(26)))
        ImageDraw.Draw(out).ellipse((pad - 7, pad - 7, pad + size + 7, pad + size + 7), fill=ring + (255,))
        pic = Image.open(ROOT / "website" / "img" / "promises" / icon).convert("RGBA").resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        pic.putalpha(Image.fromarray(np.minimum(np.array(pic.getchannel("A")), np.array(mask))))
        out.alpha_composite(pic, (pad, pad))
        _badges[icon] = out
    if icon not in _badges:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtCore import QByteArray, Qt
        from PySide6.QtGui import QGuiApplication, QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
        QGuiApplication.instance() or QGuiApplication([])
        svg = (OUT / "promise-icons" / icon).read_text().replace("currentColor", "#ffffff") \
            .replace('stroke-width="2"', 'stroke-width="1.6"')
        px = int(size * 0.5)
        r = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        q = QImage(px, px, QImage.Format_ARGB32)
        q.fill(Qt.transparent)
        p = QPainter(q)
        p.setRenderHint(QPainter.Antialiasing, True)
        r.render(p)
        p.end()
        tmp = OUT / "intro" / "_badge.png"
        q.save(str(tmp))
        glyph = Image.open(tmp).convert("RGBA")
        tmp.unlink()
        pad = 60
        out = Image.new("RGBA", (size + 2 * pad, size + 2 * pad), (0, 0, 0, 0))
        glow = Image.new("RGBA", out.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((pad, pad + 10, pad + size, pad + size + 10), fill=(122, 92, 255, 90))
        out.alpha_composite(glow.filter(ImageFilter.GaussianBlur(24)))
        g = np.linspace(0, 1, size)[None, :, None]
        a, b = np.array((122, 92, 255))[None, None], np.array((214, 72, 170))[None, None]
        grad = (a * (1 - g) + b * g).repeat(size, axis=0).astype(np.uint8)
        disc = Image.fromarray(grad, "RGB").convert("RGBA")
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        disc.putalpha(mask)
        out.alpha_composite(disc, (pad, pad))
        out.alpha_composite(glyph, (pad + (size - px) // 2, pad + (size - px) // 2))
        _badges[icon] = out
    return _badges[icon]


def pop(k: float) -> float:
    """0 -> 1 with a little overshoot, for things that appear."""
    k = min(max(k, 0.0), 1.0)
    return 1 + 2.2 * (k - 1) ** 3 + 1.2 * (k - 1) ** 2 if k < 1 else 1.0


def promises(im: Image.Image, t: float) -> None:
    for i, (icon, _title, _sub) in enumerate(PROMISES):
        start = PROMISE_AT + i * PROMISE_EACH
        a = window(t, start, PROMISE_EACH)
        if a <= 0:
            continue
        s = max(0.3, pop((t - start) / 0.55))
        b = badge(icon)
        pic = b.resize((int(b.width * s), int(b.height * s)), Image.LANCZOS)
        im.alpha_composite(faded(pic, a), (W // 2 - pic.width // 2, 300 - pic.height // 2))


_logo: list[Image.Image] = []


def logo_src() -> Image.Image:
    if not _logo:
        _logo.append(Image.open(APP_ICON).convert("RGBA"))
    return _logo[0]


def logo(im: Image.Image, t: float) -> None:
    """The myGeeKy icon drops out of the sky on the left and lands like a brick: stretched as it falls,
    squashed when it hits, a few bounces and a wobble. Then its name fades in under it. Both leave with
    the last screen."""
    k = (t - LOGO_AT) / LOGO_FALL
    if k <= 0:
        return
    out_a = 1 - ease((t - (TOUR_END - FADE_OUT)) / 0.8)
    if out_a <= 0:
        return
    src = logo_src()
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    if k < 1:
        stretch = 0.18 * k
        w, h = int(LOGO_SIZE * (1 - stretch * 0.6)), int(LOGO_SIZE * (1 + stretch))
        y = -h + (LOGO_Y + LOGO_SIZE / 2 - (-h)) * k * k          # its bottom, falling
        pic = src.resize((w, h), Image.LANCZOS).rotate(-25 * (1 - k) ** 2, Image.BICUBIC, expand=True)
        layer.alpha_composite(pic, (int(LOGO_X - pic.width / 2), int(y - pic.height)))
    else:
        lift, sx, sy = landing(t - LOGO_AT - LOGO_FALL, 1.0)
        pic = src.resize((int(LOGO_SIZE * sx), int(LOGO_SIZE * sy)), Image.LANCZOS)
        bottom = LOGO_Y + LOGO_SIZE / 2 - lift * 1.8
        layer.alpha_composite(pic, (int(LOGO_X - pic.width / 2), int(bottom - pic.height)))
        a = ease((t - LOGO_AT - LOGO_FALL - 0.5) / 0.6)
        if a > 0:
            d = ImageDraw.Draw(layer)
            name_w = d.textlength("myGeeKy", font=NAME)
            d.text((LOGO_X - name_w / 2, LOGO_Y + LOGO_SIZE / 2 + 30 + 16 * (1 - a)), "myGeeKy", font=NAME,
                   fill=INK + (int(255 * a),))
    im.alpha_composite(faded(layer, out_a))


def finale(im: Image.Image, t: float) -> None:
    """Last: the myGeeKy icon in the middle, popping in, over its line."""
    k = (t - FINALE_AT) / 0.7
    if k <= 0:
        return
    s = max(0.3, pop(k))
    size = int(280 * s)
    cy = 360
    pic = logo_src().resize((size, size), Image.LANCZOS)
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((W / 2 - 220, cy - 220, W / 2 + 220, cy + 220),
                                 fill=(214, 72, 170, int(60 * ease(k))))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(50)))
    im.alpha_composite(faded(pic, ease(k)), (W // 2 - size // 2, cy - size // 2))
    platforms(im, t)


# Where it runs, drawn here rather than taken from anyone's artwork: Google Play's four-colour triangle,
# Windows' four panes, and for macOS a plain laptop -- no Apple logo.
PLATFORMS = [("play", "Google Play"), ("windows", "Windows"), ("mac", "macOS")]
PLAT_SIZE, PLAT_GAP, PLAT_Y = 96, 300, 860        # mark size, centre to centre, the marks' centre
PLAT_LABEL = _font("PlayfairDisplay.ttf", 36, 650)
_marks: dict[str, Image.Image] = {}


def mark(kind: str) -> Image.Image:
    if kind not in _marks:
        n = PLAT_SIZE * 4                               # drawn big, then shrunk: smooth edges
        im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        if kind == "play":
            a, b, tip = (n * 0.14, n * 0.04), (n * 0.14, n * 0.96), (n * 0.94, n * 0.5)
            o = (n * 0.5, n * 0.5)
            near = (n * 0.72, n * 0.5)
            d.polygon([a, o, b], fill=(66, 133, 244, 255))                       # blue, the left
            d.polygon([a, (n * 0.7, n * 0.36), near, o], fill=(52, 168, 83, 255))  # green, the top
            d.polygon([b, (n * 0.7, n * 0.64), near, o], fill=(234, 67, 53, 255))  # red, the bottom
            d.polygon([(n * 0.7, n * 0.36), tip, (n * 0.7, n * 0.64), near], fill=(251, 188, 4, 255))
            mask = Image.new("L", (n, n), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, n, n), 0, fill=0)
            ImageDraw.Draw(mask).polygon([a, b, tip], fill=255)
            im.putalpha(Image.fromarray(np.minimum(np.array(im.getchannel("A")), np.array(mask))))
        elif kind == "windows":
            g, half = n * 0.05, n * 0.45
            for i in range(2):
                for j in range(2):
                    x0 = n * 0.05 + i * (half + g)
                    y0 = n * 0.05 + j * (half + g)
                    d.rectangle((x0, y0, x0 + half, y0 + half), fill=(0, 120, 212, 255))
        else:                                           # a laptop, in ink: screen, then base
            w8 = n * 0.05
            d.rounded_rectangle((n * 0.16, n * 0.18, n * 0.84, n * 0.66), n * 0.05, outline=INK + (255,), width=int(w8))
            d.rounded_rectangle((n * 0.04, n * 0.74, n * 0.96, n * 0.82), n * 0.04, fill=INK + (255,))
        _marks[kind] = im.resize((PLAT_SIZE, PLAT_SIZE), Image.LANCZOS)
    return _marks[kind]


def platforms(im: Image.Image, t: float) -> None:
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0 = W / 2 - PLAT_GAP * (len(PLATFORMS) - 1) / 2
    for i, (kind, label) in enumerate(PLATFORMS):
        k = (t - (PLATFORMS_AT + i * 0.3)) / 0.5
        if k <= 0:
            continue
        a, s = ease(k), max(0.3, pop(k))
        cx = x0 + i * PLAT_GAP
        m = mark(kind)
        m = m.resize((int(m.width * s), int(m.height * s)), Image.LANCZOS)
        layer.alpha_composite(faded(m, a), (int(cx - m.width / 2), int(PLAT_Y - m.height / 2)))
        lw = d.textlength(label, font=PLAT_LABEL)
        d.text((cx - lw / 2, PLAT_Y + PLAT_SIZE / 2 + 18), label, font=PLAT_LABEL, fill=SUBTLE + (int(255 * a),))
    im.alpha_composite(layer)


def questions(im: Image.Image, t: float) -> None:
    """Every word on screen at t: arriving (fading in as it rises into place), or leaving with its line."""
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for w in QWORDS:
        k = (t - w["at"]) / WORD_IN
        if k <= 0:
            continue
        e = ease(k)
        if w["end"] is not None:                       # leaving: the whole line fades together
            e *= 1 - ease((t - w["end"]) / FADE_OUT)
            if e <= 0:
                continue
        d.text((w["x"], w["y"] + WORD_RISE * (1 - ease(k))), w["text"], font=w["font"],
               fill=w["color"] + (int(255 * e),))
    im.alpha_composite(layer)


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def frame(t: float, icons, pile) -> Image.Image:
    """The whole picture at t: the kid's clip underneath, and the rest of the scene KID_LEAD behind it."""
    im = kid_frame(t)
    t -= KID_LEAD
    if t < 0:
        return im.convert("RGB")
    gone = ease((t - OUTRO) / CLEAR)                   # the kid and the mountain fading away
    if gone > 0:
        im = Image.blend(im, empty_wall(), gone)

    # GeekOc first: his motion, his arms and his mood all come out of the simulation
    gx = int(geek_x(t))
    if gx - GEEK_SIZE // 2 < W:
        im.alpha_composite(geek(int(round(t * FPS))), (gx - GEEK_SIZE // 2, GEEK_Y - GEEK_SIZE // 2))

    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    for p in (pile if gone < 1 else []):
        k = (t - p["at"]) / p["fall"]
        if k <= 0:
            continue
        if k < 1:                                      # in the air: accelerating, stretched by the speed
            angle = p["spin_air"] * (1 - k) ** 2        # tumbling, and squared up by the time it lands
            stretch = 0.16 * k
            pic = piece_img(icons, p, angle, 1 - stretch * 0.6, 1 + stretch)
            y0 = -pic.height
            yc = y0 + (p["y"] - y0) * (k * k)
            x = p["x"] + p["drift"] * (1 - k) ** 2
            layer.alpha_composite(pic, (int(x - pic.width / 2), int(yc - pic.height / 2)))
        else:                                          # down: bounce, squash, wobble, rest
            lift, sx, sy = landing(t - p["at"] - p["fall"], p["bounce"])
            pic = piece_img(icons, p, 0, sx, sy)
            bottom = p["y"] + p["size"] / 2 - lift     # squash from the bottom: it sits on what is below
            layer.alpha_composite(pic, (int(p["x"] - pic.width / 2), int(bottom - pic.height)))
    im.alpha_composite(faded(layer, 1 - gone))
    logo(im, t)
    screens(im, t)
    terminal(im, t)
    promises(im, t)
    finale(im, t)
    questions(im, t)
    return im.convert("RGB")


def main() -> None:
    icons = prepare_icons()
    if not icons:
        raise SystemExit("no icons found -- pass --assets DIR")
    render_geekoc()
    extract_kid()
    pile = plan(len(icons))
    total = KID_LEAD + DUR
    if "--preview" in sys.argv:
        for sec in (40.0, 80.0, 117.0, total - 0.5):   # a phone detail, a desktop one, the end
            frame(sec, icons, pile).save(OUT / f"falling_{sec:04.1f}.png")
        print("preview frames written")
        return
    import imageio_ffmpeg
    video = OUT / "falling.mp4"
    proc = subprocess.Popen([
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(video)], stdin=subprocess.PIPE)
    for n in range(int(total * FPS)):
        proc.stdin.write(frame(n / FPS, icons, pile).tobytes())
        if n % (FPS * 4) == 0:
            print(f"  {n / FPS:4.0f}s / {total:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    print(f"Wrote {video} ({video.stat().st_size / 1e6:.1f} MB, {total:.0f} s)")


if __name__ == "__main__":
    main()
