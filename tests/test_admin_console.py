"""The Admin console (gui/qt_panel.py, trace_ui.py, support_ui.py): nine sections from its own menu, the Dashboard's
Needs you and TRACE plots, a news item accepted from its card (and logged), Publish listing exactly what would go out
with each link's site, Support showing what users wrote as plain text -- and the phone's overview file holding counts
only, read the same way by the phone."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

import phone
from mygeeky import admin, adminaudit, support, trace
from mygeeky.config import MyGeekyConfig

NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")


def _seed():
    trace.add_feed("youtube", "UC" + "a" * 22, "Two Minute Papers", "news")
    st = trace.load()
    sid = next(iter(st["sources"]))
    st["items"]["tr-0123456789ab"] = {
        "id": "tr-0123456789ab", "kind": "news", "sid": sid, "title": "A 1B model beats 70B models at maths",
        "summary": "<b>Example</b> Labs released a small model.", "why": "Cheaper to run.", "topic": "small language models",
        "keywords": ["llm"], "url": "https://www.youtube.com/watch?v=abc", "sources": ["https://www.youtube.com/watch?v=abc",
                                                                                     "https://example-labs.ai/blog"],
        "grounded": 1.0, "status": "new", "at": NOW, "published": NOW, "from": "Two Minute Papers", "p": 0.71,
        "features": {"grounded": 1.0, "corroboration": 0.33, "source": 0.5, "fresh": 1.0, "linked": 1.0, "duplicate": 0.0},
        "checks": [[True, "headline found in what was fetched (100%)"], [True, "2 independent site(s)"]]}
    st["mentions"] = {"small language models": {NOW[:10]: 6}}
    st["triggers"] = [{"id": "t1", "sid": sid, "at": NOW, "kind": "news", "from": "Two Minute Papers",
                       "title": "A 1B model beats 70B models at maths", "url": "", "result": "2 source(s) → 1 item in Review",
                       "followed": True}]
    trace.save(st)
    sst = support.load()
    sst["threads"]["<m1@x>"] = {"id": "<m1@x>", "who": "Rana", "addr": "rana.k@uni.edu", "subject": "<img src=x> Panel won't open",
                                "date": "today", "seen": NOW, "body": "Hi <script>x</script>, it won't open.", "tag": "Problem",
                                "status": "new", "references": "", "draft": "", "replies": []}
    support.save(sst)


@pytest.fixture
def console(qapp_offscreen, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from mygeeky.gui import app as logic
    from mygeeky.gui.qt_panel import MyGeekyPanel
    _seed()
    monkeypatch.setattr(logic, "is_admin", lambda cfg: True)
    monkeypatch.setattr(logic, "trace_run", lambda manual=False: {"message": "ok"})       # no network in tests
    p = MyGeekyPanel(MyGeekyConfig(github_username="alsammanalsamman", keywords=["llm"]))
    p.resize(1120, 900)
    p.show()
    p._switch_tab("admin")
    for _ in range(10):
        QApplication.processEvents()
    p._render_admin()
    yield p
    p.close()


def test_nine_sections_from_its_own_menu(console):
    from mygeeky.gui.qt_panel import ADMIN_PARTS
    assert list(console.admin_menu_btns) == [p for p, *_ in ADMIN_PARTS] and len(ADMIN_PARTS) == 9
    for part in console.admin_menu_btns:
        console.admin_menu_btns[part].click()
        assert console._admin_part == part
        assert [p for p, box in console.admin_sections.items() if box.isVisibleTo(console)] == [part]
    console._set_admin_part("overview")                       # an older name still lands somewhere sensible
    assert console._admin_part == "dashboard"


def test_the_dashboard_says_what_needs_you_and_draws_trace(console):
    console._set_admin_part("dashboard")
    labels = [console.admin_needs.itemAt(i).widget().text() for i in range(console.admin_needs.count())]
    assert any("News to review" in x for x in labels) and any("Support emails" in x for x in labels)
    assert console.trace_plots.funnel.data and console.trace_plots.heat.data["heat"][0]["topic"] == "small language models"
    assert "Rising topics" in " ".join(labels)


def test_a_news_item_is_accepted_from_its_card_and_logged(console):
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
    console._set_admin_part("review")
    texts = [w.text() for w in console.trace_review.findChildren(QLabel)]
    assert "<b>Example</b> Labs released a small model." in texts                  # plain text, never HTML
    assert any("youtube.com · example-labs.ai" in x for x in texts)
    accept = next(b for b in console.trace_review.findChildren(QPushButton) if b.text() == "Accept")
    accept.click()
    for _ in range(50):
        QApplication.processEvents()
        if trace.load()["items"]["tr-0123456789ab"]["status"] != "new":
            break
    assert trace.load()["items"]["tr-0123456789ab"]["status"] == "accepted"
    assert adminaudit.recent()[0]["what"].startswith("Accepted news")
    console._render_admin()
    assert "📰 A 1B model beats 70B models at maths  →  youtube.com" in console.admin_waiting.text()   # Publish shows it


def test_support_shows_what_users_wrote_as_text(console):
    from PySide6.QtCore import Qt
    console._set_admin_part("support")
    page = console.support_page
    assert page.threads and page.body.textFormat() == Qt.PlainText and "<script>" in page.body.text()
    assert page.head.textFormat() == Qt.PlainText and "<img src=x>" in page.head.text()


def test_the_phones_overview_holds_counts_only():
    _seed()
    out = admin.write_summary()
    text = json.dumps(out)
    for private in ("rana", "Rana", "@", "example-labs", "Two Minute Papers"):
        assert private not in text, private
    assert out["waiting"]["news"] == 1 and out["waiting"]["support"] == 1
    assert admin.SUMMARY_FILE.exists()


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+")
def test_the_phone_reads_the_overview_the_same_way():
    _seed()
    out = admin.summary()
    said = phone.run("""
import { cleanSummary } from './lib/admin.ts';
out(cleanSummary(INPUT.s));
""", {"s": {**out, "adoption": {**out["adoption"], "stars": -5}, "waiting": {**out["waiting"], "news": "lots"}}}, name="adminsum")
    assert said["waiting"]["support"] == 1 and said["waiting"]["news"] == 0            # bad values become 0
    assert said["adoption"]["stars"] is None and said["trace"]["rising"] == out["trace"]["rising"]
