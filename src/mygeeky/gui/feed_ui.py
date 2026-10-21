"""🏠 Home (feed.py): the first page -- one scrolling feed of what myGeeKy already found for you, new things first and
then, after "You're all caught up", what you've seen. Every card says why it's there and leads to its page.

The cards are Neon: outlined and softly glowing in their kind's colour (a plain outline in light themes), each with
what makes it worth a look -- a ring counting down a deadline, a repo's stars, a dataset's size, a quiz question you
answer right there. A milestone sits on top ("3 new papers from your circle this week") when there is one.

It learns from what you do here: opening a card, ♡ (Home and your Model both learn), 🔖 Save (kept in Saved, and
teaches like ♡), ✕ (fewer like this, with Undo; your Model is left alone) and -- unless you switch it off -- how long
a card stayed on screen (a quick scroll past counts as "not for me"). Nothing here goes online: the feed is built from
what the other pages keep, off the screen's thread. The phone has the same page (components/feed-view.tsx).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from .. import feed
from .window_ui import qcolor

FIRST, MORE = 12, 12            # cards drawn at first, and each time you near the bottom (each card is ~20 widgets)
TICK_MS = 1000                  # how often time on screen is counted
VISIBLE = 0.6                   # a card counts as on screen when this much of it shows
GLOW = 4                        # px kept around each card for its glow
LIKED = "#ff6f91"


def _label(text: str, style: str, wrap: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.PlainText)                 # titles come from the internet: never rendered as HTML
    lbl.setWordWrap(wrap)
    lbl.setStyleSheet(style + " background:transparent;")
    return lbl


def _plain(text: str, name: str, wrap: bool = True) -> QLabel:
    """A label styled by its card's one stylesheet (one sheet per card, not per label: Qt keeps a style per sheet)."""
    lbl = QLabel(text)
    lbl.setObjectName(name)
    lbl.setTextFormat(Qt.PlainText)                 # titles come from the internet: never rendered as HTML
    lbl.setWordWrap(wrap)
    return lbl


def cards_sheet(t: dict[str, Any]) -> str:
    """One stylesheet for every card on Home, each kind picking its colour by the card's "kind" property: Qt keeps a
    style object per widget that has its own sheet, and ~20 labels a card each with a sheet cost megabytes."""
    card = "QFrame#feedCard"
    rules = [
        "QWidget#homeInner { background:transparent; }",
        f"{card} QLabel {{ background:transparent; color:{t['text']}; }}",
        f"{card} QLabel#kind {{ font-size:11px; font-weight:800; }}",
        f"{card} QLabel#title {{ font-size:13px; font-weight:700; }}",
        f'{card}[hero="yes"] QLabel#title {{ font-size:16px; font-weight:800; }}',
        f"{card} QLabel#sub {{ color:{t['muted']}; font-size:11.5px; }}",
        f"{card} QLabel#why {{ color:{t['muted']}; font-size:10.5px; font-style:italic; }}",
        f"{card} QLabel#chip {{ font-size:11px; font-weight:600; padding:1px 8px; border-radius:8px; }}",
        f"{card} QLabel#choice {{ background:{t['btn_bg']}; border:1px solid transparent; border-radius:9px; padding:6px 9px; font-size:12px; }}",
        f"{card} QPushButton {{ background:transparent; color:{t['muted']}; border:none; border-radius:7px; padding:3px 7px; font-size:13px; }}",
        f"{card} QPushButton:hover {{ background:{t['btn_hover']}; color:{t['text']}; }}",
        f"{card} QPushButton#more {{ color:{t['text']}; font-size:11.5px; }}",
        f"{card} QPushButton#liked {{ color:{LIKED}; }}",
    ]
    for kind in feed.KINDS:
        c = kind_color(kind, t)
        rules.append(f'{card}[kind="{kind}"] QLabel#kind {{ color:{c.name()}; }}')
        rules.append(f'{card}[kind="{kind}"] QLabel#chip {{ background:rgba({c.red()},{c.green()},{c.blue()},40); }}')
    return "\n".join(rules)


def kind_color(kind: str, theme: dict[str, Any]) -> QColor:
    """The kind's colour, darkened in light themes so its words stay readable."""
    from .app import readable
    return QColor(readable(feed.KIND_COLORS.get(kind) or theme.get("accent") or "#a78bfa", theme))


class Ring(QWidget):
    """A deadline's days left: the ring empties as it nears."""

    def __init__(self, days: int, color: QColor, theme: dict[str, Any]) -> None:
        super().__init__()
        self.days, self.color, self.theme = days, color, theme
        self.setFixedSize(52, 52)
        self.setAccessibleName("closes today" if days == 0 else f"{days} days left")

    def paintEvent(self, e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(4, 4, 44, 44)
        track = QColor(self.theme["text"])
        track.setAlpha(28)
        p.setPen(QPen(track, 4.5))
        p.drawEllipse(r)
        pen = QPen(self.color, 4.5)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        part = max(0.04, min(1.0, self.days / feed.RING_DAYS))
        p.drawArc(r, 90 * 16, int(-360 * 16 * part))
        f = QFont(self.font())
        f.setPixelSize(16 if self.days < 100 else 13)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(self.theme["text"]))
        p.drawText(QRectF(0, 9, 52, 22), Qt.AlignCenter, "!" if self.days == 0 else str(self.days))
        f.setPixelSize(9)
        f.setBold(False)
        p.setFont(f)
        p.setPen(qcolor(self.theme["muted"]))
        p.drawText(QRectF(0, 28, 52, 12), Qt.AlignCenter, "today" if self.days == 0 else "days")
        p.end()


class _Choice(QLabel):
    """One answer of a quiz card (a label, so long answers wrap)."""

    def __init__(self, text: str, on_pick: Callable[[], None]) -> None:
        super().__init__(text)
        self._on_pick = on_pick
        self.setTextFormat(Qt.PlainText)
        self.setWordWrap(True)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        self._on_pick()


class FeedCard(QFrame):
    def __init__(self, page: "HomePage", item: dict[str, Any], hero: bool = False, saved_at: str = "") -> None:
        super().__init__()
        self.page, self.item, self.card, self.hero = page, item, item["card"], hero
        self._answered = False
        self.setObjectName("feedCard")
        t = page.theme()
        self.color = kind_color(self.card["kind"], t)
        label, emoji, _ = feed.KINDS.get(self.card["kind"], ("", "•", 14))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12 + GLOW, 10 + GLOW, 12 + GLOW, 6 + GLOW)
        lay.setSpacing(5)
        self.setProperty("kind", self.card["kind"])            # styled by Home's one sheet (cards_sheet)
        self.setProperty("hero", "yes" if hero else "no")
        lay.addWidget(_plain(f"{emoji}  {label}", "kind"))
        title = _plain(self.card["title"], "title")
        title.setCursor(Qt.PointingHandCursor)
        title.mousePressEvent = lambda e: self.open()          # noqa: ARG005
        sub = _plain(self.card["sub"], "sub") if self.card.get("sub") else None
        days = feed.days_left(self.card)
        if days is not None:                                       # a deadline: the ring beside its title
            row = QHBoxLayout()
            row.setSpacing(10)
            row.addWidget(Ring(days, self.color, t), 0, Qt.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(title)
            if sub:
                col.addWidget(sub)
            row.addLayout(col, 1)
            lay.addLayout(row)
        else:
            lay.addWidget(title)
            if sub:
                lay.addWidget(sub)
        facts = self.card.get("facts") or {}
        if self.card["kind"] == "quiz" and facts.get("options"):
            self._quiz(lay, facts, t)
        chips = feed.facts_line(self.card)
        if chips:
            crow = QHBoxLayout()
            crow.setSpacing(5)
            for text in chips:
                crow.addWidget(_plain(text, "chip", wrap=False))
            crow.addStretch(1)
            lay.addLayout(crow)
        lay.addWidget(_plain(f"saved {saved_at}" if saved_at else item.get("why", ""), "why"))
        lay.addLayout(self._actions(t))

    # ---- parts
    def _quiz(self, lay: QVBoxLayout, facts: dict[str, Any], t: dict[str, Any]) -> None:
        self.choices: list[_Choice] = []
        for i, text in enumerate(facts["options"]):
            ch = _Choice(text, lambda i=i: self.answer(i))
            ch.setObjectName("choice")
            self.choices.append(ch)
            lay.addWidget(ch)
        self.verdict = _plain("", "sub")
        self.verdict.hide()
        lay.addWidget(self.verdict)

    def _style_choices(self, picked: int) -> None:
        """Only once answered do the two answers that matter get a style of their own."""
        t = self.page.theme()
        right = (self.card.get("facts") or {}).get("answer")
        for i, ch in enumerate(self.choices):
            if i == right:
                ch.setStyleSheet(f"QLabel {{ background:rgba(74,222,128,45); border:1px solid {t['good']}; }}")
            elif i == picked:
                ch.setStyleSheet(f"QLabel {{ background:rgba(248,113,113,40); border:1px solid {t['bad']}; }}")

    def answer(self, i: int) -> None:
        if self._answered:
            return
        self._answered = True
        facts = self.card.get("facts") or {}
        self._style_choices(i)
        self.verdict.setText(("✓ Right! " if i == facts.get("answer") else "✗ Not quite. ") + str(facts.get("why") or ""))
        self.verdict.show()
        self.page.learned(self.card, "open")                       # answering is reading it

    def _actions(self, t: dict[str, Any]) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(2)

        def button(text: str, tip: str, fn) -> QPushButton:
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(tip)
            b.setAccessibleName(tip)
            b.clicked.connect(fn)
            row.addWidget(b)
            return b

        self.like_btn = button("♡", "More like this (Home and your Model learn)", self.like)
        self.save_btn = button("🔖", "Save for later (in 🔖 Saved)", self.save)
        button("✕", "Fewer like this", self.dismiss)
        if self.card.get("url"):
            button("↗", "Open", self.open)
        row.addStretch(1)
        more = self.page.page_label(self.card.get("page", ""))
        if more:
            button(f"More in {more} ›", f"More in {more}", self.more).setObjectName("more")
        self._paint_marks()
        return row

    def _paint_marks(self) -> None:
        liked, saved = self.card["id"] in self.page.liked_ids, self.card["id"] in self.page.saved_ids()
        self.like_btn.setText("♥" if liked else "♡")
        self.like_btn.setObjectName("liked" if liked else "")
        self.like_btn.style().unpolish(self.like_btn)
        self.like_btn.style().polish(self.like_btn)
        self.save_btn.setText("🔖✓" if saved else "🔖")

    # ---- what you do
    def open(self) -> None:
        self.page.opened(self.item)

    def more(self) -> None:
        self.page.go(self.card.get("page", ""))

    def like(self) -> None:
        self.page.like(self.card)
        self._paint_marks()

    def save(self) -> None:
        self.page.toggle_save(self.card)
        self._paint_marks()

    def dismiss(self) -> None:
        self.page.dismiss(self)

    # ---- Neon
    def paintEvent(self, e) -> None:  # noqa: N802
        t = self.page.theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(GLOW, GLOW, -GLOW, -GLOW)
        dark = t.get("dark", True)
        if dark:                                                   # the glow: soft strokes fading outwards
            for width, alpha in ((8, 14), (5, 26), (3, 46)):
                g = QColor(self.color)
                g.setAlpha(alpha)
                p.setPen(QPen(g, width))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(r, 12, 12)
        bg = QColor(t.get("solid_bg") or "#1c1c2a")
        bg = bg.darker(118) if dark else bg.lighter(103)
        if self.hero:                                              # the first card: tinted with its colour
            c = self.color
            bg = QColor((bg.red() * 4 + c.red()) // 5, (bg.green() * 4 + c.green()) // 5, (bg.blue() * 4 + c.blue()) // 5)
        line = QColor(self.color)
        line.setAlpha(200 if dark else 170)
        p.setPen(QPen(line, 1.5))
        p.setBrush(bg)
        p.drawRoundedRect(r, 12, 12)
        p.end()


class _Clickable(QFrame):
    def __init__(self, on_click: Callable[[], None]) -> None:
        super().__init__()
        self._on_click = on_click
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        self._on_click()


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
        self.liked_ids: set[str] = set()
        self.pending_down: dict[str, dict[str, Any]] = {}       # ✕ waits until you leave, so Undo can take it back
        self.showing_saved = False
        self._saved_cache: list[dict[str, Any]] | None = None
        self.caught: QLabel | None = None
        self._building = False
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("homeInner")
        self.inner = inner
        self.lay = QVBoxLayout(inner)
        self.lay.setContentsMargins(0, 2, 4, 8)
        self.lay.setSpacing(4)
        self.setWidget(inner)
        self.viewport().setStyleSheet("background:transparent;")
        head = QHBoxLayout()
        self.title = _label("Home", "font-size:15px; font-weight:800;", wrap=False)
        self.status = _label("", "font-size:10.5px;", wrap=False)
        self.saved_btn = QPushButton("🔖")
        self.saved_btn.setCursor(Qt.PointingHandCursor)
        self.saved_btn.setToolTip("Saved for later")
        self.saved_btn.setAccessibleName("Saved for later")
        self.saved_btn.clicked.connect(self.toggle_saved_view)
        self.dwell_btn = QPushButton("")
        self.dwell_btn.setCursor(Qt.PointingHandCursor)
        self.dwell_btn.setToolTip("Home learns from how long a card stays on screen (only on your computers). "
                                  "Click to switch it off or on.")
        self.dwell_btn.clicked.connect(self.toggle_dwell)
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setToolTip("Refresh Home (from what the other pages already have: nothing is downloaded)")
        self.refresh_btn.setAccessibleName("Refresh Home")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(lambda: self.rebuild(force=True))
        head.addWidget(self.title)
        head.addWidget(self.status, 1)
        head.addWidget(self.saved_btn)
        head.addWidget(self.dwell_btn)
        head.addWidget(self.refresh_btn)
        self.head = QWidget()
        self.head.setLayout(head)
        self.lay.addWidget(self.head)
        self.cards_box = QVBoxLayout()
        self.cards_box.setSpacing(2)
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
        self.showing_saved = False
        self._render()
        self.verticalScrollBar().setValue(0)

    def _clear(self) -> None:
        self.caught = None
        while self.cards_box.count():
            w = self.cards_box.takeAt(0).widget()
            if w is not None:
                w.hide()
                w.deleteLater()
        self.drawn = 0

    def _render(self) -> None:
        self._clear()
        self.apply_theme()
        if self.showing_saved:
            self._draw_saved()
            return
        fresh = [x["card"] for x in self.items if not x["seen"]]
        mark = feed.milestone(fresh, date.today().isoformat())
        if mark:
            self.cards_box.addWidget(self._milestone(mark))
        self._draw(FIRST)
        if not self.items:
            self.cards_box.addWidget(_label("Nothing yet: the other pages fill Home as they update.",
                                            f"color:{self.theme()['muted']}; font-size:12px; padding:12px 4px;"))

    def _milestone(self, mark: dict[str, str]) -> QWidget:
        t = self.theme()
        box = _Clickable(lambda: self.go(mark.get("page", "")))
        box.setObjectName("milestone")
        box.setStyleSheet("QFrame#milestone { border-radius:12px; background:qlineargradient(x1:0,y1:0,x2:1,y2:0, "
                          "stop:0 rgba(255,111,216,70), stop:1 rgba(167,139,250,50)); }")
        row = QHBoxLayout(box)
        row.setContentsMargins(12, 9, 12, 9)
        row.setSpacing(10)
        row.addWidget(_label(mark["emoji"], "font-size:22px;", wrap=False), 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(_label(mark["title"], f"color:{t['text']}; font-size:13px; font-weight:800;"))
        col.addWidget(_label(mark["sub"] + " ›", f"color:{t['muted']}; font-size:11px;"))
        row.addLayout(col, 1)
        return box

    def _caught_text(self) -> str:
        return feed.caught_up(sum(1 for x in self.items if not x["seen"]), len(self.liked_ids), len(self.saved_ids()))

    def _draw(self, n: int) -> None:
        t = self.theme()
        for item in self.items[self.drawn:self.drawn + n]:
            if item["seen"] and (self.drawn == 0 or not self.items[self.drawn - 1]["seen"]):
                self.caught = _label(self._caught_text(), f"color:{t['text']}; font-size:12.5px; font-weight:800; padding:10px 2px 0;")
                self.cards_box.addWidget(self.caught)
                self.cards_box.addWidget(_label("Below: seen before, best first", f"color:{t['muted']}; font-size:11px; padding:0 2px 6px;"))
            self.cards_box.addWidget(FeedCard(self, item, hero=self.drawn == 0 and not item["seen"]))
            self.drawn += 1
        if self.drawn >= len(self.items) and self.items and self.caught is None:
            self.caught = _label(self._caught_text(), f"color:{t['text']}; font-size:12.5px; font-weight:800; padding:12px 2px;")
            self.cards_box.addWidget(self.caught)

    def _draw_saved(self) -> None:
        t = self.theme()
        saved = self._saved()
        self.cards_box.addWidget(_label(f"🔖 Saved for later · {len(saved)}" if saved else
                                        "🔖 Nothing saved yet: tap 🔖 on a card to keep it here.",
                                        f"color:{t['text']}; font-size:12.5px; font-weight:800; padding:4px 2px 6px;"))
        for x in saved:
            self.cards_box.addWidget(FeedCard(self, {"card": x["card"], "why": "", "seen": True}, saved_at=x.get("at", "")))

    def _near_bottom(self, value: int) -> None:
        bar = self.verticalScrollBar()
        if not self.showing_saved and self.drawn < len(self.items) and value >= bar.maximum() - 300:
            self._draw(MORE)

    # ---- saved
    def _saved(self) -> list[dict[str, Any]]:
        if self._saved_cache is None:
            self._saved_cache = feed.load()["saved"]
        return self._saved_cache

    def saved_ids(self) -> set[str]:
        return {x["card"]["id"] for x in self._saved()}

    def toggle_saved_view(self) -> None:
        self.showing_saved = not self.showing_saved
        self._render()
        self.verticalScrollBar().setValue(0)

    def toggle_save(self, card: dict[str, Any]) -> None:
        try:
            now = feed.toggle_save(card, date.today().isoformat())
        except Exception:
            return
        self._saved_cache = None
        if now and card["id"] not in self.liked_ids:
            self._teach_model(card)
        self.apply_theme()
        self.status.setText("  saved for later: 🔖 above" if now else "  taken out of Saved")
        if self.caught is not None:
            self.caught.setText(self._caught_text())

    # ---- what you do
    def opened(self, item: dict[str, Any]) -> None:
        card = item["card"]
        if card.get("url"):
            self.open_url(card["url"])
        self.learned(card, "open")
        try:                                              # what you open here teaches the Model too
            from .. import interests
            interests.record(feed.interest_kind(card), text=feed.interest_text(card), topics=card.get("terms") or [],
                             source="home", cfg=self.cfg)
        except Exception:
            pass

    def like(self, card: dict[str, Any]) -> None:
        """♡: Home learns the kind, and your Model the card's topics (once per card)."""
        if card["id"] in self.liked_ids:
            self.liked_ids.discard(card["id"])
            return
        self.liked_ids.add(card["id"])
        self.learned(card, "up")
        if card["id"] not in self.saved_ids():
            self._teach_model(card)
        self.status.setText("  thanks: Home and your Model learn from that")
        if self.caught is not None:
            self.caught.setText(self._caught_text())

    def _teach_model(self, card: dict[str, Any]) -> None:
        try:
            from .. import interests
            interests.record("like", text=feed.interest_text(card), topics=card.get("terms") or [],
                             source="home", cfg=self.cfg)
        except Exception:
            pass

    def dismiss(self, w: FeedCard) -> None:
        """✕: the card folds into "Fewer like this · Undo"; Home learns it when you leave, unless you undo."""
        t = self.theme()
        self.pending_down[w.card["id"]] = w.card
        strip = QFrame()
        strip.setObjectName("goneStrip")
        strip.setStyleSheet(f"QFrame#goneStrip {{ border:1px dashed {t['border']}; border-radius:10px; }}")
        row = QHBoxLayout(strip)
        row.setContentsMargins(10, 4, 6, 4)
        label = feed.KINDS.get(w.card["kind"], ("these", "", 0))[0]
        row.addWidget(_label(f"Fewer “{label}” cards from now on", f"color:{t['muted']}; font-size:11.5px;"), 1)
        undo = QPushButton("Undo")
        undo.setCursor(Qt.PointingHandCursor)
        undo.setStyleSheet(f"QPushButton {{ background:transparent; color:{t['accent']}; border:none; font-weight:700; font-size:11.5px; }}")
        row.addWidget(undo)
        self.cards_box.insertWidget(self.cards_box.indexOf(w), strip)
        w.hide()

        def back() -> None:
            self.pending_down.pop(w.card["id"], None)
            strip.hide()
            strip.deleteLater()
            w.show()
        undo.clicked.connect(back)
        w.undo_btn = undo

    def learned(self, card: dict[str, Any], what: str, dwell: float = 0.0) -> None:
        try:
            feed.record(card["kind"], card["id"], what, dwell, date.today().isoformat())
            if what == "open" and card.get("page"):
                from .. import wisep
                wisep.opened(card["page"])                   # what you enjoy here, WISEP keeps fresh first
        except Exception:
            pass

    _learn = learned

    # ---- time on screen
    def _tick(self) -> None:
        if self.showing_saved or not (self.isVisible() and self.visible()):
            return
        view = self.viewport().rect()
        for i in range(self.cards_box.count()):
            w = self.cards_box.itemAt(i).widget()
            if not isinstance(w, FeedCard) or w.card["id"] in self.told or w.isHidden():
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
        """Leaving Home (or refreshing it) isn't skipping what's on screen: only a card read long enough teaches. A ✕
        not undone is learned now."""
        for i in range(self.cards_box.count()):
            w = self.cards_box.itemAt(i).widget()
            if isinstance(w, FeedCard) and w.card["id"] in self.dwell and w.card["id"] not in self.told:
                if self.dwell[w.card["id"]] >= feed.READ_SECONDS:
                    self._tell(w.card)
                else:
                    self.dwell.pop(w.card["id"])
        for card in list(self.pending_down.values()):
            self.told.add(card["id"])
            self._learn(card, "down")
        self.pending_down.clear()

    def toggle_dwell(self) -> None:
        feed.set_dwell(not feed.load()["dwell"])
        self.apply_theme()

    def apply_theme(self) -> None:
        t = self.theme()
        sheet = cards_sheet(t)
        if self.inner.styleSheet() != sheet:
            changed = bool(self.inner.styleSheet())
            self.inner.setStyleSheet(sheet)
            if changed and self.built_at is not None:   # another theme: redraw the cards (their banner, ring, glow)
                self._render()
                return
        self.title.setStyleSheet(f"color:{t['text']}; font-size:15px; font-weight:800; background:transparent;")
        self.status.setStyleSheet(f"color:{t['muted']}; font-size:10.5px; background:transparent;")
        on = feed.load()["dwell"]
        self.dwell_btn.setText("⏱ learning" if on else "⏱ off")
        n = len(self._saved())
        self.saved_btn.setText(f"🔖 {n}" if n else "🔖")
        if self.showing_saved:
            self.status.setText("  saved for later")
        elif self.built_at is not None:
            new = sum(1 for x in self.items if not x["seen"])
            self.status.setText(f"  {new} new · updated {self.built_at:%H:%M}" if self.items
                                else "  nothing yet: the other pages fill this as they update")
        for b in (self.saved_btn, self.dwell_btn, self.refresh_btn):
            lit = b is self.saved_btn and self.showing_saved
            b.setStyleSheet(f"QPushButton {{ background:{t['accent'] if lit else t['section_btn']}; "
                            f"color:{t['on_accent'] if lit else t['text']}; border:none; "
                            "border-radius:8px; padding:4px 9px; font-size:11px; }")
