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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

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


class FlowRow(QWidget):
    """Mode buttons that wrap onto a second line instead of making the panel wider."""

    PER_LINE = 3

    def __init__(self) -> None:
        super().__init__()
        self._lines = QVBoxLayout(self)
        self._lines.setContentsMargins(0, 0, 0, 0)
        self._lines.setSpacing(4)
        self._line: QHBoxLayout | None = None
        self._count = 0

    def add(self, w: QWidget) -> None:
        if self._line is None or self._count % self.PER_LINE == 0:
            if self._line is not None:
                self._line.addStretch(1)
            self._line = QHBoxLayout()
            self._line.setSpacing(4)
            self._lines.addLayout(self._line)
        self._line.addWidget(w)
        self._count += 1

    def finish(self) -> None:
        """Keep the last line's buttons at their own size."""
        if self._line is not None:
            self._line.addStretch(1)


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


def _small_button(text: str, tip: str, theme: dict[str, Any], on_click: Callable[[], Any]) -> QPushButton:
    b = QPushButton(text)
    b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    b.setFixedHeight(22)
    b.setStyleSheet(f"QPushButton {{ background:transparent; color:{theme['muted']}; border:none; padding:0 4px; "
                    f"font-size:11px; }} QPushButton:hover {{ color:{theme['text']}; }}")
    b.clicked.connect(lambda checked=False: on_click())
    return b


class ProtocolCard(QFrame):
    """A protocol: its stages in order, each with its status (done, known, start here), its links and
    its level check. In edit mode every stage and link can be moved, renamed, added or removed.

    act(action, *args) changes the protocol (see app.protocol_action); on_check(stage) opens the level
    check; on_add_link(stage id) and on_rename(stage) ask for text; on_publish() sends it to the maker."""

    def __init__(self, p: dict[str, Any], theme: dict[str, Any], editing: bool, act: Callable[..., Any],
                 on_check: Callable[[dict[str, Any]], None], on_open: Callable[[str], Any],
                 on_edit: Callable[[], None], on_publish: Callable[[], None],
                 on_add_link: Callable[[str], None], on_rename: Callable[[dict[str, Any]], None],
                 on_add_stage: Callable[[], None], vote_item: Callable[[dict[str, Any]], Callable[[bool], int]],
                 vote_of: Callable[[dict[str, Any]], int]) -> None:
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
        lay.setSpacing(5)
        head = QHBoxLayout()
        flag = "🏁 " if p["finished"] else "🧭 "
        src = p.get("source", "mine")
        badge_color = theme["good"] if src == "reviewed" else theme["muted"]
        badge = SOURCE.get(src, "")
        if src == "mine" and p.get("based_on"):
            badge += " · changed from a reviewed one"
        head.addWidget(_label(f"<b>{flag}{html.escape(p['title'])}</b> "
                              f"<span style='color:{theme['muted']}'>{p['done']}/{p['total']}</span><br>"
                              f"<span style='color:{badge_color}; font-size:10px'>{html.escape(badge)}</span>",
                              f"color:{theme['text']}; font-size:12px; background:transparent;", rich=True), 1)
        head.addWidget(_small_button("✅ Done editing" if editing else "✏️ Edit",
                                     "Reorder, rename, add or remove stages and links", theme, on_edit), 0, Qt.AlignTop)
        head.addWidget(_small_button("📤 Publish", "Send this protocol to myGeeKy, for everyone", theme, on_publish),
                       0, Qt.AlignTop)
        head.addWidget(_small_button("✕", "Stop this protocol", theme, lambda: act("stop")), 0, Qt.AlignTop)
        lay.addLayout(head)
        bar = QFrame()
        bar.setFixedHeight(4)
        share = p["done"] / max(p["total"], 1)
        bar.setStyleSheet(f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {theme['good']}, "
                          f"stop:{max(share, 0.001):.3f} {theme['good']}, stop:{min(share + 0.001, 1):.3f} {theme['btn_bg']}, "
                          f"stop:1 {theme['btn_bg']}); border-radius:2px;")
        lay.addWidget(bar)
        if p.get("summary"):
            lay.addWidget(_label(p["summary"], _muted(theme, 10.5)))
        last = len(p["stages"]) - 1
        for i, st in enumerate(p["stages"]):
            lay.addWidget(self._stage(st, i, last))
        if editing:
            row = QHBoxLayout()
            row.addWidget(_small_button("➕ Add a stage", "A new stage before 'Use it in your own work'", theme,
                                        on_add_stage))
            row.addStretch(1)
            lay.addLayout(row)
        self.setStyleSheet(_card_style("protocolCard", theme))

    def _stage(self, st: dict[str, Any], i: int, last: int) -> QFrame:
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
