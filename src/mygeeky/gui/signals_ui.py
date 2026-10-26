"""The 📡 Signals planet's own widgets: "Your field" (a thin ruler that unfolds into a
radar), cards for calls for contributors, and the two small windows: invite
contributors to one of your projects, and send someone a signal.

Everything shown from someone's beacon is plain text (Qt.PlainText or escaped):
beacons are untrusted input. Nothing here talks to GitHub: the panel runs the
work in the background (gui/app.py) and hands the results back."""
from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPlainTextEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
PINK = "#ff6fd8"
VIOLET = "#8b6dff"
PALETTE = ("#ff6fd8", "#8b6dff", "#4fd1ff", "#3ddc97", "#f6b44a", "#ff8f6b")

# line drawings in the planets' own style; they take the colour they're given
_SVG = {
    "invite": '<path d="M15 20v-1.5a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4V20"/><circle cx="8.5" cy="7.5" r="3.5"/>'
              '<path d="M19 8v6M16 11h6"/>',
    "send": '<path d="M21.5 2.5 14.6 21a.6.6 0 0 1-1.1.05L10 14l-7.05-3.5a.6.6 0 0 1 .05-1.1L21.5 2.5Z"/>'
            '<path d="M21.5 2.5 10 14"/>',
}


def icon(name: str, color: str, size: int = 16) -> QIcon:
    """One of the line icons, drawn at `size` in `color` (empty if Qt can't draw SVG)."""
    try:
        from PySide6.QtSvg import QSvgRenderer
    except Exception:
        return QIcon()
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
           f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{_SVG[name]}</svg>')
    out = QIcon()
    for scale in (1, 2):
        pix = QPixmap(size * scale, size * scale)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(painter)
        painter.end()
        pix.setDevicePixelRatio(scale)
        out.addPixmap(pix)
    return out


def _color_of(name: str) -> str:
    return PALETTE[sum(ord(c) for c in name) % len(PALETTE)] if name else PALETTE[0]


def _initials(name: str) -> str:
    parts = [p for p in name.replace("-", " ").replace("_", " ").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def _muted(theme: dict[str, Any], size: float = 10.5) -> str:
    return f"color:{theme['muted']}; font-size:{size}px; background:transparent;"


def _button_style(theme: dict[str, Any], accent: bool = False) -> str:
    if accent:
        return ("QPushButton { color:#ffffff; border:none; border-radius:9px; padding:6px 10px; font-size:11px; "
                f"font-weight:700; background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {PINK}, stop:1 {VIOLET}); }}"
                "QPushButton:disabled { color:rgba(255,255,255,120); }")
    return (f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['text']}; border:none; border-radius:9px; "
            f"padding:6px 10px; font-size:11px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{theme['btn_hover']}; }}"
            f"QPushButton:checked {{ background:{theme['section_btn']}; }}"
            f"QPushButton:disabled {{ color:{theme['muted']}; }}")


# --------------------------------------------------------------------------- your field: the ruler and the radar
class FieldMap(QWidget):
    """Everyone on Signals and every call that fits you, placed by how close they are to
    your work. Folded: a thin ruler (calls above the line, people below; further right =
    closer). Unfolded: a radar, you in the middle. Click a dot to open it."""

    picked = Signal(str)

    FOLDED_HEIGHT = 62

    def __init__(self, theme: dict[str, Any]) -> None:
        super().__init__()
        self.theme = theme
        self.items: list[dict[str, Any]] = []        # {id, login, label, fit, call}
        self.selected: str | None = None
        self.unfolded = False
        self._dots: list[tuple[QPointF, float, dict[str, Any]]] = []
        self.hovered: dict[str, Any] | None = None      # its label is drawn here (a system tooltip came out unreadable)
        self._me = QPixmap(str(ASSETS_DIR / "icon_64.png"))
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(self.FOLDED_HEIGHT)

    def set_items(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        if self.selected and not any(i["id"] == self.selected for i in items):
            self.selected = None
        self.update()

    def set_unfolded(self, unfolded: bool) -> None:
        self.unfolded = unfolded
        self.setFixedHeight(min(300, max(220, self.width() - 20)) if unfolded else self.FOLDED_HEIGHT)
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self.unfolded:
            self.setFixedHeight(min(300, max(220, self.width() - 20)))

    # where each dot goes
    def _layout_ruler(self) -> list[tuple[QPointF, float, dict[str, Any]]]:
        w, h = self.width(), self.height()
        left, right = 26.0, w - 24.0
        mid = h / 2
        r = 7.0
        out = []
        for is_call, rows in ((True, (mid - 10, mid - 24)), (False, (mid + 10, mid + 24))):
            ends = [-1e9] * len(rows)
            group = sorted((i for i in self.items if bool(i.get("call")) == is_call), key=lambda i: i["fit"])
            for item in group:
                x = left + min(max(item["fit"], 0.0), 0.97) * (right - left)
                row = next((k for k, e in enumerate(ends) if x - e >= 2 * r + 3), None)
                if row is None:
                    row = min(range(len(rows)), key=lambda k: ends[k])
                ends[row] = x
                y = max(r + 1, min(h - r - 1, rows[row]))
                out.append((QPointF(x, y), r, item))
        return out

    def _layout_radar(self) -> list[tuple[QPointF, float, dict[str, Any]]]:
        w, h = self.width(), self.height()
        c = QPointF(w / 2, h / 2)
        radius = min(w, h) / 2 - 12
        out = []
        for k, item in enumerate(self.items):
            dist = radius * (0.2 + 0.78 * (1 - min(max(item["fit"], 0.0), 1.0)))
            a = math.radians(k * 137.5 + 20)
            out.append((QPointF(c.x() + dist * math.cos(a), c.y() + dist * math.sin(a)), 10.0, item))
        return out

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        muted = QColor(self.theme["muted"]) if self.theme["muted"].startswith("#") else QColor(160, 160, 180)
        w, h = self.width(), self.height()
        self._dots = self._layout_radar() if self.unfolded else self._layout_ruler()
        if self.unfolded:
            c = QPointF(w / 2, h / 2)
            radius = min(w, h) / 2 - 12
            pen = QPen(QColor(236, 236, 248, 40), 1, Qt.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            for f in (0.25, 0.5, 0.75, 1.0):
                p.drawEllipse(c, radius * f, radius * f)
            if not self._me.isNull():
                p.drawPixmap(QRectF(c.x() - 17, c.y() - 17, 34, 34), self._me, QRectF(self._me.rect()))
        else:
            mid = h / 2
            left, right = 26.0, w - 24.0
            grad = QLinearGradient(left, 0, right, 0)
            grad.setColorAt(0, QColor(246, 180, 74, 90))
            grad.setColorAt(0.6, QColor(139, 109, 255, 150))
            grad.setColorAt(1, QColor(PINK))
            p.setPen(QPen(QBrush(grad), 2))
            p.drawLine(QPointF(left, mid), QPointF(right, mid))
            p.setPen(QPen(QColor(236, 236, 248, 70), 1))
            for f in (0.25, 0.5, 0.75):
                x = left + f * (right - left)
                p.drawLine(QPointF(x, mid - 4), QPointF(x, mid + 4))
            p.setPen(muted)
            small = QFont(self.font())
            small.setPointSizeF(7)
            p.setFont(small)
            p.drawText(QRectF(0, mid - 8, 24, 16), Qt.AlignCenter, "far")
            if not self._me.isNull():
                p.drawPixmap(QRectF(right + 2, mid - 9, 18, 18), self._me, QRectF(self._me.rect()))
        font = QFont(self.font())
        font.setBold(True)
        for center, r, item in self._dots:
            color = QColor(_color_of(item.get("login", "")))
            rect = QRectF(center.x() - r, center.y() - r, 2 * r, 2 * r)
            ring = PINK if item["id"] == self.selected else self.theme.get("card_bg", "#1f1f2b")
            p.setPen(QPen(QColor(ring) if ring.startswith("#") else QColor(23, 23, 31), 2 if item["id"] == self.selected else 1.5))
            p.setBrush(color)
            if item.get("call"):
                p.drawRoundedRect(rect, 4, 4)
            else:
                p.drawEllipse(rect)
            font.setPointSizeF(max(5.5, r * 0.62))
            p.setFont(font)
            p.setPen(QColor("#15151f"))
            p.drawText(rect, Qt.AlignCenter, _initials(item.get("login", "")))
        if not self.items:
            p.setPen(muted)
            p.drawText(self.rect(), Qt.AlignCenter, "Nobody on Signals yet")
        spot = next(((c, r) for c, r, it in self._dots if self.hovered and it["id"] == self.hovered["id"]), None)
        if spot:
            self._draw_label(p, spot[0], spot[1], self.hover_text(self.hovered))
        p.end()

    @staticmethod
    def hover_text(item: dict[str, Any]) -> str:
        what = "project calling" if item.get("call") else "on Signals"
        return f"{item['label']} · {what} · {round(item['fit'] * 100)}% fit"

    def _draw_label(self, p: QPainter, center: QPointF, r: float, text: str) -> None:
        """A small dark pill with the dot's name, kept inside the widget."""
        font = QFont(self.font())
        font.setPointSizeF(8)
        font.setBold(False)
        p.setFont(font)
        fm = p.fontMetrics()
        w = min(fm.horizontalAdvance(text) + 14, self.width() - 4)
        h = fm.height() + 6
        x = min(max(center.x() - w / 2, 2), self.width() - w - 2)
        above = center.y() - r - h - 3
        y = above if above >= 1 else min(center.y() + r + 3, self.height() - h - 1)
        box = QRectF(x, y, w, h)
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.setBrush(QColor(20, 20, 30, 235))
        p.drawRoundedRect(box, h / 2, h / 2)
        p.setPen(QColor("#f0f0f5"))
        p.drawText(box, Qt.AlignCenter, fm.elidedText(text, Qt.ElideRight, int(w - 10)))

    def _hit(self, pos: QPointF) -> dict[str, Any] | None:
        best = None
        for center, r, item in self._dots:
            d = math.hypot(center.x() - pos.x(), center.y() - pos.y())
            if d <= r + 3 and (best is None or d < best[0]):
                best = (d, item)
        return best[1] if best else None

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        item = self._hit(event.position())
        if (item or {}).get("id") != (self.hovered or {}).get("id"):
            self.hovered = item
            self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self.hovered is not None:
            self.hovered = None
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        item = self._hit(event.position())
        if item:
            self.selected = None if self.selected == item["id"] else item["id"]
            self.update()
            self.picked.emit(self.selected or "")


class FieldCard(QFrame):
    """The folded radar with its header and the two actions: invite and send."""

    def __init__(self, theme: dict[str, Any], on_invite: Callable[[], None], on_send: Callable[[], None],
                 unfolded: bool, on_fold: Callable[[bool], None]) -> None:
        super().__init__()
        self.setObjectName("fieldCard")
        self.theme = theme
        lay = QVBoxLayout(self)
        lay.setContentsMargins(9, 6, 9, 8)
        lay.setSpacing(4)
        head = QHBoxLayout()
        self.title = QLabel("")
        self.title.setTextFormat(Qt.RichText)
        self.title.setStyleSheet(f"color:{theme['text']}; font-size:11px; background:transparent;")
        head.addWidget(self.title, 1)
        self.toggle = QPushButton("⌄")
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.toggle.setFixedSize(26, 20)
        self.toggle.setStyleSheet(f"QPushButton {{ background:transparent; color:{theme['accent']}; "
                                  f"border:1px solid {theme['border']}; border-radius:10px; font-size:12px; }}"
                                  f"QPushButton:hover {{ background:{theme['btn_hover']}; }}")
        self.toggle.clicked.connect(lambda: self._fold(not self.map.unfolded))
        head.addWidget(self.toggle)
        lay.addLayout(head)
        self.map = FieldMap(theme)
        lay.addWidget(self.map)
        self.picked_area = QVBoxLayout()
        self.picked_area.setSpacing(4)
        lay.addLayout(self.picked_area)
        acts = QHBoxLayout()
        acts.setSpacing(6)
        self.invite_btn = QPushButton("Invite to a project")
        self.invite_btn.setIcon(icon("invite", "#ffffff", 15))
        self.invite_btn.setToolTip("Invite people whose skills fit to help with one of your repos")
        self.invite_btn.setStyleSheet(_button_style(theme, accent=True))
        self.send_btn = QPushButton("Send a signal")
        self.send_btn.setIcon(icon("send", theme["text"] if theme["text"].startswith("#") else "#f0f0f5", 14))
        self.send_btn.setToolTip("Thank someone, or tell them you learned from or used their work")
        self.send_btn.setStyleSheet(_button_style(theme))
        for b, fn in ((self.invite_btn, on_invite), (self.send_btn, on_send)):
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, f=fn: f())
            acts.addWidget(b, 1)
        lay.addLayout(acts)
        self._on_fold = on_fold
        self.setStyleSheet(f"QFrame#fieldCard {{ background:{theme['card_bg']}; border-radius:12px; }}")
        self._fold(unfolded, tell=False)

    def _fold(self, unfolded: bool, tell: bool = True) -> None:
        self.map.set_unfolded(unfolded)
        self.toggle.setText("⌃" if unfolded else "⌄")
        self.toggle.setToolTip("Fold the radar" if unfolded else "Open the radar")
        if tell:
            self._on_fold(unfolded)

    def set_counts(self, people: int, calls: int) -> None:
        self.title.setText(f"<b>📡 Your field</b> <span style='color:{self.theme['muted']}'>· {people} "
                           f"{'person' if people == 1 else 'people'} · {calls} calling</span>")


# --------------------------------------------------------------------------- calls: other people's, and yours
def _chips(skills: list[str], matched: list[str], theme: dict[str, Any]) -> str:
    out = []
    for s in skills:
        if s in matched:
            out.append(f"<span style='color:{theme['good']}; font-weight:700'>✓ {html.escape(s)}</span>")
        else:
            out.append(f"<span style='color:{theme['muted']}'>{html.escape(s)}</span>")
    return " &nbsp;·&nbsp; ".join(out)


class CallCard(QFrame):
    """Someone's call for contributors that fits you (or 🔭 new territory)."""

    def __init__(self, call: dict[str, Any], theme: dict[str, Any], make_avatar: Callable[[str, str, int], QWidget],
                 on_join: Callable[["CallCard"], None], on_leave: Callable[["CallCard"], None],
                 on_hide: Callable[["CallCard"], None], on_open: Callable[[str], Any]) -> None:
        super().__init__()
        self.call = call
        self.setObjectName("callCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(9, 8, 9, 8)
        lay.setSpacing(5)
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(make_avatar(call["owner"], call.get("avatar_url", ""), 26))
        box = QVBoxLayout()
        box.setSpacing(0)
        name = QLabel(call["full_name"])
        name.setTextFormat(Qt.PlainText)
        name.setStyleSheet(f"color:{theme['link']}; font-size:11.5px; font-weight:700; background:transparent;")
        box.addWidget(name)
        meta = QLabel(f"{call['level_label']} · {call['time_label']} · {call['days_left']} days left")
        meta.setStyleSheet(_muted(theme, 10))
        box.addWidget(meta)
        head.addLayout(box, 1)
        fit = QLabel(f"{round(call['fit'] * 100)}%")
        fit.setToolTip("How well it fits your work, worked out on this computer")
        fit.setStyleSheet(f"color:{theme['good']}; font-size:10.5px; font-weight:700; background:transparent;")
        head.addWidget(fit, 0, Qt.AlignTop)
        lay.addLayout(head)
        note = QLabel(call["note"])
        note.setTextFormat(Qt.PlainText)
        note.setWordWrap(True)
        note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        note.setStyleSheet(f"color:{theme['text']}; font-size:11.5px; background:transparent;")
        lay.addWidget(note)
        chips = QLabel(_chips(call["skills"], call.get("matched") or [], theme))
        chips.setTextFormat(Qt.RichText)
        chips.setWordWrap(True)
        chips.setStyleSheet("font-size:10.5px; background:transparent;")
        lay.addWidget(chips)
        tag = QLabel("🔭 new territory: outside your usual work" if call.get("explore") else "fits your work")
        tag.setStyleSheet(f"color:{theme['explore'] if call.get('explore') else theme['accent']}; font-size:10px; "
                          "font-weight:700; background:transparent;")
        lay.addWidget(tag)
        self.done = QLabel("")
        self.done.setWordWrap(True)
        self.done.setStyleSheet(f"color:{theme['good']}; font-size:10.5px; background:transparent;")
        lay.addWidget(self.done)
        row = QHBoxLayout()
        row.setSpacing(5)
        self.join_btn = QPushButton("🙋 I'm in")
        self.join_btn.setStyleSheet(_button_style(theme, accent=True))
        self.join_btn.setToolTip(f"Tell {call['owner']} privately, with the skills of yours that matched. "
                                 "Your suggestions will lean a little toward this area too.")
        self.join_btn.clicked.connect(lambda: on_join(self))
        self.leave_btn = QPushButton("Changed my mind")
        self.leave_btn.setStyleSheet(_button_style(theme))
        self.leave_btn.clicked.connect(lambda: on_leave(self))
        repo_btn = QPushButton("See the repo")
        repo_btn.setStyleSheet(_button_style(theme))
        repo_btn.clicked.connect(lambda: on_open(call["repo_url"]))
        self.hide_btn = QPushButton("Not for me")
        self.hide_btn.setStyleSheet(_button_style(theme))
        self.hide_btn.setToolTip("Hide this call. Nobody is told.")
        self.hide_btn.clicked.connect(lambda: on_hide(self))
        for b in (self.join_btn, self.leave_btn, repo_btn, self.hide_btn):
            b.setCursor(Qt.PointingHandCursor)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.setStyleSheet(f"QFrame#callCard {{ background:{theme['card_bg']}; border-radius:10px; }}")
        self.set_joined(bool(call.get("joined")))

    def set_joined(self, joined: bool) -> None:
        self.call["joined"] = joined
        matched = self.call.get("matched") or []
        self.done.setText(f"✓ Sent privately to {self.call['owner']}"
                          + (f", with the skills that matched: {', '.join(matched)}." if matched else ".")
                          if joined else "")
        self.done.setVisible(joined)
        self.join_btn.setVisible(not joined)
        self.hide_btn.setVisible(not joined)
        self.leave_btn.setVisible(joined)

    def set_busy(self, busy: bool, text: str = "") -> None:
        for b in (self.join_btn, self.leave_btn, self.hide_btn):
            b.setEnabled(not busy)
        if text:
            self.done.setText(text)
            self.done.setVisible(True)


class MyCallCard(QFrame):
    """One of your own calls, with who said they're in."""

    def __init__(self, call: dict[str, Any], theme: dict[str, Any], make_avatar: Callable[[str, str, int], QWidget],
                 on_close: Callable[["MyCallCard", bool], None], on_open: Callable[[str], Any]) -> None:
        super().__init__()
        self.call = call
        self.setObjectName("myCallCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(9, 8, 9, 8)
        lay.setSpacing(5)
        head = QHBoxLayout()
        name = QLabel(call["full_name"])
        name.setTextFormat(Qt.PlainText)
        name.setStyleSheet(f"color:{theme['link']}; font-size:11.5px; font-weight:700; background:transparent;")
        head.addWidget(name, 1)
        n = len(call.get("responders") or [])
        state = QLabel("filled" if call.get("filled") else f"{n} in")
        state.setStyleSheet(f"color:{PINK}; font-size:10px; font-weight:700; background:transparent;")
        head.addWidget(state)
        lay.addLayout(head)
        meta = QLabel(f"{call['level_label']} · {call['time_label']} · {call['days_left']} days left")
        meta.setStyleSheet(_muted(theme, 10))
        lay.addWidget(meta)
        note = QLabel(call["note"])
        note.setTextFormat(Qt.PlainText)
        note.setWordWrap(True)
        note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        note.setStyleSheet(f"color:{theme['text']}; font-size:11.5px; background:transparent;")
        lay.addWidget(note)
        skills = QLabel(" · ".join(call["skills"]))
        skills.setTextFormat(Qt.PlainText)
        skills.setWordWrap(True)
        skills.setStyleSheet(_muted(theme))
        lay.addWidget(skills)
        who = QLabel("WHO'S IN")
        who.setStyleSheet(f"color:{theme['muted']}; font-size:9.5px; font-weight:700; letter-spacing:0.5px; "
                          "background:transparent; margin-top:2px;")
        lay.addWidget(who)
        if not call.get("responders"):
            none = QLabel("Nobody yet. It's shown to people whose skills fit; you'll see who says yes.")
            none.setWordWrap(True)
            none.setStyleSheet(_muted(theme))
            lay.addWidget(none)
        for r in call.get("responders") or []:
            row = QHBoxLayout()
            row.setSpacing(6)
            row.addWidget(make_avatar(r["login"], r.get("avatar_url", ""), 22))
            line = QLabel(f"<b>{html.escape(r['login'])}</b> &nbsp;"
                          + _chips(r.get("skills") or [], r.get("skills") or [], theme))
            line.setTextFormat(Qt.RichText)
            line.setWordWrap(True)
            line.setStyleSheet(f"color:{theme['text']}; font-size:11px; background:transparent;")
            row.addWidget(line, 1)
            open_btn = QPushButton("↗")
            open_btn.setFixedSize(24, 22)
            open_btn.setToolTip(f"Open {r['login']}'s GitHub profile")
            open_btn.setStyleSheet(_button_style(theme))
            open_btn.clicked.connect(lambda checked=False, url=r.get("profile_url", ""): on_open(url))
            row.addWidget(open_btn)
            lay.addLayout(row)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(_muted(theme))
        self.status.setVisible(False)
        lay.addWidget(self.status)
        row = QHBoxLayout()
        row.setSpacing(5)
        self.fill_btn = QPushButton("Mark as filled")
        self.fill_btn.setToolTip("It stops showing to others; it stays here until it ends.")
        self.close_btn = QPushButton("Close the call")
        self.close_btn.setToolTip("It leaves your beacon.")
        for b, filled in ((self.fill_btn, True), (self.close_btn, False)):
            b.setStyleSheet(_button_style(theme))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, f=filled: on_close(self, f))
            row.addWidget(b)
        self.fill_btn.setVisible(not call.get("filled"))
        row.addStretch(1)
        lay.addLayout(row)
        self.setStyleSheet(f"QFrame#myCallCard {{ background:{theme['card_bg']}; border-radius:10px; }}")

    def set_busy(self, busy: bool, text: str = "") -> None:
        self.fill_btn.setEnabled(not busy)
        self.close_btn.setEnabled(not busy)
        self.status.setText(text)
        self.status.setVisible(bool(text))


# --------------------------------------------------------------------------- the two windows
def _window_style(theme: dict[str, Any]) -> str:
    return ("QDialog { background:#17171f; } QLabel { color:#f0f0f5; font-size:11.5px; }"
            "QLineEdit, QPlainTextEdit, QComboBox, QListWidget { background:#22222e; color:#f0f0f5; "
            "border:1px solid #34344a; border-radius:7px; padding:5px; font-size:11.5px; }"
            "QListWidget::item { padding:5px 4px; border-radius:6px; }"
            "QListWidget::item:selected { background:rgba(255,111,216,60); color:#ffffff; }"
            + _button_style({**theme, "text": "#f0f0f5", "muted": "rgba(240,240,245,150)",
                             "btn_bg": "rgba(255,255,255,26)", "btn_hover": "rgba(255,255,255,51)",
                             "section_btn": "rgba(255,111,216,90)"}))


def _label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet("color:rgba(240,240,245,150); font-size:9.5px; font-weight:700; letter-spacing:0.6px;")
    return lbl


class _Choice(QWidget):
    """A row of buttons where one is chosen (level, time)."""

    def __init__(self, options: dict[str, str], chosen: str, on_change: Callable[[], None]) -> None:
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        for key, label in options.items():
            b = QPushButton(label)
            b.setCheckable(True)
            b.setChecked(key == chosen)
            b.setCursor(Qt.PointingHandCursor)
            self.group.addButton(b)
            self.buttons[key] = b
            b.toggled.connect(lambda on: on and on_change())
            lay.addWidget(b)
        lay.addStretch(1)

    def value(self) -> str:
        return next(k for k, b in self.buttons.items() if b.isChecked())


class InviteWindow(QDialog):
    """Invite contributors to one of your repos: a call that reaches people whose skills fit."""

    def __init__(self, parent: QWidget, theme: dict[str, Any], on_publish: Callable[["InviteWindow", dict], None],
                 open_calls: int) -> None:
        super().__init__(parent)
        from ..beacon import CALL_DAYS, CALL_LEVELS, CALL_TIMES, MAX_CALL_SKILLS, MAX_CALLS, MAX_NOTE
        self.max_skills, self.max_note = MAX_CALL_SKILLS, MAX_NOTE
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)   # in front of the always-on-top panel
        self.setWindowTitle("Invite contributors")
        self.setWindowIcon(icon("invite", PINK, 32))
        self.setMinimumWidth(400)
        self.repos: list[dict[str, Any]] = []
        self.skill_buttons: dict[str, QPushButton] = {}
        lay = QVBoxLayout(self)
        lay.setSpacing(7)
        title = QLabel("Invite contributors")
        title.setStyleSheet("font-size:15px; font-weight:800;")
        lay.addWidget(title)
        intro = QLabel("Your call goes into your beacon. Each person's own myGeeKy decides whether it fits them: "
                       "nobody is targeted, and you only ever see who says yes.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color:rgba(240,240,245,170); font-size:11px;")
        lay.addWidget(intro)
        lay.addWidget(_label("Which project"))
        self.repo = QComboBox()
        self.repo.addItem("Loading your repos…")
        self.repo.setEnabled(False)
        self.repo.currentIndexChanged.connect(self._repo_changed)
        lay.addWidget(self.repo)
        lay.addWidget(_label(f"Skills you need (up to {MAX_CALL_SKILLS})"))
        self.skills_box = QWidget()
        self.skills_grid = QGridLayout(self.skills_box)
        self.skills_grid.setContentsMargins(0, 0, 0, 0)
        self.skills_grid.setSpacing(4)
        lay.addWidget(self.skills_box)
        self.add_skill = QLineEdit()
        self.add_skill.setPlaceholderText("Add a skill and press Enter")
        self.add_skill.setMaxLength(40)
        self.add_skill.returnPressed.connect(self._add_skill)
        lay.addWidget(self.add_skill)
        lay.addWidget(_label("What you need, in a sentence or two"))
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText("e.g. Looking for a second pair of eyes on the LD-pruning step before we publish.")
        self.note.setFixedHeight(66)
        self.note.textChanged.connect(self._changed)
        lay.addWidget(self.note)
        self.count = QLabel("")
        self.count.setAlignment(Qt.AlignRight)
        self.count.setStyleSheet("color:rgba(240,240,245,140); font-size:10px;")
        lay.addWidget(self.count)
        lay.addWidget(_label("Level"))
        self.level = _Choice(CALL_LEVELS, "any", self._changed)
        lay.addWidget(self.level)
        lay.addWidget(_label("Time it takes"))
        self.time = _Choice(CALL_TIMES, "hours", self._changed)
        lay.addWidget(self.time)
        lay.addWidget(_label("Open for"))
        self.days = QComboBox()
        for d in CALL_DAYS:
            self.days.addItem(f"{d} days", d)
        self.days.setCurrentIndex(1)
        self.days.currentIndexChanged.connect(self._changed)
        lay.addWidget(self.days)
        lay.addWidget(_label("How others will see it"))
        self.preview = QLabel("")
        self.preview.setTextFormat(Qt.RichText)
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet("border:1px dashed #44445a; border-radius:9px; padding:8px; font-size:11px;")
        lay.addWidget(self.preview)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        row = QHBoxLayout()
        self.limit = QLabel(f"{open_calls}/{MAX_CALLS} open calls")
        self.limit.setStyleSheet("color:rgba(240,240,245,140); font-size:10px;")
        row.addWidget(self.limit, 1)
        close = QPushButton("Cancel")
        close.clicked.connect(self.reject)
        self.publish = QPushButton("Publish the call")
        self.publish.setIcon(icon("invite", "#ffffff", 14))
        self.publish.setStyleSheet(_button_style(theme, accent=True))
        self.publish.clicked.connect(lambda: on_publish(self, self.payload()))
        row.addWidget(close)
        row.addWidget(self.publish)
        lay.addLayout(row)
        self.setStyleSheet(_window_style(theme) + "QPushButton[accent='true'] {}")
        self.publish.setStyleSheet(_button_style(theme, accent=True))
        self._changed()

    # the repos arrive from GitHub in the background
    def set_repos(self, repos: list[dict[str, Any]]) -> None:
        self.repos = repos
        self.repo.blockSignals(True)
        self.repo.clear()
        for r in repos:
            self.repo.addItem(r["name"], r["name"])
        self.repo.blockSignals(False)
        self.repo.setEnabled(bool(repos))
        if not repos:
            self.repo.addItem("No public repos of yours found")
        self._repo_changed()

    def _repo_changed(self) -> None:
        repo = next((r for r in self.repos if r["name"] == self.repo.currentData()), None)
        pool = list(dict.fromkeys([*(repo or {}).get("topics", []), *([repo["language"].lower()] if repo and repo.get("language") else [])]))
        chosen = set(pool[:3])
        self._set_skills(pool, chosen)

    def _set_skills(self, pool: list[str], chosen: set[str]) -> None:
        while self.skills_grid.count():
            w = self.skills_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.skill_buttons = {}
        for k, s in enumerate(pool[:12]):
            b = QPushButton(s)
            b.setCheckable(True)
            b.setChecked(s in chosen)
            b.setCursor(Qt.PointingHandCursor)
            b.toggled.connect(self._skill_toggled)
            self.skill_buttons[s] = b
            self.skills_grid.addWidget(b, k // 3, k % 3)
        if not pool:
            hint = QLabel("This repo has no topics: add the skills below.")
            hint.setStyleSheet("color:rgba(240,240,245,140); font-size:10.5px;")
            self.skills_grid.addWidget(hint, 0, 0, 1, 3)
        self._changed()

    def _skill_toggled(self, on: bool) -> None:
        chosen = [s for s, b in self.skill_buttons.items() if b.isChecked()]
        if on and len(chosen) > self.max_skills:
            sender = self.sender()
            if isinstance(sender, QPushButton):
                sender.blockSignals(True)
                sender.setChecked(False)
                sender.blockSignals(False)
        self._changed()

    def _add_skill(self) -> None:
        from ..beacon import clean_interests
        new = clean_interests([self.add_skill.text()])
        self.add_skill.clear()
        if not new:
            return
        chosen = {s for s, b in self.skill_buttons.items() if b.isChecked()}
        if len(chosen) < self.max_skills:
            chosen.add(new[0])
        self._set_skills(list(dict.fromkeys([*self.skill_buttons, new[0]])), chosen)

    def payload(self) -> dict[str, Any]:
        return {"repo": self.repo.currentData() or "", "note": self.note.toPlainText().strip(),
                "skills": [s for s, b in self.skill_buttons.items() if b.isChecked()],
                "level": self.level.value(), "time": self.time.value(), "days": int(self.days.currentData())}

    def _changed(self) -> None:
        from ..beacon import CALL_LEVELS, CALL_TIMES
        if not hasattr(self, "publish"):
            return
        p = self.payload()
        n = len(p["note"])
        self.count.setText(f"{n}/{self.max_note} · no links")
        self.count.setStyleSheet(f"color:{'#f87171' if n > self.max_note else 'rgba(240,240,245,140)'}; font-size:10px;")
        repo = html.escape(p["repo"] or "your-repo")
        note = html.escape(p["note"] or "Your sentence shows here.")
        skills = html.escape(" · ".join(p["skills"]) or "the skills you need")
        self.preview.setText(f"<b style='color:#7fd8ff'>you/{repo}</b> &nbsp;<span style='color:#9b9bb2'>"
                             f"{CALL_LEVELS[p['level']]} · {CALL_TIMES[p['time']]} · {p['days']} days left</span><br>"
                             f"{note}<br><span style='color:#9b9bb2'>{skills}</span>")
        self.publish.setEnabled(bool(p["repo"]) and 10 <= n <= self.max_note and bool(p["skills"]))

    def set_busy(self, busy: bool, text: str = "", error: bool = False) -> None:
        self.publish.setEnabled(not busy)
        self.status.setText(text)
        self.status.setStyleSheet(f"color:{'#f87171' if error else '#34d399'}; font-size:11px;")


SIGNAL_CHOICES = (
    ("thanks", "🙏 Thanks", "for their work"),
    ("learn", "📚 Learned", "from their work"),
    ("used", "⭐ Used it", "one of their repos"),
    ("watching", "👀 Following", "their work"),
    ("collab", "🤝 Collaborate", "only shown if they choose you too"),
)


class SendSignalWindow(QDialog):
    """Pick a person, pick a signal (⭐ also asks which of their repos), see what they'll see, send."""

    def __init__(self, parent: QWidget, theme: dict[str, Any], people: list[dict[str, Any]],
                 on_send: Callable[["SendSignalWindow", str, str, str | None], None],
                 load_repos: Callable[["SendSignalWindow", str], None],
                 to: str | None = None, gesture: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setWindowTitle("Send a signal")
        self.setWindowIcon(icon("send", PINK, 32))
        self.setMinimumWidth(380)
        self.people = [p for p in people if p.get("can_receive") and not p.get("muted")]
        self.load_repos = load_repos
        self.to: str | None = None
        lay = QVBoxLayout(self)
        lay.setSpacing(7)
        title = QLabel("Send a signal")
        title.setStyleSheet("font-size:15px; font-weight:800;")
        lay.addWidget(title)
        lay.addWidget(_label("To"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search people on Signals, or a topic")
        self.search.textChanged.connect(self._filter)
        lay.addWidget(self.search)
        self.list = QListWidget()
        self.list.setFixedHeight(150)
        self.list.itemClicked.connect(lambda item: self._choose(item.data(Qt.UserRole)))
        lay.addWidget(self.list)
        self.chosen_row = QWidget()
        cr = QHBoxLayout(self.chosen_row)
        cr.setContentsMargins(0, 0, 0, 0)
        self.chosen = QLabel("")
        self.chosen.setTextFormat(Qt.RichText)
        cr.addWidget(self.chosen, 1)
        change = QPushButton("Change")
        change.clicked.connect(lambda: self._choose(None))
        cr.addWidget(change)
        lay.addWidget(self.chosen_row)
        lay.addWidget(_label("Signal"))
        grid = QGridLayout()
        grid.setSpacing(5)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.gesture_buttons: dict[str, QPushButton] = {}
        for k, (key, label, sub) in enumerate(SIGNAL_CHOICES):
            b = QPushButton(f"{label}\n{sub}")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(40)
            b.setStyleSheet("text-align:left; padding:6px 9px;")
            self.group.addButton(b)
            self.gesture_buttons[key] = b
            b.toggled.connect(lambda on: on and self._changed())
            grid.addWidget(b, k // 2, k % 2)
        lay.addLayout(grid)
        self.repo_label = _label("Which of their repos")
        lay.addWidget(self.repo_label)
        self.repo = QComboBox()
        self.repo.currentIndexChanged.connect(self._changed)
        lay.addWidget(self.repo)
        self.preview = QLabel("")
        self.preview.setTextFormat(Qt.RichText)
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet("border:1px dashed #44445a; border-radius:9px; padding:8px; font-size:11px;")
        lay.addWidget(self.preview)
        hint = QLabel("🔒 Sealed: only they can read it. One of each kind per person a month; no reply expected.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:rgba(240,240,245,150); font-size:10.5px;")
        lay.addWidget(hint)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        row = QHBoxLayout()
        row.addStretch(1)
        close = QPushButton("Cancel")
        close.clicked.connect(self.reject)
        self.send = QPushButton("Send")
        self.send.setIcon(icon("send", "#ffffff", 14))
        self.send.clicked.connect(lambda: on_send(self, self.to or "", self.gesture() or "",
                                                  self.repo.currentData() if self.gesture() == "used" else None))
        row.addWidget(close)
        row.addWidget(self.send)
        lay.addLayout(row)
        self.setStyleSheet(_window_style(theme))
        self.send.setStyleSheet(_button_style(theme, accent=True))
        self._filter("")
        self._choose(to if to and any(p["login"] == to for p in self.people) else None)
        if gesture in self.gesture_buttons:
            self.gesture_buttons[gesture].setChecked(True)
        self._changed()

    def gesture(self) -> str | None:
        return next((k for k, b in self.gesture_buttons.items() if b.isChecked()), None)

    def _filter(self, text: str) -> None:
        q = text.strip().lower()
        self.list.clear()
        for p in sorted(self.people, key=lambda p: p.get("fit", 0), reverse=True):
            if q and q not in p["login"].lower() and not any(q in i for i in p.get("interests") or []):
                continue
            shared = ", ".join((p.get("shared") or p.get("interests") or [])[:3])
            item = QListWidgetItem(f"{p['login']}   ·   {round(p.get('fit', 0) * 100)}%" + (f"\n{shared}" if shared else ""))
            item.setData(Qt.UserRole, p["login"])
            self.list.addItem(item)
        if not self.list.count():
            empty = QListWidgetItem("Nobody on Signals matches that yet." if self.people else
                                    "Nobody on Signals can receive signals yet.")
            empty.setFlags(Qt.NoItemFlags)
            self.list.addItem(empty)

    def _choose(self, login: str | None) -> None:
        self.to = login
        picking = login is None
        self.search.setVisible(picking)
        self.list.setVisible(picking)
        self.chosen_row.setVisible(not picking)
        if login:
            p = next(p for p in self.people if p["login"] == login)
            self.chosen.setText(f"<b>{html.escape(login)}</b> <span style='color:#9b9bb2'>"
                                f"{html.escape(p.get('status') or 'on Signals')}</span>")
        for b in self.gesture_buttons.values():
            b.setEnabled(not picking)
        self.repo.clear()
        if login:
            self.repo.addItem("Loading their repos…")
            self.load_repos(self, login)
        self._changed()

    def set_repos(self, login: str, names: list[str]) -> None:
        if login != self.to:
            return
        self.repo.blockSignals(True)
        self.repo.clear()
        for n in names:
            self.repo.addItem(n, n)
        if not names:
            self.repo.addItem("No public repos found")
        self.repo.blockSignals(False)
        self._changed()

    def _changed(self) -> None:
        if not hasattr(self, "send"):
            return
        g = self.gesture()
        used = g == "used"
        self.repo_label.setVisible(used and bool(self.to))
        self.repo.setVisible(used and bool(self.to))
        if self.to and g:
            what = {"thanks": "🙏 thanked you for your work", "learn": "📚 learned from your work",
                    "watching": "👀 is following your work",
                    "collab": "🤝 you both want to collaborate (only if they choose you too)",
                    "used": f"⭐ used {html.escape(self.repo.currentData() or 'one of your repos')} in their work"}[g]
            self.preview.setText(f"<span style='color:#9b9bb2'>{html.escape(self.to)} will see:</span><br>"
                                 f"<b>you</b> {what} · no reply needed")
            self.preview.setVisible(True)
        else:
            self.preview.setVisible(False)
        self.send.setEnabled(bool(self.to and g and (not used or self.repo.currentData())))

    def set_busy(self, busy: bool, text: str = "", error: bool = False) -> None:
        self.send.setEnabled(not busy)
        self.status.setText(text)
        self.status.setStyleSheet(f"color:{'#f87171' if error else '#34d399'}; font-size:11px;")
