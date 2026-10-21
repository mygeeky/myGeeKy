"""🏠 Home (feed.py): the first page -- one scrolling feed of what myGeeKy already found for you, new things first and
then, after "You're all caught up", what you've seen. Every card says why it's there and leads to its page.

It learns from what you do here: opening a card, 👍/👎, and -- unless you switch it off -- how long a card stayed on
screen (a quick scroll past counts as "not for me"). Nothing here goes online: the feed is built from what the other
pages keep, off the screen's thread. The phone has the same page (components/feed-view.tsx).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from .. import feed

FIRST, MORE = 20, 15            # cards drawn at first, and each time you near the bottom
TICK_MS = 1000                  # how often time on screen is counted
VISIBLE = 0.6                   # a card counts as on screen when this much of it shows


def _label(text: str, style: str, wrap: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.PlainText)                 # titles come from the internet: never rendered as HTML
    lbl.setWordWrap(wrap)
    lbl.setStyleSheet(style + " background:transparent;")
    return lbl


class FeedCard(QFrame):
    def __init__(self, page: "HomePage", item: dict[str, Any]) -> None:
        super().__init__()
        self.page, self.item, self.card = page, item, item["card"]
        self.setObjectName("feedCard")
        t = page.theme()
        color = page.color_of(self.card)
        label, emoji, _ = feed.KINDS.get(self.card["kind"], ("", "•", 14))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)
        lay.addWidget(_label(f"{emoji}  {label}", f"color:{color}; font-size:10.5px; font-weight:700;"))
        title = _label(self.card["title"], f"color:{t['text']}; font-size:12.5px; font-weight:700;")
        title.setCursor(Qt.PointingHandCursor)
        title.mousePressEvent = lambda e: self.open()          # noqa: ARG005
        lay.addWidget(title)
        if self.card.get("sub"):
            lay.addWidget(_label(self.card["sub"], f"color:{t['muted']}; font-size:11px;"))
        lay.addWidget(_label(item["why"], f"color:{t['muted']}; font-size:10px; font-style:italic;"))
        row = QHBoxLayout()
        row.setSpacing(6)
        buttons = []
        if self.card.get("url"):
            buttons.append(("Open ↗", self.open))
        more = page.page_label(self.card.get("page", ""))
        if more:
            buttons.append((f"More in {more} ›", self.more))
        buttons += [("\U0001f44d", lambda: self.vote("up")), ("\U0001f44e", lambda: self.vote("down"))]
        for text, fn in buttons:
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            b.setStyleSheet(f"QPushButton {{ background:{t['btn_bg']}; color:{t['text']}; border:none; border-radius:7px; "
                            f"padding:3px 8px; font-size:10.5px; }} QPushButton:hover {{ background:{t['btn_hover']}; }}")
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.setStyleSheet(f"QFrame#feedCard {{ background:{t['card_bg']}; border-radius:10px; }}")

    def open(self) -> None:
        self.page.opened(self.item)

    def more(self) -> None:
        self.page.go(self.card.get("page", ""))

    def vote(self, how: str) -> None:
        self.page.voted(self.item, how)


class HomePage(QScrollArea):
    def __init__(self, cfg: Any, theme: Callable[[], dict[str, Any]], run_async: Callable[..., None],
                 open_url: Callable[[str], Any], go: Callable[[str], None], page_label: Callable[[str], str],
                 color_of: Callable[[dict[str, Any]], str], visible: Callable[[], bool]) -> None:
        super().__init__()
        self.cfg, self.theme, self.run_async, self.open_url = cfg, theme, run_async, open_url
        self.go, self.page_label, self.color_of, self.visible = go, page_label, color_of, visible
        self.items: list[dict[str, Any]] = []
        self.drawn = 0
        self.built_at: datetime | None = None
        self.dwell: dict[str, float] = {}
        self.told: set[str] = set()
        self._building = False
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        self.lay = QVBoxLayout(inner)
        self.lay.setContentsMargins(0, 2, 4, 8)
        self.lay.setSpacing(8)
        self.setWidget(inner)
        self.viewport().setStyleSheet("background:transparent;")
        head = QHBoxLayout()
        self.title = _label("Home", "font-size:15px; font-weight:800;", wrap=False)
        self.status = _label("", "font-size:10.5px;", wrap=False)
        self.dwell_btn = QPushButton("")
        self.dwell_btn.setCursor(Qt.PointingHandCursor)
        self.dwell_btn.setToolTip("Home learns from how long a card stays on screen (only on your computers). "
                                  "Click to switch it off or on.")
        self.dwell_btn.clicked.connect(self.toggle_dwell)
        self.refresh_btn = QPushButton("\u21bb")
        self.refresh_btn.setToolTip("Refresh Home (from what the other pages already have: nothing is downloaded)")
        self.refresh_btn.setAccessibleName("Refresh Home")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(lambda: self.rebuild(force=True))
        head.addWidget(self.title)
        head.addWidget(self.status, 1)
        head.addWidget(self.dwell_btn)
        head.addWidget(self.refresh_btn)
        self.head = QWidget()
        self.head.setLayout(head)
        self.lay.addWidget(self.head)
        self.cards_box = QVBoxLayout()
        self.cards_box.setSpacing(8)
        self.lay.addLayout(self.cards_box)
        self.lay.addStretch(1)
        self.verticalScrollBar().valueChanged.connect(self._near_bottom)
        self.timer = QTimer(self)
        self.timer.setInterval(TICK_MS)
        self.timer.timeout.connect(self._tick)
        self.apply_theme()

    # ---- building
    def shown(self) -> None:
        """Home came on screen: build it if it's new or more than ten minutes old; count time on screen."""
        if self.built_at is None or (datetime.now() - self.built_at).total_seconds() > 600:
            self.rebuild()
        self.timer.start()

    def hideEvent(self, e) -> None:  # noqa: N802
        super().hideEvent(e)
        self.timer.stop()
        self._flush()

    def rebuild(self, force: bool = False) -> None:
        if self._building:
            return
        self._building = True
        self.status.setText("updating…")
        self.run_async(lambda: feed.build(self.cfg, 90), self._got)

    def _got(self, items: Any) -> None:
        self._building = False
        self._flush()
        self.items = items if isinstance(items, list) else []
        self.built_at = datetime.now()
        self.dwell, self.told = {}, set()
        while self.cards_box.count():
            w = self.cards_box.takeAt(0).widget()
            if w is not None:
                w.hide()
                w.deleteLater()
        self.drawn = 0
        self._draw(FIRST)
        new = sum(1 for x in self.items if not x["seen"])
        self.status.setText(f"  {new} new · updated {self.built_at:%H:%M}" if self.items
                            else "  nothing yet: the other pages fill this as they update")
        self.verticalScrollBar().setValue(0)

    def _draw(self, n: int) -> None:
        t = self.theme()
        for item in self.items[self.drawn:self.drawn + n]:
            if item["seen"] and (self.drawn == 0 or not self.items[self.drawn - 1]["seen"]):
                self.cards_box.addWidget(_label("✓  You're all caught up · seen before, best first",
                                                f"color:{t['muted']}; font-size:11px; font-weight:700; padding:6px 2px;"))
            self.cards_box.addWidget(FeedCard(self, item))
            self.drawn += 1

    def _near_bottom(self, value: int) -> None:
        bar = self.verticalScrollBar()
        if self.drawn < len(self.items) and value >= bar.maximum() - 300:
            self._draw(MORE)

    # ---- what you do
    def opened(self, item: dict[str, Any]) -> None:
        card = item["card"]
        if card.get("url"):
            self.open_url(card["url"])
        self._learn(card, "open")
        try:                                              # what you open here teaches the Model too
            from .. import interests
            interests.record(feed.interest_kind(card), text=feed.interest_text(card), topics=card.get("terms") or [],
                             source="home", cfg=self.cfg)
        except Exception:
            pass

    def voted(self, item: dict[str, Any], how: str) -> None:
        self._learn(item["card"], how)
        self.status.setText("  thanks: Home learns from that" if how == "up" else "  fewer like that from now on")

    def _learn(self, card: dict[str, Any], what: str, dwell: float = 0.0) -> None:
        try:
            feed.record(card["kind"], card["id"], what, dwell, date.today().isoformat())
            if what == "open" and card.get("page"):
                from .. import wisep
                wisep.opened(card["page"])                   # what you enjoy here, WISEP keeps fresh first
        except Exception:
            pass

    # ---- time on screen
    def _tick(self) -> None:
        if not (self.isVisible() and self.visible()):
            return
        view = self.viewport().rect()
        for i in range(self.cards_box.count()):
            w = self.cards_box.itemAt(i).widget()
            if not isinstance(w, FeedCard) or w.card["id"] in self.told:
                continue
            top = w.mapTo(self.viewport(), w.rect().topLeft()).y()
            shown = max(0, min(top + w.height(), view.height()) - max(top, 0))
            cid = w.card["id"]
            if w.height() and shown / w.height() >= VISIBLE:     # first seen counts 0 s, so a quick pass is a skip
                self.dwell[cid] = self.dwell[cid] + TICK_MS / 1000 if cid in self.dwell else 0.0
            elif cid in self.dwell:                          # it was on screen and now isn't: what did it teach?
                self._tell(w.card)

    def _tell(self, card: dict[str, Any]) -> None:
        self.told.add(card["id"])
        self._learn(card, "view", self.dwell.pop(card["id"], 0.0))

    def _flush(self) -> None:
        """Leaving Home (or refreshing it) isn't skipping what's on screen: only a card read long enough teaches."""
        for i in range(self.cards_box.count()):
            w = self.cards_box.itemAt(i).widget()
            if isinstance(w, FeedCard) and w.card["id"] in self.dwell and w.card["id"] not in self.told:
                if self.dwell[w.card["id"]] >= feed.READ_SECONDS:
                    self._tell(w.card)
                else:
                    self.dwell.pop(w.card["id"])

    def toggle_dwell(self) -> None:
        feed.set_dwell(not feed.load()["dwell"])
        self.apply_theme()

    def apply_theme(self) -> None:
        t = self.theme()
        self.title.setStyleSheet(f"color:{t['text']}; font-size:15px; font-weight:800; background:transparent;")
        self.status.setStyleSheet(f"color:{t['muted']}; font-size:10.5px; background:transparent;")
        on = feed.load()["dwell"]
        self.dwell_btn.setText("⏱ learning" if on else "⏱ off")
        for b in (self.dwell_btn, self.refresh_btn):
            b.setStyleSheet(f"QPushButton {{ background:{t['section_btn']}; color:{t['text']}; border:none; "
                            "border-radius:8px; padding:4px 9px; font-size:11px; }")
