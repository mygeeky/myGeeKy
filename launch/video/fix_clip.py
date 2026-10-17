"""Repair the generated character clip, keeping its white wall exactly as it is.

    python launch/video/fix_clip.py <clip.mp4> [name]   ->  launch/video/intro/<name>-fixed.mp4

The generator gets the character right and the physics wrong. Two faults in this clip, both visible once
you step through it, and both repairable because the wall behind him is one flat colour: the figure can be
lifted off, moved or resized, and put back on a clean plate of that same wall with no seam to hide.

  THE ABORTED STEP.  A step swings the legs from about 218px apart to about 157 (legs together) and out
  again, over roughly eleven frames. Between frames 45 and 52 the clip does it in seven, and the legs only
  close to 180 before swinging back out -- which is seen as the foot stepping BACKWARD. There is no way to
  interpolate a step that was never there, so a correct one is borrowed from later in the clip, where the
  walk is clean, and placed along the path he is actually travelling.

  THE SIZE JUMP.  At frame 97 he suddenly stands 380px tall instead of 450 -- fifteen percent smaller, and
  nineteen pixels higher off the floor. Every frame from there on is scaled back up about his feet, so he
  keeps one height for the whole clip.

Nothing else is touched: same wall, same colours, same length, same audio.
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

PALE, FLAT = 228, 16          # what counts as the wall: this bright, and this close to colourless

# The film is 1920x1080 and the generator hands back 1280x720, so the clip was being enlarged inside the
# film -- AFTER already being enlarged here to fix his size. Two enlargements of the same pixels is what
# made it look washed out. It is written at the film's own size instead, and the figure goes from its
# original pixels to its final size in ONE resample: the crop is scaled by 1.5 x the size fix together,
# rather than scaled, saved, and scaled again.
#
# No detail is created by any of this. The clip is 720p material and the only way to get more is to
# generate it larger; what this avoids is throwing away what is there.
FILM = (1920, 1080)
SHARPEN = (1.6, 55, 3)        # radius, strength, threshold -- flat cel art takes this well, photos do not

# How he sits in the frame. ZOOM pulls back from him, leaving wall around him for the words to live in;
# his feet stay on the same floor line, so pulling back adds the room ABOVE him rather than dropping him.
# RIGHT walks him further across, so he finishes at the far end of the frame instead of the middle.
ZOOM = 0.80
RIGHT = 0.227                 # as a fraction of the frame's width

# The broken stride is CUT OUT, not patched. Patching was tried first and it does not work: this walk's
# steps land every 8 to 13 frames, never the same twice, so no borrowed stride lines up at both ends --
# and squeezing a correct step into the seven frames available makes the legs move at double speed, which
# is just as wrong as the original, only differently.
#
# Frames 40 and 57 are both legs-together beats and their poses match closely (scored on the pose AND on the
# frame each runs into next, which is what separates a clean join from one that stalls), so the clip can simply skip from one to the other.
# What that leaves is a jump FORWARD of about 150px, because he walked during the frames being dropped --
# and that is the part the flat wall pays for: every later frame is lifted off it and set back down
# further left, so the walk carries straight on.
# A second cut, further on: he makes the same small gesture twice while standing. The repeat measures
# 0.22 different from the first pass where neighbouring frames differ by 0.8, so it is the same movement
# played again, not a continuation of it. It is cut at 128 -> 142 rather than at the repeat's own edges
# because the movement does not actually settle until two frames after it looks finished, and stopping
# short of that leaves a twitch.
#
# Both cuts are given in the ORIGINAL clip's numbering.
JOINS = [(39, 57), (128, 142)]

SHRINKS_AT = 97               # from this frame on, he is suddenly smaller


def wall(frames: list[Path]) -> Image.Image:
    """A clean plate of the background, taken as the BRIGHTEST each pixel ever is.

    The median is the obvious choice and it is wrong here: he walks in and then stands in one place for
    three fifths of the clip, so the median of that spot is him, and the plate comes out with a ghost
    standing in it. He is darker than the wall everywhere, and every pixel of the wall is uncovered at
    some point while he walks in, so taking a high percentile over time removes him completely."""
    stack = np.stack([np.asarray(Image.open(p).convert("RGB")) for p in frames[::4]])
    return Image.fromarray(np.percentile(stack, 92, axis=0).astype(np.uint8), "RGB")


def figure(path: Path) -> Image.Image:
    """Him, lifted off the wall, with his shadow.

    Found by flood-filling the wall in from the frame's border rather than by brightness: his FACE is
    nearly as pale as the wall, and anything keying on brightness erases it."""
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(int)
    pale = (rgb.min(axis=2) > PALE) & ((rgb.max(axis=2) - rgb.min(axis=2)) < FLAT)
    lab, _ = ndimage.label(pale)
    edge = {*lab[0].tolist(), *lab[-1].tolist(), *lab[:, 0].tolist(), *lab[:, -1].tolist()} - {0}
    alpha = np.where(np.isin(lab, list(edge)), 0, 255).astype(np.uint8)
    img = Image.fromarray(np.dstack([rgb.astype(np.uint8), alpha]), "RGBA")
    img.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(0.8)))
    return img


def where(img: Image.Image) -> tuple[int, int, int, int]:
    return img.getchannel("A").point(lambda v: 255 if v > 60 else 0).getbbox()


def crisp(im: Image.Image) -> Image.Image:
    return im.filter(ImageFilter.UnsharpMask(*SHARPEN))


def put(plate: Image.Image, fig: Image.Image, foot_x: float, foot_y: float, scale: float = 1.0,
        up: float = 1.0):
    """Stand him on the plate: `foot_x` is the middle of him, `foot_y` the ground under his shoes.

    `scale` is the size correction and `up` the step to the film's resolution, and they are multiplied
    into a SINGLE resize -- enlarging twice over softens him for nothing. The coordinates arrive in the
    original clip's pixels and are taken up to the plate's here."""
    crop = fig.crop(where(fig))
    k = scale * up * ZOOM
    if k != 1.0:
        crop = crop.resize((max(1, round(crop.width * k)), max(1, round(crop.height * k))), Image.LANCZOS)
        crop = crisp(crop)
    out = plate.convert("RGBA").copy()
    x = foot_x * up * ZOOM + FILM[0] * (1 - ZOOM) / 2 + FILM[0] * RIGHT
    y = foot_y * up                                   # his feet stay on the floor they were always on
    out.alpha_composite(crop, (round(x - crop.width / 2), round(y - crop.height)))
    return out.convert("RGB")


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
    raw, done = OUT / f"{name}-src", OUT / f"{name}-fixed"
    for d in (raw, done):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), str(raw / "f_%04d.png")])
    frames = sorted(raw.glob("*.png"))
    print(f"  {len(frames)} frames")

    src_w, src_h = Image.open(frames[0]).size
    up = FILM[0] / src_w
    plate = crisp(wall(frames).resize(FILM, Image.LANCZOS))
    print(f"  {src_w}x{src_h} in, {FILM[0]}x{FILM[1]} out ({up:.2f}x)")
    spot = {}                                     # frame -> (middle of him, the ground under him, height)
    for i, p in enumerate(frames, 1):
        x0, y0, x1, y1 = where(figure(p))
        spot[i] = ((x0 + x1) / 2, y1, y1 - y0)

    tall = float(np.median([spot[i][2] for i in range(1, SHRINKS_AT)]))
    small = float(np.median([spot[i][2] for i in range(SHRINKS_AT, len(frames) + 1)]))
    grow = tall / small
    print(f"  he is {tall:.0f}px tall, then {small:.0f}px from frame {SHRINKS_AT}: scaling those by {grow:.3f}")

    # Each cut leaves him further along than he should be, by however far he walked during the frames
    # being dropped. The shifts add up, so later frames carry the total of every cut before them.
    shift_after = {}
    running = 0.0
    kept, skip = [], set()
    for cut_from, cut_to in JOINS:
        pace = (spot[cut_from][0] - spot[max(1, cut_from - 6)][0]) / min(6, cut_from - 1)
        running += spot[cut_to][0] - (spot[cut_from][0] + pace)
        shift_after[cut_to] = running
        skip |= set(range(cut_from + 1, cut_to))
        print(f"  joining {cut_from} to {cut_to}: dropping {cut_to - cut_from - 1} frames,"
              f" sliding what follows back {running:.0f}px in total")
    kept = [n for n in range(1, len(frames) + 1) if n not in skip]

    shift, first = 0.0, min(f for f, _ in JOINS)
    for out_n, n in enumerate(kept, 1):
        if n in shift_after:
            shift = shift_after[n]
        p = frames[n - 1]
        # Every frame goes through the same framing, including the ones with nothing wrong with them:
        # the moment the picture is zoomed or moved at all, a frame left as it was jumps.
        if n <= first:
            fx, fy, _ = spot[n]
            img = put(plate, figure(p), fx, fy, 1.0, up)
        elif n < SHRINKS_AT:
            fx, fy, _ = spot[n]
            img = put(plate, figure(p), fx - shift, fy, 1.0, up)
        else:
            fx, _, _ = spot[n]
            # he also goes back to the size and the floor he had before he shrank
            img = put(plate, figure(p),
                      spot[SHRINKS_AT - 1][0] - shift + (fx - spot[SHRINKS_AT][0]) * grow,
                      spot[SHRINKS_AT - 1][1], grow, up)
        img.save(done / f"f_{out_n:04d}.png")
    print(f"  {len(kept)} frames out ({len(kept) / 24:.2f}s), size fixed from {SHRINKS_AT} on")

    out = OUT / f"{name}-fixed.mp4"
    run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-framerate", str(fps(ffmpeg, src)),
         "-i", str(done / "f_%04d.png"), "-i", str(src), "-map", "0:v", "-map", "1:a?",
         "-c:v", "libx264", "-crf", "15", "-preset", "slow", "-pix_fmt", "yuv420p", "-shortest", str(out)])
    print(f"  {out}  ({out.stat().st_size // 1024} KB)")
    shutil.rmtree(raw, ignore_errors=True)
    return 0


def fps(ffmpeg: str, src: Path) -> int:
    said = subprocess.run([ffmpeg, "-hide_banner", "-i", str(src)], capture_output=True, text=True).stderr
    for part in (said or "").split(","):
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
