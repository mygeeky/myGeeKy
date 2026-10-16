"""The one who works alone, and the others out there: the picture beside "For anyone who works alone".

    python docs/make_alone_scene.py     ->  docs/geekoc/works-alone.svg (and a .png beside it)

Drawn in GeekOc's hand -- his ink colour, his outline weight, his palette -- for the same reason the plant
is: a figure drawn in a different hand reads as clip art sitting next to him.

THE KID IS SEEN FROM BEHIND, and that is the whole design. This picture has to be *anyone* who is the only
one in their building who does this -- any country, any age past about fifteen, any gender. A face cannot do
that; it is always somebody in particular, and every reader who is not that person is quietly told the
picture is not about them. From behind, the reader is looking at their own back.

Nothing in it is animated. The section it belongs to is about quiet, and a picture that moves while somebody
reads is the opposite of that.
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
OUT_SVG = Path(__file__).parent / "geekoc" / "works-alone.svg"

W, H = 820, 430
# ...and what is actually SHOWN. The drawing sits in the lower two thirds of the space it was laid out in,
# and a picture that stands beside a list has to be wide and short rather than tall with a field of nothing
# above it. Cropping with the viewBox keeps every coordinate below unchanged.
VIEW = (0, 150, 820, 268)

INK = "#2b1053"          # the outline every shape of his carries
OW = 7                   # and its weight
HOOD = "#7a5cff"         # the brand purple: the kid's hoodie
HOOD_DEEP = "#5b3fd6"    # its shadow side
DESK = "#ffc457"         # the same gold as his belly
DESK_DEEP = "#e8a93a"
SCREEN = "#7fd8ff"       # the glow off the laptop, and the thread between people
FAR = "#b9a9ff"          # the others, further away: the same purple, stepped back
GLOW = "#fff3c9"

# The others stand where they are because of how far away they feel, not where they fit: one close enough to
# reach, one further, one nearly off the edge. All three are the same size -- shrinking them would say they
# matter less, when what the picture means is that they are simply elsewhere.
OTHERS = [(606, 232), (700, 190), (766, 262)]


def geekoc(size: int, pose: str, face: dict, ident: str) -> str:
    """One drawing of the octopus, out of the rig in website/geekoc/geekoc.js."""
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


def placed(markup: str, x: int, y: int, size: int) -> str:
    """Put him into the scene as a transformed group -- never a nested <svg>, which Qt draws as nothing."""
    box = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', markup)
    if not box:
        raise SystemExit("GeekOc's SVG has no viewBox to place him by")
    inner = re.sub(r"^<svg\b[^>]*>", "", markup.strip(), count=1)
    inner = re.sub(r"</svg>\s*$", "", inner)
    k = size / float(box.group(1))
    return f'<g transform="translate({x},{y}) scale({k:.4f})">{inner}</g>'


def desk() -> str:
    """The desk, drawn BEHIND the kid: they are nearer the reader than it is."""
    return f"""
  <g stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round" stroke-linecap="round">
    <path d="M96 336 L128 404" fill="none"/>
    <path d="M430 336 L398 404" fill="none"/>
    <path d="M74 318 L452 318 L452 338 L74 338 Z" fill="{DESK}"/>
    <path d="M74 332 L452 332 L452 338 L74 338 Z" fill="{DESK_DEEP}" stroke="none"/>
  </g>"""


def laptop() -> str:
    """The light the whole picture is lit by, open away from the reader."""
    return f"""
  <g stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round" stroke-linecap="round">
    <path d="M316 316 L326 212 L420 204 L424 312 Z" fill="{SCREEN}"/>
    <path d="M326 226 L412 219" fill="none" stroke="#ffffff" stroke-width="6" opacity="0.6"/>
    <path d="M330 248 L386 243" fill="none" stroke="#ffffff" stroke-width="6" opacity="0.45"/>
  </g>"""


def kid() -> str:
    """Seen from behind, and built out of exactly the same two shapes as the others: a round head and a
    dome of shoulders.

    That rhyme is the point of the picture. The one at the desk and the three further off are the same
    drawing at different sizes -- so the reader is not a different KIND of thing from the people myGeeKy is
    offering to find. Earlier attempts gave the kid a hood, a neck and an arm and they stopped reading as a
    person at all: at this size, detail is noise and silhouette is everything.

    Drawn AFTER the laptop, so they sit in front of its light rather than beside it."""
    x, y, r = 238, 232, 48
    return f"""
  <g stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round" stroke-linecap="round">
    <circle cx="{x}" cy="{y}" r="{r}" fill="{HOOD}"/>
    <path d="M{x - 92} 372 C{x - 88} 314 {x - 50} 288 {x} 288
             C{x + 50} 288 {x + 88} 314 {x + 92} 372 Z" fill="{HOOD}"/>
    <path d="M{x + 28} 294 C{x + 66} 306 {x + 88} 330 {x + 92} 372 L{x + 52} 372
             C{x + 48} 330 {x + 40} 306 {x + 20} 296 Z" fill="{HOOD_DEEP}" stroke="none"/>
  </g>"""


def others() -> str:
    """Three people, further off, each joined to the desk by a thread.

    They are smaller and paler because they are further away, and that is all it means. The threads are
    DASHED because nothing has been sent yet: a connection that could exist, which is the honest version of
    what myGeeKy offers. A solid line would say it has already happened."""
    out = []
    for x, y in OTHERS:
        out.append(f"""
  <g stroke="{INK}" stroke-width="6" stroke-linejoin="round" stroke-linecap="round" opacity="0.62">
    <circle cx="{x}" cy="{y}" r="22" fill="{FAR}"/>
    <path d="M{x - 34} {y + 72} C{x - 32} {y + 34} {x - 18} {y + 22} {x} {y + 22}
             C{x + 18} {y + 22} {x + 32} {y + 34} {x + 34} {y + 72} Z" fill="{FAR}"/>
  </g>""")
    for x, y in OTHERS:
        out.append(f'<path d="M424 250 C{(424 + x) / 2} {y - 50} {(424 + x) / 2} {y + 14} {x - 26} {y + 6}"'
                   f' fill="none" stroke="{SCREEN}" stroke-width="5" stroke-linecap="round"'
                   f' stroke-dasharray="2 16" opacity="0.85"/>')
    return "".join(out)


def scene() -> str:
    # He looks LEFT here, back at the kid, not out of the picture: he is showing them the others, and a
    # character gazing out of a drawing while pointing into it is what makes an illustration feel wrong.
    him = geekoc(190, "point", {"mouth": "smile", "brow": 0.5, "lids": 0.1, "look": [-1.5, 0.1]}, "a0")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VIEW[0]} {VIEW[1]} {VIEW[2]} {VIEW[3]}" width="{VIEW[2]}" height="{VIEW[3]}" \
role="img" aria-label="Someone working alone at a desk, seen from behind, with three other people further \
away joined to them by dotted threads, and GeekOc beside them">
  <title>The one who works alone, and the others out there</title>
  <ellipse cx="320" cy="292" rx="186" ry="118" fill="{GLOW}" opacity="0.42"/>
  {others()}
  {desk()}
  {laptop()}
  {kid()}
  {placed(him, 426, 206, 190)}
</svg>
"""


def main() -> int:
    OUT_SVG.parent.mkdir(parents=True, exist_ok=True)
    OUT_SVG.write_text(scene(), encoding="utf-8")
    print(f"  {OUT_SVG}  ({OUT_SVG.stat().st_size // 1024} KB)")

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import QByteArray, Qt
        from PySide6.QtGui import QGuiApplication, QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
    except ImportError:
        print("  (Qt not here: no PNG written, and the SVG was not checked)")
        return 0
    QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(QByteArray(OUT_SVG.read_text(encoding="utf-8").encode("utf-8")))
    if not renderer.isValid():
        raise SystemExit("the SVG this wrote is not readable")
    image = QImage(VIEW[2] * 2, VIEW[3] * 2, QImage.Format_ARGB32)
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
