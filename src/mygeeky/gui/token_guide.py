"""A picture guide for making a GitHub token: one drawn step at a time, numbered dots underneath.

The steps move on by themselves every few seconds and stop as soon as you pick one (a dot, or ‹ ›). In setup,
whose pages can't scroll, it starts folded behind "Show me step by step" (folded=True). The
steps, their drawings and the timing come from data/token_guides.json (written by tools/token_guides.py),
which the phone reads too (components/token-guide.tsx), so both show the same guide.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

GUIDES_FILE = Path(__file__).resolve().parents[1] / "data" / "token_guides.json"


def load() -> dict[str, Any]:
    try:
        return json.loads(GUIDES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"seconds": 4, "guides": {}}


class TokenGuide(QWidget):
    def __init__(self, key: str, parent: QWidget | None = None, folded: bool = False) -> None:
        super().__init__(parent)
        data = load()
        self.guide = data["guides"].get(key) or {"title": "", "url": "", "tips": [], "steps": []}
        self.steps = self.guide["steps"]
        self.at = 0
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 4)
        self.show_btn = QPushButton("\U0001f5bc  Show me step by step")
        self.show_btn.setCursor(Qt.PointingHandCursor)
        self.show_btn.clicked.connect(self.unfold)
        self.show_btn.setVisible(folded)
        outer.addWidget(self.show_btn, 0, Qt.AlignLeft)
        self.body = QWidget()
        self.body.setVisible(not folded)
        outer.addWidget(self.body)
        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        head = QHBoxLayout()
        self.title = QLabel(self.guide["title"])
        self.title.setStyleSheet("font-weight:700; font-size:13px;")
        head.addWidget(self.title, 1)
        self.open_btn = QPushButton("Open GitHub's token page ↗")
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.guide["url"])))
        head.addWidget(self.open_btn)
        lay.addLayout(head)
        self.picture = QSvgWidget()
        self.picture.setFixedSize(QSize(320, 150))
        lay.addWidget(self.picture, 0, Qt.AlignHCenter)
        self.step_title = QLabel("")
        self.step_title.setTextFormat(Qt.PlainText)
        self.step_title.setStyleSheet("font-weight:700;")
        lay.addWidget(self.step_title)
        self.step_text = QLabel("")
        self.step_text.setTextFormat(Qt.PlainText)
        self.step_text.setWordWrap(True)
        lay.addWidget(self.step_text)
        dots = QHBoxLayout()
        dots.setSpacing(4)
        self.prev_btn = QPushButton("‹")
        self.prev_btn.clicked.connect(lambda: self.pick(self.at - 1))
        dots.addWidget(self.prev_btn)
        self.dots: list[QPushButton] = []
        for i in range(len(self.steps)):
            d = QPushButton(str(i + 1))
            d.setFixedSize(26, 26)
            d.setCursor(Qt.PointingHandCursor)
            d.setToolTip(self.steps[i]["title"])
            d.clicked.connect(lambda checked=False, i=i: self.pick(i))
            self.dots.append(d)
            dots.addWidget(d)
        self.next_btn = QPushButton("›")
        self.next_btn.clicked.connect(lambda: self.pick(self.at + 1))
        dots.addWidget(self.next_btn)
        dots.addStretch(1)
        lay.addLayout(dots)
        for b in (self.prev_btn, self.next_btn):
            b.setFixedSize(26, 26)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("QPushButton { padding:0; font-size:15px; font-weight:700; border-radius:13px; }")
        self.tips = QLabel("\n".join(f"• {t}" for t in self.guide["tips"]))
        self.tips.setTextFormat(Qt.PlainText)
        self.tips.setWordWrap(True)
        self.tips.setStyleSheet("color: rgba(240,240,245,170); font-size:12px;")
        lay.addWidget(self.tips)
        self.timer = QTimer(self)
        self.timer.setInterval(int(data.get("seconds", 4)) * 1000)
        self.timer.timeout.connect(lambda: self.show_step(self.at + 1))
        if self.steps:
            self.show_step(0)
            if not folded:
                self.timer.start()

    def unfold(self) -> None:
        self.show_btn.setVisible(False)
        self.body.setVisible(True)
        self.show_step(0)
        self.timer.start()

    def show_step(self, i: int) -> None:
        self.at = i % len(self.steps)
        step = self.steps[self.at]
        self.picture.load(QByteArray(step["svg"].encode("utf-8")))
        self.step_title.setText(f"{self.at + 1}. {step['title']}")
        self.step_text.setText(step["text"])
        for n, d in enumerate(self.dots):
            on = n == self.at
            d.setStyleSheet("QPushButton { border-radius:13px; font-weight:700; padding:0; "
                            + ("background:#ff6fd8; color:#3a0a2e; }" if on else "background:#2a2a3c; color:#c8c8d8; }"))

    def pick(self, i: int) -> None:
        """You chose a step: show it, and stop moving on by itself."""
        self.timer.stop()
        self.show_step(i)
