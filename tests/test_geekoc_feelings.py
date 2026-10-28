"""GeeKOc in the games: a few still feelings (tools/geekoc_poses.py FEELINGS, GAME_FEELINGS), the same on both apps,
and each one a real picture on the desktop."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "src" / "mygeeky" / "data" / "geekoc_moves.json"
PHONE = ROOT / "mobile" / "src" / "data" / "geekoc_moves.json"


def test_phone_has_the_same_feelings():
    assert DESK.read_bytes() == PHONE.read_bytes()


def test_every_game_with_geekoc_has_its_feelings():
    m = json.loads(DESK.read_text(encoding="utf-8"))
    assert set(m["games"]) == {"whack", "catch", "run", "flappy", "rise", "maze", "hunter"}
    for game, moments in m["games"].items():
        assert {"stand", "happy", "sad"} <= set(moments), game
        assert all(f in m["feelings"] for f in moments.values()), game
    for game in ("run", "flappy", "rise"):               # the ones he jumps in
        assert m["games"][game]["jump"] == "jump"


def test_desktop_draws_each_feeling_once(qapp_offscreen):
    from mygeeky.gui.tour_ui import feeling, still
    m = json.loads(DESK.read_text(encoding="utf-8"))
    for name in m["feelings"]:
        img = still(name, 64).toImage()
        assert any(img.pixelColor(x, y).alpha() > 0 for x in range(0, 64, 4) for y in range(0, 64, 4)), name
    assert still("sad", 64) is still("sad", 64)           # drawn once, then only copied
    assert feeling("run", "jump") == "jump" and feeling("whack", "stand") == "point"
    assert feeling("whack", "jump") == "point"             # a moment a game doesn't have: he stands
    assert feeling("nope", "happy") == "stand"
