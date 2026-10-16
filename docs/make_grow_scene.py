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

W, H = 800, 440

# his palette, so the plant belongs to the same drawing
INK = "#2b1053"          # the outline every shape of his carries
OW = 7                   # and its weight
LEAF = "#35e0c1"
LEAF_DEEP = "#19b89b"
STEM = "#1f9c86"
POT = "#ffc457"          # the same gold as his belly and his suckers' band
POT_DEEP = "#e8a93a"
SPARK = "#ffc457"

# he is excited, and he is looking at the plant rather than at you
# `look` moves a pupil by only nine units inside an eye of thirty, so even a full 1.0 reads as
# "straight ahead with a thought". The engine does not clamp it, and the pupil is clipped to the eye
# anyway, so this scene asks for more than the faces do: his eyes are hard right, on the plant.
FACE = {"mouth": "open", "brow": 1.0, "lids": 0, "look": [1.8, -0.5]}


def geekoc(size: int) -> str:
    """The octopus, from the rig, as a nested <svg> ready to drop into a bigger picture."""
    js = """
      require(process.env.GEEKOC);
      const G = globalThis.GeekOc;
      G.FACES.__watching = JSON.parse(process.env.FACE);
      process.stdout.write(G.svg({ pose: 'cheer', face: '__watching', t: 1.4, still: true,
                                   size: Number(process.env.SIZE) }));
    """
    env = {**os.environ, "GEEKOC": str(ENGINE), "FACE": json.dumps(FACE), "SIZE": str(size)}
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=180, env=env)
    if r.returncode != 0:
        raise SystemExit("node could not draw GeekOc:\n" + (r.stderr or "")[-500:])
    return r.stdout.strip()


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


CYCLE = "13s"            # slow enough to watch: it was over before the eye had followed it

# The cycle, as fractions of it. The stem has to REACH its height before a leaf opens, or a leaf
# hangs in the air above a stem that has not got there yet -- which is exactly what it was doing.
RISE_END = 0.30          # the stem is at full height here, carrying its leaves still folded
OPEN_END = 0.46          # and here the leaves have opened
HOLD_END = 0.92          # it stays grown for most of the cycle, then folds away


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

    `order` staggers the opening from the bottom leaf to the top one. It starts at 0.3 rather than 0
    because a leaf is a small leaf while it travels, not nothing -- "the stem should have leaves
    small, and then the small leaves grow"."""
    open_at = RISE_END + 0.02 + order * 0.05
    done_at = min(open_at + 0.1, OPEN_END + order * 0.04)
    return scaled(f'<path d="{d}" fill="{fill}"/>', ox, oy,
                  values="0.3 0.3;0.3 0.3;1 1;1 1",
                  keytimes=f"0;{open_at:.3f};{done_at:.3f};1",
                  splines="0 0 1 1;.2 .8 .3 1;0 0 1 1")


def spark(x: float, y: float, r: float, order: float) -> str:
    """A four-pointed glint, arriving after the leaves have opened.

    The glints are what turn "a plant" into "it just did that". They are late on purpose: a sparkle
    before the thing it is celebrating reads as decoration."""
    at = OPEN_END + 0.03 + order * 0.035
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

    stem = (f'<path d="M588 334 C585 290 572 258 580 206" fill="none" stroke="{STEM}"'
            f' stroke-width="15"/>')
    leaves = "".join([
        leaf("M584 318 C546 316 526 294 528 268 C564 266 586 292 584 318Z", LEAF_DEEP, 584, 318, 0),
        leaf("M583 274 C629 272 656 240 650 208 C606 210 580 240 583 274Z", LEAF, 583, 276, 1),
        leaf("M580 224 C538 214 514 174 522 136 C570 146 590 186 580 224Z", LEAF, 580, 226, 2),
    ])
    # the stem and its leaves rise together, out of the soil
    out.append(scaled(stem + leaves, *SOIL,
                      values="0 0;1 1;1 1;0 0",
                      keytimes=f"0;{RISE_END};{HOLD_END};1",
                      splines=".25 .7 .35 1;0 0 1 1;.7 0 .9 .4"))
    out.append('</g>')
    out.append(spark(664, 132, 21, 0))
    out.append(spark(520, 92, 15, 1))
    out.append(spark(624, 60, 12, 2))
    return (chr(10) + "  ").join(out)


def scene() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" \
role="img" aria-label="GeekOc, the myGeeKy octopus, watching a plant grow">
  <title>GeekOc watching a plant grow</title>
  <g><animateTransform attributeName="transform" type="translate" values="0 0;0 -9;0 0;0 -4;0 0"
       keyTimes="0;0.25;0.5;0.75;1" dur="3.6s" calcMode="spline"
       keySplines=".4 0 .6 1;.4 0 .6 1;.4 0 .6 1;.4 0 .6 1" repeatCount="indefinite"/>
    {placed(geekoc(440), 6, 2, 440)}</g>
  {plant()}
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
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
    except ImportError:
        print("  (Qt not here: no PNG written, and the SVG was not checked)")
        return 0
    renderer = QSvgRenderer(QByteArray(OUT_SVG.read_bytes()))
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
    print(f"  {png}  ({png.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
