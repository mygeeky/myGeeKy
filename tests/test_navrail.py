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
    assert "3 new" in host.tip(panel.nav_tree["children"][3])
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
