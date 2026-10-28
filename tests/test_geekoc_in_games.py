"""Play every game GeeKOc is in, a whole round each, the way a person might: mostly right, sometimes wrong. The real
frame loop runs (ArcadeGame._frame, WordHunter.step) and every frame is painted. Each round must finish with its
answers, nothing may raise, and GeeKOc must stay worth watching: he shows every feeling his game has, and he changes
often enough to answer what you do -- not a picture that never moves, not one that flickers."""
from __future__ import annotations

import random
import sys
import time
from typing import Any

import pytest

from mygeeky.config import MyGeekyConfig

GAMES = ("whack", "catch", "run", "flappy", "rise", "maze", "hunter")
PLAYING = [False]                                         # only frames of play count: not a card, not after the end


@pytest.fixture
def drawn(monkeypatch):
    """Every GeeKOc painted, as (game, feeling), through the real picture (a missing one raises here, where the game
    itself would only skip drawing him)."""
    from mygeeky.gui import games_arcade
    from mygeeky.gui.tour_ui import feeling, still
    seen: list[tuple[str, str]] = []

    def oc(p, game, moment, x, y, size):
        name = feeling(game, moment)
        assert not still(name, 64).isNull()
        if PLAYING[0]:
            seen.append((game, name))
    monkeypatch.setattr(games_arcade, "_oc", oc)
    return seen


def _game(gid: str):
    from mygeeky.gui.app import THEMES
    from mygeeky.gui.games_adventure import GAMES as ADVENTURES
    from mygeeky.gui.games_arcade import GAMES as ARCADE
    from mygeeky.gui.games_ui import WordHunter
    maker = {**ARCADE, **ADVENTURES, "hunter": WordHunter}[gid]
    theme = next(iter(THEMES.values()))
    w = maker(MyGeekyConfig(github_username="me", keywords=["gwas", "python", "rna-seq"]), lambda: theme, lambda s: None)
    w.resize(420, 640)
    w.show()
    return w


def _gone(w) -> None:
    """Delete the game the way the panel does, and let Qt finish every deletion it has pending now, while the game
    still exists: left for later, a card it dropped is deleted after the game is gone, and a later test that flushes
    deletions crashes."""
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication
    w.close()
    if hasattr(w, "stop"):
        w.stop()
    w.timer.stop()
    w.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete.value)


def _cards(w, rnd: random.Random) -> None:
    """A card is up (start, a door's question, the question between waves, the surface): answer it like a person,
    any option, then go on."""
    from PySide6.QtWidgets import QPushButton
    if w.overlay is None or not w.overlay.isVisible():
        return
    buttons = [b for b in w.overlay.findChildren(QPushButton) if b.isVisible() and b.isEnabled()]
    go = [b for b in buttons if b.text() in ("Go", "OK", "Through the door ›", "Next wave ›", "See how you did")]
    (go[0] if go else rnd.choice(buttons)).click()


def _bot(gid: str, w, rnd: random.Random) -> None:
    """One move, mostly right (about four times in five)."""
    right = rnd.random() < 0.8
    if gid == "whack":
        w._layout()
        for h in w.holes:
            if h["up"] and (h["up"]["c"]["bug"] or rnd.random() < 0.04):
                w.press(h["x"], h["y"] - 10)
                return
    elif gid == "catch" and w.cur and w.cur["vy"] < 500:
        nb = len(w.set["bins"])
        lane = w.cur["bin"] if right else (w.cur["bin"] + 1) % nb
        w.press(w._nx(lane), w.H - 60)
    elif gid == "run":
        px = 92
        for o in w.obs:
            if o.get("done") or o.get("decided"):
                continue
            if "label" in o and 35 < o["x"] - px < 70:     # a bug: in the air before it arrives, down after it
                o["decided"] = True
                if rnd.random() < 0.95:
                    w.jump()
            elif "gate" in o and 40 < o["x"] - px < 70:    # high when it reaches him: the top answer
                o["decided"] = True
                if o["top"] == right:                     # the top answer is the right one: jump for it
                    w.jump()
    elif gid == "flappy":
        (t0, t1), (b0, b1) = w._gaps()
        nxt = next((pp for pp in w.pipes if not pp.get("done")), None)
        aim = w.H / 2 if nxt is None else ((t0 + t1) / 2 if nxt["top"] == nxt.setdefault("bot_right", right) else (b0 + b1) / 2)
        if w.y > aim + 12 and w.vy > -40:
            w.flap()
    elif gid == "rise":
        if w.jump or not w.opts:
            w.think = 20 + rnd.randrange(40)              # reading the next row: one to three seconds
            return
        w.think = getattr(w, "think", 30) - 1
        if w.think <= 0:
            live = [i for i, o in enumerate(w.opts) if not o.get("gone")]
            good = [i for i in live if w.opts[i]["ok"]]
            if w.row == 1 and not w.mistakes:             # everyone climbs a wrong platform once
                right = False
            bad = [i for i in live if i not in good]
            w.choose(good[0] if (right or not bad) and good else rnd.choice(bad))
    elif gid == "maze":
        if w.anim[2] >= 1 and w.overlay is None:
            route = w._path(w.at[0], w.at[1], lambda k: w.doors.get(k, {}).get("state") == "locked")
            if route and len(route) > 1:
                (x, y), (nx, ny) = route[0], route[1]
                w.move(nx - x, ny - y)
    elif gid == "hunter":
        if w.cool <= 0:
            for r in w.rocks:
                if r["y"] > 20 and (r["good"] or rnd.random() < 0.03):
                    w.fire(r["x"], r["y"] + r["vy"] * 0.25)
                    return


def _play(gid: str, w, seed: int) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication
    rnd = random.Random(seed)
    random.seed(seed)
    done: list[tuple] = []
    w.finished.connect(lambda *a: done.append(a))
    errors, hook = [], sys.excepthook
    sys.excepthook = lambda *e: errors.append(e[1])
    frames = 0
    try:
        for i in range(8000):                             # 0.05 s a frame: at most 400 s of play
            if done:
                break
            _cards(w, rnd)
            _bot(gid, w, rnd)
            w.last = time.monotonic() - 0.05
            (w.step if gid == "hunter" else w._frame)()
            QApplication.processEvents()
            if i % 2 == 0:
                PLAYING[0] = not w.paused and not getattr(w, "ended", False) and w.overlay is None
                w.grab()                                  # paint: GeeKOc is drawn here
                frames += PLAYING[0]
    finally:
        sys.excepthook = hook
    return {"done": done, "errors": errors, "frames": frames}


@pytest.mark.parametrize("gid", GAMES)
@pytest.mark.parametrize("seed", [1, 2])
def test_a_whole_round_plays_and_geekoc_answers_what_you_do(qapp_offscreen, drawn, gid, seed):
    from mygeeky.gui.tour_ui import _moves
    w = _game(gid)
    try:
        r = _play(gid, w, seed)
    finally:
        _gone(w)
    assert not r["errors"], r["errors"]
    assert r["done"], f"{gid}: the round never finished"
    answers = r["done"][0][0]
    assert answers and all({"id", "right", "level", "terms"} <= set(a) for a in answers), gid

    feelings = [f for g, f in drawn if g == gid]
    assert feelings, f"{gid}: GeeKOc was never drawn"
    expect = set(_moves()["games"][gid].values())      # every feeling his game has: the bot errs now and then
    assert expect <= set(feelings), (gid, sorted(set(feelings)), sorted(expect))
    # he answers what you do: changes at least a few times a round, but never every frame (no flicker)
    changes = sum(1 for a, b in zip(feelings, feelings[1:]) if a != b)
    assert changes >= 3, (gid, changes)
    assert changes < len(feelings) / 3, (gid, changes, len(feelings))


def test_flappy_edges_cost_no_life(qapp_offscreen):
    """Tapping too often (or not at all) never ends a round by itself: the surface and the sea floor are free, only
    the coral and a wrong gap take a life."""
    w = _game("flappy")
    try:
        w.go()
        for flap in (True, False):                        # five seconds tapping all the time, then five not at all
            for _ in range(100):
                if flap:
                    w.flap()
                w.step(0.05)
                w.pipes.clear()                           # no coral in the way: only the edges
                assert 8 <= w.y <= w.H - 12
        assert w.lives == 3 and not w.ended
    finally:
        _gone(w)

