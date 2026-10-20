"""News → 🏁 AI race, in the panel: who leads, what's new, the race replayed, how far open models trail, what each
model is best at, fingerprints, and a picker for your own work. airace.py works out every number; the phone shows
the same page (components/ai-race-view.tsx). Everything fits the panel's narrow column: details come on click.

Model and lab names come from the internet, so they're shown as plain text (or escaped where a label is rich).
"""

from __future__ import annotations

import html
import math
from typing import Any, Callable

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QToolTip, QVBoxLayout,
                               QWidget)

from .. import airace

# the two kinds of weights, and the skills in airace.GROUPS order (the dataviz palette's validated order; the ninth
# is a neutral grey): a colour per skill in the fingerprints, the same on the phone
CLOSED = {False: "#2a78d6", True: "#3987e5"}
OPEN = {False: "#eb6834", True: "#d95926"}
SKILL = {False: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948", "#7c7896"],
         True: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767", "#8f8ba8"]}
VIOLET = {False: "#6d4fff", True: "#a08cff"}
SHORT_ORG = {"Google DeepMind": "Google", "Z.ai (Zhipu AI)": "Z.ai", "Thinking Machines": "Thinking M."}
SHORT = {"Reasoning": "Rsn", "Coding": "Code", "Math": "Math", "Science": "Sci", "Agents": "Agt", "Knowledge": "Know",
         "Writing": "Wri", "Vision": "Vis", "Security": "Sec"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def month_label(iso: str) -> str:
    return f"{MONTHS[int(iso[5:7]) - 1]} {iso[:4]}"


def kind_color(open_: bool, dark: bool) -> str:
    return (OPEN if open_ else CLOSED)[dark]


def _label(text: str, css: str, rich: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.RichText if rich else Qt.PlainText)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(css + " background:transparent;")
    return lbl


# --------------------------------------------------------------------------- the race
class RaceBars(QWidget):
    """Six lanes: each lab's best model so far, the name inside its bar, the score after it."""
    LANE = 24

    def __init__(self, theme: dict[str, Any]) -> None:
        super().__init__()
        self.theme, self.rows = theme, []
        self.setMinimumHeight(self.LANE * 6 + 2)
        self.setMouseTracking(True)

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.update()

    def _geometry(self) -> list[tuple[QRectF, dict[str, Any]]]:
        if not self.rows:
            return []
        lo, hi = min(r["eci"] for r in self.rows) - 18, self.rows[0]["eci"]
        w = max(60, self.width() - 34)
        return [(QRectF(0, i * self.LANE + 2, max(56, (r["eci"] - lo) / max(1, hi - lo) * w), self.LANE - 6), r)
                for i, r in enumerate(self.rows)]

    def paintEvent(self, _event) -> None:  # noqa: N802 -- Qt's naming
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        dark = bool(self.theme.get("dark"))
        f = QFont(self.font())
        f.setPointSizeF(8.5)
        f.setBold(True)
        for rect, r in self._geometry():
            path = QPainterPath()
            path.addRoundedRect(rect, 4, 4)
            p.fillPath(path, QColor(kind_color(r["open"], dark)))
            p.setFont(f)
            p.setPen(QColor("#ffffff"))
            p.drawText(rect.adjusted(6, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft, SHORT_ORG.get(r["org"], r["org"]))
            p.setPen(QColor(self.theme["text"]))
            p.drawText(QRectF(rect.right() + 5, rect.top(), 40, rect.height()), Qt.AlignVCenter, f"{r['eci']:.0f}")

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        for rect, r in self._geometry():
            if rect.adjusted(0, 0, 40, 0).contains(event.position()):
                QToolTip.showText(event.globalPosition().toPoint(), f"{r['org']}\n{r['model']} · {r['eci']:.1f}", self)
                return
        QToolTip.hideText()


# --------------------------------------------------------------------------- the gap
class GapChart(QWidget):
    """The best closed and best open model so far, month by month, the gap between them shaded."""

    def __init__(self, theme: dict[str, Any]) -> None:
        super().__init__()
        self.theme, self.s = theme, None
        self.setMinimumHeight(92)
        self.setMouseTracking(True)

    def set_stats(self, s: dict[str, Any]) -> None:
        self.s = s
        self.update()

    def _points(self) -> tuple[list[QPointF], list[QPointF], list[int]]:
        s = self.s
        idx = [i for i, (c, o) in enumerate(zip(s["closed"], s["open"])) if c is not None and o is not None]
        if len(idx) < 2:
            return [], [], []
        vals = [s["closed"][i] for i in idx] + [s["open"][i] for i in idx]
        lo, hi = min(vals) - 3, max(vals) + 3
        w, h = self.width() - 4, self.height() - 20
        x = lambda k: 2 + k / (len(s["months"]) - 1) * w  # noqa: E731
        y = lambda v: 4 + (1 - (v - lo) / (hi - lo)) * (h - 4)  # noqa: E731
        return [QPointF(x(i), y(s["closed"][i])) for i in idx], [QPointF(x(i), y(s["open"][i])) for i in idx], idx

    def paintEvent(self, _event) -> None:  # noqa: N802
        if not self.s:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        dark = bool(self.theme.get("dark"))
        closed, opened, _ = self._points()
        if not closed:
            return
        band = QPainterPath(closed[0])
        for pt in closed[1:]:
            band.lineTo(pt)
        for pt in reversed(opened):
            band.lineTo(pt)
        band.closeSubpath()
        fill = QColor(VIOLET[dark])
        fill.setAlpha(36)
        p.fillPath(band, fill)
        for pts, color in ((closed, CLOSED[dark]), (opened, OPEN[dark])):
            p.setPen(QPen(QColor(color), 2))
            for a, b in zip(pts, pts[1:]):
                p.drawLine(a, b)
        f = QFont(self.font())
        f.setPointSizeF(7.5)
        p.setFont(f)
        p.setPen(QColor(self.theme["muted"]))
        months = self.s["months"]
        for k, iso in enumerate(months):
            if iso[5:7] == "01" and k > 0:
                xx = 2 + k / (len(months) - 1) * (self.width() - 4)
                p.drawText(QRectF(xx - 20, self.height() - 13, 40, 12), Qt.AlignCenter, iso[:4])

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        s = self.s
        if not s or len(s["months"]) < 2:
            return
        k = round((event.position().x() - 2) / max(1, self.width() - 4) * (len(s["months"]) - 1))
        k = max(0, min(len(s["months"]) - 1, k))
        c, o, b = s["closed"][k], s["open"][k], s["behind"][k]
        if c is None or o is None:
            return
        QToolTip.showText(event.globalPosition().toPoint(),
                          f"{month_label(s['months'][k])}\nClosed {c:.0f} · Open {o:.0f}\nOpen {b} months behind", self)


# --------------------------------------------------------------------------- best at
class Dots(QWidget):
    """A dot per model that is best at this skill: blue closed, orange open."""

    def __init__(self, models: list[dict[str, Any]], theme: dict[str, Any]) -> None:
        super().__init__()
        self.models, self.theme = models, theme
        self.setMinimumHeight(10)
        self.setToolTip("\n".join(m["model"] for m in models[:20]))

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        dark = bool(self.theme.get("dark"))
        x = 1.0
        for m in self.models:
            if x + 8 > self.width() - 22:
                break
            p.setBrush(QColor(kind_color(m["open"], dark)))
            p.drawEllipse(QRectF(x, 1.5, 7, 7))
            x += 9
        p.setPen(QColor(self.theme["muted"]))
        f = QFont(self.font())
        f.setPointSizeF(7.5)
        p.setFont(f)
        p.drawText(QRectF(x + 4, -1, 24, 12), Qt.AlignVCenter | Qt.AlignLeft, str(len(self.models)))


class SkillRow(QWidget):
    """One skill: its name, a dot per model best at it, and its top model. Click to open its top five."""

    def __init__(self, row: dict[str, Any], theme: dict[str, Any]) -> None:
        super().__init__()
        self.theme = theme
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(1)
        self.head = QPushButton()
        self.head.setCursor(Qt.PointingHandCursor)
        self.head.setStyleSheet(f"QPushButton {{ background:transparent; border:none; border-radius:8px; text-align:left; }}"
                                f"QPushButton:hover {{ background:{theme['btn_bg']}; }}")
        hl = QGridLayout(self.head)
        hl.setContentsMargins(4, 3, 4, 3)
        hl.setHorizontalSpacing(6)
        hl.setVerticalSpacing(0)
        hl.addWidget(_label(row["group"], f"color:{theme['text']}; font-size:11px; font-weight:700;"), 0, 0)
        hl.addWidget(Dots(row["models"], theme), 0, 1)
        self.chev = _label("▸", f"color:{theme['muted']}; font-size:10px;")
        hl.addWidget(self.chev, 0, 2)
        top = row["top"][0] if row["top"] else None
        hl.addWidget(_label(f"Top: {top['model']} {top['score']:.2f}" if top else "Not enough results yet",
                            f"color:{theme['muted']}; font-size:10px;"), 1, 1)
        hl.setColumnMinimumWidth(0, 66)
        hl.setColumnStretch(1, 1)
        self.head.setMinimumHeight(36)
        self.head.clicked.connect(self.toggle)
        lay.addWidget(self.head)
        self.more = QWidget()
        ml = QVBoxLayout(self.more)
        ml.setContentsMargins(76, 0, 6, 6)
        ml.setSpacing(2)
        dark = bool(theme.get("dark"))
        for t in row["top"]:
            line = QWidget()
            ll = QHBoxLayout(line)
            ll.setContentsMargins(0, 0, 0, 0)
            ll.setSpacing(6)
            ll.addWidget(_label(t["model"] + ("  · open" if t["open"] else ""), f"color:{theme['text']}; font-size:10px;"), 1)
            bar = Bar(t["score"], kind_color(t["open"], dark), theme)
            bar.setFixedWidth(54)
            ll.addWidget(bar)
            ll.addWidget(_label(f"{t['score']:.2f}", f"color:{theme['muted']}; font-size:10px;"))
            ml.addWidget(line)
        self.more.setVisible(False)
        lay.addWidget(self.more)

    def toggle(self) -> None:
        shown = not self.more.isVisible()
        self.more.setVisible(shown)
        self.chev.setText("▾" if shown else "▸")


class Bar(QWidget):
    def __init__(self, value: float, color: str, theme: dict[str, Any]) -> None:
        super().__init__()
        self.value, self.color, self.theme = value, color, theme
        self.setFixedHeight(10)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.theme["btn_bg"]))
        p.drawRoundedRect(QRectF(0, 2.5, self.width(), 5), 2.5, 2.5)
        p.setBrush(QColor(self.color))
        p.drawRoundedRect(QRectF(0, 2.5, max(3, self.width() * self.value), 5), 2.5, 2.5)


# --------------------------------------------------------------------------- fingerprints
class Flower(QWidget):
    """One petal per skill, its length the score, its colour the skill's; the best-at petal full and outlined."""

    def __init__(self, m: dict[str, Any], theme: dict[str, Any]) -> None:
        super().__init__()
        self.m, self.theme = m, theme
        self.setMinimumSize(96, 96)
        self.setMouseTracking(True)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        dark = bool(self.theme.get("dark"))
        side = min(self.width(), self.height())
        p.translate(self.width() / 2, self.height() / 2)
        k = side / 136                                     # the drawing is 136 units across, as on the phone
        p.scale(k, k)
        p.setPen(QPen(QColor(self.theme["btn_bg"]), 1))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), 50, 50)
        f = QFont(self.font())
        f.setPixelSize(9)
        p.setFont(f)
        n = len(airace.SKILLS)
        for i, g in enumerate(airace.SKILLS):
            a = -math.pi / 2 + i / n * math.pi * 2
            w = math.pi / n * 0.8
            p.setPen(QColor(self.theme["muted"]))
            p.drawText(QRectF(57 * math.cos(a) - 12, 57 * math.sin(a) - 6, 24, 12), Qt.AlignCenter, SHORT[g])
            sc = self.m["groups"].get(g)
            if not sc:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(self.theme["muted"]))
                p.drawEllipse(QPointF(7 * math.cos(a), 7 * math.sin(a)), 1.8, 1.8)
                continue
            L = 5 + sc["score"] * 40
            pt = lambda ang, r: QPointF(r * math.cos(ang), r * math.sin(ang))  # noqa: E731
            path = QPainterPath(QPointF(0, 0))
            path.lineTo(pt(a - w, L * 0.8))
            path.quadTo(pt(a, L * 1.12), pt(a + w, L * 0.8))
            path.closeSubpath()
            color = QColor(SKILL[dark][i])
            best = self.m["best"] == g
            color.setAlphaF(1.0 if best else 0.6)
            p.setBrush(color)
            p.setPen(QPen(QColor(self.theme["text"]), 1.6) if best else Qt.NoPen)
            p.drawPath(path)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        side = min(self.width(), self.height())
        dx, dy = event.position().x() - self.width() / 2, event.position().y() - self.height() / 2
        if math.hypot(dx, dy) > side / 2:
            return
        n = len(airace.SKILLS)
        i = round(((math.atan2(dy, dx) + math.pi / 2) % (2 * math.pi)) / (2 * math.pi) * n) % n
        g = airace.SKILLS[i]
        sc = self.m["groups"].get(g)
        QToolTip.showText(event.globalPosition().toPoint(),
                          f"{self.m['model']}\n{g}: {sc['score']:.2f}" if sc else f"{self.m['model']}\n{g}: too few results", self)


# --------------------------------------------------------------------------- the page
class AiRacePage(QWidget):
    def __init__(self, theme: Callable[[], dict[str, Any]], on_first_show: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.theme = theme
        self.on_first_show = on_first_show        # the data is read when the page is first seen, not before
        self.data: dict[str, Any] | None = None
        self.s: dict[str, Any] | None = None
        self.chosen = {"Coding", "Math"}
        self.timer = QTimer(self)
        self.timer.setInterval(420)
        self.timer.timeout.connect(self._step)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 2, 0, 0)
        self.lay.setSpacing(8)
        self.lay.addWidget(_label("Loading the AI race…", "color:gray; font-size:11px;"))

    def showEvent(self, event) -> None:  # noqa: N802 -- Qt's naming
        super().showEvent(event)
        if self.on_first_show is not None:
            first, self.on_first_show = self.on_first_show, None
            QTimer.singleShot(0, first)

    def set_data(self, data: dict[str, Any]) -> None:
        self.data = data
        self.s = airace.stats(data)
        self.render()

    def _clear(self) -> None:
        self.timer.stop()
        while self.lay.count():
            item = self.lay.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

    def _head(self, title: str, note: str) -> None:
        t = self.theme()
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 8, 0, 0)
        hl.addWidget(_label(title, f"color:{t['text']}; font-size:12.5px; font-weight:800;"), 1)
        note_lbl = _label(note, f"color:{t['muted']}; font-size:10px;")
        note_lbl.setWordWrap(False)
        hl.addWidget(note_lbl)
        self.lay.addWidget(row)

    def render(self) -> None:
        self._clear()
        t, s = self.theme(), self.s
        dark = bool(t.get("dark"))
        if not s or s.get("empty"):
            self.lay.addWidget(_label("The AI race isn't here yet. It arrives with the next update.",
                                      f"color:{t['muted']}; font-size:11px;"))
            return
        lead, opn = s["leader"], s["best_open"]
        accent = VIOLET[dark]
        self.lay.addWidget(_label(f"{html.escape(lead['org'])} leads. <span style='color:{accent}'>Open is "
                                  f"{s['behind_now']} months behind.</span>",
                                  f"color:{t['text']}; font-size:17px; font-weight:800;", rich=True))
        if opn:
            self.lay.addWidget(_label(f"{lead['model']} tops {s['count']} models. Best open: {opn['model']}, "
                                      f"{lead['eci'] - opn['eci']:.1f} points back.", f"color:{t['muted']}; font-size:11px;"))
        tiles = QWidget()
        tl = QHBoxLayout(tiles)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(5)
        for value, what in ((f"{lead['eci']:.0f}", "top score"), (f"{opn['eci']:.0f}" if opn else "–", "best open"),
                            (f"+{s['rise']:.0f}", "in 12 months"), (str(s["count"]), "models")):
            tile = _label(f"<b style='font-size:14px'>{value}</b><br><span style='font-size:9.5px'>{what}</span>",
                          f"color:{t['text']}; background:{t['btn_bg']}; border-radius:9px; padding:5px 2px;", rich=True)
            tile.setAlignment(Qt.AlignCenter)
            tl.addWidget(tile, 1)
        self.lay.addWidget(tiles)

        # new and recent
        self._head("New and recent", "the latest releases")
        for r in s["recent"]:
            row = QWidget()
            row.setStyleSheet(f"background:{t['card_bg']}; border-radius:10px;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 5, 8, 5)
            rl.setSpacing(8)
            when = _label(f"<b style='font-size:13px; color:{accent}'>{int(r['date'][8:10])}</b><br>"
                          f"<span style='font-size:8.5px'>{MONTHS[int(r['date'][5:7]) - 1].upper()}</span>",
                          f"color:{t['muted']};", rich=True)
            when.setAlignment(Qt.AlignCenter)
            when.setFixedWidth(30)
            rl.addWidget(when)
            mid = QVBoxLayout()
            mid.setSpacing(0)
            name = f"<b>{html.escape(r['model'])}</b>"
            if r["fresh"]:
                name += f" <span style='color:#ffffff; background:{accent}; font-size:8.5px; font-weight:800'>&nbsp;NEW&nbsp;</span>"
            mid.addWidget(_label(name, f"color:{t['text']}; font-size:11.5px;", rich=True))
            meta = f"{html.escape(r['org'])} · {'open weights' if r['open'] else 'closed'}"
            if r["best"]:
                c = SKILL[dark][airace.SKILLS.index(r["best"])]
                meta += f" · <span style='color:{c}; font-weight:700'>● {html.escape(r['best'])}</span>"
            mid.addWidget(_label(meta, f"color:{t['muted']}; font-size:10px;", rich=True))
            rl.addLayout(mid, 1)
            rank = _label(f"<b style='font-size:12.5px'>#{r['rank']}</b><br><span style='font-size:9px'>of {s['count']}</span>",
                          f"color:{t['text']};", rich=True)
            rank.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            rl.addWidget(rank)
            self.lay.addWidget(row)

        # the race
        self._head("The race", "each lab's best model")
        ctl = QWidget()
        cl = QHBoxLayout(ctl)
        cl.setContentsMargins(0, 0, 0, 0)
        self.play = QPushButton("▶")
        self.play.setFixedWidth(30)
        self.play.setCursor(Qt.PointingHandCursor)
        self.play.setToolTip("Replay the race from 2024")
        self.play.setStyleSheet(f"QPushButton {{ background:{t['btn_bg']}; color:{t['text']}; border:none; border-radius:12px; padding:3px; }}"
                                f"QPushButton:hover {{ background:{t['btn_hover']}; }}")
        self.play.clicked.connect(self._play)
        self.month = _label("", f"color:{accent}; font-size:11px; font-weight:700;")
        self.month.setWordWrap(False)
        self.month.setFixedWidth(64)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, len(s["months"]) - 1)
        self.slider.valueChanged.connect(self._frame)
        self.slider.sliderPressed.connect(self.timer.stop)
        cl.addWidget(self.play)
        cl.addWidget(self.month)
        cl.addWidget(self.slider, 1)
        self.lay.addWidget(ctl)
        self.bars = RaceBars(t)
        self.lay.addWidget(self.bars)
        self.lay.addWidget(_label(f"<span style='color:{CLOSED[dark]}'>●</span> Closed &nbsp; "
                                  f"<span style='color:{OPEN[dark]}'>●</span> Open weights",
                                  f"color:{t['muted']}; font-size:10px;", rich=True))
        self.slider.setValue(len(s["months"]) - 1)
        self._frame(len(s["months"]) - 1)

        # the gap
        self._head("Open trails closed", "hover the chart")
        gap = QWidget()
        gl = QHBoxLayout(gap)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(8)
        big = _label(f"<span style='font-size:24px; font-weight:800; color:{OPEN[dark]}'>{s['behind_now']} mo</span><br>"
                     "<span style='font-size:9.5px'>behind the best closed model</span>", f"color:{t['muted']};", rich=True)
        big.setFixedWidth(84)
        gl.addWidget(big)
        chart = GapChart(t)
        chart.set_stats(s)
        gl.addWidget(chart, 1)
        self.lay.addWidget(gap)

        # best at
        self._head("Best at", "each dot is a recent model")
        for row in s["best_at"]:
            self.lay.addWidget(SkillRow(row, t))

        # fingerprints
        self._head("Fingerprints", "one petal per skill")
        key = " &nbsp;".join(f"<span style='color:{SKILL[dark][i]}'>■</span> {g}" for i, g in enumerate(airace.SKILLS))
        self.lay.addWidget(_label(key, f"color:{t['muted']}; font-size:9.5px;", rich=True))
        grid = QWidget()
        gr = QGridLayout(grid)
        gr.setContentsMargins(0, 0, 0, 0)
        gr.setSpacing(2)
        for k, m in enumerate(s["prints"]):
            cell = QWidget()
            cv = QVBoxLayout(cell)
            cv.setContentsMargins(0, 0, 0, 0)
            cv.setSpacing(0)
            cv.addWidget(Flower(m, t))
            nm = _label(m["model"], f"color:{t['text']}; font-size:10px; font-weight:700;")
            nm.setAlignment(Qt.AlignCenter)
            cv.addWidget(nm)
            if m["best"]:
                c = SKILL[dark][airace.SKILLS.index(m["best"])]
                bt = _label(f"<span style='color:{c}'>●</span> {html.escape(m['best'])} · {m['eci']:.0f}",
                            f"color:{t['muted']}; font-size:9.5px;", rich=True)
                bt.setAlignment(Qt.AlignCenter)
                cv.addWidget(bt)
            gr.addWidget(cell, k // 3, k % 3)
        self.lay.addWidget(grid)

        # for my work
        self._head("For my work", "pick skills")
        chips = QWidget()
        ch = QGridLayout(chips)
        ch.setContentsMargins(0, 0, 0, 0)
        ch.setSpacing(4)
        self.chip_buttons = {}
        for k, g in enumerate(airace.SKILLS):
            b = QPushButton(g)
            b.setCheckable(True)
            b.setChecked(g in self.chosen)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ background:{t['btn_bg']}; color:{t['text']}; border:none; border-radius:10px; "
                            f"padding:3px 6px; font-size:10.5px; }} QPushButton:checked {{ background:{accent}; color:#ffffff; "
                            "font-weight:700; }")
            b.toggled.connect(lambda on, g=g: self._choose(g, on))
            ch.addWidget(b, k // 3, k % 3)
            self.chip_buttons[g] = b
        self.lay.addWidget(chips)
        self.pick_box = QWidget()
        self.pick_lay = QVBoxLayout(self.pick_box)
        self.pick_lay.setContentsMargins(0, 0, 0, 0)
        self.pick_lay.setSpacing(2)
        self.lay.addWidget(self.pick_box)
        self._picked()

        credit = QLabel(f"Data: <a style='color:{t['link']}' href='https://epoch.ai/benchmarks'>Epoch AI</a>, CC BY 4.0. "
                        "Skill groups and scores are myGeeKy's own.")
        credit.setTextFormat(Qt.RichText)
        credit.setWordWrap(True)
        credit.setOpenExternalLinks(False)
        credit.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        credit.setStyleSheet(f"color:{t['muted']}; font-size:9.5px; background:transparent; margin-top:6px;")
        self.lay.addWidget(credit)

    # ---- the race's frames
    def _frame(self, i: int) -> None:
        if not self.s or not self.data:
            return
        until = self.s["months"][i]
        self.bars.set_rows(airace.race(self.data, until))
        self.month.setText(month_label(until))

    def _step(self) -> None:
        i = self.slider.value() + 1
        if i > self.slider.maximum():
            self.timer.stop()
            self.play.setText("▶")
            return
        self.slider.setValue(i)

    def _play(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            self.play.setText("▶")
            return
        if self.slider.value() >= self.slider.maximum():
            self.slider.setValue(0)
        self.play.setText("❚❚")
        self.timer.start()

    # ---- the picker
    def _choose(self, g: str, on: bool) -> None:
        if on:
            self.chosen.add(g)
        elif len(self.chosen) > 1:
            self.chosen.discard(g)
        else:
            self.chip_buttons[g].setChecked(True)          # one skill at least
            return
        self._picked()

    def _picked(self) -> None:
        t = self.theme()
        dark = bool(t.get("dark"))
        while self.pick_lay.count():
            w = self.pick_lay.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        rows = airace.pick(self.data, sorted(self.chosen, key=airace.SKILLS.index))
        if not rows:
            self.pick_lay.addWidget(_label("No recent model has results in all of these. Choose fewer.",
                                           f"color:{t['muted']}; font-size:10.5px;"))
        for i, r in enumerate(rows):
            line = QWidget()
            ll = QHBoxLayout(line)
            ll.setContentsMargins(0, 0, 0, 0)
            ll.setSpacing(6)
            ll.addWidget(_label(str(i + 1), f"color:{t['muted']}; font-size:10px;"))
            ll.addWidget(_label(r["model"] + ("  · open" if r["open"] else ""), f"color:{t['text']}; font-size:11px; font-weight:600;"), 1)
            bar = Bar(r["score"], kind_color(r["open"], dark), t)
            bar.setFixedWidth(70)
            ll.addWidget(bar)
            ll.addWidget(_label(f"{r['score']:.2f}", f"color:{t['text']}; font-size:10.5px;"))
            self.pick_lay.addWidget(line)
