"""❓ Help, the last main: start GeeKOc's tours again (the one that fits you, Settings', one for each main) and read
the answers to how and why myGeeKy works, one question at a time. All the words come from data/tour.json, in the
tours' language, picked here (tour.py). The phone has the same page (components/help-view.tsx)."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from .. import tour


def _label(text: str, name: str, wrap: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName(name)
    lbl.setTextFormat(Qt.PlainText)
    lbl.setWordWrap(wrap)
    return lbl


class _Question(QFrame):
    """One question: tap it and its answer drops down under it (tap again to fold it)."""

    def __init__(self, q: str, a: str) -> None:
        super().__init__()
        self.setObjectName("question")
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)
        self.q = _label(f"▸  {q}", "q")
        self.a = _label(a, "a")
        self.a.hide()
        self._text = q
        lay.addWidget(self.q)
        lay.addWidget(self.a)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        opening = self.a.isHidden()
        self.a.setVisible(opening)
        self.q.setText(f"{'▾' if opening else '▸'}  {self._text}")


class HelpPage(QScrollArea):
    def __init__(self, cfg: Any, theme: Callable[[], dict[str, Any]], start: Callable[[str], None],
                 labels: Callable[[str], str], save: Callable[[], None]) -> None:
        super().__init__()
        self.cfg, self.theme, self.start, self.labels, self.save = cfg, theme, start, labels, save
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.viewport().setStyleSheet("background:transparent;")
        self.build()

    def lang(self) -> str:
        return tour.lang_of(self.cfg.tour_lang or "en")

    def build(self) -> None:
        lang = self.lang()
        inner = QWidget()
        inner.setObjectName("helpInner")
        inner.setLayoutDirection(Qt.RightToLeft if tour.rtl(lang) else Qt.LeftToRight)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 2, 6, 10)
        lay.setSpacing(8)
        lay.addWidget(_label(tour.ui("help", lang), "title"))
        lay.addWidget(_label(tour.ui("help_sub", lang), "sub"))

        lay.addWidget(_label(tour.ui("language", lang).upper(), "head"))
        row = QHBoxLayout()
        row.setSpacing(4)
        self.lang_btns: dict[str, QPushButton] = {}
        for code, name in tour.load()["langs"].items():
            b = QPushButton(name)
            b.setObjectName("langOn" if code == lang else "lang")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=code: self.set_lang(c))
            self.lang_btns[code] = b
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)

        lay.addWidget(_label(tour.ui("tours", lang).upper(), "head"))
        self.tour_btns: dict[str, QPushButton] = {}

        def tour_button(name: str, text: str, main: bool = False) -> None:
            b = QPushButton(text)
            b.setObjectName("tourMain" if main else "tour")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda: self.start(name))
            self.tour_btns[name] = b
            lay.addWidget(b)

        tour_button("start", "🐙  " + tour.ui("start_tour", lang), main=True)
        tour_button("settings", "⚙  " + tour.ui("settings_tour", lang))
        for name in tour.MAINS:
            tour_button(name, tour.ui("main_tour", lang, name=self.labels(name)))

        lay.addWidget(_label(tour.ui("faq", lang).upper(), "head"))
        self.questions = [_Question(q, a) for q, a in tour.faq(lang)]
        for w in self.questions:
            lay.addWidget(w)
        lay.addStretch(1)
        old = self.takeWidget()
        self.setWidget(inner)
        if old is not None:
            old.deleteLater()
        self.apply_theme()

    def set_lang(self, code: str) -> None:
        self.cfg.tour_lang = code
        self.save()
        self.build()

    def apply_theme(self) -> None:
        from .app import readable
        t = self.theme()
        w = self.widget()
        if w is None:
            return
        w.setStyleSheet(
            f"QWidget#helpInner {{ background:transparent; }}"
            f"QLabel {{ background:transparent; color:{t['text']}; }}"
            f"QLabel#title {{ font-size:15px; font-weight:800; }}"
            f"QLabel#sub, QLabel#a {{ color:{t['muted']}; font-size:11.5px; }}"
            f"QLabel#head {{ color:{readable(t['accent'], t)}; font-size:10.5px; font-weight:800; letter-spacing:1px; margin-top:6px; }}"
            f"QLabel#q {{ font-size:12px; font-weight:700; }}"
            f"QFrame#question {{ background:{t['card_bg']}; border:1px solid {t['border']}; border-radius:10px; }}"
            f"QPushButton {{ background:{t['btn_bg']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:9px;"
            f" padding:7px 10px; font-size:12px; text-align:left; }}"
            f"QPushButton:hover {{ background:{t['btn_hover']}; }}"
            f"QPushButton#tourMain {{ background:{t['accent']}; color:{t['on_accent']}; font-weight:800; border:none; }}"
            f"QPushButton#lang, QPushButton#langOn {{ padding:4px 9px; border-radius:12px; text-align:center; font-size:11.5px; }}"
            f"QPushButton#langOn {{ background:{t['accent']}; color:{t['on_accent']}; border:none; font-weight:700; }}")
