"""You → 📑 Cited by, in the panel: your citations at a glance, the new papers citing you, the people who cite you
most, and where you're read. citedby.py does the reading; the phone shows the same (components/cited-by-view.tsx).
Titles and names come from OpenAlex, so they're shown as plain text.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


def flag(code: str) -> str:
    """'SE' -> 🇸🇪 (a country's flag from its two letters)."""
    code = (code or "").upper()
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code) if len(code) == 2 and code.isalpha() else "🌍"


def _label(text: str, css: str, wrap: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.PlainText)
    lbl.setWordWrap(wrap)
    lbl.setStyleSheet(css + " background:transparent;")
    return lbl


class _Row(QFrame):
    """A card you can click to open its link."""

    def __init__(self, url: str, css: str) -> None:
        super().__init__()
        self.url = url
        self.setStyleSheet(css)
        if url:
            self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 -- Qt's naming
        if self.url.startswith("https://"):
            QDesktopServices.openUrl(QUrl(self.url))


class CitedByPage(QWidget):
    def __init__(self, theme: Callable[[], dict[str, Any]], on_first_show: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.theme, self.on_first_show = theme, on_first_show
        self.data: dict[str, Any] | None = None
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 4, 0, 0)
        self.lay.setSpacing(6)
        self.lay.addWidget(_label("Looking for who cites you…", "color:gray; font-size:11px;"))

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self.on_first_show is not None:
            first, self.on_first_show = self.on_first_show, None
            QTimer.singleShot(0, first)

    def set_data(self, data: Any) -> None:
        self.data = data if isinstance(data, dict) else {}
        self.render()

    def _head(self, text: str) -> None:
        t = self.theme()
        self.lay.addWidget(_label(text, f"color:{t['text']}; font-size:10.5px; font-weight:800; letter-spacing:0.5px; "
                                        "margin-top:8px;"))

    def render(self) -> None:
        while self.lay.count():
            w = self.lay.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        t, d = self.theme(), self.data or {}
        muted = f"color:{t['muted']}; font-size:10.5px;"
        if not d.get("author"):
            self.lay.addWidget(_label("See who cites your papers: add your ORCID iD, or find your papers by your name "
                                      "(⚙ → Your papers).", f"color:{t['muted']}; font-size:11px;"))
            return
        s = d.get("summary") or {}
        tot = s.get("totals") or {}
        tiles = QWidget()
        tl = QHBoxLayout(tiles)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(5)
        for value, what in ((tot.get("cited", 0), "citations"), (tot.get("h", 0), "h-index"),
                            (s.get("this_month", 0), "this month"), (s.get("new", 0), "new to you")):
            tile = QLabel(f"<b style='font-size:14px'>{int(value)}</b><br><span style='font-size:9.5px'>{what}</span>")
            tile.setTextFormat(Qt.RichText)
            tile.setAlignment(Qt.AlignCenter)
            tile.setStyleSheet(f"color:{t['text']}; background:{t['btn_bg']}; border-radius:9px; padding:5px 2px;")
            tl.addWidget(tile, 1)
        self.lay.addWidget(tiles)
        if d.get("busy"):
            self.lay.addWidget(_label("OpenAlex is busy right now: this is what was found before. It looks again tomorrow.",
                                      f"color:{t['warn']}; font-size:10.5px;"))

        citing = s.get("citing") or []
        self._head("📑 NEW PAPERS CITING YOU")
        if not citing:
            self.lay.addWidget(_label("No citing papers found yet. They appear here as they're published.", muted))
        card = f"QFrame {{ background:{t['card_bg']}; border-radius:10px; }}"
        for c in citing[:12]:
            row = _Row(c.get("url", ""), card)
            rl = QVBoxLayout(row)
            rl.setContentsMargins(9, 7, 9, 7)
            rl.setSpacing(2)
            title = ("🆕 " if c.get("new") else "") + c.get("title", "")
            rl.addWidget(_label(title, f"color:{t['text']}; font-size:11.5px; font-weight:700;"))
            authors = c.get("authors") or []
            first = authors[0] if authors else {}
            who = (first.get("name", "") + (" et al." if len(authors) > 1 else "")) if first else ""
            where = ", ".join(x for x in (first.get("institution", ""), first.get("country", "")) if x)
            rl.addWidget(_label(" · ".join(x for x in (who, where, c.get("date", "")) if x), muted))
            mine = [x for x in c.get("cites_titles") or [] if x]
            if mine:
                rl.addWidget(_label("cites: " + "; ".join(m[:70] for m in mine[:2]), f"color:{t['link']}; font-size:10px;"))
            self.lay.addWidget(row)

        people = s.get("people") or []
        if people:
            self._head("👥 WHO CITES YOU MOST")
            for p in people[:6]:
                url = f"https://openalex.org/{p['id']}" if p.get("id") else ""
                row = _Row(url, card)
                rl = QHBoxLayout(row)
                rl.setContentsMargins(9, 5, 9, 5)
                rl.addWidget(_label(f"{flag(p.get('country', ''))}  {p.get('name', '')}", f"color:{t['text']}; font-size:11px; "
                                                                                          "font-weight:700;"), 1)
                rl.addWidget(_label(f"{p.get('count', 0)}×", muted, wrap=False))
                self.lay.addWidget(row)
                if p.get("institution"):
                    rl.parentWidget().setToolTip(p["institution"])

        countries = s.get("countries") or []
        if countries:
            self._head("🌍 WHERE YOU'RE READ")
            top = max(c["count"] for c in countries) or 1
            for c in countries[:6]:
                line = QWidget()
                ll = QHBoxLayout(line)
                ll.setContentsMargins(0, 0, 0, 0)
                ll.setSpacing(6)
                ll.addWidget(_label(f"{flag(c['code'])} {c['code']}", f"color:{t['text']}; font-size:10.5px;", wrap=False))
                bar = QFrame()
                bar.setFixedHeight(7)
                bar.setFixedWidth(max(6, int(150 * c["count"] / top)))
                bar.setStyleSheet(f"background:{t['accent']}; border-radius:3px;")
                ll.addWidget(bar)
                ll.addWidget(_label(str(c["count"]), muted, wrap=False))
                ll.addStretch(1)
                self.lay.addWidget(line)
        credit = QLabel(f"Data: <a style='color:{t['link']}' href='https://openalex.org'>OpenAlex</a>, checked once a day.")
        credit.setTextFormat(Qt.RichText)
        credit.setOpenExternalLinks(False)
        credit.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        credit.setStyleSheet(f"color:{t['muted']}; font-size:9.5px; background:transparent; margin-top:6px;")
        self.lay.addWidget(credit)
        self.lay.addStretch(1)
