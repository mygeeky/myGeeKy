"""The Quizzes page of the Admin tab, and the row layout underneath it.

Two bugs, both the kind that only show up with real data on screen:

  * every reviewed protocol had its own row and its own button, so once they all had enough questions
    the page was fourteen identical "More questions" buttons under a heading saying there was nothing
    to do;
  * the rows' labels were invisible. A wrapping QLabel declares QSizePolicy.Ignored (it can shrink to
    any width, because it wraps), which makes its sizeHint nought wide -- and the flow layout laid it
    out at exactly that. The protocol titles and question counts were present and never drawn, which is
    why the page read as a wall of unlabelled buttons.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="PySide6 (the 'gui' extra) is not installed")

from PySide6.QtCore import QRect           # noqa: E402
from PySide6.QtWidgets import QPushButton  # noqa: E402

from test_window_place import _close, _panel, no_save, qapp  # noqa: F401


# --------------------------------------------------------------------------- the row layout
def test_a_wrapping_label_in_a_flow_row_is_given_a_real_width(qapp):
    """It asks for no width at all; being laid out at nought wide means present and never drawn."""
    from mygeeky.gui.growth_ui import FlowRow, _label

    row = FlowRow()
    wrapping = _label("a sentence long enough that it would wrap if it were ever given room", "")
    row.add(wrapping)
    row.finish()
    row.resize(300, 80)
    row.layout().setGeometry(QRect(0, 0, 300, 80))
    # The policy is applied by the LAYOUT ITEM, not the widget: QWidget.sizeHint() still reports the
    # text's natural size, while QWidgetItem.sizeHint() reports nought. The layout only sees the latter.
    item = row.layout().itemAt(0)
    assert item.sizeHint().width() == 0, "the premise changed: this item now asks for a width"
    assert wrapping.width() > 100, f"laid out {wrapping.width()}px wide -- invisible"
    assert wrapping.height() > 0


def test_one_line_chips_still_sit_side_by_side(qapp):
    """The fix for wrapping text must not give every short chip a line of its own."""
    from mygeeky.gui.growth_ui import FlowRow, _label

    row = FlowRow()
    chips = [_label(word, "", wrap=False) for word in ("one", "two", "three")]
    for chip in chips:
        row.add(chip)
    row.finish()
    row.resize(300, 60)
    row.layout().setGeometry(QRect(0, 0, 300, 60))
    assert len({c.y() for c in chips}) == 1, "short chips were split across lines"
    assert all(c.width() > 0 for c in chips)


# --------------------------------------------------------------------------- the page itself
def _quiz_state(ready=10, good=20, counts=None):
    counts = counts or {}
    return {"protocols": len(counts), "with_quiz": len(counts), "bank": sum(sum(v.values())
                                                                            for v in counts.values()),
            "ready": ready, "good": good, "has_key": True, "per_protocol": counts, "batches": {},
            "missing": []}


def _page(monkeypatch, counts, batches=None):
    monkeypatch.setattr("mygeeky.gui.app.is_admin", lambda cfg: True)    # the Quizzes page is maker-only
    panel = _panel(monkeypatch)
    state = _quiz_state(counts=counts)
    state["batches"] = batches or {}
    monkeypatch.setattr("mygeeky.gui.app.quizwriter_state", lambda: state)
    monkeypatch.setattr(panel, "_reviewed_protocols",
                        lambda: [{"id": k, "title": k.replace("-", " ")} for k in counts])
    panel._render_quizwriter()
    return panel


def _more_buttons(panel):
    return [b for b in panel.admin_quiz.parentWidget().findChildren(QPushButton)
            if b.text().startswith("➕") and not b.parentWidget().isHidden()]


def test_protocols_that_need_nothing_fold_into_one_line(qapp, monkeypatch, no_save):
    counts = {f"p{i}": {"easy": 8, "medium": 8, "tricky": 4} for i in range(14)}
    panel = _page(monkeypatch, counts)
    try:
        assert _more_buttons(panel) == [], "fourteen settled protocols still showed their buttons"
        said = [b for b in panel.admin_quiz.parentWidget().findChildren(QPushButton)
                if b.text() == "Show them"]
        assert said, "no way to open them at all"
    finally:
        _close(panel)


def test_opening_them_brings_every_button_back(qapp, monkeypatch, no_save):
    counts = {f"p{i}": {"easy": 8, "medium": 8, "tricky": 4} for i in range(14)}
    panel = _page(monkeypatch, counts)
    try:
        panel._on_quiz_toggle_settled()
        qapp.processEvents()
        assert len(_more_buttons(panel)) == 14
        panel._on_quiz_toggle_settled()
        qapp.processEvents()
        assert _more_buttons(panel) == []
    finally:
        _close(panel)


def test_anything_that_wants_doing_is_never_folded_away(qapp, monkeypatch, no_save):
    """Too few questions, or a batch waiting to be spot-checked: both are work, so both stay up."""
    counts = {"thin": {"easy": 2}, "full": {"easy": 8, "medium": 8, "tricky": 4},
              "awaiting": {"easy": 8, "medium": 8, "tricky": 4}}
    batches = {"awaiting": {"questions": [1, 2, 3], "spot_check": [1, 2], "verdict": None}}
    panel = _page(monkeypatch, counts, batches)
    try:
        buttons = [b.text() for b in panel.admin_quiz.parentWidget().findChildren(QPushButton)
                   if not b.parentWidget().isHidden()]
        assert any("Write questions" in b for b in buttons), "the thin one was hidden"
        assert any("Spot-check" in b for b in buttons), "a batch waiting to be read was hidden"
        assert _more_buttons(panel) == [], "the settled one was not folded away"
    finally:
        _close(panel)


def test_each_row_says_which_protocol_it_is(qapp, monkeypatch, no_save):
    """The titles were laid out nought wide, so the page was a wall of unlabelled buttons."""
    from PySide6.QtWidgets import QLabel
    counts = {"nextflow-pipelines": {"easy": 2}}
    panel = _page(monkeypatch, counts)
    try:
        qapp.processEvents()
        panel.admin_quiz.parentWidget().resize(360, 600)
        panel.admin_quiz.activate()
        titles = [lbl for lbl in panel.admin_quiz.parentWidget().findChildren(QLabel)
                  if "nextflow pipelines" in lbl.text()]
        assert titles, "the protocol's name is not on its row at all"
        assert titles[0].width() > 0, "the row's title was laid out nought wide -- invisible"
    finally:
        _close(panel)
