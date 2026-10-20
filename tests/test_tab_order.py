"""Tabs (desktop) and planets (phone) in order: You first; without GitHub, what would only say "add GitHub" last."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from mygeeky.gui.qt_panel import NEEDS_GITHUB_TABS, TABS, tab_order

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"


def test_you_first_and_github_only_tabs_last_without_an_account():
    names = [n for n in TABS if n != "admin"]
    with_gh, without = tab_order(names, True), tab_order(names, False)
    assert with_gh[0] == without[0] == "model"
    assert sorted(with_gh) == sorted(without) == sorted(names)
    assert without[-len(NEEDS_GITHUB_TABS):] == list(NEEDS_GITHUB_TABS)
    rest = [n for n in names if n != "model"]
    assert with_gh[1:] == rest                                              # otherwise the usual order
    assert [n for n in without if n not in NEEDS_GITHUB_TABS][1:] == [n for n in rest if n not in NEEDS_GITHUB_TABS]


def test_the_github_only_lists_name_the_parts_that_show_the_add_github_card():
    panel = (ROOT / "src" / "mygeeky" / "gui" / "qt_panel.py").read_text(encoding="utf-8")
    whole_tab_cards = set(re.findall(r'self\._github_card\(self\.(\w+)_area, "(\w+)"', panel))
    assert {"activity", "signals"} <= {part for _, part in whole_tab_cards}
    home = (MOBILE / "src" / "app" / "home.tsx").read_text(encoding="utf-8")
    block = re.search(r"const NEEDS_GITHUB: Partial<Record<SectionId, string>> = \{(.*?)\n\};", home, re.S).group(1)
    phone_cards = set(re.findall(r"^\s{2}(\w+):", block, re.M))
    order = (MOBILE / "src" / "lib" / "tab-order.ts").read_text(encoding="utf-8")
    listed = set(re.findall(r"'(\w+)'", re.search(r"NEEDS_GITHUB_IDS: SectionId\[\] = \[(.*?)\]", order).group(1)))
    assert listed == phone_cards                                            # the phone moves exactly those


def _node() -> bool:
    if not shutil.which("node"):
        return False
    v = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip().lstrip("v").split(".")
    return len(v) > 1 and v[0].isdigit() and v[1].isdigit() and (int(v[0]), int(v[1])) >= (22, 6)


@pytest.mark.skipif(not _node(), reason="needs Node 22.6+")
def test_the_phone_orders_its_ring_by_the_same_rule():
    work = MOBILE / ".crosscheck"
    work.mkdir(exist_ok=True)
    shutil.copy(MOBILE / "src" / "lib" / "tab-order.ts", work / "tab-order.ts")
    (work / "order-side.ts").write_text(
        "import { ordered } from './tab-order.ts';\n"
        "const inner = ['live', 'people', 'activity', 'signals', 'grow'];\n"
        "console.log(JSON.stringify([ordered(inner, true), ordered(inner, false)]));\n", encoding="utf-8")
    out = subprocess.run(["node", "--experimental-strip-types", str(work / "order-side.ts")],
                         capture_output=True, text=True, cwd=MOBILE, timeout=60)
    assert out.returncode == 0, out.stderr[-600:]
    with_gh, without = json.loads(out.stdout)
    assert with_gh == ["live", "people", "activity", "signals", "grow"]
    assert without == ["grow", "live", "people", "activity", "signals"]   # what works first, the same stable rule


@pytest.mark.parametrize("username", ["me", ""])
def test_the_panel_shows_its_tabs_in_that_order_and_still_opens_on_live(monkeypatch, username):
    pytest.importorskip("PySide6")
    from mygeeky.config import MyGeekyConfig
    from tests.test_freshness import _close, _quiet_panel
    app, panel = _quiet_panel(monkeypatch, MyGeekyConfig(github_username=username, keywords=["gwas"]))
    try:
        shown = [n for n in panel._tab_order]
        assert shown == tab_order([n for n in TABS if n in shown], bool(username))
        from mygeeky import navtree
        bar = panel.tab_bar.layout()
        row = lambda: [bar.itemAt(i).widget() for i in range(bar.count())]   # noqa: E731
        assert row() == [panel.nav_buttons[g["id"]] for g in navtree.GROUPS]   # the dock: the six groups
        assert panel.nav_back_text.isHidden() and panel.nav_trail.text() == "Circle \u203a Live"   # where you are
        panel.nav_buttons["circle"].click()                                    # a group: back planet, then its pages
        circle = [panel.nav_buttons[i] for i in ("live", "suggestions", "activity", "signals")]
        if not username:                                                       # what needs GitHub goes last
            assert [b.accessibleName() for b in row()[1:]] == ["Live", "People", "Activity", "Signals"]
        assert row()[0] is panel.nav_back and set(row()[1:]) == set(circle)
        assert panel.nav_back_text.text().endswith("Back to All") and panel.nav_trail.text() == "Circle \u203a Live"
        panel.nav_back.click()
        assert row() == [panel.nav_buttons[g["id"]] for g in navtree.GROUPS]
        assert panel.active_tab == "live" and panel.content_stack.currentIndex() == shown.index("live")
        panel._switch_tab("model")
        assert panel.content_stack.currentWidget() is panel.content_stack.widget(0)   # You is the first page
        panel._switch_tab("chances")
        assert panel.content_stack.currentIndex() == shown.index("chances")
    finally:
        _close(panel)
