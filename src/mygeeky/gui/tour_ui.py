"""GeeKOc's tour over the panel (tour.py has which stops and their words): the panel dims, a spotlight sits on the
page's line in the side rail (or on a part of ⚙), and GeeKOc -- arms swimming -- says one thing beside it. Next,
Back, Skip; Esc skips, ← and → step. The first time, his first bubble asks for the tours' language.

The panel does the moving (MyGeekyPanel.tour_go opens the page, the rail or ⚙; tour_rect says where the spotlight
goes): this file only draws and steps. The phone has the same tour (components/tour-overlay.tsx)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QByteArray, QEvent, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import tour

MOVES = Path(__file__).resolve().parents[1] / "data" / "geekoc_moves.json"     # tools/geekoc_poses.py
DIM = QColor(6, 4, 16, 185)
SPOT = QColor("#ff6fd8")


@lru_cache(maxsize=1)
def _moves() -> dict[str, Any]:
    return json.loads(MOVES.read_text(encoding="utf-8"))


@lru_cache(maxsize=8)
def _frames(pose: str) -> tuple[QSvgRenderer, ...]:
    m = _moves()
    p = m["poses"].get(pose) or m["poses"]["wave"]
    return tuple(QSvgRenderer(QByteArray(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{m["viewBox"]}">'
                                         f'{"".join(p["parts"][i] for i in f)}</svg>'.encode()))
                 for f in p["frames"])


class GeekOcMover(QWidget):
    """GeeKOc in one pose, his arms swimming: the pose's frames, played in a loop while he's on screen."""

    def __init__(self, size: int = 76) -> None:
        super().__init__()
        self.setFixedSize(size, size)
        self.pose, self.frame = "wave", 0
        self.timer = QTimer(self)
        self.timer.setInterval(int(1000 / _moves().get("fps", 8)))
        self.timer.timeout.connect(self._tick)

    def set_pose(self, pose: str) -> None:
        self.pose, self.frame = pose, 0
        self.update()

    def _tick(self) -> None:
        self.frame = (self.frame + 1) % len(_frames(self.pose))
        self.update()

    def showEvent(self, e) -> None:  # noqa: N802
        self.timer.start()

    def hideEvent(self, e) -> None:  # noqa: N802
        self.timer.stop()

    def paintEvent(self, e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        frames = _frames(self.pose)
        frames[self.frame % len(frames)].render(p, QRectF(0, 0, self.width(), self.height()))
        p.end()


def _label(text: str, name: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName(name)
    lbl.setTextFormat(Qt.PlainText)          # the words are ours, but labels are plain text everywhere
    lbl.setWordWrap(True)
    return lbl


class TourOverlay(QWidget):
    """Covers the panel while a tour runs. `go(target)` moves the app, `rect(target)` is the spotlight (in this
    widget's coordinates, or None), `path(target)` its "Chances → Seasons", `done(finished)` ends it."""

    def __init__(self, parent: QWidget, cfg: Any, kind: str, steps: list[str], go: Callable[[str], None],
                 rect: Callable[[str], QRect | None], path: Callable[[str], str], done: Callable[[bool], None],
                 save: Callable[[], None]) -> None:
        super().__init__(parent)
        self.cfg, self.kind, self.steps = cfg, kind, steps
        self.go, self.rect_of, self.path_of, self.done, self.save = go, rect, path, done, save
        self.i = 0
        self.picking = not cfg.tour_lang                  # the very first bubble asks for the language
        self.hole: QRect | None = None
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        parent.installEventFilter(self)
        self.setGeometry(parent.rect())
        self.bubble = QFrame(self)
        self.bubble.setObjectName("tourBubble")
        self.gk = GeekOcMover()
        self.gk.setParent(self)
        self.show()
        self.raise_()
        self.setFocus()
        self.step()

    # ---- moving through it
    def lang(self) -> str:
        return tour.lang_of(self.cfg.tour_lang or "en")

    def step(self) -> None:
        self.hole = None
        stop = self.steps[self.i]
        target = "" if self.picking else tour.at(stop, "desktop")
        if target:
            self.go(target)
        self._fill()
        QTimer.singleShot(420 if target else 0, lambda: self._place(target))     # the page settles, then aim

    def next(self) -> None:
        if self.i >= len(self.steps) - 1:
            self.finish(True)
            return
        self.i += 1
        self.step()

    def back(self) -> None:
        if self.i:
            self.i -= 1
            self.step()

    def finish(self, finished: bool) -> None:
        self.parent().removeEventFilter(self)
        self.hide()
        self.deleteLater()
        self.done(finished)

    def pick(self, code: str) -> None:
        self.cfg.tour_lang = code
        self.save()
        self.picking = False
        self.step()

    # ---- drawing
    def _fill(self) -> None:
        old = self.bubble.layout()
        if old is not None:
            QWidget().setLayout(old)                       # drop the last stop's words and buttons
        lang, stop = self.lang(), self.steps[self.i]
        lay = QVBoxLayout(self.bubble)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        self.bubble.setLayoutDirection(Qt.RightToLeft if tour.rtl(lang) and not self.picking else Qt.LeftToRight)
        if self.picking:
            self.gk.set_pose("wave")
            lay.addWidget(_label("GeeKOc", "path"))
            lay.addWidget(_label("\n".join(w for w in tour.load()["ui"]["pick"].values()), "text"))
            grid = QGridLayout()
            grid.setSpacing(6)
            for n, (code, name) in enumerate(tour.load()["langs"].items()):
                b = QPushButton(name)
                b.setObjectName("lang")
                b.setCursor(Qt.PointingHandCursor)
                b.clicked.connect(lambda _=False, c=code: self.pick(c))
                grid.addWidget(b, n // 2, n % 2)
            lay.addLayout(grid)
        else:
            self.gk.set_pose(tour.load()["stops"][stop]["pose"])
            target = tour.at(stop, "desktop")
            lay.addWidget(_label(self.path_of(target) if target else "GeeKOc", "path"))
            lay.addWidget(_label(tour.text(stop, lang, self.kind), "text"))
            if tour.phrase(stop, lang):
                lay.addWidget(_label(tour.phrase(stop, lang), "phrase"))
            dots = QLabel(" ".join("●" if n == self.i else "○" for n in range(len(self.steps))))
            dots.setObjectName("dots")
            lay.addWidget(dots)
            row = QHBoxLayout()
            row.addStretch(1)
            last = self.i == len(self.steps) - 1

            def button(key: str, name: str, fn) -> None:
                b = QPushButton(tour.ui(key, lang))
                b.setObjectName(name)
                b.setCursor(Qt.PointingHandCursor)
                b.clicked.connect(fn)
                row.addWidget(b)
            if not last:
                button("skip", "ghost", lambda: self.finish(False))
            if self.i:
                button("back", "ghost", self.back)
            button("done" if last else "next", "go", self.next)
            lay.addLayout(row)
        self.bubble.setStyleSheet(
            "QFrame#tourBubble { background:#fbf9ff; border-radius:14px; }"
            "QLabel { background:transparent; color:#1d1838; font-size:12.5px; }"
            "QLabel#path { color:#7c3aed; font-size:10.5px; font-weight:800; }"
            "QLabel#phrase { color:#7c3aed; font-size:13px; font-weight:800; }"
            "QLabel#dots { color:#7c3aed; font-size:8px; letter-spacing:2px; }"
            "QPushButton { border:none; border-radius:8px; padding:5px 10px; font-size:11.5px; font-weight:700; }"
            "QPushButton#go { background:#7c3aed; color:#ffffff; }"
            "QPushButton#ghost { background:transparent; color:#6b6394; }"
            "QPushButton#lang { background:#efe9ff; color:#1d1838; padding:7px; font-size:12.5px; }")

    def _fit(self) -> None:
        """As tall as its words need at this width (wrapped labels don't say so by themselves)."""
        lay = self.bubble.layout()
        lay.activate()
        self.bubble.setFixedHeight(lay.totalHeightForWidth(self.bubble.width()))

    def _place(self, target: str) -> None:
        if not self.isVisible():
            return
        self.hole = self.rect_of(target) if target else None
        W, H = self.width(), self.height()
        gk = self.gk.width()
        if self.hole is None:                                       # no spotlight: in the middle
            bw = min(W - 40, 340)
            self.bubble.setFixedWidth(bw - gk)
            self._fit()
            x, y = (W - bw) // 2 + gk, int(H * 0.28)
        else:
            h = self.hole
            if h.top() < H * 0.15:                                  # up by ⚙: under it
                bw = min(W - 24, 320)
                x, y = W - bw - 10 + gk, h.bottom() + 12
            elif h.left() > W * 0.45:                               # the rail on the right: to its left
                bw = max(220, h.left() - 16)
                x, y = 8 + gk, h.center().y() - 40
            elif h.right() < W * 0.55:                              # the rail on the left: to its right
                bw = max(220, W - h.right() - 16)
                x, y = h.right() + 8 + gk, h.center().y() - 40
            else:                                                   # a part of ⚙ across the panel: above or below
                bw = min(W - 24, 340)
                x = (W - bw) // 2 + gk
                y = h.top() - 10 if h.center().y() > H / 2 else h.bottom() + 12
            self.bubble.setFixedWidth(bw - gk)
            self._fit()
            if h.top() >= H * 0.15 and not (h.left() > W * 0.45 or h.right() < W * 0.55) and h.center().y() > H / 2:
                y -= self.bubble.height()
        y = max(8, min(y, H - self.bubble.height() - 8))
        x = max(8 + gk, min(x, W - self.bubble.width() - 8))
        self.bubble.move(x, y)
        self.gk.move(x - gk + 4, y + self.bubble.height() - gk + 10)
        self.bubble.show()
        self.gk.show()
        self.gk.raise_()
        self.update()

    def paintEvent(self, e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        shade = QPainterPath()
        shade.addRoundedRect(QRectF(self.rect()), 20, 20)
        if self.hole is not None:
            spot = QPainterPath()
            spot.addRoundedRect(QRectF(self.hole), 10, 10)
            shade = shade.subtracted(spot)
        p.fillPath(shade, DIM)
        if self.hole is not None:
            p.setPen(QPen(SPOT, 2.5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(self.hole), 10, 10)
        p.end()

    # ---- keys and size
    def keyPressEvent(self, e) -> None:  # noqa: N802
        if e.key() == Qt.Key_Escape:
            self.finish(False)
        elif self.picking:
            return
        elif e.key() in (Qt.Key_Right, Qt.Key_Return, Qt.Key_Enter):
            self.next()
        elif e.key() == Qt.Key_Left:
            self.back()

    def mousePressEvent(self, e) -> None:  # noqa: N802
        e.accept()                           # the page under the shade isn't clickable while GeeKOc talks

    def eventFilter(self, obj, ev) -> bool:  # noqa: N802
        if ev.type() == QEvent.Resize:
            self.setGeometry(self.parent().rect())
            QTimer.singleShot(0, lambda: self._place(tour.at(self.steps[self.i], "desktop") if not self.picking else ""))
        return False
