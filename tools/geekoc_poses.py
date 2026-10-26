"""Draw GeekOc in a few poses for the apps: src/mygeeky/data/geekoc.json, and the phone's identical copy
mobile/src/data/geekoc.json; and the tour's moving GeekOc, a short loop of frames per pose whose arms swim
(geekoc_moves.json, both apps). Run it after changing GeekOc (website/geekoc/geekoc.js):

    python tools/geekoc_poses.py

The website draws GeekOc live in JavaScript; the apps get him pre-drawn, as plain SVG markup (gradients,
paths and one clip path), which QtSvg and react-native-svg both draw. Each pose is the inside of a
viewBox="0 0 620 620" drawing. Needs Node (node --version) to run geekoc.js.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = [ROOT / "src" / "mygeeky" / "data" / "geekoc.json", ROOT / "mobile" / "src" / "data" / "geekoc.json"]
KIT = ROOT / "website" / "geekoc" / "geekoc.js"
# name -> (body pose, face, how long his arms are: 1 is his own; "head" is nearly all head, for the language
# drawing, whose arms are the languages)
POSES = {
    "cheer": ("cheer", "excited", 1),
    "wave": ("wave", "happy", 1),
    "think": ("think", "happy", 1),
    "proud": ("present", "proud", 1),
    "sleep": ("sleep", "sleepy", 1),
    "idle": ("idle", "happy", 1),
    "swim": ("swim", "happy", 1),
    "point": ("point", "curious", 1),
    "head": ("idle", "happy", 0.12),
}

# the tour's poses (data/tour.json): each a loop of FRAMES drawings, one sway of the arms
MOVES = {"wave": "happy", "point": "curious", "think": "happy", "cheer": "excited", "present": "proud"}
FRAMES = 8
MOVES_OUT = [ROOT / "src" / "mygeeky" / "data" / "geekoc_moves.json", ROOT / "mobile" / "src" / "data" / "geekoc_moves.json"]

DRAW = """
const fs = require('fs'); global.window = global; eval(fs.readFileSync(process.argv[1], 'utf8'));
const G = global.GeekOc, poses = JSON.parse(process.argv[2]), out = {};
for (const [name, [pose, face, arm]] of Object.entries(poses)) {
  out[name] = G.markup(G.build({ pose, face, arm, still: true }), { id: 'gk' + name });
}
process.stdout.write(JSON.stringify(out));
"""


# The arms swim: a wave runs along the eight of them, each swinging and curling; the arm doing the gesture
# (pointing, waving) moves least, so the gesture still reads. One loop is one period of the sine.
MOVE = """
const fs = require('fs'); global.window = global; eval(fs.readFileSync(process.argv[1], 'utf8'));
const G = global.GeekOc, poses = JSON.parse(process.argv[2]), frames = +process.argv[3], out = {};
for (const [name, face] of Object.entries(poses)) {
  const p = G.POSES[name], busy = p.swing.map(Math.abs), top = Math.max(...busy);
  const k = (i) => (top > 40 && busy[i] === top ? 0.35 : 1);
  out[name] = [];
  for (let f = 0; f < frames; f++) {
    const a = (f / frames) * 2 * Math.PI;
    const pose = { ...p, swing: p.swing.map((s, i) => s + k(i) * 13 * Math.sin(a + i * 0.9)),
                   curl: p.curl.map((c, i) => c + k(i) * 34 * Math.sin(a + i * 0.9 + 1.2)) };
    out[name].push(G.markup(G.build({ pose, face, still: true }), { id: 'gm' + name }));
  }
}
// The phone's welcome: GeekOc jet-swims. The mantle fills (arms open like an umbrella, he drifts down), squeezes
// shut (the arms snap into one streamlined bundle, water leaves the siphon as bubbles, he shoots up), then he glides
// and sinks while it refills. JET_FRAMES at the same fps as the rest.
const ease = (x) => x * x * (3 - 2 * x), lerp = (a, b, t) => a + (b - a) * t;
const open = { ...G.POSES.jet, face: 'happy' };
const shut = { len: 1.06, face: 'happy', swing: [-36, -27, -17, -7, 7, 17, 27, 36], curl: [16, 12, 9, 6, -6, -9, -12, -16] };
const J = +process.argv[4];
out.jet = [];
for (let f = 0; f < J; f++) {
  const u = f / J;
  let fill, arms, y, puff = -1;
  if (u < 0.55) { const k = ease(u / 0.55); fill = k; arms = k; y = lerp(0, 12, k); }
  else if (u < 0.68) { const k = ease((u - 0.55) / 0.13); fill = lerp(1, -0.7, k); arms = 1 - k; y = lerp(12, -30, k); puff = k * 0.4; }
  else { const k = (u - 0.68) / 0.32; fill = lerp(-0.7, 0, ease(k)); arms = 0.15 * ease(k); y = lerp(-30, 0, ease(k)); puff = 0.4 + k * 0.6; }
  let svg = G.markup(G.build({ pose: G.mix(shut, open, arms), face: 'happy', still: true, head: 0.98 * (1 + 0.07 * fill), at: [0, y] }),
                     { id: 'gmjet' + f });   // an id per frame: his face moves, and the phone keeps a reused clip where it first was
  if (puff >= 0) {
    const by = 520 + y;
    svg += '<g fill="none" stroke="#9fe6ff" stroke-width="6" opacity="' + (1 - puff).toFixed(2) + '">' +
      [[0, 0, 16], [-22, 30, 11], [20, 54, 13], [-8, 80, 9]].map(([dx, dy, r]) => '<circle cx="' + Math.round(310 + dx * (1 + puff)) +
        '" cy="' + Math.round(by + dy * (0.4 + puff * 1.2)) + '" r="' + Math.round(r * (0.6 + puff * 0.7)) + '"/>').join('') + '</g>';
  }
  out.jet.push(svg);
}
process.stdout.write(JSON.stringify(out));
"""
JET_FRAMES = 20


def _thin(m: re.Match) -> str:
    d = m.group(1)
    if "C" in d or "Q" in d:
        return m.group(0)
    closed = d.endswith("Z")
    pts = (d[:-1] if closed else d).split("L")
    if len(pts) < 12:
        return m.group(0)
    keep = [p for i, p in enumerate(pts) if i % 2 == 0 or i == len(pts) - 1]
    return 'd="M' + "L".join(keep) + ("Z" if closed else "") + '"'


def moves() -> dict[str, object]:
    """Each pose as its pieces (one SVG element each, coordinates in whole units: plenty at the size he's drawn)
    and its frames as lists of pieces: the body, face and glasses are the same in every frame, so they're kept
    once. A frame is "".join(parts[i] for i in frame)."""
    drawn = json.loads(subprocess.run(["node", "-e", MOVE, str(KIT), json.dumps(MOVES), str(FRAMES), str(JET_FRAMES)], check=True,
                                      capture_output=True, text=True).stdout)
    poses = {}
    for name, frames in drawn.items():
        parts: list[str] = []
        index: dict[str, int] = {}
        out = []
        for markup in frames:
            markup = re.sub(r"-?\d+\.\d+", lambda m: (str(round(float(m.group()))) if abs(float(m.group())) >= 2
                                                       else m.group()), markup)   # gradient stops stay as they are
            if name == "jet":                       # the welcome's loop: every other point of an arm's outline is plenty
                markup = re.sub(r'd="M([^"]+)"', _thin, markup)
            row = []
            for piece in re.split(r"(?=<)", markup):
                if piece:
                    row.append(index.setdefault(piece, len(parts)))
                    if row[-1] == len(parts):
                        parts.append(piece)
            out.append(row)
        poses[name] = {"parts": parts, "frames": out}
    return {"viewBox": "0 0 620 620", "fps": 8, "poses": poses}


def build() -> dict[str, object]:
    drawn = subprocess.run(["node", "-e", DRAW, str(KIT), json.dumps(POSES)], check=True, capture_output=True,
                           text=True).stdout
    return {"viewBox": "0 0 620 620", "poses": json.loads(drawn)}


def main() -> None:
    text = json.dumps(build(), ensure_ascii=False, separators=(",", ":")) + "\n"
    for path in OUT:
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({len(text) // 1024} KB)")
    text = json.dumps(moves(), ensure_ascii=False, separators=(",", ":")) + "\n"
    for path in MOVES_OUT:
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({len(text) // 1024} KB)")


if __name__ == "__main__":
    main()
