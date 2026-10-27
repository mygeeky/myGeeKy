"""The admin console's TRACE parts (trace.py): the eight plots on the Dashboard, the news waiting in Review, and the
Triggers page (the trigger inbox, allowed senders, feeds, the budget and the latest triggers).

Colours: every text colour comes from the theme (through logic.readable); the four kinds have fixed hues, checked
for colour blindness and contrast on the panel's dark and light surfaces (blue news, orange jobs, green conferences,
yellow funding), and every mark that carries one also carries a label or a tooltip. Text from feeds, emails and pages
is shown as plain text, always.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSpinBox, QToolTip, QVBoxLayout, QWidget)

from . import app as logic

KIND_COLORS = {"news": "#3987e5", "jobs": "#d95926", "conferences": "#199e70", "funding": "#c98500"}
KIND_LABELS = {"news": "News", "jobs": "Jobs", "conferences": "Conferences", "funding": "Funding"}


def qc(value: str) -> QColor:
    """A theme colour as a QColor: themes use rgba(r,g,b,a) too, which QColor can't read by itself."""
    import re
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*(\d+(?:\.\d+)?))?\)", str(value).strip())
    if m:
        a = float(m.group(4)) if m.group(4) else 255
        return QColor(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(a * 255) if a <= 1 else int(a))
    return QColor(value)


def _label(text: str, css: str, wrap: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.PlainText)
    lbl.setWordWrap(wrap)
    lbl.setStyleSheet(css + " background:transparent;")
    return lbl



def on_accent(t: dict) -> str:
    """Text that reads on the theme's accent: dark ink on a light accent, the theme's text on a dark one."""
    from PySide6.QtGui import QColor as _C
    c = _C(t["accent"]) if str(t["accent"]).startswith("#") else _C("#888888")
    return "#0d0d16" if (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) > 150 else t["text"]

def _button(text: str, t: dict[str, Any], primary: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"QPushButton {{ background:{t['accent'] if primary else t['section_btn']}; "
                    f"color:{on_accent(t) if primary else t['text']}; "
                    f"border:none; border-radius:8px; padding:5px 11px; font-size:11.5px; "
                    f"font-weight:{'700' if primary else '500'}; }} QPushButton:disabled {{ color:{t['muted']}; }}")
    return b


def _hours(h: float | None) -> str:
    if h is None:
        return "–"
    return f"{round(h * 60)} min" if h < 1 else f"{h:.1f} h" if h < 48 else f"{h / 24:.1f} d"


# --------------------------------------------------------------------------- the plots
class _Plot(QWidget):
    """A small chart: a title and a note above, a painted area below. Marks register hit areas for tooltips."""
    HEIGHT = 170

    def __init__(self, title: str, theme: Callable[[], dict[str, Any]]) -> None:
        super().__init__()
        self.title, self.theme = title, theme
        self.note = ""
        self.data: Any = None
        self.hits: list[tuple[QRectF, str]] = []
        self.setMinimumHeight(self.HEIGHT + 44)
        self.setMouseTracking(True)
        self.setAccessibleName(title)

    def set_data(self, data: Any, note: str = "") -> None:
        self.data, self.note = data, note
        self.setToolTip("")
        self.update()

    def event(self, e) -> bool:  # noqa: D401
        if e.type() == QEvent.ToolTip:
            for rect, tip in self.hits:
                if rect.contains(e.position() if hasattr(e, "position") else QPointF(e.pos())):
                    QToolTip.showText(e.globalPos(), tip, self)
                    return True
            QToolTip.hideText()
            return True
        return super().event(e)

    def paintEvent(self, _e) -> None:  # noqa: N802
        t = self.theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(qc(t['card_bg']))
        p.drawRoundedRect(QRectF(self.rect()), 10, 10)
        f = p.font()
        f.setPixelSize(12)
        f.setBold(True)
        p.setFont(f)
        p.setPen(qc(t['text']))
        p.drawText(QRectF(12, 8, self.width() - 24, 18), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        f.setBold(False)
        f.setPixelSize(10)
        p.setFont(f)
        p.setPen(QColor(logic.readable(t["muted"] if t["muted"].startswith("#") else "#9aa0b8", t)))
        p.drawText(QRectF(12, 25, self.width() - 24, 14), Qt.AlignLeft | Qt.AlignVCenter, self.note)
        self.hits = []
        area = QRectF(12, 44, self.width() - 24, self.height() - 54)
        if not self.data:
            p.drawText(area, Qt.AlignCenter, "Nothing yet: it fills in as TRACE runs and you decide.")
        else:
            self.draw(p, area, t)
        p.end()

    def muted(self, t: dict[str, Any]) -> QColor:
        return QColor(logic.readable("#9aa0b8", t))

    def draw(self, p: QPainter, area: QRectF, t: dict[str, Any]) -> None:
        raise NotImplementedError


class FunnelPlot(_Plot):
    def draw(self, p, area, t):
        rows = self.data
        top = max(1, rows[0][1])
        h = min(20.0, area.height() / len(rows) - 4)
        for i, (label, n) in enumerate(rows):
            y = area.top() + i * (h + 4)
            p.setPen(qc(t['text']))
            p.drawText(QRectF(area.left(), y, 104, h), Qt.AlignLeft | Qt.AlignVCenter, label)
            track = QRectF(area.left() + 108, y + 3, area.width() - 150, h - 6)
            p.setPen(Qt.NoPen)
            p.setBrush(qc(t['btn_bg']))
            p.drawRoundedRect(track, 3, 3)
            bar = QRectF(track.left(), track.top(), max(2.0, track.width() * n / top), track.height())
            p.setBrush(QColor(KIND_COLORS["news"]))
            p.drawRoundedRect(bar, 3, 3)
            p.setPen(qc(t['text']))
            p.drawText(QRectF(track.right() + 6, y, 36, h), Qt.AlignRight | Qt.AlignVCenter, str(n))
            self.hits.append((QRectF(area.left(), y, area.width(), h), f"{label}: {n} ({round(100 * n / top)}% of triggers)"))


class SourcesPlot(_Plot):
    def draw(self, p, area, t):
        rows = self.data[:6]
        h = min(22.0, area.height() / max(1, len(rows)) - 2)
        for i, s in enumerate(rows):
            y = area.top() + i * (h + 2)
            p.setPen(qc(t['text']))
            name = p.fontMetrics().elidedText(s["name"], Qt.ElideRight, 122)
            p.drawText(QRectF(area.left(), y, 124, h), Qt.AlignLeft | Qt.AlignVCenter, name)
            track = QRectF(area.left() + 128, y + h / 2 - 1, area.width() - 190, 2)
            p.setPen(Qt.NoPen)
            p.setBrush(qc(t['btn_bg']))
            p.drawRect(track)
            band = QRectF(track.left() + track.width() * s["lo"], y + h / 2 - 3, track.width() * (s["hi"] - s["lo"]), 6)
            col = QColor(KIND_COLORS.get(s.get("kind"), KIND_COLORS["news"]))
            soft = QColor(col)
            soft.setAlpha(110)
            p.setBrush(soft)
            p.drawRoundedRect(band, 3, 3)
            p.setBrush(col)
            p.setPen(QPen(qc(t['card_bg']), 2))
            p.drawEllipse(QPointF(track.left() + track.width() * s["mean"], y + h / 2), 5, 5)
            p.setPen(self.muted(t))
            p.drawText(QRectF(track.right() + 6, y, 56, h), Qt.AlignRight | Qt.AlignVCenter, f"{s['n']} decided")
            self.hits.append((QRectF(area.left(), y, area.width(), h),
                              f"{s['name']} ({KIND_LABELS.get(s.get('kind'), '')}): about {round(s['mean'] * 100)}% accepted, "
                              f"95% range {round(s['lo'] * 100)}–{round(s['hi'] * 100)}%, {s['n']} decisions"))


class HeatPlot(_Plot):
    def draw(self, p, area, t):
        days, heat = self.data["days"], self.data["heat"]
        lab_w = 124
        cw = (area.width() - lab_w) / max(1, len(days))
        p.setPen(self.muted(t))
        for j, d in enumerate(days):
            p.drawText(QRectF(area.left() + lab_w + j * cw, area.top(), cw, 12), Qt.AlignCenter, d[5:])
        h = min(20.0, (area.height() - 16) / max(1, len(heat)) - 2)
        bg, ink = qc(t.get("solid_bg") or "#1c1c2a"), qc(t["text"])      # "usual": a quiet step off the background
        base = QColor(round(bg.red() * 0.85 + ink.red() * 0.15), round(bg.green() * 0.85 + ink.green() * 0.15),
                      round(bg.blue() * 0.85 + ink.blue() * 0.15))
        hot = QColor(KIND_COLORS["news"])
        for i, row in enumerate(heat):
            y = area.top() + 16 + i * (h + 2)
            p.setPen(qc(t['text']))
            p.drawText(QRectF(area.left(), y, lab_w - 4, h), Qt.AlignLeft | Qt.AlignVCenter,
                       p.fontMetrics().elidedText(row["topic"], Qt.ElideRight, lab_w - 6))
            for j, c in enumerate(row["cells"]):
                k = max(0.0, min(1.0, (c["ratio"] - 1) / 2))           # usual → three times usual
                col = QColor(round(base.red() + (hot.red() - base.red()) * k), round(base.green() + (hot.green() - base.green()) * k),
                             round(base.blue() + (hot.blue() - base.blue()) * k))
                r = QRectF(area.left() + lab_w + j * cw + 1, y, cw - 2, h)
                p.setPen(Qt.NoPen)
                p.setBrush(col)
                p.drawRoundedRect(r, 3, 3)
                self.hits.append((r, f"{row['topic']}, {days[j]}: {c['ratio']}× its usual rate (z {c['z']})"))


class CalibrationPlot(_Plot):
    def draw(self, p, area, t):
        box = QRectF(area.left() + 26, area.top(), area.width() - 32, area.height() - 14)
        p.setPen(QPen(self.muted(t), 1, Qt.DashLine))
        p.drawLine(box.bottomLeft(), box.topRight())
        p.setPen(QPen(qc(t['btn_bg']), 1))
        p.drawRect(box)
        pts = [QPointF(box.left() + c["p"] * box.width(), box.bottom() - c["actual"] * box.height()) for c in self.data]
        if len(pts) > 1:
            path = QPainterPath(pts[0])
            for q in pts[1:]:
                path.lineTo(q)
            p.setPen(QPen(QColor(KIND_COLORS["news"]), 2))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        for c, q in zip(self.data, pts):
            p.setPen(QPen(qc(t['card_bg']), 2))
            p.setBrush(QColor(KIND_COLORS["news"]))
            p.drawEllipse(q, 5, 5)
            self.hits.append((QRectF(q.x() - 8, q.y() - 8, 16, 16),
                              f"Predicted {round(c['p'] * 100)}% → you accepted {round(c['actual'] * 100)}% ({c['n']} items)"))
        p.setPen(self.muted(t))
        p.drawText(QRectF(box.left(), box.bottom() + 1, box.width(), 13), Qt.AlignCenter, "predicted chance you accept →")
        p.drawText(QRectF(area.left(), box.top(), 24, 12), Qt.AlignLeft, "100%")


class MixPlot(_Plot):
    def draw(self, p, area, t):
        weeks = self.data
        top = max(1, max(sum(w[k] for k in KIND_COLORS) for w in weeks))
        bw = area.width() / len(weeks)
        chart_h = area.height() - 14
        for i, w in enumerate(weeks):
            x, y = area.left() + i * bw + bw * 0.2, area.top() + chart_h
            for k in ("news", "jobs", "conferences", "funding"):
                if not w[k]:
                    continue
                h = chart_h * w[k] / top
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(KIND_COLORS[k]))
                p.drawRoundedRect(QRectF(x, y - h, bw * 0.6, h - 2), 2, 2)
                y -= h
            p.setPen(self.muted(t))
            p.drawText(QRectF(area.left() + i * bw, area.top() + chart_h, bw, 13), Qt.AlignCenter, w["label"])
            self.hits.append((QRectF(area.left() + i * bw, area.top(), bw, chart_h),
                              f"{w['label']}: " + ", ".join(f"{w[k]} {KIND_LABELS[k].lower()}" for k in KIND_COLORS)))


class CostPlot(_Plot):
    def draw(self, p, area, t):
        weeks = [w for w in self.data if w.get("per_accepted") is not None]
        if not weeks:
            p.setPen(self.muted(t))
            p.drawText(area, Qt.AlignCenter, "No accepted items yet to divide the cost by.")
            return
        top = max(w["per_accepted"] for w in weeks) * 1.15 or 1
        box = QRectF(area.left() + 24, area.top(), area.width() - 30, area.height() - 14)
        p.setPen(QPen(qc(t['btn_bg']), 1))
        p.drawLine(box.bottomLeft(), box.bottomRight())
        step = box.width() / max(1, len(weeks) - 1)
        pts = [QPointF(box.left() + i * step, box.bottom() - box.height() * w["per_accepted"] / top) for i, w in enumerate(weeks)]
        if len(pts) > 1:
            path = QPainterPath(pts[0])
            for q in pts[1:]:
                path.lineTo(q)
            p.setPen(QPen(qc(t['accent']), 2))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        for w, q in zip(weeks, pts):
            p.setPen(QPen(qc(t['card_bg']), 2))
            p.setBrush(qc(t['accent']))
            p.drawEllipse(q, 5, 5)
            self.hits.append((QRectF(q.x() - 8, q.y() - 8, 16, 16),
                              f"{w['label']}: {w['per_accepted']} DeepSeek calls per accepted item ({w['calls']} calls)"))
        p.setPen(self.muted(t))
        p.drawText(QRectF(box.left(), box.bottom() + 1, 60, 13), Qt.AlignLeft, weeks[0]["label"])
        p.drawText(QRectF(box.right() - 60, box.bottom() + 1, 60, 13), Qt.AlignRight, weeks[-1]["label"])


class DeadlinesPlot(_Plot):
    def draw(self, p, area, t):
        rows = self.data[:6]
        h = min(22.0, (area.height() - 14) / max(1, len(rows)) - 2)
        lab_w = 150
        line_w = area.width() - lab_w - 50
        for i, d in enumerate(rows):
            y = area.top() + i * (h + 2)
            p.setPen(qc(t['text']))
            p.drawText(QRectF(area.left(), y, lab_w - 4, h), Qt.AlignLeft | Qt.AlignVCenter,
                       p.fontMetrics().elidedText(d["title"], Qt.ElideRight, lab_w - 6))
            p.setPen(QPen(qc(t['btn_bg']), 1, Qt.DashLine))
            p.drawLine(QPointF(area.left() + lab_w, y + h / 2), QPointF(area.left() + lab_w + line_w, y + h / 2))
            x = area.left() + lab_w + line_w * min(1.0, d["days"] / 90)
            p.setPen(QPen(qc(t['card_bg']), 2))
            p.setBrush(QColor(KIND_COLORS.get(d["kind"], KIND_COLORS["jobs"])))
            p.drawEllipse(QPointF(x, y + h / 2), 5, 5)
            p.setPen(self.muted(t))
            p.drawText(QRectF(area.right() - 46, y, 46, h), Qt.AlignRight | Qt.AlignVCenter, f"{d['days']} d")
            self.hits.append((QRectF(area.left(), y, area.width(), h),
                              f"{d['title']} · {KIND_LABELS.get(d['kind'], d['kind'])} · closes in {d['days']} days ({d['status']})"))
        p.setPen(self.muted(t))
        p.drawText(QRectF(area.left() + lab_w, area.bottom() - 12, line_w, 12), Qt.AlignLeft, "today")
        p.drawText(QRectF(area.left() + lab_w, area.bottom() - 12, line_w, 12), Qt.AlignRight, "90 days")


class SpeedPlot(_Plot):
    def draw(self, p, area, t):
        tiles = [("Trigger → your queue", self.data.get("to_queue_h")), ("Queue → your decision", self.data.get("to_decision_h")),
                 ("Accepted → users see it", self.data.get("to_users_h"))]
        w = area.width() / 3
        for i, (label, v) in enumerate(tiles):
            r = QRectF(area.left() + i * w + 3, area.top() + 10, w - 6, area.height() - 20)
            p.setPen(Qt.NoPen)
            p.setBrush(qc(t['btn_bg']))
            p.drawRoundedRect(r, 8, 8)
            p.setPen(self.muted(t))
            p.drawText(QRectF(r.left() + 8, r.top() + 8, r.width() - 16, 28), Qt.AlignLeft | Qt.TextWordWrap, label)
            f = p.font()
            f.setPixelSize(20)
            f.setBold(True)
            p.setFont(f)
            p.setPen(qc(t['text']))
            p.drawText(QRectF(r.left() + 8, r.top() + 40, r.width() - 16, 30), Qt.AlignLeft, _hours(v))
            f.setPixelSize(10)
            f.setBold(False)
            p.setFont(f)
            self.hits.append((r, f"{label}: median {_hours(v)} this week"))


class TracePlots(QWidget):
    """The Dashboard's eight TRACE plots, two to a row, with the kinds' colour key above."""

    def __init__(self, theme: Callable[[], dict[str, Any]]) -> None:
        super().__init__()
        self.theme = theme
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        self.key = _label("", "")
        outer.addWidget(self.key)
        grid = QGridLayout()
        grid.setSpacing(10)
        self.funnel = FunnelPlot("From trigger to published", theme)
        self.sources = SourcesPlot("Sources: how often you accept them", theme)
        self.heat = HeatPlot("What's rising", theme)
        self.calib = CalibrationPlot("Can the score be trusted?", theme)
        self.mix = MixPlot("What you accepted, per week", theme)
        self.cost = CostPlot("DeepSeek calls per accepted item", theme)
        self.deadlines = DeadlinesPlot("Deadlines coming up", theme)
        self.speed = SpeedPlot("How fast it reaches users", theme)
        for i, w in enumerate((self.funnel, self.sources, self.heat, self.calib, self.mix, self.cost, self.deadlines, self.speed)):
            grid.addWidget(w, i // 2, i % 2)
        outer.addLayout(grid)
        self.setStyleSheet("background:transparent;")

    def set_stats(self, s: dict[str, Any]) -> None:
        t = self.theme()
        self.key.setText("Colours: blue news · orange jobs · green conferences · yellow funding. Hover any mark for "
                         "its numbers. TRACE learns from your Accept and Reject only.")
        self.key.setStyleSheet(f"color:{logic.readable('#9aa0b8', t)}; font-size:10.5px; background:transparent;")
        funnel = s.get("funnel") or []
        pub = dict(funnel).get("Published", 0)
        trig = dict(funnel).get("Triggers", 0)
        self.funnel.set_data(funnel if trig else None, f"{round(100 * pub / trig)}% of this week's triggers were published" if trig else "this week")
        self.sources.set_data(s.get("sources") or None, "dot = estimate · bar = 95% range")
        self.heat.set_data({"days": s.get("days", []), "heat": s.get("heat", [])} if s.get("heat") else None,
                           "mentions against each topic's usual rate")
        err = s.get("calibration_error")
        self.calib.set_data(s.get("calibration") or None, f"off by {round(err * 100)} points on average, {s.get('decisions', 0)} decisions"
                            if err is not None else "predicted against what you accepted")
        weeks = s.get("weeks") or []
        self.mix.set_data(weeks if any(sum(w[k] for k in KIND_COLORS) for w in weeks) else None, "last 6 weeks")
        self.cost.set_data(weeks if any(w.get("per_accepted") is not None for w in weeks) else None,
                           f"today {s.get('spent_today', 0)} of {s.get('budget', {}).get('per_day', 40)} calls")
        self.deadlines.set_data(s.get("upcoming") or None, "next 90 days · waiting and published")
        self.speed.set_data(s.get("speed") or None, "median, this week")

    def apply_theme(self) -> None:
        for w in self.findChildren(_Plot):
            w.update()


# --------------------------------------------------------------------------- news waiting in Review
class NewsReview(QWidget):
    """News items TRACE wrote, best first: what it says, its sources and checks, and Accept / Reject."""

    def __init__(self, theme: Callable[[], dict[str, Any]], on_decide: Callable[[str, bool], None]) -> None:
        super().__init__()
        self.theme, self.on_decide = theme, on_decide
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(6)
        self.setStyleSheet("background:transparent;")

    def set_items(self, items: list[dict[str, Any]]) -> None:
        while self.lay.count():
            w = self.lay.takeAt(0).widget()
            if w is not None:
                w.hide()                 # out of sight now: deleteLater waits for the event loop
                w.deleteLater()
        t = self.theme()
        if not items:
            self.lay.addWidget(_label("No news waiting. TRACE adds items here as feeds and allowed senders bring "
                                      "something new (Triggers).", f"color:{t['muted']}; font-size:10.5px;"))
        for it in items[:30]:
            self.lay.addWidget(self._card(it, t))

    def _card(self, it: dict[str, Any], t: dict[str, Any]) -> QFrame:
        card = QFrame()
        card.setObjectName("trCard")
        card.setStyleSheet(f"#trCard {{ background:{t['card_bg']}; border-radius:10px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)
        top = QHBoxLayout()
        top.addWidget(_label(f"News · {it.get('topic', '')} · from {it.get('from', '')}",
                             f"color:{logic.readable(KIND_COLORS['news'], t)}; font-size:10px; font-weight:700;"), 1)
        top.addWidget(_label(f"{round(100 * float(it.get('p', 0)))}% likely you accept", f"color:{t['muted']}; font-size:10px;", False))
        lay.addLayout(top)
        lay.addWidget(_label(it.get("title", ""), f"color:{t['text']}; font-size:12.5px; font-weight:700;"))
        if it.get("summary"):
            lay.addWidget(_label(it["summary"], f"color:{t['text']}; font-size:11px;"))
        if it.get("why"):
            lay.addWidget(_label("Why: " + it["why"], f"color:{t['muted']}; font-size:10.5px;"))
        hosts = list(dict.fromkeys(logic.host_of(u) for u in it.get("sources", [])))
        lay.addWidget(_label("Links go to: " + " · ".join(hosts), f"color:{logic.readable(t['link'], t)}; font-size:10.5px;"))
        checks = "   ".join(("✓ " if ok else "• ") + text for ok, text in it.get("checks", []))
        lay.addWidget(_label(checks, f"color:{t['muted']}; font-size:10px;"))
        row = QHBoxLayout()
        row.setSpacing(6)
        acc, rej, op = _button("Accept", t, True), _button("Reject", t), _button("Open ↗", t)
        acc.clicked.connect(lambda checked=False, i=it["id"]: self.on_decide(i, True))
        rej.clicked.connect(lambda checked=False, i=it["id"]: self.on_decide(i, False))
        op.clicked.connect(lambda checked=False, u=it.get("url", ""): logic.open_link(u))
        for b in (acc, rej, op):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        return card


# --------------------------------------------------------------------------- the Triggers page
class TriggersPage(QWidget):
    """What sets TRACE off: the trigger inbox (an app password, read-only labels), the allowed senders, the feeds,
    the daily budget, and what each latest trigger led to."""

    def __init__(self, theme: Callable[[], dict[str, Any]], run_async: Callable[..., None], toast: Callable[[str], None],
                 on_changed: Callable[[], None]) -> None:
        super().__init__()
        self.theme, self.run_async, self.toast, self.on_changed = theme, run_async, toast, on_changed
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(10)
        self.setStyleSheet("background:transparent;")
        self.stats: dict[str, Any] = {}

    def _field(self, placeholder: str, value: str = "", secret: bool = False) -> QLineEdit:
        t = self.theme()
        f = QLineEdit(value)
        f.setPlaceholderText(placeholder)
        if secret:
            f.setEchoMode(QLineEdit.Password)
        f.setStyleSheet(f"QLineEdit {{ background:{t['btn_bg']}; color:{t['text']}; border:none; border-radius:7px; "
                        f"padding:5px 8px; font-size:11.5px; }}")
        return f

    def _box(self, title: str) -> QVBoxLayout:
        t = self.theme()
        frame = QFrame()
        frame.setObjectName("trBox")
        frame.setStyleSheet(f"#trBox {{ background:{t['card_bg']}; border-radius:10px; }}")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        lay.addWidget(_label(title, f"color:{t['text']}; font-size:12.5px; font-weight:800;"))
        self.lay.addWidget(frame)
        return lay

    def render(self, stats: dict[str, Any]) -> None:
        self.stats = stats
        while self.lay.count():
            w = self.lay.takeAt(0).widget()
            if w is not None:
                w.hide()                 # out of sight now: deleteLater waits for the event loop
                w.deleteLater()
        t = self.theme()
        muted = f"color:{t['muted']}; font-size:10.5px;"
        inbox = stats.get("inbox") or {}
        # the trigger inbox
        lay = self._box("📬 Trigger inbox")
        state = ("connected · read-only" if inbox.get("address") and inbox.get("has_password") else
                 "add the address and an app password" if not inbox.get("address") else "add the app password")
        lay.addWidget(_label(f"{inbox.get('address') or 'Not set up yet'} · {state}"
                             + (f" · last checked {inbox['checked'][:16].replace('T', ' ')}" if inbox.get("checked") else "")
                             + (f" · {inbox.get('ignored', 0)} emails from senders not on the list were ignored" if inbox.get("ignored") else ""),
                             f"color:{t['text']}; font-size:11.5px;"))
        lay.addWidget(_label("Gmail: turn on 2-Step Verification, then Google Account → Security → App passwords → "
                             "create one named myGeeKy, and paste it here. It's kept in this computer's keyring and "
                             "used only to read the labels below, read-only.", muted))
        row = QHBoxLayout()
        self.addr = self._field("bioresearch3000@gmail.com", inbox.get("address") or "bioresearch3000@gmail.com")
        self.labels = self._field("labels, comma-separated", ", ".join(inbox.get("labels") or ["mygeeky"]))
        self.pw = self._field("app password (16 letters)", "", secret=True)
        for w in (self.addr, self.labels, self.pw):
            row.addWidget(w, 1)
        lay.addLayout(row)
        row = QHBoxLayout()
        save, check = _button("Save the inbox", t, True), _button("Check feeds and inbox now", t)
        save.clicked.connect(self._save_inbox)
        check.clicked.connect(self._check_now)
        row.addWidget(save)
        row.addWidget(check)
        row.addStretch(1)
        lay.addLayout(row)
        # allowed senders and feeds
        srcs = stats.get("sources") or []
        lay = self._box("✉ Allowed senders (only these can trigger anything)")
        for s in [x for x in srcs if x["type"] == "email"]:
            lay.addWidget(self._source_row(s, t))
        row = QHBoxLayout()
        self.s_addr, self.s_name = self._field("sender's address, e.g. scholaralerts-noreply@google.com"), self._field("name")
        self.s_kind = self._kind_box()
        add = _button("Add sender", t)
        add.clicked.connect(self._add_sender)
        for w in (self.s_addr, self.s_name):
            row.addWidget(w, 1)
        row.addWidget(self.s_kind)
        row.addWidget(add)
        lay.addLayout(row)
        lay = self._box("📡 Feeds (better than email where they exist: nothing to sign in to, nothing to fake)")
        for s in [x for x in srcs if x["type"] in ("youtube", "arxiv", "rss")]:
            lay.addWidget(self._source_row(s, t))
        row = QHBoxLayout()
        self.f_type = QComboBox()
        self.f_type.addItems(["youtube", "arxiv", "rss"])
        self._styled(self.f_type)
        self.f_ref = self._field("YouTube channel id (UC…), arXiv category (cs.LG) or https feed")
        self.f_name = self._field("name")
        self.f_kind = self._kind_box()
        add = _button("Add feed", t)
        add.clicked.connect(self._add_feed)
        row.addWidget(self.f_type)
        row.addWidget(self.f_ref, 2)
        row.addWidget(self.f_name, 1)
        row.addWidget(self.f_kind)
        row.addWidget(add)
        lay.addLayout(row)
        # budget and rules
        b = stats.get("budget") or {}
        lay = self._box("💶 Budget and rules")
        row = QHBoxLayout()
        row.addWidget(_label("DeepSeek items a day:", f"color:{t['text']}; font-size:11.5px;", False))
        self.per_day = QSpinBox()
        self.per_day.setRange(0, 500)
        self.per_day.setValue(int(b.get("per_day", 40)))
        self._styled(self.per_day)
        self.per_day.editingFinished.connect(lambda: self.run_async(lambda: logic.trace_set_budget(self.per_day.value()),
                                                                    lambda _r: self.on_changed()))
        row.addWidget(self.per_day)
        row.addWidget(_label(f"· today {stats.get('spent_today', 0)} used · {round(100 * b.get('reserve', 0.2))}% kept for "
                             f"what you ask yourself · {round(100 * b.get('explore', 0.1))}% for new sources to prove "
                             "themselves", muted), 1)
        lay.addLayout(row)
        lay.addWidget(_label("Triggers are followed best first: P(you accept) × novelty × urgency ÷ cost. The same "
                             "story from several sources becomes one item. Nothing reaches users without your Accept, "
                             "and words in emails or pages are never followed as instructions.", muted))
        # the latest triggers
        lay = self._box("⚡ Latest triggers")
        trig = stats.get("triggers") or []
        if not trig:
            lay.addWidget(_label("None yet: add a feed or an allowed sender, then Check now.", muted))
        for tr in trig[:12]:
            lay.addWidget(_label(f"{tr.get('at', '')[11:16]}  {KIND_LABELS.get(tr.get('kind'), '')} · {tr.get('from', '')} · "
                                 f"{tr.get('title', '')[:90]}  →  {tr.get('result', '')}", f"color:{t['text']}; font-size:10.5px;"))

    def _styled(self, w: QWidget) -> QWidget:
        t = self.theme()
        w.setStyleSheet(f"QComboBox, QSpinBox {{ background:{t['btn_bg']}; color:{t['text']}; border:none; "
                        f"border-radius:7px; padding:4px 8px; font-size:11.5px; }} QComboBox QAbstractItemView {{ "
                        f"background:{t.get('solid_bg') or '#1c1c2a'}; color:{t['text']}; }}")
        return w

    def _kind_box(self) -> QComboBox:
        box = QComboBox()
        box.addItems(["news", "jobs", "conferences", "funding"])
        self._styled(box)
        return box

    def _source_row(self, s: dict[str, Any], t: dict[str, Any]) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        sw = QPushButton("On" if s["enabled"] else "Off")
        sw.setCheckable(True)
        sw.setChecked(bool(s["enabled"]))
        sw.setCursor(Qt.PointingHandCursor)
        sw.setStyleSheet(f"QPushButton {{ background:{t['section_btn'] if s['enabled'] else t['btn_bg']}; color:{t['text']}; "
                         "border:none; border-radius:7px; padding:3px 9px; font-size:10.5px; }")
        sw.clicked.connect(lambda on, sid=s["id"]: self.run_async(lambda: logic.trace_set_enabled(sid, on), lambda _r: self.on_changed()))
        row.addWidget(sw)
        per_week = s.get("rate_per_week") or 0
        rate = (f" · ~{round(per_week) if per_week >= 10 else per_week}/week · checked every {s['next_check_h']:g} h"
                if s.get("next_check_h") else "")
        row.addWidget(_label(f"{s['name']} · {KIND_LABELS.get(s.get('kind'), '')}{rate}", f"color:{t['text']}; font-size:11px;"), 1)
        row.addWidget(_label(f"{round(s['mean'] * 100)}% kept ({s['n']} decided)" if s["n"] else "new: proving itself",
                             f"color:{t['muted']}; font-size:10.5px;", False))
        return w

    def _done(self, out: Any) -> None:
        out = out if isinstance(out, dict) else {"error": str(out)}
        self.toast(out.get("error") or out.get("message") or "Saved.")
        self.on_changed()

    def _save_inbox(self) -> None:
        addr, labels, pw = self.addr.text(), [x.strip() for x in self.labels.text().split(",")], self.pw.text()
        self.pw.clear()
        self.run_async(lambda: logic.trace_set_inbox(addr, labels, pw), self._done)

    def _check_now(self) -> None:
        self.toast("TRACE is checking the feeds and the inbox…")
        self.run_async(lambda: logic.trace_run(manual=True), self._done)

    def _add_sender(self) -> None:
        a, n, k = self.s_addr.text(), self.s_name.text(), self.s_kind.currentText()
        self.run_async(lambda: logic.trace_add_sender(a, n, k), self._done)

    def _add_feed(self) -> None:
        ft, ref, n, k = self.f_type.currentText(), self.f_ref.text(), self.f_name.text(), self.f_kind.currentText()
        self.run_async(lambda: logic.trace_add_feed(ft, ref, n, k), self._done)

    def apply_theme(self) -> None:
        if self.stats:
            self.render(self.stats)
