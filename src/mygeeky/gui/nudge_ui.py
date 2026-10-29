"""The card that asks again for what setup skipped (nudges.py decides which and when): above the page, with its one
action (opens Settings -> Accounts), "Not now" and "Don't ask again". The phone has the same card
(components/nudge-card.tsx)."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .. import nudges


class NudgeCard(QFrame):
    def __init__(self, theme: Callable[[], dict[str, Any]], act: Callable[[str, str], None]) -> None:
        super().__init__()
        self.theme, self.act, self.key = theme, act, ""
        self.setObjectName("nudgeCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(5)
        self.title, self.text = QLabel(), QLabel()
        for lbl in (self.title, self.text):
            lbl.setTextFormat(Qt.PlainText)
            lbl.setWordWrap(True)
            lay.addWidget(lbl)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.go, self.later, self.never = QPushButton(), QPushButton("Not now"), QPushButton("Don't ask again")
        for b, what in ((self.go, "go"), (self.later, "skip"), (self.never, "never")):
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _c=False, w=what: self.act(self.key, w))
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.hide()
        self.apply_theme()

    def show_key(self, key: str) -> None:
        self.key = key
        t = nudges.text(key, "computer")
        self.title.setText(t["title"])
        self.text.setText(t["text"])
        self.go.setText(t["go"])
        self.go.setAccessibleName(t["go"])
        self.show()

    def apply_theme(self) -> None:
        t = self.theme()
        bg = t["card_bg"] if not str(t["card_bg"]).startswith("rgba") else t["solid_bg"]
        self.setStyleSheet(f"#nudgeCard {{ background:{bg}; border:1.5px solid {t['accent']}; border-radius:12px; }}")
        self.title.setStyleSheet(f"color:{t['text']}; font-size:13px; font-weight:800; background:transparent;")
        self.text.setStyleSheet(f"color:{t['muted']}; font-size:11.5px; background:transparent;")
        self.go.setStyleSheet(f"QPushButton {{ background:{t['accent']}; color:{t['on_accent']}; border:none; border-radius:8px; "
                              "padding:5px 11px; font-size:11.5px; font-weight:700; }")
        quiet = (f"QPushButton {{ background:transparent; color:{t['muted']}; border:none; padding:5px 4px; "
                 "font-size:11px; } QPushButton:hover { text-decoration: underline; }")
        self.later.setStyleSheet(quiet)
        self.never.setStyleSheet(quiet)
