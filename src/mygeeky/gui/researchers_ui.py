"""Circle → 📄 Researchers, in the panel: 🆕 New work from the people you follow (preprints first, a preprint and its
published version as one), 👥 Following (find anyone by name, the "is this the right one?" check, and the list), and
✨ Suggested (who cites you, who leads your field's rising papers). The parts are planets in the navigation, not tabs
in the page. researchers.py does the reading; the phone shows the same (components/researchers-view.tsx). Titles and
names come from OpenAlex, so they're plain text.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QToolTip,
                               QVBoxLayout, QWidget)

from .. import researchers as rs

PARTS = [("new", "New work", "🆕"), ("following", "Following", "👥"), ("suggested", "Suggested", "✨"),
         ("network", "Network", "🕸")]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def day_text(iso: str) -> str:
    return f"{int(iso[8:10])} {MONTHS[int(iso[5:7]) - 1]} {iso[:4]}" if len(iso) >= 10 else iso


def rate_text(rate: float) -> str:
    if rate >= 1:
        return f"about {rate:.0f} paper{'s' if round(rate) != 1 else ''} a month"
    if rate > 0:
        return f"about {round(rate * 12)} a year"
    return "nothing in the last year yet"


def _label(text: str, css: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.PlainText)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(css + " background:transparent;")
    return lbl


YOU, CO, FAR, FOLLOWED = "#7a5cff", "#2a78d6", "#8f8ba8", "#eb6834"


class NetworkMap(QWidget):
    """You in the middle, co-authors on the inner ring, one introduction away outside, the people you follow in
    orange; lines where people wrote together. Click someone to see who connects you."""

    def __init__(self, net: dict[str, Any], theme: Callable[[], dict[str, Any]], on_pick: Callable[[str], None]) -> None:
        super().__init__()
        self.net, self.theme, self.on_pick = net, theme, on_pick
        self.pos = rs.layout(net)
        self.picked = ""
        self.setMinimumHeight(340)
        self.setMouseTracking(True)

    def _xy(self, nid: str) -> QPointF:
        x, y = self.pos[nid]
        r = min(self.width(), self.height()) / 2 - 18
        return QPointF(self.width() / 2 + x * r, self.height() / 2 + y * r)

    def _radius(self, n: dict[str, Any]) -> float:
        return 10.0 if n["ring"] == 0 else 4.0 + min(5.0, n["n"] ** 0.5 * 1.5)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self.theme()
        path = set(rs.path_to(self.net, self.picked)) if self.picked else set()
        for a, b, w in self.net.get("edges") or []:
            if a not in self.pos or b not in self.pos:
                continue
            on = a in path and b in path
            c = QColor(FOLLOWED if on else t.get("muted", "#888"))
            c.setAlphaF(0.9 if on else min(0.5, 0.12 + 0.06 * w))
            p.setPen(QPen(c, 2.5 if on else 1.0))
            p.drawLine(self._xy(a), self._xy(b))
        for n in self.net.get("nodes") or []:
            if n["id"] not in self.pos:
                continue
            color = YOU if n["ring"] == 0 else FOLLOWED if n["followed"] else CO if n["ring"] == 1 else FAR
            p.setPen(QPen(QColor(t.get("text", "#fff")), 2) if n["id"] == self.picked else Qt.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(self._xy(n["id"]), self._radius(n), self._radius(n))
        p.setPen(QColor(t.get("text", "#fff")))
        f = p.font()
        f.setPointSizeF(7.5)
        p.setFont(f)
        for n in self.net.get("nodes") or []:
            if n["ring"] == 1 or n["followed"] or n["id"] == self.picked or n["ring"] == 0:
                pt = self._xy(n["id"])
                label = (n["name"] if n["ring"] else "you").split(" ")[-1][:14]
                w = p.fontMetrics().horizontalAdvance(label)
                p.drawText(QPointF(pt.x() - w / 2, pt.y() - self._radius(n) - 3), label)

    def _at(self, pt: QPointF) -> str:
        best, dist = "", 1e9
        for n in self.net.get("nodes") or []:
            if n["id"] in self.pos:
                q = self._xy(n["id"])
                d = (q.x() - pt.x()) ** 2 + (q.y() - pt.y()) ** 2
                if d < dist and d <= (self._radius(n) + 6) ** 2:
                    best, dist = n["id"], d
        return best

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        nid = self._at(e.position())
        n = next((x for x in self.net.get("nodes") or [] if x["id"] == nid), None)
        if n:
            QToolTip.showText(e.globalPosition().toPoint(), " · ".join(x for x in (n["name"], n["institution"]) if x), self)
        else:
            QToolTip.hideText()

    def mousePressEvent(self, e) -> None:  # noqa: N802
        nid = self._at(e.position())
        if nid:
            self.picked = nid
            self.update()
            self.on_pick(nid)


class ResearchersPage(QScrollArea):
    def __init__(self, theme: Callable[[], dict[str, Any]], run_async: Callable[..., None],
                 on_open: Callable[[str], Any], suggested: Callable[[], list[dict[str, Any]]],
                 me: Callable[[], str] = lambda: "") -> None:
        super().__init__()
        self.theme, self.run_async, self.on_open, self.suggested, self.me = theme, run_async, on_open, suggested, me
        self.part, self.candidates, self.note, self.picked = "new", [], "", ""
        self._network_asked = False
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("background:transparent; border:none;")
        self.body = QWidget()
        self.body.setStyleSheet("background:transparent;")
        self.lay = QVBoxLayout(self.body)
        self.lay.setContentsMargins(0, 4, 4, 4)
        self.lay.setSpacing(6)
        self.setWidget(self.body)
        self._loaded = False

    # ---- what the navigation asks for
    def set_part(self, part: str) -> None:
        self.part = part if part in {p for p, *_ in PARTS} else "new"
        self.render()
        if self.part == "network" and not self._network_asked:          # the map, rebuilt weekly
            self._network_asked = True
            self.run_async(lambda: rs.refresh_network(self.me()), lambda _out: self.render())

    def shown(self) -> None:
        """The first time the page is seen: what's kept at once, then a look for new work (when anyone is due)."""
        self.render()
        if not self._loaded:
            self._loaded = True
            self.run_async(lambda: rs.refresh(), lambda _out: self.render())

    # ---- drawing
    def _clear(self) -> None:
        while self.lay.count():
            item = self.lay.takeAt(0)
            if item.widget():
                item.widget().hide()                  # gone at once, not only when Qt gets round to deleting it
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().hide()
                        sub.widget().deleteLater()

    def _btn(self, text: str, fn: Callable[[], Any], accent: bool = False) -> QPushButton:
        t = self.theme()
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(f"QPushButton {{ background:{t['accent'] if accent else t['section_btn']}; "
                        f"color:{t['on_accent'] if accent else t['text']}; "
                        "border:none; border-radius:8px; padding:4px 10px; font-size:11px; }")
        b.clicked.connect(fn)
        return b

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        t = self.theme()
        card = QFrame()
        card.setObjectName("rcard")
        card.setStyleSheet(f"#rcard {{ background:{t.get('card_bg', 'rgba(128,128,128,25)')}; border-radius:10px; }}")
        col = QVBoxLayout(card)
        col.setContentsMargins(10, 8, 10, 8)
        col.setSpacing(2)
        return card, col

    def render(self) -> None:
        self._clear()
        t = self.theme()
        muted, text = f"color:{t['muted']}; font-size:10.5px;", f"color:{t['text']}; font-size:12px; font-weight:700;"
        state = rs.load()
        if self.note:
            self.lay.addWidget(_label(self.note, muted))
        if self.part == "new":
            self.lay.addWidget(_label("New preprints and papers from the people you follow, as they appear: a preprint "
                                      "and its published version show as one.", muted))
            row = QHBoxLayout()
            row.addWidget(_label(f"Following {len(state['following'])} · updated "
                                 f"{day_text((state.get('updated_at') or '')[:10]) or 'never'}", muted), 1)
            row.addWidget(self._btn("Refresh", self.refresh))
            self.lay.addLayout(row)
            items = rs.feed(state, "")[:40]
            if not state["following"]:
                self.lay.addWidget(_label("You don't follow anyone yet: find people in 👥 Following, or start from ✨ "
                                          "Suggested.", muted))
            for w in items:
                card, col = self._card()
                head = _label(("🆕 " if w["new"] else "") + w["title"], text)
                head.setCursor(Qt.PointingHandCursor)
                head.mousePressEvent = lambda ev, u=w["url"]: self.on_open(u)  # noqa: ARG005
                col.addWidget(head)
                col.addWidget(_label(", ".join(w["names"]) + (f" and {w['authors'] - len(w['names'])} more"
                                                              if w["authors"] > len(w["names"]) else ""), muted))
                where = ("📄 preprint · " if w["preprint"] else "") + (w["venue"] or "") + f" · {day_text(w['date'])}"
                col.addWidget(_label(where, muted))
                if w.get("preprint_of"):
                    p = w["preprint_of"]
                    col.addWidget(_label(f"now published · first as a preprint on {p['venue'] or 'a preprint server'}, "
                                         f"{day_text(p['date'])}", f"color:{t.get('good', '#34d399')}; font-size:10.5px;"))
                self.lay.addWidget(card)
            rs.mark_seen([w["id"] for w in items])
        elif self.part == "following":
            self.lay.addWidget(_label("Follow anyone who publishes, by name. The list stays on this computer: nobody is "
                                      "told, and myGeeKy never contacts them.", muted))
            row = QHBoxLayout()
            self.query = QLineEdit()
            self.query.setPlaceholderText("First and last name")
            self.query.setStyleSheet(f"background:rgba(128,128,128,30); color:{t['text']}; border-radius:6px; padding:4px;")
            self.query.returnPressed.connect(self.find)
            row.addWidget(self.query, 1)
            row.addWidget(self._btn("Find", self.find, accent=True))
            self.lay.addLayout(row)
            for c in self.candidates:
                card, col = self._card()
                col.addWidget(_label(c["name"], text))
                col.addWidget(_label(" · ".join(x for x in (c.get("institution"), ", ".join(c.get("topics") or []),
                                                            f"{c.get('works', 0)} works") if x), muted))
                for title in (c.get("titles") or [])[:2]:
                    col.addWidget(_label("· " + title, muted))
                col.addWidget(self._btn("Follow", lambda c=c: self.follow(c), accent=True), 0, Qt.AlignLeft)
                self.lay.addWidget(card)
            if state["following"]:
                self.lay.addWidget(_label(f"YOU FOLLOW ({len(state['following'])})", f"color:{t['text']}; font-size:10.5px; "
                                          "font-weight:700; margin-top:6px;"))
            for p in state["following"]:
                card, col = self._card()
                r = QHBoxLayout()
                r.addWidget(_label(p["name"], text), 1)
                r.addWidget(self._btn("Unfollow", lambda aid=p["id"]: self.unfollow(aid)))
                col.addLayout(r)
                col.addWidget(_label(" · ".join(x for x in (p.get("institution"), rate_text(p.get("rate") or 0.0),
                                                            "checked " + day_text(p["checked"]) if p.get("checked") else "")
                                                if x), muted))
                self.lay.addWidget(card)
        elif self.part == "network":
            net = state.get("network") or {}
            self.lay.addWidget(_label("You in the middle, your co-authors around you, the people one introduction away "
                                      "outside, and the people you follow in orange. Click anyone to see who connects "
                                      "you. Rebuilt weekly from your papers.", muted))
            if not self.me():
                self.lay.addWidget(_label("Add your ORCID iD, or find your papers by your name (⚙ → Your papers), to "
                                          "see your co-author network.", muted))
            elif not net.get("nodes"):
                self.lay.addWidget(_label("Building your network…", muted))
            else:
                legend = QHBoxLayout()
                for color, word in ((YOU, "you"), (CO, "co-authors"), (FAR, "one introduction away"), (FOLLOWED, "you follow")):
                    legend.addWidget(_label(f"● {word}", f"color:{color}; font-size:10px;"))
                legend.addStretch(1)
                self.lay.addLayout(legend)
                self.lay.addWidget(NetworkMap(net, self.theme, self.pick))
                who = next((n for n in net["nodes"] if n["id"] == self.picked), None)
                if who and who["ring"]:
                    card, col = self._card()
                    col.addWidget(_label(who["name"], text))
                    names = {n["id"]: n["name"] for n in net["nodes"]}
                    route = rs.path_to(net, who["id"])
                    col.addWidget(_label(" · ".join(x for x in (who["institution"], "you → " + " → ".join(
                        names.get(x, x) for x in route[1:]) if len(route) > 1 else "") if x), muted))
                    if not who["followed"]:
                        col.addWidget(self._btn("Follow", lambda w=who: self.follow(w), accent=True), 0, Qt.AlignLeft)
                    self.lay.addWidget(card)
                circle = rs.circle_weights(net.get("topics") or {})
                on = rs.circle_on(state)
                top = ", ".join(list(circle)[:5])
                self.lay.addWidget(_label(("Your Model learns from your circle: " if on else "Your Model doesn't learn from "
                                           "your circle (switched off). It would add: ") + (top or "nothing yet") + ".", muted))
                self.lay.addWidget(self._btn("Stop learning from my circle" if on else "Learn from my circle",
                                             lambda: (rs.set_circle(not on), self.render())), 0, Qt.AlignLeft)
        else:
            self.lay.addWidget(_label("People worth following, from what myGeeKy already read: who cites your work, and "
                                      "who leads the papers rising in your field.", muted))
            people = self.suggested()
            if not people:
                self.lay.addWidget(_label("No suggestions yet. They come from You → Cited by and World → Papers.", muted))
            for p in people:
                card, col = self._card()
                col.addWidget(_label(p["name"], text))
                col.addWidget(_label(" · ".join(x for x in (p.get("institution"), p["why"]) if x), muted))
                col.addWidget(self._btn("Follow", lambda p=p: self.follow(p), accent=True), 0, Qt.AlignLeft)
                self.lay.addWidget(card)
        self.lay.addStretch(1)

    # ---- actions
    def refresh(self) -> None:
        self.note = "Looking for new work…"
        self.render()

        def done(out: dict[str, Any]) -> None:
            self.note = "OpenAlex is resting for now (its daily budget): this is what was found before." if out.get("busy") else ""
            self.render()
        self.run_async(lambda: rs.refresh(force=True), done)

    def find(self) -> None:
        name = self.query.text().strip()
        self.note = "Looking…"
        self.render()

        def done(out: dict[str, Any]) -> None:
            self.candidates = out.get("candidates") or []
            self.note = ("" if self.candidates else out.get("why") or
                         ("OpenAlex is resting for now (its daily budget). Try again later." if out.get("status") == "busy"
                          else "Nobody by that name. Try their full name as it appears on their papers."))
            self.render()
        self.run_async(lambda: rs.search(name), done)

    def follow(self, person: dict[str, Any]) -> None:
        rs.follow(person)
        self.candidates = [c for c in self.candidates if c["id"] != person["id"]]
        self.note = f"Following {person['name']}. Their new work appears in 🆕 New work."
        self.render()
        self.run_async(lambda: rs.refresh(), lambda _out: self.render())

    def pick(self, nid: str) -> None:
        self.picked = nid
        self.render()

    def unfollow(self, aid: str) -> None:
        rs.unfollow(aid)
        self.note = ""
        self.render()
