"""⚙ → Window: where the panel lives and how it stacks with other windows.

Two small controls, both instant (nothing to save or confirm):
  * LayerSwitch: one segmented control: In front / Normal / Behind.
  * ScreenPicker: a little drawing of your screen. Click the spot where the
    panel should live (left or right edge, bottom-left or bottom-right
    corner); the drawing shows where it opens. Next to it, Off screen hides
    the panel until you open myGeeKy again.
"""
from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QSizePolicy, QWidget

LAYER_CHOICES = (
    ("front", "In front", "Always in front of other windows"),
    ("normal", "Normal", "Like any window: others can cover it"),
    ("behind", "Behind", "Folded, it waits under your windows, on the desktop"),
)
RAIL_CHOICES = (
    ("auto", "Screen edge", "The menu sits on the side of the panel nearest the screen's edge"),
    ("left", "Left", "The menu always on the panel's left"),
    ("right", "Right", "The menu always on the panel's right"),
)
SIDE_LABELS = {
    "right": ("Right edge", "folded in the middle of the right edge"),
    "left": ("Left edge", "folded in the middle of the left edge"),
    "bottom-right": ("Bottom right", "folded in the corner, rises to the middle when opened"),
    "bottom-left": ("Bottom left", "folded in the corner, rises to the middle when opened"),
}


def qcolor(spec: str) -> QColor:
    """'#rrggbb' or the themes' 'rgba(r,g,b,a)' (a in 0-255)."""
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)", spec or "")
    if m:
        r, g, b = (int(x) for x in m.groups()[:3])
        a = m.group(4)
        alpha = 255 if a is None else (int(float(a) * 255) if "." in a and float(a) <= 1 else int(float(a)))
        return QColor(r, g, b, max(0, min(255, alpha)))
    c = QColor(spec)
    return c if c.isValid() else QColor("#888888")


class LayerSwitch(QWidget):
    """In front | Normal | Behind (or any other `choices`), as one segmented pill."""

    changed = Signal(str)

    def __init__(self, value: str, parent: QWidget | None = None, choices: tuple = LAYER_CHOICES,
                 name: str = "Stay") -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        for key, label, tip in choices:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(tip)
            btn.setAccessibleName(f"{name}: {label}")
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked=False, k=key: self._pick(k))
            self.group.addButton(btn)
            self.buttons[key] = btn
            row.addWidget(btn)
        self.set_value(value)

    def value(self) -> str:
        return next((k for k, b in self.buttons.items() if b.isChecked()), next(iter(self.buttons)))

    def set_value(self, value: str) -> None:
        self.buttons.get(value, next(iter(self.buttons.values()))).setChecked(True)

    def _pick(self, key: str) -> None:
        self.changed.emit(key)

    def set_theme(self, theme: dict[str, Any]) -> None:
        self.setObjectName("layerSwitch")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"#layerSwitch {{ background:{theme['btn_bg']}; border-radius:9px; }}"
            f"QPushButton {{ background:transparent; color:{theme['muted']}; border:none; border-radius:7px; "
            f"padding:5px 4px; font-size:11px; font-weight:600; }}"
            f"QPushButton:hover {{ color:{theme['text']}; }}"
            f"QPushButton:checked {{ background:{theme['accent']}; color:{theme['on_accent']}; }}")


class ScreenPicker(QWidget):
    """A small screen: click a spot to dock the panel there. Hover previews the
    spot; the selected one shows where the panel opens."""

    picked = Signal(str)
    hovered = Signal(str)       # "" when the mouse leaves every spot

    W, H = 150, 92

    def __init__(self, side: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.side = side
        self.hover = ""
        self.setFixedSize(self.W, self.H)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName("Where the panel lives on your screen")
        self.colors = {"frame": QColor("#9a9ab0"), "screen": QColor(255, 255, 255, 18), "accent": QColor("#7fd8ff"),
                       "muted": QColor(240, 240, 245, 120), "on": QColor("#15151f")}

    def set_side(self, side: str) -> None:
        self.side = side
        self.update()

    def set_theme(self, theme: dict[str, Any]) -> None:
        self.colors = {"frame": qcolor(theme["muted"]), "screen": qcolor(theme["card_bg"]),
                       "accent": qcolor(theme["accent"]), "muted": qcolor(theme["muted"]),
                       "on": qcolor(theme["on_accent"])}
        self.update()

    # ---- geometry of the drawing
    def _screen(self) -> QRectF:
        return QRectF(6, 4, self.W - 12, self.H - 20)

    def _spots(self) -> dict[str, QPointF]:
        s = self._screen().adjusted(9, 9, -9, -9)
        return {"left": QPointF(s.left(), s.center().y()), "right": QPointF(s.right(), s.center().y()),
                "bottom-left": QPointF(s.left(), s.bottom()), "bottom-right": QPointF(s.right(), s.bottom())}

    def _spot_at(self, pos) -> str:
        for key, c in self._spots().items():
            if (QPointF(pos) - c).manhattanLength() <= 16:
                return key
        return ""

    # ---- mouse
    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        spot = self._spot_at(event.position())
        if spot != self.hover:
            self.hover = spot
            self.setCursor(Qt.PointingHandCursor if spot else Qt.ArrowCursor)
            self.hovered.emit(spot)
            self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self.hover:
            self.hover = ""
            self.hovered.emit("")
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        spot = self._spot_at(event.position())
        if spot and event.button() == Qt.LeftButton:
            self.side = spot
            self.picked.emit(spot)
            self.update()

    # ---- drawing
    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        c = self.colors
        scr = self._screen()
        # the monitor and its stand
        p.setPen(QPen(c["frame"], 1.4))
        p.setBrush(c["screen"])
        p.drawRoundedRect(scr, 7, 7)
        stand = QPainterPath()
        stand.moveTo(scr.center().x() - 7, scr.bottom() + 1)
        stand.lineTo(scr.center().x() - 10, self.H - 5)
        stand.lineTo(scr.center().x() + 10, self.H - 5)
        stand.lineTo(scr.center().x() + 7, scr.bottom() + 1)
        p.drawPath(stand)

        spots = self._spots()
        # where the selected spot opens: a slim panel at that edge, in the middle
        sel = spots.get(self.side)
        if sel is not None:
            left = self.side.endswith("left")
            ph = scr.height() * 0.58
            px = scr.left() + 20 if left else scr.right() - 20 - 16       # inside the edge dots, clear of them
            panel = QRectF(px, scr.center().y() - ph / 2, 16, ph)
            fill = QColor(c["accent"])
            fill.setAlpha(46)
            p.setPen(QPen(c["accent"], 1, Qt.DashLine))
            p.setBrush(fill)
            p.drawRoundedRect(panel, 4, 4)
            if self.side.startswith("bottom"):        # it rises from the corner to the middle
                x = panel.center().x()
                p.setPen(QPen(c["accent"], 1.4))
                p.drawLine(QPointF(x, sel.y() - 2), QPointF(x, panel.center().y() + 4))
                head = QPainterPath()
                head.moveTo(x - 3.5, panel.center().y() + 8)
                head.lineTo(x, panel.center().y() + 3)
                head.lineTo(x + 3.5, panel.center().y() + 8)
                p.drawPath(head)

        # the four spots: the folded icon could live at any of them
        for key, center in spots.items():
            on, hot = key == self.side, key == self.hover
            r = 7.5 if on else 6 if hot else 5
            if on:
                ring = QColor(c["accent"])
                ring.setAlpha(70)
                p.setPen(Qt.NoPen)
                p.setBrush(ring)
                p.drawEllipse(center, r + 4, r + 4)
                p.setBrush(c["accent"])
            else:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(c["accent"] if hot else c["muted"], 1.6))
            p.drawEllipse(center, r, r)
        p.end()
