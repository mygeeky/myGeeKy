"""GeekOc watching something grow: the README's picture under the title.

    python docs/make_grow_scene.py     ->  docs/geekoc/geekoc-grows.svg (and a .png beside it)

The octopus is not drawn here. He comes out of the rig in `website/geekoc/geekoc.js`, the same one the
website animates, so he cannot drift away from himself: change the rig and this picture changes with
it. Only the plant, the pot and the sparks are drawn here, in his palette and with his outline weight,
because a plant drawn in a different hand would read as clip art sitting next to him.

He is given his own face for this: excited, but looking RIGHT, at the plant. A character looking out
of the picture while pointing at something inside it is the thing that makes an illustration feel
wrong without anyone being able to say why.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "website" / "geekoc" / "geekoc.js"
OUT_SVG = Path(__file__).parent / "geekoc" / "geekoc-grows.svg"

W, H = 1000, 440   # the extra width is where the words go, to the right of the plant

# his palette, so the plant belongs to the same drawing
INK = "#2b1053"          # the outline every shape of his carries
OW = 7                   # and its weight
LEAF = "#35e0c1"
LEAF_DEEP = "#19b89b"
STEM = "#1f9c86"
POT = "#ffc457"          # the same gold as his belly and his suckers' band
POT_DEEP = "#e8a93a"
SPARK = "#ffc457"

# HE REACTS, and what he does follows what the plant is doing: he watches it come up, is surprised
# by the first leaf, points it out, is delighted when it is done, and ends amused.
#
# Every one of these looks RIGHT, at the plant. `look` moves a pupil by only nine units inside an eye
# of thirty, so even a full 1.0 reads as "straight ahead with a thought". The engine does not clamp
# it and the pupil is clipped to the eye anyway, so this scene asks for far more than the faces do.
#
# `lids` as a PAIR is a wink, which is the nearest the rig has to amused.
REACTIONS = [
    # pose,    face,                                                                  from, to
    ("idle",  {"mouth": "smile", "brow": 0.45, "lids": 0.1, "look": [1.6, 0.15]},     0.00, 0.25),
    ("idle",  {"mouth": "oh", "brow": 1.0, "lids": 0, "look": [1.7, -0.05]},          0.25, 0.43),
    ("point", {"mouth": "open", "brow": 0.9, "lids": 0, "look": [1.75, -0.2]},        0.43, 0.61),
    ("cheer", {"mouth": "open", "brow": 1.0, "lids": 0, "look": [1.5, -0.45]},        0.61, 0.80),
    ("idle",  {"mouth": "grin", "brow": 0.35, "lids": [0, 1], "look": [1.5, 0.05]},   0.80, 1.00),
]
STILL_REACTION = 3       # the one a still shows: delighted, beside a grown plant


def geekoc(size: int, pose: str, face: dict, ident: str) -> str:
    """One drawing of the octopus, out of the rig.

    Each reaction gets its own `id`, because several of him end up in the same file and they would
    otherwise share one set of gradient and clip-path names."""
    js = """
      require(process.env.GEEKOC);
      const G = globalThis.GeekOc;
      G.FACES.__r = JSON.parse(process.env.FACE);
      process.stdout.write(G.svg({ pose: process.env.POSE, face: '__r', t: 1.4, still: true,
                                   id: process.env.IDENT, size: Number(process.env.SIZE) }));
    """
    env = {**os.environ, "GEEKOC": str(ENGINE), "FACE": json.dumps(face), "POSE": pose,
           "IDENT": ident, "SIZE": str(size)}
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=180, env=env)
    if r.returncode != 0:
        raise SystemExit("node could not draw GeekOc:\n" + (r.stderr or "")[-500:])
    return r.stdout.strip()


def reacting(x: int, y: int, size: int) -> str:
    """All of his reactions, stacked, with one visible at a time.

    Cross-fading stacked drawings is how a rig that produces stills becomes a performance. The
    changes are quick on purpose -- a slow dissolve between two faces reads as a ghost, where a
    fast one reads as him having reacted."""
    snap = 0.012
    out = []
    for i, (pose, face, start, end) in enumerate(REACTIONS):
        drawing = placed(geekoc(size, pose, face, f"r{i}"), x, y, size)
        if start <= 0:                       # on screen from the very beginning
            values, keytimes = "1;1;0;0", f"0;{end:.3f};{end + snap:.3f};1"
        elif end >= 1:                       # ...and this one carries the cycle out
            values, keytimes = "0;0;1;1", f"0;{start:.3f};{start + snap:.3f};1"
        else:
            values = "0;0;1;1;0;0"
            keytimes = (f"0;{start:.3f};{start + snap:.3f};"
                        f"{end:.3f};{end + snap:.3f};1")
        base = "1" if i == STILL_REACTION else "0"
        out.append(f'<g opacity="{base}">'
                   f'<animate attributeName="opacity" values="{values}" keyTimes="{keytimes}"'
                   f' dur="{CYCLE}" calcMode="discrete" repeatCount="indefinite"/>'
                   f'{drawing}</g>')
    return "".join(out)


def placed(markup: str, x: int, y: int, size: int) -> str:
    """Put the octopus into the scene as a transformed group.

    Not as a nested <svg>, which is valid and which browsers honour -- but Qt's renderer draws
    nothing for it, so the first version of this picture was a pot and some sparkles with an
    invisible octopus beside them. Unwrapping his drawing into a <g> works everywhere, and the
    scale comes from his own viewBox rather than from a guess."""
    box = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', markup)
    if not box:
        raise SystemExit("GeekOc's SVG has no viewBox to place him by")
    inner = re.sub(r"^<svg\b[^>]*>", "", markup.strip(), count=1)
    inner = re.sub(r"</svg>\s*$", "", inner)
    k = size / float(box.group(1))
    return f'<g transform="translate({x},{y}) scale({k:.4f})">{inner}</g>'


CYCLE = "21s"            # a word needs time to be read, and there are four of them now

# The cycle, as fractions of it. The stem has to REACH its height before a leaf opens, or a leaf
# hangs in the air above a stem that has not got there yet -- which is exactly what it was doing.
RISE_END = 0.20          # the stem is at full height here, carrying its leaves still folded
HOLD_END = 0.95          # it stays grown for most of the cycle, then folds away

# Each leaf opens, and the word it stands for takes the place of the one before it. The leaves are
# spread much further apart than the growing alone needed, because the pace is set by reading rather
# than by the plant: four words a third of a second apart would be a flicker, not a sentence.
LEAVES = [  # (opens, finished opening)
    (0.23, 0.29),
    (0.35, 0.41),
    (0.47, 0.53),
    (0.59, 0.65),
]
# A colour each, every one of them measured against BOTH a white README and a dark one -- large bold
# text, so 3:1 is the bar. The pretty versions fail it: the leaf teal sits at 2.51 on white and the
# glasses blue at 2.97, which is the same mistake the suckers made, so these are the deepened ones.
WORDS = [   # (the word, when it fades in, when it fades out, its colour)
    ("skills",        0.24, 0.37, "#0f9880"),   # the leaf teal, deepened until white can hold it
    ("knowledge",     0.36, 0.49, "#7a5cff"),   # the brand purple
    ("collaboration", 0.48, 0.61, "#d94fb0"),   # pink, the third hue the badge carries
    # funding and scholarships, which is what 🎯 Chances is for -- and the colour money has
    ("opportunity",   0.60, 0.78, "#c06a12"),
]
WORD_AT = (800, 240)     # while it is animating, all four share this spot and take turns in it
# ...and where they sit when it is NOT animating: a list, so a still of this file is a finished
# picture rather than four words printed on top of each other.
STACKED = [174, 220, 266, 312]

# ...and the last thing to arrive is the name: "my" and the last "y" in light blue, the G and the K
# black and bold, the "ee" in dark gold. Only the G and the K are bold.
#
# Black disappears on a dark README and light blue disappears on a white one, so the first attempt
# swapped both with a `prefers-color-scheme` rule inside the file. THAT WAS WRONG, and how it is
# wrong is worth keeping: prefers-color-scheme follows the OPERATING SYSTEM, not the theme GitHub is
# set to. A reader whose computer is dark but whose GitHub is light -- an ordinary combination, and
# the one it was caught on -- got the dark-mode colours on a white page: white letters on white.
#
# So the colours are fixed, and legibility comes from a HALO instead. Every letter is stroked in
# white underneath its own fill (`paint-order="stroke"`), which on a white page is invisible and on
# a dark one outlines the letters so they read anyway. One file, and nothing depending on anybody's
# settings.
NAME_ON, NAME_OFF = 0.82, 0.98
NAME_GOLD = "#b87b12"            # the same dark gold as his suckers
NAME_INK = "#12101c"             # the black of the G and the K
NAME_SKY = "#5cc6f5"             # the light blue, off his glasses
NAME_HALO = "#ffffff"
NAME_HALO_W = 7


def scaled(inner: str, ox: float, oy: float, values: str, keytimes: str, splines: str) -> str:
    """Scale something about its own root, on the one shared clock.

    The scaling nests translate -> scale -> translate-back rather than using a CSS transform-origin,
    so the path data stays in the picture's own coordinates and behaves the same in a browser, in a
    Markdown preview and in Qt. Everything is keyed to the SAME `dur`, with no `begin` offsets, so
    the parts cannot drift out of step with each other however long the page has been open."""
    return (f'<g transform="translate({ox},{oy})">'
            f'<g><animateTransform attributeName="transform" type="scale"'
            f' values="{values}" keyTimes="{keytimes}" dur="{CYCLE}"'
            f' calcMode="spline" keySplines="{splines}" repeatCount="indefinite"/>'
            f'<g transform="translate({-ox},{-oy})">{inner}</g></g></g>')


def leaf(d: str, fill: str, ox: float, oy: float, order: float) -> str:
    """A leaf that rides up with the stem folded, and opens once the stem has arrived.

    `order` picks its moment from LEAVES, and the fold is 0.3 rather than 0 because a leaf is a small
    leaf while it travels, not nothing -- "the stem should have leaves small, and then the small
    leaves grow"."""
    open_at, done_at = LEAVES[int(order)]
    return scaled(f'<path d="{d}" fill="{fill}"/>', ox, oy,
                  values="0.3 0.3;0.3 0.3;1 1;1 1",
                  keytimes=f"0;{open_at:.3f};{done_at:.3f};1",
                  splines="0 0 1 1;.2 .8 .3 1;0 0 1 1")


def words() -> str:
    """One word per leaf, each taking the place of the one before it.

    They share a single spot rather than stacking: the picture says *skills*, then *knowledge*, then
    *collaboration*, and what is left at the end is the plant rather than a list. A word fades in as
    its leaf opens, so the two read as the same event.

    The base state -- what anything that ignores animation draws -- is nothing at all, because three
    words sharing one position would otherwise print on top of each other."""
    out = []
    for i, (text, on, off, colour) in enumerate(WORDS):
        last = i == len(WORDS) - 1
        fade = 0.035
        out.append(
            # THE BASE STATE IS THE FALLBACK, and it has to be a finished picture rather than the
            # wreckage of an unplayed animation: every word visible, stacked into a list so they do
            # not sit on top of each other. An animation REPLACES both of these, so when it does run
            # all four come back to the one shared spot and take turns there. If it never runs --
            # GitHub refusing the file, a reader that strips SMIL, a thumbnail -- what shows is the
            # grown plant with all four words beside it, and no name.
            f'<text x="{WORD_AT[0]}" y="{WORD_AT[1]}" text-anchor="middle" opacity="1"'
            f' transform="translate(0,{STACKED[i] - WORD_AT[1]})"'
            f' font-family="Segoe UI,Helvetica Neue,Helvetica,Arial,sans-serif"'
            f' font-size="34" font-weight="700" fill="{colour}">{text}'
            f'<animate attributeName="opacity" values="0;0;1;1;0;0"'
            f' keyTimes="0;{on:.3f};{on + fade:.3f};{off - fade:.3f};{off:.3f};1"'
            f' dur="{CYCLE}" calcMode="spline"'
            f' keySplines="0 0 1 1;.3 .7 .4 1;0 0 1 1;.4 0 .7 .3;0 0 1 1"'
            f' repeatCount="indefinite"/>'
            # the word it belongs to rises a little as it arrives, so it does not merely blink on
            f'<animateTransform attributeName="transform" type="translate"'
            f' values="0 14;0 14;0 0;0 0;0 {"0" if last else "-10"};0 {"0" if last else "-10"}"'
            f' keyTimes="0;{on:.3f};{on + fade * 2:.3f};{off - fade:.3f};{off:.3f};1"'
            f' dur="{CYCLE}" calcMode="spline"'
            f' keySplines="0 0 1 1;.2 .8 .3 1;0 0 1 1;.4 0 .7 .3;0 0 1 1"'
            f' repeatCount="indefinite"/></text>')
    return "".join(out)


def spark(x: float, y: float, r: float, order: float) -> str:
    """A four-pointed glint, arriving after the leaves have opened.

    The glints are what turn "a plant" into "it just did that". They are late on purpose: a sparkle
    before the thing it is celebrating reads as decoration."""
    at = LEAVES[-1][1] + 0.02 + order * 0.03      # after the last leaf has opened
    path = (f'<path d="M{x} {y - r}C{x + r * .18} {y - r * .22} {x + r * .22} {y - r * .18} {x + r} {y}'
            f'C{x + r * .22} {y + r * .18} {x + r * .18} {y + r * .22} {x} {y + r}'
            f'C{x - r * .18} {y + r * .22} {x - r * .22} {y + r * .18} {x - r} {y}'
            f'C{x - r * .22} {y - r * .18} {x - r * .18} {y - r * .22} {x} {y - r}Z" fill="{SPARK}">'
            f'<animate attributeName="opacity" values="1;0.4;1;0.55;1" dur="2.6s"'
            f' repeatCount="indefinite"/></path>')
    return scaled(path, x, y,
                  values=f"0 0;0 0;1 1;1 1;0 0",
                  keytimes=f"0;{at:.3f};{at + 0.04:.3f};{HOLD_END};1",
                  splines=".2 .8 .3 1;.2 .9 .3 1;0 0 1 1;.7 0 .9 .4")


def name() -> str:
    """The last thing to arrive: the badge, where the words were.

    It takes the place of `opportunity` rather than sitting somewhere else, so the sequence reads as
    one sentence ending in who said it -- skills, knowledge, collaboration, opportunity, myGeeKy.

    THIS IS THE REAL MARK, docs/logo.png, not the name typeset here. Setting it in type was wrong
    twice over. A README SVG cannot carry a typeface -- it gets whatever the reader's machine has,
    which is a different drawing of the name on every computer -- and the colours then have to survive
    both a white page and a dark one, which is what the whole halo apparatus was for. The badge solves
    both by being a picture: it brings its own letterforms and its own dark disc, so it is the same
    mark everywhere and legible on any background without a single trick.

    It is embedded rather than linked because a README image is fetched through GitHub's proxy and an
    SVG rendered as an image may not load anything external. WebP at this size costs about 19 KB."""
    size = 210
    x, y = WORD_AT[0] - size // 2, WORD_AT[1] - size // 2
    img = (f'<image x="{x}" y="{y}" width="{size}" height="{size}"'
           # `xlink:href` alone, not both spellings: every current browser still honours it, older
           # ones need it, and carrying the same 19 KB payload twice is 19 KB for nothing
           f' xlink:href="{_badge_uri()}"/>')
    snap = 0.02
    # it comes up to size rather than simply appearing, which is what makes a mark LAND
    popped = scaled(img, WORD_AT[0], WORD_AT[1],
                    values="0.74 0.74;0.74 0.74;1 1;1 1",
                    keytimes=f"0;{NAME_ON:.3f};{NAME_ON + snap * 2:.3f};1",
                    splines="0 0 1 1;.2 .9 .3 1;0 0 1 1")
    return (f'<g opacity="0">'
            f'<animate attributeName="opacity" values="0;0;1;1;0;0"'
            f' keyTimes="0;{NAME_ON:.3f};{NAME_ON + snap:.3f};'
            f'{NAME_OFF - snap:.3f};{NAME_OFF:.3f};1"'
            f' dur="{CYCLE}" calcMode="spline"'
            f' keySplines="0 0 1 1;.3 .7 .4 1;0 0 1 1;.4 0 .7 .3;0 0 1 1" repeatCount="indefinite"/>'
            f'{popped}</g>')


def _badge_uri(_cache: list[str] = []) -> str:
    """The round myGeeKy badge, as a data URI. Read once and reused for both href spellings."""
    if _cache:
        return _cache[0]
    import base64
    import io

    from PIL import Image

    src = Path(__file__).parent / "logo.png"
    if not src.exists():
        raise SystemExit(f"the badge is missing: {src}")
    buf = io.BytesIO()
    Image.open(src).convert("RGBA").resize((256, 256), Image.LANCZOS).save(
        buf, "WEBP", quality=88, method=6)
    _cache.append("data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode())
    return _cache[0]


def plant() -> str:
    """The pot, then everything that grows out of it.

    The stem and its leaves are ONE group rising from the soil line, so the leaves travel up with the
    stem instead of waiting in mid-air for it: that was the bug you could see. Only once the stem is
    at its full height do the leaves open, bottom first."""
    SOIL = (588, 336)
    out = [f'<g stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round" stroke-linecap="round">']
    # the pot does not grow: it is the thing everything else grows out of
    out.append(f'<path d="M506 332 L664 332 L646 420 Q585 434 524 420 Z" fill="{POT}"/>')
    out.append(f'<path d="M506 332 L664 332 L658 358 Q585 372 512 358 Z" fill="{POT_DEEP}"/>')

    # A fourth word needs a fourth leaf: every word in this picture rides one, and an `opportunity`
    # with nothing under it would be the only one that is just text. So the stem is taller and the
    # four alternate up it, each a little larger than the one below.
    stem = (f'<path d="M588 334 C585 296 574 252 582 178" fill="none" stroke="{STEM}"'
            f' stroke-width="15"/>')
    leaves = "".join([
        leaf("M585 320 C551 320 529 302 530 278 C562 278 584 300 585 320Z", LEAF_DEEP, 585, 320, 0),
        leaf("M583 282 C623 282 652 260 650 232 C610 234 581 258 583 282Z", LEAF, 583, 284, 1),
        leaf("M580 240 C538 238 512 212 514 180 C556 184 582 212 580 240Z", LEAF, 580, 242, 2),
        leaf("M582 196 C628 192 660 162 656 126 C610 132 578 162 582 196Z", LEAF, 582, 198, 3),
    ])
    # the stem and its leaves rise together, out of the soil
    out.append(scaled(stem + leaves, *SOIL,
                      values="0 0;1 1;1 1;0 0",
                      keytimes=f"0;{RISE_END};{HOLD_END};1",
                      splines=".25 .7 .35 1;0 0 1 1;.7 0 .9 .4"))
    out.append('</g>')
    out.append(spark(686, 104, 20, 0))
    out.append(spark(504, 128, 15, 1))
    # the first two glints sit INSIDE the jar, which is a gift rather than a clash -- a plant
    # sparkling under glass. The third used to be at (614, 46), where the cloche's knob now is.
    out.append(spark(740, 96, 14, 2))
    return (chr(10) + "  ").join(out)


# The glass cloche: a bell jar that comes down over the grown plant and stands for PROTECTION --
# the thing myGeeKy does that nobody sees, around work that is still small enough to be knocked over.
#
# It arrives LAST of the plant's events, after every leaf has opened: a cover put over something
# already growing reads as protecting it, where a cover there from the start would read as a cage.
#
# Glass is drawn, not simulated. What makes a shape read as glass at thumbnail size is three things
# together -- a pale fill you can see the plant THROUGH, one hard bright streak across it, and the
# same ink outline every other shape here carries. A gradient would be prettier and Qt's renderer
# handles them unevenly, so this is flat fill plus fill-opacity, which looks the same everywhere.
GLASS = "#dff1ff"
GLASS_ON, GLASS_DOWN = 0.68, 0.74      # it starts down after the last leaf, and settles
GLASS_UP = 0.93                        # and lifts away just before the plant folds


def cloche() -> str:
    """The bell jar, descending.

    Its base state -- what a reader that ignores animation draws -- is DOWN and visible, like the
    words: the fallback picture is the grown plant with all four words and the glass over it.

    Two measurements set its shape, and both were got wrong first time round. It has to STAND ON the
    pot -- a jar wider than the pot it covers has its walls hanging in mid-air beside it -- so the
    walls come down at x=492 and x=678, inside the pot's 506..664 rim. And it has to CLEAR the widest
    leaf, which reaches x=656 at y=126: the walls therefore stay straight until y=180 and the dome
    turns in high, which puts the glass about fourteen units clear of the leaf tip at its tightest."""
    body = "M492 338 L492 180 C492 96 540 48 585 48 C630 48 678 96 678 180 L678 338 Z"
    out = [f'<g stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round" stroke-linecap="round">',
           # the glass itself: pale, and transparent enough that the leaves read straight through it
           f'<path d="{body}" fill="{GLASS}" fill-opacity="0.3"/>',
           # the streak, which is the whole trick -- without it this is a pale balloon
           f'<path d="M518 318 L518 182 C518 132 538 96 566 78" fill="none" stroke="#ffffff"'
           f' stroke-opacity="0.85" stroke-width="13"/>',
           f'<path d="M548 322 L548 190" fill="none" stroke="#ffffff" stroke-opacity="0.55"'
           f' stroke-width="7"/>',
           # the rim it stands on, and the knob you lift it by
           f'<path d="M492 338 L678 338" fill="none"/>',
           f'<path d="M562 50 Q585 18 608 50 Z" fill="{GLASS}" fill-opacity="0.55"/>',
           f'<circle cx="585" cy="26" r="15" fill="{POT}"/>',
           '</g>']
    inner = "".join(out)
    snap = 0.015
    # down from above the frame, overshooting nothing: glass is heavy, so it settles rather than bounces
    return (f'<g opacity="1">'
            f'<animate attributeName="opacity" values="0;0;1;1;0;0"'
            f' keyTimes="0;{GLASS_ON:.3f};{GLASS_ON + snap:.3f};'
            f'{GLASS_UP - snap:.3f};{GLASS_UP:.3f};1"'
            f' dur="{CYCLE}" calcMode="spline"'
            f' keySplines="0 0 1 1;.3 .7 .4 1;0 0 1 1;.4 0 .7 .3;0 0 1 1" repeatCount="indefinite"/>'
            f'<g transform="translate(0,0)">'
            f'<animateTransform attributeName="transform" type="translate"'
            f' values="0 -400;0 -400;0 0;0 0;0 -400;0 -400"'
            f' keyTimes="0;{GLASS_ON:.3f};{GLASS_DOWN:.3f};'
            f'{GLASS_UP - snap:.3f};{GLASS_UP:.3f};1"'
            f' dur="{CYCLE}" calcMode="spline"'
            f' keySplines="0 0 1 1;.25 .7 .3 1;0 0 1 1;.5 0 .8 .4;0 0 1 1" repeatCount="indefinite"/>'
            f'{inner}</g></g>')


def scene() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" \
viewBox="0 0 {W} {H}" width="{W}" height="{H}" \
role="img" aria-label="GeekOc, the myGeeKy octopus, watching a plant grow skills, knowledge, \
collaboration and opportunity, with a glass cloche coming down over it to keep it safe">
  <title>GeekOc watching a plant grow, safe under glass</title>
  <g><animateTransform attributeName="transform" type="translate" values="0 0;0 -9;0 0;0 -4;0 0"
       keyTimes="0;0.25;0.5;0.75;1" dur="3.6s" calcMode="spline"
       keySplines=".4 0 .6 1;.4 0 .6 1;.4 0 .6 1;.4 0 .6 1" repeatCount="indefinite"/>
    {reacting(6, 2, 440)}</g>
  {plant()}
  {cloche()}
  {words()}
  {name()}
</svg>
"""


def main() -> int:
    OUT_SVG.parent.mkdir(parents=True, exist_ok=True)
    OUT_SVG.write_text(scene(), encoding="utf-8")
    print(f"  {OUT_SVG}  ({OUT_SVG.stat().st_size // 1024} KB)")

    # a PNG beside it: proof that what was written is readable as a picture, and a fallback anywhere
    # an SVG is not welcome
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import QByteArray, Qt
        from PySide6.QtGui import QGuiApplication, QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
    except ImportError:
        print("  (Qt not here: no PNG written, and the SVG was not checked)")
        return 0

    # Qt will rasterise shapes with no application object, but the moment it has to touch a FONT --
    # which this picture now does, because it has words in it -- it kills the process outright: exit
    # 127, no message, no traceback. One of these first, and it is fine.
    app = QGuiApplication.instance() or QGuiApplication([])
    # The still is rendered from a copy with every animation element STRIPPED OUT, not from the
    # animated file. Qt applies an animation's first keyframe and stops there, and the first keyframe
    # of a thing that grows is nothing -- so rasterising the real file gave a picture of an empty
    # pot. Without the animations the groups keep their own transforms, which are the grown ones.
    still = re.sub(r"<animate(?:Transform)?\b[^>]*/>", "", OUT_SVG.read_text(encoding="utf-8"))
    # ...and with the words taken out of it as well, to be drawn back in below with a real font.
    # Offscreen Qt has no font at all here: it draws every letter as an empty box, which would have
    # made the fallback picture -- the one that exists for when the animation does NOT play -- a row
    # of little squares. The shapes it rasterises perfectly well; the type it cannot.
    still = re.sub(r"<text\b.*?</text>", "", still, flags=re.S)
    # ...and the badge with them. The still deliberately has no mark on it -- that is the one thing
    # that only happens at the end of a performance -- and Qt's WebP support is a plugin that may or
    # may not be installed, so carrying it here would risk a grey box in the fallback picture.
    still = re.sub(r"<image\b[^>]*/>", "", still)
    renderer = QSvgRenderer(QByteArray(still.encode("utf-8")))
    if not renderer.isValid():
        raise SystemExit("the SVG this wrote is not readable")
    image = QImage(W * 2, H * 2, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    png = OUT_SVG.with_suffix(".png")
    image.save(str(png))
    _write_the_words_on(png)
    print(f"  {png}  ({png.stat().st_size // 1024} KB)")
    return 0


def _write_the_words_on(png: Path) -> None:
    """Draw the four words onto the still with a font that exists, in their own colours.

    The PNG is the picture for anywhere the animated SVG does not play, so it has to say the same
    thing the animation says: the plant, and all four words beside it. The name is deliberately NOT
    here -- it is the one thing that only happens at the end of a performance."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  (Pillow not here: the still has no words on it)")
        return
    face = next((c for c in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf")
                 if Path(f"C:/Windows/Fonts/{c}").exists()), None)
    if face is None:
        print("  (no bold font found: the still has no words on it)")
        return
    sheet = Image.open(png).convert("RGBA")
    draw = ImageDraw.Draw(sheet)
    # Each word is SHRUNK TO FIT rather than drawn at the size the SVG asks for. Whatever font this
    # machine has is not the one a browser picks, and the difference showed: `collaboration` at the
    # nominal size ran off the right edge of the picture here while fitting comfortably in the SVG.
    # The room is what is left between the glass and the edge, with a margin either side.
    # Centred on WORD_AT, it may reach neither the picture's edge nor the glass at x=678.
    room = 2 * 2 * min(W - 24 - WORD_AT[0], WORD_AT[0] - 686)
    for (text, _on, _off, colour), y in zip(WORDS, STACKED):
        size = 34 * 2
        while size > 20:
            font = ImageFont.truetype(f"C:/Windows/Fonts/{face}", size)
            if draw.textlength(text, font=font) <= room:
                break
            size -= 2
        draw.text((WORD_AT[0] * 2, y * 2), text, font=font, fill=colour, anchor="ms")
    sheet.save(png)


if __name__ == "__main__":
    sys.exit(main())
