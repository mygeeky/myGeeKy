"""The opening animation: its timeline ends on the exact badge, and it plays only once."""
from pathlib import Path

import pytest

from mygeeky.config import MyGeekyConfig, load_config
from mygeeky.gui.splash import ASSETS_DIR, INTRO_SECONDS, LAYERS, pose


def test_the_animation_starts_almost_empty_and_ends_on_the_badge():
    start = {n: pose(n, 0.0) for n in ("badge", *LAYERS)}
    assert start["ring"].opacity == pytest.approx(0.05) and start["ring"].turn == pytest.approx(-360)
    assert all(start[n].opacity == 0 for n in ("badge", "G", "ee", "K", "m", "y"))
    for name in ("badge", *LAYERS):                         # every part lands exactly where the icon has it
        p = pose(name, INTRO_SECONDS)
        assert (p.opacity, p.dx, p.dy, p.scale, p.turn, p.glow) == pytest.approx((1, 0, 0, 1, 0, 0), abs=1e-6), name
    order = [min(t / 100 for t in range(0, 400) if pose(n, t / 100).opacity > 0.5) for n in ("ring", "G", "K", "m", "y")]
    assert order == sorted(order)                           # the arms first, then G and K, then m and y


def test_its_pictures_ship_with_the_package():
    for name in LAYERS:
        assert (ASSETS_DIR / f"loader_{name}.png").stat().st_size > 1000, name
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert '"assets/*.png"' in pyproject


def test_it_plays_once_and_never_stops_myGeeKy_starting(monkeypatch):
    from mygeeky.gui import app as logic
    from mygeeky.gui import splash
    played = []

    class Fake:
        def play(self):
            played.append(1)
    darks = []
    monkeypatch.setattr(splash, "make_splash", lambda dark=True: (darks.append(dark), Fake())[1])
    cfg = MyGeekyConfig()
    assert isinstance(logic._play_intro_once(cfg), Fake) and played == [1] and darks == [True]
    light = MyGeekyConfig(gui_theme="frosted")
    logic._play_intro_once(light)
    assert darks == [True, False]                     # the light theme: the letters stand on the icon's dark badge
    assert cfg.gui_intro_shown and load_config().gui_intro_shown        # remembered on disk
    assert logic._play_intro_once(cfg) is None and played == [1, 1]     # never again

    def broken():
        raise RuntimeError("no screen")
    monkeypatch.setattr(splash, "make_splash", broken)
    assert logic._play_intro_once(MyGeekyConfig()) is None              # a failure just skips it
