"""The arcade games of Play with GeeKOc (GEMS, docs/GEMS.md), each with questions inside:

- Whack-a-bug: bugs and good practices pop up for 30 seconds; whack the bugs, spare the friends;
- Sort the catch: names fall one at a time; steer each into the right net;
- GeeKOc run: jump the bugs; at a gate, jump for the top answer or stay low for the bottom one;
- Flappy GeeKOc: puff ink to swim up through the gap of the right answer.

They share ArcadeGame: a frame loop that runs only while the game is on screen, a field as wide as FIELD_W and as
tall as the panel, a card to start, and the result. Every answer goes to gems_store.finish like the other games. The
phone has the same four (components/games-arcade.tsx). Everything shown comes from the pack: plain text only.
"""
from __future__ import annotations

import random
import time
from typing import Any, Callable

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import gems, gems_store


def _label(text: str, css: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.PlainText)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(css + " background:transparent;")
    return lbl


def _oc(p: QPainter, pose: str, x: float, y: float, size: float) -> None:
    """GeeKOc in a pose, his arms swimming (the tour's frames)."""
    try:
        from .tour_ui import _frames
        frames = _frames(pose)
        frames[int(time.monotonic() * 8) % len(frames)].render(p, QRectF(x - size / 2, y - size / 2, size, size))
    except Exception:
        pass


def _pill(p: QPainter, text: str, cx: float, cy: float, bg: str, ink: str = "#1a1428", px: int = 13) -> QRectF:
    f = QFont(p.font())
    f.setPixelSize(px)
    f.setBold(True)
    p.setFont(f)
    w = p.fontMetrics().horizontalAdvance(text) + 18
    r = QRectF(cx - w / 2, cy - 12, w, 24)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(bg))
    p.drawRoundedRect(r, 12, 12)
    p.setPen(QColor(ink))
    p.drawText(r, Qt.AlignCenter, text)
    return r


class ArcadeGame(QWidget):
    finished = Signal(list, float, int)
    FIELD_W = 420.0
    GAME = ""
    TITLE, HOWTO = "", ""

    def __init__(self, cfg: Any, theme: Callable[[], dict[str, Any]], hud: Callable[[str], None]) -> None:
        super().__init__()
        self.cfg, self.theme, self.hud = cfg, theme, hud
        self.W, self.H = self.FIELD_W, 560.0
        self.setMinimumHeight(300)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.answers: list[dict[str, Any]] = []
        self.paused, self.ended, self.bonus = True, False, 0
        self.message, self.message_t = "", 0.0
        self.t0 = time.monotonic()
        self.overlay: QWidget | None = None
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._frame)
        self.last = time.monotonic()
        self.setup()
        self._card(self.TITLE, self.HOWTO, "Go", self.go)

    # ---- what a game says
    def setup(self) -> None: ...
    def step(self, dt: float) -> None: ...
    def draw(self, p: QPainter) -> None: ...
    def press(self, x: float, y: float) -> None: ...
    def key(self, k: int) -> bool: return False

    # ---- the frame
    def go(self) -> None:
        self._drop_card()
        self.paused = False
        self.t0 = time.monotonic()
        self.setFocus()

    def stop(self) -> None:
        self.timer.stop()

    def showEvent(self, e) -> None:  # noqa: N802
        self.last = time.monotonic()
        self.timer.start()

    def hideEvent(self, e) -> None:  # noqa: N802
        self.timer.stop()

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        if self.width() > 0:
            self.H = max(360.0, self.W * self.height() / self.width())
        self._place_card()

    def say(self, text: str, secs: float = 2.6) -> None:
        self.message, self.message_t = text, secs

    def answer(self, iid: str, right: bool, level: int, terms: list[str]) -> None:
        self.answers.append({"id": iid, "right": right, "level": level, "terms": list(terms)})

    def end(self) -> None:
        if self.ended:
            return
        self.ended, self.paused = True, True
        QTimer.singleShot(450, lambda: self.finished.emit(self.answers, time.monotonic() - self.t0, self.bonus))

    def _frame(self) -> None:
        now = time.monotonic()
        dt = min(0.05, now - self.last)
        self.last = now
        self.message_t -= dt
        if not self.paused:
            self.step(dt)
        self.update()

    def _world(self, pos) -> QPointF:
        k = self.width() / self.W
        return QPointF(pos.x() / k, pos.y() / k)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        self.setFocus()
        if not self.paused:
            w = self._world(e.position())
            self.press(w.x(), w.y())

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if self.paused or not self.key(e.key()):
            super().keyPressEvent(e)

    def paintEvent(self, e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        k = self.width() / self.W
        p.scale(k, k)
        self.draw(p)
        if self.message_t > 0 and self.message:
            f = QFont(p.font())
            f.setPixelSize(12)
            f.setBold(True)
            p.setFont(f)
            box = QRectF(14, self.H - 64, self.W - 28, 40)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(28, 28, 44, 235))
            p.drawRoundedRect(box, 10, 10)
            p.setPen(QColor("#f0f0f5"))
            p.drawText(box.adjusted(8, 2, -8, -2), Qt.AlignCenter | Qt.TextWordWrap, self.message)
        p.end()

    # ---- cards over the field
    def _card(self, title: str, text: str, button: str, fn: Callable[[], None]) -> None:
        t = self.theme()
        self._drop_card()
        box = QFrame(self)
        box.setObjectName("arcCard")
        box.setStyleSheet(f"#arcCard {{ background:{t['card_bg'] if not t['card_bg'].startswith('rgba') else t['solid_bg']}; "
                          f"border:1px solid {t['accent']}; border-radius:14px; }}")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.addWidget(_label(title, f"color:{t['text']}; font-size:14px; font-weight:800;"))
        if text:
            lay.addWidget(_label(text, f"color:{t['muted']}; font-size:11.5px;"))
        row = QHBoxLayout()
        b = QPushButton(button)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(f"QPushButton {{ background:{t['accent']}; color:{t['on_accent']}; border:none; border-radius:9px; "
                        "padding:6px 14px; font-size:12px; font-weight:700; }")
        b.clicked.connect(fn)
        row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.overlay = box
        self._place_card()
        box.show()
        box.raise_()
        b.setFocus()

    def _place_card(self) -> None:
        if self.overlay is not None:
            w = max(200, min(self.width() - 24, 360))
            self.overlay.setFixedWidth(w)
            lay = self.overlay.layout()
            if lay is not None and lay.hasHeightForWidth():          # wrapped text: as tall as it needs at this width
                self.overlay.setFixedHeight(lay.totalHeightForWidth(w))
            else:
                self.overlay.adjustSize()
            self.overlay.move((self.width() - self.overlay.width()) // 2, max(8, (self.height() - self.overlay.height()) // 2))

    def _drop_card(self) -> None:
        if self.overlay is not None:
            self.overlay.hide()
            self.overlay.deleteLater()
            self.overlay = None

    def show_result(self, summary: dict[str, Any], again: Callable[[], None], hub: Callable[[], None]) -> None:
        from .games_ui import ResultCard
        self.timer.stop()
        self._drop_card()
        card = ResultCard(summary, self.theme, again, hub)
        card.setParent(self)
        self.overlay = card
        self._place_card()
        card.show()
        card.raise_()


# ------------------------------------------------------------------------------------------------ Whack-a-bug
class WhackABug(ArcadeGame):
    GAME = "whack"
    TITLE = "Whack the bugs, spare the friends"
    HOWTO = "Bugs (an off-by-one, a memory leak) pop up: click them. Friends (a unit test, a README) pop up too: leave them be. 30 seconds."
    LENGTH = 30.0

    def setup(self) -> None:
        self.critters = gems_store.round_items(self.cfg, self.GAME, "critter", 16)
        self.queue = list(self.critters)
        self.holes = [{"x": 0.0, "y": 0.0, "up": None} for _ in range(9)]
        self.left, self.spawn, self.hammer = self.LENGTH, 0.0, (0.0, 0.0, 0.0)
        self.score = 0
        self.counted: set[str] = set()          # each critter counts once a round: its first outcome

    def _count(self, c: dict[str, Any], right: bool) -> None:
        if c["id"] not in self.counted:
            self.counted.add(c["id"])
            self.answer(c["id"], right, c["level"], c["terms"])

    def _layout(self) -> None:
        top = 190.0                              # below GeeKOc and the clock, so a pop-up never covers them
        gap = (self.H - top - 40) / 3
        for i, h in enumerate(self.holes):
            h["x"] = self.W / 2 + (i % 3 - 1) * (self.W / 3.2)
            h["y"] = top + gap * (i // 3) + gap * 0.6

    def step(self, dt: float) -> None:
        self._layout()
        self.left -= dt
        self.spawn -= dt
        if self.spawn <= 0:
            free = [h for h in self.holes if h["up"] is None]
            if free:
                if not self.queue:
                    self.queue = random.sample(self.critters, len(self.critters))
                c = self.queue.pop()
                random.choice(free)["up"] = {"c": c, "life": random.uniform(1.3, 2.0) - (self.LENGTH - self.left) * 0.015}
            self.spawn = random.uniform(0.45, 0.85)
        for h in self.holes:
            up = h["up"]
            if up:
                up["life"] -= dt
                if up["life"] <= 0:
                    self._count(up["c"], not up["c"]["bug"])     # a friend rightly spared; a bug that got away
                    h["up"] = None
        if self.left <= 0:
            self.end()
        self.hud(f"{max(0, int(self.left + 0.99))} s · {self.score}")

    def press(self, x: float, y: float) -> None:
        self.hammer = (x, y, 0.15)
        for h in self.holes:
            up = h["up"]
            if up and abs(x - h["x"]) < 52 and h["y"] - 70 < y < h["y"] + 24:
                c = up["c"]
                h["up"] = None
                if c["bug"]:
                    self.score += 10
                    self._count(c, True)
                else:
                    self.score = max(0, self.score - 15)
                    self._count(c, False)
                    self.say(f"You whacked a {c['label'].lower()}: {c['why'][0].lower()}{c['why'][1:]}")
                return

    def draw(self, p: QPainter) -> None:
        self._layout()
        p.fillRect(QRectF(0, 0, self.W, self.H), QColor("#2b1d3a"))
        _oc(p, "point", 52, 54, 92)
        p.setPen(QColor("#f0f0f5"))
        f = QFont(p.font())
        f.setPixelSize(15)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(100, 30, self.W - 110, 40), Qt.AlignVCenter, f"{max(0, int(self.left + 0.99))} s left   ·   {self.score}")
        for h in self.holes:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#120a1c"))
            p.drawEllipse(QPointF(h["x"], h["y"] + 14), 50, 15)
            up = h["up"]
            if up:
                c = up["c"]
                f.setPixelSize(36)
                p.setFont(f)
                p.setPen(QColor("#ffffff"))
                p.drawText(QRectF(h["x"] - 30, h["y"] - 46, 60, 50), Qt.AlignCenter, "\U0001f41b" if c["bug"] else "\U0001f98b")
                _pill(p, c["label"], h["x"], h["y"] - 58, "#f87171" if c["bug"] else "#34d399", px=11)
        x, y, t = self.hammer
        if t > 0 or True:
            p.save()
            p.translate(x, y)
            p.rotate(-50 if t > 0 else -18)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#c9871a"))
            p.drawRect(QRectF(-3, -2, 6, 40))
            p.setBrush(QColor("#8b45e0"))
            p.drawRoundedRect(QRectF(-20, -18, 40, 20), 5, 5)
            p.restore()
        self.hammer = (x, y, t - 0.016)

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        w = self._world(e.position())
        self.hammer = (w.x(), w.y(), self.hammer[2])


# ------------------------------------------------------------------------------------------------ Sort the catch
class SortTheCatch(ArcadeGame):
    GAME = "catch"
    TITLE = "Sort the catch"
    HOWTO = "Names fall one at a time. Steer each into the right net: ← → then ↓ to drop, or click a net."
    COLORS = ("#7fd8ff", "#ffc457", "#34d399")

    def setup(self) -> None:
        sets = gems_store.round_items(self.cfg, self.GAME, "sort", 1)
        self.set = sets[0]
        self.things = random.sample(self.set["things"], min(10, len(self.set["things"])))
        self.cur: dict[str, Any] | None = None
        self.flash: tuple[int, bool, float] | None = None
        self.n = 0
        self.right = 0

    def go(self) -> None:
        super().go()
        self._next()

    def _nx(self, i: int) -> float:
        nb = len(self.set["bins"])
        return self.W / 2 + (i - (nb - 1) / 2) * (self.W / nb)

    def _next(self) -> None:
        if not self.things:
            self.cur = None
            self.end()
            return
        name, b = self.things.pop()
        self.cur = {"name": name, "bin": b, "lane": len(self.set["bins"]) // 2, "x": self.W / 2, "y": 70.0, "vy": 48 + self.n * 5}

    def step(self, dt: float) -> None:
        c = self.cur
        if c is None:
            return
        c["x"] += (self._nx(c["lane"]) - c["x"]) * min(1, dt * 10)
        c["y"] += c["vy"] * dt
        if c["y"] > self.H - 130:
            self.n += 1
            ok = c["lane"] == c["bin"]
            self.right += ok
            self.answer(f"{self.set['id']}:{c['name']}", ok, self.set["level"], self.set["terms"])
            self.flash = (c["lane"], ok, 0.8)
            if not ok:
                self.say(f"{c['name']} goes in “{self.set['bins'][c['bin']]}”.")
            self._next()
        if self.flash:
            lane, ok, t = self.flash
            self.flash = (lane, ok, t - dt) if t - dt > 0 else None
        self.hud(f"{self.right}/{self.n} right · {len(self.things) + (1 if self.cur else 0)} to go")

    def key(self, k: int) -> bool:
        c = self.cur
        if c is None:
            return False
        if k in (Qt.Key_Left, Qt.Key_A):
            c["lane"] = max(0, c["lane"] - 1)
        elif k in (Qt.Key_Right, Qt.Key_D):
            c["lane"] = min(len(self.set["bins"]) - 1, c["lane"] + 1)
        elif k in (Qt.Key_Down, Qt.Key_Space, Qt.Key_S):
            c["vy"] = 520
        else:
            return False
        return True

    def press(self, x: float, y: float) -> None:
        if self.cur is None:
            return
        nb = len(self.set["bins"])
        self.cur["lane"] = min(range(nb), key=lambda i: abs(x - self._nx(i)))
        self.cur["vy"] = 520

    def draw(self, p: QPainter) -> None:
        p.fillRect(QRectF(0, 0, self.W, self.H), QColor("#071628"))
        _oc(p, "point", 50, 50, 88)
        f = QFont(p.font())
        f.setPixelSize(15)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#f0f0f5"))
        p.drawText(QRectF(96, 26, self.W - 104, 44), Qt.AlignVCenter | Qt.TextWordWrap, self.set["name"])
        nb = len(self.set["bins"])
        for i, name in enumerate(self.set["bins"]):
            x, top = self._nx(i), self.H - 110
            col = QColor(self.COLORS[i % 3])
            fill = QColor(255, 255, 255, 12)
            if self.flash and self.flash[0] == i:
                fill = QColor(52, 211, 153, 70) if self.flash[1] else QColor(248, 113, 113, 70)
            path = QPainterPath(QPointF(x - self.W / nb / 2 + 12, top))
            path.quadTo(QPointF(x, self.H + 10), QPointF(x + self.W / nb / 2 - 12, top))
            path.closeSubpath()
            p.setBrush(fill)
            p.setPen(QPen(col, 2.5))
            p.drawPath(path)
            p.setPen(col)
            f.setPixelSize(14)
            p.setFont(f)
            p.drawText(QRectF(x - 70, top - 26, 140, 22), Qt.AlignCenter, name)
        c = self.cur
        if c:
            _pill(p, c["name"], c["x"], c["y"], "#ff6fd8", px=14)


# ------------------------------------------------------------------------------------------------ GeeKOc run
class GeeKOcRun(ArcadeGame):
    GAME = "run"
    TITLE = "GeeKOc run"
    HOWTO = "Space, ↑ or click to jump. Jump the bugs. At a gate, jump for the top answer or stay low for the bottom one."
    GATES = 8

    def setup(self) -> None:
        self.gates = gems_store.round_items(self.cfg, self.GAME, "gate", self.GATES)
        self.gi = 0
        self.y, self.vy = 0.0, 0.0
        self.obs: list[dict[str, Any]] = []
        self.speed, self.dist, self.next_obs, self.next_gate = 200.0, 0.0, 1.4, 3.5
        self.lives, self.hurt = 3, 0.0

    @property
    def ground(self) -> float:
        return self.H - 90

    def jump(self) -> None:
        if self.y >= -1:
            self.vy = -560

    def key(self, k: int) -> bool:
        if k in (Qt.Key_Space, Qt.Key_Up, Qt.Key_W):
            self.jump()
            return True
        return False

    def press(self, x: float, y: float) -> None:
        self.jump()

    def step(self, dt: float) -> None:
        self.dist += self.speed * dt
        self.speed += dt * 5
        self.vy += 1650 * dt
        self.y = min(0.0, self.y + self.vy * dt)
        if self.y >= 0:
            self.vy = 0
        self.next_obs -= dt
        self.next_gate -= dt
        self.hurt -= dt
        far = any(o["x"] > self.W - 160 for o in self.obs)
        if self.next_gate <= 0 and not far and self.gi < len(self.gates):
            g = self.gates[self.gi]
            self.gi += 1
            top = random.random() < 0.5
            self.obs.append({"gate": g, "x": self.W + 30, "w": 22, "top": top})
            self.next_gate, self.next_obs = random.uniform(5.5, 7.0), 1.8
        elif self.next_obs <= 0 and not far:
            label = random.choice(["NaN", "Segfault", "404", "OOM", "Merge conflict", "Typo"])
            # every bug the same jumpable size (a wide one once took longer to pass than a jump lasts); its name above it
            self.obs.append({"label": label, "x": self.W + 20, "w": 34, "h": random.uniform(28, 40)})
            self.next_obs = random.uniform(1.3, 2.2)
        for o in self.obs:
            o["x"] -= self.speed * dt
        px = 92
        for o in self.obs:
            if o.get("done"):
                continue
            if "gate" in o and o["x"] < px + 10 < o["x"] + o["w"] + 20:
                o["done"] = True
                g = o["gate"]
                took_top = self.y < -60
                ok = took_top == o["top"]
                self.answer(g["id"], ok, g["level"], g["terms"])
                if ok:
                    self.bonus += 5
                else:
                    self.lives -= 1
                    self.hurt = 1.0
                    self.say(f"{g['q']}? {g['right']}.")
            elif "label" in o and o["x"] < px + 16 and o["x"] + o["w"] > px - 16 and -self.y < o["h"] - 6:
                o["done"] = True
                self.lives -= 1
                self.hurt = 1.0
                self.say(f"Ouch: {o['label']}!", 1.2)
        self.obs = [o for o in self.obs if o["x"] + o["w"] > -40]
        if self.lives <= 0 or (self.gi >= len(self.gates) and not any("gate" in o and not o.get("done") for o in self.obs)):
            self.end()
        self.hud(f"{int(self.dist / 10)} m · gate {min(self.gi, len(self.gates))}/{len(self.gates)} · {'♥' * max(0, self.lives)}")

    def draw(self, p: QPainter) -> None:
        g = self.ground
        p.fillRect(QRectF(0, 0, self.W, self.H), QColor("#f4efe9"))
        p.setPen(QPen(QColor("#8a8070"), 2))
        p.drawLine(QPointF(0, g + 22), QPointF(self.W, g + 22))
        for x in range(int(-(self.dist % 60)), int(self.W), 60):
            p.fillRect(QRectF(x, g + 30, 14, 2), QColor("#b8ad9c"))
        nxt = next((o for o in self.obs if "gate" in o and not o.get("done")), None)
        if nxt:
            f = QFont(p.font())
            f.setPixelSize(15)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("#241f1a"))
            p.drawText(QRectF(12, 18, self.W - 24, 48), Qt.AlignCenter | Qt.TextWordWrap, nxt["gate"]["q"] + "?")
        for o in self.obs:
            if "gate" in o:
                gt = o["gate"]
                top_text, low_text = (gt["right"], gt["wrong"]) if o["top"] else (gt["wrong"], gt["right"])
                p.fillRect(QRectF(o["x"], 80, o["w"], g + 22 - 80), QColor("#6d28d9"))
                p.fillRect(QRectF(o["x"] - 2, g - 110, o["w"] + 4, 4), QColor("#f4efe9"))
                _pill(p, top_text, o["x"] + o["w"] / 2, g - 150, "#ffc457", "#241f1a", 14)
                _pill(p, low_text, o["x"] + o["w"] / 2, g - 30, "#ffc457", "#241f1a", 14)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor("#c0367f"))
                p.drawRoundedRect(QRectF(o["x"], g + 22 - o["h"], o["w"], o["h"]), 6, 6)
                f = QFont(p.font())
                f.setPixelSize(18)
                p.setFont(f)
                p.setPen(QColor("#ffffff"))
                p.drawText(QRectF(o["x"], g + 22 - o["h"], o["w"], o["h"]), Qt.AlignCenter, "\U0001f41b")
                f.setPixelSize(11)
                f.setBold(True)
                p.setFont(f)
                p.setPen(QColor("#c0367f"))
                p.drawText(QRectF(o["x"] - 40, g + 2 - o["h"] - 18, o["w"] + 80, 16), Qt.AlignCenter, o["label"])
        if self.hurt <= 0 or int(time.monotonic() * 12) % 2:
            _oc(p, "jet" if self.y < -2 else "wave", 92, g - 8 + self.y, 76)


# ------------------------------------------------------------------------------------------------ Flappy GeeKOc
class FlappyGeeKOc(ArcadeGame):
    GAME = "flappy"
    TITLE = "Flappy GeeKOc"
    HOWTO = "Space, ↑ or click to puff ink and swim up. Fly through the gap of the right answer; the coral costs a life."
    GATES = 8

    def setup(self) -> None:
        self.gates = gems_store.round_items(self.cfg, self.GAME, "gate", self.GATES)
        self.gi = 0
        self.y, self.vy = 200.0, 0.0
        self.pipes: list[dict[str, Any]] = []
        self.next = 0.8
        self.lives, self.hurt = 3, 0.0
        self.puffs: list[list[float]] = []

    def flap(self) -> None:
        self.vy = -300
        self.puffs.append([110.0, self.y + 26, 6.0, 0.7])

    def key(self, k: int) -> bool:
        if k in (Qt.Key_Space, Qt.Key_Up, Qt.Key_W):
            self.flap()
            return True
        return False

    def press(self, x: float, y: float) -> None:
        self.flap()

    def _gaps(self) -> tuple[tuple[float, float], tuple[float, float]]:
        h = self.H
        return (h * 0.16, h * 0.16 + 120), (h * 0.84 - 120, h * 0.84)

    def step(self, dt: float) -> None:
        self.vy += 820 * dt
        self.y += self.vy * dt
        self.hurt -= dt
        self.next -= dt
        if self.next <= 0 and self.gi < len(self.gates):
            g = self.gates[self.gi]
            self.gi += 1
            self.pipes.append({"g": g, "x": self.W + 40, "top": random.random() < 0.5})
            self.next = 3.4
        for pp in self.pipes:
            pp["x"] -= 128 * dt
        for pf in self.puffs:
            pf[0] -= 60 * dt
            pf[2] += 18 * dt
            pf[3] -= dt
        self.puffs = [pf for pf in self.puffs if pf[3] > 0]
        (t0, t1), (b0, b1) = self._gaps()
        gx = 120
        for pp in self.pipes:
            if pp.get("done"):
                continue
            if pp["x"] < gx + 14 and pp["x"] + 54 > gx - 14:
                in_top, in_low = t0 < self.y < t1, b0 < self.y < b1
                if not in_top and not in_low and self.hurt <= 0:
                    self.lives -= 1
                    self.hurt = 1.0
                    self.say("Bonk! Into the coral.", 1.2)
                    self.y, self.vy = (t0 + t1) / 2 if pp["top"] else (b0 + b1) / 2, -100
                elif in_top or in_low:
                    pp["gap"] = "top" if in_top else "low"
            elif pp["x"] + 54 <= gx - 14 and "gap" in pp:
                pp["done"] = True
                g = pp["g"]
                ok = (pp["gap"] == "top") == pp["top"]
                self.answer(g["id"], ok, g["level"], g["terms"])
                if ok:
                    self.bonus += 5
                else:
                    self.lives -= 1
                    self.hurt = 1.0
                    self.say(f"{g['q']}? {g['right']}.")
            elif pp["x"] + 54 <= gx - 14:
                pp["done"] = True
        self.pipes = [pp for pp in self.pipes if pp["x"] > -80]
        if self.y > self.H - 12 or self.y < 8:
            if self.hurt <= 0:
                self.lives -= 1
                self.hurt = 1.0
                self.say("Careful: stay in the water!", 1.2)
            self.y, self.vy = self.H / 2, -120
        if self.lives <= 0 or (self.gi >= len(self.gates) and not self.pipes):
            self.end()
        self.hud(f"gate {min(self.gi, len(self.gates))}/{len(self.gates)} · {'♥' * max(0, self.lives)}")

    def draw(self, p: QPainter) -> None:
        p.fillRect(QRectF(0, 0, self.W, self.H), QColor("#0b3b5e"))
        for pf in self.puffs:
            c = QColor(20, 10, 40)
            c.setAlphaF(max(0.0, pf[3]))
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(pf[0], pf[1]), pf[2], pf[2])
        (t0, t1), (b0, b1) = self._gaps()
        for pp in self.pipes:
            x = pp["x"]
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#ff7a8a"))
            p.drawRect(QRectF(x, 0, 54, t0))
            p.drawRect(QRectF(x, t1, 54, b0 - t1))
            p.drawRect(QRectF(x, b1, 54, self.H - b1))
            g = pp["g"]
            top_text, low_text = (g["right"], g["wrong"]) if pp["top"] else (g["wrong"], g["right"])
            _pill(p, top_text, x + 27, (t0 + t1) / 2, "#ffc457", "#241f1a", 13)
            _pill(p, low_text, x + 27, (b0 + b1) / 2, "#ffc457", "#241f1a", 13)
        nxt = next((pp for pp in self.pipes if not pp.get("done")), None)
        if nxt:
            f = QFont(p.font())
            f.setPixelSize(15)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("#ffffff"))
            p.drawText(QRectF(12, 8, self.W - 24, self.H * 0.16 - 12), Qt.AlignCenter | Qt.TextWordWrap, nxt["g"]["q"] + "?")
        if self.hurt <= 0 or int(time.monotonic() * 12) % 2:
            _oc(p, "jet" if self.vy < 0 else "cheer", 120, self.y, 66)


GAMES = {"whack": WhackABug, "catch": SortTheCatch, "run": GeeKOcRun, "flappy": FlappyGeeKOc}
assert set(GAMES) <= set(gems.GAME_IDS)
