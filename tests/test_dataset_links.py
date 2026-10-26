"""A dataset opens when it's clicked: on Home (a new-dataset card, the "new datasets" banner) and in Grow → Data.

Zenodo, Figshare and NCBI links were refused by open_link's safe-link check, so every click on a dataset did nothing."""
from __future__ import annotations

from datetime import date

import pytest

from mygeeky import datasets
from mygeeky.config import MyGeekyConfig
from mygeeky.files import write_json


def _radar(n: int = 4) -> list[dict]:
    today = date.today().isoformat()
    hosts = ["https://zenodo.org/records/1{}", "https://figshare.com/articles/dataset/x/2{}",
             "https://plos.figshare.com/articles/dataset/y/3{}", "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE4{}"]
    return [{"id": f"r{i}", "title": f"Single-cell atlas {i}", "source": "Zenodo", "url": hosts[i % 4].format(i),
             "date": today, "size_mb": 1.0, "license": "cc-by-4.0", "nc": False, "about": "gwas genomics", "term": "gwas"}
            for i in range(n)]


def test_dataset_links_pass_the_safe_link_check(monkeypatch):
    pytest.importorskip("PySide6")
    from mygeeky.gui import app as logic
    opened = []
    monkeypatch.setattr("PySide6.QtGui.QDesktopServices.openUrl", lambda u: opened.append(u.toString()) or True)
    write_json(datasets.RADAR_FILE, {"items": _radar()})
    for it in _radar():
        assert logic.open_link(it["url"]), it["url"]
    catalog = datasets.load()["datasets"]
    assert catalog and all(logic.open_link(d["url"]) for d in catalog), "every dataset in Grow → Data opens"
    assert all(logic.open_link(d["download"]) for d in catalog if d.get("download"))
    assert all(logic.open_link(d["tutorial"]) for d in catalog if d.get("tutorial"))
    assert not logic.open_link("https://zenodo.org.evil.example/records/1"), "only the dataset sites themselves"
    assert not logic.open_link("https://zenodo.org/records/999999"), "a link that isn't one of our datasets stays shut"
    assert not logic.open_link("http://zenodo.org/records/10"), "https only"


def _cards() -> list[dict]:
    return [{"id": f"dataset:{d['id']}", "kind": "dataset", "title": d["title"], "url": d["url"], "sub": "Zenodo · gwas",
             "at": d["date"], "terms": ["gwas"], "source": "Zenodo", "page": "grow:data:new",
             "facts": {"size_mb": 1.0, "license": "cc-by-4.0"}} for d in _radar()]


def test_clicking_datasets_on_home_and_in_data_opens_them(qapp_offscreen, monkeypatch):
    """Real mouse clicks: a dataset card, its Open ↗, the "new datasets" banner, See all in Data, then Data's own
    cards (title, buttons, 👍 / 👎). Every link opens, and nothing falls over."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
    from mygeeky import feed
    from mygeeky.gui.feed_ui import FeedCard
    from tests.test_freshness import _close, _quiet_panel
    opened = []
    monkeypatch.setattr("PySide6.QtGui.QDesktopServices.openUrl", lambda u: opened.append(u.toString()) or True)
    write_json(datasets.RADAR_FILE, {"items": _radar()})
    app, p = _quiet_panel(monkeypatch, MyGeekyConfig(github_username="me", keywords=["gwas"]))
    try:
        p.resize(460, 900)
        p.show()
        home = p.home_page
        home._got(feed.arrange(_cards(), {"today": date.today().isoformat(), "weights": {"gwas": 1.0}}, 90))
        QApplication.processEvents()
        cards = [w for w in home.findChildren(FeedCard) if w.card["kind"] == "dataset"]
        assert cards
        QTest.mouseClick(cards[0], Qt.LeftButton, Qt.NoModifier, QPoint(20, 20))       # the card itself
        assert opened[-1] == cards[0].card["url"]
        b = next(x for x in cards[1].findChildren(QPushButton) if x.objectName() == "open")
        QTest.mouseClick(b, Qt.LeftButton)                                              # its Open ↗
        assert opened[-1] == cards[1].card["url"]
        banner = home.cards_box.itemAt(0).widget()
        assert banner.objectName() == "milestone"                                       # "4 new datasets for you today"
        QTest.mouseClick(banner, Qt.LeftButton, Qt.NoModifier, QPoint(20, 10))
        for _ in range(5):
            QApplication.processEvents()
        assert p.active_tab == "grow" and p._grow_mode == "data:new"
        for mode in ("data:new", "data:for-you"):
            p._set_grow_mode(mode)
            for w in list(p._workers):
                w.wait(5000)
            for _ in range(5):
                QApplication.processEvents()
            before = len(opened)
            area = p._grow_scroll.widget()
            titles = [x for x in area.findChildren(QLabel) if x.cursor().shape() == Qt.PointingHandCursor]
            assert titles, mode
            QTest.mouseClick(titles[0], Qt.LeftButton, Qt.NoModifier, QPoint(5, 5))
            buttons = [x for x in area.findChildren(QPushButton) if x.text().startswith(("⬇", "Page", "📘", "Open"))]
            for x in buttons[:4]:
                QTest.mouseClick(x, Qt.LeftButton)
            assert len(opened) > before, f"{mode}: a click opened nothing"
            thumbs = [x for x in area.findChildren(QPushButton) if x.text() in ("👍", "👎")]
            for x in thumbs[:2]:                                                        # voting redraws the list
                if x.isVisible():
                    QTest.mouseClick(x, Qt.LeftButton)
                    QApplication.processEvents()
        p._switch_tab("home")
        QApplication.processEvents()
    finally:
        _close(p)
