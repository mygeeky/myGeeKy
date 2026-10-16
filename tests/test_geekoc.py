"""GeekOc has to survive being still, and being shrunk.

He is drawn by `website/geekoc/geekoc.js` and had no tests at all, which is how his poses quietly
became indistinguishable: the rig is watched moving, where the arms trail and the smallest change is
obvious, so nobody noticed that `wave` and `point` were within three percent of standing still. Every
picture of him in the README, the poster and the app tours is a STILL, and a pose that cannot be told
apart there says nothing.

These need node (to run the rig) and Qt (to rasterise it); they skip where either is missing.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "website" / "geekoc" / "geekoc.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None or not ENGINE.exists(),
                                reason="GeekOc is drawn by node; nothing to check without it")


def _node(script: str, **env_extra: str) -> str:
    env = {**os.environ, "GEEKOC": str(ENGINE), **env_extra}
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=300, env=env)
    assert r.returncode == 0, (r.stderr or "")[-600:]
    return r.stdout


def _names() -> dict[str, list[str]]:
    return json.loads(_node("require(process.env.GEEKOC); const G = globalThis.GeekOc;"
                            "console.log(JSON.stringify({poses: Object.keys(G.POSES),"
                            " faces: Object.keys(G.FACES), moves: Object.keys(G.MOVES)}));"))


def _render(pose: str, face: str = "happy", px: int = 300):
    """One still, rasterised. Qt is asked for last so the test skips cleanly without it."""
    pytest.importorskip("PySide6.QtSvg")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    markup = _node("require(process.env.GEEKOC); const G = globalThis.GeekOc;"
                   "process.stdout.write(G.svg({pose: process.env.POSE, face: process.env.FACE,"
                   " t: 1.4, still: true, size: 300}));", POSE=pose, FACE=face)
    renderer = QSvgRenderer(QByteArray(markup.encode("utf-8")))
    assert renderer.isValid(), f"{pose}/{face} did not produce readable SVG"
    image = QImage(px, px, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    return image


def _differs(a, b) -> float:
    """How much of the picture changed, as a percentage of the pixels looked at."""
    seen = changed = 0
    for y in range(0, a.height(), 2):
        for x in range(0, a.width(), 2):
            seen += 1
            if a.pixel(x, y) != b.pixel(x, y):
                changed += 1
    return 100.0 * changed / seen


# --------------------------------------------------------------------------- the rig still runs
def test_every_pose_and_move_simulates_without_going_wrong():
    said = _node("""
      require(process.env.GEEKOC); const G = globalThis.GeekOc; const bad = [];
      for (const move of Object.keys(G.MOVES)) {
        const life = G.alive({}); let clock = 0;
        for (let f = 0; f < 420; f++) {
          clock += 1/60;
          const m = life.follow(move, clock);
          life.step(m.pose, 'happy', 1/60);
          if (JSON.stringify(life.parts(m.pose, 'happy')).includes('NaN')) { bad.push(move + '@' + f); break; }
        }
      }
      for (const pose of Object.keys(G.POSES)) {
        const life = G.alive({});
        for (let f = 0; f < 120; f++) life.step(G.POSES[pose], 'happy', 1/60);
        if (JSON.stringify(life.parts(G.POSES[pose], 'happy')).includes('NaN')) bad.push('pose ' + pose);
      }
      console.log(JSON.stringify(bad));
    """)
    assert json.loads(said) == [], "the simulation produced NaN"


# --------------------------------------------------------------------------- he has to READ
#
# Six percent is not a style preference. `wave` was 3.4% and `point` 2.5% away from standing still,
# and at the size a README or a tour card shows him neither could be told from the other. The ones
# built to be seen still are held to a bar; `sleep` and `idle` are quiet on purpose and are not.
SPEAKS = {"wave", "point", "cheer", "present", "swim", "jet"}
FLOOR = 6.0


@pytest.mark.parametrize("pose", sorted(SPEAKS))
def test_a_pose_that_says_something_can_be_told_apart_from_idle(pose):
    idle = _render("idle")
    assert _differs(idle, _render(pose)) >= FLOOR, (
        f"{pose!r} is within {FLOOR}% of standing still, so it says nothing in a picture. "
        "Swing an outer arm further -- up and OUT past the body's edge, never up across it.")


def test_no_two_poses_draw_the_same_picture():
    """An unknown pose name is accepted in silence and draws the default, and two poses that drifted
    together look exactly like that bug. Either way the answer is the same: look at the pixels."""
    names = _names()["poses"]
    seen: dict[bytes, str] = {}
    for pose in names:
        blob = _render(pose, px=160).constBits().tobytes()
        assert blob not in seen, f"{pose!r} draws the same picture as {seen[blob]!r}"
        seen[blob] = pose


def test_the_poses_the_website_moves_with_are_left_alone():
    """`swim` and `jet` carry every move. Their numbers are load-bearing for the trailing arms that
    took the longest to get right, so a change to them should be a decision, not a side effect."""
    poses = json.loads(_node("require(process.env.GEEKOC);"
                             "console.log(JSON.stringify(globalThis.GeekOc.POSES));"))
    assert poses["swim"]["swing"] == [16, 10, 4, 0, 0, -4, -10, -16]
    assert poses["swim"]["curl"] == [54, 48, 42, 34, -34, -42, -48, -54]
    assert poses["jet"]["swing"] == [26, 18, 8, 2, -2, -8, -18, -26]
    assert poses["jet"]["curl"] == [22, 18, 14, 10, -10, -14, -18, -22]


# --------------------------------------------------------------------------- the suckers
#
# The single detail that says "octopus" fastest, and it went missing twice in different ways. First
# the colour: dark gold went in, and a later revert of the whole appearance took it back out with
# everything else, leaving pale cups nobody could see. Then the renderer: `markup` never drew the
# undersides at all -- only the canvas did -- so every still exported for the README, the poster and
# the app tours was an octopus with no suckers on it.
GOLD = "#c9871a"


def test_the_suckers_are_drawn_in_the_svg_and_not_only_on_the_canvas():
    for pose in ("idle", "wave", "point", "swim", "jet"):
        markup = _node("require(process.env.GEEKOC); const G = globalThis.GeekOc;"
                       "process.stdout.write(G.svg({pose: process.env.POSE, face: 'happy',"
                       " t: 1.4, still: true, size: 400}));", POSE=pose)
        cups = markup.lower().count(GOLD)
        assert cups >= 8, f"{pose}: only {cups} suckers in the SVG; the canvas draws them, this must too"
        assert "ffc457" in markup.lower(), f"{pose}: the pale underside band is missing"


def test_the_sucker_colour_stays_the_measured_one():
    """Bright yellow measures 1.20:1 against the cream band and this gold 2.39:1. Value is what
    survives a thumbnail; hue is not. Anything lighter than this has been tried and was wrong."""
    skin = json.loads(_node("require(process.env.GEEKOC);"
                            "console.log(JSON.stringify(globalThis.GeekOc.SKIN));"))
    assert skin["sucker"].lower() == GOLD


# --------------------------------------------------------------------------- the eyelids
#
# The lid comes down from ABOVE. The SVG renderer had the old sum, which shut the eye at 0.5, showed
# the top half at 0 -- so he looked half asleep in every picture -- and at 1 covered the BOTTOM half,
# an eye closing upwards from the chin. `parts` had been corrected and `markup` had not.
def _eye_in_picture(face, px=300):
    """The left eye's circle, in the rendered picture's own pixels.

    Taken from the SVG rather than from `parts`: the two describe the same octopus in different
    coordinates, and `parts({size: 300})` put the eye in the corner of a 300px render. The markup
    carries its own viewBox, so the mapping is in the file and does not have to be guessed."""
    markup = _node("require(process.env.GEEKOC); const G = globalThis.GeekOc;"
                   "process.stdout.write(G.svg({pose: 'idle', face: process.env.FACE,"
                   " t: 1.4, still: true, size: " + str(px) + "}));", FACE=face)
    box = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', markup)
    assert box, "the SVG has no viewBox to scale by"
    scale = px / float(box.group(1))
    eyes = re.findall(r'<circle cx="([-\d.]+)" cy="([-\d.]+)" r="30" fill="#ffffff"', markup)
    assert eyes, "no eye white found in the markup"
    x, y = (float(v) for v in eyes[0])
    return x * scale, y * scale, 30 * scale


def _white_above_and_below(face):
    """How much of the eye's white shows in its top half, and in its bottom half."""
    image = _render("idle", face)
    cx, cy, r = _eye_in_picture(face)
    above = below = 0
    for dy in range(-int(r) + 2, int(r) - 1):
        for dx in range(-int(r) + 2, int(r) - 1):
            if dx * dx + dy * dy > (r - 2) ** 2:
                continue
            pixel = image.pixel(int(cx) + dx, int(cy) + dy)
            if (pixel >> 16 & 255) > 220 and (pixel >> 8 & 255) > 220 and (pixel & 255) > 220:
                if dy < 0:
                    above += 1
                else:
                    below += 1
    return above, below


def test_a_wide_open_eye_is_not_half_covered():
    above, below = _white_above_and_below("happy")
    assert above > 0 and below > 0, "no white in the eye at all"
    assert above > below * 0.6, (
        f"only {above} white pixels in the top half against {below} below: the lid is sitting on a "
        "wide-open eye, which is what made him look half asleep in every picture")


def test_a_lowered_lid_covers_the_top_of_the_eye_not_the_bottom():
    above, below = _white_above_and_below("shy")          # lids 0.35
    assert below > above, (
        f"{above} white pixels above the middle and {below} below: the lid is closing from underneath")


def test_asleep_means_the_eye_is_covered():
    above, below = _white_above_and_below("sleepy")       # lids 1
    assert above + below < 40, f"{above + below} white pixels still showing on a shut eye"
