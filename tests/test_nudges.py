"""The cards that ask again for what setup skipped (nudges.py; the phone's lib/nudges.ts): the schedule the maker asked
for, and the phone giving the same answers as the computer on the same days."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

import phone
from mygeeky import nudges as N

ALL = ["data", "orcid", "github"]


def days(n: int, start: date = date(2026, 11, 2)) -> list[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def shows(state, page, day, missing=ALL) -> str:
    return N.pick(state, page, day, missing)


def test_never_in_the_first_week_of_use():
    s = N.fresh()
    seen = [shows(s, "model:month", d) for d in days(6)]
    assert seen == [""] * 6
    assert shows(s, "model:month", days(7)[-1]) == "data"         # the 7th day of use


def test_days_of_use_not_calendar_days():
    s = N.fresh()
    for d in days(6, date(2026, 1, 1)):                          # six days in January...
        shows(s, "model:month", d)
    assert shows(s, "model:month", "2026-03-01") == "data"       # ...the 7th, months later, counts as day 7
    s2 = N.fresh()
    for _ in range(10):                                          # ten visits on one day are one day of use
        shows(s2, "model:month", "2026-01-01")
    assert s2["days"] == 1


def test_not_now_two_days_then_weekly_after_three():
    s = N.fresh()
    when = []
    for i, d in enumerate(days(50)):
        k = shows(s, "model:month", d, ["data"])
        if k:
            when.append(i + 1)                                   # the day of use it showed
            N.skip(s, k)
    # day 7, then +2, +2, then weekly (+7) after the third "Not now"
    assert when[:6] == [7, 9, 11, 18, 25, 32]


def test_gone_two_months_after_it_first_appeared():
    s = N.fresh()
    ds = days(90)
    seen = []
    for d in ds:
        k = shows(s, "model:month", d, ["data"])
        if k:
            seen.append(d)
            N.skip(s, k)
    first = date.fromisoformat(seen[0])
    assert all((date.fromisoformat(d) - first).days < N.GIVE_UP for d in seen)
    assert (date.fromisoformat(seen[-1]) - first).days >= 50     # it kept coming, weekly, until then


def test_dont_ask_again_and_linked_stop_it():
    s = N.fresh()
    for d in days(7):
        k = shows(s, "model:month", d, ["data"])
    assert k == "data"
    N.never(s, "data")
    assert all(shows(s, "model:month", d, ["data"]) == "" for d in days(30, date(2026, 12, 1)))
    s2 = N.fresh()
    assert all(shows(s2, "model:month", d, []) == "" for d in days(30))   # nothing missing: never a card


def test_each_card_only_where_it_helps_and_one_kind_a_day():
    s = N.fresh()
    for d in days(6):
        shows(s, "badges", d)
    day = days(7)[-1]
    assert shows(s, "badges", day) == ""                          # not a place of any card
    assert shows(s, "researchers:network", day) == "orcid"        # ORCID on Researchers...
    assert shows(s, "model:month", day) == ""                     # ...so not saving today, on the same day
    assert shows(s, "you:cited", day) == "orcid"                  # ORCID again, on another of its pages
    nxt = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
    assert shows(s, "model:month", nxt) == "data"                 # saving comes first when both are due
    assert shows(s, "repos:help", nxt) == ""                      # GitHub waits for another day


def test_every_place_is_a_real_page_on_both_apps():
    from mygeeky import navtree
    from mygeeky.gui.qt_panel import panel_tree
    desk = {n["id"] for n in navtree.walk(panel_tree(True, True))}
    said = phone.run("""
import { phoneTree, walk } from './lib/nav-tree.ts';
out(walk(phoneTree(true, true)).map((n) => n.id));
""") if phone.node_ok() else None
    for page, place in N.PAGE_PLACE.items():
        assert any(place in places for places in N.PLACES.values()), place
        if said is not None:                                     # (the phone's tree needs Node 22.6+)
            assert page in desk or page in said, page
    for places in N.PLACES.values():                             # every place has a page on the computer and the phone
        for place in places:
            assert any(N.place_of(p) == place for p in desk), place
            if said is not None:
                assert any(N.place_of(p) == place for p in said), place
    # the computer's own ids in the table are real pages on the computer, Node or not
    assert {p for p in N.PAGE_PLACE if p.startswith(("model:", "market:", "chances:", "grow:"))} <= desk


# --------------------------------------------------------------------------- the phone, the same answers
STEPS = []
for i, d in enumerate(days(80)):
    page = ["model:month", "you:cited", "researchers:new", "repos:help", "you:month", "chances:jobs", "badges",
            "market:repos", "grow:highlights", "you:model"][i % 10]
    missing = ALL if i < 40 else ["orcid", "github"]              # saving set up halfway through
    STEPS.append({"day": d, "page": page, "missing": missing, "act": "never" if i == 61 else "skip" if i % 3 else ""})


def desktop_trace():
    s, trace = N.fresh(), []
    for st in STEPS:
        k = N.pick(s, st["page"], st["day"], st["missing"])
        trace.append(k)
        if k and st["act"] == "skip":
            N.skip(s, k)
        elif k and st["act"] == "never":
            N.never(s, k)
    return trace, s


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+")
def test_the_phone_gives_the_same_answers():
    said = phone.run("""
import * as N from './lib/nudges.ts';
const s = N.fresh(), trace = [];
for (const st of INPUT.steps) {
  const k = N.pick(s, st.page, st.day, st.missing);
  trace.push(k);
  if (k && st.act === 'skip') N.skip(s, k);
  else if (k && st.act === 'never') N.never(s, k);
}
out({ trace, state: s, texts: ['data', 'orcid', 'github'].map((k) => N.text(k, 'phone')),
      places: N.PLACES, pages: N.PAGE_PLACE, consts: [N.START, N.AGAIN, N.WEEKLY_AFTER, N.WEEK, N.GIVE_UP] });
""", {"steps": STEPS})
    trace, state = desktop_trace()
    assert said["trace"] == trace
    assert said["state"] == json.loads(json.dumps(state))
    assert said["texts"] == [N.text(k, "phone") for k in ALL]
    assert said["places"] == {k: list(v) for k, v in N.PLACES.items()}
    assert said["pages"] == N.PAGE_PLACE
    assert said["consts"] == [N.START, N.AGAIN, N.WEEKLY_AFTER, N.WEEK, N.GIVE_UP]
    assert sum(1 for k in trace if k) >= 8                        # the scenario really shows cards


def test_kept_on_this_device_and_survives_a_bad_file(tmp_path, monkeypatch):
    from mygeeky import config
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    s = N.load()
    assert s == N.fresh()
    N.used(s, "2026-11-02")
    N.save(s)
    assert N.load()["days"] == 1
    (tmp_path / "nudges.json").write_text("{not json", encoding="utf-8")
    assert N.load() == N.fresh()


# --------------------------------------------------------------------------- the computer's card on the real panel
def _panel(cfg_kwargs=None):
    from PySide6.QtWidgets import QApplication
    from mygeeky.config import MyGeekyConfig
    from mygeeky.gui.qt_panel import MyGeekyPanel
    p = MyGeekyPanel(MyGeekyConfig(**(cfg_kwargs or {"keywords": ["gwas"]})))
    p.resize(460, 760)
    p.show()
    QApplication.processEvents()
    return p


def _a_week_used():
    s = N.fresh()
    for d in days(6, date(2026, 1, 1)):
        N.used(s, d)
    N.save(s)


def test_the_card_on_the_panel_and_its_buttons(qapp_offscreen):
    from mygeeky import navtree
    _a_week_used()
    p = _panel()                                   # keywords only: no GitHub, no ORCID, nothing saved anywhere
    try:
        p._nav_open(navtree.find(p.nav_tree, "model:month"))
        assert p.nudge_card.isVisible() and p.nudge_card.key == "data"
        assert "Google Drive (recommended)" in p.nudge_card.text.text()
        assert p.nudge_card.text.textFormat() == p.nudge_card.text.textFormat().PlainText
        p.nudge_card.later.click()                  # Not now
        assert not p.nudge_card.isVisible()
        s = N.load()
        assert s["cards"]["data"]["skips"] == 1 and s["cards"]["data"]["next"] == s["days"] + N.AGAIN
        p._nav_open(navtree.find(p.nav_tree, "model:model"))
        assert not p.nudge_card.isVisible()         # not again today, on another of its pages
        p._nav_open(navtree.find(p.nav_tree, "badges"))
        assert not p.nudge_card.isVisible()
    finally:
        p.close()


def test_its_action_opens_accounts_and_dont_ask_again_stops_it(qapp_offscreen):
    from mygeeky import navtree
    _a_week_used()
    p = _panel()
    try:
        p._nav_open(navtree.find(p.nav_tree, "model:cited"))
        assert p.nudge_card.isVisible() and p.nudge_card.key == "orcid"
        p.nudge_card.go.click()
        assert p.settings_panel.isVisible()         # Settings -> Accounts, where ORCID is added
        assert not p.nudge_card.isVisible()
        p.nudge_card.act("orcid", "never")
        assert N.load()["cards"]["orcid"]["never"] is True
    finally:
        p.close()


def test_nothing_missing_no_card_ever(qapp_offscreen):
    from mygeeky import navtree
    _a_week_used()
    p = _panel({"keywords": ["gwas"], "github_username": "me"})
    try:
        p._sign_states = {"github": "on", "orcid": "on", "data": "on", "beacon": "off"}
        for page in ("model:month", "model:cited", "repos", "researchers"):
            p._nav_open(navtree.find(p.nav_tree, page) or navtree.find(p.nav_tree, page + ":new"))
            assert not p.nudge_card.isVisible(), page
    finally:
        p.close()
