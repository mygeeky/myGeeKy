"""⚙ → Window: In front / Normal / Behind, and where on the screen the panel lives."""
import time

import pytest

pytest.importorskip("PySide6", reason="PySide6 (the 'gui' extra) is not installed")

from mygeeky.config import MyGeekyConfig
from mygeeky.gui import app as logic


@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def no_save(monkeypatch):
    saved = []
    monkeypatch.setattr(logic, "save_config", lambda cfg: saved.append(1))   # never the real settings
    return saved


def _panel(monkeypatch, **cfg):
    from mygeeky.gui.qt_panel import MyGeekyPanel
    monkeypatch.setattr(logic, "get_contributions", lambda cfg: [])
    monkeypatch.setattr(logic, "get_suggestions", lambda cfg: {"followback": [], "domain_highlights": []})
    monkeypatch.setattr(logic, "get_activity", lambda cfg, force=False: {"events": []})
    monkeypatch.setattr(logic, "get_model_history", lambda: [])
    monkeypatch.setattr(logic, "get_friend_stats", lambda cfg: {
        "total_friends": 0, "new_this_week": 0, "follow_back_rate": None, "total_labeled": 0})
    return MyGeekyPanel(MyGeekyConfig(gui_expanded_width=380, gui_folded_width=60, gui_folded_height=60,
                                      gui_panel_height_fraction=0.6, **cfg))


def _close(panel):
    panel.ticker.stop()
    panel._activity_timer.stop()
    for w in list(panel._workers):
        w.wait(2000)
    panel.hide()
    panel.deleteLater()


def _wait(qapp, seconds=0.5):
    end = time.time() + seconds
    while time.time() < end:
        qapp.processEvents()


def test_a_bottom_corner_folds_into_the_corner_and_opens_in_the_middle():
    from PySide6.QtCore import QRect
    screen = QRect(0, 0, 1920, 1040)
    cfg = MyGeekyConfig(gui_dock_side="bottom-right", gui_folded_width=60, gui_folded_height=60,
                        gui_expanded_width=380, gui_panel_height_fraction=0.6)
    assert logic._panel_geometry(cfg, True, screen) == (1860, 980, 60, 60)          # in the corner
    x, y, w, h = logic._panel_geometry(cfg, False, screen)
    assert (x + w, y + h // 2) == (1920, 520)                                         # the middle of the edge
    cfg.gui_dock_side = "bottom-left"
    assert logic._panel_geometry(cfg, True, screen)[:2] == (0, 980)
    cfg.gui_dock_side = "top-middle"                                                   # unknown: the right edge
    assert logic._panel_geometry(cfg, True, screen) == (1860, 490, 60, 60)


def test_only_known_places_and_layers_are_saved(no_save):
    cfg = MyGeekyConfig()
    assert logic.layer(cfg) == "front" and logic.dock_side(cfg) == "right"            # the defaults
    assert logic.set_dock_side(cfg, "bottom-left") and cfg.gui_dock_side == "bottom-left"
    assert not logic.set_dock_side(cfg, "middle") and cfg.gui_dock_side == "bottom-left"
    assert logic.set_layer(cfg, "behind") and cfg.gui_layer == "behind"
    assert not logic.set_layer(cfg, "floating") and cfg.gui_layer == "behind"
    assert len(no_save) == 2


def test_opening_from_a_corner_rises_to_the_middle_and_folding_sinks_back(qapp, monkeypatch, no_save):
    panel = _panel(monkeypatch, gui_dock_side="bottom-right")
    try:
        area = panel.screen().availableGeometry()
        panel.show()
        panel.fold()
        _wait(qapp)
        g = panel.geometry()
        assert panel.folded_widget.isVisible()
        assert (g.right(), g.bottom()) == (area.right(), area.bottom())                 # icon in the corner

        panel.unfold()
        start = panel.geometry()
        assert start.bottom() == area.bottom() and panel._dock_moving()                # opens at the bottom...
        _wait(qapp)
        end = panel.geometry()
        assert not panel._dock_moving()
        assert abs(end.center().y() - area.center().y()) <= 1 and end.right() == area.right()   # ...risen to the middle

        panel.fold()
        assert panel.panel_frame.isVisible() and panel._dock_moving()                  # sinks first
        _wait(qapp)
        g = panel.geometry()
        assert panel.folded_widget.isVisible() and (g.right(), g.bottom()) == (area.right(), area.bottom())
    finally:
        _close(panel)


def test_picking_a_spot_moves_the_panel_now(qapp, monkeypatch, no_save):
    panel = _panel(monkeypatch)
    try:
        area = panel.screen().availableGeometry()
        panel.screen_picker.picked.emit("left")
        assert panel.cfg.gui_dock_side == "left" and panel.geometry().left() == area.left()
        assert panel.place_name.text() == "Left edge"
        panel.screen_picker.hovered.emit("bottom-right")                               # hover previews the words
        assert panel.place_name.text() == "Bottom right"
        panel.screen_picker.hovered.emit("")
        assert panel.place_name.text() == "Left edge"
    finally:
        _close(panel)


def test_in_front_normal_and_behind(qapp, monkeypatch, no_save):
    from PySide6.QtCore import Qt
    from mygeeky.gui import topmost
    sent_back = []
    monkeypatch.setattr(topmost, "send_to_back", lambda hwnd: sent_back.append(hwnd) or True)
    panel = _panel(monkeypatch)
    try:
        panel.show()
        assert panel.windowFlags() & Qt.WindowStaysOnTopHint                            # the default: in front
        panel.layer_switch.buttons["normal"].click()
        assert panel.cfg.gui_layer == "normal" and not panel.windowFlags() & Qt.WindowStaysOnTopHint
        assert panel.isVisible()                                                         # a flag change never hides it
        panel.layer_switch.buttons["behind"].click()
        panel.fold()
        _wait(qapp, 0.1)
        assert sent_back                                                                 # folded: under the others
        panel.layer_switch.buttons["front"].click()
        assert panel.windowFlags() & Qt.WindowStaysOnTopHint
    finally:
        _close(panel)


def test_off_screen_hides_it_until_you_open_it_again(qapp, monkeypatch, no_save):
    from PySide6.QtWidgets import QMessageBox
    panel = _panel(monkeypatch)
    try:
        panel.show()
        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton",
                            lambda self: next(b for b in self.buttons() if b.text() == "Cancel"))
        panel._go_off_screen()
        assert panel.isVisible()                                                         # Cancel: nothing changes
        monkeypatch.setattr(QMessageBox, "clickedButton",
                            lambda self: next(b for b in self.buttons() if b.text() == "Hide"))
        panel._go_off_screen()
        assert not panel.isVisible() and not panel.hearts.isVisible()
        panel.unfold()                                                                   # what a second start does
        panel.show()
        assert panel.isVisible() and panel.panel_frame.isVisible()
    finally:
        _close(panel)
