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
