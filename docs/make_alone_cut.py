"""Cut the kid out of the poster, and let everything around him fade away.

    python docs/make_alone_cut.py     ->  docs/geekoc/alone.png

docs/character.jpg is a square poster: the name across the top, a tagline under it, a brick wall behind.
All of that is right on a poster and wrong beside a list -- the name is already the page's heading, and a
hard-edged rectangle of brick wall in the middle of a README reads as a photograph someone pasted in.

So this keeps the figure and dissolves the rest. No background is REMOVED, because the hoodie, the wall and
the shadow are all nearly the same dark and anything that cuts by colour eats the boy's shoulder. What it
does instead is fade: full strength over him, nothing at all at the edges, so he sits on the page instead
of in a box. Works on a white README and a dark one alike -- nothing is assumed about what is behind it.
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).parent / "character.jpg"
OUT = Path(__file__).parent / "geekoc" / "alone.png"

# The figure, measured in the poster's own 1200px square, PLUS a margin on every side. The margin is the
# whole trick: without room to fade into, the fade starts on his knees and dissolves the boy instead of the
# background. The title and tagline sit above this box and are simply not in it.
BOX = (120, 236, 1112, 1160)

SOLID = 0.66      # out to here he is untouched...
GONE = 1.00       # ...and by here there is nothing left


def main() -> int:
    try:
        from PIL import Image
    except ImportError:
        raise SystemExit("this needs Pillow: pip install pillow")
    im = Image.open(SRC).convert("RGBA").crop(BOX)
    w, h = im.size
    alpha = Image.new("L", (w, h))
    px = alpha.load()
    cx, cy = w / 2, h / 2
    for y in range(h):
        for x in range(w):
            # distance from the middle, as a fraction of the way to the edge, measured on an ellipse so a
            # tall picture fades at its top and bottom at the same time as at its sides
            r = (((x - cx) / cx) ** 2 + ((y - cy) / cy) ** 2) ** 0.5
            if r <= SOLID:
                px[x, y] = 255
            elif r >= GONE:
                px[x, y] = 0
            else:
                t = (r - SOLID) / (GONE - SOLID)
                px[x, y] = int(255 * (1 - t * t * (3 - 2 * t)))      # smoothstep, so the edge has no seam
    im.putalpha(alpha)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    im.save(OUT)
    print(f"  {OUT}  {im.size[0]}x{im.size[1]}  ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
