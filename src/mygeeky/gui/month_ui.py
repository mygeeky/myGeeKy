"""The My month tab: your rank on its ladder, your month in eight drawings with GeekOc (monthviz.py), and this
month's card to save or copy (month.py does the counting).

The card and the ladder are SVGs drawn by month.py, the same drawings the phone makes (lib/month.ts), shown
here with QSvgRenderer and saved as a 1080 x 1350 PNG -- the 4:5 shape LinkedIn and X show largest. Nothing is
posted: you save or copy the picture and share it yourself.
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget,
)

from .. import month as months
from .. import monthviz
from . import app as logic

CARD_PX = (1080, 1350)
FRESH_SECONDS = 60                # coming back to You within this shows what's drawn; later, it's redrawn
CARD_MAX = 380                   # the card's width on the panel
DRAWING_MAX = 420                # each drawing's


class SvgPicture(QWidget):
    """An SVG drawn at the panel's width, keeping its shape (no wider than `max_width`)."""

    def __init__(self, max_width: int = 10_000, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.renderer = QSvgRenderer(self)
        self.max_width = max_width
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def set_svg(self, svg: str) -> None:
        self.renderer.load(QByteArray(svg.encode("utf-8")))
        self.updateGeometry()
        self.update()

    def _ratio(self) -> float:
        size = self.renderer.defaultSize()
        return size.height() / size.width() if size.width() > 0 else 1.0

    def hasHeightForWidth(self) -> bool:            # noqa: N802 (Qt)
        return True

    def heightForWidth(self, w: int) -> int:        # noqa: N802 (Qt)
        return int(min(w, self.max_width) * self._ratio())

    def sizeHint(self) -> QSize:                    # noqa: N802 (Qt)
        w = min(self.max_width, 360)
        return QSize(w, int(w * self._ratio()))

    def paintEvent(self, event) -> None:            # noqa: N802, ARG002 (Qt)
        w = min(self.width(), self.max_width)
        h = w * self._ratio()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self.renderer.render(p, QRectF((self.width() - w) / 2, 0, w, h))
        p.end()


def card_image(svg: str, size: tuple[int, int] = CARD_PX) -> QImage:
    """The card as a picture to save or paste."""
    img = QImage(size[0], size[1], QImage.Format_ARGB32)
    img.fill(QColor("#ffffff"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(p, QRectF(0, 0, size[0], size[1]))
    p.end()
    return img


def rank_line(s: dict[str, Any]) -> str:
    if s["next"] is None:
        return f"{s['rank_name']} · {s['points']} points: the top rank!"
    return f"{s['rank_name']} · {s['points']} points · {s['to_next']} more to {s['next']}"


def month_line(s: dict[str, Any]) -> str:
    gained = f"+{s['month_points']} points in {s['month_name']}"
    return gained + (f" · promoted to {s['rank_name']} this month!" if s["promoted"] else "")


def points_help() -> str:
    names = {k: v[2] for k, v in months.KINDS.items()}
    return "Points: " + ", ".join(f"{names[k]} +{n}" for k, n in sorted(months.POINTS.items(), key=lambda kv: kv[1]))


class MonthPage(QWidget):
    """Your rank and this month's card. `theme()` gives the panel's colours, `toast(text)` says something briefly."""

    def __init__(self, cfg, theme: Callable[[], dict[str, Any]], toast: Callable[[str], None],
                 run_async: Callable[[Callable[[], Any], Callable[[Any], None]], None] | None = None) -> None:
        super().__init__()
        self.cfg, self.theme, self.toast, self.run_async = cfg, theme, toast, run_async
        today = date.today()
        self.shown = (today.year, today.month)
        self.hidden: set[str] = set()
        self.data: dict[str, Any] | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 4, 4)
        lay.setSpacing(8)
        nav = QHBoxLayout()
        self.prev_btn, self.next_btn = QPushButton("‹"), QPushButton("›")
        self.title = QLabel("")
        self.title.setAlignment(Qt.AlignCenter)
        for b, step in ((self.prev_btn, -1), (self.next_btn, 1)):
            b.setFixedSize(30, 30)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, step=step: self.move(step))
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.title, 1)
        nav.addWidget(self.next_btn)
        lay.addLayout(nav)
        self.rank = QLabel("")
        self.rank.setTextFormat(Qt.PlainText)
        self.rank.setWordWrap(True)
        lay.addWidget(self.rank)
        self.gained = QLabel("")
        self.gained.setTextFormat(Qt.PlainText)
        lay.addWidget(self.gained)
        self.ladder = SvgPicture()
        lay.addWidget(self.ladder)
        self.card_head = QLabel("YOUR CARD")
        lay.addWidget(self.card_head)
        self.card = SvgPicture(CARD_MAX)
        lay.addWidget(self.card)
        self.show_label = QLabel("Show on the card:")
        lay.addWidget(self.show_label)
        self.toggles = QGridLayout()
        self.toggles.setSpacing(2)
        lay.addLayout(self.toggles)
        row = QHBoxLayout()
        self.save_btn, self.copy_btn = QPushButton("💾  Save image…"), QPushButton("📋  Copy image")
        for b in (self.save_btn, self.copy_btn):
            b.setCursor(Qt.PointingHandCursor)
            row.addWidget(b)
        self.save_btn.clicked.connect(self.save)
        self.copy_btn.clicked.connect(self.copy)
        lay.addLayout(row)
        self.dives_head = QLabel("YOUR MONTH IN PICTURES")
        lay.addWidget(self.dives_head)
        self.dives: list[tuple[QLabel, SvgPicture, QLabel, SvgPicture]] = []
        for _key, title, _pose, _draw in monthviz.DIVES:
            head = QHBoxLayout()
            geek = SvgPicture(54)
            geek.setFixedSize(54, 54)
            words = QVBoxLayout()
            name, said = QLabel(title), QLabel("")
            said.setTextFormat(Qt.PlainText)
            said.setWordWrap(True)
            words.addWidget(name)
            words.addWidget(said)
            head.addWidget(geek)
            head.addLayout(words, 1)
            lay.addLayout(head)
            drawing = SvgPicture(DRAWING_MAX)
            lay.addWidget(drawing)
            self.dives.append((name, said, geek, drawing))
        self.note = QLabel("Points come from what you do yourself: reading, learning, building, sharing ideas and "
                           "meeting people. They count over all your time in myGeeKy, so a rank never goes down. "
                           "Worked out on this computer; nothing is sent anywhere, and nothing is posted for you.")
        self.note.setWordWrap(True)
        lay.addWidget(self.note)
        self.points = QLabel(points_help())
        self.points.setWordWrap(True)
        lay.addWidget(self.points)
        lay.addStretch(1)

    # ---- data
    def move(self, step: int) -> None:
        y, m = self.shown
        m += step
        y, m = (y - 1, 12) if m < 1 else (y + 1, 1) if m > 12 else (y, m)
        self.shown = (y, m)
        self.hidden.clear()
        self.render()

    def show(self) -> None:
        """You opened the page: redraw unless it was drawn a moment ago (it reads several files)."""
        if self.data is None or time.monotonic() - getattr(self, "_drawn_at", 0.0) > FRESH_SECONDS:
            self.render()

    def svg(self) -> str:
        s = self.data or {}
        return months.card_svg(s, months.geekoc(months.card_pose(s)), self.hidden)

    def render(self) -> None:
        t = self.theme()
        self._drawn_at = time.monotonic()
        self.data = s = logic.get_month(self.cfg, *self.shown)
        today = date.today()
        self.prev_btn.setEnabled(self.shown > tuple(s["first"]))
        self.next_btn.setEnabled(self.shown < (today.year, today.month))
        self.title.setText(f"{s['month_name']} {s['year']}")
        light = QColor(t["text"]).lightness() < 128
        self.ladder.set_svg(months.ladder_svg(s["points"], light))
        self.rank.setText("🎖  " + rank_line(s))
        self.gained.setText(month_line(s))
        self.card.set_svg(self.svg())
        self._render_dives(t)
        while self.toggles.count():
            w = self.toggles.takeAt(0).widget()
            if w:
                w.deleteLater()
        for n, (kind, count) in enumerate(s["counts"].items()):
            box = QCheckBox(f"{count} {months.KINDS[kind][2] if count == 1 else months.KINDS[kind][1]}")
            box.setChecked(kind not in self.hidden)
            box.toggled.connect(lambda on, kind=kind: self._toggle(kind, on))
            box.setStyleSheet(f"color:{t['text']}; font-size:11px; background:transparent;")
            self.toggles.addWidget(box, n // 3, n % 3)
        self.show_label.setVisible(bool(s["counts"]))
        self.title.setStyleSheet(f"color:{t['text']}; font-size:15px; font-weight:700; background:transparent;")
        self.rank.setStyleSheet(f"color:{t['text']}; font-size:13px; font-weight:700; background:transparent;")
        for lbl in (self.gained, self.note, self.points, self.show_label):
            lbl.setStyleSheet(f"color:{t['muted']}; font-size:10.5px; background:transparent;")
        self.card_head.setStyleSheet(f"color:{t['text']}; font-size:10.5px; font-weight:700; letter-spacing:0.5px; "
                                     "margin-top:6px; background:transparent;")
        for b in (self.prev_btn, self.next_btn, self.save_btn, self.copy_btn):
            b.setStyleSheet(f"QPushButton {{ background:{t['btn_bg']}; color:{t['text']}; border:none; "
                            f"border-radius:8px; padding:6px 10px; font-weight:700; }} "
                            f"QPushButton:hover {{ background:{t['btn_hover']}; }} "
                            "QPushButton:disabled { color:rgba(128,128,128,120); }")

    def _render_dives(self, t: dict[str, Any]) -> None:
        stats = logic.get_month_stats(self.cfg, *self.shown)
        poses = {p: months.geekoc(p) for p in ("wave", "head", "swim", "point", "idle", "sleep", "think", "cheer", "proud")}
        for (key, _title, pose, draw), (name, said, geek, drawing) in zip(monthviz.DIVES, self.dives):
            drawing.set_svg(draw(stats, poses))
            geek.set_svg(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 620" width="620" height="620">'
                         f'{poses.get(pose, "")}</svg>')
            said.setText(monthviz.say(stats, key))
            name.setStyleSheet(f"color:{t['text']}; font-size:13px; font-weight:700; background:transparent;")
            said.setStyleSheet(f"color:{t['muted']}; font-size:11px; background:transparent;")
        self.dives_head.setStyleSheet(f"color:{t['text']}; font-size:10.5px; font-weight:700; letter-spacing:0.5px; "
                                      "margin-top:6px; background:transparent;")
        if self.run_async and self.cfg.github_username and not getattr(self, "_github_asked", False):
            self._github_asked = True             # once per panel: the newest GitHub events, then draw again
            self.run_async(lambda: logic.refresh_my_github(self.cfg),
                           lambda changed: self._render_dives(self.theme()) if changed is True else None)

    def _toggle(self, kind: str, on: bool) -> None:
        (self.hidden.discard if on else self.hidden.add)(kind)
        self.card.set_svg(self.svg())

    # ---- the picture
    def save(self) -> None:
        y, m = self.shown
        path, _ = QFileDialog.getSaveFileName(self, "Save your month card", str(Path.home() / f"mygeeky-{y}-{m:02d}.png"),
                                              "PNG image (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        if card_image(self.svg()).save(path, "PNG"):
            self.toast("Saved. Attach it to your post on LinkedIn, X or anywhere 🎉")
        else:
            self.toast("Couldn't save it there. Try another folder.")

    def copy(self) -> None:
        QApplication.clipboard().setImage(card_image(self.svg()))
        self.toast("Copied: paste it into your post 🎉")
