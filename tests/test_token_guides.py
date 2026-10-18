"""The picture guides for making GitHub tokens: the same steps and drawings on the desktop and the phone."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "src" / "mygeeky" / "data" / "token_guides.json"
PHONE = ROOT / "mobile" / "src" / "data" / "token-guides.json"


def _generator():
    spec = importlib.util.spec_from_file_location("token_guides", ROOT / "tools" / "token_guides.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_both_apps_ship_exactly_what_the_generator_writes():
    built = _generator().build()
    assert json.loads(DESKTOP.read_text(encoding="utf-8")) == built, "run: python tools/token_guides.py"
    assert PHONE.read_text(encoding="utf-8") == DESKTOP.read_text(encoding="utf-8")
    assert built["seconds"] == 4                                   # each step stays 4 s unless you pick one


def test_each_guide_says_exactly_what_to_choose():
    g = json.loads(DESKTOP.read_text(encoding="utf-8"))["guides"]
    text = {k: " ".join([s["title"] + " " + s["text"] for s in v["steps"]] + v["tips"]) for k, v in g.items()}
    assert "mygeeky-data" in text["data"] and "Contents" in text["data"] and "Read and write" in text["data"]
    assert "mygeeky-beacon" in text["signals"] and "Signals is optional" in text["signals"]
    assert "Public repositories" in text["read"] and "Followers" in text["read"] and "Read-only" in text["read"]
    for k, t in text.items():
        assert "The name can be anything" in t and "several tokens for the same repo" in t, k
        assert g[k]["url"] == "https://github.com/settings/personal-access-tokens/new"


def test_the_drawings_use_only_plain_shapes_both_apps_draw():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QByteArray
    from PySide6.QtSvg import QSvgRenderer
    allowed = {"svg", "rect", "text", "line", "circle"}
    for k, guide in json.loads(DESKTOP.read_text(encoding="utf-8"))["guides"].items():
        assert len(guide["steps"]) >= 6, k
        for i, step in enumerate(guide["steps"]):
            tags = {re.sub(r"^\{.*\}", "", e.tag) for e in ET.fromstring(step["svg"]).iter()}
            assert tags <= allowed, (k, i, tags - allowed)
            assert QSvgRenderer(QByteArray(step["svg"].encode())).isValid(), (k, i)


def test_the_desktop_guide_moves_on_by_itself_and_stops_when_you_pick(monkeypatch):
    pytest.importorskip("PySide6")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from mygeeky.gui.token_guide import TokenGuide
    guide = TokenGuide("data")
    assert len(guide.dots) == len(guide.steps) and guide.timer.isActive() and guide.timer.interval() == 4000
    assert guide.step_title.text().startswith("1. ")
    guide.timer.timeout.emit()                                     # 4 s later
    assert guide.at == 1 and guide.step_title.text().startswith("2. ")
    guide.dots[4].click()                                          # you pick step 5
    assert guide.at == 4 and not guide.timer.isActive()           # and it stays there
    guide.next_btn.click()
    assert guide.at == 5
    opened = []
    monkeypatch.setattr("mygeeky.gui.token_guide.QDesktopServices.openUrl", lambda u: opened.append(u.toString()))
    guide.open_btn.click()
    assert opened == ["https://github.com/settings/personal-access-tokens/new"]


def test_setup_shows_the_guides_where_a_token_is_made():
    pytest.importorskip("PySide6")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from mygeeky.gui import setup_wizard as sw
    from mygeeky.gui.token_guide import TokenGuide
    w = sw.SetupWizard()
    pages = {type(w.page(i)).__name__: w.page(i) for i in w.pageIds()}
    assert isinstance(pages["TokenPage"].guide, TokenGuide) and pages["TokenPage"].guide.guide["key"] == "read"
    assert isinstance(pages["SignalsPage"].guide, TokenGuide) and pages["SignalsPage"].guide.guide["key"] == "signals"
    g = pages["SignalsPage"].guide                     # setup pages can't scroll: folded until asked for
    assert g.body.isHidden() and not g.timer.isActive()
    g.show_btn.click()
    assert not g.body.isHidden() and g.timer.isActive() and g.at == 0


def test_the_phone_shows_them_in_its_four_token_places():
    src = ROOT / "mobile" / "src"
    places = {"components/setup-steps.tsx": "data", "components/you-parts.tsx": "data",
              "components/signals-view.tsx": "signals", "app/setup.tsx": "read"}
    for f, key in places.items():
        assert f'<TokenGuide which="{key}" />' in (src / f).read_text(encoding="utf-8"), f
