"""The side rail: myGeeKy's navigation down the left of the panel (navtree.py has the groups and pages).

Folded, it is a 46px strip: the six groups' icons, each with its "new" count on the corner, and the page you're on
written down the side. Opened, it is 128px wide and lists the groups; a group drops down its pages and a page with
parts (Data, News, Researchers) drops down its parts. Tap an open line again, or ‹ (or Esc), to go up one level.
Unpinned it opens over the page (dimmed behind it) and folds itself after you pick a page; 📌 pins it beside the page.
Every count sits on its icon, open or folded, so the open rail needs no column for numbers.

The rail only draws and asks: what a page holds, its count, which page is open and how to open one come from the
panel (qt_panel.py), which keeps doing the navigation itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QByteArray, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QToolButton, QVBoxLayout, QWidget

from .. import navtree

FOLDED_W = 46
OPEN_W = 128
DARK_INK = QColor("#0d0d16")


@dataclass
class RailState:
    open: bool = False
    pinned: bool = False
    open_group: str | None = None       # the group whose pages are dropped down
    open_page: str | None = None        # the page whose parts are dropped down


def _svg(path: str, color: QColor) -> QSvgRenderer:
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color.name()}" '
           f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="{path}"/></svg>')
    return QSvgRenderer(QByteArray(svg.encode()))


def paint_tile(p: QPainter, rect: QRectF, color: QColor, path: str, emoji: str, filled: bool, sub: bool,
               count: int, dot: bool, ring_bg: QColor, ink: QColor | None = None) -> None:
    """A rounded tile with its icon, and its count (or a dot) on the top-right corner. On a light background the
    group colour is deepened so a yellow or light-blue ring still reads."""
    if ring_bg.lightness() > 160:
        color = QColor(color).darker(135)
    radius = rect.width() * 0.29
    border = QColor(color)
    if sub and not filled:
        border.setAlpha(150)
    p.setPen(QPen(border, 1.5 if not sub or filled else 1.0))
    p.setBrush(color if filled else Qt.NoBrush)
    p.drawRoundedRect(rect, radius, radius)
    if emoji:
        f = p.font()
        f.setPixelSize(int(rect.height() * 0.5))
        p.setFont(f)
        p.setPen(DARK_INK if filled else (ink or QColor("#f0f0f5")))     # a monochrome emoji takes the pen colour
        p.drawText(rect, Qt.AlignCenter, emoji)
    elif path:
        side = rect.width() * 0.56
        _svg(path, DARK_INK if filled else color).render(
            p, QRectF(rect.center().x() - side / 2, rect.center().y() - side / 2, side, side))
    if count > 0:
        text = "9+" if count > 9 else str(count)
        f = QFont(p.font())
        f.setPixelSize(9)
        f.setBold(True)
        p.setFont(f)
        w = max(14.0, p.fontMetrics().horizontalAdvance(text) + 7.0)
        bubble = QRectF(rect.right() - w + 6, rect.top() - 5, w, 14)
        p.setPen(QPen(ring_bg, 2))
        p.setBrush(color)
        p.drawRoundedRect(bubble, 7, 7)
        p.setPen(DARK_INK)
        p.drawText(bubble, Qt.AlignCenter, text)
    elif dot:
        p.setPen(QPen(ring_bg, 2))
        p.setBrush(QColor("#f0f0f5"))
        p.drawEllipse(QPointF(rect.right() + 1, rect.top() + 1), 4, 4)


class _Clickable(QWidget):
    def __init__(self, on_click: Callable[[], None], tip: str) -> None:
        super().__init__()
        self._on_click = on_click
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self.setAttribute(Qt.WA_Hover, True)
        self.setToolTip(tip)
        self.setAccessibleName(tip.split(" · ")[0])

    def enterEvent(self, e) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, e) -> None:  # noqa: N802
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self._on_click()

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self._on_click()
        else:
            super().keyPressEvent(e)


class RailRow(_Clickable):
    """One line of the open rail: tile (with its count), name (cut with … when long), and ▸/▾ when it opens."""

    def __init__(self, rail: "NavRail", nd: dict[str, Any], level: int) -> None:
        self.rail, self.nd, self.level = rail, nd, level
        super().__init__(lambda: rail.tapped(nd["id"]), rail.tip(nd))
        self.setFixedHeight(38 if level == 0 else 34)          # room above the tile for its badge

    def paintEvent(self, e) -> None:  # noqa: N802
        r, nd, theme = self.rail, self.nd, self.rail.theme()
        on_path, here = nd["id"] in r.path_ids, nd["id"] == r.leaf_id
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        ink = QColor(theme["text"])
        if here or self._hover or self.hasFocus():
            bg = QColor(ink)
            bg.setAlpha(26 if here else 15)
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)
        color = QColor(nd["color"])
        if here:
            p.fillRect(QRectF(1, 6, 2.5, self.height() - 12), color)
        indent = {0: 4, 1: 9, 2: 16}[self.level]
        side = 28 if self.level < 2 else 24
        tile = QRectF(indent, self.height() - side - 3, side, side)
        path, emoji = r.icon_of(nd)
        paint_tile(p, tile, color, path, emoji, filled=on_path and self.level == 0, sub=self.level > 0,
                   count=r.count_of(nd["id"]), dot=r.dot_of(nd["id"]), ring_bg=r.bg(), ink=QColor(theme["text"]))
        has_kids = bool(nd["children"])
        right = self.width() - (14 if has_kids else 4)
        f = QFont(self.font())
        f.setPixelSize(12 if self.level < 2 else 11)
        f.setBold(here or (on_path and self.level == 0))
        p.setFont(f)
        muted = QColor(theme["text"])
        if not (on_path or here or self._hover):
            muted.setAlpha(165)
        p.setPen(muted)
        text_rect = QRectF(tile.right() + 9, tile.top() - 4, max(0.0, right - tile.right() - 9), side + 8)
        p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft,
                   p.fontMetrics().elidedText(nd["label"], Qt.ElideRight, int(text_rect.width())))
        if has_kids:
            p.setPen(QColor(theme["text"]))
            f.setPixelSize(8)
            f.setBold(False)
            p.setFont(f)
            opened = nd["id"] in (r.state.open_group, r.state.open_page)
            p.drawText(QRectF(self.width() - 13, tile.top(), 10, side), Qt.AlignCenter, "▾" if opened else "▸")
        p.end()


class FoldedTile(_Clickable):
    def __init__(self, rail: "NavRail", nd: dict[str, Any]) -> None:
        self.rail, self.nd = rail, nd
        super().__init__(lambda: rail.open_at(nd["id"]), rail.tip(nd))
        self.setFixedSize(QSize(FOLDED_W - 6, 42))

    def paintEvent(self, e) -> None:  # noqa: N802
        r, nd = self.rail, self.nd
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        if self._hover or self.hasFocus():
            bg = QColor(r.theme()["text"])
            bg.setAlpha(15)
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(2, 2, -2, -2), 9, 9)
        side = 30
        tile = QRectF((self.width() - side) / 2, (self.height() - side) / 2 + 2, side, side)
        path, emoji = r.icon_of(nd)
        paint_tile(p, tile, QColor(nd["color"]), path, emoji, filled=nd["id"] in r.path_ids, sub=False,
                   count=r.count_of(nd["id"]), dot=r.dot_of(nd["id"]), ring_bg=r.bg(), ink=QColor(r.theme()["text"]))
        p.end()


class VerticalLabel(QWidget):
    """The page you're on, written down the folded strip."""

    def __init__(self, rail: "NavRail") -> None:
        super().__init__()
        self.rail = rail
        self.setMinimumHeight(40)

    def paintEvent(self, e) -> None:  # noqa: N802
        leaf = self.rail.leaf()
        if not leaf:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        f = QFont(self.font())
        f.setPixelSize(11)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(leaf["color"]))
        p.translate(self.width() / 2 + 5, 6)
        p.rotate(90)
        text = p.fontMetrics().elidedText(leaf["label"], Qt.ElideRight, max(0, self.height() - 12))
        p.drawText(QPointF(0, 0), text)
        p.end()


class NavRail(QWidget):
    """The rail in one of its two looks: folded (46px) or open (128px). The host decides where it sits."""

    def __init__(self, host: "RailHost", folded: bool) -> None:
        super().__init__(host)
        self.host, self.folded = host, folded
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(FOLDED_W if folded else OPEN_W)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(3, 4, 3, 4)
        self.lay.setSpacing(2)
        self.path_ids: set[str] = set()
        self.leaf_id = ""

    # what the host knows, asked by the rows
    state = property(lambda self: self.host.state)
    theme = property(lambda self: self.host.theme)
    tip = property(lambda self: self.host.tip)
    icon_of = property(lambda self: self.host.icon_of)
    count_of = property(lambda self: self.host.count_of)
    dot_of = property(lambda self: self.host.dot_of)
    leaf = property(lambda self: self.host.leaf)
    bg = property(lambda self: self.host.rail_bg)

    def tapped(self, nid: str) -> None:
        self.host.tapped(nid)

    def open_at(self, nid: str) -> None:
        self.host.open_at(nid)

    def _button(self, text: str, tip: str, on_click: Callable[[], None], checked: bool = False) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setAccessibleName(tip)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedSize(26, 26)
        b.setCheckable(checked is not None)
        b.setChecked(bool(checked))
        b.clicked.connect(on_click)
        return b

    def rebuild(self) -> None:
        while self.lay.count():
            item = self.lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()
        leaf = self.leaf()
        self.leaf_id = leaf["id"] if leaf else ""
        self.path_ids = {n["id"] for n in navtree.path(leaf)} if leaf else set()
        tree = self.host.tree
        if self.folded:
            top = self._button("»", "Open the menu (Ctrl+\\)", self.host.open_here, checked=None)
            self.lay.addWidget(top, 0, Qt.AlignHCenter)
            for g in tree["children"]:
                self.lay.addWidget(FoldedTile(self, g), 0, Qt.AlignHCenter)
            self.lay.addWidget(VerticalLabel(self), 1)
        else:
            bar = QWidget()
            bl = QHBoxLayout(bar)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(0)
            self.back_btn = self._button("‹", "Up a level (Esc)", self.host.back, checked=None)
            self.pin_btn = self._button("\U0001f4cc", "Unpin (opens over the page)" if self.state.pinned
                                        else "Pin beside the page", self.host.toggle_pin, checked=self.state.pinned)
            self.fold_btn = self._button("«", "Fold (Ctrl+\\)", self.host.fold, checked=None)
            bl.addWidget(self.back_btn)
            bl.addStretch(1)
            bl.addWidget(self.pin_btn)
            bl.addWidget(self.fold_btn)
            self.lay.addWidget(bar)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            inner = QWidget()
            il = QVBoxLayout(inner)
            il.setContentsMargins(0, 0, 0, 0)
            il.setSpacing(1)
            self.rows: dict[str, RailRow] = {}
            for g in tree["children"]:
                self._add(il, g, 0)
                if self.state.open_group == g["id"]:
                    for pg in g["children"]:
                        self._add(il, pg, 1)
                        if pg["children"] and self.state.open_page == pg["id"]:
                            for part in pg["children"]:
                                self._add(il, part, 2)
            il.addStretch(1)
            scroll.setWidget(inner)
            self.scroll = scroll
            scroll.viewport().setAutoFillBackground(False)
            inner.setAutoFillBackground(False)
            self.lay.addWidget(scroll, 1)
        self.restyle()
        if not self.folded:                              # the place you're on, or the one just opened, in view
            target = self.rows.get(self.leaf_id) or self.rows.get(self.state.open_page or "") \
                or self.rows.get(self.state.open_group or "")
            if target is not None:
                QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(target, 0, 40) if target.isVisible() else None)

    def _add(self, lay: QVBoxLayout, nd: dict[str, Any], level: int) -> None:
        row = RailRow(self, nd, level)
        self.rows[nd["id"]] = row
        lay.addWidget(row)

    def restyle(self) -> None:
        t = self.theme()
        bg = self.bg().name()
        line = QColor(t["text"])
        line.setAlpha(28)
        self.setStyleSheet(
            f"NavRail {{ background:{bg}; border-right:1px solid rgba({line.red()},{line.green()},{line.blue()},28); }}"
            f"QToolButton {{ background:transparent; color:{t['muted']}; border:none; border-radius:7px; font-size:13px; }}"
            f"QToolButton:hover {{ background:{t['btn_hover']}; color:{t['text']}; }}"
            f"QToolButton:checked {{ background:{t['section_btn']}; color:{t['text']}; }}"
            "QScrollArea, QScrollArea > QWidget > QWidget { background:transparent; }")

    def refresh(self) -> None:
        """Counts or the open page changed: repaint (rows stay as they are)."""
        leaf = self.leaf()
        self.leaf_id = leaf["id"] if leaf else ""
        self.path_ids = {n["id"] for n in navtree.path(leaf)} if leaf else set()
        for w in self.findChildren(QWidget):
            w.update()
        self.update()


class _Scrim(QWidget):
    def __init__(self, host: "RailHost") -> None:
        super().__init__(host)
        self.host = host
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, e) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(8, 8, 14, 115))
        p.end()

    def mousePressEvent(self, e) -> None:  # noqa: N802
        self.host.fold()


class RailHost(QWidget):
    """The rail beside the pages: folded strip or docked rail in the row, and, unpinned, the open rail over the page."""

    def __init__(self, content: QWidget, tree: dict[str, Any], *, open_node: Callable[[dict[str, Any]], None],
                 leaf: Callable[[], dict[str, Any] | None], count_of: Callable[[str], int],
                 dot_of: Callable[[str], bool], icon_of: Callable[[dict[str, Any]], tuple[str, str]],
                 theme: Callable[[], dict[str, Any]], pinned: bool, on_pin: Callable[[bool], None]) -> None:
        super().__init__()
        self.tree, self.content = tree, content
        self._open_node, self.leaf, self.count_of, self.dot_of, self.icon_of = open_node, leaf, count_of, dot_of, icon_of
        self.theme, self._on_pin = theme, on_pin
        self.state = RailState(open=pinned, pinned=pinned)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(6)
        self.strip = NavRail(self, folded=True)
        self.docked = NavRail(self, folded=False)
        self.overlay = NavRail(self, folded=False)
        self.scrim = _Scrim(self)
        self.row.addWidget(self.strip)
        self.row.addWidget(self.docked)
        self.row.addWidget(content, 1)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self._escape, context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence("Ctrl+\\"), self, self.toggle, context=Qt.WidgetWithChildrenShortcut)
        self._follow_leaf()
        self.apply()

    def rail_bg(self) -> QColor:
        t = self.theme()
        return QColor(t.get("solid_bg") or ("#1c1c2a" if t.get("dark", True) else "#ffffff"))

    def tip(self, nd: dict[str, Any]) -> str:
        n = self.count_of(nd["id"])
        return nd["label"] + (f" · {n} new" if n else "")

    def _follow_leaf(self) -> None:
        """Open at the page you're on: its group dropped down, and its page if it has parts."""
        leaf = self.leaf()
        path = navtree.path(leaf) if leaf else []
        self.state.open_group = path[1]["id"] if len(path) > 1 else None
        self.state.open_page = path[2]["id"] if len(path) > 3 else None

    # ---- what the person does
    def tapped(self, nid: str) -> None:
        nd = navtree.find(self.tree, nid)
        if nd is None:
            return
        level = len(navtree.path(nd)) - 1                 # 1 group, 2 page, 3 part
        if level == 1 and not nd["children"]:              # 🏠 Home: a page of its own, not a group
            self._open_node(nd)
            self.state.open_group, self.state.open_page = None, None
            if not self.state.pinned:
                self.state.open = False
        elif level == 1:
            same = self.state.open_group == nid
            self.state.open_group, self.state.open_page = (None, None) if same else (nid, None)
        elif nd["children"]:
            self.state.open_page = None if self.state.open_page == nid else nid
        else:
            self._open_node(nd)
            if not self.state.pinned:
                self.state.open = False
        self.apply()

    def open_at(self, nid: str) -> None:
        self.state.open, self.state.open_group, self.state.open_page = True, nid, None
        leaf = self.leaf()
        path = navtree.path(leaf) if leaf else []
        if len(path) > 3 and path[1]["id"] == nid:
            self.state.open_page = path[2]["id"]
        self.apply()

    def open_here(self) -> None:
        self._follow_leaf()
        self.state.open = True
        self.apply()

    def back(self) -> None:
        if self.state.open_page:
            self.state.open_page = None
        elif self.state.open_group:
            self.state.open_group = None
        else:
            self.state.open = False
        self.apply()

    def fold(self) -> None:
        self.state.open = False
        self.apply()

    def toggle(self) -> None:
        if self.state.open:
            self.fold()
        else:
            self.open_here()

    def toggle_pin(self) -> None:
        self.state.pinned = not self.state.pinned
        self.state.open = True
        self._on_pin(self.state.pinned)
        self.apply()

    def _escape(self) -> None:
        if self.state.open:
            self.back()

    # ---- drawing
    def apply(self) -> None:
        s = self.state
        docked = s.open and s.pinned
        over = s.open and not s.pinned
        self.strip.setVisible(not docked)
        self.docked.setVisible(docked)
        self.overlay.setVisible(over)
        self.scrim.setVisible(over)
        for rail in (self.strip, self.docked, self.overlay):
            if rail.isVisibleTo(self) or rail is self.strip:
                rail.rebuild()
        self._place()

    def refresh(self) -> None:
        for rail in (self.strip, self.docked, self.overlay):
            if rail.isVisibleTo(self):
                rail.refresh()

    def restyle(self) -> None:
        for rail in (self.strip, self.docked, self.overlay):
            rail.restyle()
            rail.refresh()

    def _place(self) -> None:
        if self.overlay.isVisibleTo(self):
            self.scrim.setGeometry(self.rect())
            self.overlay.setGeometry(0, 0, OPEN_W, self.height())
            self.scrim.raise_()
            self.overlay.raise_()

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._place()
