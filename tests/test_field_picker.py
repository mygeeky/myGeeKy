"""The keyword picker and the account nudge, in the panel itself."""
import pytest

pytest.importorskip("PySide6", reason="PySide6 (the 'gui' extra) is not installed")

from test_window_place import _close, _panel, no_save, qapp  # noqa: F401

# isHidden(), not isVisible(): a panel that was never shown makes isVisible() False for every child of
# it, so a test asking isVisible() would pass whatever the code did.


def _buttons(widget):
    from PySide6.QtWidgets import QPushButton
    return [b for b in widget.findChildren(QPushButton) if not b.parentWidget().isHidden()]


def test_a_blank_profile_is_met_by_the_picker_not_a_terminal_command(qapp, monkeypatch, no_save):
    """"Run `mygeeky init` in a terminal" is not a door. Five keywords is."""
    panel = _panel(monkeypatch)
    try:
        panel._load_status()
        assert not panel.start_holder.isHidden()
        said = " ".join(b.text() for b in _buttons(panel.start_holder))
        assert "Start" in said, "no way to start from the picker"
        assert "no account needed" in panel.status_label.text().lower()
    finally:
        _close(panel)


def test_picking_keywords_saves_them_and_closes_the_door(qapp, monkeypatch, no_save):
    panel = _panel(monkeypatch)
    kept = []
    def _keep(cfg, picked):          # the real one saves; here it only records and updates the config
        kept.append(list(picked))
        cfg.keywords = list(picked)
        return {}

    monkeypatch.setattr("mygeeky.gui.app.field_keep", _keep)
    try:
        panel._load_status()
        panel._on_field_picked(["metagenomics", "economics", "robotics"])
        assert kept == [["metagenomics", "economics", "robotics"]]
        assert panel.start_holder.isHidden()
    finally:
        _close(panel)


def test_a_keyword_profile_sees_the_nudge_but_never_loses_anything(qapp, monkeypatch, no_save):
    panel = _panel(monkeypatch, keywords=["metagenomics", "economics", "robotics"],
                   field_started_at="2020-01-01")
    try:
        panel._load_status()
        assert not panel.start_holder.isHidden(), "the scheduled ask never appeared"
        said = " ".join(lbl.text() for lbl in panel.start_holder.findChildren(type(panel.status_label)))
        assert "account" in said.lower()
        panel._on_nudge_dismissed()                 # "No thanks"
        assert panel.start_holder.isHidden()
        assert panel.cfg.account_asks == 1
        # Nothing was withdrawn: the panel still has a field to work from.
        from mygeeky.config import profile_ready
        assert profile_ready(panel.cfg)
    finally:
        _close(panel)


def test_a_signed_in_profile_is_never_nudged(qapp, monkeypatch, no_save):
    panel = _panel(monkeypatch, github_username="me")
    try:
        panel._load_status()
        assert panel.start_holder.isHidden()
    finally:
        _close(panel)


def test_the_picker_keeps_the_panel_inside_its_width(qapp, monkeypatch, no_save):
    """Side-by-side buttons and long chip labels each pushed the 380px dock off the screen once."""
    panel = _panel(monkeypatch)
    try:
        panel._load_status()
        panel.show()
        qapp.processEvents()
        assert panel.start_holder.minimumSizeHint().width() <= 380
    finally:
        _close(panel)


def test_the_picker_is_not_rebuilt_under_somebody_half_way_through(qapp, monkeypatch, no_save):
    """A fresh picker starts at round one with nothing picked, so anything that redraws the status would
    quietly throw away the chips somebody had already tapped. Found by driving the real panel."""
    from mygeeky.gui.growth_ui import FieldPicker
    panel = _panel(monkeypatch)
    try:
        panel._load_status()
        picker = panel._picker
        assert isinstance(picker, FieldPicker)
        picker._take("metagenomics")
        picker._take("economics")
        panel._load_status()                       # a theme change, a token check, anything
        qapp.processEvents()
        assert panel._picker is picker, "the picker was replaced mid-flow"
        assert picker.picked == ["metagenomics", "economics"], picker.picked
        live = [w for w in panel.start_holder.findChildren(FieldPicker)
                if panel.start_layout.indexOf(w) >= 0]
        assert len(live) == 1, f"{len(live)} pickers stacked in the layout"
    finally:
        _close(panel)


def test_switching_to_a_tab_this_panel_did_not_build_is_ignored(qapp, monkeypatch, no_save):
    """TABS is every tab there is; _tab_order is the ones built. Admin only exists for a maker, and
    _tab_order.index() raised ValueError on it."""
    panel = _panel(monkeypatch)
    try:
        was = panel.active_tab
        panel._switch_tab("admin")                 # not built for a non-maker
        assert panel.active_tab == was
        panel._switch_tab("nonsense")
        assert panel.active_tab == was
    finally:
        _close(panel)


def test_a_picked_chip_reads_as_words_but_is_kept_as_a_dictionary_key(qapp, monkeypatch, no_save):
    """"machine-learning" is what lookup and expand need; "machine learning" is what a person reads."""
    from PySide6.QtWidgets import QPushButton
    from mygeeky.gui.growth_ui import FieldPicker
    panel = _panel(monkeypatch)
    try:
        panel._load_status()
        picker = panel._picker
        picker._take("machine-learning")
        qapp.processEvents()
        shown = [b.text() for b in picker.findChildren(QPushButton) if b.text().startswith("✓")]
        assert shown == ["✓ machine learning"], shown
        assert picker.picked == ["machine-learning"], picker.picked
    finally:
        _close(panel)
