"""Take a generated character clip off its background, so he can stand anywhere in the video.

    python launch/video/cut_clip.py <clip.mp4> [name]

Writes into launch/video/intro/:
    <name>-cut.mov    the character on nothing (QuickTime RLE, which carries real alpha)
    <name>-cut.mp4    the same thing composited on the video's own dark, to watch and to check
    <name>-cut/       the frames as PNGs with alpha, which is what make_video.py actually reads

The clips come back from the generator as a figure standing on a flat pale wall. That wall cannot go into
the video -- a white rectangle in the middle of a dark film reads as a mistake -- so it has to come off.

TWO THINGS MAKE THAT HARDER THAN IT SOUNDS, and both cost an attempt:

  * His FACE is nearly as pale as the wall, so anything keying on brightness erases it. What actually
    separates them is not colour but connection -- the wall touches the frame's border and he does not --
    so the background is found by flood-filling in from the edges.

  * The LAPTOP LID is the same flat grey as the shadow pooled under his shoes. Removing that shadow by
    colour removes the laptop with it, so the shadow is only taken out of the bottom quarter of the
    figure, where nothing of his is ever that grey.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

OUT = Path(__file__).parent / "intro"
DARK = (18, 18, 28)          # make_video.py's BG, so the preview shows what the film will show

PALE = 228       # a pixel this bright and this grey may be wall...
FLAT = 16        # ...if it is also this close to colourless
SHADOW = 185     # the pooled shadow is paler than this
FLOOR = 0.72     # and lives below this much of the way down the figure


def alpha_cut(rgb: np.ndarray) -> np.ndarray:
    """The alpha channel for one frame: 0 where the wall is, 255 where he is."""
    pale = (rgb.min(axis=2) > PALE) & ((rgb.max(axis=2) - rgb.min(axis=2)) < FLAT)
    lab, _ = ndimage.label(pale)
    edge = {*lab[0].tolist(), *lab[-1].tolist(), *lab[:, 0].tolist(), *lab[:, -1].tolist()} - {0}
    alpha = np.where(np.isin(lab, list(edge)), 0, 255).astype(np.uint8)
    rows = np.where(alpha.max(axis=1) > 0)[0]
    if len(rows):
        floor = int(rows.min() + FLOOR * (rows.max() - rows.min()))
        grey = (rgb.min(axis=2) > SHADOW) & ((rgb.max(axis=2) - rgb.min(axis=2)) < 18)
        alpha[floor:][grey[floor:]] = 0
    return alpha


def cut(path: Path) -> Image.Image:
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(int)
    img = Image.fromarray(np.dstack([rgb.astype(np.uint8), alpha_cut(rgb)]), "RGBA")
    img.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(0.8)))   # no hard sawtooth edge
    return img


def main(argv: list[str]) -> int:
    if not argv:
        raise SystemExit(__doc__)
    src = Path(argv[0])
    if not src.exists():
        raise SystemExit(f"no such clip: {src}")
    name = argv[1] if len(argv) > 1 else src.stem
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    OUT.mkdir(parents=True, exist_ok=True)
    raw = OUT / f"{name}-raw"
    frames = OUT / f"{name}-cut"
    for d in (raw, frames):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)

    fps = probe_fps(ffmpeg, src)
    run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), str(raw / "f_%04d.png")])
    shots = sorted(raw.glob("*.png"))
    print(f"  {len(shots)} frames at {fps} fps")

    flat = Image.new("RGB", Image.open(shots[0]).size, DARK)
    for i, p in enumerate(shots, 1):
        img = cut(p)
        img.save(frames / p.name)
        Image.alpha_composite(flat.convert("RGBA"), img).convert("RGB").save(raw / f"dark_{i:04d}.png")
    print(f"  cut: {frames}")

    mov = OUT / f"{name}-cut.mov"      # qtrle is lossless and in every ffmpeg build; alpha survives it
    run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-framerate", str(fps),
         "-i", str(frames / "f_%04d.png"), "-c:v", "qtrle", "-pix_fmt", "argb", str(mov)])
    mp4 = OUT / f"{name}-cut.mp4"
    run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-framerate", str(fps),
         "-i", str(raw / "dark_%04d.png"), "-i", str(src), "-map", "0:v", "-map", "1:a?",
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-shortest", str(mp4)])
    for f in (mov, mp4):
        print(f"  {f}  ({f.stat().st_size // 1024} KB)")
    shutil.rmtree(raw, ignore_errors=True)
    return 0


def probe_fps(ffmpeg: str, src: Path) -> int:
    out = subprocess.run([ffmpeg, "-hide_banner", "-i", str(src)], capture_output=True, text=True).stderr
    for part in (out or "").split(","):
        if " fps" in part:
            try:
                return int(round(float(part.strip().split()[0])))
            except ValueError:
                pass
    return 24


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit((r.stderr or "")[-800:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
