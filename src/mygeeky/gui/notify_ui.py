"""Notifications on the computer: the ⚙ Settings section that shows exactly what you agreed to (all off until
you switch a kind on), and the one system notification a summary becomes (notify.py decides what's in it).

Showing it: the system tray's message where there is a tray (Windows, macOS, most Linux desktops), else
notify-send on Linux or osascript on macOS. Clicking the tray message opens the right tab; the tab's planet
also gets a dot, so a missed notification is still seen.
"""

from __future__ import annotations

import shutil
import sys
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from .. import notify, winproc


class NotifySettings(QWidget):
    """🔔 Notifications in ⚙: one switch per kind, how often, quiet hours, and a line saying what's on."""

    def __init__(self, get: Callable[[], dict[str, Any]], save: Callable[[dict[str, Any]], dict[str, Any]],
                 theme: Callable[[], dict[str, Any]]) -> None:
        super().__init__()
        self.get, self.save, self.theme = get, save, theme
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(4)
        self.head = QLabel("🔔 NOTIFICATIONS")
        lay.addWidget(self.head)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.PlainText)
        lay.addWidget(self.summary)
        self.boxes: dict[str, QCheckBox] = {}
        for kind, emoji, label, about, _short in notify.KINDS:
            box = QCheckBox(f"{emoji}  {label}")
            box.setToolTip(about)
            box.toggled.connect(self._changed)
            self.boxes[kind] = box
            lay.addWidget(box)
        row = QHBoxLayout()
        self.every = QComboBox()
        self.every.addItem("At most once a day", "daily")
        self.every.addItem("At most once a week", "weekly")
        self.every.currentIndexChanged.connect(self._changed)
        row.addWidget(self.every)
        row.addStretch(1)
        lay.addLayout(row)
        row = QHBoxLayout()                              # quiet hours on their own line, so ⚙ fits a narrow panel
        self.quiet_label = QLabel("Quiet from")
        row.addWidget(self.quiet_label)
        self.q_start, self.q_end = QSpinBox(), QSpinBox()
        for spin in (self.q_start, self.q_end):
            spin.setRange(0, 23)
            spin.setSuffix(":00")
            spin.valueChanged.connect(self._changed)
        row.addWidget(self.q_start)
        self.to_label = QLabel("to")
        row.addWidget(self.to_label)
        row.addWidget(self.q_end)
        row.addStretch(1)
        lay.addLayout(row)
        self.off_btn = QPushButton("Turn all off")
        self.off_btn.setCursor(Qt.PointingHandCursor)
        self.off_btn.clicked.connect(self.all_off)
        lay.addWidget(self.off_btn, 0, Qt.AlignLeft)
        self._loading = False
        self.load()

    def load(self) -> None:
        s = self.get()
        self._loading = True
        for kind, box in self.boxes.items():
            box.setChecked(kind in s["kinds"])
        self.every.setCurrentIndex(0 if s["every"] == "daily" else 1)
        self.q_start.setValue(s["quiet"][0])
        self.q_end.setValue(s["quiet"][1])
        self._loading = False
        self._show(s)

    def current(self) -> dict[str, Any]:
        return {"kinds": [k for k, b in self.boxes.items() if b.isChecked()], "every": self.every.currentData(),
                "quiet": [self.q_start.value(), self.q_end.value()]}

    def _changed(self, *_: Any) -> None:
        if not self._loading:
            self._show(self.save(self.current()))

    def all_off(self) -> None:
        self._loading = True
        for box in self.boxes.values():
            box.setChecked(False)
        self._loading = False
        self._show(self.save(self.current()))

    def apply_theme(self) -> None:
        self._show(self.get())

    def _show(self, s: dict[str, Any]) -> None:
        t = self.theme()
        on = bool(s["kinds"])
        self.summary.setText(notify.describe(s))
        for w in (self.every, self.quiet_label, self.q_start, self.to_label, self.q_end, self.off_btn):
            w.setEnabled(on)
        self.head.setStyleSheet(f"color:{t['text']}; font-size:10.5px; font-weight:700; letter-spacing:0.5px; "
                                "background:transparent;")
        self.summary.setStyleSheet(f"color:{'#7fe6c8' if on else t['muted']}; font-size:11px; background:transparent;")
        for w in (self.quiet_label, self.to_label):
            w.setStyleSheet(f"color:{t['text']}; font-size:11px; background:transparent;")
        self.off_btn.setStyleSheet(f"QPushButton {{ background:{t['btn_bg']}; color:{t['text']}; border:none; border-radius:7px; "
                                   f"padding:4px 10px; font-size:11px; }} QPushButton:disabled {{ color:{t['muted']}; }}")
        for box in self.boxes.values():                 # a visible box, empty or filled: plainly a switch
            box.setStyleSheet(
                f"QCheckBox {{ color:{t['text']}; font-size:11px; background:transparent; spacing:7px; }}"
                f"QCheckBox::indicator {{ width:14px; height:14px; border:1.5px solid {t['muted']}; border-radius:4px; "
                f"background:transparent; }}"
                "QCheckBox::indicator:checked { background:#7a5cff; border-color:#7a5cff; }")


class Notifier:
    """Shows one notification. `on_click(tab)` runs when the tray message is clicked."""

    def __init__(self, icon, on_click: Callable[[str], None]) -> None:
        self.icon, self.on_click = icon, on_click
        self.tray: QSystemTrayIcon | None = None
        self.tab = ""

    def show(self, title: str, body: str, tab: str) -> bool:
        self.tab = tab
        if QSystemTrayIcon.isSystemTrayAvailable() and QSystemTrayIcon.supportsMessages():
            if self.tray is None:
                self.tray = QSystemTrayIcon(self.icon)
                self.tray.setToolTip("myGeeKy")
                self.tray.messageClicked.connect(lambda: self.on_click(self.tab))
                self.tray.activated.connect(lambda _reason: self.on_click(self.tab))
            self.tray.show()
            self.tray.showMessage(title, body, self.icon, 15000)
            return True
        try:
            if sys.platform.startswith("linux") and shutil.which("notify-send"):
                winproc.popen(["notify-send", "--app-name=myGeeKy", title, body])
                return True
            if sys.platform == "darwin" and shutil.which("osascript"):
                safe = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')       # noqa: E731
                winproc.popen(["osascript", "-e", f'display notification "{safe(body)}" with title "{safe(title)}"'])
                return True
        except OSError:
            return False
        return False
