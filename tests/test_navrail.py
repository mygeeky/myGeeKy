"""The side rail (gui/navrail.py): folded with each group's count, open over the page or pinned beside it, a group
drops down its pages and a page its parts, tapping again or Back goes up, picking a page folds it unless pinned."""

import pytest

from mygeeky.config import MyGeekyConfig


@pytest.fixture
def panel(qapp_offscreen):
    from PySide6.QtWidgets import QApplication
    from mygeeky.gui.qt_panel import MyGeekyPanel
    p = MyGeekyPanel(MyGeekyConfig(github_username="me", keywords=["gwas"]))
    p.resize(380, 760)
    p.show()
    for _ in range(10):
        QApplication.processEvents()
    yield p
    p.close()


def test_it_starts_folded_with_the_planet_row_gone(panel):
    from mygeeky.gui import navrail
    host = panel.rail_host
    assert not panel.tab_bar.isVisible() and host.isVisible()
    assert host.strip.isVisible() and host.strip.width() == navrail.FOLDED_W
    assert not host.overlay.isVisible() and not host.docked.isVisible()


def test_unpinned_it_opens_over_the_page_and_folds_after_a_pick(panel):
    from mygeeky.gui import navrail
    host = panel.rail_host
    host.open_at("chances")
    assert host.overlay.isVisible() and host.scrim.isVisible() and host.overlay.width() == navrail.OPEN_W
    assert host.strip.isVisible()                                   # the page doesn't move: the rail is over it
    assert {"chances:seasons", "chances:jobs", "chances:funding", "chances:conferences"} <= set(host.overlay.rows)
    host.tapped("chances:jobs")
    assert panel.active_tab == "chances" and panel._chance_mode == "jobs"
    assert not host.overlay.isVisible() and host.strip.isVisible()  # picked: folded again
    assert panel.nav_trail.text() == "Chances › Jobs"


def test_a_group_opens_and_closes_and_back_goes_up_a_level(panel):
    host = panel.rail_host
    host.open_at("grow")
    host.tapped("grow:data")                                        # a page with parts drops them down
    assert host.state.open_page == "grow:data" and "grow:data:plants" in host.overlay.rows
    host.tapped("grow:data")                                        # tapping it again closes it
    assert host.state.open_page is None and "grow:data:plants" not in host.overlay.rows
    host.tapped("grow:data")
    host.back()
    assert host.state.open_page is None and host.state.open_group == "grow"
    host.back()
    assert host.state.open_group is None and host.state.open
    host.back()
    assert not host.state.open                                      # at the top, Back folds it
    host.open_at("world")
    host.tapped("world")                                            # tapping the open group closes it
    assert host.state.open_group is None


def test_pinned_it_sits_beside_the_page_stays_open_and_is_remembered(panel):
    from mygeeky.gui import navrail
    host = panel.rail_host
    host.open_at("grow")
    host.toggle_pin()
    assert panel.cfg.gui_rail_pinned is True
    assert host.docked.isVisible() and not host.overlay.isVisible() and not host.strip.isVisible()
    assert host.docked.width() == navrail.OPEN_W
    host.tapped("grow:data")
    host.tapped("grow:data:plants")                                 # three levels deep
    assert panel.active_tab == "grow" and panel._grow_mode == "data:plants"
    assert host.docked.isVisible()                                  # pinned: still open
    assert host.docked.rows["grow:data:plants"].nd["id"] == host.docked.leaf_id
    host.toggle_pin()
    assert panel.cfg.gui_rail_pinned is False and host.overlay.isVisible()


def test_counts_sit_on_the_icons_folded_and_open(panel):
    host = panel.rail_host
    panel.nav_buttons["suggestions"].set_count(3)
    panel.nav_buttons["news"].set_count(12)
    panel._update_group_counts()
    assert host.count_of("circle") == 3 and host.count_of("world") == 12
    assert host.count_of("news") == 12                              # a page with parts keeps its own count
    assert "3 new" in host.tip(next(c for c in panel.nav_tree["children"] if c["id"] == "circle"))
    host.open_at("world")
    row = host.overlay.rows["news"]
    assert row.rail.count_of("news") == 12


def test_the_rail_draws_in_every_theme(panel):
    from mygeeky.gui.app import THEMES
    for name in THEMES:
        panel.cfg.gui_theme = name
        panel._apply_theme()
        panel.rail_host.open_at("you")
        assert not panel.rail_host.overlay.grab().isNull()
        panel.rail_host.fold()


def test_the_rail_sits_on_the_screen_edge_side_and_can_be_moved_in_settings(panel, monkeypatch):
    from mygeeky.gui import app as logic
    monkeypatch.setattr(logic, "save_config", lambda cfg: None)
    host = panel.rail_host
    assert panel.cfg.gui_dock_side == "right" and host.side == "right"     # a panel on the right: the menu on the right
    assert host.strip.x() > host.content.x() and host.arrow(opening=True) == "«"
    host.open_at("grow")
    assert host.overlay.geometry().right() == host.width() - 1           # it opens from the right edge
    host.fold()
    panel._on_side_picked("left")                                        # the panel moves: "screen edge" follows
    assert host.side == "left" and host.strip.x() < host.content.x() and host.arrow(opening=True) == "»"
    panel._on_rail_side_changed("right")                                 # ⚙ → Menu side: always right
    assert panel.cfg.gui_rail_side == "right" and host.side == "right"
    panel._on_side_picked("bottom-right")
    assert host.side == "right"
    panel._on_rail_side_changed("left")
    assert host.side == "left" and panel.rail_side_switch.value() == "left"


def test_the_panel_is_wider_and_its_inner_edge_or_settings_change_the_width(panel, monkeypatch):
    from mygeeky.config import _migrate
    from mygeeky.gui import app as logic
    saved = []
    monkeypatch.setattr(logic, "save_config", lambda cfg: saved.append(cfg.gui_expanded_width))
    assert MyGeekyConfig().gui_expanded_width == 460
    assert _migrate({"gui_expanded_width": 380}, 4)["gui_expanded_width"] == 460   # the old default grows
    assert _migrate({"gui_expanded_width": 520}, 4)["gui_expanded_width"] == 520   # a chosen width is kept
    grip = panel.width_grip
    assert grip.x() == 0 and grip.width() == 6                           # docked right: the grip on the left edge
    panel._resize_width_from_grip(120, 460, True)
    assert panel.cfg.gui_expanded_width == 580 and saved[-1] == 580 and panel.width_slider.value() == 580
    panel._resize_width_from_grip(-900, 460, True)
    assert panel.cfg.gui_expanded_width == logic.MIN_PANEL_WIDTH
    panel.width_slider.setValue(700)
    panel._on_width_committed()
    assert saved[-1] == 700 and panel.width_value_label.text() == "700 px"


def test_up_a_level_takes_the_panel_to_that_level_then_home(panel):
    from mygeeky.gui.navrail import LevelTile
    host = panel.rail_host
    host.open_at("chances")
    host.tapped("chances:jobs")                                     # on Chances › Jobs, the menu folded
    assert panel.nav_back_text.isVisible() and "Chances" in panel.nav_back_text.text()
    panel.nav_back_text.click()                                     # the panel shows Chances' pages
    assert panel._level_node()["id"] == "chances" and panel.nav_trail.text() == "Chances"
    assert host.state.open_group == "chances" and not host.state.open             # the menu follows, still folded
    assert "chances:jobs" in [w.nd["id"] for w in panel.level_page.findChildren(LevelTile) if not w.isHidden()]
    assert host.up_target()["label"] == "All sections"
    panel.nav_back_text.click()                                     # all sections: the six groups and Home
    assert panel._level_node() is panel.nav_tree and panel.nav_trail.text() == "All sections"
    assert host.state.open_group is None and host.up_target()["label"] == "Home"
    panel.nav_back_text.click()                                     # last: Home
    assert panel.active_tab == "home" and panel._level_node() is None and not panel.nav_back_text.isVisible()


def _tiles(panel):
    """The level page's tiles now (from its grid, not the old ones still waiting to be deleted)."""
    g = panel.level_page.grid
    return [g.itemAt(i).widget() for i in range(g.count())]


def test_a_level_tile_opens_its_page_or_its_own_level(panel):
    host = panel.rail_host
    host.open_at("grow")
    host.tapped("grow:skills")
    host.up()                                                       # Grow's pages
    tiles = {w.nd["id"]: w for w in _tiles(panel)}
    tiles["grow:data"]._on_click()                                  # Data has parts: its own level
    assert panel._level_node()["id"] == "grow:data" and host.up_target()["label"] == "Grow"
    _tiles(panel)[0]._on_click()                                    # a part: the page opens
    assert panel._level_node() is None and panel.active_tab == "grow" and panel._grow_mode.startswith("data")


def test_settings_is_a_page_in_the_panel_with_a_way_back(panel):
    from mygeeky import navtree
    panel._nav_open(navtree.find(panel.nav_tree, "grow:skills"))
    panel._nav_open(navtree.find(panel.nav_tree, "settings:accounts"))
    assert panel.content_stack.currentWidget() is panel.settings_panel
    assert panel.rail_host.isVisibleTo(panel) and panel.nav_head.isVisibleTo(panel)          # the menu and ‹ back stay
    assert panel.nav_trail.text() == "Settings \u203a Accounts" and "Settings" in panel.nav_back_text.text()
    panel._nav_open(navtree.find(panel.nav_tree, "settings:look"))       # the side menu moves between settings pages
    assert not hasattr(panel, "settings_nav")                       # no second row of page buttons inside ⚙
    assert panel.nav_trail.text() == "Settings \u203a Look and window"
    panel.nav_back_text.click()                                     # up: the Settings level, in the panel
    assert panel._level_node()["id"] == "settings"
    panel._toggle_settings()
    panel._toggle_settings()                                        # ⚙ closes back to the page you were on
    assert panel.content_stack.currentWidget() is not panel.settings_panel and panel.active_tab == "grow"


def test_the_pin_stands_up_when_pinned_and_leans_when_not(panel):
    from mygeeky.gui import navrail
    a = navrail.pin_icon("#ffffff", upright=True).pixmap(36, 36).toImage()
    b = navrail.pin_icon("#ffffff", upright=False).pixmap(36, 36).toImage()
    assert a != b and not a.isNull()
    host = panel.rail_host
    host.open_at("grow")
    assert not host.overlay.pin_btn.icon().isNull() and host.overlay.pin_btn.text() == ""


def test_admin_widens_the_panel_and_leaving_it_brings_it_back(qapp_offscreen, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from mygeeky.gui import app as logic
    from mygeeky.gui.qt_panel import MyGeekyPanel
    assert logic.admin_width(1920) == logic.ADMIN_WIDTH and logic.admin_width(1000) == 850
    monkeypatch.setattr(logic, "is_admin", lambda cfg: True)
    p = MyGeekyPanel(MyGeekyConfig(github_username="me", keywords=["gwas"]))
    p.show()
    p._dock(folded=False)
    QApplication.processEvents()
    normal = p.width()
    p._switch_tab("admin")
    QApplication.processEvents()
    screen = p._home_screen().availableGeometry().width()
    assert p.width() >= min(logic.admin_width(screen), screen) > normal or screen <= normal
    p._switch_tab("home")
    QApplication.processEvents()
    assert p.width() == normal                                       # your own width again
    p.close()


def test_accounts_opens_no_window_of_its_own(panel):
    """Opening Accounts with Signals on once showed a hidden, parentless "Turn Signals off" button as its own empty
    window beside the panel. Nothing in ⚙ may become a window."""
    from PySide6.QtWidgets import QApplication
    from mygeeky import navtree
    panel._nav_open(navtree.find(panel.nav_tree, "settings:accounts"))
    panel._render_setup({"signals": True, "beacon_token": True, "version": "test"})
    QApplication.processEvents()
    stray = [w for w in QApplication.topLevelWidgets() if w.isVisible() and w is not panel and w.isWindow()
             and w.window() is w and not w.inherits("QMenu") and w.windowType() not in (0x0c, 0x13)]   # not popups/tooltips
    assert not [w for w in stray if w.parent() is None and type(w).__name__ in ("QPushButton", "QLabel")], stray
    assert panel.signals_btn.parent() is not None and not panel.signals_btn.isVisible()


def test_up_follows_the_panel_even_with_the_menu_pinned_open(panel):
    """A pinned menu used to send "up" wherever the menu was browsing: "‹ All sections" on Settings, and a dead
    "‹ Home" on Home. Up always climbs from what the panel shows."""
    host = panel.rail_host
    host.toggle_pin()                                               # pinned beside the page, open
    panel._switch_tab("home")
    assert not panel.nav_back_text.isVisible() or not panel.nav_back_text.text()               # nothing above Home
    panel._toggle_settings()                                        # ⚙ → Accounts
    assert host.state.open_group == "settings" and "Settings" in panel.nav_back_text.text()
    panel.nav_back_text.click()
    assert panel._level_node()["id"] == "settings" and panel.level_page.grid.count() > 0
    panel.nav_back_text.click()
    assert panel._level_node() is panel.nav_tree
    panel.nav_back_text.click()
    assert panel.active_tab == "home" and panel._level_node() is None
