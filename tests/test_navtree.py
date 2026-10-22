"""Moving around: the groups, a level with its back planet, where a tap leads, and the phone agreeing."""
from __future__ import annotations

import json

import pytest

import phone
from mygeeky import navtree as nt


def sample() -> dict:
    n = nt.node
    return nt.finish(n("home", "Home", children=[
        n("you", "You", "#ffd24a", children=[n("you:month", "My month", tab="you", part="month"), n("you:badges", "Badges", tab="badges")]),
        n("world", "World", "#eab308", children=[
            n("news", "News", tab="news", children=[n("news:airace", "AI race", tab="news", part="airace"),
                                                   n("news:headlines", "Headlines", tab="news", part="headlines")]),
            n("papers", "Papers", tab="papers"), n("models", "AI models", tab="market", part="models")]),
        n("repos", "Repos", "#7fd8ff", children=[n("repos:rising", "Rising", tab="market", part="repos")]),
    ]))


def test_a_level_shows_a_back_planet_named_after_where_it_goes():
    t = sample()
    assert nt.level(t) == {"back": None, "items": ["you", "world", "repos"]}
    assert nt.level(nt.find(t, "world"))["back"] == {"to": "home", "label": "All", "color": "#ff6fd8"}
    assert nt.level(nt.find(t, "news")) == {"back": {"to": "world", "label": "World", "color": "#eab308"},
                                            "items": ["news:airace", "news:headlines"]}
    assert nt.find(t, "news:airace")["color"] == "#eab308", "parts take their group's colour"


def test_taps():
    t = sample()
    assert nt.tap(t, "home", "world", "you:month") == {"at": "world", "open": "news:airace"}, "a group opens its first page"
    assert nt.tap(t, "world", "news", "news:headlines") == {"at": "news", "open": "news:headlines"}, "already inside: kept"
    assert nt.tap(t, "news", "news:headlines", "news:airace") == {"at": "news", "open": "news:headlines"}
    assert nt.tap(t, "news", "back", "news:headlines") == {"at": "world", "open": "news:headlines"}
    assert nt.tap(t, "home", "back", "x") == {"at": "home", "open": "x"}


def test_the_page_you_are_on():
    t = sample()
    assert nt.leaf_for(t, "market", "repos")["id"] == "repos:rising"
    assert nt.leaf_for(t, "news", "")["id"] == "news:airace", "a tab with parts: its first"
    assert nt.leaf_for(t, "papers")["id"] == "papers" and nt.leaf_for(t, "nope") is None


def test_rows_and_order():
    assert [nt.rows(n) for n in (2, 6, 7, 8)] == [[2], [6], [4, 3], [4, 4]]
    assert nt.ordered(["live", "activity", "people"], False, ("activity",)) == ["live", "people", "activity"]
    assert nt.ordered(["live", "activity"], True, ("activity",)) == ["live", "activity"]


def test_the_panel_tree_has_every_tab():
    from mygeeky.gui.qt_panel import TABS, panel_tree
    t = panel_tree(True, True)
    tabs = {n["tab"] for n in nt.walk(t) if n["tab"]}
    assert tabs == set(TABS), "every tab is somewhere under a group"
    assert [g["id"] for g in t["children"]] == ["feed"] + [g["id"] for g in nt.GROUPS] + ["help"]   # 🏠 Home, the groups, ❓ Help
    assert "admin" not in {n["tab"] for n in nt.walk(panel_tree(False, False))}
    circle = [c["tab"] for c in nt.find(panel_tree(False, False), "circle")["children"]]
    assert circle[-2:] == ["activity", "signals"], "without GitHub, what needs it goes last"


def plain(n: dict) -> dict:
    return {"id": n["id"], "label": n["label"], "color": n["color"], "icon": n.get("icon", ""), "tab": n["tab"],
            "part": n["part"], "children": [plain(c) for c in n["children"]]}


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_moves_the_same_way():
    t = sample()
    taps = [["home", "world", "you:month"], ["world", "news", "news:headlines"], ["news", "back", "news:headlines"],
            ["news", "news:headlines", "news:airace"], ["home", "back", "x"], ["world", "nope", "papers"]]
    said = phone.run("""
import * as N from './lib/nav-tree.ts';
const [raw, taps, ids] = INPUT;
const t = N.finish(raw);
const ph = N.phoneTree(false, false);
out({ groups: N.GROUPS, root: N.ROOT_LABEL, levels: ids.map((id: string) => N.level(N.find(t, id)!)),
  taps: taps.map(([a, p, o]: string[]) => N.tap(t, a, p, o)), rows: [2, 6, 7, 8].map(N.rows),
  leaf: [N.leafFor(t, 'market', 'repos')?.id, N.leafFor(t, 'news', '')?.id, N.leafFor(t, 'nope')],
  phoneGroups: ph.children.map((g) => g.id), phoneCircle: N.find(ph, 'circle')!.children.map((c) => c.id),
  phoneTabs: [...new Set(N.walk(ph).map((n) => n.tab).filter(Boolean))].sort() });
""", [plain(t), taps, ["home", "world", "news", "repos"]])
    assert said["groups"] == nt.GROUPS and said["root"] == nt.ROOT_LABEL
    assert said["levels"] == [nt.level(nt.find(t, i)) for i in ("home", "world", "news", "repos")]
    assert said["taps"] == [nt.tap(t, *x) for x in taps]
    assert said["rows"] == [nt.rows(n) for n in (2, 6, 7, 8)]
    assert said["leaf"] == ["repos:rising", "news:airace", None]
    assert said["phoneGroups"] == ["feed"] + [g["id"] for g in nt.GROUPS] + ["help"]   # 🏠 Home first, ❓ Help last, as on the computer
    assert said["phoneCircle"] == ["researchers", "live", "people", "activity", "signals"]   # no GitHub: what works first
    assert said["phoneTabs"] == sorted(["you", "grow", "news", "papers", "models", "launches", "live", "people", "activity",
                                        "signals", "repos", "chances", "researchers", "feed", "help"])


def test_the_panel_row_goes_in_and_out(monkeypatch):
    pytest.importorskip("PySide6")
    from mygeeky.config import MyGeekyConfig
    from tests.test_freshness import _close, _quiet_panel
    app, panel = _quiet_panel(monkeypatch, MyGeekyConfig(github_username="me", keywords=["gwas"]))
    try:
        bar = panel.tab_bar.layout()
        names = lambda: [bar.itemAt(i).widget().accessibleName() for i in range(bar.count())]   # noqa: E731
        panel.nav_buttons["world"].click()
        assert names() == ["Back to All", "News", "Research", "AI models"]
        assert panel.active_tab == "news" and panel._news_mode == "airace", "a group opens its first page"
        panel.nav_buttons["news"].click()
        assert names() == ["Back to World", "AI race", "Headlines", "Papers & discussions"]
        panel.nav_buttons["news:headlines"].click()
        assert panel._news_mode == "headlines" and panel.nav_trail.text() == "World › News › Headlines"
        panel.nav_back.click()
        panel.nav_back.click()
        panel.nav_buttons["repos"].click()                 # the Repos group: Help out, Rising
        panel.nav_buttons["market:repos"].click()
        assert panel.active_tab == "market" and panel._market_mode == "repos"
        assert names() == ["Back to All", "Help out", "Rising"], "the row stays where you tapped"
        panel._switch_tab("chances")                       # from elsewhere (a notification): the row follows
        assert names()[0] == "Back to All" and "Jobs" in names()
    finally:
        _close(panel)
