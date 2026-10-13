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
    lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
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
    return (f"QPushButton {{ background:{theme['tab_active'] if active else theme['card_bg']}; "
            f"color:{theme['text']}; border:none; border-radius:8px; padding:4px 10px; "
            f"font-size:11px; font-weight:{'700' if active else '400'}; }}")


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
              "video": "#f472b6", "website": "#94a3b8", "search": "#94a3b8"}


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


def _status_color(theme: dict[str, Any], status: str) -> str:
    return {"done": theme["good"], "known": theme["good"], "current": theme["accent"]}.get(status, theme["muted"])


class StepBar(QWidget):
    """The protocol's steps as a line of numbered circles: green when done or known, the accent colour
    where to start, grey still to do. The chosen step is ringed; click a circle to show that step."""

    def __init__(self, steps: list[Any], selected: str, theme: dict[str, Any], on_select: Callable[[str], None]) -> None:
        super().__init__()
        self.steps, self.selected, self.theme, self.on_select = steps, selected, theme, on_select
        self.setMinimumHeight(58)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click a step to see it")

    def _centres(self) -> list[float]:
        n = max(len(self.steps), 1)
        w = self.width()
        pad = min(30.0, w / (2 * n))
        return [pad + i * (w - 2 * pad) / max(n - 1, 1) for i in range(n)] if n > 1 else [w / 2]

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        xs, y, r = self._centres(), 18.0, 11.0
        t = self.theme
        for i in range(len(xs) - 1):                         # the line between steps: green once the left one is done
            left = self.steps[i].status in ("done", "known")
            p.setPen(QPen(QColor(t["good"] if left else t["btn_bg"]), 3))
            p.drawLine(int(xs[i] + r), int(y), int(xs[i + 1] - r), int(y))
        f = QFont(self.font())
        f.setPointSizeF(7.5)
        fm = QFontMetrics(f)
        col = (self.width() / max(len(xs), 1)) - 4
        for x, st in zip(xs, self.steps):
            c = QColor(_status_color(t, st.status))
            if st.id == self.selected:
                p.setPen(QPen(QColor(t["text"]), 2))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QRectF(x - r - 4, y - r - 4, 2 * r + 8, 2 * r + 8))
            p.setPen(Qt.NoPen)
            p.setBrush(c if st.status != "todo" else QColor(t["btn_bg"]))
            p.drawEllipse(QRectF(x - r, y - r, 2 * r, 2 * r))
            p.setPen(QColor("#ffffff" if st.status != "todo" else t["text"]))
            bf = QFont(f)
            bf.setBold(True)
            bf.setPointSizeF(8.5)
            p.setFont(bf)
            mark = "✓" if st.status in ("done", "known") else str(st.number)
            p.drawText(QRectF(x - r, y - r, 2 * r, 2 * r), Qt.AlignCenter, mark)
            p.setFont(f)
            p.setPen(QColor(t["text"] if st.id == self.selected else t["muted"]))
            label = fm.elidedText(st.title, Qt.ElideRight, int(max(col, 30)))
            p.drawText(QRectF(x - col / 2, y + r + 6, col, 16), Qt.AlignHCenter | Qt.AlignTop, label)
        p.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        x = event.position().x()
        xs = self._centres()
        if xs:
            i = min(range(len(xs)), key=lambda k: abs(xs[k] - x))
            self.on_select(self.steps[i].id)


class StepDots(QWidget):
    """A folded protocol's progress in one glance: one small dot per step."""

    def __init__(self, steps: list[Any], theme: dict[str, Any]) -> None:
        super().__init__()
        self.steps, self.theme = steps, theme
        self.setFixedSize(12 * len(steps) + 2, 12)

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QColor, QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        for i, st in enumerate(self.steps):
            p.setBrush(QColor(_status_color(self.theme, st.status) if st.status != "todo" else self.theme["btn_bg"]))
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


class ProtocolCard(QFrame):
    """A protocol. Folded, it's one line: its name, a dot per step and how far you are. Open, it shows its
    steps as a bar of circles (StepBar) and one step at a time: what kind of step it is, where you stand
    and why, what you can do (check, done), and its resources as cards. In edit mode every stage and link
    can be moved, renamed, added or removed.

    act(action, *args) changes the protocol (see app.protocol_action); on_check(stage) opens the level
    check; on_add_link(stage id) and on_rename(stage) ask for text; on_publish() sends it to the maker;
    on_toggle() opens or folds it; on_select(step id) shows another step."""

    def __init__(self, p: dict[str, Any], theme: dict[str, Any], editing: bool, act: Callable[..., Any],
                 on_check: Callable[[dict[str, Any]], None], on_open: Callable[[str], Any],
                 on_edit: Callable[[], None], on_publish: Callable[[], None],
                 on_add_link: Callable[[str], None], on_rename: Callable[[dict[str, Any]], None],
                 on_add_stage: Callable[[], None], vote_item: Callable[[dict[str, Any]], Callable[[bool], int]],
                 vote_of: Callable[[dict[str, Any]], int], is_open: bool = True, selected: str = "",
                 on_toggle: Callable[[], None] | None = None, on_select: Callable[[str], None] | None = None) -> None:
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
        if it.get("who"):
            lay.addWidget(_label("Who can apply: " + it["who"], _muted(theme, 10.5)))
        if it.get("student"):
            lay.addWidget(_label("Students: " + it["student"], _muted(theme, 10.5)))
        if it.get("summary"):
            lay.addWidget(_label(it["summary"], f"color:{theme['text']}; font-size:10.5px; background:transparent;"))
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
