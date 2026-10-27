"""The opening animation: the badge's arms spin in out of nothing, then G, ee and K pop
in, and m and y land last. The same timeline as docs/loader.svg, drawn with Qt from the
layers that docs/make_loader.py exports (Qt can't play the SVG's CSS animation).

Shown the first time myGeeKy starts, while the panel is being built."""
from __future__ import annotations

import math
from dataclasses import dataclass

from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

INTRO_SECONDS = 3.2          # then it only breathes, until the panel is ready
LAYERS = ("ring", "G", "ee", "K", "m", "y")


@dataclass
class Pose:
    opacity: float = 1.0
    dx: float = 0.0          # in units of the badge's size
    dy: float = 0.0
    scale: float = 1.0
    turn: float = 0.0        # degrees
    glow: float = 0.0        # 0..1: drawn again, brighter, on top


def _clamp(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def _out_cubic(p: float) -> float:
    return 1 - (1 - p) ** 3


def _out_back(p: float, s: float = 1.7) -> float:
    """Overshoots a little past 1, then settles: the "pop"."""
    p -= 1
    return p * p * ((s + 1) * p + s) + 1


def _phase(t: float, start: float, length: float) -> float:
    return _clamp((t - start) / length)


def pose(name: str, t: float) -> Pose:
    """Where each layer is at t seconds (the same timeline as docs/loader.svg)."""
    if name == "badge":
        return Pose(opacity=_out_cubic(_phase(t, 0, 0.5)))
    if name == "ring":
        p = _out_cubic(_phase(t, 0, 1.4))
        breathe = 0.0 if t < INTRO_SECONDS else 0.1 * (1 - math.cos((t - INTRO_SECONDS) * math.pi))
        flash = _phase(t, 2.6, 0.6)
        glow = (flash / 0.3 if flash < 0.3 else (1 - flash) / 0.7) * 0.85 if 0 < flash < 1 else 0.0
        return Pose(opacity=(0.05 + 0.95 * p) * (1 - breathe), scale=0.92 + 0.08 * p,
                    turn=-360 * (1 - p), glow=glow)
    if name == "G":
        p = _phase(t, 1.2, 0.6)
        return Pose(opacity=_clamp(p / 0.6), scale=0.6 + 0.4 * _out_back(p))
    if name == "ee":
        p = _phase(t, 1.55, 0.55)
        e = _out_back(p, 1.2)
        return Pose(opacity=_clamp(p / 0.6), dx=-0.055 * (1 - e), scale=0.7 + 0.3 * e)
    if name == "K":
        p = _phase(t, 1.7, 0.6)
        e = _out_back(p)
        return Pose(opacity=_clamp(p / 0.6), dy=-0.08 * (1 - e), scale=0.85 + 0.15 * e)
    if name in ("m", "y"):                         # the dramatic landing: big, bright, from far away
        p = _phase(t, 2.3 if name == "m" else 2.4, 0.7)
        e = _out_back(p, 2.2)
        side = -1 if name == "m" else 1
        return Pose(opacity=_clamp(p / 0.4), dy=side * 0.23 * (1 - e), scale=1 + 0.8 * (1 - e),
                    glow=(1 - p) if p > 0 else 0.0)
    raise ValueError(name)


def _qt():
    from PySide6.QtCore import QElapsedTimer, QEventLoop, QPointF, QRectF, Qt, QTimer
    from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPixmap, QRegion
    from PySide6.QtWidgets import QWidget
    return locals()


BADGE_BG = "#14141f"          # the app icon's dark ground: the neon letters were drawn for it


def make_splash(size: int = 260, dark: bool = True):
    """A small, frameless window in the middle of the screen that plays the animation. On a light theme (`dark`
    False) it stands on a dark rounded badge, like the app icon: its neon, half-transparent letters vanish on white."""
    q = _qt()
    Qt, QWidget, QPixmap, QPainter = q["Qt"], q["QWidget"], q["QPixmap"], q["QPainter"]
    QTimer, QElapsedTimer, QRectF, QPointF, QColor = q["QTimer"], q["QElapsedTimer"], q["QRectF"], q["QPointF"], q["QColor"]

    class LoadingSplash(QWidget):
        def __init__(self) -> None:
            super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            self.setWindowTitle("myGeeKy")
            self.setFixedSize(size, size)
            self.layers = {n: QPixmap(str(ASSETS_DIR / f"loader_{n}.png")) for n in LAYERS}
            # each letter grows and shrinks around its own middle (the ring around the badge's)
            self.centres = {}
            for n, pix in self.layers.items():
                box = q["QRegion"](pix.mask()).boundingRect() if n != "ring" and not pix.isNull() else None
                self.centres[n] = ((box.center().x() + 0.5) / pix.width(), (box.center().y() + 0.5) / pix.height())                     if box is not None and not box.isEmpty() else (0.5, 0.5)
            self.clock = QElapsedTimer()
            self.fade = 1.0
            self.timer = QTimer(self)
            self.timer.setInterval(16)
            self.timer.timeout.connect(self.update)
            screen = q["QGuiApplication"].primaryScreen()
            if screen is not None:
                area = screen.availableGeometry()
                self.move(area.center().x() - size // 2, area.center().y() - size // 2)

        def start(self) -> None:
            self.clock.start()
            self.timer.start()
            self.show()

        def seconds(self) -> float:
            return self.clock.elapsed() / 1000 if self.clock.isValid() else 0.0

        def paintEvent(self, event) -> None:  # noqa: N802 -- Qt's own naming convention
            t = self.seconds()
            s = float(self.width())
            painter = QPainter(self)
            painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
            # on a dark theme the ring and letters stand on their own, as the logo does; on a light one they'd fade
            # into the light behind them, so they get the icon's dark badge
            if not dark:
                painter.setPen(q["Qt"].NoPen)
                ground = QColor(BADGE_BG)
                ground.setAlphaF(0.94 * self.fade)
                painter.setBrush(ground)
                painter.drawRoundedRect(QRectF(0, 0, s, s), s * 0.22, s * 0.22)
            for name in LAYERS:
                pix = self.layers[name]
                if pix.isNull():
                    continue
                p = pose(name, t)
                if p.opacity <= 0.001:
                    continue
                painter.save()
                cx, cy = self.centres[name][0] * s, self.centres[name][1] * s
                painter.translate(cx + p.dx * s, cy + p.dy * s)
                painter.rotate(p.turn)
                painter.scale(p.scale, p.scale)
                target = QRectF(-cx, -cy, s, s)
                painter.setOpacity(_clamp(p.opacity) * self.fade)
                painter.drawPixmap(target, pix, QRectF(pix.rect()))
                if p.glow > 0.01:                  # the bright flash: the layer again, added on top
                    painter.setCompositionMode(QPainter.CompositionMode_Plus)
                    painter.setOpacity(_clamp(p.glow) * 0.8 * self.fade)
                    painter.drawPixmap(target, pix, QRectF(pix.rect()))
                painter.restore()
            painter.end()

        def play(self, seconds: float = INTRO_SECONDS) -> None:
            """Show it and keep the app responsive until the intro has played."""
            self.start()
            loop = q["QEventLoop"]()
            QTimer.singleShot(max(0, int((seconds - self.seconds()) * 1000)), loop.quit)
            loop.exec()

        def finish(self, ms: int = 300) -> None:
            """Fade out and close (the panel is up)."""
            steps = max(1, ms // 16)
            state = {"n": 0}
            fader = QTimer(self)
            fader.setInterval(16)

            def step() -> None:
                state["n"] += 1
                self.fade = max(0.0, 1 - state["n"] / steps)
                self.update()
                if state["n"] >= steps:
                    fader.stop()
                    self.timer.stop()
                    self.close()
                    self.deleteLater()
            fader.timeout.connect(step)
            fader.start()

    return LoadingSplash()
