"""Circle → 📄 Researchers, in the panel: 🆕 New work from the people you follow (preprints first, a preprint and its
published version as one), 👥 Following (find anyone by name, the "is this the right one?" check, and the list), and
✨ Suggested (who cites you, who leads your field's rising papers). The parts are planets in the navigation, not tabs
in the page. researchers.py does the reading; the phone shows the same (components/researchers-view.tsx). Titles and
names come from OpenAlex, so they're plain text.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from .. import researchers as rs

PARTS = [("new", "New work", "🆕"), ("following", "Following", "👥"), ("suggested", "Suggested", "✨")]
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


class ResearchersPage(QScrollArea):
    def __init__(self, theme: Callable[[], dict[str, Any]], run_async: Callable[..., None],
                 on_open: Callable[[str], Any], suggested: Callable[[], list[dict[str, Any]]]) -> None:
        super().__init__()
        self.theme, self.run_async, self.on_open, self.suggested = theme, run_async, on_open, suggested
        self.part, self.candidates, self.note = "new", [], ""
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
                item.widget().deleteLater()

    def _btn(self, text: str, fn: Callable[[], Any], accent: bool = False) -> QPushButton:
        t = self.theme()
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(f"QPushButton {{ background:{t['accent'] if accent else t['section_btn']}; color:{t['text']}; "
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

    def unfollow(self, aid: str) -> None:
        rs.unfollow(aid)
        self.note = ""
        self.render()
