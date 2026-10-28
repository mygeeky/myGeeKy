"""The card games of Play with GeeKOc (GEMS, docs/GEMS.md): one engine, six faces.

Every one is a round of questions: a prompt drawn the game's own way, a few answers, an explanation that always says
why, then the next. The engine (ChoiceGame) keeps the answers for gems_store.finish; each game says what a question
looks like:

- Real tool or made up? / Gene or Pokémon?: a name on a big card, two answers;
- Which came first?: two names side by side; the older one is right;
- Reviewer 2 attacks: the grumpy anglerfish's comment, the right reply among wrong ones, and the paper's chance of
  acceptance climbing or falling;
- Debug reef: a short snippet; click the line with the bug before GeeKOc's bubble reaches the top;
- Fix the figure: a flawed chart (drawn here, eight kinds) and its flaw among wrong ones.

The phone has the same games (components/games-cards.tsx). Everything shown comes from the pack: plain text only.
"""
from __future__ import annotations

import math
import random
import time
from typing import Any, Callable

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from .. import gems, gems_store
from . import app as logic


def _label(text: str, css: str, wrap: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.PlainText)
    lbl.setWordWrap(wrap)
    lbl.setStyleSheet(css + " background:transparent;")
    return lbl


def _clear(lay) -> None:
    while lay.count():
        item = lay.takeAt(0)
        if item.widget() is not None:
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())


class WrapButton(QPushButton):
    """A button whose text wraps (a push button never does, and a long answer pushed the panel wider)."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.label = QLabel(text, self)
        self.label.setTextFormat(Qt.PlainText)
        self.label.setWordWrap(True)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(11, 8, 11, 8)
        lay.addWidget(self.label)
        sp = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def text(self) -> str:  # noqa: D401
        return self.label.text()

    def set_ink(self, color: str, size: str = "12px") -> None:
        self.label.setStyleSheet(f"color:{color}; font-size:{size}; background:transparent;")

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, w: int) -> int:  # noqa: N802
        return self.label.heightForWidth(max(40, w - 22)) + 18

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(200, self.heightForWidth(max(200, self.width())))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(60, self.heightForWidth(max(60, self.width())))


class ChoiceGame(QWidget):
    """A round of questions. A subclass sets GAME, KIND and ROUND and says how a question looks (`prompt`), what its
    answers are and which is right (`choices`), and what it teaches (`why`)."""

    finished = Signal(list, float, int)
    GAME, KIND, ROUND = "", "", 8
    HINT = ""
    TIMED = 0.0                                   # seconds per question (Debug reef's bubble); 0: no clock

    def __init__(self, cfg: Any, theme: Callable[[], dict[str, Any]], hud: Callable[[str], None]) -> None:
        super().__init__()
        self.cfg, self.theme, self.hud = cfg, theme, hud
        self.items = self.load(cfg)
        self.answers: list[dict[str, Any]] = []
        self.i, self.t0, self.bonus = 0, time.monotonic(), 0
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(4, 6, 4, 4)
        self.lay.setSpacing(8)
        self.setFocusPolicy(Qt.StrongFocus)
        self.clock = QTimer(self)
        self.clock.setInterval(100)
        self.clock.timeout.connect(self._tick)
        self.show_question()

    # ---- what a game says
    def load(self, cfg: Any) -> list[dict[str, Any]]:
        return gems_store.round_items(cfg, self.GAME, self.KIND, self.ROUND)

    def prompt(self, it: dict[str, Any]) -> QWidget:
        raise NotImplementedError

    def choices(self, it: dict[str, Any]) -> tuple[list[str], int]:
        raise NotImplementedError

    def why(self, it: dict[str, Any], right: bool) -> str:
        return ""

    def answered(self, it: dict[str, Any], right: bool) -> list[dict[str, Any]]:
        """The answers this question gives GEMS (usually one; Which came first? gives both of its items)."""
        return [{"id": it["id"], "right": right, "level": it["level"], "terms": it["terms"]}]

    def after(self, right: bool) -> None:
        """Something the game does once a question is answered (Reviewer 2's meter)."""

    # ---- the engine
    def stop(self) -> None:
        self.clock.stop()

    def show_question(self) -> None:
        _clear(self.lay)
        self.clock.stop()
        if self.i >= len(self.items):
            self.finished.emit(self.answers, time.monotonic() - self.t0, self.bonus)
            return
        t = self.theme()
        it = self.items[self.i]
        self.hud(f"{self.i + 1}/{len(self.items)} · {sum(1 for a in self.answers if a['right'])} right")
        if self.HINT:
            self.lay.addWidget(_label(self.HINT, f"color:{t['muted']}; font-size:11px;"))
        self.lay.addWidget(self.prompt(it))
        options, self.right_index = self.choices(it)
        self.buttons: list[QPushButton] = []
        self.done = False
        row = QHBoxLayout() if len(options) == 2 and max(len(o) for o in options) < 24 else None
        box = QVBoxLayout()
        box.setSpacing(6)
        for k, text in enumerate(options):
            b = QPushButton(text) if row is not None else WrapButton(text)
            if isinstance(b, WrapButton):
                b.set_ink(t["text"])
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(self._css(t, "", big=row is not None))
            b.clicked.connect(lambda _c=False, kk=k: self.pick(kk))
            (row or box).addWidget(b)
            self.buttons.append(b)
        self.lay.addLayout(row or box)
        self.note = _label("", f"color:{t['text']}; font-size:11.5px;")
        self.lay.addWidget(self.note)
        self.next_btn = QPushButton("Next ›")
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.setStyleSheet(f"QPushButton {{ background:{t['accent']}; color:{t['on_accent']}; border:none; "
                                    "border-radius:9px; padding:6px 14px; font-size:12px; font-weight:700; }")
        self.next_btn.clicked.connect(self.next)
        self.next_btn.hide()
        self.lay.addWidget(self.next_btn, 0, Qt.AlignLeft)
        self.lay.addStretch(1)
        if self.TIMED:
            self.left = self.TIMED
            self.clock.start()

    def _css(self, t: dict[str, Any], mark: str, big: bool = False) -> str:
        border = {"right": t["good"], "wrong": t["bad"]}.get(mark, t["btn_bg"])
        size = "14px; font-weight:800" if big else "12px"
        return (f"QPushButton {{ text-align:{'center' if big else 'left'}; color:{t['text']}; background:{t['btn_bg']}; "
                f"border:2px solid {border}; border-radius:10px; padding:{'12px' if big else '0px'}; font-size:{size}; }}"
                f"QPushButton:hover {{ background:{t['btn_hover']}; }}")

    def _tick(self) -> None:
        self.left -= 0.1
        self.update()
        if self.left <= 0 and not self.done:
            self.pick(-1)

    def pick(self, k: int) -> None:
        if self.done:
            return
        self.done = True
        self.clock.stop()
        t, it = self.theme(), self.items[self.i]
        right = k == self.right_index
        big = len(self.buttons) == 2 and self.buttons[0].styleSheet().count("14px") > 0
        for j, b in enumerate(self.buttons):
            b.setStyleSheet(self._css(t, "right" if j == self.right_index else "wrong" if j == k else "", big))
        self.answers.extend(self.answered(it, right))
        lead = "✅ Right. " if right else ("⏱ Time's up. " if k < 0 else "❌ Not quite. ")
        self.note.setText(lead + self.why(it, right))
        self.after(right)
        self.next_btn.setText("Next ›" if self.i + 1 < len(self.items) else "See how you did")
        self.next_btn.show()
        self.next_btn.setFocus()

    def keyPressEvent(self, e) -> None:  # noqa: N802
        keys = {Qt.Key_1: 0, Qt.Key_2: 1, Qt.Key_3: 2, Qt.Key_4: 3, Qt.Key_Left: 0, Qt.Key_Right: 1}
        if not self.done and e.key() in keys and keys[e.key()] < len(self.buttons):
            self.pick(keys[e.key()])
        elif self.done and e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.next()
        else:
            super().keyPressEvent(e)

    def next(self) -> None:
        self.i += 1
        self.show_question()

    def show_result(self, summary: dict[str, Any], again: Callable[[], None], hub: Callable[[], None]) -> None:
        from .games_ui import ResultCard
        _clear(self.lay)
        self.lay.addWidget(ResultCard(summary, self.theme, again, hub))
        self.lay.addStretch(1)


class NameCard(QFrame):
    """A big card with one name on it (the swipe games)."""

    def __init__(self, text: str, theme: Callable[[], dict[str, Any]], sub: str = "") -> None:
        super().__init__()
        t = theme()
        self.setObjectName("nameCard")
        self.setMinimumHeight(130)
        self.setStyleSheet(f"#nameCard {{ background:{t['card_bg']}; border:2px solid {t['accent']}; border-radius:18px; }}")
        lay = QVBoxLayout(self)
        lay.addStretch(1)
        name = _label(text, f"color:{t['text']}; font-size:22px; font-weight:800;")
        name.setAlignment(Qt.AlignCenter)
        lay.addWidget(name)
        if sub:
            s = _label(sub, f"color:{t['muted']}; font-size:11px;")
            s.setAlignment(Qt.AlignCenter)
            lay.addWidget(s)
        lay.addStretch(1)


# ------------------------------------------------------------------------------------------------ the games
class RealOrFake(ChoiceGame):
    GAME, KIND, ROUND = "realfake", "realfake", 10
    HINT = "Real tool, or made up? (keys: ← real, → made up)"

    def prompt(self, it: dict[str, Any]) -> QWidget:
        return NameCard(it["name"], self.theme)

    def choices(self, it: dict[str, Any]) -> tuple[list[str], int]:
        return ["Real tool", "Made up"], 0 if it["real"] else 1

    def why(self, it: dict[str, Any], right: bool) -> str:
        return it["fact"]


class GeneOrMon(ChoiceGame):
    GAME, KIND, ROUND = "genemon", "genemon", 10
    HINT = "Gene, or Pokémon? (keys: ← gene, → Pokémon)"

    def prompt(self, it: dict[str, Any]) -> QWidget:
        return NameCard(it["name"], self.theme)

    def choices(self, it: dict[str, Any]) -> tuple[list[str], int]:
        return ["Gene", "Pokémon"], 0 if it["answer"] == "gene" else 1

    def why(self, it: dict[str, Any], right: bool) -> str:
        return it["fact"]


class WhichFirst(ChoiceGame):
    """Pairs of year cards with different years; the older one is the right answer."""

    GAME, KIND, ROUND = "first", "year", 6
    HINT = "Which came first?"

    def load(self, cfg: Any) -> list[dict[str, Any]]:
        pool = gems_store.round_items(cfg, self.GAME, self.KIND, self.ROUND * 2)
        pairs, rest = [], list(pool)
        while len(rest) >= 2 and len(pairs) < self.ROUND:
            a = rest.pop(0)
            b = next((x for x in rest if x["year"] != a["year"]), None)
            if b is None:
                break
            rest.remove(b)
            pairs.append({"id": f"{a['id']}+{b['id']}", "a": a, "b": b, "level": max(a["level"], b["level"]),
                          "terms": sorted(set(a["terms"]) | set(b["terms"]))})
        return pairs

    def prompt(self, it: dict[str, Any]) -> QWidget:
        t = self.theme()
        return _label(f"{it['a']['name']}   or   {it['b']['name']}?", f"color:{t['text']}; font-size:15px; font-weight:800;")

    def choices(self, it: dict[str, Any]) -> tuple[list[str], int]:
        return [it["a"]["name"], it["b"]["name"]], 0 if it["a"]["year"] < it["b"]["year"] else 1

    def why(self, it: dict[str, Any], right: bool) -> str:
        a, b = it["a"], it["b"]
        return f"{a['name']}: {a['year']} ({a['event']}). {b['name']}: {b['year']} ({b['event']})."

    def answered(self, it: dict[str, Any], right: bool) -> list[dict[str, Any]]:
        return [{"id": x["id"], "right": right, "level": x["level"], "terms": x["terms"]} for x in (it["a"], it["b"])]


class Angler(QWidget):
    """Reviewer 2: a grumpy anglerfish, its lantern green when pleased, and the paper's chance of acceptance."""

    def __init__(self, theme: Callable[[], dict[str, Any]], chance: int, mood: int, comment: str) -> None:
        super().__init__()
        self.theme, self.chance, self.mood, self.comment = theme, chance, mood, comment
        self.setMinimumHeight(150)

    def paintEvent(self, e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self.theme()
        w, h = self.width(), self.height()
        fx, fy = 62, h / 2 + 8
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#4b5a7a"))
        p.drawEllipse(QPointF(fx, fy), 48, 36)
        tail = QPainterPath(QPointF(fx + 42, fy))
        tail.lineTo(fx + 70, fy - 22)
        tail.lineTo(fx + 70, fy + 22)
        tail.closeSubpath()
        p.drawPath(tail)
        p.setPen(QPen(QColor("#4b5a7a"), 3))
        p.drawLine(QPointF(fx - 14, fy - 32), QPointF(fx - 34, fy - 56))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#34d399" if self.mood > 0 else "#f87171" if self.mood < 0 else "#ffc457"))
        p.drawEllipse(QPointF(fx - 36, fy - 58), 7, 7)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(fx - 18, fy - 8), 8, 8)
        p.setBrush(QColor("#111111"))
        p.drawEllipse(QPointF(fx - 20, fy - 7), 3.5, 3.5)
        p.setPen(QPen(QColor("#111111"), 3))
        p.drawLine(QPointF(fx - 30, fy - 22), QPointF(fx - 8, fy - 17 if self.mood <= 0 else fy - 24))
        p.setPen(QPen(QColor("#1a1428"), 2.5))
        p.drawLine(QPointF(fx - 40, fy + 14), QPointF(fx - 12, fy + (10 if self.mood > 0 else 18)))
        # the comment, in a bubble beside the fish
        bub = QRectF(fx + 82, 10, w - fx - 92, h - 52)
        p.setPen(QPen(QColor(t["accent"]), 1.5))
        p.setBrush(QColor(t["card_bg"]) if not t["card_bg"].startswith("rgba") else QColor(t["solid_bg"]))
        p.drawRoundedRect(bub, 12, 12)
        f = QFont(self.font())
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(t["text"]))
        p.drawText(bub.adjusted(10, 6, -10, -6), Qt.AlignVCenter | Qt.TextWordWrap, f"“{self.comment}”")
        # the chance of acceptance
        bar = QRectF(fx + 82, h - 30, w - fx - 92, 10)
        p.setPen(Qt.NoPen)
        back = QColor(t["text"])
        back.setAlpha(40)
        p.setBrush(back)
        p.drawRoundedRect(bar, 5, 5)
        p.setBrush(QColor("#34d399" if self.chance >= 50 else "#f87171"))
        p.drawRoundedRect(QRectF(bar.x(), bar.y(), bar.width() * self.chance / 100, bar.height()), 5, 5)
        f.setPixelSize(10)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(t["muted"]) if not t["muted"].startswith("rgba") else QColor(t["text"]))
        p.drawText(QRectF(bar.x(), bar.bottom() + 2, bar.width(), 14), Qt.AlignLeft, f"Chance of acceptance: {self.chance}%")
        p.end()


class Reviewer2(ChoiceGame):
    GAME, KIND, ROUND = "reviewer", "review", 5
    HINT = "Reviewer 2 has read your paper. Reply well."

    def __init__(self, *a: Any) -> None:
        self.chance, self.mood = 50, 0
        super().__init__(*a)

    def prompt(self, it: dict[str, Any]) -> QWidget:
        self.fish = Angler(self.theme, self.chance, 0, it["comment"])
        return self.fish

    def choices(self, it: dict[str, Any]) -> tuple[list[str], int]:
        opts = random.sample([it["right"]] + list(it["wrong"]), len(it["wrong"]) + 1)
        return opts, opts.index(it["right"])

    def why(self, it: dict[str, Any], right: bool) -> str:
        return "Reviewer 2 grumbles, but nods." if right else f"Reviewer 2's lantern flickers. Better: {it['right'][0].lower()}{it['right'][1:]}."

    def after(self, right: bool) -> None:
        self.chance = max(0, min(100, self.chance + (12 if right else -15)))
        self.fish.chance, self.fish.mood = self.chance, 1 if right else -1
        self.fish.update()

    def next(self) -> None:
        if self.i + 1 >= len(self.items):
            self.bonus = max(0, self.chance - 50)            # an accepted paper is worth a little extra
        super().next()


class Bubble(QWidget):
    """Debug reef: the snippet, one clickable row per line, with GeeKOc's bubble rising beside it."""

    def __init__(self, game: "DebugReef", it: dict[str, Any]) -> None:
        super().__init__()
        self.game, self.it = game, it
        t = game.theme()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        code = QFrame()
        code.setObjectName("reefCode")
        code.setStyleSheet(f"#reefCode {{ background:{'#0d0d18' if t.get('dark', True) else '#ffffff'}; border-radius:10px; }}")
        cl = QVBoxLayout(code)
        cl.setContentsMargins(4, 6, 4, 6)
        cl.setSpacing(0)
        self.rows: list[QPushButton] = []
        for k, line in enumerate(it["lines"]):
            b = QPushButton(f"{k + 1:>2}  {line}")
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(game._row_css(t, ""))
            b.clicked.connect(lambda _c=False, kk=k: game.pick(kk))
            cl.addWidget(b)
            self.rows.append(b)
        lay.addWidget(code, 1)
        self.meter = _Rise(game)
        lay.addWidget(self.meter)


class _Rise(QWidget):
    def __init__(self, game: "DebugReef") -> None:
        super().__init__()
        self.game = game
        self.setFixedWidth(26)

    def paintEvent(self, e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.height()
        frac = max(0.0, min(1.0, 1 - self.game.left / self.game.TIMED)) if self.game.TIMED else 0
        p.setPen(QPen(QColor(127, 216, 255, 120), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(5, 2, 16, h - 4), 8, 8)
        y = (h - 18) * (1 - frac) + 9
        p.setPen(QPen(QColor("#7fd8ff"), 2))
        p.setBrush(QColor(127, 216, 255, 60))
        p.drawEllipse(QPointF(13, y), 7, 7)
        p.end()


class DebugReef(ChoiceGame):
    GAME, KIND, ROUND = "reef", "snippet", 5
    HINT = "Click the line with the bug before the bubble reaches the top."
    TIMED = 20.0

    def prompt(self, it: dict[str, Any]) -> QWidget:
        t = self.theme()
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(_label(it["lang"], f"color:{logic.readable(t['accent'], t)}; font-size:12px; font-weight:800;"))
        self.view = Bubble(self, it)
        lay.addWidget(self.view)
        return box

    def _row_css(self, t: dict[str, Any], mark: str) -> str:
        bg = {"right": "rgba(52,211,153,0.22)", "wrong": "rgba(248,113,113,0.22)"}.get(mark, "transparent")
        ink = "#f0f0f5" if t.get("dark", True) else "#241f1a"
        return (f"QPushButton {{ text-align:left; font-family:'JetBrains Mono','DejaVu Sans Mono',monospace; font-size:12px; "
                f"color:{ink}; background:{bg}; border:none; border-radius:6px; padding:4px 8px; }}"
                f"QPushButton:hover {{ background:rgba(127,216,255,0.16); }}")

    def choices(self, it: dict[str, Any]) -> tuple[list[str], int]:
        return [], it["bug"]                               # the lines themselves are the answers

    def show_question(self) -> None:
        super().show_question()
        if hasattr(self, "view") and self.i < len(self.items):
            self.buttons = self.view.rows

    def pick(self, k: int) -> None:
        if self.done:
            return
        it, t = self.items[self.i], self.theme()
        for j, b in enumerate(self.view.rows):
            b.setStyleSheet(self._row_css(t, "right" if j == it["bug"] else "wrong" if j == k else ""))
        rows, self.buttons = self.view.rows, []
        super().pick(k)
        self.buttons = rows
        if k == it["bug"] and self.left > self.TIMED / 2:
            self.bonus += 5 * it["level"]                  # found it fast
        self.view.meter.update()

    def _tick(self) -> None:
        super()._tick()
        if hasattr(self, "view"):
            self.view.meter.update()

    def why(self, it: dict[str, Any], right: bool) -> str:
        return it["why"]


class FigureCanvas(QWidget):
    """A small chart with one deliberate flaw, drawn from its kind (gems.FIGURE_KINDS). The phone draws the same eight."""

    def __init__(self, kind: str, theme: Callable[[], dict[str, Any]]) -> None:
        super().__init__()
        self.kind, self.theme = kind, theme
        self.setMinimumHeight(190)

    def paintEvent(self, e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#11111c"))
        ink, soft = QColor("#e8e8f0"), QColor("#9a9ab0")
        f = QFont(self.font())
        f.setPixelSize(11)
        p.setFont(f)
        L, T, R, B = 42.0, 22.0, w - 14.0, h - 30.0
        k = self.kind
        title = {"truncated": "Survival (%) by treatment", "rainbow": "Expression of 8 genes in 12 samples",
                 "noerror": "Mean cell count (n = 3 per group)", "dualaxis": "Sales and temperature",
                 "pie3d": "Share of reads by species", "overplot": "Gene length vs expression (50,000 genes)",
                 "spaghetti": "Growth of 12 strains", "nolabels": ""}[k]
        p.setPen(ink)
        p.drawText(QRectF(L, 2, w - L, 18), Qt.AlignLeft | Qt.AlignVCenter, title)

        def axes(labels: bool = True) -> None:
            p.setPen(QPen(soft, 1.2))
            p.drawLine(QPointF(L, T), QPointF(L, B))
            p.drawLine(QPointF(L, B), QPointF(R, B))

        colors = [QColor(c) for c in ("#7fd8ff", "#ffc457", "#34d399", "#ff6fd8", "#a873f5", "#f87171")]
        if k == "truncated":
            axes()
            vals, lo, hi = [96, 97.5, 99], 95, 100
            for v in range(95, 101):
                y = B - (v - lo) / (hi - lo) * (B - T)
                p.setPen(soft)
                p.drawText(QRectF(4, y - 7, L - 8, 14), Qt.AlignRight | Qt.AlignVCenter, str(v))
            bw = (R - L) / 5
            for i, v in enumerate(vals):
                y = B - (v - lo) / (hi - lo) * (B - T)
                p.fillRect(QRectF(L + bw * (0.6 + i * 1.4), y, bw, B - y), colors[i])
                p.setPen(soft)
                p.drawText(QRectF(L + bw * (0.6 + i * 1.4) - 10, B + 2, bw + 20, 14), Qt.AlignCenter, ["Control", "Drug A", "Drug B"][i])
        elif k == "rainbow":
            rows, cols = 8, 12
            cw, ch = (R - L) / cols, (B - T) / rows
            for r in range(rows):
                for c in range(cols):
                    v = (math.sin(r * 0.7 + c * 0.45) + 1) / 2
                    p.fillRect(QRectF(L + c * cw, T + r * ch, cw - 1, ch - 1), QColor.fromHsvF((1 - v) * 0.66, 1, 1))
        elif k == "noerror":
            axes()
            bw = (R - L) / 5
            for i, v in enumerate([42, 55, 61]):
                y = B - v / 70 * (B - T)
                p.fillRect(QRectF(L + bw * (0.6 + i * 1.4), y, bw, B - y), colors[i + 3])
                p.setPen(soft)
                p.drawText(QRectF(L + bw * (0.6 + i * 1.4) - 10, B + 2, bw + 20, 14), Qt.AlignCenter, ["WT", "KO-1", "KO-2"][i])
        elif k == "dualaxis":
            axes()
            p.setPen(QPen(soft, 1.2))
            p.drawLine(QPointF(R, T), QPointF(R, B))
            a = [0.2, 0.3, 0.35, 0.5, 0.62, 0.7, 0.8]
            b = [0.9, 0.75, 0.66, 0.5, 0.4, 0.3, 0.15]
            for vals, col in ((a, colors[0]), (b, colors[1])):
                p.setPen(QPen(col, 2.4))
                pts = [QPointF(L + (R - L) * i / (len(vals) - 1), B - v * (B - T)) for i, v in enumerate(vals)]
                for i in range(len(pts) - 1):
                    p.drawLine(pts[i], pts[i + 1])
            p.setPen(colors[0])
            p.drawText(QRectF(2, T, L - 6, 14), Qt.AlignRight, "€")
            p.setPen(colors[1])
            p.drawText(QRectF(R + 2, T, 14, 14), Qt.AlignLeft, "°C")
        elif k == "pie3d":
            cx, cy, rx, ry = w / 2, h / 2 + 6, min(w * 0.32, 120), min(w * 0.32, 120) * 0.42
            shares, start = [0.4, 0.25, 0.2, 0.15], 30.0
            for depth in range(14, 0, -2):
                ang = start
                for i, s in enumerate(shares):
                    c = QColor(colors[i]).darker(140)
                    p.setBrush(c)
                    p.setPen(Qt.NoPen)
                    p.drawPie(QRectF(cx - rx, cy - ry + depth, 2 * rx, 2 * ry), int(ang * 16), int(s * 360 * 16))
                    ang += s * 360
            ang = start
            for i, s in enumerate(shares):
                p.setBrush(colors[i])
                p.drawPie(QRectF(cx - rx, cy - ry, 2 * rx, 2 * ry), int(ang * 16), int(s * 360 * 16))
                ang += s * 360
        elif k == "overplot":
            axes()
            rng = random.Random(3)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(127, 216, 255))
            for _ in range(2500):
                x = rng.gauss(0.5, 0.18)
                y = 0.5 + (x - 0.5) * 0.6 + rng.gauss(0, 0.12)
                if 0 < x < 1 and 0 < y < 1:
                    p.drawEllipse(QPointF(L + x * (R - L), B - y * (B - T)), 2.6, 2.6)
        elif k == "spaghetti":
            axes()
            rng = random.Random(5)
            for s in range(12):
                c = QColor.fromHsvF(0.58 + s * 0.01, 0.5, 0.95)
                p.setPen(QPen(c, 1.6))
                y = 0.1 + rng.random() * 0.1
                prev = QPointF(L, B - y * (B - T))
                for i in range(1, 12):
                    y = min(0.95, y + rng.random() * 0.12)
                    pt = QPointF(L + (R - L) * i / 11, B - y * (B - T))
                    p.drawLine(prev, pt)
                    prev = pt
        elif k == "nolabels":
            axes()
            rng = random.Random(9)
            p.setPen(Qt.NoPen)
            p.setBrush(colors[2])
            for i in range(14):
                x = i / 13
                p.drawEllipse(QPointF(L + x * (R - L), B - (0.15 + 0.7 * x + rng.uniform(-0.08, 0.08)) * (B - T)), 4, 4)
        p.end()


class FixFigure(ChoiceGame):
    GAME, KIND, ROUND = "figure", "figure", 4
    HINT = "What's wrong with this figure?"

    def prompt(self, it: dict[str, Any]) -> QWidget:
        return FigureCanvas(it["draw"], self.theme)

    def choices(self, it: dict[str, Any]) -> tuple[list[str], int]:
        opts = random.sample([it["right"]] + list(it["wrong"])[:3], 4)
        return opts, opts.index(it["right"])

    def why(self, it: dict[str, Any], right: bool) -> str:
        return it["right"] + "."


GAMES = {"realfake": RealOrFake, "genemon": GeneOrMon, "first": WhichFirst, "reviewer": Reviewer2, "reef": DebugReef,
         "figure": FixFigure}
assert set(GAMES) <= set(gems.GAME_IDS)
