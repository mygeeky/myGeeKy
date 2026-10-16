"""Pictures of GeekOc, from the one rig that defines him.

    python docs/make_geekoc.py                      the standard set, into docs/geekoc/
    python docs/make_geekoc.py --list               the poses and faces that exist
    python docs/make_geekoc.py --pose wave --face excited --size 840 --out he.png

GeekOc lives in `website/geekoc/geekoc.js` and nowhere else: 9 poses, 10 faces, arms that are
simulated rather than drawn. Everything that needs a picture of him -- the README, the poster, the
desktop setup window, the phone -- is not JavaScript, so this bridges the two:

    node  ->  GeekOc.svg({pose, face, size})  ->  SVG  ->  Qt QSvgRenderer  ->  PNG

Qt is already a dependency of the panel, so this adds nothing to install. Node is needed only to
make the pictures, never to use them.

Why this is a script and not a folder of saved images: a picture saved by hand drifts from the rig
the moment the rig changes, and then GeekOc looks slightly different in the README than in the app.
Run this again instead.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "website" / "geekoc" / "geekoc.js"
OUT_DIR = Path(__file__).parent / "geekoc"

# The standard set. Each entry says what the picture is FOR, because a pose chosen for a reason
# survives someone later wondering whether it can be swapped.
STANDARD = [
    ("hero",     "wave",    "excited",  "the README's first picture: GeekOc says hello"),
    ("chances",  "point",   "proud",    "jobs, funding, conferences -- he points at what he found"),
    ("grow",     "think",   "thinking", "what you are learning, and what to learn next"),
    ("quiz",     "cheer",   "excited",  "the quiz: learning by answering"),
    ("people",   "present", "happy",    "people worth working with"),
    ("privacy",  "idle",    "shy",      "it stays on your computer: nothing to boast about"),
    ("swim",     "swim",    "curious",  "the website and anywhere he is moving"),
    ("sleep",    "sleep",   "sleepy",   "nothing waiting for you right now"),
]

SIZE = 840          # the pixel size written; everything else scales down from it cleanly


def engine_names() -> dict[str, list[str]]:
    """The poses and faces the rig actually has.

    Worth asking rather than assuming: `GeekOc.svg` accepts an unknown pose without complaint and
    quietly draws the default one, so a typo produces a picture that looks fine and is wrong."""
    said = _node("require(process.env.GEEKOC); const G = globalThis.GeekOc;"
                 "console.log(JSON.stringify({poses: Object.keys(G.POSES),"
                 " faces: Object.keys(G.FACES), moves: Object.keys(G.MOVES)}));")
    return json.loads(said)


def _node(script: str, **env_extra: str) -> str:
    env = {**os.environ, "GEEKOC": str(ENGINE), **env_extra}
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=180, env=env)
    if r.returncode != 0:
        tail = "\n".join((r.stderr or "").strip().splitlines()[-4:])
        raise SystemExit(f"node could not run the GeekOc engine:\n{tail}")
    return r.stdout


def svg(pose: str, face: str, size: int = 400, t: float = 1.4) -> str:
    """One still of GeekOc, as SVG."""
    return _node(
        "require(process.env.GEEKOC); const G = globalThis.GeekOc;"
        "process.stdout.write(G.svg({pose: process.env.POSE, face: process.env.FACE,"
        " t: Number(process.env.T), still: true, size: Number(process.env.SIZE)}));",
        POSE=pose, FACE=face, SIZE=str(size), T=str(t))


def png(markup: str, out: Path, px: int = SIZE) -> Path:
    """Rasterise with Qt, on a transparent background."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")     # no screen needed, and none assumed
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(markup.encode("utf-8")))
    if not renderer.isValid():
        raise SystemExit(f"Qt could not read the SVG for {out.name}")
    image = QImage(px, px, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    out.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(out)):
        raise SystemExit(f"could not write {out}")
    return out


def check(pose: str, face: str, names: dict[str, list[str]]) -> None:
    if pose not in names["poses"]:
        raise SystemExit(f"no such pose: {pose!r}\nthe rig has: {', '.join(names['poses'])}")
    if face not in names["faces"]:
        raise SystemExit(f"no such face: {face!r}\nthe rig has: {', '.join(names['faces'])}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render GeekOc to PNG.")
    ap.add_argument("--list", action="store_true", help="say which poses and faces exist")
    ap.add_argument("--pose")
    ap.add_argument("--face")
    ap.add_argument("--size", type=int, default=SIZE)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    names = engine_names()
    if args.list:
        for kind in ("poses", "faces", "moves"):
            print(f"{kind:>6}: {', '.join(names[kind])}")
        return 0

    if args.pose or args.face:
        pose, face = args.pose or "idle", args.face or "happy"
        check(pose, face, names)
        out = args.out or (OUT_DIR / f"geekoc-{pose}-{face}.png")
        png(svg(pose, face, size=max(200, args.size // 2)), out, px=args.size)
        print(f"  {out}")
        return 0

    written = []
    for name, pose, face, why in STANDARD:
        check(pose, face, names)
        out = png(svg(pose, face, size=SIZE // 2), OUT_DIR / f"geekoc-{name}.png", px=SIZE)
        written.append(out)
        print(f"  {out.name:<22} {pose:<8} {face:<9} {why}")
    # Two identical files mean a pose silently fell back to the default, which is the one failure
    # this script can have while looking like it worked.
    seen: dict[bytes, str] = {}
    for out in written:
        blob = out.read_bytes()
        if blob in seen:
            raise SystemExit(f"{out.name} is identical to {seen[blob]}: a pose did not take effect")
        seen[blob] = out.name
    print(f"\n{len(written)} pictures in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
