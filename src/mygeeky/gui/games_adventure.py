"""The two adventures of Play with GeeKOc (GEMS, docs/GEMS.md):

- Rise: GeeKOc climbs out of the sea on a pipeline's steps (a ladder from the pack). Each row offers the right next
  step and wrong ones; a wrong platform sinks and says why, and you choose again. The tide rises while you think. At
  the surface: the whole pipeline you climbed.
- GeeKOc goes home: a maze to his home, new every round. Doors ask questions from the quiz bank (data/questions.json):
  the Basics region easy ones, Core medium, Advanced hard. A wrong answer locks that door, so find another way round;
  if there is none, the door asks a different question.

Both build on ArcadeGame (games_arcade.py). The phone has the same two (components/games-adventure.tsx). Everything
shown comes from the pack or the quiz bank: plain text only.
"""
from __future__ import annotations

import random
from typing import Any, Callable

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QVBoxLayout

from .. import gems, gems_store
from .games_arcade import ArcadeGame, _label, _oc

# a quiz protocol, as the field terms GEMS uses (for the Model and for picking questions from your field)
PROTOCOL_TERMS = {
    "gwas": ["gwas", "genetics"], "single-cell-rna-seq": ["single-cell", "rna-seq"], "python-data-analysis": ["python"],
    "r-data-analysis": ["r"], "ml-in-practice": ["machine learning"], "git-github-teamwork": ["git"],
    "stats-for-experiments": ["statistics"], "figures-for-papers": ["visualization"], "nextflow": ["workflow"],
    "image-analysis-fiji": ["imaging"], "excel-to-r": ["r", "data analysis"], "open-source-first-pr": ["open source", "git"],
    "algorithms-interviews": ["programming"], "first-web-app": ["software"],
}


def _wrap_button(text: str, t: dict[str, Any]):
    from .games_cards import WrapButton
    b = WrapButton(text)
    b.set_ink(t["text"])
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"QPushButton {{ background:{t['btn_bg']}; border:2px solid {t['btn_bg']}; border-radius:10px; padding:0px; }}"
                    f"QPushButton:hover {{ background:{t['btn_hover']}; }}")
    return b


def _mark(b, t: dict[str, Any], mark: str) -> None:
    border = {"right": t["good"], "wrong": t["bad"]}.get(mark, t["btn_bg"])
    b.setStyleSheet(f"QPushButton {{ background:{t['btn_bg']}; border:2px solid {border}; border-radius:10px; padding:0px; }}")


# ------------------------------------------------------------------------------------------------ Rise
class Rise(ArcadeGame):
    GAME = "rise"
    TITLE = "Rise: climb out of the sea"
    HOWTO = "Each row: click the right next step (or press 1, 2, 3). Wrong platforms sink and say why. The tide rises while you think."
    ROW = 150.0

    def setup(self) -> None:
        self.ladder = gems_store.round_items(self.cfg, self.GAME, "ladder", 1)[0]
        self.TITLE = f"Rise: climb {self.ladder['name']}"
        self.row = 0
        self.opts: list[dict[str, Any]] = []
        self.first_try = True
        self.me = [self.W / 2, 0.0]
        self.jump: dict[str, Any] | None = None
        self.cam = self.cam_to = 0.0
        self.tide = 0.0
        self.mistakes = 0
        self._lay_row()

    def _y(self, r: int) -> float:
        return self.H - 150 - r * self.ROW

    def _lay_row(self) -> None:
        r = self.ladder["rows"][self.row]
        opts = [{"text": r["right"], "ok": True, "why": ""}] + [{"text": w["text"], "ok": False, "why": w["why"]} for w in r["wrong"]]
        random.shuffle(opts)
        n, gap = len(opts), 12.0
        w = (self.W - 30 - gap * (n - 1)) / n
        for i, o in enumerate(opts):
            o.update(x=15 + i * (w + gap), w=w, y=self._y(self.row + 1))
        self.opts = opts
        self.first_try = True
        if self.row == 0:
            self.me = [self.W / 2, self._y(0)]
            self.tide = self._y(0) + 140

    def resizeEvent(self, e) -> None:  # noqa: N802
        old = self.H
        super().resizeEvent(e)
        if abs(old - self.H) > 1 and self.row == 0 and not self.jump:
            self._lay_row()

    def press(self, x: float, y: float) -> None:
        y += self.cam
        for i, o in enumerate(self.opts):
            if not o.get("gone") and o["x"] <= x <= o["x"] + o["w"] and o["y"] - 10 <= y <= o["y"] + 80:
                self.choose(i)

    def key(self, k: int) -> bool:
        idx = {Qt.Key_1: 0, Qt.Key_2: 1, Qt.Key_3: 2, Qt.Key_4: 3}.get(k)
        live = [i for i, o in enumerate(self.opts) if not o.get("gone")]
        if idx is not None and idx < len(live):
            self.choose(live[idx])
            return True
        return False

    def choose(self, i: int) -> None:
        if self.jump or self.paused:
            return
        o = self.opts[i]
        self.jump = {"from": list(self.me), "to": [o["x"] + o["w"] / 2, o["y"]], "t": 0.0, "opt": o}

    def step(self, dt: float) -> None:
        self.cam += (self.cam_to - self.cam) * min(1.0, dt * 4)
        if not self.jump:
            self.tide -= dt * 4                      # gentle: about 27 s a row before it reaches GeeKOc
            if self.tide < self.me[1] + 30:
                self.say("The tide caught GeeKOc.", 3)
                self.end()
                return
        else:
            j = self.jump
            j["t"] = min(1.0, j["t"] + dt / 0.55)
            k = j["t"]
            self.me = [j["from"][0] + (j["to"][0] - j["from"][0]) * k,
                       j["from"][1] + (j["to"][1] - j["from"][1]) * k - (1 - (2 * k - 1) ** 2) * 90]
            if k >= 1:
                self.jump = None
                o = j.get("opt")
                if o is None:
                    return
                rid = f"{self.ladder['id']}:{self.row}"
                if o["ok"]:
                    if self.first_try:
                        self.answer(rid, True, self.ladder["level"], self.ladder["terms"])
                    self.row += 1
                    self.cam_to = -self.row * self.ROW
                    # a step up buys breathing room: the tide drops back to between 140 and 220 below GeeKOc
                    self.tide = min(max(self.tide, self.me[1] + 140), self.me[1] + 220)
                    if self.row >= len(self.ladder["rows"]):
                        self.paused = True
                        QTimer.singleShot(400, self._surface)
                    else:
                        self._lay_row()
                else:
                    if self.first_try:
                        self.answer(rid, False, self.ladder["level"], self.ladder["terms"])
                    self.first_try = False
                    self.mistakes += 1
                    o["gone"] = True
                    self.say(o["why"], 3.6)
                    self.jump = {"from": list(self.me), "to": [self.W / 2, self._y(self.row)], "t": 0.0, "opt": None}
        self.hud(f"step {min(self.row + 1, len(self.ladder['rows']))}/{len(self.ladder['rows'])} · {self.mistakes} sank")

    def _surface(self) -> None:
        steps = "\n".join(f"{i + 1}. {r['right']}" for i, r in enumerate(self.ladder["rows"]))
        self._card("GeeKOc reached the surface!", f"The pipeline you climbed, {self.ladder['name']}:\n{steps}",
                   "See how you did", self._done)

    def _done(self) -> None:
        self._drop_card()
        self.end()

    def draw(self, p: QPainter) -> None:
        depth = min(1.0, self.row / max(1, len(self.ladder["rows"])))
        top = QColor.fromHsvF(0.55, 0.75, 0.30 + depth * 0.35)
        p.fillRect(QRectF(0, 0, self.W, self.H), top)
        p.save()
        p.translate(0, -self.cam)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#2f6f7a"))
        p.drawRoundedRect(QRectF(self.W / 2 - 70, self._y(self.row) + 36, 140, 12), 6, 6)
        f = QFont(p.font())
        f.setPixelSize(12)
        f.setBold(True)
        p.setFont(f)
        for i, o in enumerate(self.opts):
            if o.get("gone"):
                continue
            r = QRectF(o["x"], o["y"] + 36, o["w"], 64)
            p.setPen(QPen(QColor("#ffc457") if self.jump is None else QColor("#5a6aa0"), 2))
            p.setBrush(QColor("#24304f"))
            p.drawRoundedRect(r, 10, 10)
            p.setPen(QColor("#f0f0f5"))
            p.drawText(r.adjusted(6, 4, -6, -4), Qt.AlignCenter | Qt.TextWordWrap, o["text"])
        _oc(p, "jet" if self.jump else "cheer" if self.row and not self.opts[0].get("gone") else "wave", self.me[0], self.me[1], 86)
        p.setBrush(QColor(8, 30, 70, 210))
        p.setPen(Qt.NoPen)
        p.drawRect(QRectF(0, self.tide, self.W, self.H + 4000))
        p.restore()
        f.setPixelSize(14)
        p.setFont(f)
        p.setPen(QColor("#f0f0f5"))
        p.drawText(QRectF(10, 6, self.W - 20, 22), Qt.AlignCenter, f"Climbing {self.ladder['name']}")


# ------------------------------------------------------------------------------------------------ GeeKOc goes home
class GoHome(ArcadeGame):
    GAME = "maze"
    TITLE = "GeeKOc goes home"
    HOWTO = "Arrow keys or WASD (or click beside GeeKOc). Doors ask questions: a wrong answer keeps that door shut, so find another way round."
    CW, CH = 9, 9

    def setup(self) -> None:
        cw, ch = self.CW, self.CH
        self.right = [[True] * ch for _ in range(cw)]
        self.down = [[True] * ch for _ in range(cw)]
        seen = [[False] * ch for _ in range(cw)]
        stack = [(0, 0)]
        seen[0][0] = True
        while stack:                                          # a maze: depth-first, no recursion limit
            x, y = stack[-1]
            nbr = [(dx, dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                   if 0 <= x + dx < cw and 0 <= y + dy < ch and not seen[x + dx][y + dy]]
            if not nbr:
                stack.pop()
                continue
            dx, dy = random.choice(nbr)
            nx, ny = x + dx, y + dy
            if dx == 1: self.right[x][y] = False                 # noqa: E701
            if dx == -1: self.right[nx][ny] = False              # noqa: E701
            if dy == 1: self.down[x][y] = False                  # noqa: E701
            if dy == -1: self.down[nx][ny] = False               # noqa: E701
            seen[nx][ny] = True
            stack.append((nx, ny))
        for _ in range(10):                                   # a few loops, so there's another way round
            x, y = random.randrange(cw - 1), random.randrange(ch - 1)
            if random.random() < 0.5:
                self.right[x][y] = False
            else:
                self.down[x][y] = False
        self.questions = self._questions()
        self.doors: dict[str, dict[str, Any]] = {}
        path = self._path(0, 0, lambda k: False) or []
        for i in range(2, len(path) - 1, 3):
            (x, y), (nx, ny) = path[i - 1], path[i]
            self.doors[self._key(x, y, nx - x, ny - y)] = {"state": "shut", "a": (x, y), "b": (nx, ny)}
        self.at = [0, 0]
        self.anim = [0.0, 0.0, 1.0]                            # from x, from y, progress
        self.face = "wave"
        self.home = False
        self.right_first = self.asked = 0

    def _questions(self) -> dict[int, list[dict[str, Any]]]:
        from .games_ui import _quiz
        weights = gems_store.weights(self.cfg)
        bank = [q for q in _quiz() if q.get("kind") == "choice"]
        rel = lambda q: sum(weights.get(t, 0) for t in PROTOCOL_TERMS.get(q.get("protocol", ""), []))  # noqa: E731
        out: dict[int, list[dict[str, Any]]] = {0: [], 1: [], 2: []}
        for q in sorted(random.sample(bank, len(bank)), key=lambda q: -rel(q)):
            out[{"easy": 0, "medium": 1, "hard": 2}.get(q.get("level"), 1)].append(q)
        return out

    def _key(self, x: int, y: int, dx: int, dy: int) -> str:
        if dx < 0: return f"{x - 1},{y},r"                    # noqa: E701
        if dy < 0: return f"{x},{y - 1},d"                    # noqa: E701
        return f"{x},{y},r" if dx > 0 else f"{x},{y},d"

    def _open(self, x: int, y: int, dx: int, dy: int) -> bool:
        nx, ny = x + dx, y + dy
        if not (0 <= nx < self.CW and 0 <= ny < self.CH):
            return False
        if dx > 0: return not self.right[x][y]                # noqa: E701
        if dx < 0: return not self.right[nx][ny]              # noqa: E701
        if dy > 0: return not self.down[x][y]                 # noqa: E701
        return not self.down[nx][ny]

    def _path(self, sx: int, sy: int, blocked: Callable[[str], bool]) -> list[tuple[int, int]] | None:
        prev: dict[tuple[int, int], tuple[int, int] | None] = {(sx, sy): None}
        queue = [(sx, sy)]
        while queue:
            x, y = queue.pop(0)
            if (x, y) == (self.CW - 1, self.CH - 1):
                out, k = [], (x, y)
                while k is not None:
                    out.append(k)
                    k = prev[k]
                return out[::-1]
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dx, y + dy)
                if self._open(x, y, dx, dy) and not blocked(self._key(x, y, dx, dy)) and n not in prev:
                    prev[n] = (x, y)
                    queue.append(n)
        return None

    def _cell(self) -> tuple[float, float, float]:
        s = min((self.W - 24) / self.CW, (self.H - 60) / self.CH)
        return s, (self.W - s * self.CW) / 2, 40.0

    def key(self, k: int) -> bool:
        m = {Qt.Key_Left: (-1, 0), Qt.Key_A: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_D: (1, 0),
             Qt.Key_Up: (0, -1), Qt.Key_W: (0, -1), Qt.Key_Down: (0, 1), Qt.Key_S: (0, 1)}.get(k)
        if m:
            self.move(*m)
            return True
        return False

    def press(self, x: float, y: float) -> None:
        s, ox, oy = self._cell()
        cx, cy = ox + (self.at[0] + 0.5) * s, oy + (self.at[1] + 0.5) * s
        dx, dy = x - cx, y - cy
        self.move(*((1 if dx > 0 else -1, 0) if abs(dx) > abs(dy) else (0, 1 if dy > 0 else -1)))

    def move(self, dx: int, dy: int) -> None:
        if self.home or self.overlay is not None or self.anim[2] < 1:
            return
        x, y = self.at
        if not self._open(x, y, dx, dy):
            return
        k = self._key(x, y, dx, dy)
        d = self.doors.get(k)
        if d and d["state"] == "locked":
            self.say("This door stays shut: find another way round.")
            self.face = "think"
            return
        if d and d["state"] == "shut":
            self._ask(d, dx, dy)
            return
        self._step(dx, dy)

    def _step(self, dx: int, dy: int) -> None:
        self.anim = [float(self.at[0]), float(self.at[1]), 0.0]
        self.at = [self.at[0] + dx, self.at[1] + dy]

    def _ask(self, d: dict[str, Any], dx: int, dy: int) -> None:
        region = min(2, d["b"][0] * 3 // self.CW)
        pool = self.questions.get(region) or self.questions[1] or self.questions[0]
        q = pool.pop(0)
        pool.append(q)
        t = self.theme()
        self._drop_card()
        box = QFrame(self)
        box.setObjectName("mzCard")
        box.setStyleSheet(f"#mzCard {{ background:{t['solid_bg']}; border:1px solid {t['accent']}; border-radius:14px; }}")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        lay.addWidget(_label(["Basics", "Core", "Advanced"][region] + " door", f"color:{t['muted']}; font-size:10.5px; font-weight:800;"))
        lay.addWidget(_label(q["q"], f"color:{t['text']}; font-size:13px; font-weight:800;"))
        right_text = q["options"][0]
        note = _label("", f"color:{t['text']}; font-size:11px;")
        buttons = []

        def pick(choice: str) -> None:
            if note.text():
                return
            ok = choice == right_text
            for b in buttons:
                _mark(b, t, "right" if b.text() == right_text else "wrong" if b.text() == choice else "")
            self.asked += 1
            self.right_first += ok
            self.answer(q["id"], ok, {"easy": 1, "medium": 2, "hard": 3}.get(q.get("level"), 1),
                        PROTOCOL_TERMS.get(q.get("protocol", ""), []))
            note.setText(("✅ " if ok else "❌ ") + q.get("why", ""))
            go = QPushButton("Through the door ›" if ok else "OK")
            go.setCursor(Qt.PointingHandCursor)
            go.setStyleSheet(f"QPushButton {{ background:{t['accent']}; color:{t['on_accent']}; border:none; border-radius:9px; "
                             "padding:6px 14px; font-size:12px; font-weight:700; }")
            go.clicked.connect(lambda: self._after(d, ok, dx, dy))
            row = QHBoxLayout()
            row.addWidget(go)
            row.addStretch(1)
            lay.addLayout(row)
            go.setFocus()
            self._place_card()

        for opt in random.sample(q["options"], len(q["options"])):
            b = _wrap_button(opt, t)
            b.clicked.connect(lambda _c=False, o=opt: pick(o))
            lay.addWidget(b)
            buttons.append(b)
        lay.addWidget(note)
        self.overlay = box
        self._place_card()
        box.show()
        box.raise_()

    def _after(self, d: dict[str, Any], ok: bool, dx: int, dy: int) -> None:
        self._drop_card()
        self.setFocus()
        if ok:
            d["state"] = "open"
            self.face = "cheer"
            self._step(dx, dy)
            return
        d["state"] = "locked"
        self.face = "think"
        if self._path(self.at[0], self.at[1], lambda k: self.doors.get(k, {}).get("state") == "locked") is None:
            d["state"] = "shut"
            self.say("No other way round here: this door will ask a different question.", 3.2)
        else:
            self.say("That door stays shut now. There's another way round.")

    def step(self, dt: float) -> None:
        if self.anim[2] < 1:
            self.anim[2] = min(1.0, self.anim[2] + dt * 7)
            if self.anim[2] >= 1 and self.at == [self.CW - 1, self.CH - 1] and not self.home:
                self.home = True
                self.face = "wave"
                QTimer.singleShot(400, lambda: self._card(
                    "GeeKOc is home!", f"{self.right_first} of {self.asked} doors opened on the first try.", "See how you did", self._done))
        self.hud(f"{self.right_first}/{self.asked} doors right")

    def _done(self) -> None:
        self._drop_card()
        self.end()

    def draw(self, p: QPainter) -> None:
        p.fillRect(QRectF(0, 0, self.W, self.H), QColor("#0b0b16"))
        s, ox, oy = self._cell()
        names, tints = ["Basics", "Core", "Advanced"], [QColor(127, 216, 255, 18), QColor(255, 196, 87, 18), QColor(255, 111, 216, 20)]
        f = QFont(p.font())
        f.setPixelSize(12)
        f.setBold(True)
        p.setFont(f)
        for i in range(3):
            x0, x1 = ox + s * (i * self.CW // 3), ox + s * ((i + 1) * self.CW // 3)
            p.fillRect(QRectF(x0, oy, x1 - x0, s * self.CH), tints[i])
            p.setPen(QColor("#a9a9c0"))
            p.drawText(QRectF(x0, oy - 22, x1 - x0, 18), Qt.AlignCenter, names[i])
        p.setPen(QPen(QColor("#6a5acd"), 2.5, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(ox, oy, s * self.CW, s * self.CH))
        for x in range(self.CW):
            for y in range(self.CH):
                if self.right[x][y] and x < self.CW - 1:
                    p.drawLine(QPointF(ox + (x + 1) * s, oy + y * s), QPointF(ox + (x + 1) * s, oy + (y + 1) * s))
                if self.down[x][y] and y < self.CH - 1:
                    p.drawLine(QPointF(ox + x * s, oy + (y + 1) * s), QPointF(ox + (x + 1) * s, oy + (y + 1) * s))
        for k, d in self.doors.items():
            if d["state"] == "open":
                continue
            (ax, ay), (bx, by) = d["a"], d["b"]
            cx, cy = ox + ((ax + bx) / 2 + 0.5) * s, oy + ((ay + by) / 2 + 0.5) * s
            horiz = k.endswith(",d")
            r = QRectF(cx - s / 2 + 5, cy - 4, s - 10, 8) if horiz else QRectF(cx - 4, cy - s / 2 + 5, 8, s - 10)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#f87171" if d["state"] == "locked" else "#ffc457"))
            p.drawRoundedRect(r, 4, 4)
        f.setPixelSize(int(s * 0.62))
        p.setFont(f)
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(ox + (self.CW - 1) * s, oy + (self.CH - 1) * s, s, s), Qt.AlignCenter, "\U0001f3e0")
        k = self.anim[2]
        px = self.anim[0] + (self.at[0] - self.anim[0]) * k
        py = self.anim[1] + (self.at[1] - self.anim[1]) * k
        _oc(p, self.face, ox + (px + 0.5) * s, oy + (py + 0.5) * s, s * 1.3)


GAMES = {"rise": Rise, "maze": GoHome}
assert set(GAMES) <= set(gems.GAME_IDS)
