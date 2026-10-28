"""Settings → Accounts in the panel: GitHub and ORCID, then saving your data and Signals, then your phone (accounts.py
says what each card says, the same as the phone's lib/accounts.ts). A connected card is one folded green line that
unfolds on a click; an optional one says why you might want it; one whose access stopped working is red. The buttons
reuse what the panel already does (the setup window, the Signals switch, a new token, Connect your phone).
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import app as logic

# (label, action name, kind) per card and state; the panel maps action names to what they do
ACTIONS: dict[tuple[str, str], list[tuple[str, str, str]]] = {
    ("github", "off"): [("Sign in with GitHub", "setup", "primary")],
    ("github", "bad"): [("Sign in again", "setup", "bad")],
    ("orcid", "off"): [("Link ORCID", "setup", "primary")],
    ("data", "off"): [("Keep it in Google Drive", "drive", "primary"), ("Use a GitHub repo", "github", "ghost")],
    ("data", "bad"): [("Open the setup window", "setup", "bad")],
    ("data", "on"): [("Sync now", "sync", "ghost")],
    ("beacon", "off"): [("Set up Signals", "signals_on", "primary")],
    ("beacon", "on"): [("Turn Signals off", "signals_off", "ghost")],
    ("beacon", "bad"): [("Renew on GitHub", "renew", "bad"), ("Paste new token", "paste_beacon", "ghost")],
    ("device", "off"): [("Connect your phone", "pair", "primary")],
}


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()
        elif item.layout():
            _clear(item.layout())


class AccountsSection(QWidget):
    def __init__(self, theme: Callable[[], dict[str, Any]], act: Callable[[str], None]) -> None:
        super().__init__()
        self.theme, self.act = theme, act
        self.items: list[dict] = []
        self.unfolded: set[str] = set()
        self.headings: dict[str, QLabel] = {}          # where the tour points ("setup": SIGN IN, "sync": SAVING)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(6)

    def set_cards(self, items: list[dict]) -> None:
        self.items = items
        self.render()

    def apply_theme(self) -> None:
        self.render()

    def _label(self, text: str, css: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.PlainText)
        lbl.setStyleSheet(css)
        return lbl

    def _button(self, text: str, kind: str, on_click: Callable[[], None]) -> QPushButton:
        t = self.theme()
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        if kind == "primary":
            css = f"background:{t['accent']}; color:{t['on_accent']}; border:none; font-weight:700;"
        elif kind == "bad":
            css = f"background:{t['bad']}; color:#1a1013; border:none; font-weight:700;"
        else:
            css = f"background:{t['btn_bg']}; color:{t['text']}; border:none;"
        b.setStyleSheet(f"QPushButton {{ {css} border-radius:9px; padding:4px 12px; font-size:11px; }}"
                        f"QPushButton:hover {{ background:{t['btn_hover']}; color:{t['text']}; }}")
        b.clicked.connect(lambda _checked=False: on_click())
        return b

    def _cols(self) -> int:
        return 1 if self.isVisible() and self.width() < 300 else 2      # not laid out yet: two

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        if (e.oldSize().width() >= 300) != (e.size().width() >= 300) and e.oldSize().width() > 0:
            self.render()                    # the buttons go one or two to a row

    def _toggle(self, key: str) -> None:
        self.unfolded ^= {key}
        self.render()

    def render(self) -> None:
        _clear(self.lay)
        self.headings = {}
        t = self.theme()
        good, bad, warn = (logic.readable(t[k], t) for k in ("good", "bad", "warn"))
        from ..accounts import todo, todo_text
        n = todo(self.items)
        if n:
            box = self._label("⚠  " + todo_text(n), f"color:{warn}; background:{t['card_bg']}; border-radius:9px; "
                                                         "padding:7px 10px; font-size:11.5px; font-weight:700;")
            self.lay.addWidget(box)
        for c in self.items:
            if c["heading"]:
                h = self._label(c["heading"], f"color:{t['muted']}; font-size:10px; font-weight:800; letter-spacing:1px; "
                                              "background:transparent; margin-top:6px;")
                self.lay.addWidget(h)
                self.headings[{"github": "setup", "data": "sync"}.get(c["key"], c["key"])] = h
            on, broken = c["state"] == "on", c["state"] == "bad"
            border = bad if broken else good if on else t["border"]
            card = QFrame()
            card.setObjectName("acct")
            card.setStyleSheet(f"QFrame#acct {{ background:{t['card_bg']}; border:1.5px solid {border}; border-radius:12px; }}")
            col = QVBoxLayout(card)
            col.setContentsMargins(10, 6 if on else 8, 10, 6 if on else 9)
            col.setSpacing(5)
            head = QHBoxLayout()
            head.setSpacing(8)
            title = QPushButton(c["title"] + ("  ▾" if on and c["key"] not in self.unfolded else "  ▴" if on else ""))
            title.setFlat(True)
            title.setCursor(Qt.PointingHandCursor if on else Qt.ArrowCursor)
            title.setStyleSheet(f"QPushButton {{ color:{t['text']}; background:transparent; border:none; text-align:left; "
                                "font-size:12.5px; font-weight:800; padding:0; }")
            if on:
                title.clicked.connect(lambda _checked=False, k=c["key"]: self._toggle(k))
            head.addWidget(title, 1)
            pill_color = bad if broken else good if on else t["muted"]
            head.addWidget(self._label(c["pill"], f"color:{pill_color}; background:{t['btn_bg']}; border-radius:8px; "
                                                  "padding:2px 8px; font-size:10px; font-weight:800;"))
            col.addLayout(head)
            if not on or c["key"] in self.unfolded:
                col.addWidget(self._label(c["why"], f"color:{t['text']}; font-size:11px; background:transparent;"))
                buttons = c.get("actions") or ACTIONS.get((c["key"], c["state"]), [])
                grid = QGridLayout()                 # two to a row, one when narrow (beside a pinned menu)
                grid.setSpacing(6)
                cols = self._cols()
                for i, (label, action, kind) in enumerate(buttons):
                    grid.addWidget(self._button(label, kind, lambda a=action: self.act(a)), i // cols, i % cols)
                if len(buttons) == 1 and cols == 2:
                    grid.setColumnStretch(1, 1)
                if buttons:
                    col.addLayout(grid)
            self.lay.addWidget(card)
