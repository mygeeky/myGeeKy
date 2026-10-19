"""Draw GeekOc in a few poses for the apps: src/mygeeky/data/geekoc.json, and the phone's identical copy
mobile/src/data/geekoc.json. Run it after changing GeekOc (website/geekoc/geekoc.js):

    python tools/geekoc_poses.py

The website draws GeekOc live in JavaScript; the apps get him pre-drawn, as plain SVG markup (gradients,
paths and one clip path), which QtSvg and react-native-svg both draw. Each pose is the inside of a
viewBox="0 0 620 620" drawing. Needs Node (node --version) to run geekoc.js.
"""
from __future__ import annotations

import json
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

DRAW = """
const fs = require('fs'); global.window = global; eval(fs.readFileSync(process.argv[1], 'utf8'));
const G = global.GeekOc, poses = JSON.parse(process.argv[2]), out = {};
for (const [name, [pose, face, arm]] of Object.entries(poses)) {
  out[name] = G.markup(G.build({ pose, face, arm, still: true }), { id: 'gk' + name });
}
process.stdout.write(JSON.stringify(out));
"""


def build() -> dict[str, object]:
    drawn = subprocess.run(["node", "-e", DRAW, str(KIT), json.dumps(POSES)], check=True, capture_output=True,
                           text=True).stdout
    return {"viewBox": "0 0 620 620", "poses": json.loads(drawn)}


def main() -> None:
    text = json.dumps(build(), ensure_ascii=False, separators=(",", ":")) + "\n"
    for path in OUT:
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({len(text) // 1024} KB)")


if __name__ == "__main__":
    main()
