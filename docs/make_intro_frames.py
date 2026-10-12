"""The phone's opening animation follows the desktop's exactly: this samples the desktop's
timeline (src/mygeeky/gui/splash.py) into keyframes for mobile/src/lib/intro-frames.ts.
Run it again whenever that timeline changes."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mygeeky.gui.splash import INTRO_SECONDS, LAYERS, pose  # noqa: E402

STEP = 0.04
times = [round(i * STEP, 2) for i in range(int(INTRO_SECONDS / STEP) + 1)]
out = {"times": times}
for name in ("badge", *LAYERS):
    poses = [pose(name, t) for t in times]
    out[name] = {k: [round(getattr(p, k), 4) for p in poses] for k in ("opacity", "dx", "dy", "scale", "turn", "glow")}
# where each layer grows from: its own middle (the ring: the badge's)
from PIL import Image  # noqa: E402
out["centres"] = {}
for name in LAYERS:
    img = Image.open(ROOT / f"mobile/assets/loader/loader_{name}.png")
    l, t, r, b = img.getchannel("A").getbbox()
    out["centres"][name] = [0.5, 0.5] if name == "ring" else [round((l + r) / 2 / img.width, 4), round((t + b) / 2 / img.height, 4)]
target = ROOT / "mobile/src/lib/intro-frames.ts"
target.write_text("// The opening animation's keyframes, sampled from the desktop's timeline\n"
                  "// (src/mygeeky/gui/splash.py) by docs/make_intro_frames.py: regenerate, don't edit.\n"
                  "export type Track = { opacity: number[]; dx: number[]; dy: number[]; scale: number[]; turn: number[]; glow: number[] };\n"
                  "export type LayerName = 'ring' | 'G' | 'ee' | 'K' | 'm' | 'y';\n"
                  "export const INTRO: { times: number[]; centres: Record<LayerName, number[]>; badge: Track } & Record<LayerName, Track> =\n"
                  f"  {json.dumps(out)};\n", encoding="utf-8")
print(f"{len(times)} keyframes -> {target}")
