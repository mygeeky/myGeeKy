"""🎮 Games (Play with GeeKOc): the hub of every game, and the games themselves (GEMS, docs/GEMS.md).

The hub shows each game with its icon, its level, your best score and how far the next level is; a game opens in the
same page with "‹ All games" to come back. Every round goes through gems_store: the items come from gems.pick (your
field, something new, what's due again), and when it ends `finish` records it (points, stars, levels), feeds the
Model and the badges, and the result card says what you know and what you're learning. The phone has the same games
(components/games-*.tsx) on the same rules (lib/gems.ts).

Everything shown comes from the pack (data/games.json), so it is drawn as plain text.
"""
from __future__ import annotations

import math
import random
import time
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
                               QStackedWidget, QVBoxLayout, QWidget)

from .. import gems, gems_store
from . import app as logic

ASSETS = Path(__file__).parent / "assets"
BUILT = tuple(g["id"] for g in gems.GAMES)          # every game is playable (ComingNext stays for a new one)


def icon(game_id: str, size: int) -> QPixmap:
    name = "games_hub.png" if game_id == "hub" else f"game_{game_id}.png"
    pm = QPixmap(str(ASSETS / name))
    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation) if not pm.isNull() else pm


def _label(text: str, css: str, wrap: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.PlainText)
    lbl.setWordWrap(wrap)
    lbl.setStyleSheet(css + " background:transparent;")
    return lbl


def _button(text: str, t: dict[str, Any], primary: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    bg, fg = (t["accent"], t["on_accent"]) if primary else (t["btn_bg"], t["text"])
    b.setStyleSheet(f"QPushButton {{ background:{bg}; color:{fg}; border:none; border-radius:9px; padding:6px 12px; "
                    f"font-size:12px; font-weight:{700 if primary else 600}; }} QPushButton:hover {{ background:{t['btn_hover']}; "
                    f"color:{t['text']}; }} QPushButton:disabled {{ color:{t['muted']}; }}")
    return b


class _Bar(QWidget):
    """A thin progress bar in the theme's colours."""

    def __init__(self, theme: Callable[[], dict[str, Any]], value: float = 0.0, height: int = 5) -> None:
        super().__init__()
        self.theme, self.value = theme, value
        self.setFixedHeight(height)

    def set(self, value: float) -> None:
        self.value = max(0.0, min(1.0, value))
        self.update()

    def paintEvent(self, e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self.theme()
        r = self.height() / 2
        back = QColor(t["text"])
        back.setAlpha(40)
        p.setPen(Qt.NoPen)
        p.setBrush(back)
        p.drawRoundedRect(QRectF(self.rect()), r, r)
        if self.value > 0:
            p.setBrush(QColor(t["accent"]))
            p.drawRoundedRect(QRectF(0, 0, max(self.height(), self.width() * self.value), self.height()), r, r)
        p.end()


class GameCard(QFrame):
    clicked = Signal(str)

    def __init__(self, game: dict[str, Any], stats: dict[str, Any], theme: Callable[[], dict[str, Any]]) -> None:
        super().__init__()
        self.game = game
        t = theme()
        self.setObjectName("gameCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"#gameCard {{ background:{t['card_bg']}; border-radius:14px; }} "
                           f"#gameCard:hover {{ border:1.5px solid {t['accent']}; }}")
        self.setAccessibleName(game["title"])
        self.setToolTip(game["about"])
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 8, 10, 8)
        lay.setSpacing(9)
        pic = QLabel()
        pic.setPixmap(icon(game["id"], 52))
        pic.setFixedSize(52, 52)
        pic.setStyleSheet("background:transparent;")
        lay.addWidget(pic, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(3)
        col.addWidget(_label(game["title"], f"color:{t['text']}; font-size:12.5px; font-weight:800;"))
        if game["id"] in BUILT:
            line = f"Level {stats['level']}" + (f" · best {stats['best']}" if stats["best"] else " · new")
            col.addWidget(_label(line, f"color:{t['muted']}; font-size:10.5px;"))
            col.addWidget(_Bar(theme, stats["progress"], 4))
        else:
            col.addWidget(_label("Coming next", f"color:{logic.readable(t['warn'], t)}; font-size:10.5px; font-weight:700;"))
        col.addStretch(1)
        lay.addLayout(col, 1)

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self.game["id"])

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit(self.game["id"])


# ------------------------------------------------------------------------------------------------ the page
class GamesPage(QWidget):
    def __init__(self, cfg: Any, theme: Callable[[], dict[str, Any]], toast: Callable[[str], None]) -> None:
        super().__init__()
        self.cfg, self.theme, self.toast = cfg, theme, toast
        self.current: str | None = None
        self.setStyleSheet("background:transparent;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack)
        # the hub
        self.hub_scroll = QScrollArea()
        self.hub_scroll.setWidgetResizable(True)
        self.hub_scroll.setFrameShape(QFrame.NoFrame)
        self.hub_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.hub_scroll.setStyleSheet("QScrollArea { background:transparent; } QScrollArea > QWidget > QWidget { background:transparent; }")
        self.hub = QWidget()
        self.hub_lay = QVBoxLayout(self.hub)
        self.hub_lay.setContentsMargins(4, 4, 4, 8)
        self.hub_lay.setSpacing(10)
        self.hub_scroll.setWidget(self.hub)
        self.stack.addWidget(self.hub_scroll)
        # one game
        self.play = QWidget()
        pl = QVBoxLayout(self.play)
        pl.setContentsMargins(2, 2, 2, 2)
        pl.setSpacing(6)
        head = QHBoxLayout()
        self.back_btn = QPushButton("‹  All games")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.show_hub)
        self.game_icon = QLabel()
        self.game_icon.setFixedSize(26, 26)
        self.game_title = _label("", "", wrap=False)
        self.game_hud = _label("", "", wrap=False)
        head.addWidget(self.back_btn)
        head.addWidget(self.game_icon)
        head.addWidget(self.game_title, 1)
        head.addWidget(self.game_hud)
        pl.addLayout(head)
        self.game_box = QVBoxLayout()
        pl.addLayout(self.game_box, 1)
        self.stack.addWidget(self.play)
        self.game_widget: QWidget | None = None
        self.render_hub()

    # ---- the hub
    def render_hub(self) -> None:
        while self.hub_lay.count():
            item = self.hub_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()
            elif item.layout() is not None:
                _clear(item.layout())
        t = self.theme()
        s = gems_store.summary()
        top = QHBoxLayout()
        pic = QLabel()
        pic.setPixmap(icon("hub", 76))
        pic.setFixedSize(76, 76)
        pic.setStyleSheet("background:transparent;")
        top.addWidget(pic)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(_label("Play with GeeKOc", f"color:{t['title']}; font-size:17px; font-weight:800;"))
        col.addWidget(_label(f"Player level {s['player_level']} · {s['minutes']} min played · {s['xp']} XP",
                             f"color:{t['muted']}; font-size:11px;"))
        col.addWidget(_label("Short games from your own field. A mistake always says why, and your progress stays yours.",
                             f"color:{t['text']}; font-size:11px;"))
        top.addLayout(col, 1)
        box = QWidget()
        box.setLayout(top)
        self.hub_lay.addWidget(box)
        stats = {g["id"]: g for g in s["games"]}
        grid = QGridLayout()
        grid.setSpacing(8)
        cols = 2 if self.width() >= 360 else 1
        order = [g for g in gems.GAMES if g["id"] in BUILT] + [g for g in gems.GAMES if g["id"] not in BUILT]
        self.cards: list[GameCard] = []
        for i, g in enumerate(order):
            card = GameCard(g, stats[g["id"]], self.theme)
            card.clicked.connect(self.open)
            self.cards.append(card)
            grid.addWidget(card, i // cols, i % cols)
        gw = QWidget()
        gw.setLayout(grid)
        self.hub_lay.addWidget(gw)
        self.hub_lay.addStretch(1)
        self._cols = cols

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        if self.stack.currentWidget() is self.hub_scroll and (2 if self.width() >= 360 else 1) != getattr(self, "_cols", 0):
            self.render_hub()

    def apply_theme(self) -> None:
        self.render_hub()
        self._style_head()
        if self.game_widget is not None and hasattr(self.game_widget, "apply_theme"):
            self.game_widget.apply_theme()

    def shown(self) -> None:
        if self.stack.currentWidget() is self.hub_scroll:
            self.render_hub()

    def show_hub(self) -> None:
        self._drop_game()
        self.current = None
        self.render_hub()
        self.stack.setCurrentWidget(self.hub_scroll)

    def _style_head(self) -> None:
        t = self.theme()
        self.back_btn.setStyleSheet(f"QPushButton {{ background:{t['accent']}; color:{t['on_accent']}; border:none; "
                                    "border-radius:10px; padding:3px 10px; font-size:10.5px; font-weight:800; }")
        self.game_title.setStyleSheet(f"color:{t['text']}; font-size:13px; font-weight:800; background:transparent;")
        self.game_hud.setStyleSheet(f"color:{t['muted']}; font-size:11px; background:transparent;")

    # ---- one game
    def _drop_game(self) -> None:
        if self.game_widget is not None:
            if hasattr(self.game_widget, "stop"):
                self.game_widget.stop()
            self.game_box.removeWidget(self.game_widget)
            self.game_widget.hide()
            self.game_widget.deleteLater()
            self.game_widget = None

    def open(self, game_id: str) -> None:
        game = next(g for g in gems.GAMES if g["id"] == game_id)
        self._drop_game()
        self.current = game_id
        self._style_head()
        self.game_icon.setPixmap(icon(game_id, 26))
        self.game_title.setText(game["title"])
        self.game_hud.setText("")
        from .games_adventure import GAMES as ADVENTURES
        from .games_arcade import GAMES as ARCADE_GAMES
        from .games_cards import GAMES as CARD_GAMES
        maker = {"hunter": WordHunter, "terminal": TerminalTyping, **CARD_GAMES, **ARCADE_GAMES, **ADVENTURES}.get(game_id)
        w = maker(self.cfg, self.theme, self.game_hud.setText) if maker else ComingNext(game, self.theme)
        if hasattr(w, "finished"):
            w.finished.connect(lambda answers, seconds, bonus, g=game_id: self._finished(g, answers, seconds, bonus))
        self.game_widget = w
        self.game_box.addWidget(w)
        self.stack.setCurrentWidget(self.play)
        w.setFocus()

    def _finished(self, game_id: str, answers: list[dict[str, Any]], seconds: float, bonus: int) -> None:
        summary = gems_store.finish(self.cfg, game_id, answers, seconds, bonus)
        if self.game_widget is not None and hasattr(self.game_widget, "show_result"):
            self.game_widget.show_result(summary, lambda: self.open(game_id), self.show_hub)


def _clear(lay) -> None:
    while lay.count():
        item = lay.takeAt(0)
        if item.widget() is not None:
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())


class ResultCard(QFrame):
    """The end of a round: points, stars, best, level, and what you know and are learning now."""

    def __init__(self, summary: dict[str, Any], theme: Callable[[], dict[str, Any]], again: Callable[[], None],
                 hub: Callable[[], None]) -> None:
        super().__init__()
        t = theme()
        self.setObjectName("result")
        self.setStyleSheet(f"#result {{ background:{t['card_bg']}; border-radius:14px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        stars = "★" * summary["stars"] + "☆" * (3 - summary["stars"])
        lay.addWidget(_label(f"{stars}   {summary['points']} points", f"color:{logic.readable(t['warn'], t)}; font-size:18px; font-weight:800;"))
        lay.addWidget(_label(f"{summary['right']} of {summary['answered']} right"
                             + (" · a new best!" if summary["new_best"] else f" · best {summary['best']}"),
                             f"color:{t['text']}; font-size:12px;"))
        lvl = f"Level {summary['level']}" + ("  ·  level up!" if summary["level_up"] else "")
        if summary.get("next_level_xp"):
            lvl += f"  ·  {summary['next_level_xp'] - summary['xp']} XP to the next"
        lay.addWidget(_label(lvl, f"color:{t['text']}; font-size:12px; font-weight:700;"))
        if summary.get("player_level_up"):
            lay.addWidget(_label(f"You reached player level {summary['player_level']}!", f"color:{logic.readable(t['good'], t)}; font-size:12px; font-weight:700;"))
        if summary.get("knows"):
            lay.addWidget(_label("You know: " + ", ".join(summary["knows"][:4]), f"color:{logic.readable(t['good'], t)}; font-size:11px;"))
        if summary.get("learning"):
            lay.addWidget(_label("You're learning: " + ", ".join(summary["learning"][:4]), f"color:{t['muted']}; font-size:11px;"))
        row = QHBoxLayout()
        a = _button("Play again", t, primary=True)
        a.clicked.connect(again)
        b = _button("All games", t)
        b.clicked.connect(hub)
        row.addWidget(a)
        row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        a.setFocus()


class ComingNext(QWidget):
    def __init__(self, game: dict[str, Any], theme: Callable[[], dict[str, Any]]) -> None:
        super().__init__()
        t = theme()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 16, 8, 8)
        lay.setSpacing(10)
        pic = QLabel()
        pic.setPixmap(icon(game["id"], 140))
        pic.setAlignment(Qt.AlignCenter)
        pic.setStyleSheet("background:transparent;")
        lay.addWidget(pic)
        lay.addWidget(_label(game["about"], f"color:{t['text']}; font-size:13px; font-weight:700;"))
        lay.addWidget(_label("This game is coming next: its questions are ready, its screen is being built.",
                             f"color:{t['muted']}; font-size:11.5px;"))
        lay.addStretch(1)


# ------------------------------------------------------------------------------------------------ Terminal typing
def _norm(cmd: str) -> str:
    return " ".join(cmd.strip().split())


class TerminalTyping(QWidget):
    """A task and three commands: two do it, one doesn't. Pick a right one, then type it (a bonus for typing it right,
    more for typing it fast). The phone only picks."""

    finished = Signal(list, float, int)
    ROUND = 5

    def __init__(self, cfg: Any, theme: Callable[[], dict[str, Any]], hud: Callable[[str], None]) -> None:
        super().__init__()
        self.theme, self.hud = theme, hud
        self.items = gems_store.round_items(cfg, "terminal", "command", self.ROUND)
        self.answers: list[dict[str, Any]] = []
        self.bonus, self.i, self.t0 = 0, 0, time.monotonic()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(4, 6, 4, 4)
        self.lay.setSpacing(8)
        self.setFocusPolicy(Qt.StrongFocus)
        self.show_task()

    def stop(self) -> None:
        pass

    def show_task(self) -> None:
        _clear(self.lay)
        if self.i >= len(self.items):
            self.finished.emit(self.answers, time.monotonic() - self.t0, self.bonus)
            return
        t = self.theme()
        it = self.items[self.i]
        self.hud(f"{self.i + 1}/{len(self.items)} · bonus {self.bonus}")
        self.lay.addWidget(_label("$ " + it["task"], f"color:{t['text']}; font-size:13px; font-weight:800;"))
        self.lay.addWidget(_label("Two of these do it. Pick one, then type it.", f"color:{t['muted']}; font-size:11px;"))
        opts = random.sample(list(it["right"]) + [it["wrong"]["cmd"]], 3)
        self.buttons = []
        for cmd in opts:
            b = QPushButton(cmd)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(self._opt_css(t))
            b.clicked.connect(lambda _c=False, c=cmd: self.pick(c))
            self.lay.addWidget(b)
            self.buttons.append(b)
        self.why = _label("", f"color:{t['text']}; font-size:11.5px;")
        self.lay.addWidget(self.why)
        self.typing = QLineEdit()
        self.typing.setPlaceholderText("$ type the command you picked, then Enter")
        self.typing.setStyleSheet(f"QLineEdit {{ font-family:'JetBrains Mono','DejaVu Sans Mono',monospace; font-size:12.5px; "
                                  f"color:{t['text']}; background:{t['btn_bg']}; border:none; border-radius:8px; padding:6px 8px; }}")
        self.typing.hide()
        self.typing.returnPressed.connect(self.typed)
        self.lay.addWidget(self.typing)
        self.next_btn = _button("Next ›", t, primary=True)
        self.next_btn.hide()
        self.next_btn.clicked.connect(self.next)
        self.lay.addWidget(self.next_btn, 0, Qt.AlignLeft)
        self.lay.addStretch(1)
        self.picked_at = time.monotonic()
        self.chosen = ""

    def _opt_css(self, t: dict[str, Any], mark: str = "") -> str:
        border = {"right": t["good"], "wrong": t["bad"]}.get(mark, t["btn_bg"])
        return (f"QPushButton {{ text-align:left; font-family:'JetBrains Mono','DejaVu Sans Mono',monospace; font-size:12px; "
                f"color:{t['text']}; background:{t['btn_bg']}; border:2px solid {border}; border-radius:9px; padding:7px 9px; }}"
                f"QPushButton:hover {{ background:{t['btn_hover']}; }}")

    def pick(self, cmd: str) -> None:
        if self.chosen:
            return
        t, it = self.theme(), self.items[self.i]
        self.chosen = cmd
        right = cmd in it["right"]
        for b in self.buttons:
            b.setStyleSheet(self._opt_css(t, "right" if b.text() in it["right"] else "wrong" if b.text() == cmd else ""))
        self.answers.append({"id": it["id"], "right": right, "level": it["level"], "terms": it["terms"]})
        if right:
            self.why.setText("✅ Right. Now type it, for a bonus.")
            self.typing.show()
            self.typing.setFocus()
            self.next_btn.setText("Skip typing ›")
        else:
            self.why.setText(f"❌ {it['wrong']['why']}")
        self.next_btn.show()

    def typed(self) -> None:
        it = self.items[self.i]
        if _norm(self.typing.text()) == _norm(self.chosen):
            secs = time.monotonic() - self.picked_at
            gain = 5 * it["level"] + (5 if secs < 12 else 0)
            self.bonus += gain
            self.why.setText(f"⌨️ Typed it: +{gain} bonus" + (" (fast!)" if secs < 12 else ""))
            self.typing.setEnabled(False)
            self.next_btn.setText("Next ›")
            self.next_btn.setFocus()
        else:
            self.why.setText("Not quite the same: check the spaces and the letters, or skip.")

    def next(self) -> None:
        self.i += 1
        self.show_task()

    def show_result(self, summary: dict[str, Any], again: Callable[[], None], hub: Callable[[], None]) -> None:
        _clear(self.lay)
        self.lay.addWidget(ResultCard(summary, self.theme, again, hub))
        self.lay.addStretch(1)


# ------------------------------------------------------------------------------------------------ Word Hunter
QUIZ_OF = {"gwas": "gwas", "single-cell": "single-cell-rna-seq", "python": "python-data-analysis", "r": "r-data-analysis",
           "machine learning": "ml-in-practice", "git": "git-github-teamwork", "statistics": "stats-for-experiments",
           "visualization": "figures-for-papers", "workflow": "nextflow", "imaging": "image-analysis-fiji"}


class WordHunter(QWidget):
    """GeeKOc's ship under a belt of word asteroids: shoot the set's words, let the others drift past. Three waves; a
    question from your protocols between waves. Every word is an answer: shot or missed, let past or shot by mistake."""

    finished = Signal(list, float, int)
    W, H = 420.0, 400.0          # the field: 420 wide (words stay readable in a narrow panel), as tall as the panel

    def __init__(self, cfg: Any, theme: Callable[[], dict[str, Any]], hud: Callable[[str], None]) -> None:
        super().__init__()
        self.cfg, self.theme, self.hud = cfg, theme, hud
        self.setMinimumHeight(260)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        pack = gems_store.load_pack()
        self.sets = gems.items_of(pack, "wordset")
        self.waves = gems_store.round_items(cfg, "hunter", "wordset", 3)
        self.answers: list[dict[str, Any]] = []
        self.t0 = time.monotonic()
        self.wave, self.shields = -1, 3
        self.rocks: list[dict[str, Any]] = []
        self.shots: list[dict[str, Any]] = []
        self.bits: list[dict[str, Any]] = []
        self.queue: list[tuple[str, dict[str, Any]]] = []
        self.ship_x, self.target_x, self.keys = self.W / 2, None, set()
        self.spawn_in, self.cool, self.paused = 0.0, 0.0, True
        self.message, self.message_t = "", 0.0
        self.mood = "cheer"
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.step)
        self.last = time.monotonic()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.overlay: QWidget | None = None
        self.next_wave()

    # ---- the round
    def stop(self) -> None:
        self.timer.stop()

    def showEvent(self, e) -> None:  # noqa: N802
        self.last = time.monotonic()
        self.timer.start()

    def hideEvent(self, e) -> None:  # noqa: N802
        self.timer.stop()

    def _card(self, title: str, text: str, buttons: list[tuple[str, Callable[[], None]]]) -> None:
        t = self.theme()
        self._drop_card()
        box = QFrame(self)
        box.setObjectName("whCard")
        box.setStyleSheet(f"#whCard {{ background:{t['card_bg']}; border-radius:14px; }}")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.addWidget(_label(title, f"color:{t['text']}; font-size:14px; font-weight:800;"))
        if text:
            lay.addWidget(_label(text, f"color:{t['muted']}; font-size:11.5px;"))
        row = QHBoxLayout()
        for i, (label, fn) in enumerate(buttons):
            b = _button(label, t, primary=i == 0)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.overlay = box
        self._place_card()
        box.show()
        box.raise_()

    def _place_card(self) -> None:
        if self.overlay is not None:
            w = min(self.width() - 24, 360)
            self.overlay.setFixedWidth(max(200, w))
            self.overlay.adjustSize()
            self.overlay.move((self.width() - self.overlay.width()) // 2, max(8, (self.height() - self.overlay.height()) // 2))

    def _drop_card(self) -> None:
        if self.overlay is not None:
            self.overlay.hide()
            self.overlay.deleteLater()
            self.overlay = None

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        if self.width() > 0:                           # the field takes the panel's shape: W wide, as tall as it fits
            self.H = max(360.0, self.W * self.height() / self.width())
        self._place_card()

    def next_wave(self) -> None:
        self.wave += 1
        if self.wave >= len(self.waves) or self.shields <= 0:
            self.paused = True
            self.finished.emit(self.answers, time.monotonic() - self.t0, 0)
            return
        ws = self.waves[self.wave]
        near = [s for s in self.sets if s["id"] != ws["id"] and set(s["terms"]) & set(ws["terms"])]
        far = [s for s in self.sets if s["id"] != ws["id"] and s not in near]
        pool = far if self.wave == 0 else far + near if self.wave == 1 else (near or far)
        decoys = random.sample([(w, s) for s in pool for w in s["words"] if w not in ws["words"]],
                               k=min(4 + self.wave, sum(len(s["words"]) for s in pool)))
        mine = [(w, ws) for w in random.sample(ws["words"], k=min(6, len(ws["words"])))]
        self.queue = random.sample(mine + decoys, k=len(mine) + len(decoys))
        self.set = ws
        self.paused = True
        self._card(f"Wave {self.wave + 1}: shoot the {ws['name']}", "Let every other word drift past. A wrong shot costs a shield.",
                   [("Go", self._go)])

    def _go(self) -> None:
        self._drop_card()
        self.paused, self.spawn_in = False, 0.3
        self.setFocus()

    def _between(self) -> None:
        self.paused = True
        topic = next((QUIZ_OF[t] for t in self.set["terms"] if t in QUIZ_OF), None)
        qs = [q for q in _quiz() if q.get("protocol") == topic and q.get("kind") == "choice"] if topic else []
        if not qs:
            return self.next_wave()
        q = random.choice(qs)
        t = self.theme()
        self._drop_card()
        box = QFrame(self)
        box.setObjectName("whCard")
        box.setStyleSheet(f"#whCard {{ background:{t['card_bg']}; border-radius:14px; }}")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        lay.addWidget(_label(q["q"], f"color:{t['text']}; font-size:13px; font-weight:800;"))
        right_text = q["options"][0]
        why = _label("", f"color:{t['text']}; font-size:11px;")
        btns: list[QPushButton] = []

        def answer(choice: str) -> None:
            if why.text():
                return
            ok = choice == right_text
            for b in btns:
                b.setStyleSheet(b.styleSheet() + (f" QPushButton {{ border:2px solid {t['good']}; }}" if b.text() == right_text else
                                                  f" QPushButton {{ border:2px solid {t['bad']}; }}" if b.text() == choice else ""))
            self.answers.append({"id": q["id"], "right": ok, "level": 1, "terms": list(self.set["terms"])})
            why.setText(("✅ " if ok else "❌ ") + q.get("why", "") + f"\nSource: {q.get('source', {}).get('title', '')}")
            go = _button("Next wave ›", t, primary=True)
            go.clicked.connect(self.next_wave)
            lay.addWidget(go)
            go.setFocus()
            self._place_card()

        for opt in random.sample(q["options"], len(q["options"])):
            b = QPushButton(opt)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ text-align:left; color:{t['text']}; background:{t['btn_bg']}; border:none; "
                            "border-radius:9px; padding:6px 9px; font-size:11.5px; }")
            b.clicked.connect(lambda _c=False, o=opt: answer(o))
            lay.addWidget(b)
            btns.append(b)
        lay.addWidget(why)
        self.overlay = box
        self._place_card()
        box.show()
        box.raise_()

    def show_result(self, summary: dict[str, Any], again: Callable[[], None], hub: Callable[[], None]) -> None:
        self.timer.stop()
        self._drop_card()
        card = ResultCard(summary, self.theme, again, hub)
        card.setParent(self)
        self.overlay = card
        self._place_card()
        card.show()
        card.raise_()

    def _answer(self, word: str, wset: dict[str, Any], right: bool) -> None:
        self.answers.append({"id": f"{wset['id']}:{word}", "right": right, "level": wset["level"], "terms": list(wset["terms"])})

    def _say(self, text: str) -> None:
        self.message, self.message_t = text, 2.6

    # ---- input
    def keyPressEvent(self, e) -> None:  # noqa: N802
        self.keys.add(e.key())
        if e.key() == Qt.Key_Space:
            self.fire()

    def keyReleaseEvent(self, e) -> None:  # noqa: N802
        self.keys.discard(e.key())

    def _to_world(self, pos) -> QPointF:
        k = self.width() / self.W
        return QPointF(pos.x() / k, pos.y() / k)

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        self.target_x = self._to_world(e.position()).x()

    def mousePressEvent(self, e) -> None:  # noqa: N802
        p = self._to_world(e.position())
        self.setFocus()
        self.fire(p.x(), p.y())

    def fire(self, tx: float | None = None, ty: float | None = None) -> None:
        if self.paused or self.cool > 0:
            return
        self.cool = 0.22
        dx, dy = 0.0, -1.0
        if tx is not None:
            dx, dy = tx - self.ship_x, ty - (self.H - 70)
            n = max(1e-6, (dx * dx + dy * dy) ** 0.5)
            dx, dy = dx / n, min(-0.15, dy / n)
        self.shots.append({"x": self.ship_x, "y": self.H - 74, "vx": dx * 520, "vy": dy * 520, "life": 1.4})

    # ---- the world
    def step(self) -> None:
        now = time.monotonic()
        dt = min(0.05, now - self.last)
        self.last = now
        self.message_t -= dt
        if not self.paused:
            left = Qt.Key_Left in self.keys or Qt.Key_A in self.keys
            right = Qt.Key_Right in self.keys or Qt.Key_D in self.keys
            if left or right:
                self.target_x = None
                self.ship_x += (right - left) * 330 * dt
            elif self.target_x is not None:
                self.ship_x += max(-380 * dt, min(380 * dt, (self.target_x - self.ship_x) * 6 * dt))
            self.ship_x = max(40, min(self.W - 40, self.ship_x))
            self.cool -= dt
            self.spawn_in -= dt
            if self.queue and self.spawn_in <= 0:
                word, wset = self.queue.pop()
                r = max(26.0, len(word) * 4.4 + 14)
                speed = 26 + self.wave * 11
                self.rocks.append({"x": random.uniform(r, self.W - r), "y": -r, "vx": random.uniform(-18, 18),
                                   "vy": random.uniform(speed, speed + 20), "r": r, "word": word, "set": wset,
                                   "good": wset is self.set, "rot": random.uniform(0, 6), "vr": random.uniform(-0.5, 0.5),
                                   "k": [random.uniform(0.82, 1.08) for _ in range(11)]})
                self.spawn_in = max(0.75, 1.4 - self.wave * 0.25)
            for r in self.rocks:
                r["x"] += r["vx"] * dt
                r["y"] += r["vy"] * dt
                r["rot"] += r["vr"] * dt
                if r["x"] < r["r"] or r["x"] > self.W - r["r"]:
                    r["vx"] *= -1
            for s in self.shots:
                s["x"] += s["vx"] * dt
                s["y"] += s["vy"] * dt
                s["life"] -= dt
            for s in self.shots:
                for r in self.rocks:
                    if r.get("dead") or s["life"] <= 0:
                        continue
                    if (s["x"] - r["x"]) ** 2 + (s["y"] - r["y"]) ** 2 < r["r"] ** 2:
                        r["dead"], s["life"] = True, 0
                        self._boom(r["x"], r["y"], r["good"])
                        if r["good"]:
                            self._answer(r["word"], r["set"], True)
                            self.mood = "cheer"
                        else:
                            self.shields -= 1
                            self._answer(r["word"], r["set"], False)
                            self.mood = "think"
                            self._say(f"{r['word']} is {r['set']['what']}, not one of the {self.set['name']}.")
            for r in self.rocks:
                if not r.get("dead") and r["y"] - r["r"] > self.H:
                    r["dead"] = True
                    if r["good"]:
                        self._answer(r["word"], r["set"], False)
                        self._say(f"Missed: {r['word']} is one of the {self.set['name']}.")
                    else:
                        self._answer(r["word"], r["set"], True)            # rightly let past
            self.rocks = [r for r in self.rocks if not r.get("dead")]
            self.shots = [s for s in self.shots if s["life"] > 0 and s["y"] > -20]
            if self.shields <= 0:
                self.paused = True
                QTimer.singleShot(500, self, lambda: self.finished.emit(self.answers, time.monotonic() - self.t0, 0))
            elif not self.queue and not self.rocks:
                self.paused = True
                QTimer.singleShot(400, self, self._between)
        for b in self.bits:
            b["x"] += b["vx"] * dt
            b["y"] += b["vy"] * dt
            b["life"] -= dt
        self.bits = [b for b in self.bits if b["life"] > 0]
        self.hud(f"Wave {max(1, self.wave + 1)}/{len(self.waves)} · {'♥' * max(0, self.shields)}{'♡' * (3 - max(0, self.shields))}")
        still = self.paused and self.message_t <= 0 and not self.bits     # a card is up: nothing moves
        if still and getattr(self, "_still", False):
            return                                          # drawn once already: no need to repaint 60 times a second
        self._still = still
        self.update()

    def _boom(self, x: float, y: float, good: bool) -> None:
        for _ in range(14):
            self.bits.append({"x": x, "y": y, "vx": random.uniform(-150, 150), "vy": random.uniform(-150, 150),
                              "life": random.uniform(0.4, 0.9), "good": good})

    def paintEvent(self, e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self.theme()
        p.fillRect(self.rect(), QColor("#070712"))
        k = self.width() / self.W
        p.scale(k, k)
        rng = random.Random(7)
        p.setPen(Qt.NoPen)
        for _ in range(70):
            c = QColor(220, 220, 255, rng.randint(60, 220))
            p.setBrush(c)
            p.drawRect(QRectF(rng.uniform(0, self.W), rng.uniform(0, self.H), 1.6, 1.6))
        if getattr(self, "set", None) is not None:
            p.fillRect(QRectF(0, 0, self.W, 26), QColor(139, 69, 224, 70))
            f = QFont(self.font())
            f.setPixelSize(14)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("#f0f0f5"))
            p.drawText(QRectF(0, 0, self.W, 26), Qt.AlignCenter, f"Shoot: {self.set['name']}")
        f = QFont(self.font())
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        for r in self.rocks:
            p.save()
            p.translate(r["x"], r["y"])
            p.rotate(r["rot"] * 57.3)
            path = QPainterPath()
            for i, kk in enumerate(r["k"]):
                a = i / len(r["k"]) * 6.2832
                pt = QPointF(math.cos(a) * r["r"] * kk, math.sin(a) * r["r"] * 0.8 * kk)
                path.moveTo(pt) if i == 0 else path.lineTo(pt)
            path.closeSubpath()
            p.setBrush(QColor("#3b3550"))
            p.setPen(QPen(QColor("#6b6290"), 2))
            p.drawPath(path)
            p.restore()
            p.setPen(QColor("#ffffff"))
            p.drawText(QRectF(r["x"] - r["r"] - 20, r["y"] - 10, 2 * r["r"] + 40, 20), Qt.AlignCenter, r["word"])
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffc457"))
        for s in self.shots:
            p.drawEllipse(QPointF(s["x"], s["y"]), 3.5, 3.5)
        for b in self.bits:
            c = QColor("#34d399" if b["good"] else "#f87171")
            c.setAlphaF(max(0.0, min(1.0, b["life"])))
            p.setBrush(c)
            p.drawRect(QRectF(b["x"], b["y"], 3, 3))
        # the ship, GeeKOc in the cockpit
        x, y = self.ship_x, self.H - 46
        p.setBrush(QColor(127, 216, 255, 60))
        p.drawChord(QRectF(x - 27, y - 46, 54, 54), 0, 180 * 16)
        p.setBrush(QColor("#7fd8ff"))
        p.drawEllipse(QRectF(x - 46, y - 2, 92, 24))
        p.setBrush(QColor("#2b1053"))
        for i in range(-2, 3):
            p.drawEllipse(QPointF(x + i * 17, y + 10), 2.8, 2.8)
        try:
            from .tour_ui import _frames
            frames = _frames("cheer" if self.mood == "cheer" else "think")
            fr = frames[int(time.monotonic() * 8) % len(frames)]
            fr.render(p, QRectF(x - 40, y - 64, 80, 80))
        except Exception:
            pass
        if self.message_t > 0 and self.message:
            f.setPixelSize(12)
            p.setFont(f)
            box = QRectF(20, self.H - 118, self.W - 40, 24)
            p.setBrush(QColor(28, 28, 44, 230))
            p.drawRoundedRect(box, 10, 10)
            p.setPen(QColor("#f0f0f5"))
            p.drawText(box, Qt.AlignCenter, self.message)
        p.end()
        del t


def _quiz() -> list[dict[str, Any]]:
    try:
        from .. import quiz
        return list(quiz.bank().get("questions", []))
    except Exception:
        import json
        path = Path(__file__).resolve().parents[1] / "data" / "questions.json"
        return list(json.loads(path.read_text(encoding="utf-8")).get("questions", []))
