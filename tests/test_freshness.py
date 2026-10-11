from datetime import datetime, timedelta, timezone

from mygeeky import freshness
from mygeeky.config import MyGeekyConfig

T0 = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
CFG = MyGeekyConfig(github_username="me")


def _people(*names):
    return [{"username": n} for n in names]


def test_seen_people_make_room_then_come_back_after_their_rest():
    freshness.mark_seen(["person:ann"], now=T0)
    data = freshness.load()
    shown = freshness.arrange(CFG, "person", _people("ann", "bob", "cy"), data=data, now=T0 + timedelta(days=1))
    assert [p["username"] for p in shown] == ["bob", "cy"] and all(p["_fresh"] == "new" for p in shown)
    later = freshness.arrange(CFG, "person", _people("ann", "bob"), data=data,
                              now=T0 + timedelta(days=CFG.fresh_people_days, minutes=1))
    assert [(p["username"], p["_fresh"]) for p in later] == [("bob", "new"), ("ann", "again")]   # new ones first


def test_seen_often_and_never_clicked_rests_much_longer():
    for d in range(CFG.fresh_ignored_after):
        freshness.mark_seen(["repo:x/y"], now=T0 + timedelta(hours=d))
    data = freshness.load()
    after_a_week = T0 + timedelta(days=CFG.fresh_repos_days + 1)
    assert freshness.state(CFG, "repo:x/y", data, now=after_a_week) == "resting"
    assert freshness.state(CFG, "repo:x/y", data, now=T0 + timedelta(days=CFG.fresh_ignored_days + 1)) == "again"


def test_a_clicked_person_and_read_news_never_come_back():
    freshness.mark_seen(["person:ann"], clicked=True, now=T0)
    freshness.mark_seen(["news:https://example.org/a"], now=T0)
    data = freshness.load()
    far = T0 + timedelta(days=90)
    assert freshness.state(CFG, "person:ann", data, now=far) == "resting"
    assert freshness.state(CFG, "news:https://example.org/a", data, now=far) == "resting"


def test_market_sinks_seen_rows_and_activity_only_dims_them():
    freshness.mark_seen(["market:a/top", "activity:e1"], now=T0)
    data = freshness.load()
    rows = [{"repo": "a/top"}, {"repo": "b/two"}, {"repo": "c/three"}]
    board = freshness.arrange(CFG, "market", rows, data=data, now=T0 + timedelta(hours=1))
    assert [r["repo"] for r in board] == ["b/two", "c/three", "a/top"] and board[-1]["_fresh"] == "seen"
    feed = freshness.arrange(CFG, "activity", [{"id": "e1"}, {"id": "e2"}], data=data, now=T0)
    assert [(e["id"], e["_fresh"]) for e in feed] == [("e1", "seen"), ("e2", "new")]     # a timeline keeps its order


def test_running_low_and_gentle_top_ups():
    shown = [{"_fresh": "new"}, {"_fresh": "again"}, {"_fresh": "again"}, {"_fresh": "again"}]
    assert freshness.running_low(shown, limit=6) and not freshness.running_low(shown * 2, limit=4)
    assert freshness.top_up_due("person", hours=6, now=T0)
    freshness.note_top_up("person", now=T0)
    assert not freshness.top_up_due("person", hours=6, now=T0 + timedelta(hours=5))
    assert freshness.top_up_due("person", hours=6, now=T0 + timedelta(hours=7))


def test_old_entries_are_forgotten_so_the_file_stays_small():
    freshness.mark_seen(["news:old"], now=datetime.now(timezone.utc) - timedelta(days=freshness.KEEP_DAYS + 5))
    freshness.mark_seen(["news:recent"])
    assert set(freshness.load()["items"]) == {"news:recent"}


def test_keys_are_stable_and_case_blind():
    assert freshness.item_key("person", {"username": "Ann"}) == freshness.item_key("person", {"username": "ann"})
    assert freshness.item_key("repo", {"full_name": "A/B"}) == "repo:a/b"
    assert freshness.item_key("news", {"title": "Only a title"}) == "news:only a title"
    assert freshness.item_key("news", {}) == ""


def _quiet_panel(monkeypatch, cfg):
    """A real panel with everything that talks to the network switched off."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from mygeeky.gui import app as logic
    for name, value in (("get_activity", lambda cfg, force=False: {"events": []}),
                        ("get_update_info", lambda cfg: {"show": False}),
                        ("get_token_warnings", lambda cfg: []),
                        ("sync_enabled", lambda cfg: False),
                        ("suggestions_auto_refresh_due", lambda cfg, now=None: False),
                        ("contributions_top_up_due", lambda cfg, now=None: False)):
        monkeypatch.setattr(logic, name, value)
    for name in ("news_refresh_due", "trends_due", "market_refresh_due", "hf_models_due"):
        monkeypatch.setattr(logic, name, lambda cfg: False)
    from mygeeky.gui.qt_panel import MyGeekyPanel
    return app, MyGeekyPanel(cfg)


def _close(panel):
    for t in (panel.ticker, panel._activity_timer, panel._signals_timer, panel._update_timer, panel._news_timer,
              panel._dock_guard, panel._sync_timer, *panel._seen_timers, panel._repos_topup_timer):
        t.stop()
    for w in list(panel._workers):
        w.wait(3000)
    panel.close()
    panel.deleteLater()


def test_the_panel_lets_what_you_saw_make_room_but_never_while_you_read(monkeypatch):
    import pytest
    pytest.importorskip("PySide6")
    from mygeeky.storage import log_suggestions
    stamp = datetime.now(timezone.utc).isoformat()
    log_suggestions([{"username": u, "score": s, "list": "followback", "timestamp": stamp,
                      "profile_url": f"https://github.com/{u}"} for u, s in (("ann", .9), ("bob", .8), ("cy", .7))])
    cfg = MyGeekyConfig(github_username="me", max_suggestions_returned=2, domain_highlight_count=0)
    app, panel = _quiet_panel(monkeypatch, cfg)
    try:
        panel.show()
        panel.unfold()
        panel._switch_tab("suggestions")
        for _ in range(5):
            app.processEvents()
        from mygeeky.gui.qt_panel import SuggestionCard
        def showing():
            return [c.property("fresh_key") for c in panel.followback_area.parentWidget().findChildren(SuggestionCard)
                    if c.isVisible()]
        assert showing() == ["person:ann", "person:bob"]
        assert panel.tab_buttons["suggestions"]._count == 2              # the planet says: 2 new
        for _ in range(4):                                                # 2 s with both cards on screen
            panel._track_seen()
        assert panel._seen_pending == {"person:ann", "person:bob"}
        assert panel.tab_buttons["suggestions"]._count == 0
        assert showing() == ["person:ann", "person:bob"]                 # nothing moved while reading
        panel._switch_tab("news")
        panel._switch_tab("suggestions")                                  # come back to People
        for _ in range(5):
            app.processEvents()
        assert showing() == ["person:cy"]                                 # the one you hadn't seen
        assert set(freshness.load()["items"]) >= {"person:ann", "person:bob"}
    finally:
        _close(panel)


def test_a_background_search_waits_until_you_next_open_the_tab(monkeypatch):
    import pytest
    pytest.importorskip("PySide6")
    from mygeeky.storage import log_suggestions
    stamp = datetime.now(timezone.utc).isoformat()
    log_suggestions([{"username": "ann", "score": .9, "list": "followback", "timestamp": stamp}])
    cfg = MyGeekyConfig(github_username="me", max_suggestions_returned=3, domain_highlight_count=0)
    app, panel = _quiet_panel(monkeypatch, cfg)
    try:
        panel.show()
        panel.unfold()
        panel._switch_tab("suggestions")
        app.processEvents()
        from mygeeky.gui.qt_panel import SuggestionCard

        def showing():
            return sorted(c.property("fresh_key") for c in panel.followback_area.parentWidget().findChildren(SuggestionCard)
                          if c.property("fresh_key"))
        assert showing() == ["person:ann"]
        # a quiet background search found two more people while you were reading People
        log_suggestions([{"username": u, "score": .8, "list": "followback", "timestamp": stamp} for u in ("bob", "cy")])
        panel._on_quiet_suggestions({"followback": []})
        assert showing() == ["person:ann"] and "suggestions" in panel._fresh_waiting   # held, nothing jumped
        assert panel.tab_buttons["suggestions"]._count == 3                            # but the planet knows
        panel._switch_tab("news")
        panel._switch_tab("suggestions")
        app.processEvents()
        assert showing() == ["person:ann", "person:bob", "person:cy"]
    finally:
        _close(panel)


def test_real_shaped_records_work_and_a_failure_falls_back_to_plain_lists(monkeypatch):
    """The 0.21.0 start-up crash: a saved repo's "fit" is a dict of parts, not a number."""
    from mygeeky.gui import app as logic
    from mygeeky.storage import log_contributions
    stamp = datetime.now(timezone.utc).isoformat()
    log_contributions([{"full_name": f"lab/tool{i}", "timestamp": stamp,
                        "fit": {"content_similarity": 0.3, "language_match": 1.0, "recency": 1.0, "fit": 0.5 - i / 10}}
                       for i in range(3)])
    cfg = MyGeekyConfig(github_username="me", contribute_max_returned=2)
    assert [r["full_name"] for r in logic.get_contributions(cfg)] == ["lab/tool0", "lab/tool1"]   # saved best first

    def broken(*a, **k):
        raise RuntimeError("seen.json went wrong somehow")
    monkeypatch.setattr(freshness, "arrange", broken)
    assert [r["full_name"] for r in logic.get_contributions(cfg)] == ["lab/tool0", "lab/tool1"]   # still shows
    assert logic.get_suggestions(cfg)["followback"] == []


def test_one_tab_failing_never_stops_the_panel_from_opening(monkeypatch):
    import pytest
    pytest.importorskip("PySide6")
    from mygeeky.gui import app as logic
    from mygeeky import crashreport
    from mygeeky.config import LOG_DIR

    def broken(cfg):
        raise TypeError("float() argument must be a string or a real number, not 'dict'")
    monkeypatch.setattr(logic, "get_contributions", broken)          # what crashed 0.21.0 at start-up
    app, panel = _quiet_panel(monkeypatch, MyGeekyConfig(github_username="me"))
    try:
        assert panel.tab_buttons and panel.content_stack.count() >= 5         # the panel opened
        reports = crashreport.pending(LOG_DIR)
        assert reports and "_load_contributions" in reports[0].read_text(encoding="utf-8")   # and you're told
    finally:
        _close(panel)
