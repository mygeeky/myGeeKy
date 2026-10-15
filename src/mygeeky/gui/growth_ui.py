"""Widgets for the 🌱 Grow planet (Rising Skills, Protocols, Learn, Wins, Collaborators)
and the 🎯 Chances planet (Verified jobs, Funding, Conferences).

Every card has a 👍 and a 👎 (ThumbBar): they teach your model (taste.py) what to show
you more and less of. Everything shown comes from a list someone else wrote (the
curated lists, other people's beacons, OpenAlex), so it's always plain text or escaped.
Nothing here touches the network: the panel runs the work in the background
(gui/app.py) and hands the results back."""
from __future__ import annotations

import html
from typing import Any, Callable

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from .signals_ui import _button_style, _muted

JOB_EMOJI = {"phd": "🎓", "postdoc": "🔬", "master": "📘", "job": "💼", "internship": "🧪", "fellowship": "🏅",
             "faculty": "🏛", "engineer": "🛠"}
WIN_EMOJI = {"stars": "⭐", "forks": "🍴", "citations": "📚"}


def _label(text: str, style: str, rich: bool = False, wrap: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.RichText if rich else Qt.PlainText)
    lbl.setWordWrap(wrap)
    # wrapping text may shrink to any width (it wraps); a one-line chip keeps its own width, or the layout
    # squeezes it away to nothing
    lbl.setSizePolicy(QSizePolicy.Ignored if wrap else QSizePolicy.Fixed, QSizePolicy.Preferred)
    lbl.setStyleSheet(style)
    return lbl


def _card_style(name: str, theme: dict[str, Any], hover: bool = False) -> str:
    out = f"QFrame#{name} {{ background:{theme['card_bg']}; border-radius:10px; }}"
    if hover:
        out += f"QFrame#{name}:hover {{ background:{theme['btn_bg']}; }}"
    return out


def deadline_text(days: int | None) -> str:
    if days is None:
        return ""
    if days <= 0:
        return "closes today"
    if days == 1:
        return "closes tomorrow"
    if days <= 60:
        return f"closes in {days} days"
    return f"closes in {days // 30} months"


def mode_style(theme: dict[str, Any], active: bool) -> str:
    """A written-out section pill. Kept for rows that still name every section, such as 🛒 Market's three."""
    return (f"QPushButton {{ background:{theme['tab_active'] if active else theme['card_bg']}; "
            f"color:{theme['text']}; border:none; border-radius:8px; padding:4px 10px; "
            f"font-size:11px; font-weight:{'700' if active else '400'}; }}")


def segment_track(theme: dict[str, Any]) -> str:
    """The sunken strip the sections sit in, so the row reads as one control rather than loose buttons."""
    return f"QWidget#modeRow {{ background:{theme['card_bg']}; border-radius:11px; }}"


def segment_style(theme: dict[str, Any], active: bool) -> str:
    """One section in that strip: its icon, and its name too when it is the one you are in.

    The ones you are not in are left transparent -- the strip behind them is what groups them -- and dimmed
    with the muted text colour rather than an opacity, so they stay legible in the light theme as well."""
    shape = "border:none; border-radius:9px; font-size:11px; text-align:center;"
    if active:
        return (f"QPushButton {{ {shape} background:{theme['tab_active']}; color:{theme['text']}; "
                "padding:5px 11px; font-weight:700; }")
    return (f"QPushButton {{ {shape} background:transparent; color:{theme['muted']}; padding:5px 8px; }}"
            f"QPushButton:hover {{ {shape} background:{theme['btn_hover']}; color:{theme['text']}; "
            "padding:5px 8px; }")


class FlowLayout(QLayout):
    """Lays its widgets out left to right and starts a new line when the next one wouldn't fit, so a
    row of buttons never makes the panel wider than it is (Qt's own flow-layout example)."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 4) -> None:
        super().__init__(parent)
        self._items: list = []
        self._gap = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, i: int):  # noqa: N802
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i: int):  # noqa: N802
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientations(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._place(QRect(0, 0, width, 0), move=False)

    def setGeometry(self, rect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._place(rect, move=True)

    def sizeHint(self):  # noqa: N802
        return self.minimumSize()

    def minimumSize(self):  # noqa: N802
        size = QSize()
        for item in self._items:                 # as narrow as its widest single button, never wider
            size = size.expandedTo(item.minimumSize())
        return size

    def _place(self, rect, move: bool) -> int:
        x, y, line = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            w = min(hint.width(), rect.width())
            if x + w > rect.x() + rect.width() and line > 0:
                x, y = rect.x(), y + line + self._gap
                line = 0
            if move:
                item.setGeometry(QRect(QPoint(x, y), QSize(w, hint.height())))
            x += w + self._gap
            line = max(line, hint.height())
        return y + line - rect.y()


class FlowRow(QWidget):
    """Buttons (modes, reviewed protocols…) that wrap onto the next line instead of making the panel wider."""

    def __init__(self) -> None:
        super().__init__()
        self._flow = FlowLayout(self)
        sp = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def add(self, w: QWidget) -> None:
        self._flow.addWidget(w)

    def finish(self) -> None:
        """Nothing left to do: lines are worked out from the width (kept so callers stay the same)."""

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._flow.heightForWidth(width)


class ThumbBar(QWidget):
    """👍 / 👎. `on_vote(up)` returns the vote now in place (1, -1 or 0), which redraws the bar.
    Pressing the same thumb again takes the vote back."""

    def __init__(self, vote: int, theme: dict[str, Any], on_vote: Callable[[bool], int],
                 up_tip: str = "More like this", down_tip: str = "Not for me: show less like this") -> None:
        super().__init__()
        self.theme = theme
        self.on_vote = on_vote
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.up = QPushButton("👍")
        self.down = QPushButton("👎")
        for b, tip, up in ((self.up, up_tip, True), (self.down, down_tip, False)):
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedSize(26, 22)
            b.clicked.connect(lambda checked=False, u=up: self._press(u))
            lay.addWidget(b)
        self.vote = vote
        self._paint()

    def _press(self, up: bool) -> None:
        try:
            self.vote = int(self.on_vote(up))
        except Exception:
            return
        self._paint()

    def _paint(self) -> None:
        for b, on in ((self.up, self.vote > 0), (self.down, self.vote < 0)):
            b.setStyleSheet(f"QPushButton {{ background:{self.theme['section_btn'] if on else 'transparent'}; "
                            f"border:none; border-radius:7px; font-size:11px; }}"
                            f"QPushButton:hover {{ background:{self.theme['btn_hover']}; }}")


# --------------------------------------------------------------------------- 🌱 Grow
class SkillCard(QFrame):
    """A rising skill you don't show yet: why it's suggested, examples, start a path."""

    def __init__(self, s: dict[str, Any], theme: dict[str, Any], on_vote: Callable[[bool], int],
                 on_path: Callable[[str], None], on_open: Callable[[str], Any], path_started: bool,
                 strength: bool = False) -> None:
        super().__init__()
        self.setObjectName("skillCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)
        head = QHBoxLayout()
        head.setSpacing(6)
        badge = "📈 rising" if s.get("rising") else ""
        title = _label(f"<b>{html.escape(s['name'])}</b>"
                       + (f" <span style='color:{theme['good']}; font-size:10px'>{badge}</span>" if badge else ""),
                       f"color:{theme['text']}; font-size:12px; background:transparent;", rich=True, wrap=False)
        head.addWidget(title, 1)
        if not strength:
            head.addWidget(ThumbBar(s.get("vote", 0), theme, on_vote,
                                    "Yes, I want to learn this", "Not for me: hide this skill"))
        lay.addLayout(head)
        why = "; ".join(s.get("reasons") or [])
        why += ("; you already show it" if strength else "; not in your profile yet") if why else ""
        lay.addWidget(_label(why, _muted(theme, 10.5)))
        if s.get("examples"):
            links = " · ".join(f"<a href='{html.escape(e['url'], quote=True)}' style='color:{theme['link']}'>"
                               f"{html.escape(e['title'][:48])}</a>" for e in s["examples"][:2])
            ex = _label("e.g. " + links, _muted(theme, 10), rich=True)
            ex.setOpenExternalLinks(False)
            ex.linkActivated.connect(on_open)
            lay.addWidget(ex)
        if not strength:
            row = QHBoxLayout()
            btn = QPushButton("✓ In your protocols" if path_started else "🧭 Make it a protocol")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setEnabled(not path_started)
            btn.setStyleSheet(_button_style(theme))
            btn.clicked.connect(lambda: on_path(s["name"]))
            row.addWidget(btn)
            row.addStretch(1)
            lay.addLayout(row)
        self.setStyleSheet(_card_style("skillCard", theme))


STATUS = {"done": ("✅", "Done"), "known": ("🎓", "You know this"), "current": ("▶", "Start here"),
          "todo": ("○", "")}
SOURCE = {"reviewed": "✓ Reviewed", "auto": "Auto-built, not reviewed", "mine": "Yours"}
STATUS_ICON_TEXT = {"done": "✓", "known": "🎓", "current": "▶", "todo": "○"}
KIND_COLOR = {"repo": "#a78bfa", "article": "#38bdf8", "book": "#f59e0b", "course": "#34d399", "tutorial": "#34d399",
              "video": "#f472b6", "protocol": "#2dd4bf", "guide": "#fb923c", "website": "#94a3b8",
              "search": "#94a3b8"}
LEVEL_COLOR = {"easy": "#34d399", "medium": "#38bdf8", "tricky": "#fb923c"}


def _small_button(text: str, tip: str, theme: dict[str, Any], on_click: Callable[[], Any]) -> QPushButton:
    b = QPushButton(text)
    b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    b.setFixedHeight(22)
    b.setStyleSheet(f"QPushButton {{ background:transparent; color:{theme['muted']}; border:none; padding:0 4px; "
                    f"font-size:11px; }} QPushButton:hover {{ color:{theme['text']}; }}")
    b.clicked.connect(lambda checked=False: on_click())
    return b


def _pill_button(text: str, tip: str, theme: dict[str, Any], on_click: Callable[[], Any], accent: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(_button_style(theme, accent=accent))
    b.clicked.connect(lambda checked=False: on_click())
    return b


def qcolor(css: str):
    """A QColor from a theme colour. Themes use CSS "rgba(r, g, b, a)" (a 0-255), which QColor can't read
    (it would paint black)."""
    import re as _re
    from PySide6.QtGui import QColor
    m = _re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)", css or "")
    if not m:
        return QColor(css)
    a = float(m.group(4)) if m.group(4) is not None else 255.0
    return QColor(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(a if a > 1 else a * 255))


def _status_color(theme: dict[str, Any], status: str) -> str:
    return {"done": theme["good"], "known": theme["good"], "current": theme["accent"]}.get(status, theme["muted"])


class StepBar(QWidget):
    """The protocol as a road map: numbered circles joined by a line, green when done or known, the
    accent colour where to start, grey still to do. The chosen step makes room for itself -- its column
    stretches to show its whole name (bold, up to two lines) -- and the others close up around it with a
    short name, or just their number when there's no room. Click a circle (or its name) to show that step."""

    R = 11.0             # circle radius
    MIN_COL = 30.0       # the narrowest a step's column gets (a circle and a little air)
    LABEL_MIN = 40.0     # below this, an unchosen step shows its number only

    def __init__(self, steps: list[Any], selected: str, theme: dict[str, Any], on_select: Callable[[str], None]) -> None:
        super().__init__()
        self.steps, self.selected, self.theme, self.on_select = steps, selected, theme, on_select
        self.setMinimumHeight(70)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click a step to see it")

    def _fonts(self):
        from PySide6.QtGui import QFont, QFontMetrics
        small = QFont(self.font())
        small.setPointSizeF(7.5)
        bold = QFont(small)
        bold.setBold(True)
        bold.setPointSizeF(8.5)
        return small, QFontMetrics(small), bold, QFontMetrics(bold)

    def columns(self) -> list[tuple[float, float]]:
        """(left, width) of each step's column: the chosen one as wide as its name needs (up to two lines),
        the rest sharing what's left equally."""
        n = len(self.steps)
        if not n:
            return []
        w = float(max(self.width(), 1))
        if n == 1:
            return [(0.0, w)]
        _, _, _, bfm = self._fonts()
        chosen = next((i for i, s in enumerate(self.steps) if s.id == self.selected), 0)
        room = w - (n - 1) * self.MIN_COL                      # the most the chosen one may take
        even = w / n
        want = bfm.horizontalAdvance(self.steps[chosen].title) + 12
        if want > room:                                        # too long for one line: two lines, half as wide
            want = max(want / 2 + 12, min(room, 120.0))
        chosen_w = max(even, min(want, room))
        other_w = (w - chosen_w) / (n - 1)
        cols, x = [], 0.0
        for i in range(n):
            cw = chosen_w if i == chosen else other_w
            cols.append((x, cw))
            x += cw
        return cols

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QPainter, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t, r, y = self.theme, self.R, 18.0
        small, fm, bold, bfm = self._fonts()
        cols = self.columns()
        xs = [left + cw / 2 for left, cw in cols]
        for i in range(len(xs) - 1):                       # the road between steps: green once the left one is done
            left_done = self.steps[i].status in ("done", "known")
            p.setPen(QPen(qcolor(t["good"] if left_done else t["btn_bg"]), 3))
            p.drawLine(int(xs[i] + r), int(y), int(xs[i + 1] - r), int(y))
        for (left, cw), x, st in zip(cols, xs, self.steps):
            chosen = st.id == self.selected
            c = qcolor(_status_color(t, st.status))
            if chosen:
                p.setPen(QPen(qcolor(t["text"]), 2))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QRectF(x - r - 4, y - r - 4, 2 * r + 8, 2 * r + 8))
            p.setPen(Qt.NoPen)
            p.setBrush(c if st.status != "todo" else qcolor(t["btn_hover"]))
            p.drawEllipse(QRectF(x - r, y - r, 2 * r, 2 * r))
            p.setPen(qcolor("#ffffff" if st.status != "todo" else t["text"]))
            p.setFont(bold)
            p.drawText(QRectF(x - r, y - r, 2 * r, 2 * r), Qt.AlignCenter,
                       "✓" if st.status in ("done", "known") else str(st.number))
            box = QRectF(left + 2, y + r + 7, cw - 4, 30)
            if chosen:                                     # the whole name, bold, up to two lines
                p.setFont(bold)
                p.setPen(qcolor(t["text"]))
                p.drawText(box, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, st.title)
            elif cw >= self.LABEL_MIN:                     # a short name in the space left
                p.setFont(small)
                p.setPen(qcolor(t["muted"]))
                p.drawText(box, Qt.AlignHCenter | Qt.AlignTop, fm.elidedText(st.title, Qt.ElideRight, int(cw - 6)))
        p.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        x = event.position().x()
        for (left, cw), st in zip(self.columns(), self.steps):
            if left <= x < left + cw:
                self.on_select(st.id)
                return


class StepDots(QWidget):
    """A folded protocol's progress in one glance: one small dot per step."""

    def __init__(self, steps: list[Any], theme: dict[str, Any]) -> None:
        super().__init__()
        self.steps, self.theme = steps, theme
        self.setFixedSize(12 * len(steps) + 2, 12)

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        for i, st in enumerate(self.steps):
            p.setBrush(qcolor(_status_color(self.theme, st.status) if st.status != "todo" else self.theme["btn_hover"]))
            p.drawEllipse(2 + 12 * i, 2, 8, 8)
        p.end()


class ResourceCard(QFrame):
    """One link inside a step: a coloured badge for what it is (GitHub repo, paper, free book…), its name,
    the facts that help you choose (owner, ⭐ stars, language, year, citations, where it lives), one or
    two lines on what it is, and one clear button."""

    def __init__(self, res: Any, theme: dict[str, Any], on_open: Callable[[str], Any],
                 thumbs: QWidget | None = None) -> None:
        super().__init__()
        self.setObjectName("resourceCard")
        color = KIND_COLOR.get(res.kind, theme["muted"])
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        icon = QLabel(res.icon)
        icon.setFixedSize(34, 34)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(f"background:{color}33; border-radius:9px; font-size:17px;")
        outer.addWidget(icon, 0, Qt.AlignTop)
        body = QVBoxLayout()
        body.setSpacing(2)
        top = QHBoxLayout()
        top.addWidget(_label(res.label.upper(), f"color:{color}; font-size:9px; font-weight:700; letter-spacing:0.6px; "
                                                "background:transparent;", wrap=False), 1)
        if thumbs is not None:
            top.addWidget(thumbs, 0, Qt.AlignRight)
        body.addLayout(top)
        title = _label(f"<b>{html.escape(res.title)}</b>", f"color:{theme['text']}; font-size:12px; background:transparent;",
                       rich=True)
        title.setCursor(Qt.PointingHandCursor)
        title.mousePressEvent = lambda ev: on_open(res.url)  # noqa: ARG005
        body.addWidget(title)
        if res.subtitle:
            body.addWidget(_label(res.subtitle, _muted(theme, 10)))
        if res.blurb:
            body.addWidget(_label(res.blurb, f"color:{theme['text']}; font-size:10.5px; background:transparent;"))
        go = QPushButton(f"{res.action}  ↗")
        go.setCursor(Qt.PointingHandCursor)
        go.setToolTip(res.url)
        go.setStyleSheet(f"QPushButton {{ background:{color}26; color:{theme['text']}; border:none; border-radius:8px; "
                         f"padding:4px 10px; font-size:10.5px; font-weight:600; }} QPushButton:hover {{ background:{color}55; }}")
        go.clicked.connect(lambda checked=False: on_open(res.url))
        row = QHBoxLayout()
        row.addWidget(go)
        row.addStretch(1)
        body.addLayout(row)
        outer.addLayout(body, 1)
        self.setStyleSheet(f"QFrame#resourceCard {{ background:{theme['btn_bg']}; border-radius:10px; }}")


class AnswerRow(QFrame):
    """One answer: a letter in a badge, and the answer itself as text that *wraps*.

    It is deliberately not a QPushButton. A button is never narrower than its own text, so four long
    answers would force the whole panel wider than it is and squeeze everything in it. A frame with a
    wrapping label inside can be as narrow as the panel and simply grow taller."""

    def __init__(self, letter: str, text: str, theme: dict[str, Any], state: str,
                 on_pick: Callable[[], None] | None) -> None:
        super().__init__()
        self.setObjectName("answerRow")
        edge = {"right": theme["good"], "wrong": theme["bad"]}.get(state, "transparent")
        fill = {"right": f"{theme['good']}26", "wrong": f"{theme['bad']}26"}.get(state, theme["btn_bg"])
        lay = QHBoxLayout(self)
        lay.setContentsMargins(9, 8, 10, 8)
        lay.setSpacing(9)
        badge = _label(letter, f"color:{theme['text']}; font-size:11px; font-weight:800; "
                               f"background:{theme['card_bg']}; border-radius:9px;", wrap=False)
        badge.setFixedSize(20, 20)
        badge.setAlignment(Qt.AlignCenter)
        lay.addWidget(badge, 0, Qt.AlignTop)
        lay.addWidget(_label(text, f"color:{theme['text']}; font-size:11.5px; background:transparent;"), 1)
        if state in ("right", "wrong"):
            lay.addWidget(_label("✓" if state == "right" else "✗",
                                 f"color:{theme['good'] if state == 'right' else theme['bad']}; font-size:12px; "
                                 "font-weight:800; background:transparent;", wrap=False), 0, Qt.AlignTop)
        self.setStyleSheet(f"QFrame#answerRow {{ background:{fill}; border:1px solid {edge}; border-radius:9px; }}"
                           + (f"QFrame#answerRow:hover {{ background:{theme['tab_active']}; }}" if on_pick else ""))
        if on_pick is not None:
            self.setCursor(Qt.PointingHandCursor)
            self._on_pick = on_pick

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if getattr(self, "_on_pick", None) is not None:
            self._on_pick()


class QuestionCard(QFrame):
    """One quiz question, as big and plain as it can be: which step it belongs to and how hard it is,
    the question (with its code set apart, in a monospace block), and four answers as full-width
    buttons. Once you answer, the one you picked turns green or red, the right one is always marked,
    and the card opens up: *why* that answer is right, the source it was written from with the sentence
    quoted from it, and a 🚩 if the question itself looks wrong."""

    def __init__(self, q: Any, theme: dict[str, Any], on_pick: Callable[[int], None],
                 on_open: Callable[[str], Any], on_flag: Callable[[], None] | None = None,
                 locked: bool = False) -> None:
        super().__init__()
        self.setObjectName("questionCard")
        self.question = q
        color = LEVEL_COLOR.get(q.level, theme["accent"])
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)
        # ---- where it comes from, and how hard
        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(_label(f"{q.number} of {q.of}", _muted(theme, 10), wrap=False))
        top.addWidget(_label(f"{q.level_icon} {q.level_label.upper()}",
                             f"color:{color}; font-size:9px; font-weight:700; letter-spacing:0.6px; "
                             f"background:{color}22; border-radius:6px; padding:2px 6px;", wrap=False))
        step = _label(f"{q.kind_icon} {q.stage_title}", _muted(theme, 10))
        step.setToolTip(q.stage_title)
        top.addWidget(step, 1)
        if on_flag is not None:
            top.addWidget(_small_button("🚩" if not q.flagged else "🚩 flagged",
                                        "This question looks wrong: tell the maker", theme, on_flag), 0, Qt.AlignRight)
        outer.addLayout(top)
        outer.addWidget(_label(q.text, f"color:{theme['text']}; font-size:13px; font-weight:600; "
                                       "background:transparent;"))
        if q.code:
            code = _label(q.code, f"color:{theme['text']}; font-family:Consolas,'Courier New',monospace; "
                                  f"font-size:11px; background:{theme['btn_bg']}; border-radius:8px; padding:8px;")
            code.setTextInteractionFlags(Qt.TextSelectableByMouse)
            outer.addWidget(code)
        # ---- the four answers, each one as wide as the panel and as tall as its own text needs
        self.answers: list[AnswerRow] = []
        for i, option in enumerate(q.options):
            if q.answered:
                state = "right" if i == q.answer else ("wrong" if i == q.picked else "")
            else:
                state = ""
            row = AnswerRow(chr(65 + i), option, theme, state,
                            None if (q.answered or locked) else (lambda i=i: on_pick(i)))
            self.answers.append(row)
            outer.addWidget(row)
        # ---- after you answer: right or wrong, why, and the source
        if q.answered:
            verdict = "✓ Right" if q.right else "✗ Not this one"
            good = theme["good"] if q.right else theme["bad"]
            outer.addWidget(_label(verdict, f"color:{good}; font-size:12px; font-weight:700; background:transparent;",
                                   wrap=False))
            if q.why:
                outer.addWidget(_label(q.why, f"color:{theme['text']}; font-size:11px; background:transparent;"))
            res = q.source
            if res is not None:
                if q.source_quote:
                    outer.addWidget(_label(f"“{q.source_quote}”",
                                           f"color:{theme['muted']}; font-size:10.5px; font-style:italic; "
                                           f"background:{theme['btn_bg']}; border-radius:8px; padding:7px;"))
                outer.addWidget(_label("WHERE THIS COMES FROM",
                                       f"color:{theme['muted']}; font-size:9px; font-weight:700; "
                                       "letter-spacing:0.6px; background:transparent;", wrap=False))
                outer.addWidget(ResourceCard(res, theme, on_open))
        self.setStyleSheet(f"QFrame#questionCard {{ background:{theme['card_bg']}; border-radius:12px; }}")


class ScoreRing(QWidget):
    """Your score as a ring: the share you got right, in green when you passed, with the number inside."""

    def __init__(self, score: float, theme: dict[str, Any], passed: bool, size: int = 110) -> None:
        super().__init__()
        self.score, self.theme, self.passed = max(0.0, min(1.0, score)), theme, passed
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QFont, QPainter, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height())
        box = QRectF(7, 7, side - 14, side - 14)
        p.setPen(QPen(qcolor(self.theme["btn_bg"]), 9))
        p.drawArc(box, 0, 360 * 16)
        colour = qcolor(self.theme["good"] if self.passed else self.theme["accent"])
        pen = QPen(colour, 9)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(box, 90 * 16, -int(360 * 16 * self.score))
        p.setPen(qcolor(self.theme["text"]))
        f = QFont()
        f.setPointSizeF(max(11.0, side / 5.2))
        f.setBold(True)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignCenter, f"{round(self.score * 100)}%")


class ResultView(QWidget):
    """What you scored: the ring, how each step and each level went, your best score, and what's next."""

    def __init__(self, attempt: Any, theme: dict[str, Any], best_before: float = 0.0) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(ScoreRing(attempt.score, theme, attempt.passed), 0, Qt.AlignTop)
        side = QVBoxLayout()
        side.setSpacing(3)
        side.addWidget(_label(f"{attempt.right} of {attempt.total} right",
                              f"color:{theme['text']}; font-size:14px; font-weight:700; background:transparent;"))
        if attempt.perfect:
            side.addWidget(_label("🏴 100%: a clean sweep.",
                                  f"color:{theme['good']}; font-size:11.5px; background:transparent;"))
        elif attempt.passed:
            side.addWidget(_label("Passed. Take it again tomorrow to push it higher.",
                                  f"color:{theme['good']}; font-size:11.5px; background:transparent;"))
        else:
            side.addWidget(_label("Not yet. The steps below show where to look; the links under each one "
                                  "are a good place to start.", _muted(theme, 11)))
        if attempt.improved and best_before > 0:
            side.addWidget(_label(f"Your best for this protocol: {round(attempt.best * 100)}% "
                                  f"(was {round(best_before * 100)}%). Only your best counts.",
                                  _muted(theme, 10.5)))
        else:
            side.addWidget(_label(f"Your best for this protocol: {round(attempt.best * 100)}%. Only your best counts.",
                                  _muted(theme, 10.5)))
        head.addLayout(side, 1)        # no stretch: the card is only as tall as what it says
        outer.addLayout(head)
        if attempt.by_level:
            row = FlowRow()
            for lv in attempt.by_level:
                colour = LEVEL_COLOR.get(lv["level"], theme["muted"])
                row.add(_label(f"{lv['icon']} {lv['label']} {lv['right']}/{lv['total']}",
                               f"color:{colour}; font-size:10px; font-weight:600; background:{colour}22; "
                               "border-radius:7px; padding:3px 7px;", wrap=False))
            row.finish()
            outer.addWidget(row)
        if len(attempt.by_stage) > 1:
            outer.addWidget(_label("BY STEP", f"color:{theme['muted']}; font-size:9px; font-weight:700; "
                                              "letter-spacing:0.6px; background:transparent;", wrap=False))
            for g in attempt.by_stage:
                ok = g["right"] == g["total"]
                mark = "✓" if ok else f"{g['right']}/{g['total']}"
                colour = theme["good"] if ok else (theme["muted"] if g["right"] else theme["bad"])
                line = QHBoxLayout()
                line.addWidget(_label(g["title"], f"color:{theme['text']}; font-size:11px; background:transparent;"), 1)
                line.addWidget(_label(mark, f"color:{colour}; font-size:11px; font-weight:700; background:transparent;",
                                      wrap=False), 0, Qt.AlignRight)
                holder = QWidget()
                holder.setLayout(line)
                holder.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                outer.addWidget(holder)
        outer.addStretch(1)              # any spare room collects at the bottom, not between the rows


class QuestionDots(QWidget):
    """One dot per question in this attempt: the ones you answered, right or wrong, the one you're on
    (ringed), and the ones still to come. It is the only progress bar a ten-question quiz needs."""

    DOT = 9
    GAP = 7

    def __init__(self, questions: list[Any], at: int, theme: dict[str, Any], marked: bool = False) -> None:
        super().__init__()
        self.questions, self.at, self.theme, self.marked = questions, at, theme, marked
        self.setFixedHeight(self.DOT + 8)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QPainter, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        n = max(1, len(self.questions))
        step = min(self.DOT + self.GAP, max(self.DOT + 2, self.width() // n))
        x = 0
        for i, q in enumerate(self.questions):
            if q.answered:
                colour = qcolor(self.theme["good"] if q.right else self.theme["bad"]) if self.marked \
                    else qcolor(self.theme["accent"])
            else:
                colour = qcolor(self.theme["btn_bg"])
            p.setPen(Qt.NoPen)
            p.setBrush(colour)
            top = (self.height() - self.DOT) // 2
            p.drawEllipse(x, top, self.DOT, self.DOT)
            if i == self.at and not self.marked:                 # where you are now
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(qcolor(self.theme["text"]), 1.6))
                p.drawEllipse(x - 3, top - 3, self.DOT + 6, self.DOT + 6)
            x += step


class QuizRunView(QFrame):
    """A whole quiz attempt, drawn inside the 🏆 Quiz tab: which protocol and step it is for, a dot per
    question, the question itself (QuestionCard), and one button to go on. When it's finished the same
    frame shows the result (ResultView) and what to do next.

    It draws; it decides nothing. The panel owns the answers and hands them in: `state` carries the drawn
    quiz, where you are, and the attempt once it has been marked."""

    def __init__(self, state: dict[str, Any], theme: dict[str, Any], on_pick: Callable[[int], None],
                 on_next: Callable[[], None], on_flag: Callable[[], None], on_open: Callable[[str], Any],
                 on_close: Callable[[], None], on_share: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.setObjectName("quizRun")
        quiz, at = state["quiz"], state["at"]
        attempt = state.get("attempt")
        questions = quiz.questions
        q = questions[min(at, len(questions) - 1)]
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 9, 10, 10)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(6)
        title = ("Your score" if attempt else f"Question {q.number} of {q.of}")
        head.addWidget(_label(f"<b>🏆 {html.escape(quiz.title)}</b><br>"
                              f"<span style='color:{theme['muted']}; font-size:10px'>{title}"
                              + (f" · {html.escape(state['stage_title'])}" if state.get("stage_title") else "")
                              + "</span>",
                              f"color:{theme['text']}; font-size:12.5px; background:transparent;", rich=True), 1)
        head.addWidget(_small_button("✕", "Leave this quiz", theme, on_close), 0, Qt.AlignTop)
        lay.addLayout(head)
        lay.addWidget(QuestionDots(questions, at, theme, marked=attempt is not None))

        if attempt is None:
            lay.addWidget(QuestionCard(q, theme, on_pick, on_open, on_flag))
            row = QHBoxLayout()
            left = len(questions) - at - (1 if q.answered else 0)
            row.addWidget(_label("Pick an answer." if not q.answered
                                 else (f"{left} to go." if left else "That's the last one."),
                                 _muted(theme, 10.5)), 1)
            nxt = _pill_button("See your score" if at == len(questions) - 1 else "Next question →",
                               "", theme, on_next, accent=True)
            nxt.setEnabled(q.answered)
            row.addWidget(nxt, 0, Qt.AlignRight)
            lay.addLayout(row)
        else:
            lay.addWidget(ResultView(attempt, theme, state.get("best_before", 0.0)))
            if state.get("stage_title"):
                lay.addWidget(_label("This step is marked as known." if attempt.passed
                                     else "Not yet: this step stays on your list.", _muted(theme, 10.5)))
            else:
                lay.addWidget(_label("One attempt a day, so a score means something. Only your best counts.",
                                     _muted(theme, 10.5)))
            row = FlowRow()
            row.add(_pill_button("← Back to the quizzes", "", theme, on_close, accent=True))
            if on_share is not None and attempt.score > 0:
                row.add(_pill_button("🌍 Show my result",
                                     "Choose whether your name and score appear on mygeeky.org", theme, on_share))
            row.finish()
            lay.addWidget(row)
            lay.addWidget(_label("Every question above came from one of this protocol's own links. Open one "
                                 "from the card to read more.", _muted(theme, 10)))
        self.setStyleSheet(_card_style("quizRun", theme))


class QuizCard(QFrame):
    """One protocol's quiz, in the 🏆 Quiz tab: what its bank holds, your best score, and the button to
    take it. A protocol you haven't started yet says so, and starting it is one press."""

    def __init__(self, row: dict[str, Any], theme: dict[str, Any], on_take: Callable[[], None],
                 on_start: Callable[[], None], on_share: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.setObjectName("quizCard")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 9, 10, 9)
        outer.setSpacing(10)
        score = float(row.get("score") or 0.0)
        got = bool(row.get("best"))
        colour = theme["good"] if score >= 1.0 else (theme["good"] if score >= row.get("pass_mark", 0.75)
                                                     else theme["accent"])
        if got:
            ring = ScoreRing(score, theme, score >= row.get("pass_mark", 0.75), size=58)
            outer.addWidget(ring, 0, Qt.AlignTop)
        else:
            mark = _label("🏆", f"background:{theme['btn_bg']}; border-radius:14px; font-size:19px;", wrap=False)
            mark.setFixedSize(46, 46)
            mark.setAlignment(Qt.AlignCenter)
            outer.addWidget(mark, 0, Qt.AlignTop)
        body = QVBoxLayout()
        body.setSpacing(3)
        body.addWidget(_label(f"<b>{html.escape(row['title'])}</b>",
                              f"color:{theme['text']}; font-size:12.5px; background:transparent;", rich=True))
        counts = row.get("counts") or {}
        mix = " · ".join(f"{counts.get(lv, 0)} {lv}" for lv in ("easy", "medium", "tricky") if counts.get(lv))
        line = f"{counts.get('total', 0)} questions" + (f" ({mix})" if mix else "")
        if got:
            line += f" · best {round(score * 100)}%" + (" 🏴" if score >= 1.0 else "")
        if row.get("flagged"):
            line += f" · {row['flagged']} flagged by you"
        body.addWidget(_label(line, _muted(theme, 10.5)))
        row_buttons = FlowRow()
        if row.get("can_try"):
            asked = min(int(row.get("per_attempt") or 10), counts.get("total", 0))
            row_buttons.add(_pill_button(f"🏁 Take the quiz ({asked} question{'s' if asked != 1 else ''})",
                                         "Drawn at random: half basics, then applied, and a few real pitfalls",
                                         theme, on_take, accent=not got))
        elif not row.get("mine"):
            row_buttons.add(_pill_button("🧭 Start this protocol",
                                         "Keep it in 🧭 Protocols, then its quiz is yours to take", theme, on_start))
        if got and on_share is not None:
            row_buttons.add(_pill_button("🌍 Show my result",
                                         "Choose whether your name and score appear on mygeeky.org", theme, on_share))
        row_buttons.finish()
        body.addWidget(row_buttons)
        # a wrapping sentence can't live in a row of buttons (it would be squeezed to nothing): its own line
        if row.get("mine") and not row.get("can_try") and row.get("why_not"):
            body.addWidget(_label(row["why_not"], _muted(theme, 10)))
        outer.addLayout(body, 1)
        self.setStyleSheet(_card_style("quizCard", theme))


class ProtocolCard(QFrame):
    """A protocol. Folded, it's one line: its name, a dot per step and how far you are. Open, it shows its
    steps as a bar of circles (StepBar) and one step at a time: what kind of step it is, where you stand
    and why, what you can do (check, done), and its resources as cards. In edit mode every stage and link
    can be moved, renamed, added or removed.

    act(action, *args) changes the protocol (see app.protocol_action); on_check(stage) opens the level
    check; on_add_link(stage id) and on_rename(stage) ask for text; on_publish() sends it to the maker;
    on_toggle() opens or folds it; on_select(step id) shows another step.

    `quiz` (app.quiz_state) adds the quiz row: how many questions this protocol has, your best score, and
    🏁 Take the quiz -- or why you can't right now (one attempt a day). on_share() opens the choice to show
    a score on mygeeky.org, which is off until you ask for it."""

    def __init__(self, p: dict[str, Any], theme: dict[str, Any], editing: bool, act: Callable[..., Any],
                 on_check: Callable[[dict[str, Any]], None], on_open: Callable[[str], Any],
                 on_edit: Callable[[], None], on_publish: Callable[[], None],
                 on_add_link: Callable[[str], None], on_rename: Callable[[dict[str, Any]], None],
                 on_add_stage: Callable[[], None], vote_item: Callable[[dict[str, Any]], Callable[[bool], int]],
                 vote_of: Callable[[dict[str, Any]], int], is_open: bool = True, selected: str = "",
                 on_toggle: Callable[[], None] | None = None, on_select: Callable[[str], None] | None = None,
                 quiz: dict[str, Any] | None = None, on_quiz: Callable[[], None] | None = None,
                 on_share: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.setObjectName("protocolCard")
        self.protocol = p
        self.theme = theme
        self.editing = editing
        self.act = act
        self.on_check = on_check
        self.on_open = on_open
        self.on_add_link = on_add_link
        self.on_rename = on_rename
        self.vote_item = vote_item
        self.vote_of = vote_of
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)
        steps = p.get("steps") or []
        src = p.get("source", "mine")
        badge = SOURCE.get(src, "")
        if src == "mine" and p.get("based_on"):
            badge += " · changed from a reviewed one"
        badge_color = theme["good"] if src == "reviewed" else theme["muted"]
        flag = "🏁" if p["finished"] else "🧭"

        head = QHBoxLayout()
        head.setSpacing(6)
        name = _label(f"<b>{flag} {html.escape(p['title'])}</b><br>"
                      f"<span style='color:{badge_color}; font-size:10px'>{html.escape(badge)}</span>",
                      f"color:{theme['text']}; font-size:12.5px; background:transparent;", rich=True)
        head.addWidget(name, 1)
        if not is_open:
            head.addWidget(StepDots(steps, theme), 0, Qt.AlignVCenter)
        head.addWidget(_label(f"{p['done']}/{p['total']}", _muted(theme, 10.5), wrap=False), 0, Qt.AlignVCenter)
        if on_toggle:
            head.addWidget(_small_button("▾" if is_open else "▸", "Fold" if is_open else "Open this protocol", theme,
                                         on_toggle), 0, Qt.AlignVCenter)
        lay.addLayout(head)
        if on_toggle and not is_open:
            for w in (name,):
                w.setCursor(Qt.PointingHandCursor)
                w.mousePressEvent = lambda ev: on_toggle()  # noqa: ARG005
            self.setStyleSheet(_card_style("protocolCard", theme, hover=True))
            return

        tools = QHBoxLayout()
        tools.setSpacing(2)
        tools.addWidget(_small_button("✅ Done editing" if editing else "✏️ Edit",
                                      "Reorder, rename, add or remove stages and links", theme, on_edit))
        tools.addWidget(_small_button("📤 Publish", "Send this protocol to myGeeKy, for everyone", theme, on_publish))
        tools.addStretch(1)
        tools.addWidget(_small_button("✕ Stop", "Stop this protocol", theme, lambda: act("stop")))
        lay.addLayout(tools)
        if p.get("summary") and not editing:
            lay.addWidget(_label(p["summary"], _muted(theme, 10.5)))
        if quiz and not editing:
            lay.addWidget(self._quiz_row(quiz, on_quiz, on_share))

        if editing:
            last = len(p["stages"]) - 1
            for i, st in enumerate(p["stages"]):
                lay.addWidget(self._edit_stage(st, i, last))
            row = QHBoxLayout()
            row.addWidget(_small_button("➕ Add a stage", "A new stage before 'Use it in your own work'", theme,
                                        on_add_stage))
            row.addStretch(1)
            lay.addLayout(row)
        elif steps:
            chosen = next((s for s in steps if s.id == selected), None) or \
                next((s for s in steps if s.status == "current"), steps[0])
            lay.addWidget(StepBar(steps, chosen.id, theme, on_select or (lambda sid: None)))
            lay.addWidget(self._step_panel(chosen, steps, on_select))
        self.setStyleSheet(_card_style("protocolCard", theme))

    def _quiz_row(self, quiz: dict[str, Any], on_quiz: Callable[[], None] | None,
                  on_share: Callable[[], None] | None) -> QFrame:
        """The quiz line: how many questions there are, your best score, and the button to take it."""
        theme = self.theme
        box = QFrame()
        box.setObjectName("quizRow")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(9, 7, 9, 7)
        lay.setSpacing(4)
        counts = quiz.get("counts") or {}
        total = int(counts.get("total") or 0)
        best = quiz.get("best") or {}
        score = float(best.get("score") or 0.0) if best else 0.0
        top = QHBoxLayout()
        top.setSpacing(6)
        if best:
            colour = theme["good"] if score >= 1.0 else (theme["good"] if score >= quiz.get("pass_mark", 0.75)
                                                         else theme["accent"])
            mark = "🏴 100%" if score >= 1.0 else f"{round(score * 100)}%"
            top.addWidget(_label(f"🏆 Your best: {mark}",
                                 f"color:{colour}; font-size:11px; font-weight:700; background:transparent;",
                                 wrap=False))
        else:
            top.addWidget(_label("🏆 Quiz", f"color:{theme['text']}; font-size:11px; font-weight:700; "
                                            "background:transparent;", wrap=False))
        if total:
            mix = " · ".join(f"{counts.get(lv, 0)} {lv}" for lv in ("easy", "medium", "tricky") if counts.get(lv))
            top.addWidget(_label(f"{total} questions ({mix})" if mix else f"{total} questions",
                                 _muted(theme, 10)), 1)
        else:
            top.addWidget(_label("no questions for this one yet", _muted(theme, 10)), 1)
        lay.addLayout(top)
        row = FlowRow()
        if total and on_quiz:
            if quiz.get("can_try"):
                asked = min(int(quiz.get("per_attempt") or 10), total)      # a small bank asks what it has
                row.add(_pill_button(f"🏁 Take the quiz ({asked} question{'s' if asked != 1 else ''})",
                                     "Drawn at random: half basics, then applied, and a few real pitfalls",
                                     theme, on_quiz, accent=not best))
            else:
                row.add(_label(quiz.get("why") or "Come back tomorrow", _muted(theme, 10)))
        if best and on_share:
            row.add(_pill_button("🌍 Show my result", "Choose whether your name and score appear on mygeeky.org",
                                 theme, on_share))
        row.finish()
        lay.addWidget(row)
        box.setStyleSheet(f"QFrame#quizRow {{ background:{theme['btn_bg']}; border-radius:9px; }}")
        return box

    def _step_panel(self, step: Any, steps: list[Any], on_select: Callable[[str], None] | None) -> QFrame:
        theme, act = self.theme, self.act
        stage = next(s for s in self.protocol["stages"] if s["id"] == step.id)
        box = QFrame()
        box.setObjectName("stepPanel")
        box.setStyleSheet(f"QFrame#stepPanel {{ background:transparent; border-top:1px solid {theme['btn_bg']}; }}")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(6)
        color = _status_color(theme, step.status)
        lay.addWidget(_label(f"STEP {step.number} OF {len(steps)} · {step.role_label.upper()}",
                             f"color:{theme['muted']}; font-size:9.5px; font-weight:700; letter-spacing:0.6px; "
                             "background:transparent;"))
        head = QHBoxLayout()
        head.addWidget(_label(f"<b>{html.escape(step.title)}</b>", f"color:{theme['text']}; font-size:14px; "
                                                                    "background:transparent;", rich=True), 1)
        chip = _label(f"{STATUS_ICON_TEXT.get(step.status, '')} {step.status_label}".strip(),
                      f"color:{color}; background:{color}22; border-radius:8px; padding:2px 8px; font-size:10px; "
                      "font-weight:700;", wrap=False)
        head.addWidget(chip, 0, Qt.AlignVCenter)
        lay.addLayout(head)
        if step.why:
            lay.addWidget(_label(step.why, _muted(theme, 10.5)))
        actions = FlowRow()                     # wraps instead of widening a narrow panel
        actions.addWidget = actions.add
        if step.can_check:
            actions.addWidget(_pill_button("🎓 I know this: check me", "A short quiz, or 'I can do these'", theme,
                                           lambda: self.on_check(stage)))
        if not step.auto:
            done = step.status == "done"
            actions.addWidget(_pill_button("↩ Not done" if done else "☑ Mark as done",
                                           "Mark as not done" if done else "Mark this step as done", theme,
                                           lambda: act("tick", step.id, not done), accent=not done and step.status == "current"))
        if step.how == "evidence" and not step.auto:
            actions.addWidget(_small_button("Not really", "Show this step as still to do", theme,
                                            lambda: act("known", step.id, "no")))
        elif step.overruled or step.how == "self":
            actions.addWidget(_small_button("Undo", "Go back to what your work shows", theme,
                                            lambda: act("known", step.id, None)))
        lay.addWidget(actions)
        for res, it in zip(step.resources, stage["items"]):
            thumbs = None if res.kind == "search" else ThumbBar(self.vote_of(it), theme, self.vote_item(it),
                                                                up_tip="Good to learn from", down_tip="Not helpful")
            lay.addWidget(ResourceCard(res, theme, self.on_open, thumbs))
        if not step.resources and not step.auto:
            lay.addWidget(_label("No links yet: ✏️ Edit to add one.", _muted(theme, 10.5)))
        if on_select and len(steps) > 1:
            i = next(k for k, s in enumerate(steps) if s.id == step.id)
            nav = QHBoxLayout()

            def short(t: str, n: int = 22) -> str:
                return t if len(t) <= n else t[: n - 1].rstrip() + "…"
            if i > 0:
                nav.addWidget(_small_button(f"← {short(steps[i - 1].title)}", "The step before", theme,
                                            lambda: on_select(steps[i - 1].id)))
            nav.addStretch(1)
            if i < len(steps) - 1:
                nav.addWidget(_small_button(f"{short(steps[i + 1].title)} →", "The next step", theme,
                                            lambda: on_select(steps[i + 1].id)))
            lay.addLayout(nav)
        return box


    def _edit_stage(self, st: dict[str, Any], i: int, last: int) -> QFrame:
        theme, act, editing = self.theme, self.act, self.editing
        box = QFrame()
        box.setObjectName("stageBox")
        current = st["status"] == "current"
        box.setStyleSheet(f"QFrame#stageBox {{ background:{theme['btn_bg'] if current else 'transparent'}; "
                          "border-radius:8px; }")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(4)
        icon, word = STATUS.get(st["status"], ("○", ""))
        how = ""
        if st.get("how") == "quiz":
            how = " (check passed" + (f", {round(st['score'] * 100)}%" if st.get("score") is not None else "") + ")"
        elif st.get("how") == "self":
            how = " (you said so)"
        color = theme["good"] if st["status"] in ("done", "known") else theme["text"]
        tag = f" <span style='color:{theme['muted']}; font-size:10px'>{word}{how}</span>" if word else ""
        top.addWidget(_label(f"<span style='color:{color}'>{icon}</span> <b>{i + 1}. {html.escape(st['title'])}</b>{tag}",
                             f"color:{theme['text']}; font-size:11.5px; background:transparent;", rich=True), 1)
        if editing:
            top.addWidget(_small_button("▲", "Move this stage up", theme, lambda: act("move_stage", st["id"], -1)))
            top.addWidget(_small_button("▼", "Move this stage down", theme, lambda: act("move_stage", st["id"], 1)))
            top.addWidget(_small_button("✎", "Rename this stage", theme, lambda: self.on_rename(st)))
            top.addWidget(_small_button("🗑", "Remove this stage", theme, lambda: act("remove_stage", st["id"])))
        elif st["role"] != "use":
            if st["status"] not in ("done", "known") and (st.get("quiz") or st.get("can")):
                top.addWidget(_small_button("🎓 Check", "Already know this? A short check skips it", theme,
                                            lambda: self.on_check(st)))
            done = st["status"] == "done"
            top.addWidget(_small_button("↩ Not done" if done else "☑ Done",
                                        "Mark as not done" if done else "Mark this stage as done", theme,
                                        lambda: act("tick", st["id"], not done)))
        lay.addLayout(top)
        if st["role"] == "use":
            text = ("Done: " + st["why"]) if st["status"] in ("done", "known") else \
                (st.get("why") or "Ticks itself when one of your repos shows the skill")
            lay.addWidget(_label(text, _muted(theme, 10)))
        elif st.get("how") == "evidence" and st.get("why"):
            why = QHBoxLayout()
            why.addWidget(_label(f"From your work: {st['why']}", _muted(theme, 10)), 1)
            why.addWidget(_small_button("Not really", "Show this stage as still to do", theme,
                                        lambda: act("known", st["id"], "no")))
            lay.addLayout(why)
        elif st.get("overruled"):
            why = QHBoxLayout()
            why.addWidget(_label(f"{st['why'] or 'Your work suggests you know this'}, but you said not yet",
                                 _muted(theme, 10)), 1)
            why.addWidget(_small_button("Undo", "Go back to what your work shows", theme,
                                        lambda: act("known", st["id"], None)))
            lay.addLayout(why)
        elif st.get("how") == "self":
            lay.addWidget(_small_button("Undo “I know this”", "Show this stage as still to do", theme,
                                        lambda: act("known", st["id"], None)), 0, Qt.AlignLeft)
        from ..protocols import ITEM_KINDS
        n = len(st["items"])
        for k, it in enumerate(st["items"]):
            row = QHBoxLayout()
            row.setSpacing(4)
            note = f"<br><span style='color:{theme['muted']}'>{html.escape(it['note'])}</span>" if it.get("note") else ""
            link = _label(f"{ITEM_KINDS.get(it['kind'], '🌐')} <a href='{html.escape(it['url'], quote=True)}' "
                          f"style='color:{theme['link']}'>{html.escape(it['title'])}</a>{note}",
                          f"color:{theme['text']}; font-size:10.5px; background:transparent; margin-left:14px;", rich=True)
            link.setOpenExternalLinks(False)
            link.linkActivated.connect(self.on_open)
            row.addWidget(link, 1)
            if editing:
                if k > 0 or i > 0:
                    row.addWidget(_small_button("▲", "Up (past the top: to the stage before)", theme,
                                                lambda u=it["url"]: act("move_item", st["id"], u, -1)), 0, Qt.AlignTop)
                if k < n - 1 or i < last:
                    row.addWidget(_small_button("▼", "Down (past the bottom: to the next stage)", theme,
                                                lambda u=it["url"]: act("move_item", st["id"], u, 1)), 0, Qt.AlignTop)
                row.addWidget(_small_button("✕", "Remove this link", theme,
                                            lambda u=it["url"]: act("remove_item", st["id"], u)), 0, Qt.AlignTop)
            elif "github.com/search" not in it["url"]:
                row.addWidget(ThumbBar(self.vote_of(it), theme, self.vote_item(it), up_tip="Good to learn from",
                                       down_tip="Not helpful"), 0, Qt.AlignTop)
            lay.addLayout(row)
        if editing:
            lay.addWidget(_small_button("➕ Add a link", "A repo, a paper or a page that teaches this stage", theme,
                                        lambda: self.on_add_link(st["id"])), 0, Qt.AlignLeft)
        return box


class ResourceRow(QFrame):
    """A learning resource: what it is, what it teaches, why it's for you."""

    def __init__(self, r: dict[str, Any], theme: dict[str, Any], on_vote: Callable[[bool], int],
                 on_open: Callable[[str], Any]) -> None:
        super().__init__()
        from ..curated import RESOURCE_TYPES
        self.setObjectName("resourceRow")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(8)
        outer.addWidget(_label(RESOURCE_TYPES.get(r.get("type", ""), "🌐"), "font-size:15px; background:transparent;",
                               wrap=False), 0, Qt.AlignTop)
        body = QVBoxLayout()
        body.setSpacing(1)
        title = _label(f"<b>{html.escape(r['title'])}</b>", f"color:{theme['text']}; font-size:11.5px; "
                       "background:transparent;", rich=True)
        title.setCursor(Qt.PointingHandCursor)
        url = r.get("url", "")
        title.mousePressEvent = lambda ev: on_open(url)  # noqa: ARG005
        body.addWidget(title)
        if r.get("summary"):
            body.addWidget(_label(r["summary"], _muted(theme, 10.5)))
        bits = [r["level"]] if r.get("level") else []
        if r.get("skills"):
            from .. import skills as sk
            bits.append("teaches " + ", ".join((sk.find(n) or {"name": n})["name"] for n in r["skills"][:4]))
        if r.get("match"):
            bits.append("matches " + ", ".join(r["match"][:3]))
        if bits:
            body.addWidget(_label(" · ".join(bits), _muted(theme, 10)))
        outer.addLayout(body, 1)
        outer.addWidget(ThumbBar(r.get("vote", 0), theme, on_vote, "Useful: more like this",
                                 "Not for me: hide it"), 0, Qt.AlignTop)
        self.setStyleSheet(_card_style("resourceRow", theme, hover=True))


class WinRow(QFrame):
    """⭐ new stars, 🍴 forks, 📚 citations (and who cited you)."""

    def __init__(self, w: dict[str, Any], theme: dict[str, Any], on_open: Callable[[str], Any],
                 when: str = "") -> None:
        super().__init__()
        self.setObjectName("winRow")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(8)
        outer.addWidget(_label(WIN_EMOJI.get(w.get("kind", ""), "🎉"), "font-size:15px; background:transparent;",
                               wrap=False), 0, Qt.AlignTop)
        body = QVBoxLayout()
        body.setSpacing(1)
        body.addWidget(_label(w.get("text", ""), f"color:{theme['text']}; font-size:11.5px; font-weight:600; "
                              "background:transparent;"))
        citing = w.get("citing") or {}
        if citing.get("title"):
            by = f"{citing['by']}: " if citing.get("by") else ""
            body.addWidget(_label(f"newest: {by}{citing['title']}", _muted(theme, 10.5)))
        if when:
            body.addWidget(_label(when, _muted(theme, 10)))
        outer.addLayout(body, 1)
        url = citing.get("url") or w.get("url", "")
        if url:
            self.setCursor(Qt.PointingHandCursor)
            self.mousePressEvent = lambda ev: on_open(url)  # noqa: ARG005
        self.setStyleSheet(_card_style("winRow", theme, hover=bool(url)))


class CollaboratorCard(QFrame):
    """A fellow myGeeKy user whose skills complement yours, and the mutual 🤝."""

    def __init__(self, p: dict[str, Any], theme: dict[str, Any], make_avatar: Callable[[str, str, int], QWidget],
                 on_vote: Callable[[bool], int], on_ask: Callable[["CollaboratorCard"], None],
                 on_open: Callable[[str], Any], can_send: bool) -> None:
        super().__init__()
        self.person = p
        self.setObjectName("collabCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(make_avatar(p["login"], p.get("avatar_url", ""), 30))
        name = _label(f"<b>{html.escape(p['login'])}</b>"
                      + (f" <span style='color:{theme['muted']}'>{html.escape(p['status'])}</span>" if p.get("status") else ""),
                      f"color:{theme['text']}; font-size:12px; background:transparent;", rich=True, wrap=False)
        name.setCursor(Qt.PointingHandCursor)
        url = p.get("profile_url", "")
        name.mousePressEvent = lambda ev: on_open(url)  # noqa: ARG005
        head.addWidget(name, 1)
        head.addWidget(ThumbBar(p.get("vote", 0), theme, on_vote, "A good match: more like them",
                                "Not a match: hide them"))
        lay.addLayout(head)
        if p.get("they_bring"):
            lay.addWidget(_label("They bring: " + ", ".join(p["they_bring"][:5]), f"color:{theme['good']}; "
                                 "font-size:10.5px; background:transparent;"))
        if p.get("you_bring"):
            lay.addWidget(_label("You bring: " + ", ".join(p["you_bring"][:5]), _muted(theme, 10.5)))
        if p.get("shared"):
            lay.addWidget(_label("Both into: " + ", ".join(p["shared"][:5]), _muted(theme, 10.5)))
        row = QHBoxLayout()
        self.ask = QPushButton("🤝 Asked" if p.get("asked") else "🤝 I'd like to collaborate")
        self.ask.setCursor(Qt.PointingHandCursor)
        self.ask.setEnabled(can_send and p.get("can_receive", True) and not p.get("asked"))
        self.ask.setToolTip("Sealed: only they can open it, and they only ever see it if they choose you too."
                            if can_send else "Finish setting up Signals (⚙ Settings) to send this.")
        self.ask.setStyleSheet(_button_style(theme, accent=not p.get("asked")))
        self.ask.clicked.connect(lambda: on_ask(self))
        row.addWidget(self.ask)
        self.note = _label("they only see it if they pick you too", _muted(theme, 10))
        row.addWidget(self.note, 1)
        lay.addLayout(row)
        self.setStyleSheet(_card_style("collabCard", theme))

    def set_result(self, ok: bool, text: str) -> None:
        self.ask.setText("🤝 Asked" if ok else "🤝 I'd like to collaborate")
        self.ask.setEnabled(not ok)
        self.note.setText(text)


class SaidPanel(QFrame):
    """One listing in another language, folded into the card it belongs to.

    myGeeKy lives in a panel docked to the side of the screen, which has no room for a window of its own --
    so this opens where the listing already is: press the languages and the card grows, press again and it
    closes. The English stays above it, because the English title and the deadline sentence are the parts
    that were checked word for word against the page; this is a reading aid beside them, and says so.
    Nothing is fetched: every language came down with the lists, so it works with no connection."""

    def __init__(self, it: dict[str, Any], theme: dict[str, Any],
                 on_close: Callable[[], None] | None = None) -> None:
        super().__init__()
        from ..curated import languages_of
        self.setObjectName("saidPanel")
        self._said = it.get("translations") or {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 7, 8, 7)
        lay.setSpacing(5)
        chips = FlowRow()              # five languages do not fit across a docked panel; they wrap
        self._chips: dict[str, QPushButton] = {}
        for code in languages_of(it):
            chip = QPushButton(self._said[code]["name"])
            chip.setCheckable(True)
            chip.setCursor(Qt.PointingHandCursor)
            chip.setStyleSheet(
                f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['muted']}; border:none; "
                f"border-radius:9px; padding:3px 9px; font-size:10.5px; }}"
                f"QPushButton:hover {{ background:{theme['btn_hover']}; color:{theme['text']}; }}"
                f"QPushButton:checked {{ background:{theme['section_btn']}; color:{theme['text']}; "
                "font-weight:700; }}")
            chip.clicked.connect(lambda _=False, c=code: self.show_language(c))
            chips.add(chip)
            self._chips[code] = chip
        if on_close is not None:
            # a way out that is visible from inside the translation, for anyone who has scrolled past the row
            shut = QPushButton("✕")
            shut.setCursor(Qt.PointingHandCursor)
            shut.setToolTip("Close the translation")
            shut.setStyleSheet(f"QPushButton {{ background:transparent; color:{theme['muted']}; border:none; "
                               "padding:3px 7px; font-size:11px; }"
                               f"QPushButton:hover {{ color:{theme['text']}; }}")
            shut.clicked.connect(on_close)
            chips.add(shut)
        lay.addWidget(chips)
        self._body = _label("", f"color:{theme['text']}; font-size:11px; background:transparent;", rich=True)
        self._body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self._body)
        lay.addWidget(_label("Translated by machine from the English above, which is the part myGeeKy "
                             "checked against the page itself.", _muted(theme, 9.5)))
        self.setStyleSheet(f"QFrame#saidPanel {{ background:{theme['btn_bg']}; border-radius:8px; }}")
        first = languages_of(it)
        if first:
            self.show_language(first[0])

    def show_language(self, code: str) -> None:
        """The listing in one language. Arabic sets the paragraph right-to-left; Qt handles the rest."""
        said = self._said.get(code) or {}
        for other, chip in self._chips.items():
            chip.setChecked(other == code)
        lines = [f"<b>{html.escape(said.get('title', ''))}</b>"]
        lines += [html.escape(said[f]) for f in ("summary", "who", "amount", "student") if said.get(f)]
        self._body.setText("<br><br>".join(lines))
        rtl = bool(said.get("rtl"))
        self._body.setLayoutDirection(Qt.RightToLeft if rtl else Qt.LeftToRight)
        self._body.setAlignment((Qt.AlignRight if rtl else Qt.AlignLeft) | Qt.AlignTop)


# --------------------------------------------------------------------------- 🎯 Chances
class OpportunityCard(QFrame):
    """A verified job, a funding call or a conference: what, where, until when, why it fits."""

    def __init__(self, kind: str, it: dict[str, Any], theme: dict[str, Any], on_vote: Callable[[bool], int],
                 on_open: Callable[[str], Any], on_report: Callable[[str, dict[str, Any]], None]) -> None:
        super().__init__()
        from ..curated import JOB_TYPES
        self.setObjectName("chanceCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)
        head = QHBoxLayout()
        head.setSpacing(6)
        emoji = {"jobs": JOB_EMOJI.get(it.get("type", ""), "💼"), "funding": "💶", "conferences": "🎤"}[kind]
        title = _label(f"{emoji} <b>{html.escape(it['title'])}</b>", f"color:{theme['text']}; font-size:12px; "
                       "background:transparent;", rich=True)
        title.setCursor(Qt.PointingHandCursor)
        url = it.get("url", "")
        title.mousePressEvent = lambda ev: on_open(url)  # noqa: ARG005
        head.addWidget(title, 1)
        head.addWidget(ThumbBar(it.get("vote", 0), theme, on_vote, "Interested: more like this",
                                "Not for me: hide it"), 0, Qt.AlignTop)
        lay.addLayout(head)
        bits = []
        if kind == "jobs":
            bits = [JOB_TYPES.get(it.get("type", ""), "Job"), it.get("org", ""), it.get("place", "")]
            if it.get("remote"):
                bits.append("remote possible")
        elif kind == "funding":
            bits = [it.get("org", ""), it.get("amount", "")]
        else:
            when = it.get("starts", "") + (f" to {it['ends']}" if it.get("ends") and it.get("ends") != it.get("starts") else "")
            bits = [it.get("place", ""), when]
        line = " · ".join(b for b in bits if b)
        if line:
            lay.addWidget(_label(line, _muted(theme, 10.5)))
        if it.get("original_title") and it.get("language"):
            # the English is what you read; the board's own words are here so you can hold it against the page
            lay.addWidget(_label(f"🌍 Translated from {html.escape(it['language'])} · "
                                 f"<i>{html.escape(it['original_title'])}</i>", _muted(theme, 10)))
        if it.get("pending"):
            lay.addWidget(_label("⏳ You accepted this: only you see it until you publish", f"color:{theme['warn']}; "
                                 "font-size:10.5px; background:transparent;"))
        if it.get("who"):
            lay.addWidget(_label("Who can apply: " + it["who"], _muted(theme, 10.5)))
        if it.get("student"):
            lay.addWidget(_label("Students: " + it["student"], _muted(theme, 10.5)))
        if it.get("summary"):
            lay.addWidget(_label(it["summary"], f"color:{theme['text']}; font-size:10.5px; background:transparent;"))
        if it.get("translations"):
            # the row names the languages in their own scripts: someone who cannot read this card can still
            # see that it is for them, which an English word like "Translate" would not manage
            from ..curated import languages_of
            names = " · ".join(it["translations"][c]["name"] for c in languages_of(it))
            said = SaidPanel(it, theme, on_close=lambda: _open_said(False))
            say = QPushButton()
            say.setCursor(Qt.PointingHandCursor)
            say.setStyleSheet(f"QPushButton {{ color:{theme['muted']}; background:transparent; border:none; "
                              f"font-size:10.5px; text-align:left; padding:2px 0; }}"
                              f"QPushButton:hover {{ color:{theme['text']}; }}")

            def _open_said(show: bool) -> None:
                """The caret is the whole hint that the row is a switch, so it is the row that carries it."""
                said.setVisible(show)
                say.setText(f"🌍 {names}  {'▴' if show else '▾'}")
                say.setToolTip("Close the translation" if show else "Read this listing in another language")

            _open_said(False)
            # isHidden, not isVisible: a card built while the panel is folded is not visible either way
            say.clicked.connect(lambda: _open_said(said.isHidden()))
            lay.addWidget(say)
            lay.addWidget(said)
        foot = QHBoxLayout()
        left = deadline_text(it.get("days_left"))
        warn = it.get("days_left") is not None and it["days_left"] <= 7
        due = _label(("⏳ " if warn else "") + left + (f" ({it['deadline']})" if it.get("deadline") else ""),
                     f"color:{theme['warn'] if warn else theme['muted']}; font-size:10px; background:transparent;",
                     wrap=False)
        due.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)      # never squeezed away
        foot.addWidget(due)
        if it.get("match"):
            foot.addWidget(_label("· matches " + ", ".join(it["match"][:3]), _muted(theme, 10)), 1)
        else:
            foot.addStretch(1)
        report = QPushButton("🚩")
        report.setFixedSize(26, 22)
        report.setCursor(Qt.PointingHandCursor)
        report.setToolTip("Looks fake, or no longer real? Tell myGeeKy's maker")
        report.setStyleSheet(f"QPushButton {{ background:transparent; border:none; font-size:11px; }}"
                             f"QPushButton:hover {{ background:{theme['btn_hover']}; border-radius:7px; }}")
        report.clicked.connect(lambda: on_report(kind, it))
        foot.addWidget(report)
        lay.addLayout(foot)
        self.setStyleSheet(_card_style("chanceCard", theme))


class SeasonCard(QFrame):
    """A scholarship that comes back every year: where it stands, and what to have ready before it does.

    The honest part is the wording. A window myGeeKy read on a page and that is still running says "open
    now"; everything else says "expected", and the card shows how many years of evidence stand behind that
    expectation. Below it, the sentence that was actually found, with a link to the page it was found on --
    so nobody has to take myGeeKy's word for any of it."""

    STATE = {"open": ("🟢", "good"), "soon": ("🟡", "warn"), "later": ("⚪", "muted"),
             "unknown": ("⚪", "muted")}

    def __init__(self, season: dict[str, Any], theme: dict[str, Any], on_open: Callable[[str], Any],
                 unverified: bool = False) -> None:
        super().__init__()
        from ..seasons import notice_text, prepare_now
        self.setObjectName("seasonCard")
        state = season.get("when") or {}
        emoji, colour = self.STATE.get(state.get("state", "later"), ("⚪", "muted"))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)
        title = _label(f"{emoji} <b>{html.escape(season.get('title', ''))}</b>",
                       f"color:{theme['text']}; font-size:12px; background:transparent;", rich=True)
        title.setCursor(Qt.PointingHandCursor)
        url = season.get("url", "")
        title.mousePressEvent = lambda ev: on_open(url)  # noqa: ARG005
        lay.addWidget(title)
        by = season.get("org", "")
        if season.get("through"):
            by = f"{by} · through {season['through']}" if by else f"through {season['through']}"
        if by:
            lay.addWidget(_label(by, _muted(theme, 10.5)))
        # where it stands, and how much to trust that
        years = state.get("years", 0)
        bits = [notice_text(state)]
        if state.get("opens") and not state.get("confirmed"):
            bits.append(f"{state['opens']} → {state['closes']}")
        bits.append("no history yet" if not years else
                    f"{years} year of evidence" if years == 1 else f"{years} years of evidence")
        lay.addWidget(_label(" · ".join(bits), f"color:{theme[colour]}; font-size:11px; "
                             "background:transparent;"))
        who = ", ".join(season.get("for") or []) or "anyone"
        going = season.get("goes_to", "")
        levels = "/".join(season.get("levels") or [])
        lay.addWidget(_label(" · ".join(x for x in [f"for {who}", f"→ {going}" if going else "", levels] if x),
                             _muted(theme, 10.5)))
        if unverified:
            lay.addWidget(_label("⏳ Not confirmed against its own page yet: only you see it",
                                 f"color:{theme['warn']}; font-size:10.5px; background:transparent;"))
        if season.get("summary"):
            lay.addWidget(_label(season["summary"], f"color:{theme['text']}; font-size:10.5px; "
                                 "background:transparent;"))
        # the part that makes somebody ready rather than merely informed
        weeks = season.get("prepare_weeks", 4)
        now = prepare_now(season)
        lay.addWidget(_label(f"{'⚠ Start preparing now' if now else 'Start preparing'} — it wants about "
                             f"{weeks} weeks:", f"color:{theme['warn'] if now else theme['muted']}; "
                             "font-size:10.5px; background:transparent;"))
        for step in season.get("prepare") or []:
            lay.addWidget(_label(f"□ {html.escape(step)}", _muted(theme, 10), rich=True))
        self._evidence(lay, season, theme, on_open)
        self.setStyleSheet(_card_style("seasonCard", theme))

    def _evidence(self, lay: QVBoxLayout, season: dict[str, Any], theme: dict[str, Any],
                  on_open: Callable[[str], Any]) -> None:
        """The sentence myGeeKy found, and where. Without this a season is only a rumour."""
        seen = [s for s in (season.get("seen") or []) if s.get("checked")]
        if not seen:
            return
        last = seen[0]
        lay.addWidget(_label(f"✓ seen open {last.get('opens') or '?'} → {last['closes']}",
                             f"color:{theme['good']}; font-size:10px; background:transparent;"))
        lay.addWidget(_label(f"<i>“{html.escape(last['quote'][:160])}”</i>", _muted(theme, 10), rich=True))
        page = QPushButton("Open the page it was found on ↗")
        page.setCursor(Qt.PointingHandCursor)
        page.setStyleSheet(f"QPushButton {{ color:{theme['link']}; background:transparent; border:none; "
                           "font-size:10px; text-align:left; padding:1px 0; }")
        page.clicked.connect(lambda: on_open(last["url"]))
        lay.addWidget(page)


def combo_style(theme: dict[str, Any]) -> str:
    """A drop box that belongs to the theme it is sitting in.

    Qt styles a combo box black-on-grey by default, and its list is drawn in a window of its own -- where
    the theme's translucent colours go black and the text disappears. So the list is given the theme's one
    opaque surface, and the arrow is drawn here rather than left to the platform, which otherwise paints a
    native triangle that belongs to neither theme."""
    return (
        f"QComboBox {{ background:{theme['btn_bg']}; color:{theme['text']}; border:1px solid "
        f"{theme['border']}; border-radius:8px; padding:4px 8px; font-size:11px; }}"
        f"QComboBox:hover {{ background:{theme['btn_hover']}; }}"
        f"QComboBox:focus {{ border:1px solid {theme['accent']}; }}"
        "QComboBox::drop-down { border:none; width:18px; }"
        f"QComboBox::down-arrow {{ image:none; border-left:4px solid transparent; "
        f"border-right:4px solid transparent; border-top:5px solid {theme['text']}; "
        "width:0; height:0; margin-right:6px; }"
        # the list: its own window, so nothing translucent and nothing inherited
        f"QComboBox QAbstractItemView {{ background:{theme['solid_bg']}; color:{theme['solid_text']}; "
        f"border:1px solid {theme['border']}; border-radius:8px; padding:3px; outline:none; "
        f"selection-background-color:{theme['section_btn']}; selection-color:{theme['solid_text']}; }}"
        f"QComboBox QAbstractItemView::item {{ padding:5px 7px; border-radius:5px; min-height:20px; }}"
        f"QComboBox QAbstractItemView::item:hover {{ background:{theme['btn_hover']}; }}"
    )


# --------------------------------------------------------------------------- starting from keywords alone
class FieldPicker(QFrame):
    """What do you work on? -- asked five chips at a time, for somebody with no account of any kind.

    A blank "type ten keywords" box is why people leave at the door, so this offers five, learns from
    whichever are taken, and offers five more. Three of each five are near what has been picked and two
    are deliberately elsewhere: all-near would turn one tap into a cul-de-sac with no way back. Waving a
    chip away (its X) rules out its whole neighbourhood, not just the word.

    The bar fills towards ten because ten is a good profile, but `ready` opens at six across three areas:
    six keywords from three corners of a field rank better than ten from one, and ten taps is a long door.
    """

    def __init__(self, logic: Any, theme: dict[str, Any], on_done: Callable[[list[str]], Any],
                 on_skip: Callable[[], Any] | None = None) -> None:
        super().__init__()
        self._logic = logic
        self._theme = theme
        self._on_done = on_done
        self._on_skip = on_skip
        self.picked: list[str] = []
        self.dismissed: list[str] = []
        self.shown: list[str] = []
        self._note = ""
        self._offered: list[dict[str, Any]] = []
        self.setObjectName("fieldPicker")
        self.setStyleSheet(f"QFrame#fieldPicker {{ background:{theme['card_bg']}; border:1px solid "
                           f"{theme['border']}; border-radius:12px; }} QLabel {{ background:transparent; "
                           f"color:{theme['text']}; }}")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(14, 12, 14, 12)
        self._lay.setSpacing(8)
        self._draw()

    # ---------------------------------------------------------------- drawing
    def _draw(self) -> None:
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        theme = self._theme
        title = QLabel("<b>What do you work on?</b>")
        title.setTextFormat(Qt.RichText)
        self._lay.addWidget(title)
        why = QLabel("No account needed — not GitHub, not ORCID, not with us. Tap whatever fits; "
                     "✕ means never show me this kind of thing.")
        why.setWordWrap(True)
        why.setStyleSheet(_muted(theme))
        self._lay.addWidget(why)

        if self._note:
            said = QLabel(self._note)
            said.setWordWrap(True)
            said.setStyleSheet(_muted(theme))
            self._lay.addWidget(said)

        chips = self._offered or self._logic.field_suggest(self.picked, self.dismissed, self.shown)
        self._offered = []
        self.shown += [c["topic"] for c in chips if c["topic"] not in self.shown]
        row = FlowRow()
        for chip in chips:
            row.add(self._chip(chip))
        row.finish()
        self._lay.addWidget(row)
        hint = QLabel("Hover a keyword to see what it covers — “16s” says little, "
                      "“microbiome, metagenomics, dada2” says everything.")
        hint.setWordWrap(True)
        hint.setStyleSheet(_muted(theme))
        self._lay.addWidget(hint)

        if self.picked:
            yours = QLabel("Your field so far — tap one to take it back:")
            yours.setStyleSheet(_muted(theme))
            self._lay.addWidget(yours)
            mine = FlowRow()
            for word in self.picked:
                mine.add(self._taken(word))
            mine.finish()
            self._lay.addWidget(mine)

        state = self._logic.field_ready(self.picked)
        self._lay.addWidget(self._bar(state))

        # A flow row, not an HBox: side-by-side buttons set the panel's minimum width between them, and
        # this panel is a 380px dock. Wrapping costs a line; not wrapping cost 60px of screen.
        buttons = FlowRow()
        own = QPushButton("＋ my own word")
        own.setCursor(Qt.PointingHandCursor)
        own.setStyleSheet(_button_style(theme))
        own.setToolTip("Anything myGeeKy has never heard of still counts — it just matches on itself")
        own.clicked.connect(lambda: self._ask_own())
        buttons.add(own)
        if self._on_skip is not None:
            later = QPushButton("Later")
            later.setCursor(Qt.PointingHandCursor)
            later.setStyleSheet(_button_style(theme))
            later.clicked.connect(lambda: self._on_skip())
            buttons.add(later)
        go = QPushButton("Start" if state["ok"] else "Start anyway")
        go.setCursor(Qt.PointingHandCursor)
        go.setStyleSheet(_button_style(theme, accent=state["ok"]))
        go.setEnabled(bool(self.picked))
        go.setToolTip("" if state["ok"] else "It will work — a wider field just ranks better")
        go.clicked.connect(lambda: self._on_done(list(self.picked)))
        buttons.add(go)
        buttons.finish()
        self._lay.addWidget(buttons)

    def _bar(self, state: dict[str, Any]) -> QWidget:
        theme = self._theme
        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 2, 0, 0)
        lay.setSpacing(3)
        full = int(round(state["bar"] * 20))
        track = QLabel("█" * full + "·" * (20 - full))
        track.setStyleSheet(f"color:{theme['accent'] if state['ok'] else theme['muted']}; "
                            f"font-family:Consolas,monospace; font-size:11px; background:transparent;")
        lay.addWidget(track)
        said = (f"{state['picks']} keyword{'s' if state['picks'] != 1 else ''} across "
                f"{state['areas']} area{'s' if state['areas'] != 1 else ''} → "
                f"{state['terms']} things to match on")
        note = QLabel(said + (f" · {state['need']}" if state["need"] else " · that's a good profile"))
        note.setWordWrap(True)
        note.setStyleSheet(_muted(theme))
        lay.addWidget(note)
        return holder

    def _chip(self, chip: dict[str, Any]) -> QWidget:
        """One offered keyword: its name, what it means here, and a way to refuse its whole area.

        The meaning matters. Nobody can say whether "16s" is them; everybody can say whether
        "microbiome, metagenomics, dada2" is. The dictionary holds related terms rather than definitions,
        which reads better for exactly this."""
        theme = self._theme
        holder = QWidget()
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        # The label alone, with the meaning in the tooltip. Spelling the related terms out on the button
        # made the widest chip set the panel's minimum width, and the panel is a narrow dock: one long
        # chip pushed it off the side of the screen.
        take = QPushButton(chip["label"])
        take.setCursor(Qt.PointingHandCursor)
        take.setToolTip(f"{chip['label']} covers: {chip['means']}" if chip.get("means")
                        else "myGeeKy has no related terms for this one — it matches on itself")
        take.setStyleSheet(_button_style(theme))
        take.clicked.connect(lambda: self._take(self._word_of(chip)))
        lay.addWidget(take)
        if not chip.get("from"):            # an OpenAlex suggestion has no neighbourhood to wave away
            away = QPushButton("✕")
            away.setCursor(Qt.PointingHandCursor)
            away.setToolTip("Not my field — and don't offer anything like it again")
            away.setStyleSheet(_button_style(theme))
            away.setFixedWidth(26)
            away.clicked.connect(lambda: self._wave_away(chip["topic"]))
            lay.addWidget(away)
        return holder

    def _taken(self, word: str) -> QPushButton:
        # Shown the way people write it, kept the way the dictionary keys it: "machine-learning" is what
        # lookup and expand need, and "machine learning" is what a person should read on a chip.
        from .. import keywords as _kw
        b = QPushButton(f"✓ {_kw.label_of(word) if _kw.known(word) else word}")
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip("Tap to take this back")
        b.setStyleSheet(_button_style(self._theme, accent=True))
        b.clicked.connect(lambda: self._drop(word))
        return b

    # ---------------------------------------------------------------- what the taps do
    @staticmethod
    def _word_of(chip: dict[str, Any]) -> str:
        """What a tapped chip is worth keeping as.

        Our own topics keep their dictionary form ("machine-learning"), because that is what lookup and
        expand are keyed on. An OpenAlex suggestion keeps its DISPLAY NAME: its slug would be stored as
        "genetic-mapping-and-diversity-in-plants", which matches nothing a page actually says."""
        if chip.get("from") == "openalex":
            return str(chip.get("label") or chip.get("topic") or "")
        return str(chip.get("topic") or chip.get("label") or "")

    def _take(self, topic: str) -> None:
        if topic not in self.picked:
            self.picked.append(topic)
        self._note = ""
        self._draw()

    def _drop(self, word: str) -> None:
        self.picked = [w for w in self.picked if w != word]
        self._draw()

    def _wave_away(self, topic: str) -> None:
        if topic not in self.dismissed:
            self.dismissed.append(topic)
        self._note = ""
        self._draw()

    def _ask_own(self) -> None:
        """Their own word. Kept whether or not myGeeKy knows it -- an unknown keyword matches on itself,
        so typing something we have never heard of costs nothing. If we have nothing close, OpenAlex is
        asked for the research-side name, which is exactly where our software-shaped dictionary is thin."""
        from PySide6.QtWidgets import QInputDialog
        said, ok = QInputDialog.getText(self, "A word of your own", "What do you work on?")
        word = " ".join(str(said or "").split())
        if not ok or not word:
            return
        offer = self._logic.field_offer(word, True)
        keep = offer.get("keep") or word
        if keep not in self.picked:
            self.picked.append(keep)
        self._note = offer.get("note") or ""
        self._offered = list(offer.get("alternatives") or [])
        self._draw()
