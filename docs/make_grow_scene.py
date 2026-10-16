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


def spark(x: float, y: float, r: float, start: float) -> str:
    """A four-pointed glint that pops after the leaf it belongs to, then twinkles.

    The glints are what turn "a plant" into "it just did that". They arrive late on purpose: a
    sparkle before the thing it is celebrating reads as decoration."""
    path = (f'<path d="M{x} {y - r}C{x + r * .18} {y - r * .22} {x + r * .22} {y - r * .18} {x + r} {y}'
            f'C{x + r * .22} {y + r * .18} {x + r * .18} {y + r * .22} {x} {y + r}'
            f'C{x - r * .18} {y + r * .22} {x - r * .22} {y + r * .18} {x - r} {y}'
            f'C{x - r * .22} {y - r * .18} {x - r * .18} {y - r * .22} {x} {y - r}Z" fill="{SPARK}">'
            f'<animate attributeName="opacity" values="1;0.45;1;0.6;1" keyTimes="0;0.2;0.45;0.7;1"'
            f' dur="2.2s" begin="{start}s" repeatCount="indefinite"/></path>')
    return grows(path, x, y, start=start, rise=0.08)


CYCLE = "7s"             # grow, hold, and away again, then round once more


def grows(inner: str, ox: float, oy: float, start: float, rise: float = 0.20) -> str:
    """Make something sprout from the point (ox, oy) and, at the end of the cycle, fold back into it.

    The scaling is done by nesting translate -> scale -> translate-back, rather than by a CSS
    transform-origin: the path data stays in the picture's own coordinates, and it behaves the same
    in a browser, in a Markdown preview and in Qt. A renderer that ignores animation altogether draws
    the base state, which is why that state is the FULL-GROWN one -- a still of this picture is a
    plant, not an empty pot."""
    return (f'<g transform="translate({ox},{oy})">'
            f'<g><animateTransform attributeName="transform" type="scale" additive="replace"'
            f' values="0 0;1 1;1 1;0 0" keyTimes="0;{rise};0.88;1" dur="{CYCLE}"'
            f' calcMode="spline"'
            f' keySplines=".2 .9 .3 1;0 0 1 1;.7 0 .9 .4"'
            f' begin="{start}s" repeatCount="indefinite"/>'
            f'<g transform="translate({-ox},{-oy})">{inner}</g></g></g>')


def plant() -> str:
    """The pot, the stem and three leaves -- each one bigger than the last, because the picture has to
    say *growing* and not merely *a plant*. Drawn with his outline so the two belong together.

    They come up in order, out of the soil line at the top of the pot, each one a little after the
    one below it. That stagger is the whole illusion: three things scaling at once reads as a picture
    being zoomed, and the same three a third of a second apart reads as something growing."""
    SOIL = (588, 336)
    out = [f'<g stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round" stroke-linecap="round">']
    # the pot does not grow: it is the thing everything else grows out of
    out.append(f'<path d="M506 332 L664 332 L646 420 Q585 434 524 420 Z" fill="{POT}"/>')
    out.append(f'<path d="M506 332 L664 332 L658 358 Q585 372 512 358 Z" fill="{POT_DEEP}"/>')
    # the stem, leaning the way it is growing
    out.append(grows(f'<path d="M588 334 C585 290 572 258 580 206" fill="none" stroke="{STEM}"'
                     f' stroke-width="15"/>', *SOIL, start=0.0, rise=0.30))
    # three leaves, smallest at the bottom: the eye reads that as time
    out.append(grows(f'<path d="M584 318 C546 316 526 294 528 268 C564 266 586 292 584 318Z"'
                     f' fill="{LEAF_DEEP}"/>', 584, 318, start=0.55))
    out.append(grows(f'<path d="M583 274 C629 272 656 240 650 208 C606 210 580 240 583 274Z"'
                     f' fill="{LEAF}"/>', 583, 276, start=1.15))
    out.append(grows(f'<path d="M580 224 C538 214 514 174 522 136 C570 146 590 186 580 224Z"'
                     f' fill="{LEAF}"/>', 580, 226, start=1.8))
    out.append('</g>')
    # and the glints, which are what make it *just happened* rather than *a plant in a pot*
    out.append(spark(664, 132, 21, start=2.3))
    out.append(spark(520, 92, 15, start=2.65))
    out.append(spark(624, 60, 12, start=2.95))
    return "\n  ".join(out)


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
