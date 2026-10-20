"""The sections row: each is its icon, and the one you are in also says its name."""

import pytest

from mygeeky.gui.qt_panel import MyGeekyPanel


def _panel(monkeypatch):
    from mygeeky.config import MyGeekyConfig
    from tests.test_freshness import _quiet_panel
    monkeypatch.setattr("mygeeky.gui.app.growth_due", lambda cfg: False)
    qapp, panel = _quiet_panel(monkeypatch, MyGeekyConfig(github_username="me"))
    return qapp, panel


def _settle(qapp, panel, tab):
    panel._switch_tab(tab)
    for w in list(panel._workers):
        w.wait(5000)
    for _ in range(6):
        qapp.processEvents()


def test_the_sections_are_still_written_out_in_one_place():
    """The icon and the name are split from the one label, so there is no second list to keep in step."""
    assert dict(MyGeekyPanel.CHANCE_MODES)["seasons"] == "🗓 Seasons"
    assert dict(MyGeekyPanel.GROW_MODES)["collab"] == "🤝 Collaborators"


@pytest.mark.parametrize("tab,row,modes,opens", [
    ("chances", "chance_mode_buttons", "CHANCE_MODES", "jobs"),
    ("grow", "grow_mode_buttons", "GROW_MODES", "highlights"),     # Grow opens on ✨ Highlights
])
def test_only_the_open_section_says_its_name(qapp_offscreen, monkeypatch, tab, row, modes, opens):
    qapp, panel = _panel(monkeypatch)
    try:
        _settle(qapp, panel, tab)
        buttons = getattr(panel, row)
        named = dict(getattr(MyGeekyPanel, modes))
        for mode, b in buttons.items():
            icon, _, name = named[mode].partition(" ")
            if mode == opens:
                assert name in b.text(), f"the open section must say {name}"
                assert icon in b.text(), "and keep its icon"
            else:
                assert b.text() == icon, f"{mode} should be its icon alone, not {b.text()!r}"
    finally:
        panel.close()


def test_an_icon_on_its_own_can_still_say_what_it_is(qapp_offscreen, monkeypatch):
    """Six small pictures in a row are no use if none of them can be identified."""
    qapp, panel = _panel(monkeypatch)
    try:
        _settle(qapp, panel, "grow")
        for mode, b in panel.grow_mode_buttons.items():
            name = dict(MyGeekyPanel.GROW_MODES)[mode].partition(" ")[2]
            assert b.toolTip() == name, mode
            assert b.accessibleName() == name, f"{mode}: a screen reader gets the icon only"
    finally:
        panel.close()


def test_the_name_moves_when_a_different_section_is_opened(qapp_offscreen, monkeypatch):
    qapp, panel = _panel(monkeypatch)
    try:
        _settle(qapp, panel, "chances")
        panel._set_chance_mode("conferences")
        qapp.processEvents()
        assert "Conferences" in panel.chance_mode_buttons["conferences"].text()
        assert panel.chance_mode_buttons["jobs"].text() == "💼", "the one left behind gives its words back"
    finally:
        panel.close()


def test_the_parts_are_chosen_in_the_dock_not_inside_the_page(qapp_offscreen, monkeypatch):
    """The planet row (navtree.py) holds a page's parts now, so the row inside the page is hidden."""
    qapp, panel = _panel(monkeypatch)
    try:
        _settle(qapp, panel, "grow")
        holder = next(iter(panel.grow_mode_buttons.values())).parentWidget()
        assert not holder.isVisibleTo(panel), "the in-page row is gone"
        for row in (panel.news_mode_buttons, panel.market_mode_buttons, panel.you_buttons):
            assert not any(b.isVisibleTo(panel) for b in row.values())
    finally:
        panel.close()


def test_the_open_section_takes_the_room_and_the_rest_share_what_is_left(qapp_offscreen, monkeypatch):
    qapp, panel = _panel(monkeypatch)
    try:
        _settle(qapp, panel, "grow")
        from PySide6.QtWidgets import QSizePolicy
        for mode, b in panel.grow_mode_buttons.items():
            want = QSizePolicy.Preferred if mode == "highlights" else QSizePolicy.Expanding
            assert b.sizePolicy().horizontalPolicy() == want, mode
    finally:
        panel.close()


def test_the_row_follows_the_theme(qapp_offscreen, monkeypatch):
    """Including the strip behind it, which is what makes the row read as one control."""
    from mygeeky.gui.app import THEMES
    qapp, panel = _panel(monkeypatch)
    try:
        _settle(qapp, panel, "grow")
        theme = THEMES[panel._theme_name()]
        holder = next(iter(panel.grow_mode_buttons.values())).parentWidget()
        assert "modeRow" in holder.styleSheet() and theme["card_bg"] in holder.styleSheet()
        assert theme["muted"] in panel.grow_mode_buttons["wins"].styleSheet(), "a closed one is dimmed"
        assert theme["text"] in panel.grow_mode_buttons["highlights"].styleSheet(), "the open one is not"
    finally:
        panel.close()


def test_every_section_stays_one_press_away(qapp_offscreen, monkeypatch):
    """Inside Grow, each of its parts is one planet in the dock's row."""
    qapp, panel = _panel(monkeypatch)
    try:
        panel.nav_buttons["grow"].click()
        bar = panel.tab_bar.layout()
        shown = {bar.itemAt(i).widget() for i in range(bar.count())}
        for mode in dict(MyGeekyPanel.GROW_MODES):
            assert panel.nav_buttons[f"grow:{mode}"] in shown, f"{mode} is not in the row"
    finally:
        panel.close()
