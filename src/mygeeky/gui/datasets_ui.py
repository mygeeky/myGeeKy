"""Grow → 🗂️ Data, in the panel: public datasets to practise and train on, ordered for you, with a field picker.
datasets.py reads and ranks the list; the phone shows the same (components/datasets-view.tsx). Titles and
descriptions come from the internet (Zenodo, GEO, OpenML), so they're shown as plain text.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import datasets
from .growth_ui import ThumbBar, _card_style


def _label(text: str, css: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.PlainText)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(css + " background:transparent;")
    return lbl


def _choice_label(f: str) -> str:
    return "✨ For you" if f == "for you" else "🆕 New on your topics" if f == "new" else "All" if f == "" else f


class DatasetCard(QFrame):
    """One dataset: what to practise, its size, format and licence, and where to get it."""

    def __init__(self, d: dict[str, Any], theme: dict[str, Any], on_vote: Callable[[bool], int],
                 on_open: Callable[[str], Any], green: str) -> None:
        super().__init__()
        self.setObjectName("datasetCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(2)
        head = QHBoxLayout()
        title = _label(d["title"], f"color:{theme['text']}; font-size:12px; font-weight:700;")
        title.setCursor(Qt.PointingHandCursor)
        title.mousePressEvent = lambda ev: on_open(d["url"])  # noqa: ARG005
        head.addWidget(title, 1)
        head.addWidget(ThumbBar(d.get("vote", 0), theme, on_vote, "Useful: more like this", "Not for me: hide it"),
                       0, Qt.AlignTop)
        lay.addLayout(head)
        lay.addWidget(_label(f"Practise: {d['why']}", f"color:{theme['text']}; font-size:11px;"))
        meta = [d["field"], d["level"], datasets.size_text(d["size_mb"]), ", ".join(d["formats"][:3]).upper(),
                d["license"] + (" (non-commercial)" if d["nc"] else "")]
        lay.addWidget(_label(" · ".join(m for m in meta if m), f"color:{theme['muted']}; font-size:10px;"))
        if d.get("for"):
            lay.addWidget(_label(f"📈 teaches {', '.join(d['for'])}, rising for you", f"color:{green}; font-size:10.5px;"))
        elif d["skills"]:
            lay.addWidget(_label("teaches " + ", ".join(d["skills"][:4]), f"color:{theme['muted']}; font-size:10.5px;"))
        row = QHBoxLayout()
        row.setSpacing(6)
        buttons = ([("⬇ Download", d["download"])] if d["download"] else []) + \
                  [("Page" if d["download"] else "⬇ Get it", d["url"])] + \
                  ([("📘 Tutorial", d["tutorial"])] if d["tutorial"] else [])
        for text, url in buttons:
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ color:{theme['text']}; background:rgba(128,128,128,40); border:none; "
                            "border-radius:8px; padding:3px 9px; font-size:10.5px; }")
            b.clicked.connect(lambda _=False, u=url: on_open(u))
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(_label(d["source"], f"color:{theme['muted']}; font-size:10px;"))
        lay.addLayout(row)
        self.setStyleSheet(_card_style("datasetCard", theme))


class RadarCard(QFrame):
    """A dataset just out on one of your keywords: where, when, how big, its licence, and a link."""

    def __init__(self, d: dict[str, Any], theme: dict[str, Any], on_vote: Callable[[bool], int],
                 on_open: Callable[[str], Any], green: str) -> None:
        super().__init__()
        self.setObjectName("radarCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(2)
        head = QHBoxLayout()
        title = _label(("🆕 " if d.get("new") else "") + d["title"], f"color:{theme['text']}; font-size:12px; font-weight:700;")
        title.setCursor(Qt.PointingHandCursor)
        title.mousePressEvent = lambda ev: on_open(d["url"])  # noqa: ARG005
        head.addWidget(title, 1)
        head.addWidget(ThumbBar(d.get("vote", 0), theme, on_vote, "Useful: more like this", "Not for me: hide it"),
                       0, Qt.AlignTop)
        lay.addLayout(head)
        if d["about"]:
            lay.addWidget(_label(d["about"][:220], f"color:{theme['text']}; font-size:10.5px;"))
        meta = [d["source"], d["date"], datasets.size_text(d["size_mb"]), d["license"] + (" (non-commercial)" if d["nc"] else "")]
        lay.addWidget(_label(" · ".join(m for m in meta if m), f"color:{theme['muted']}; font-size:10px;"))
        lay.addWidget(_label(f"matches “{d['term']}”", f"color:{green}; font-size:10.5px;"))
        b = QPushButton("Open")
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(f"QPushButton {{ color:{theme['text']}; background:rgba(128,128,128,40); border:none; "
                        "border-radius:8px; padding:3px 9px; font-size:10.5px; }")
        b.clicked.connect(lambda: on_open(d["url"]))
        row = QHBoxLayout()
        row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.setStyleSheet(_card_style("radarCard", theme))


class DatasetsSection(QWidget):
    """One field's list (or For you): the fields themselves are planets in the navigation, not tabs in the page."""

    def __init__(self, items: list[dict[str, Any]], weights: dict[str, float], wanted: list[str],
                 theme: dict[str, Any], on_vote: Callable[[dict[str, Any], bool], int],
                 on_open: Callable[[str], Any], field: str = "for you", radar: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.setStyleSheet("background:transparent;")
        self.items, self.weights, self.wanted, self.theme = items, weights, wanted, theme
        self.on_vote, self.on_open, self.field, self.radar = on_vote, on_open, field, radar or {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        terms = ", ".join(f"“{t}”" for t in self.radar.get("terms") or [])
        lay.addWidget(_label(
            f"🆕 Public datasets just out on your keywords ({terms or 'your keywords'}), from Zenodo, NCBI GEO and "
            "Figshare, checked once a day: open, no login, on topic." if field == "new" else
            f"{_choice_label(field)}: of {len(items)} datasets, each open, documented and downloadable without a login.",
            f"color:{theme['muted']}; font-size:10.5px;"))
        self.list = QVBoxLayout()
        self.list.setSpacing(6)
        lay.addLayout(self.list)
        self.fill()

    def _votes(self) -> dict[str, int]:
        from .. import taste
        votes = taste.load()
        return {d["id"]: int(votes.get(taste.key_of("dataset", d["id"]), {}).get("vote", 0)) for d in self.items}

    def fill(self) -> None:
        while self.list.count():
            w = self.list.takeAt(0).widget()
            if w:
                w.deleteLater()
        votes = self._votes()
        green = self.theme.get("good", "#34d399")
        if self.field == "new":
            from datetime import date
            from .. import taste
            all_votes = taste.load()
            rv = {i["id"]: int(all_votes.get(taste.key_of("dataset", i["id"]), {}).get("vote", 0))
                  for i in self.radar.get("items") or []}
            r = datasets.radar_rank(self.radar, self.weights, rv, date.today().isoformat())
            for d in r["items"]:
                self.list.addWidget(RadarCard(d, self.theme, lambda up, d=d: self._vote(d, up), self.on_open, green))
            if not r["items"]:
                self.list.addWidget(_label("Nothing new on your keywords yet. myGeeKy looks once a day.",
                                           f"color:{self.theme['muted']}; font-size:11px;"))
            datasets.radar_seen([d["id"] for d in r["items"]])          # shown: no longer 🆕 next time
            return
        r = datasets.rank(self.items, self.weights, self.wanted, self.field, votes)
        if self.field == "for you" and not r["items"]:     # nothing matches you yet: everything, not an empty page
            r = datasets.rank(self.items, self.weights, self.wanted, "", votes)
        green = self.theme.get("good", "#34d399")
        for d in r["items"]:
            self.list.addWidget(DatasetCard(d, self.theme, lambda up, d=d: self._vote(d, up), self.on_open, green))
        if not r["items"]:
            self.list.addWidget(_label("No datasets in this field yet.", f"color:{self.theme['muted']}; font-size:11px;"))
        if r["hidden"]:
            self.list.addWidget(_label(f"{r['hidden']} hidden with 👎.", f"color:{self.theme['muted']}; font-size:10px;"))

    def _vote(self, d: dict[str, Any], up: bool) -> int:
        v = self.on_vote({**d, "skills": d.get("skills") or [d.get("term", "")]}, up)
        if v < 0:
            self.fill()
        return v
