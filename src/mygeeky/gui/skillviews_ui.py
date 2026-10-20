"""Grow → Skills, drawn: directions (where the field is going: a launch pad, bridges and a horizon), next steps, bridges (a flow from your skills to rising ones), the ladder (your rising
strengths joined to new rising skills) and your lens (what your feed sees against the world). skills.shapes() works
out every number; the phone draws the same four (components/skill-views.tsx). Skill names come from myGeeKy's own
dictionary, but they're still drawn as plain text.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QToolTip, QVBoxLayout, QWidget

from .growth_ui import qcolor

# yours / rising, not yours yet / rising and yours -- the dataviz palette's first three, the same on the phone
YOURS = {False: "#2a78d6", True: "#3987e5"}
RISING = {False: "#eb6834", True: "#d95926"}
BOTH = {False: "#1baf7a", True: "#199e70"}


def _short(s: str, n: int = 16) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _label(text: str, css: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.PlainText)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(css + " background:transparent;")
    return lbl


class _Drawing(QWidget):
    def __init__(self, theme: dict[str, Any], height: int) -> None:
        super().__init__()
        self.theme, self.dark = theme, bool(theme.get("dark"))
        self.setMinimumHeight(height)
        self.setMouseTracking(True)
        self.hits: list[tuple[QRectF, str]] = []

    def font_of(self, size: float, bold: bool = False) -> QFont:
        f = QFont(self.font())
        f.setPointSizeF(size)
        f.setBold(bold)
        return f

    def text(self, p: QPainter, x: float, y: float, s: str, right: bool = False, color: str | None = None) -> None:
        p.setPen(qcolor(color or self.theme["text"]))
        w = p.fontMetrics().horizontalAdvance(s)
        p.drawText(QPointF(x - w if right else x, y + p.fontMetrics().ascent() / 2 - 1), s)

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        for rect, tip in self.hits:
            if rect.contains(e.position()):
                QToolTip.showText(e.globalPosition().toPoint(), tip, self)
                return
        QToolTip.hideText()


def _column(n: int, top: float, height: float) -> list[float]:
    return [top + height / 2] if n == 1 else [top + i * height / (n - 1) for i in range(n)]


class FlowView(_Drawing):
    """Bands from your skills (left) to rising ones (right), as wide as the documents they share."""

    def __init__(self, flow: dict[str, Any], theme: dict[str, Any]) -> None:
        super().__init__(theme, min(210, 40 + 28 * max(len(flow["left"]), len(flow["right"]), 1)))   # the same on the phone
        self.flow = flow

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(self.font_of(8))
        left, right, bands = self.flow["left"], self.flow["right"], self.flow["bands"]
        if not bands:
            return
        lx, rx = self.width() * 0.34, self.width() * 0.62
        gap, h = 5.0, self.height() - 12
        total = sum(b[2] for b in bands)
        lw = {n: sum(b[2] for b in bands if b[0] == n) for n in left}
        rw = {n: sum(b[2] for b in bands if b[1] == n) for n in right}
        scale = (h - gap * (max(len(left), len(right)) - 1)) / total
        ly, ry, y = {}, {}, 6.0
        for n in left:
            ly[n] = y
            y += lw[n] * scale + gap
        y = 6.0
        for n in right:
            ry[n] = y
            y += rw[n] * scale + gap
        lcur, rcur = dict(ly), dict(ry)
        self.hits = []
        band = QColor(RISING[self.dark])
        band.setAlphaF(0.3)
        for a, b, k in sorted(bands, key=lambda x: (left.index(x[0]), right.index(x[1]))):
            t = k * scale
            y1, y2 = lcur[a], rcur[b]
            lcur[a] += t
            rcur[b] += t
            mid = (lx + rx) / 2
            path = QPainterPath(QPointF(lx, y1))
            path.cubicTo(mid, y1, mid, y2, rx, y2)
            path.lineTo(rx, y2 + t)
            path.cubicTo(mid, y2 + t, mid, y1 + t, lx, y1 + t)
            path.closeSubpath()
            p.fillPath(path, band)
            self.hits.append((QRectF(lx, min(y1, y2), rx - lx, abs(y2 - y1) + t), f"{a} → {b}: {k} documents mention both"))
        p.setPen(Qt.NoPen)
        for n in left:
            p.setBrush(QColor(YOURS[self.dark]))
            p.drawRoundedRect(QRectF(lx - 5, ly[n], 5, max(2, lw[n] * scale)), 2, 2)
            self.text(p, lx - 9, ly[n] + lw[n] * scale / 2, _short(n, 17), right=True)
        for n in right:
            p.setBrush(QColor(RISING[self.dark]))
            p.drawRoundedRect(QRectF(rx, ry[n], 5, max(2, rw[n] * scale)), 2, 2)
            self.text(p, rx + 9, ry[n] + rw[n] * scale / 2, _short(n, 17))


class LadderView(_Drawing):
    """Your rising strengths on the left, new rising skills on the right, joined where they appear together."""

    def __init__(self, ladder: dict[str, Any], theme: dict[str, Any]) -> None:
        super().__init__(theme, 24 + 21 * max(len(ladder["left"]), len(ladder["right"]), 2))
        self.ladder = ladder

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        left, right, links = self.ladder["left"], self.ladder["right"], self.ladder["links"]
        lx, rx = self.width() * 0.36, self.width() * 0.6
        ly, ry = _column(len(left), 26, self.height() - 34), _column(len(right), 26, self.height() - 34)
        p.setFont(self.font_of(7, True))
        self.text(p, lx, 8, "YOURS, RISING", right=True, color=self.theme["muted"])
        self.text(p, rx, 8, "NEW, RISING", color=self.theme["muted"])
        p.setFont(self.font_of(8))
        top = max([k for *_, k in links] or [1])
        self.hits = []
        for a, b, k in links:
            y1, y2 = ly[left.index(a)], ry[right.index(b)]
            c = QColor(RISING[self.dark])
            c.setAlphaF(0.2 + 0.6 * k / top)
            p.setPen(QPen(c, 1 + 4 * k / top))
            path = QPainterPath(QPointF(lx, y1))
            mid = (lx + rx) / 2
            path.cubicTo(mid, y1, mid, y2, rx, y2)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            self.hits.append((QRectF(lx, min(y1, y2) - 3, rx - lx, abs(y2 - y1) + 6), f"{a} → {b}: {k} documents mention both"))
        p.setPen(Qt.NoPen)
        for n, y in zip(left, ly):
            p.setBrush(QColor(BOTH[self.dark]))
            p.drawEllipse(QPointF(lx, y), 4, 4)
            self.text(p, lx - 9, y, _short(n, 17), right=True)
        for n, y in zip(right, ry):
            p.setBrush(QColor(RISING[self.dark]))
            p.drawEllipse(QPointF(rx, y), 4, 4)
            self.text(p, rx + 9, y, _short(n, 17))


class LensView(_Drawing):
    """Dumbbells: how often a skill shows in your feed (blue) and in the world's documents (orange)."""
    ROW = 20

    def __init__(self, lens: dict[str, Any], theme: dict[str, Any]) -> None:
        self.rows = []
        for head, side in (("YOU SEE MORE", lens["mine"]), ("THE WORLD SEES MORE", lens["world"])):
            if side:                                  # an empty half gets no heading
                self.rows += [(head, None)] + [(r["name"], r) for r in side]
        super().__init__(theme, self.ROW * len(self.rows) + 4)
        self.top = max([max(r["mine"], r["world"]) for _, r in self.rows if r] or [1e-9])

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        x0, w = self.width() * 0.4, self.width() * 0.56
        self.hits = []
        for i, (name, r) in enumerate(self.rows):
            y = i * self.ROW + self.ROW / 2
            if r is None:
                p.setFont(self.font_of(7, True))
                self.text(p, 0, y + 2, name, color=self.theme["muted"])
                continue
            p.setFont(self.font_of(8))
            self.text(p, x0 - 10, y, _short(name, 18), right=True, color=BOTH[self.dark] if r["yours"] else None)
            xm, xw = x0 + r["mine"] / self.top * w, x0 + r["world"] / self.top * w
            p.setPen(QPen(qcolor(self.theme["muted"]), 2))
            p.drawLine(QPointF(xm, y), QPointF(xw, y))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(YOURS[self.dark]))
            p.drawEllipse(QPointF(xm, y), 4.5, 4.5)
            p.setBrush(QColor(RISING[self.dark]))
            p.drawEllipse(QPointF(xw, y), 4.5, 4.5)
            self.hits.append((QRectF(0, y - self.ROW / 2, self.width(), self.ROW),
                              f"{name}: in {r['mine'] * 100:.1f}% of your feed, {r['world'] * 100:.1f}% of the world's documents"))


class LaunchPadView(_Drawing):
    """Your skills on the ground (`aim` pads); each direction a rocket launched from the one it's most tied to:
    higher = faster growth, bigger = more preprints."""
    GROUND = 250

    def __init__(self, dirs: list[dict[str, Any]], pads: list[str], theme: dict[str, Any]) -> None:
        super().__init__(theme, self.GROUND + 26)
        self.dirs, self.pads = [d for d in dirs if d["pad"]], pads

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, ground = self.width(), self.GROUND
        top_g = max([d["growth"] for d in self.dirs] or [2]) * 1.1
        top_m = max([d["mentions"] for d in self.dirs] or [1])
        alt = lambda g: ground - 20 - math.log(max(g, 1)) / math.log(max(top_g, 1.5)) * (ground - 50)  # noqa: E731
        px = lambda i: 24 + (i + 0.5) * (W - 48) / max(len(self.pads), 1)  # noqa: E731
        sky = QColor(qcolor(self.theme["text"]))
        sky.setAlphaF(0.04)
        p.setPen(Qt.NoPen)
        p.setBrush(sky)
        p.drawRoundedRect(QRectF(0, 0, W, ground), 8, 8)
        p.setFont(self.font_of(7))
        for g in (2, 4, 8):
            if g < top_g:
                y = alt(g)
                p.setPen(QPen(qcolor(self.theme["muted"]), 1, Qt.DotLine))
                p.drawLine(QPointF(0, y), QPointF(W, y))
                self.text(p, W - 3, y - 6, f"×{g}", right=True, color=self.theme["muted"])
        p.setPen(QPen(qcolor(self.theme["muted"]), 1.5))
        p.drawLine(QPointF(0, ground), QPointF(W, ground))
        p.setFont(self.font_of(8, True))
        for i, name in enumerate(self.pads):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(YOURS[self.dark]))
            p.drawRoundedRect(QRectF(px(i) - 13, ground, 26, 5), 2, 2)
            w = p.fontMetrics().horizontalAdvance(_short(name, 12))
            self.text(p, px(i) - w / 2, ground + 15, _short(name, 12))
        self.hits, placed, seen = [], [], {}
        rocket, flame = QColor(RISING[self.dark]), QColor("#f6b54a")
        for d in self.dirs:
            i = self.pads.index(d["pad"])
            k = seen[d["pad"]] = seen.get(d["pad"], -1) + 1
            x = max(14.0, min(W - 14.0, px(i) + (1 if k % 2 else -1) * math.ceil(k / 2) * 22))
            y, r = alt(d["growth"]), 5 + 6 * math.sqrt(d["mentions"] / top_m)
            trail = QColor(rocket)
            trail.setAlphaF(0.35)
            path = QPainterPath(QPointF(px(i), ground))
            path.cubicTo(px(i), (ground + y) / 2, x, (ground + y) / 2 + 20, x, y + r)
            p.setPen(QPen(trail, 2, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            body = QPainterPath(QPointF(x, y - r * 1.5))
            body.cubicTo(x + r * .9, y - r * .6, x + r * .8, y + r * .6, x + r * .55, y + r)
            body.lineTo(x - r * .55, y + r)
            body.cubicTo(x - r * .8, y + r * .6, x - r * .9, y - r * .6, x, y - r * 1.5)
            p.setPen(Qt.NoPen)
            p.fillPath(body, rocket)
            fire = QPainterPath(QPointF(x - r * .35, y + r))
            fire.lineTo(x, y + r * 1.9)
            fire.lineTo(x + r * .35, y + r)
            p.fillPath(fire, flame)
            p.setBrush(QColor("#191824" if self.dark else "#ffffff"))
            p.drawEllipse(QPointF(x, y - r * .3), r * .28, r * .28)
            self.hits.append((QRectF(x - r, y - r * 1.6, 2 * r, 3.4 * r), f"{d['name']}: {d['line']}"))
            ly = y - r * 1.5 - 7
            if not any(abs(a - x) < 76 and abs(b - ly) < 12 for a, b in placed):
                placed.append((x, ly))
                p.setFont(self.font_of(7.5, True))
                label = _short(d["name"], 18)
                w = p.fontMetrics().horizontalAdvance(label)
                self.text(p, max(0.0, min(W - w, x - w / 2)), ly, label)


class HorizonView(_Drawing):
    """You at the bottom, your skills (`aim` pads) as spokes; the closer a direction sits, the more of its preprints
    also mention that skill; bigger dots grow faster."""

    def __init__(self, dirs: list[dict[str, Any]], pads: list[str], theme: dict[str, Any]) -> None:
        super().__init__(theme, 256)
        self.dirs, self.pads = [d for d in dirs if d["pad"]], pads

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, cy = self.width(), self.height() - 18
        cx, R = W / 2, min(W / 2 - 24, self.height() - 44)
        ang = lambda i: math.pi * (0.24 + 0.52 * (0.5 if len(self.pads) == 1 else i / (len(self.pads) - 1)))  # noqa: E731
        p.setFont(self.font_of(7))
        for f, words in ((0.33, "a short step"), (0.66, "a stretch"), (1.0, "a leap")):
            p.setPen(QPen(qcolor(self.theme["muted"]), 1, Qt.DotLine if f < 1 else Qt.SolidLine))
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(cx - R * f, cy - R * f, 2 * R * f, 2 * R * f), 0, 180 * 16)
            self.text(p, cx + R * f - p.fontMetrics().horizontalAdvance(words) / 2, cy + 9, words, color=self.theme["muted"])
        spoke = QColor(YOURS[self.dark])
        p.setFont(self.font_of(8, True))
        for i, name in enumerate(self.pads):
            a = ang(i)
            spoke.setAlphaF(0.3)
            p.setPen(QPen(spoke, 1))
            p.drawLine(QPointF(cx, cy), QPointF(cx - math.cos(a) * R, cy - math.sin(a) * R))
            label = _short(name, 13)
            w = p.fontMetrics().horizontalAdvance(label)
            x = max(w / 2 + 2, min(W - w / 2 - 2, cx - math.cos(a) * (R + 10)))
            self.text(p, x - w / 2, cy - math.sin(a) * (R + 10) - 2, label, color=YOURS[self.dark])
        p.setPen(QPen(QColor(BOTH[self.dark]), 1.5))
        you = QColor(BOTH[self.dark])
        you.setAlphaF(0.2)
        p.setBrush(you)
        p.drawEllipse(QPointF(cx, cy), 13, 13)
        p.setFont(self.font_of(7.5, True))
        self.text(p, cx - p.fontMetrics().horizontalAdvance("you") / 2, cy, "you")
        top_g = max([d["growth"] for d in self.dirs] or [2])
        self.hits, placed, seen = [], [], {}
        for d in self.dirs:
            i = self.pads.index(d["pad"])
            k = seen[d["pad"]] = seen.get(d["pad"], -1) + 1
            a = ang(i) + (1 if k % 2 else -1) * math.ceil(k / 2) * 0.13
            dist = 0.22 + 0.78 * (1 - d["closeness"])
            x, y = cx - math.cos(a) * R * dist, cy - math.sin(a) * R * dist
            r = 4 + 6 * math.log(max(d["growth"], 1)) / math.log(max(top_g, 1.5))
            p.setPen(QPen(QColor("#191824" if self.dark else "#ffffff"), 1.5))
            p.setBrush(QColor(RISING[self.dark]))
            p.drawEllipse(QPointF(x, y), r, r)
            self.hits.append((QRectF(x - r, y - r, 2 * r, 2 * r), f"{d['name']}: {d['line']}"))
            ly = y - r - 7
            if not any(abs(a2 - x) < 74 and abs(b - ly) < 11 for a2, b in placed):
                placed.append((x, ly))
                p.setFont(self.font_of(7.5))
                label = _short(d["name"], 16)
                w = p.fontMetrics().horizontalAdvance(label)
                self.text(p, max(0.0, min(W - w, x - w / 2)), ly, label)


def _legend(items: list[tuple[str, str]], theme: dict[str, Any]) -> QWidget:
    w = QWidget()
    w.setStyleSheet("background:transparent;")
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(10)
    for color, text in items:
        row.addWidget(_label(f"●", f"color:{color}; font-size:10px;"))
        row.addWidget(_label(text, f"color:{theme['muted']}; font-size:10px;"))
    row.addStretch(1)
    return w


class SkillViews(QWidget):
    """The views, one under the other, each with a line saying what it shows; the protocol suggestions come last."""

    def __init__(self, shapes: dict[str, Any], theme: dict[str, Any], on_path: Callable[[str], None] | None = None,
                 started: set[str] | None = None) -> None:
        super().__init__()
        self.setStyleSheet("background:transparent;")
        dark = bool(theme.get("dark"))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        head = f"color:{theme['text']}; font-size:11px; font-weight:800; letter-spacing:0.5px; margin-top:8px;"
        hint = f"color:{theme['muted']}; font-size:10.5px;"
        dirs, aim = shapes.get("directions") or [], shapes.get("aim") or {"pads": [], "bands": []}
        if dirs and aim["pads"]:
            lay.addWidget(_label("🚀 DIRECTIONS", head))
            lay.addWidget(_label("Where your field is heading: rising for sure across new preprints, and tied to "
                                 "what you know, even if your feed hasn't shown them yet. Each rocket launches from "
                                 "the skill of yours it's most tied to: higher grows faster, bigger has more preprints.",
                                 hint))
            lay.addWidget(LaunchPadView(dirs, aim["pads"], theme))
            if aim["bands"]:
                lay.addWidget(_label("Which of your skills lead where: bands as wide as the preprints that mention both.",
                                     hint))
                lay.addWidget(FlowView(aim, theme))
            lay.addWidget(_label("How far each is from you: the closer, the more of its preprints mention that "
                                 "skill of yours.", hint))
            lay.addWidget(HorizonView(dirs, aim["pads"], theme))
        if shapes["next"]:
            lay.addWidget(_label("🧭 NEXT STEPS", head))
            lay.addWidget(_label("What to learn, and the skill of yours that leads there.", hint))
            top = max([n["weight"] for n in shapes["next"]] or [1]) or 1
            for i, n in enumerate(shapes["next"], 1):
                lay.addWidget(self._step(i, n, top, theme, dark))
        if shapes["flow"]["bands"]:
            lay.addWidget(_label("🌉 BRIDGES FROM WHAT YOU KNOW", head))
            lay.addWidget(_label("Wider bands: more documents mention both. Hover a band for the count.", hint))
            lay.addWidget(FlowView(shapes["flow"], theme))
        if shapes["ladder"]["left"] and shapes["ladder"]["links"]:
            lay.addWidget(_label("🪜 RISING WITH YOU", head))
            lay.addWidget(_label("Your skills that are rising too, and the new ones they appear with.", hint))
            lay.addWidget(LadderView(shapes["ladder"], theme))
        if shapes["lens"]["mine"] or shapes["lens"]["world"]:
            lay.addWidget(_label("🔍 YOUR LENS", head))
            lay.addWidget(_label("How often a skill shows in what myGeeKy reads for you, against new preprints "
                                 "across the field. A wide gap is your bubble: rising skills are measured on the "
                                 "world's side.", hint))
            lay.addWidget(_legend([(YOURS[dark], "your feed"), (RISING[dark], "the world"),
                                   (BOTH[dark], "names in green are yours")], theme))
            lay.addWidget(LensView(shapes["lens"], theme))
        picks = [(d["name"], d["line"], f"×{d['growth']:g}") for d in dirs] + \
                [(n["name"], (f"via {n['via']}" + (f" and {n['more']} more of yours" if n["more"] else "")) if n["via"]
                  else "nothing of yours leads here yet", "") for n in shapes["next"]]
        if picks and on_path:
            lay.addWidget(_label("🧭 START A PROTOCOL", head))
            lay.addWidget(_label("Turn a direction or a next step into stages you can follow.", hint))
            for name, why, chip in picks:
                lay.addWidget(self._protocol_row(name, why, chip, theme, dark, on_path, name in (started or set())))

    @staticmethod
    def _protocol_row(name: str, why: str, chip: str, theme: dict[str, Any], dark: bool,
                      on_path: Callable[[str], None], started: bool) -> QWidget:
        w = QWidget()
        w.setObjectName("direction")
        w.setStyleSheet(f"#direction {{ background:rgba(128,128,128,22); border-left:3px solid {RISING[dark]}; "
                        "border-radius:6px; } QLabel { background:transparent; }")
        col = QVBoxLayout(w)
        col.setContentsMargins(10, 6, 8, 6)
        col.setSpacing(2)
        top = QHBoxLayout()
        top.addWidget(_label(name, f"color:{theme['text']}; font-size:12.5px; font-weight:800;"), 1)
        if chip:
            top.addWidget(_label(chip, f"color:{RISING[dark]}; font-size:11px; font-weight:800;"))
        col.addLayout(top)
        col.addWidget(_label(why, f"color:{theme['muted']}; font-size:10.5px;"))
        if on_path:
            btn = QPushButton("✓ In your protocols" if started else "🧭 Make it a protocol")
            btn.setEnabled(not started)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"QPushButton {{ color:{theme['text']}; background:rgba(128,128,128,40); border:none; "
                              "border-radius:8px; padding:3px 9px; font-size:10.5px; }")
            btn.clicked.connect(lambda: on_path(name))
            row = QHBoxLayout()
            row.addWidget(btn)
            row.addStretch(1)
            col.addLayout(row)
        return w

    @staticmethod
    def _step(i: int, n: dict[str, Any], top: int, theme: dict[str, Any], dark: bool) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(8)
        row.addWidget(_label(str(i), f"color:{theme['muted']}; font-size:10px; font-family:monospace;"))
        col = QVBoxLayout()
        col.setSpacing(0)
        tag = "  🌍 beyond your usual" if n["beyond"] else ("  📈 sure it's rising" if n["sure"] else "")
        col.addWidget(_label(n["name"] + tag, f"color:{theme['text']}; font-size:12px; font-weight:700;"))
        via = (f"via {n['via']}" + (f" and {n['more']} more of yours" if n["more"] else "")) if n["via"] \
            else "nothing of yours leads here yet"
        col.addWidget(_label(via, f"color:{theme['muted']}; font-size:10.5px;"))
        row.addLayout(col, 1)
        bar = QWidget()
        bar.setFixedSize(54, 7)
        pct = int(100 * n["weight"] / top) if top else 0
        bar.setStyleSheet(f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {RISING[dark]}, "
                          f"stop:{max(pct, 1) / 100:.2f} {RISING[dark]}, stop:{min(pct / 100 + 0.01, 1):.2f} "
                          f"rgba(128,128,128,40), stop:1 rgba(128,128,128,40)); border-radius:3px;")
        row.addWidget(bar)
        return w
