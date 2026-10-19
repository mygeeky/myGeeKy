"""While something loads: GeekOc swimming (a gentle bob and drift, bubbles rising) instead of a plain
"Loading…", with a line saying what is happening -- as on the phone (components/geek-loader.tsx).

It animates only while it is on screen: hidden (another tab, scrolled away in a closed page) it stops its
timer, so a loader left behind costs nothing.
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from .. import month

FRAME_MS = 33


class GeekLoader(QWidget):
    def __init__(self, text: str = "Loading…", color: str = "#a9b0d6", size: int = 72,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.text, self.color, self.size = text, QColor(color), size
        self.renderer = QSvgRenderer(QByteArray(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 620">{month.geekoc("swim")}</svg>'.encode("utf-8")), self)
        self.started = time.monotonic()
        self.timer = QTimer(self)
        self.timer.setInterval(FRAME_MS)
        self.timer.timeout.connect(self.update)
        self.setMinimumHeight(size + 46)
        self.setAccessibleName(text)

    def sizeHint(self) -> QSize:                    # noqa: N802 (Qt)
        return QSize(220, self.size + 46)

    def showEvent(self, ev) -> None:                # noqa: N802 (Qt)
        self.timer.start()
        super().showEvent(ev)

    def hideEvent(self, ev) -> None:                # noqa: N802 (Qt)
        self.timer.stop()
        super().hideEvent(ev)

    def paintEvent(self, ev) -> None:               # noqa: N802, ARG002 (Qt)
        t = time.monotonic() - self.started
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, top = self.width() / 2, 6
        for i in range(3):                          # bubbles rising past him, one after another
            k = ((t + i * 0.42) % 1.3) / 1.3
            r = 3 + i
            p.setPen(QPen(QColor(160, 220, 255, int(180 * (1 - k))), 1))
            p.setBrush(QColor(127, 216, 255, int(40 * (1 - k))))
            p.drawEllipse(QRectF(cx + (i - 1) * 12 - r, top + self.size * (0.75 - 0.8 * k), 2 * r, 2 * r))
        dx = math.sin(t * 2 * math.pi / 3.0) * 14
        dy = math.sin(t * 2 * math.pi / 1.4) * 5
        p.save()
        p.translate(cx + dx, top + self.size / 2 + dy)
        p.rotate(math.sin(t * 2 * math.pi / 3.0) * 6)
        self.renderer.render(p, QRectF(-self.size / 2, -self.size / 2, self.size, self.size))
        p.restore()
        if self.text:
            p.setPen(self.color)
            p.drawText(QRectF(0, top + self.size + 8, self.width(), 24), Qt.AlignHCenter | Qt.AlignTop, self.text)
        p.end()
