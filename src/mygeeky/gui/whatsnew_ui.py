"""News → 📰 What's new: the AI and technology news the maker checked and published (whatsnew_shape.py, from TRACE),
newest first and nudged toward your field. The phone shows the same list (components/whatsnew-view.tsx).

Everything here came from the internet, so it's shown as plain text, and a link opens only through the panel's
allowed-link check (logic.open_link)."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import app as logic


def _label(text: str, css: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.PlainText)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(css + " background:transparent;")
    return lbl


class WhatsNewPage(QWidget):
    def __init__(self, theme: Callable[[], dict[str, Any]]) -> None:
        super().__init__()
        self.theme = theme
        self.items: list[dict[str, Any]] = []
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(8)
        self.setStyleSheet("background:transparent;")

    def set_items(self, items: list[dict[str, Any]]) -> None:
        self.items = list(items)
        self.render()

    def apply_theme(self) -> None:
        self.render()

    def render(self) -> None:
        while self.lay.count():
            w = self.lay.takeAt(0).widget()
            if w is not None:
                w.hide()                 # out of sight now: deleteLater waits for the event loop
                w.deleteLater()
        t = self.theme()
        if not self.items:
            self.lay.addWidget(_label("Nothing here yet. New AI and technology news appears here once it has been "
                                      "checked: every item is read against its sources first.",
                                      f"color:{t['muted']}; font-size:11.5px;"))
            return
        for it in self.items:
            self.lay.addWidget(self._card(it, t))

    def _card(self, it: dict[str, Any], t: dict[str, Any]) -> QFrame:
        card = QFrame()
        card.setObjectName("wnCard")
        card.setStyleSheet(f"#wnCard {{ background:{t['card_bg']}; border-radius:10px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)
        top = QHBoxLayout()
        top.setSpacing(6)
        if it.get("topic"):
            top.addWidget(_label(it["topic"], f"color:{logic.readable(t['accent'], t)}; font-size:10px; font-weight:700;"))
        top.addStretch(1)
        top.addWidget(_label(it.get("added", ""), f"color:{t['muted']}; font-size:10px;"))
        lay.addLayout(top)
        lay.addWidget(_label(it["title"], f"color:{t['text']}; font-size:13px; font-weight:700;"))
        if it.get("summary"):
            lay.addWidget(_label(it["summary"], f"color:{t['text']}; font-size:11.5px;"))
        if it.get("why"):
            lay.addWidget(_label("Why it matters: " + it["why"], f"color:{t['muted']}; font-size:11px;"))
        row = QHBoxLayout()
        row.setSpacing(6)
        hosts = []
        for u in it.get("sources", []):
            h = logic.host_of(u)
            if h and h not in hosts:
                hosts.append(h)
        row.addWidget(_label(f"{len(hosts)} source{'s' if len(hosts) != 1 else ''}: " + " · ".join(hosts[:4]),
                             f"color:{t['muted']}; font-size:10.5px;"), 1)
        go = QPushButton("Open ↗")
        go.setCursor(Qt.PointingHandCursor)
        go.setStyleSheet(f"QPushButton {{ background:{t['section_btn']}; color:{t['text']}; border:none; "
                         f"border-radius:8px; padding:3px 10px; font-size:11px; font-weight:600; }}")
        go.clicked.connect(lambda checked=False, u=it["url"]: logic.open_link(u))
        row.addWidget(go)
        lay.addLayout(row)
        return card
