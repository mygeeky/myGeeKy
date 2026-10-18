"""Building a protocol says so: "✓ Your protocol is built…" above your protocols, once, on both apps."""

import re
from pathlib import Path

import pytest

from mygeeky import protocols
from mygeeky.config import MyGeekyConfig
from mygeeky.gui.qt_panel import protocol_built_text

PHONE = Path(__file__).resolve().parents[1] / "mobile" / "src" / "components" / "protocols-view.tsx"


def test_the_message_names_the_protocol_and_its_stages():
    assert protocol_built_text("R for data analysis", 5, False) == \
        "✓ Your protocol is built: R for data analysis · 5 stages. It's open below."
    assert protocol_built_text("GWAS", 1, True) == "✓ Protocol started: GWAS (reviewed) · 1 stage. It's open below."


def test_the_phone_says_the_same_words():
    ts = PHONE.read_text(encoding="utf-8")
    body = re.search(r"export function builtText\(.*?\n}\n", ts, re.S).group(0)
    for words in ("Protocol started: ${title} (reviewed)", "Your protocol is built: ${title}",
                  "✓ ${what} · ${stages} stage${stages !== 1 ? 's' : ''}. It's open below."):
        assert words in body, words


def test_the_panel_says_it_after_building_and_forgets_it_at_the_next_action(monkeypatch):
    pytest.importorskip("PySide6")
    from tests.test_freshness import _close, _quiet_panel
    monkeypatch.setattr("mygeeky.gui.app.growth_due", lambda cfg: False)
    cfg = MyGeekyConfig(github_username="me", keywords=["gwas"])
    pid = protocols.start(cfg, protocols.fill(protocols.template("R", "data analysis"), [], {"resources": []}))
    app, panel = _quiet_panel(monkeypatch, cfg)
    try:
        from PySide6.QtWidgets import QLabel

        def shown() -> str:
            for w in list(panel._workers):
                w.wait(5000)
            app.processEvents()
            from PySide6.QtCore import QCoreApplication, QEvent
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)   # the screen before is really gone
            return " ".join(lbl.text() for lbl in panel.grow_area.parentWidget().findChildren(QLabel))

        panel._switch_tab("grow")
        panel._set_grow_mode("paths")
        assert "Your protocol is built" not in shown()
        panel._on_protocol_built({"id": pid, "reviewed": False})
        assert "✓ Your protocol is built: R for data analysis · 5 stages. It's open below." in shown()
        panel._protocol_act(pid, "tick", panel._growth["paths"][0]["stages"][0]["id"])
        assert "Your protocol is built" not in shown()
    finally:
        _close(panel)
