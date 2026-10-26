"""Circle → Researchers → 🌟 Leading lights, in the panel: a few people who lead your field (a new set every three days,
picked by your Model), each with why (🏅 🏆 📈 🛠), their latest papers, Follow, and their links; a tap unfolds their
report under them (lights.py does the reading; the phone shows the same in components/lights-view.tsx). Everything is plain
text: the list and OpenAlex's answers come from the internet."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import lights
from .. import researchers as rs
from .app import readable

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
REPORT_MAIL = ("mailto:support@mygeeky.org?subject=Leading%20lights%3A%20a%20mistake"
               "&body=Who%2C%20and%20what%20is%20wrong%20(wrong%20person%2C%20wrong%20prize%2C%20has%20passed%20away%E2%80%A6)%3A%0A")


def _label(text: str, css: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.PlainText)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(css + " background:transparent;")
    return lbl


def _day(iso: str) -> str:
    return f"{int(iso[8:10])} {MONTHS[int(iso[5:7]) - 1]}" if len(iso) >= 10 else iso


def badge_text(p: dict[str, Any]) -> str:
    emoji, word = lights.BADGES[p["badge"]]
    return f"{emoji} {word}"


class YearBars(QWidget):
    """Papers (bars) and citations (dots on a line) per year, the last ten years: rising, steady or quieter."""

    def __init__(self, years: list[list[int]], theme: dict[str, Any]) -> None:
        super().__init__()
        self.years, self.theme = years, theme
        self.setFixedHeight(110)          # fixed: inside a card that wraps text, a minimum gets squeezed

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t, n = self.theme, max(1, len(self.years))
        w, h = self.width(), self.height() - 16
        most_w = max([y[1] for y in self.years] + [1])
        most_c = max([y[2] for y in self.years] + [1])
        step = w / n
        bar = QColor(t.get("accent", "#7c3aed"))
        bar.setAlphaF(0.75)
        line = QColor(t.get("text", "#ffffff"))
        pts = []
        for i, (year, works, cites) in enumerate(self.years):
            bh = (h - 6) * works / most_w
            p.fillRect(QRectF(i * step + step * 0.2, h - bh, step * 0.6, bh), bar)
            pts.append((i * step + step / 2, h - (h - 6) * cites / most_c))
            if i % 3 == n % 3 or i == n - 1:
                p.setPen(QColor(t.get("muted", "#999")))
                p.drawText(QRectF(i * step - 6, h + 2, step + 12, 14), Qt.AlignHCenter, str(year))
        p.setPen(line)
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            p.drawLine(int(x1), int(y1), int(x2), int(y2))
        p.setBrush(line)
        for x, y in pts:
            p.drawEllipse(QRectF(x - 2, y - 2, 4, 4))
        p.end()


class ReportPanel(QFrame):
    """What a tap on someone shows, unfolded right under them in the list (like a GitHub person's profile in People):
    their numbers, the last ten years, their topics (yours marked), their most cited papers and where to read more."""

    def __init__(self, person: dict[str, Any], rep: dict[str, Any], theme: dict[str, Any],
                 on_open: Callable[[str], Any]) -> None:
        super().__init__()
        t = theme
        self.setObjectName("lightReport")
        self.setStyleSheet(f"QFrame#lightReport {{ background:{t['card_bg']}; border:1px solid {t['accent']}; "
                           "border-radius:10px; }")
        muted, text = f"color:{t['muted']}; font-size:10.5px;", f"color:{t['text']}; font-size:11.5px;"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(4)
        if rep.get("institution"):
            lay.addWidget(_label(rep["institution"], muted))
        nums = QHBoxLayout()
        for value, word in ((rep["works"], "papers"), (rep["cited"], "citations"), (rep["h"], "h-index"),
                            (rep["i10"], "i10-index")):
            box = QVBoxLayout()
            box.setSpacing(0)
            box.addWidget(_label(f"{value:,}", f"color:{t['text']}; font-size:14px; font-weight:800;"))
            box.addWidget(_label(word, muted))
            nums.addLayout(box)
        lay.addLayout(nums)
        lay.addWidget(_label("Papers (bars) and citations (line), the last ten years", muted))
        lay.addWidget(YearBars(rep["years"], t))
        if rep["topics"]:
            lay.addWidget(_label("Topics: " + ", ".join(("★ " if mine else "") + name for name, mine in rep["topics"])
                                 + ("   (★ also yours)" if any(m for _, m in rep["topics"]) else ""), text))
        if rep["top"]:
            lay.addWidget(_label("MOST CITED", f"color:{t['text']}; font-size:10px; font-weight:700; margin-top:4px;"))
        for w in rep["top"]:
            row = _label(f"{w['title']}  ·  {w['year'] or ''} · {w['cited']:,} citations", text)
            row.setCursor(Qt.PointingHandCursor)
            row.mousePressEvent = lambda ev, u=w["url"]: on_open(u)  # noqa: ARG005
            lay.addWidget(row)
        links = QHBoxLayout()
        for word, url in lights.links(person):
            b = QPushButton(word + " ↗")
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ background:{t['section_btn']}; color:{t['text']}; border:none; "
                            "border-radius:8px; padding:3px 9px; font-size:10.5px; }")
            b.clicked.connect(lambda _=False, u=url: on_open(u))
            links.addWidget(b)
        links.addStretch(1)
        lay.addLayout(links)
        if person.get("source"):
            src = _label("Why they're here: source ↗", muted)
            src.setCursor(Qt.PointingHandCursor)
            src.mousePressEvent = lambda ev: on_open(person["source"])  # noqa: ARG005
            lay.addWidget(src)


def render(page: Any, muted: str, text: str) -> None:
    """The 🌟 part of the Researchers page (researchers_ui.ResearchersPage), drawn into its layout."""
    t = page.theme()
    today = date.today().isoformat()
    people = page.lights_people()
    shown = lights.pick(people, page.weights(), today)
    following = {p["id"] for p in rs.load()["following"]}
    page.lay.addWidget(_label(f"People who lead your field, picked by your Model: a new set every {lights.EVERY_DAYS} "
                              f"days (next on {_day(lights.next_change(today))}). Tap a name for their numbers.", muted))
    if not shown:
        page.lay.addWidget(_label("The list isn't here yet.", muted))
    for p in shown:
        card, col = page._card()
        head = QHBoxLayout()
        name = _label(p["name"], text)
        name.setCursor(Qt.PointingHandCursor)
        name.mousePressEvent = lambda ev, p=p: page.light_report(p)  # noqa: ARG005
        head.addWidget(name, 1)
        head.addWidget(_label(badge_text(p), f"color:{readable(t['accent'], t)}; font-size:10.5px; font-weight:700;"),
                       0, Qt.AlignTop)
        col.addLayout(head)
        col.addWidget(_label(" · ".join(x for x in (p["why"], p["institution"]) if x), muted))
        for w in page.lights_recent.get(p["id"]) or []:
            paper = _label(f"📄 {w['title']}  ·  {_day(w['date'])}{' · ' + w['venue'] if w['venue'] else ''}",
                           f"color:{t['text']}; font-size:11px;")
            paper.setCursor(Qt.PointingHandCursor)
            paper.mousePressEvent = lambda ev, u=w["url"]: page.on_open(u)  # noqa: ARG005
            col.addWidget(paper)
        row = QHBoxLayout()
        row.addWidget(page._btn("Hide" if page.lights_open == p["id"] else "Report", lambda p=p: page.light_report(p),
                                accent=True))
        if p["id"] in following:
            row.addWidget(_label("✓ Following", muted))
        else:
            row.addWidget(page._btn("Follow", lambda p=p: page.follow(
                {"id": p["id"], "name": p["name"], "institution": p["institution"], "topics": p["topics"][:3]})))
        word, url = lights.links(p)[0]
        row.addWidget(page._btn(word + " ↗", lambda u=url: page.on_open(u)))
        row.addStretch(1)
        col.addLayout(row)
        if page.lights_open == p["id"]:                    # the report, unfolded under them
            rep = page.lights_reports.get(p["id"])
            col.addWidget(ReportPanel(p, rep, t, page.on_open) if rep else
                          _label(page.lights_wait or f"Looking up {p['name']}…", muted))
        page.lay.addWidget(card)
    wrong = _label("Something wrong (wrong person, wrong prize, someone who has passed away)? Report a mistake ↗", muted)
    wrong.setCursor(Qt.PointingHandCursor)
    wrong.mousePressEvent = lambda ev: page.on_open(REPORT_MAIL)  # noqa: ARG005
    page.lay.addWidget(wrong)
    ids = tuple(p["id"] for p in shown)
    if ids and page.lights_for != ids:                     # their latest papers: one search for everyone on show
        page.lights_for = ids                              # (asked last: an answer redraws the page)
        page.run_async(lambda: lights.fetch_recent(shown, today), page.lights_got)
