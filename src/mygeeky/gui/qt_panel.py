"""The Qt widget tree for the live glass panel. Kept separate from app.py
so app.py (and its business-logic functions) can be imported/tested without
requiring PySide6 to be importable."""

from __future__ import annotations

import hashlib
import html
import math
import os
import threading
import sys
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import (
    QByteArray,
    QRect,
    QUrl,
    QEasingCurve,
    QEvent,
    QObject,
    QParallelAnimationGroup,
    QPoint,
    QPointF,
    Qt,
    QPropertyAnimation,
    QRectF,
    QSize,
    QRunnable,
    QThreadPool,
    QTimer,
    QVariantAnimation,
    Signal,
)
import shiboken6
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import (
    QDesktopServices,
    QBrush,
    QColor,
    QGuiApplication,
    QIcon,
    QImage,
    QCursor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QGridLayout,
    QApplication,
    QCheckBox,
    QComboBox,
    QProgressBar,
    QDialog,
    QMessageBox,
    QLineEdit,
    QPlainTextEdit,
    QRadioButton,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import freshness, navtree
from . import app as logic
from .app import THEME_NAMES, THEMES
from .window_ui import SIDE_LABELS, LayerSwitch, ScreenPicker
from ..config import AVATAR_CACHE_DIR, MyGeekyConfig, profile_ready
from ..protocols import REVIEWED_SHOWN

ASSETS_DIR = Path(__file__).parent / "assets"
SYNC_EVERY_MS = 60 * 60 * 1000   # how often the panel syncs your data between computers (and at quit); was 15 min:
#                                  138 commits a day between two computers (docs/RESOURCES.md, plan 4)
DOCK_GUARD_MS = 3000   # how often the panel checks it is still docked where it belongs
DOCK_ANIM_MS = 280     # a bottom-corner panel rising to the middle as it opens (and sinking as it folds)
ICON_WINDOW = ASSETS_DIR / "icon_64.png"
ICON_HEADER = ASSETS_DIR / "icon_32.png"
ICON_FOLDED = ASSETS_DIR / "icon_128.png"   # drawn at ~58px: start large so it downscales crisply

SWATCH_GRADIENTS = {
    "frosted": "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #fff6ee, stop:1 #cfe0ff)",
    "midnight": "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #2a2a3d, stop:1 #0c0c14)",
    "aurora": "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #ff6fd8, stop:0.5 #7a5cff, stop:1 #35e0c1)",
}

AVATAR_PALETTE = ["#e08a4f", "#7aa6e0", "#5ac8a8", "#ff6fd8", "#7a5cff", "#35c2e0", "#e05c5c"]


def _build_spotlight_items(activity_events: list[dict[str, Any]],
                            suggestions: list[dict[str, Any]],
                            signals: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Normalizes activity events and follow-back suggestions into one
    interleaved rotation for the Live tab's ticker: recent real activity
    (pushes, merges, new repos, releases, stars -- already exactly "what
    they've been working on" and "repos they starred", straight from
    GitHub's events feed) alternated with top suggestions, so the ticker
    doesn't just show one or the other for several slides in a row."""
    activity_items = [{
        "kind": "activity",
        "username": e.get("actor", ""),
        "avatar_url": e.get("actor_avatar", ""),
        "profile_url": e.get("profile_url", ""),
        "headline": (e.get("verb", "") + (f" in {e['repo']}" if e.get("repo") else "")).strip(),
        "detail": "",
        "time_text": _time_ago(e.get("created_at", "")),
    } for e in activity_events]

    suggestion_items = [{
        "kind": "suggestion",
        "username": s.get("username", ""),
        "avatar_url": s.get("avatar_url", ""),
        "profile_url": s.get("profile_url", ""),
        "headline": f"might follow back · score {s['score']:.2f}" if isinstance(s.get("score"), (int, float))
                    else "matches your profile",
        "detail": (s.get("bio") or "")[:70],
        "time_text": "",
    } for s in suggestions]

    # signals people sent you lead the rotation -- they're about you
    interleaved: list[dict[str, Any]] = [{
        "kind": "signal",
        "username": s.get("from", ""),
        "avatar_url": s.get("avatar_url", ""),
        "profile_url": s.get("profile_url", ""),
        "headline": s.get("text", "") + ("  🤝" if s.get("mutual") else ""),
        "detail": "",
        "time_text": _time_ago(s.get("at", "")),
    } for s in (signals or [])[:5]]
    i = j = 0
    while i < len(activity_items) or j < len(suggestion_items):
        if i < len(activity_items):
            interleaved.append(activity_items[i])
            i += 1
        if j < len(suggestion_items):
            interleaved.append(suggestion_items[j])
            j += 1
    return interleaved


def _alive(w: QWidget) -> bool:
    """False once Qt has deleted the widget behind this Python object."""
    try:
        w.objectName()
        return True
    except RuntimeError:
        return False


def _reconnect(signal: Any, slot: Any) -> None:
    """Give a button one job, replacing whatever it did before.

    A button that changes what it means (Update becoming "Copy the command") must not keep its old
    connection as well, or one click does both. Disconnecting a signal that has nothing connected
    raises, so that case is simply allowed to happen."""
    try:
        signal.disconnect()
    except (RuntimeError, TypeError):
        pass
    signal.connect(slot)


def _short(text: str, n: int) -> str:
    """A label that fits: cut on a word boundary and end with an ellipsis. Buttons can't shrink below
    their own text, so a long title in a button makes the whole panel wider than it is."""
    text = " ".join((text or "").split())
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0] if " " in text[:n] else text[:n]
    return cut.rstrip(" ,.;:") + "…"


def _plain(label: QLabel) -> QLabel:
    """Show remote text as text. A QLabel left at Qt's default (AutoText) renders anything that looks like HTML
    as HTML, and an <img> in a GitHub bio or a repo description then makes Qt open whatever path it names:
    /dev/zero exhausts memory and kills the panel, and on Windows a file:// share sends the user's login hash
    to whoever runs it. Every label that shows a stranger's words goes through here."""
    label.setTextFormat(Qt.PlainText)
    return label


def _tip(text: Any, limit: int = 1200) -> str:
    """A tooltip that shows remote text as text. Qt guesses HTML for tooltips too, so the text is escaped and
    wrapped in <qt>, which also lets a long abstract wrap instead of running off the screen."""
    t = str(text or "")[:limit]
    return "<qt>" + html.escape(t).replace("\n", "<br>") + "</qt>" if t.strip() else ""


def _time_ago(iso: str) -> str:
    if not iso:
        return ""
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return ""
    now = datetime.now(then.tzinfo) if then.tzinfo else datetime.now()
    diff = max(0.0, (now - then).total_seconds())
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{int(diff // 60)}m ago"
    if diff < 86400:
        return f"{int(diff // 3600)}h ago"
    return f"{int(diff // 86400)}d ago"


def _avatar_color(name: str) -> str:
    if not name:
        return AVATAR_PALETTE[0]
    return AVATAR_PALETTE[sum(ord(c) for c in name) % len(AVATAR_PALETTE)]


def _avatar_label(username: str, size: int = 32) -> QLabel:
    """The immediate, always-available fallback: a colored circle with initials.
    `_avatar_widget` below upgrades this to a real photo once one loads."""
    parts = [p for p in username.replace("-", " ").replace("_", " ").split() if p]
    initials = "".join(p[0] for p in parts[:2]).upper() or "?"
    label = QLabel(initials)
    label.setFixedSize(size, size)
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet(
        f"background:{_avatar_color(username)}; color:white; border-radius:{size // 2}px; "
        f"font-weight:700; font-size:{max(9, size // 3)}px;"
    )
    return label


def _circular_image(source: QImage, size: int) -> QImage:
    """Crop + mask a square photo into a smooth circle with transparent corners.
    QImage, not QPixmap: this also runs in background threads, where Qt only
    allows QImage (a QPixmap there can crash on some graphics drivers)."""
    scaled = source.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = max(0, (scaled.width() - size) // 2)
    y = max(0, (scaled.height() - size) // 2)
    cropped = scaled.copy(x, y, size, size)

    result = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    painter.drawImage(0, 0, cropped)
    painter.end()
    return result


def _circular_pixmap(source: QPixmap, size: int) -> QPixmap:
    return QPixmap.fromImage(_circular_image(source.toImage(), size))


def _avatar_widget(username: str, avatar_url: str, size: int, loader: "AvatarLoader | None") -> QLabel:
    """Starts as the colored-initials fallback, upgraded in place to the
    person's real GitHub photo once it loads (async, cached)."""
    label = _avatar_label(username, size)
    if loader and avatar_url:
        def _apply(pixmap: QPixmap) -> None:
            try:
                label.setPixmap(pixmap)
                label.setText("")
                label.setStyleSheet("background: transparent;")
            except RuntimeError:
                pass  # the widget was already destroyed (e.g. ticker rotated past it)

        loader.request(avatar_url, size, _apply)
    return label


def dialog_css(theme: dict[str, Any]) -> str:
    """Dialogs are windows of their own: the panel's see-through colours would sit on black there (and
    the text kept the system's black), so they get solid colours that match the theme."""
    dark = theme.get("dark", True)
    bg, fg, field, btn, hover, edge = (("#1f1b2e", "#f0f0f5", "#2a2640", "#3a3456", "#4a4370", "#4a4466") if dark
                                       else ("#f6f3ee", "#241f1a", "#ffffff", "#e4ded4", "#d6cec2", "#cfc6b8"))
    return (f"QDialog, QMessageBox, QInputDialog {{ background:{bg}; }}"
            f"QLabel, QRadioButton, QCheckBox {{ color:{fg}; background:transparent; font-size:12px; }}"
            f"QLineEdit {{ background:{field}; color:{fg}; border:1px solid {edge}; border-radius:6px; padding:5px; }}"
            f"QPushButton {{ background:{btn}; color:{fg}; border:none; border-radius:8px; padding:6px 14px; "
            f"font-size:12px; min-width:64px; }} QPushButton:hover {{ background:{hover}; }}")


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setProperty("fresh_key", None)      # on its way out: no longer counted or tracked
            widget.setProperty("fresh_state", None)
            widget.hide()  # deleteLater only runs on a later event-loop turn
            widget.deleteLater()
        elif item.layout() is not None:
            # a row inside the list: its widgets belong to the list's own widget, so without this they'd
            # stay on screen behind the next drawing (old boxes and buttons piling up on each redraw)
            _clear_layout(item.layout())
            item.layout().deleteLater()


# --------------------------------------------------------------------------- freshness (see freshness.py)
SEEN_AFTER_MS = 1500        # a card this long mostly on screen counts as seen
SEEN_FRACTION = 0.6         # "mostly": this much of it (or a screenful of a tall one)
SEEN_TICK_MS = 500


def _fresh_dot(card: QWidget, color: str) -> QLabel:
    """A small 'new' dot in a card's top-right corner (it goes once you've seen the card).
    A plain label owned by the card: no Python-made QObject and no event filter riding on
    the card. That pattern crashed Linux ("free(): invalid pointer" in Shiboken while Qt
    deleted a refreshed card's children). The seen-check keeps it in its corner."""
    dot = QLabel(card)
    dot.setObjectName("freshDot")
    dot.setFixedSize(8, 8)
    dot.setStyleSheet(f"background:{color}; border-radius:4px;")
    dot.setToolTip("New since you last looked")
    dot.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    _place_dot(card, dot)
    return dot


def _place_dot(card: QWidget, dot: QLabel) -> None:
    dot.move(max(0, card.width() - 14), 6)
    dot.raise_()


def _mark_fresh(card: QWidget, item: dict[str, Any], theme: dict[str, Any]) -> QWidget:
    """Label a card for the freshness tracker: new ones get a dot and are watched; ones
    you've already seen (shown at the end, or dimmed in a timeline) are dimmed."""
    state, key = item.get("_fresh"), item.get("_key")
    if state in ("new", "again") and key:
        card.setProperty("fresh_key", key)
        card.setProperty("fresh_state", state)
        if state == "new":
            _fresh_dot(card, theme["accent"])
    elif state == "seen":
        effect = QGraphicsOpacityEffect(card)
        effect.setOpacity(0.8)               # quieter than new, still easy to read
        card.setGraphicsEffect(effect)
    return card


def _caught_up(theme: dict[str, Any], text: str) -> QLabel:
    note = QLabel("✔ " + text)
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{theme['good']}; font-size:10.5px; background:transparent; margin:2px 0 4px 0;")
    return note


SEEN_EARLIER_MAX = 4        # a read-once list you've finished still shows this many, dimmed

# What each GitHub-only part gives you, said on its "add GitHub" card (myGeeKy without a GitHub username)
GITHUB_UNLOCKS = {
    "people": "Researchers in your field share their code on GitHub. myGeeKy finds the ones you'd enjoy "
              "following, and who'd likely follow you back. Until then, 📈 Market → Research shows who is publishing in your field.",
    # The follow-back list is scored against your own account: who follows you, who you follow, how like you
    # someone is. There is nothing to score without an account, so this half is the only part that waits.
    "followback": "Who would likely follow you back — scored against your own account, so this half needs "
                  "GitHub. The people below it are found by searching your field, and need nothing.",
    "repos": "Repos in your field where your skills would be welcome, with open starter issues.",
    "activity": "What people in your field are building, as it happens.",
    "signals": "Thank the people whose code you use, and invite collaborators, without words.",
}


TOAST_MS = 4000             # the floating message stays this long (the phone's toast.tsx uses the same)
LOCAL_ONLY_TEXT = ("💻 Learning on this computer only. Save it in Google Drive or a private GitHub repo (⚙ Settings → "
                   "Accounts) to keep it and share it with your phone: what this computer learned goes there too.")


def reviewed_heading(some: bool) -> str:
    """The reviewed protocols' heading: only the best fits, or all (the phone's reviewedHeading says the same)."""
    return "✓ REVIEWED FOR YOUR FIELD" if some else "✓ REVIEWED PROTOCOLS"


def see_all_text(n: int, showing_all: bool) -> str:
    return "Show fewer" if showing_all else f"See all {n} reviewed protocols ›"


def protocol_built_text(title: str, stages: int, reviewed: bool) -> str:
    """What the Protocols tab says once a protocol is built or started (the phone says the same: protocols-view.tsx)."""
    what = f"Protocol started: {title} (reviewed)" if reviewed else f"Your protocol is built: {title}"
    return f"✓ {what} · {stages} stage{'s' if stages != 1 else ''}. It's open below."


def _activity_key(group: dict[str, Any]) -> str:
    """A person's activity counts as new again as soon as they do something new."""
    return f"activity:{str(group.get('actor', '')).lower()}:{group.get('latest', '')}"


def _with_seen_earlier(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """New and returning ones, then only a few already-seen ones."""
    fresh = [i for i in items if i.get("_fresh") != "seen"]
    return fresh + [i for i in items if i.get("_fresh") == "seen"][:SEEN_EARLIER_MAX]


class _Job(QRunnable):
    def __init__(self, worker: "_Worker") -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._worker = worker

    def run(self) -> None:
        self._worker._run()


class _Worker(QObject):
    """Runs one callable off the UI thread so a slow network call (a real
    `mygeeky run`, or an activity-feed fetch) never freezes the panel.

    The callables share a small pool of threads instead of each starting a new one (a page of avatars started
    dozens at once; docs/RESOURCES.md, plan 8): WORK_THREADS for work, AVATAR_THREADS for photos, so a page full
    of photos never queues real work behind it. `done` is emitted from the pool thread and delivered on the UI
    thread (this object lives there); `_alive` holds every worker until its callable has returned."""

    done = Signal(object)
    _over = Signal()                 # queued after `done`, so the worker is released only once its result arrived
    _alive: set = set()
    WORK_THREADS = 8
    AVATAR_THREADS = 8
    _pools: dict[str, QThreadPool] = {}

    def __init__(self, fn: Callable[[], Any], pool: str = "work") -> None:
        super().__init__()
        self._fn = fn
        self._pool = pool
        self._finished = threading.Event()
        self._started = False
        self._over.connect(self._release)

    def _release(self) -> None:
        _Worker._alive.discard(self)

    @classmethod
    def _pool_for(cls, name: str) -> QThreadPool:
        if name not in cls._pools:
            pool = QThreadPool()
            pool.setMaxThreadCount(cls.AVATAR_THREADS if name == "avatar" else cls.WORK_THREADS)
            pool.setExpiryTimeout(30_000)          # idle threads end after 30 s
            cls._pools[name] = pool
        return cls._pools[name]

    def start(self, *args: Any) -> None:
        _Worker._alive.add(self)
        self._started = True
        self._pool_for(self._pool).start(_Job(self))

    def _run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # keep the worker thread from ever crashing the app
            from ..errors import describe
            result = {"error": describe(exc)}    # what happened in plain words (network, limits, files...)
        try:
            self.done.emit(result)
            self._over.emit()
        except RuntimeError:
            _Worker._alive.discard(self)           # its Qt object is gone (the app is closing)
        finally:
            self._finished.set()

    def isRunning(self) -> bool:  # noqa: N802 -- the QThread name callers already use
        return self._started and not self._finished.is_set()

    def wait(self, ms: int | None = None) -> bool:
        return self._finished.wait(None if ms is None else ms / 1000) if self._started else True

    @classmethod
    def drain(cls, timeout_ms: int) -> int:
        """On quit: give running work up to `timeout_ms` to finish; how many are still running."""
        deadline = time.monotonic() + timeout_ms / 1000
        for w in list(cls._alive):
            w.wait(max(0, int((deadline - time.monotonic()) * 1000)))
        return sum(1 for w in list(cls._alive) if w.isRunning())


class AvatarLoader:
    """Fetches GitHub avatar photos off the UI thread. Cached in memory for
    this session and on disk (`AVATAR_CACHE_DIR`) across restarts, so the
    same photo is only ever downloaded once."""

    MAX_FILES = 600          # on disk: the newest photos kept, the rest asked again if ever needed (plan 7)
    MAX_MEMORY = 400         # in memory this session: the oldest dropped first

    def __init__(self) -> None:
        self._memory: dict[str, QPixmap] = {}
        self._workers: list[_Worker] = []
        threading.Thread(target=self.prune, daemon=True).start()

    @classmethod
    def prune(cls, folder: Path | None = None) -> int:
        """Keep the newest MAX_FILES photos on disk; returns how many were removed."""
        folder = folder or AVATAR_CACHE_DIR
        try:
            files = sorted(folder.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            return 0
        gone = 0
        for p in files[cls.MAX_FILES:]:
            try:
                p.unlink()
                gone += 1
            except OSError:
                pass
        return gone

    def request(self, url: str, size: int, on_loaded: Callable[[QPixmap], None]) -> None:
        if not url:
            return
        cache_key = f"{url}@{size}"
        cached = self._memory.get(cache_key)
        if cached is not None:
            on_loaded(cached)
            return

        disk_path = AVATAR_CACHE_DIR / (hashlib.sha1(cache_key.encode()).hexdigest() + ".png")

        def fetch() -> QImage | None:          # runs in a worker thread: QImage only, never QPixmap
            if disk_path.exists():
                cached_img = QImage(str(disk_path))
                if not cached_img.isNull():
                    return cached_img
            try:
                import requests
                resp = requests.get(url, timeout=6)
                resp.raise_for_status()
            except Exception:
                return None
            raw = QImage()
            if not raw.loadFromData(resp.content):
                return None
            circular = _circular_image(raw, size)
            try:
                AVATAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                circular.save(str(disk_path), "PNG")
            except OSError:
                pass
            return circular

        worker = _Worker(fetch, pool="avatar")

        def _finish(result: Any) -> None:
            if isinstance(result, QImage) and not result.isNull():
                pixmap = QPixmap.fromImage(result)        # here, on the UI thread
                self._memory[cache_key] = pixmap
                while len(self._memory) > self.MAX_MEMORY:
                    self._memory.pop(next(iter(self._memory)))
                on_loaded(pixmap)
            if worker in self._workers:
                self._workers.remove(worker)

        worker.done.connect(_finish)
        self._workers.append(worker)
        worker.start()


def _auc_color(auc: float | None) -> QColor:
    """Grade colour shared by the gauge and the verdict chip."""
    if auc is None:
        return QColor("#9ca3af")
    if auc >= 0.8:
        return QColor("#34d399")
    if auc >= 0.7:
        return QColor("#60a5fa")
    if auc >= 0.6:
        return QColor("#fbbf24")
    return QColor("#f87171")


class _Pulse:
    """A slow 0..1..0 breathing phase that only ticks while the widget is
    visible, so the idle panel costs no CPU."""

    def __init__(self, widget: QWidget, period_ms: int = 2400) -> None:
        self._widget = widget
        self._period = period_ms
        self._t = 0
        self._timer = QTimer(widget)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    def _tick(self) -> None:
        self._t = (self._t + 40) % self._period
        self._widget.update()

    @property
    def phase(self) -> float:
        return 0.5 - 0.5 * math.cos(2 * math.pi * self._t / self._period)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()


def _grow_animation(owner: QWidget, setter: Callable[[float], None], ms: int = 900) -> QVariantAnimation:
    anim = QVariantAnimation(owner)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setDuration(ms)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.valueChanged.connect(lambda v: setter(float(v)))
    return anim


def _short_date(entry: dict[str, Any]) -> str:
    try:
        return datetime.fromisoformat(entry.get("timestamp", "")).strftime("%b %d")
    except (TypeError, ValueError):
        return ""


class AucGauge(QWidget):
    """Ring gauge for the cross-validated AUC: sweeps in when played and
    softly glows, coloured by grade."""

    def __init__(self, size: int = 112) -> None:
        super().__init__()
        self.setFixedSize(size, size)
        self._auc: float | None = None
        self._progress = 1.0
        self._text_color = QColor("#f0f0f5")
        self._pulse = _Pulse(self)
        self._anim = _grow_animation(self, self._set_progress, 1100)

    def _set_progress(self, v: float) -> None:
        self._progress = v
        self.update()

    def set_theme_colors(self, text_color: str) -> None:
        self._text_color = QColor(text_color)
        self.update()

    def set_auc(self, auc: float | None) -> None:
        self._auc = auc
        self.update()

    def play(self) -> None:
        self._anim.stop()
        self._anim.start()

    def showEvent(self, event) -> None:  # noqa: N802 -- Qt's own naming convention
        self._pulse.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        self._pulse.stop()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height())
        ring = QRectF(12, 12, side - 24, side - 24)
        color = _auc_color(self._auc)

        track = QColor(self._text_color)
        track.setAlpha(28)
        painter.setPen(QPen(track, 9, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(ring, 0, 360 * 16)

        if self._auc is not None:
            span = -int(360 * 16 * max(0.0, min(1.0, self._auc)) * self._progress)
            glow = QColor(color)
            glow.setAlpha(int(35 + 55 * self._pulse.phase))
            painter.setPen(QPen(glow, 17, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(ring, 90 * 16, span)
            painter.setPen(QPen(color, 9, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(ring, 90 * 16, span)

        value = "–" if self._auc is None else f"{self._auc * self._progress:.3f}"
        font = painter.font()
        font.setPixelSize(22)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self._text_color)
        painter.drawText(QRectF(0, side / 2 - 18, side, 26), Qt.AlignCenter, value)
        font.setPixelSize(10)
        font.setBold(False)
        painter.setFont(font)
        muted = QColor(self._text_color)
        muted.setAlpha(150)
        painter.setPen(muted)
        painter.drawText(QRectF(0, side / 2 + 8, side, 14), Qt.AlignCenter, "AUC")
        painter.end()


class StatTile(QFrame):
    """A small number + caption tile whose number counts up when played."""

    def __init__(self, caption: str) -> None:
        super().__init__()
        self.setObjectName("statTile")
        box = QVBoxLayout(self)
        box.setContentsMargins(8, 6, 8, 6)
        box.setSpacing(0)
        self.value_label = QLabel("–")
        self.caption_label = QLabel(caption)
        box.addWidget(self.value_label)
        box.addWidget(self.caption_label)
        self._target = 0.0
        self._fmt: Callable[[float], str] = lambda v: f"{v:.0f}"
        self._anim = _grow_animation(self, self._render, 1000)

    def set_value(self, value: float, fmt: Callable[[float], str] | None = None) -> None:
        self._target = value
        if fmt:
            self._fmt = fmt
        self._render(1.0)

    def _render(self, progress: float) -> None:
        self.value_label.setText(self._fmt(self._target * progress))

    def play(self) -> None:
        self._anim.stop()
        self._anim.start()

    def apply_theme(self, theme: dict[str, Any]) -> None:
        self.setStyleSheet(f"QFrame#statTile {{ background:{theme['card_bg']}; border-radius:10px; }}")
        self.value_label.setStyleSheet(
            f"color:{theme['text']}; font-size:16px; font-weight:600; background:transparent;")
        self.caption_label.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")


class WeightBars(QWidget):
    """Diverging bars of what the model rewards (right) and penalizes
    (left), growing out from a centre line when played."""

    ROW = 24

    def __init__(self) -> None:
        super().__init__()
        self._weights: list[dict[str, Any]] = []
        self._progress = 1.0
        self._text_color = QColor("#f0f0f5")
        self._accent = QColor("#7fd8ff")
        self._anim = _grow_animation(self, self._set_progress, 1000)
        self.setFixedHeight(self.ROW + 4)

    def _set_progress(self, v: float) -> None:
        self._progress = v
        self.update()

    def set_theme_colors(self, text_color: str, accent_color: str) -> None:
        self._text_color = QColor(text_color)
        self._accent = QColor(accent_color)
        self.update()

    def set_weights(self, weights: list[dict[str, Any]]) -> None:
        self._weights = weights
        self.setFixedHeight(max(1, len(weights)) * self.ROW + 4)
        self.update()

    def play(self) -> None:
        self._anim.stop()
        self._anim.start()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        muted = QColor(self._text_color)
        muted.setAlpha(150)
        font = painter.font()
        font.setPixelSize(11)
        painter.setFont(font)
        if not self._weights:
            painter.setPen(muted)
            painter.drawText(QRectF(self.rect()), Qt.AlignLeft | Qt.AlignVCenter, "No trained model yet.")
            painter.end()
            return

        w = self.width()
        label_w = w * 0.42
        mid = label_w + (w - label_w) / 2
        half = (w - label_w) / 2 - 34
        biggest = max(abs(x["weight"]) for x in self._weights) or 1.0
        negative = QColor("#f87171")

        for i, item in enumerate(self._weights):
            y = i * self.ROW + 2
            positive = item["weight"] >= 0
            painter.setPen(self._text_color)
            painter.drawText(QRectF(0, y, label_w - 6, self.ROW), Qt.AlignLeft | Qt.AlignVCenter, item["label"])
            length = half * abs(item["weight"]) / biggest * self._progress
            color = QColor(self._accent if positive else negative)
            faded = QColor(color)
            faded.setAlpha(110)
            grad = QLinearGradient(mid, 0, mid + length if positive else mid - length, 0)
            grad.setColorAt(0, faded)
            grad.setColorAt(1, color)
            bar = QRectF(mid, y + 6, length, self.ROW - 12) if positive \
                else QRectF(mid - length, y + 6, length, self.ROW - 12)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(bar, 4, 4)
            painter.setPen(muted)
            text = f"{item['weight']:+.2f}"
            if positive:
                painter.drawText(QRectF(bar.right() + 4, y, 40, self.ROW), Qt.AlignLeft | Qt.AlignVCenter, text)
            else:
                painter.drawText(QRectF(bar.left() - 44, y, 40, self.ROW), Qt.AlignRight | Qt.AlignVCenter, text)

        axis = QColor(self._text_color)
        axis.setAlpha(60)
        painter.setPen(QPen(axis, 1))
        painter.drawLine(QPointF(mid, 0), QPointF(mid, self.height()))
        painter.end()


class TrendChart(QWidget):
    """Hand-drawn AUC-over-time chart -- no charting dependency needed. A
    smooth line over faint training-set-size bars, a zoomed y-axis with the
    coin-flip line, a pulsing newest point, a draw-in animation and a hover
    tooltip."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(150)
        self.setMouseTracking(True)
        self._history: list[dict[str, Any]] = []
        self._points: list[float] = []
        self._text_color = QColor("#f0f0f5")
        self._accent_color = QColor("#7fd8ff")
        self._progress = 1.0
        self._hover: int | None = None
        self._pulse = _Pulse(self, 1600)
        self._anim = _grow_animation(self, self._set_progress, 1200)

    def _set_progress(self, v: float) -> None:
        self._progress = v
        self.update()

    def set_theme_colors(self, text_color: str, accent_color: str) -> None:
        self._text_color = QColor(text_color)
        self._accent_color = QColor(accent_color)
        self.update()

    def set_history(self, history: list[dict[str, Any]]) -> None:
        self._history = [h for h in history if h.get("auc") is not None]
        self._points = [h["auc"] for h in self._history]
        self._hover = None
        self.update()

    def play(self) -> None:
        self._anim.stop()
        self._anim.start()

    def showEvent(self, event) -> None:  # noqa: N802
        self._pulse.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        self._pulse.stop()
        super().hideEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = None
        self.update()

    def _bounds(self) -> tuple[float, float, float, float, float, float]:
        left, right, top, bottom = 34.0, 10.0, 12.0, 18.0
        lo = min(self._points + [0.5]) - 0.03
        hi = max(self._points) + 0.03
        if hi - lo < 0.1:
            hi = lo + 0.1
        return left, right, top, bottom, max(0.0, lo), min(1.0, hi)

    def _xy(self) -> tuple[list[float], list[float]]:
        left, right, top, bottom, lo, hi = self._bounds()
        w, h = self.width(), self.height()
        n = len(self._points)
        if n == 1:
            xs = [left + (w - left - right) / 2]
        else:
            xs = [left + (i / (n - 1)) * (w - left - right) for i in range(n)]
        ys = [top + (1 - (p - lo) / (hi - lo)) * (h - top - bottom) for p in self._points]
        return xs, ys

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self._points:
            return
        xs, _ = self._xy()
        x = event.position().x()
        self._hover = min(range(len(xs)), key=lambda i: abs(xs[i] - x))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        muted = QColor(self._text_color)
        muted.setAlpha(140)
        font = painter.font()
        font.setPixelSize(10)
        painter.setFont(font)

        if not self._points:
            painter.setPen(muted)
            painter.drawText(QRectF(self.rect()), Qt.AlignCenter, "No retrains yet to chart")
            painter.end()
            return

        left, right, top, bottom, lo, hi = self._bounds()
        plot_h = h - top - bottom
        grid = QColor(self._text_color)
        grid.setAlpha(26)
        for k in range(3):
            v = lo + (hi - lo) * k / 2
            y = top + (1 - k / 2) * plot_h
            painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(left, y), QPointF(w - right, y))
            painter.setPen(muted)
            painter.drawText(QRectF(0, y - 7, left - 6, 14), Qt.AlignRight | Qt.AlignVCenter, f"{v:.2f}")

        if lo <= 0.5 <= hi:  # the coin-flip line the model has to beat
            y = top + (1 - (0.5 - lo) / (hi - lo)) * plot_h
            painter.setPen(QPen(muted, 1, Qt.DashLine))
            painter.drawLine(QPointF(left, y), QPointF(w - right, y))
            painter.drawText(QRectF(left + 4, y - 14, 80, 12), Qt.AlignLeft, "chance")

        xs, ys = self._xy()
        n = len(xs)

        # faint bars: how many labelled examples each retrain learned from
        sizes = [entry.get("n_train") or 0 for entry in self._history]
        biggest = max(sizes) or 1
        bar_w = max(4.0, min(18.0, (w - left - right) / n * 0.35))
        bar_color = QColor(self._accent_color)
        bar_color.setAlpha(24)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bar_color)
        for x, size in zip(xs, sizes):
            bh = plot_h * 0.45 * size / biggest * self._progress
            painter.drawRoundedRect(QRectF(x - bar_w / 2, top + plot_h - bh, bar_w, bh), 2, 2)

        painter.save()
        painter.setClipRect(QRectF(0, 0, left + (w - left - right) * self._progress + 4, h))
        if n > 1:
            line = QPainterPath(QPointF(xs[0], ys[0]))
            for i in range(1, n):
                cx = (xs[i - 1] + xs[i]) / 2
                line.cubicTo(QPointF(cx, ys[i - 1]), QPointF(cx, ys[i]), QPointF(xs[i], ys[i]))
            area = QPainterPath(line)
            area.lineTo(xs[-1], top + plot_h)
            area.lineTo(xs[0], top + plot_h)
            area.closeSubpath()
            fill = QLinearGradient(0, top, 0, top + plot_h)
            strong = QColor(self._accent_color)
            strong.setAlpha(110)
            clear = QColor(self._accent_color)
            clear.setAlpha(0)
            fill.setColorAt(0, strong)
            fill.setColorAt(1, clear)
            painter.fillPath(area, QBrush(fill))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(self._accent_color, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(line)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._accent_color)
        for x, y in zip(xs, ys):
            painter.drawEllipse(QPointF(x, y), 3, 3)
        painter.restore()

        if self._progress >= 0.999:  # the newest retrain breathes
            phase = self._pulse.phase
            halo = QColor(self._accent_color)
            halo.setAlpha(int(150 * (1 - phase)))
            painter.setPen(Qt.NoPen)
            painter.setBrush(halo)
            painter.drawEllipse(QPointF(xs[-1], ys[-1]), 4 + 7 * phase, 4 + 7 * phase)
            painter.setBrush(self._accent_color)
            painter.drawEllipse(QPointF(xs[-1], ys[-1]), 4.5, 4.5)

        painter.setPen(muted)
        painter.drawText(QRectF(left, h - 14, 90, 14), Qt.AlignLeft, _short_date(self._history[0]))
        if n > 1:
            painter.drawText(QRectF(w - right - 90, h - 14, 90, 14), Qt.AlignRight, _short_date(self._history[-1]))

        if self._hover is not None and self._hover < n:
            i = self._hover
            guide = QColor(self._text_color)
            guide.setAlpha(70)
            painter.setPen(QPen(guide, 1, Qt.DotLine))
            painter.drawLine(QPointF(xs[i], top), QPointF(xs[i], top + plot_h))
            entry = self._history[i]
            text = f"AUC {entry['auc']:.3f} · {entry.get('n_train', '?')} examples · {_short_date(entry)}"
            tw = painter.fontMetrics().horizontalAdvance(text) + 14
            tx = min(max(xs[i] - tw / 2, 0), w - tw)
            ty = max(ys[i] - 30, 0)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(20, 20, 30, 225))
            painter.drawRoundedRect(QRectF(tx, ty, tw, 20), 6, 6)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(tx, ty, tw, 20), Qt.AlignCenter, text)
        painter.end()


def _explore_chip(theme: dict[str, Any]) -> QLabel:
    """Marks an item from outside your usual interests (see interests.mix)."""
    chip = QLabel("🔭 new territory")
    chip.setToolTip("Outside your usual interests, on purpose: a little room to discover something new. "
                    "Clicking it teaches myGeeKy that this interests you too.")
    chip.setStyleSheet(f"color:{theme['text']}; background:rgba(122,92,255,70); border-radius:7px; "
                       f"padding:1px 6px; font-size:9.5px;")
    chip.setFixedHeight(16)
    return chip


NEWS_BADGES = {"arxiv": ("arXiv", "#b31b1b"), "biorxiv": ("bioRxiv", "#bd2736"), "hackernews": ("HN", "#ff6600")}


class HeadlineRow(QFrame):
    """One headline: a small source tag and the title. Click to read it."""

    def __init__(self, item: dict[str, Any], theme: dict[str, Any], on_open: Callable[[str], bool]) -> None:
        super().__init__()
        self.setObjectName("headlineRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 5, 8, 5)
        lay.setSpacing(7)
        color = theme.get(f"cat_{item.get('category', '')}", theme["muted"])
        tag = QLabel(("\U0001f30d " if item.get("explore") else "") + item.get("source", ""))
        tag.setTextFormat(Qt.PlainText)
        tag.setFixedWidth(92)
        tag.setStyleSheet(f"color:{color}; font-size:9.5px; font-weight:700; background:transparent;")
        tag.setToolTip("\U0001f30d the big picture: outside your usual interests" if item.get("explore")
                       else "for you: " + ", ".join(item.get("match") or []))
        lay.addWidget(tag, 0, Qt.AlignTop)
        from ..badges import BADGES, item_kind
        kind = item_kind(item)
        lay.addWidget(letter_badge(kind, f"{BADGES[kind][0].capitalize()}"), 0, Qt.AlignTop)
        title = QLabel(item.get("title", ""))
        title.setTextFormat(Qt.PlainText)
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title.setStyleSheet(f"color:{theme['text']}; font-size:11px; background:transparent;")
        lay.addWidget(title, 1)
        when = QLabel(_time_ago(item.get("published", "")))
        when.setStyleSheet(f"color:{theme['muted']}; font-size:9.5px; background:transparent;")
        lay.addWidget(when, 0, Qt.AlignTop)
        self.setStyleSheet(f"QFrame#headlineRow {{ background:transparent; border-radius:8px; }}"
                           f"QFrame#headlineRow:hover {{ background:{theme['card_bg']}; }}")
        self.setCursor(Qt.PointingHandCursor)
        link = item.get("link", "")
        self.mousePressEvent = lambda ev: on_open(link)  # noqa: ARG005


class NewsCard(QFrame):
    """One news item: source badge, title, why it's here (matching terms, or
    🔭 new territory) and when. Text from the source is shown as plain text.
    Clicking opens it (and counts as an interest signal)."""

    def __init__(self, item: dict[str, Any], theme: dict[str, Any], on_open: Callable[[str], bool]) -> None:
        super().__init__()
        self.setObjectName("newsCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(3)
        top = QHBoxLayout()
        top.setSpacing(6)
        name, color = NEWS_BADGES.get(item.get("source", ""), (item.get("source", ""), theme["accent"]))
        badge = _plain(QLabel(name))
        badge.setStyleSheet(f"color:white; background:{color}; border-radius:6px; padding:0 6px; "
                            f"font-size:9.5px; font-weight:700;")
        badge.setFixedHeight(15)
        top.addWidget(badge)
        from ..badges import BADGES, item_kind
        kind = item_kind(item)
        top.addWidget(letter_badge(kind, BADGES[kind][0].capitalize()))
        if item.get("explore"):
            top.addWidget(_explore_chip(theme))
        top.addStretch(1)
        when = QLabel(_time_ago(item.get("published", "")))
        when.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")
        top.addWidget(when)
        outer.addLayout(top)
        title = QLabel(item.get("title", ""))
        title.setTextFormat(Qt.PlainText)
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title.setStyleSheet(f"color:{theme['text']}; font-size:11.5px; font-weight:600; background:transparent;")
        outer.addWidget(title)
        why = ", ".join(item.get("match") or [])
        if why and not item.get("explore"):
            sub = QLabel(f"matches {why}")
            sub.setTextFormat(Qt.PlainText)
            sub.setWordWrap(True)
            sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            sub.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")
            outer.addWidget(sub)
        self.setToolTip(_tip(item.get("summary", "")))
        self.setStyleSheet(f"QFrame#newsCard {{ background:{theme['card_bg']}; border-radius:10px; }}"
                           f"QFrame#newsCard:hover {{ background:{theme['btn_bg']}; }}")
        self.setCursor(Qt.PointingHandCursor)
        url = item.get("url", "")
        self.mousePressEvent = lambda ev: on_open(url)  # noqa: ARG005


def letter_badge(letter: str, tooltip: str, url: str = "",
                 on_open: Callable[[str], bool] | None = None) -> QPushButton:
    """P (paper, green) · N (news, yellow) · D (discussion, blue) · A (announcement,
    violet): one small square, one meaning, everywhere. Clickable when it has a link."""
    from ..badges import BADGES
    color = BADGES[letter][1]
    badge = QPushButton(letter)
    badge.setFixedSize(18, 18)
    badge.setToolTip(tooltip)
    text = "#1a1a1a" if letter == "N" else "white"          # dark on yellow reads better
    badge.setStyleSheet(f"QPushButton {{ background:{color}; color:{text}; border:none; border-radius:4px; "
                        f"font-size:10px; font-weight:800; padding:0; }}")
    if url and on_open is not None:
        badge.setCursor(Qt.PointingHandCursor)
        badge.clicked.connect(lambda: on_open(url))
    return badge


def published_badge(paper: dict[str, Any], on_open: Callable[[str], bool]) -> QPushButton:
    """The green [P]: this repo has a published paper. Click to open it."""
    cited = paper.get("cited")
    title = paper.get("title") or paper.get("doi") or "a paper"
    year = (paper.get("date") or "")[:4]
    return letter_badge("P", f"Published: {title}" + (f" ({year})" if year else "")
                        + (f" · cited {cited} times" if cited else "") + "\nClick to open the paper.",
                        paper.get("url", ""), on_open)


def news_badge(story: dict[str, Any], on_open: Callable[[str], bool]) -> QPushButton:
    """The yellow [N] (in the news) or blue [D] (discussed on Hacker News) on a repo."""
    what = "In the news" if story["kind"] == "N" else "Discussed on Hacker News"
    return letter_badge(story["kind"], f"{what} this week: {story.get('title', '')}\nClick to read it.",
                        story.get("url", ""), on_open)


BADGE_LEGEND = ("<span style='color:#22c55e'>■</span> P paper &nbsp; <span style='color:#eab308'>■</span> N news "
                "&nbsp; <span style='color:#38bdf8'>■</span> D discussion &nbsp; "
                "<span style='color:#a78bfa'>■</span> A announcement")


class ResearchCard(QFrame):
    """A paper: why it's trending, title, venue and citations, lead authors,
    and its GitHub repo. Clicking expands it: open the paper or the repo, and
    see the people working on the repo (loaded on first expand)."""

    def __init__(self, paper: dict[str, Any], theme: dict[str, Any], on_open: Callable[[str], bool],
                 on_open_repo: Callable[[str], bool], on_people: Callable[["ResearchCard", str], None] | None,
                 loader: "AvatarLoader | None" = None, kind: str = "rising") -> None:
        super().__init__()
        self.setObjectName("researchCard")
        self.paper, self.theme, self.loader = paper, theme, loader
        self._on_people, self._people_loaded = on_people, False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(3)

        self.header = QWidget()
        self.header.setCursor(Qt.PointingHandCursor)
        head = QVBoxLayout(self.header)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(3)
        top = QHBoxLayout()
        top.setSpacing(6)
        v = paper.get("velocity", 0) or 0
        per_month = round(v) if v >= 10 else round(v, 1)
        trend = QLabel(f"🔥 {per_month}/month" if kind == "rising"
                       else f"🛠️ {paper.get('cited', 0)} citations")
        trend.setToolTip("Citations per month since it was published" if kind == "rising" else
                         "A recent tool in your field, with a paper and its code on GitHub")
        trend.setStyleSheet(f"color:{theme['text']}; background:{theme['section_btn']}; border-radius:7px; "
                            f"padding:1px 6px; font-size:9.5px;")
        trend.setFixedHeight(16)
        top.addWidget(trend)
        if paper.get("repos"):
            top.addWidget(published_badge(paper, on_open))
        if paper.get("explore"):
            top.addWidget(_explore_chip(theme))
        top.addStretch(1)
        year = QLabel((paper.get("date") or "")[:4])
        year.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")
        top.addWidget(year)
        head.addLayout(top)
        title = QLabel(paper.get("title", ""))
        title.setTextFormat(Qt.PlainText)
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title.setStyleSheet(f"color:{theme['text']}; font-size:11.5px; font-weight:600; background:transparent;")
        head.addWidget(title)
        authors = paper.get("authors") or []
        who = authors[0]["name"] if authors else ""
        if len(authors) > 1:
            who += f" … {authors[-1]['name']}"
        meta_bits = [b for b in (paper.get("venue"), f"cited {paper.get('cited', 0)}", who) if b]
        if paper.get("repos"):
            meta_bits.append("code: " + paper["repos"][0])
        meta = QLabel(" · ".join(meta_bits))
        meta.setTextFormat(Qt.PlainText)
        meta.setWordWrap(True)
        meta.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        meta.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")
        head.addWidget(meta)
        outer.addWidget(self.header)

        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 4, 0, 0)
        body.setSpacing(4)
        buttons = QHBoxLayout()
        btn_style = (f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['text']}; border:none; "
                     f"border-radius:7px; padding:4px 9px; font-size:10.5px; }}"
                     f"QPushButton:hover {{ background:{theme['btn_hover']}; }}")
        paper_btn = QPushButton("Paper ↗")
        paper_btn.setStyleSheet(btn_style)
        paper_btn.setCursor(Qt.PointingHandCursor)
        url = paper.get("url", "")
        paper_btn.clicked.connect(lambda: on_open(url))
        buttons.addWidget(paper_btn)
        for repo in (paper.get("repos") or [])[:2]:
            b = QPushButton(f"{repo} ↗")
            b.setStyleSheet(btn_style)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, r=repo: on_open_repo(f"https://github.com/{r}"))
            buttons.addWidget(b)
        buttons.addStretch(1)
        body.addLayout(buttons)
        self.people_box = QVBoxLayout()
        self.people_box.setSpacing(3)
        body.addLayout(self.people_box)
        outer.addWidget(self.body)
        self.body.setVisible(False)

        self.setStyleSheet(f"QFrame#researchCard {{ background:{theme['card_bg']}; border-radius:10px; }}")
        self.setToolTip(_tip(paper.get("abstract", "")))
        self.header.mousePressEvent = lambda ev: self.toggle()  # noqa: ARG005

    def toggle(self) -> None:
        # isHidden(), not isVisible(): the latter is False whenever the window itself isn't shown
        expanded = self.body.isHidden()
        self.body.setVisible(expanded)
        repos = self.paper.get("repos") or []
        if expanded and repos and self._on_people and not self._people_loaded:
            self._people_loaded = True
            note = QLabel("Finding the people working on it…")
            note.setStyleSheet(f"color:{self.theme['muted']}; font-size:10px; background:transparent;")
            self.people_box.addWidget(note)
            self._on_people(self, repos[0])

    def set_people(self, people: list[dict[str, Any]], on_open: Callable[[str], bool]) -> None:
        _clear_layout(self.people_box)
        if not people:
            note = QLabel("No one found on GitHub for this repo.")
            note.setStyleSheet(f"color:{self.theme['muted']}; font-size:10px; background:transparent;")
            self.people_box.addWidget(note)
            return
        head = QLabel("PEOPLE WORKING ON IT")
        head.setStyleSheet(f"color:{self.theme['muted']}; font-size:9.5px; font-weight:700; background:transparent;")
        self.people_box.addWidget(head)
        for person in people:
            row = QFrame()
            row.setObjectName("personRow")
            lay = QHBoxLayout(row)
            lay.setContentsMargins(2, 2, 2, 2)
            lay.setSpacing(6)
            lay.addWidget(_avatar_widget(person["login"], person.get("avatar", ""), 20, self.loader))
            name = QLabel(person["login"])
            name.setTextFormat(Qt.PlainText)
            name.setStyleSheet(f"color:{self.theme['text']}; font-size:10.5px; font-weight:600; background:transparent;")
            lay.addWidget(name)
            role = QLabel(person.get("role", ""))
            role.setTextFormat(Qt.PlainText)
            role.setStyleSheet(f"color:{self.theme['muted']}; font-size:10px; background:transparent;")
            lay.addWidget(role)
            lay.addStretch(1)
            row.setCursor(Qt.PointingHandCursor)
            row.setToolTip(f"Open {person['login']}'s GitHub profile")
            row.setStyleSheet(f"QFrame#personRow {{ border-radius:6px; }}"
                              f"QFrame#personRow:hover {{ background:{self.theme['btn_bg']}; }}")
            login = person["login"]
            row.mousePressEvent = lambda ev, u=login: on_open(f"https://github.com/{u}")  # noqa: ARG005
            self.people_box.addWidget(row)


class ResearcherRow(QFrame):
    """Someone who keeps leading the trending papers; opens their ORCID or OpenAlex page."""

    def __init__(self, person: dict[str, Any], theme: dict[str, Any], on_open: Callable[[str], bool]) -> None:
        super().__init__()
        self.setObjectName("researcherRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(8)
        lay.addWidget(_avatar_label(person.get("name", "?"), 26))
        box = QVBoxLayout()
        box.setSpacing(1)
        name = QLabel(person.get("name", ""))
        name.setTextFormat(Qt.PlainText)
        name.setStyleSheet(f"color:{theme['text']}; font-size:11.5px; font-weight:600; background:transparent;")
        box.addWidget(name)
        n = person.get("papers", 0)
        stats = QLabel(f"{n} trending paper{'s' if n != 1 else ''} · {person.get('citations', 0)} citations")
        stats.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")
        box.addWidget(stats)
        lay.addLayout(box, 1)
        self.setStyleSheet(f"QFrame#researcherRow {{ background:{theme['card_bg']}; border-radius:10px; }}"
                           f"QFrame#researcherRow:hover {{ background:{theme['btn_bg']}; }}")
        url = person.get("url", "")
        if url:
            self.setCursor(Qt.PointingHandCursor)
            self.setToolTip("Open their ORCID / OpenAlex profile")
            self.mousePressEvent = lambda ev: on_open(url)  # noqa: ARG005


MAP_FIELD = "#7fd8ff"      # your research field
MAP_LEARNED = "#ff6fd8"    # what you're into lately
MAP_EXPLORE = "#9b87ff"    # today's new territory


MAP_MOTION_MS = 8000    # the interest map moves this long after it appears, then rests (docs/RESOURCES.md, plan 1)
MAP_WAKE_MS = 6000      # ...and this long again when the mouse comes over it (the phone: a tap)


class InterestMap(QWidget):
    """Your interests as a slowly turning constellation: you in the middle,
    your research field on the inner ring, what you've been into lately on
    the middle ring (bigger = stronger, gently pulsing), and today's new
    territory drifting on a dashed outer ring. Hover a point for what it is.
    It moves for a few seconds when it appears or the mouse comes over it, then rests: a page left open must not
    repaint 30 times a second for hours."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(300)
        self.setMouseTracking(True)
        self._center = "you"
        self._nodes: list[dict[str, Any]] = []
        self._phase = 0.0
        self._intro = 1.0
        self._text = QColor("#f0f0f5")
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._awake_until = 0.0
        self._intro_anim = _grow_animation(self, self._set_intro, 1400)

    def set_theme_colors(self, text_color: str, explore_color: str | None = None) -> None:
        self._text = _parse_color(text_color, force_alpha=255)
        self._explore = QColor(explore_color) if explore_color else None
        self.update()

    def set_data(self, center: str, field: list[str], learned: list[tuple[str, float]], explore: list[str]) -> None:
        self._center = center or "you"
        top = max((w for _, w in learned), default=1.0) or 1.0
        def short(topic: str) -> str:   # "Genetic Mapping and Diversity in ..." -> "Genetic Mapping"
            words = [w for w in topic.split() if w.lower() not in ("and", "in", "of", "the", "for")]
            return " ".join(words[:2])
        nodes = [{"ring": 0, "label": short(t), "size": 8.0, "color": MAP_FIELD,
                  "tip": f"{t}\nYour research field (OpenAlex topics, Scholar interests, your topics)"}
                 for t in field[:6]]
        nodes += [{"ring": 1, "label": t, "size": 5.0 + 9.0 * (w / top), "color": MAP_LEARNED,
                   "tip": f"{t}\nWhat you're into lately: strength {w:g}, learned from your clicks, follows, "
                          "stars and forks"} for t, w in learned[:10]]
        nodes += [{"ring": 2, "label": t, "size": 6.0, "color": MAP_EXPLORE,
                   "tip": f"{t}\nNew territory today: outside your usual interests, on purpose"}
                  for t in explore[:4]]
        for ring in (0, 1, 2):
            members = [n for n in nodes if n["ring"] == ring]
            step = 2 * math.pi / max(len(members), 1)
            for i, n in enumerate(members):
                # each ring starts half a step further round, so labels fall between, not on top
                n["angle"] = step * i + ring * step / 2 + ring * 0.35
        self._nodes = nodes
        self.update()

    def play(self) -> None:
        self._intro_anim.stop()
        self._intro_anim.start()

    def _set_intro(self, v: float) -> None:
        self._intro = v
        self.update()

    def wake(self, ms: int) -> None:
        self._awake_until = max(self._awake_until, time.monotonic() + ms / 1000)
        if self.isVisible() and not self._timer.isActive():
            self._timer.start()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.wake(MAP_MOTION_MS)

    def enterEvent(self, event) -> None:  # noqa: N802
        super().enterEvent(event)
        self.wake(MAP_WAKE_MS)

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        self._timer.stop()

    def _tick(self) -> None:
        if time.monotonic() > self._awake_until:
            self._timer.stop()                         # at rest: drawn once more where it stopped, then nothing
            return
        self._phase += 0.033
        self.update()

    def _geometry(self) -> tuple[float, float, list[float]]:
        w, h = self.width(), self.height()
        r = min(w, h) / 2 - 18
        return w / 2, h / 2, [r * 0.38, r * 0.72, r * 0.98]

    def _pos(self, n: dict[str, Any]) -> QPointF:
        cx, cy, radii = self._geometry()
        speed = (0.05, -0.035, 0.022)[n["ring"]]
        a = n["angle"] + self._phase * speed
        rr = radii[n["ring"]] * self._intro
        return QPointF(cx + math.cos(a) * rr, cy + math.sin(a) * rr * 0.86)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtWidgets import QToolTip
        pos = event.position()
        best, best_d = None, 18.0
        for n in self._nodes:
            p = self._pos(n)
            d = math.hypot(p.x() - pos.x(), p.y() - pos.y())
            if d < best_d:
                best, best_d = n, d
        if best:
            QToolTip.showText(event.globalPosition().toPoint(), best["tip"], self)
        else:
            QToolTip.hideText()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        cx, cy, radii = self._geometry()
        # rings
        for i, r in enumerate(radii):
            ring = QColor(self._text)
            ring.setAlpha(30 if i < 2 else 40)
            pen = QPen(ring, 1)
            if i == 2:
                pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), r * self._intro, r * 0.86 * self._intro)
        # threads from you to each point
        for n in self._nodes:
            p = self._pos(n)
            c = QColor(n["color"])
            c.setAlpha(40 if n["ring"] < 2 else 28)
            pen = QPen(c, 1)
            if n["ring"] == 2:
                pen.setStyle(Qt.DotLine)
            painter.setPen(pen)
            painter.drawLine(QPointF(cx, cy), p)
        # the points: a soft glow, a core, a label
        font = painter.font()
        font.setPointSizeF(7.6)
        painter.setFont(font)
        dots = []
        for n in self._nodes:
            p = self._pos(n)
            size = n["size"] * (1 + 0.12 * math.sin(self._phase * 2.2 + n["angle"] * 3)) if n["ring"] == 1 else n["size"]
            glow = QRadialGradient(p, size * 2.6)
            c = QColor(n["color"])
            c.setAlpha(110)
            glow.setColorAt(0, c)
            c.setAlpha(0)
            glow.setColorAt(1, c)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(p, size * 2.6, size * 2.6)
            core = QColor(n["color"])
            if n["ring"] == 2:
                painter.setBrush(Qt.NoBrush)
                pen = QPen(core, 1.4)
                pen.setStyle(Qt.DashLine)
                painter.setPen(pen)
            else:
                painter.setBrush(core)
            painter.drawEllipse(p, size, size)
            dots.append((n, p, size))
        # labels last, so none collides with another label or a point: lately-into first, then
        # new territory, then your field; each tries outward, inward, above, below -- and a label
        # with no free spot is left to the hover tooltip rather than drawn on top of another
        fm = painter.fontMetrics()
        taken = [QRectF(p.x() - sz, p.y() - sz, 2 * sz, 2 * sz) for _, p, sz in dots]
        taken.append(QRectF(cx - 24, cy - 24, 48, 48))
        for n, p, size in sorted(dots, key=lambda d: (1, 2, 0).index(d[0]["ring"])):
            label = n["label"] if len(n["label"]) <= 20 else n["label"][:19] + "…"
            tw, th = fm.horizontalAdvance(label), fm.height()
            out_x = p.x() + size + 4 if p.x() >= cx else p.x() - size - 4 - tw
            in_x = p.x() - size - 4 - tw if p.x() >= cx else p.x() + size + 4
            spots = [(out_x, p.y() - th / 2), (in_x, p.y() - th / 2),
                     (p.x() - tw / 2, p.y() - size - th - 1), (p.x() - tw / 2, p.y() + size + 1)]
            own = QRectF(p.x() - size, p.y() - size, 2 * size, 2 * size)
            for x, y in spots:
                rect = QRectF(x, y, tw, th)
                if rect.left() < 1 or rect.right() > self.width() - 1 or rect.top() < 0                         or rect.bottom() > self.height():
                    continue
                if any(rect.intersects(r.adjusted(-2, -1, 2, 1)) for r in taken if r != own):
                    continue
                taken.append(rect)
                painter.setPen(self._text if n["ring"] < 2 else (getattr(self, "_explore", None) or QColor(n["color"])))
                painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, label)
                break
        # you
        halo = QRadialGradient(QPointF(cx, cy), 34)
        halo.setColorAt(0, QColor(255, 111, 216, 120))
        halo.setColorAt(1, QColor(255, 111, 216, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(halo))
        painter.drawEllipse(QPointF(cx, cy), 34, 34)
        grad = QLinearGradient(cx - 16, cy - 16, cx + 16, cy + 16)
        grad.setColorAt(0, QColor("#ff6fd8"))
        grad.setColorAt(1, QColor("#7a5cff"))
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPointF(cx, cy), 16, 16)
        font.setPointSizeF(8.5)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("white"))
        initials = "".join(w[0] for w in self._center.replace("-", " ").split()[:2]).upper() or "Y"
        painter.drawText(QRectF(cx - 16, cy - 16, 32, 32), Qt.AlignCenter, initials[:2])
        painter.end()


class ExploreDonut(QWidget):
    """How much of every list is kept for new territory."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(84, 84)
        self._share = 0.0
        self._shown = 0.0
        self._text = QColor("#f0f0f5")
        self._anim = _grow_animation(self, self._set, 1100)

    def set_theme_colors(self, text_color: str) -> None:
        self._text = QColor(text_color)
        self.update()

    def set_share(self, share: float) -> None:
        self._share = max(0.0, min(share, 1.0))
        self._shown = self._share
        self.update()

    def play(self) -> None:
        self._anim.stop()
        self._anim.start()

    def _set(self, v: float) -> None:
        self._shown = self._share * v
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(8, 8, self.width() - 16, self.height() - 16)
        painter.setPen(QPen(QColor(255, 255, 255, 30), 9, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, 0, 360 * 16)
        painter.setPen(QPen(QColor(MAP_EXPLORE), 9, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, 90 * 16, -int(360 * 16 * self._shown))
        painter.setPen(self._text)
        font = painter.font()
        font.setPointSizeF(11)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, f"{round(self._shown * 100)}%")
        painter.end()


WHOIS_MINUTES = 30         # how often a pending "Is this you?" search is tried again (OpenAlex was busy)
NOTIFY_MINUTES = 20        # how often the panel looks for something worth notifying (only if a kind is on)

# The dock's planets: each tab's colour and line icon (24x24 SVG path data).
PLANETS = {
    "live": ("#ff6fd8", "M13 2 3 14h9l-1 8 10-12h-9l1-8z"),
    "suggestions": ("#7fd8ff", "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"),
    "repos": ("#22c55e", "M6 3v12M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 9a9 9 0 0 1-9 9"),
    "market": ("#ffc457", "M22 7 13.5 15.5 8.5 10.5 2 17M16 7h6v6"),
    "news": ("#eab308", "M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-4 0v-9h4M18 14h-8M15 18h-5M10 6h8v4h-8z"),
    "activity": ("#34d399", "M22 12h-4l-3 9L9 3l-3 9H2"),
    "signals": ("#a78bfa", "M4.9 19.1a10 10 0 0 1 0-14.2M7.8 16.2a6 6 0 0 1 0-8.4M16.2 7.8a6 6 0 0 1 0 8.4M19.1 4.9a10 10 0 0 1 0 14.2M12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z"),
    "grow": ("#4ade80", "M7 20h10M10 20c5.5-2.5.8-6.4 3-10M9.5 9.4c1.1.8 1.8 2.2 2.3 3.7-2 .4-3.5.4-4.8-.3-1.2-.6-2.3-1.9-3-4.2 2.8-.5 4.4 0 5.5.8zM14.1 6a7 7 0 0 0-1.1 4c1.9-.1 3.3-.6 4.3-1.4 1-1 1.6-2.3 1.7-4.6-2.7.1-4 1-4.9 2z"),
    "chances": ("#f472b6", "M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16M4 6h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z"),
    "model": ("#ffd24a", "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"),
    "badges": ("#f0a35e", "M12 15a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM8.2 13.9 7 23l5-3 5 3-1.2-9.1"),
    "admin": ("#94a3b8", "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"),
}
# the groups' line icons (navtree.GROUPS), and the back planet's chevron
GROUP_ICONS = {
    "you": PLANETS["model"][1], "grow": PLANETS["grow"][1], "repos": PLANETS["repos"][1], "chances": PLANETS["chances"][1],
    "world": "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z",
    "circle": PLANETS["suggestions"][1],
    "feed": "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",     # 🏠 Home, the first page
    "settings": ("M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 "
                 "1.65 0 0 0-2.82 1.17V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-2.82-1.17l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 "
                 "1.65 0 0 0 3 13H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83"
                 "l.06.06A1.65 1.65 0 0 0 10 3.09V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 2.82 1.17l.06-.06a2 2 0 1 1 2.83 2.83l-.06"
                 ".06A1.65 1.65 0 0 0 21 11h.09a2 2 0 1 1 0 4H21a1.65 1.65 0 0 0-1.6 0z"),   # ⚙ Settings (its pages, Help), the last
}
BACK_ICON = "M15 18l-6-6 6-6"


# Google Drive's logo, for the Saving sign when your data is saved there (the phone's components/status-signs.tsx)
DRIVE_LOGO = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 87.3 78">'
    '<path d="m6.6 66.85 3.85 6.65c.8 1.4 1.95 2.5 3.3 3.3l13.75-23.8h-27.5c0 1.55.4 3.1 1.2 4.5z" fill="#0066da"/>'
    '<path d="m43.65 25-13.75-23.8c-1.35.8-2.5 1.9-3.3 3.3l-25.4 44a9.06 9.06 0 0 0 -1.2 4.5h27.5z" fill="#00ac47"/>'
    '<path d="m73.55 76.8c1.35-.8 2.5-1.9 3.3-3.3l1.6-2.75 7.65-13.25c.8-1.4 1.2-2.95 1.2-4.5h-27.502l5.852 11.5z" '
    'fill="#ea4335"/>'
    '<path d="m43.65 25 13.75-23.8c-1.35-.8-2.9-1.2-4.5-1.2h-18.5c-1.6 0-3.15.45-4.5 1.2z" fill="#00832d"/>'
    '<path d="m59.8 53h-32.3l-13.75 23.8c1.35.8 2.9 1.2 4.5 1.2h50.8c1.6 0 3.15-.45 4.5-1.2z" fill="#2684fc"/>'
    '<path d="m73.4 26.5-12.7-22c-.8-1.4-1.95-2.5-3.3-3.3l-13.75 23.8 16.15 28h27.45c0-1.55-.4-3.1-1.2-4.5z" '
    'fill="#ffba00"/></svg>')

SIGN_ICONS = {
    "github": "M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 "
              "1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.4 5.4 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49"
              "-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4M9 18c-4.51 2-5-2-7-2",
    "data": "M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9ZM9 13l2 2 4-4",
    "data_bad": "M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9ZM3 3l18 18",
    "beacon": "M4.9 19.1C1 15.2 1 8.8 4.9 4.9M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5M19.1 "
              "4.9C23 8.8 23 15.1 19.1 19M12 12h.01",
}


class StatusSigns(QWidget):
    """The four signs on the right of the strip with the page's name (signs.py; the phone's
    components/status-signs.tsx): GitHub, ORCID, saving to your data repo, your Signals beacon. Lit when on,
    faint when never set up, red when its access stopped working. A click says what the sign means."""

    clicked = Signal(str)
    D = 22

    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict[str, str]] = []
        self._colors: dict[str, QColor] = {}
        self.setFixedHeight(self.D)
        self.setCursor(Qt.PointingHandCursor)

    def set_signs(self, items: list[dict[str, str]], theme: dict[str, Any]) -> None:
        lit = {"github": theme["text"], "orcid": "#a6ce39", "data": "#22d3ee", "beacon": "#ff6fd8"}
        self.items = items
        self._colors = {s["key"]: QColor(logic.readable(theme["bad"] if s["state"] == "bad" else lit[s["key"]], theme))
                        for s in items}
        self.setFixedWidth(len(items) * (self.D + 5))
        self.setToolTip("\n".join(f"{s['label']}: {s['tip']}" for s in items))
        self.update()

    def _at(self, x: float) -> dict[str, str] | None:
        i = int(x // (self.D + 5))
        return self.items[i] if 0 <= i < len(self.items) else None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        s = self._at(event.position().x())
        if s:
            self.clicked.emit(s["tip"])

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for i, s in enumerate(self.items):
            c = self._colors.get(s["key"], QColor("#888888"))
            box = QRectF(i * (self.D + 5) + 1, 1, self.D - 2, self.D - 2)
            p.setOpacity(0.3 if s["state"] == "off" else 1.0)
            if s["state"] == "bad":
                fill = QColor(c)
                fill.setAlpha(40)
                p.setBrush(fill)
            else:
                p.setBrush(Qt.NoBrush)
            p.setPen(QPen(c, 1.4))
            p.drawEllipse(box)
            if s["key"] == "orcid":
                f = p.font()
                f.setPixelSize(9)
                f.setBold(True)
                p.setFont(f)
                p.drawText(box, Qt.AlignCenter, "iD")
                continue
            if s.get("icon") == "drive":
                QSvgRenderer(QByteArray(DRIVE_LOGO.encode())).render(p, box.adjusted(4, 4.6, -4, -4.4))
                continue
            path = SIGN_ICONS["data_bad" if s["key"] == "data" and s["state"] == "bad" else s["key"]]
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c.name()}" '
                   f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="{path}"/></svg>')
            QSvgRenderer(QByteArray(svg.encode())).render(p, box.adjusted(4, 4, -4, -4))
        p.end()


class PlanetButton(QPushButton):
    """One planet in the dock: a coloured ring with a line icon. The selected one
    swells into a filled planet with a soft halo, with a little spring to it."""

    def __init__(self, color: str, path: str, emoji: str = "", solid: bool = False) -> None:
        super().__init__("")
        self._color = QColor(color)
        self._path = path
        self._emoji = emoji              # a part's planet shows its emoji instead of a line icon
        self._solid = solid              # the back planet: filled in its colour, darker, with a white chevron
        self._grow = 0.0
        self._hover = False
        self._dot = False
        self._count = 0                  # new things in this tab (see freshness.py)
        self._selected = False
        self._bg = QColor("#1c1c2c")
        self._icons: dict[str, QSvgRenderer] = {}
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(360)
        self._anim.setEasingCurve(QEasingCurve.OutBack)
        self._anim.valueChanged.connect(self._on_grow)
        self.setFixedHeight(48)
        self.setMinimumWidth(1)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)

    def _on_grow(self, v) -> None:
        self._grow = float(v)
        self.update()

    def set_selected(self, on: bool, animate: bool = True) -> None:
        if on == self._selected and (self._grow in (0.0, 1.0) or self._anim.state() == QVariantAnimation.Running):
            return
        self._selected = on
        target = 1.0 if on else 0.0
        if animate and self.isVisible():
            self._anim.stop()
            self._anim.setEasingCurve(QEasingCurve.OutBack if on else QEasingCurve.OutCubic)
            self._anim.setStartValue(self._grow)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._grow = target
            self.update()

    def set_dot(self, on: bool) -> None:
        self._dot = on
        self.update()

    def set_count(self, n: int) -> None:
        if n != self._count:
            self._count = n
            self.update()

    def set_planet_bg(self, color: QColor) -> None:
        self._bg = color
        self.update()

    def _icon(self, color: QColor) -> QSvgRenderer:
        key = color.name()
        if key not in self._icons:
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{key}" '
                   f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="{self._path}"/></svg>')
            self._icons[key] = QSvgRenderer(QByteArray(svg.encode()))
        return self._icons[key]

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        g = self._grow
        c = QPointF(self.width() / 2, self.height() / 2)
        r = 12 + 6 * g + (1 if self._hover and g < 0.5 else 0)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        if g > 0.01:                                       # the halo of the selected planet
            halo = QColor(self._color)
            halo.setAlpha(int(70 * min(g, 1.0)))
            painter.setPen(Qt.NoPen)
            painter.setBrush(halo)
            painter.drawEllipse(c, r + 3 * g, r + 3 * g)
        fill = QColor(
            int(self._bg.red() + (self._color.red() - self._bg.red()) * min(max(g, 0), 1)),
            int(self._bg.green() + (self._color.green() - self._bg.green()) * min(max(g, 0), 1)),
            int(self._bg.blue() + (self._color.blue() - self._bg.blue()) * min(max(g, 0), 1)))
        if self._solid:
            fill = self._color.darker(150)
        painter.setPen(QPen(self._color, 2))
        painter.setBrush(fill)
        painter.drawEllipse(c, r, r)
        side = r * 1.05
        if self._emoji:
            font = painter.font()
            font.setPixelSize(int(r * 1.05))
            painter.setFont(font)
            painter.setPen(QColor("#0d0d16") if g > 0.5 else self._color)
            painter.drawText(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), Qt.AlignCenter, self._emoji)
        else:
            icon_color = QColor("#ffffff") if self._solid else QColor("#0d0d16") if g > 0.5 else self._color
            self._icon(icon_color).render(painter, QRectF(c.x() - side / 2, c.y() - side / 2, side, side))
        if self._count > 0 and g < 0.5:                   # how many new things wait in this tab
            text = "9+" if self._count > 9 else str(self._count)
            font = painter.font()
            font.setPixelSize(9)
            font.setBold(True)
            painter.setFont(font)
            w = max(13.0, painter.fontMetrics().horizontalAdvance(text) + 6.0)
            bubble = QRectF(c.x() + r * 0.45, c.y() - r - 3, w, 13)
            painter.setPen(Qt.NoPen)
            painter.setBrush(self._color)
            painter.drawRoundedRect(bubble, 6.5, 6.5)
            painter.setPen(QColor("#0d0d16"))
            painter.drawText(bubble, Qt.AlignCenter, text)
        elif self._dot and g < 0.5:                       # something new here (e.g. a new badge)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#f0f0f5"))
            painter.drawEllipse(QPointF(c.x() + r * 0.8, c.y() - r * 0.8), 3.5, 3.5)
        painter.end()


class HeightGrip(QWidget):
    """A small handle at the bottom of the panel: drag it to make the panel taller
    or shorter (within limits). Double-click goes back to the default height."""

    def __init__(self, on_drag: Callable[[float, float, bool], None], current: Callable[[], float]) -> None:
        super().__init__()
        self._on_drag, self._current = on_drag, current
        self._start_y: float | None = None
        self._start_fraction = 0.6
        self.setFixedSize(64, 12)
        self.setCursor(Qt.SizeVerCursor)
        self.setToolTip("Drag to make the panel taller or shorter (double-click: back to normal)")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 110 if self.underMouse() or self._start_y is not None else 55))
        painter.drawRoundedRect(QRectF(12, 4, self.width() - 24, 4), 2, 2)
        painter.end()

    def enterEvent(self, event) -> None:  # noqa: N802
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._start_y = event.globalPosition().y()
        self._start_fraction = self._current()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._start_y is not None:
            self._on_drag(event.globalPosition().y() - self._start_y, self._start_fraction, False)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._start_y is not None:
            self._on_drag(event.globalPosition().y() - self._start_y, self._start_fraction, True)
        self._start_y = None
        self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self._on_drag(0, 0.6, True)


class WidthGrip(QWidget):
    """The panel's inner edge (away from the screen edge): drag it to make the panel wider or narrower. Double-click
    goes back to the default width. It sits over the frame's edge and follows it as the panel resizes."""

    def __init__(self, frame: QWidget, on_drag: Callable[[float, int, bool], None], current: Callable[[], int],
                 side: Callable[[], str]) -> None:
        super().__init__(frame)
        self._on_drag, self._current, self._side = on_drag, current, side
        self._start_x: float | None = None
        self._start_w = 460
        self.setCursor(Qt.SizeHorCursor)
        self.setToolTip("Drag to make the panel wider or narrower (double-click: back to normal)")
        frame.installEventFilter(self)
        self.place()

    def place(self) -> None:
        frame = self.parentWidget()
        x = frame.width() - 6 if self._side().endswith("left") else 0      # a panel on the left grows rightwards
        self.setGeometry(x, 24, 6, max(0, frame.height() - 48))
        self.raise_()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() in (QEvent.Resize, QEvent.Show):
            self.place()
        return False

    def paintEvent(self, event) -> None:  # noqa: N802
        if not (self.underMouse() or self._start_x is not None):
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 110))
        mid = self.height() / 2
        painter.drawRoundedRect(QRectF(1.5, mid - 32, 3, 64), 1.5, 1.5)
        painter.end()

    def enterEvent(self, event) -> None:  # noqa: N802
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.update()

    def _outward(self, event) -> float:
        dx = event.globalPosition().x() - self._start_x
        return dx if self._side().endswith("left") else -dx

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._start_x = event.globalPosition().x()
        self._start_w = self._current()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._start_x is not None:
            self._on_drag(self._outward(event), self._start_w, False)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._start_x is not None:
            self._on_drag(self._outward(event), self._start_w, True)
        self._start_x = None
        self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self._on_drag(0, MyGeekyConfig().gui_expanded_width, True)


class QrWidget(QWidget):
    """Paints a QR code (a matrix of dark modules) crisply at any size."""

    def __init__(self, matrix: list[list[bool]], size: int = 260) -> None:
        super().__init__()
        self._m = matrix
        self.setFixedSize(size, size)

    def set_matrix(self, matrix: list[list[bool]]) -> None:
        self._m = matrix
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self._m:
            return                                     # nothing yet: leave the space empty
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("white"))
        n = len(self._m) or 1
        cell = self.width() / n
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#12121c"))
        for y, row in enumerate(self._m):
            for x, dark in enumerate(row):
                if dark:
                    painter.drawRect(QRectF(x * cell, y * cell, cell + 0.5, cell + 0.5))
        painter.end()


class PairDialog(QDialog):
    """⚙ → Connect your phone: a QR code the myGeeKy phone app scans to set
    itself up. It closes by itself after a couple of minutes."""

    def __init__(self, parent: "MyGeekyPanel", theme: dict[str, Any]) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)   # in front of the always-on-top panel
        self.setWindowTitle("Connect your phone")
        self.setMinimumWidth(340)
        self._panel = parent
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lay.setSizeConstraint(QLayout.SetFixedSize)   # the window always fits its contents, as they change
        self.intro = QLabel("In the myGeeKy phone app, tap <b>Scan from your computer</b> and point it at this code.")
        self.intro.setWordWrap(True)
        self.intro.setFixedWidth(320)
        lay.addWidget(self.intro)
        self.wait = QLabel("Checking your GitHub token\u2026")
        lay.addWidget(self.wait, 0, Qt.AlignCenter)
        self.qr = QrWidget([])                         # its space is reserved now; the code is drawn when ready
        lay.addWidget(self.qr, 0, Qt.AlignCenter)
        self.why = QLabel("")
        self.why.setWordWrap(True)
        self.why.setFixedWidth(320)
        lay.addWidget(self.why)
        self.countdown = QLabel("")
        lay.addWidget(self.countdown)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        lay.addWidget(close, 0, Qt.AlignRight)
        self.setStyleSheet(f"QDialog {{ background:#17171f; }} QLabel {{ color:{theme['text']}; font-size:11.5px; }}"
                           f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['text']}; border:none; "
                           f"border-radius:7px; padding:6px 14px; }}")
        self._left = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        parent._run_async(lambda: logic.phone_pairing(parent.cfg), self._ready)

    def _ready(self, result: Any) -> None:
        result = result if isinstance(result, dict) else {}
        self.wait.setVisible(False)
        if not result.get("ok"):
            self.why.setText(result.get("error", "Couldn't make the code."))
            return
        self.qr.set_matrix(result["matrix"])
        self.why.setText(("\U0001f512 " if result["with_token"] else "") + result["why"]
                         + " Your Signals token never leaves this computer.")
        self._left = result["seconds"]
        self._tick()
        self._timer.start(1000)

    def _tick(self) -> None:
        if self._left <= 0:
            self._timer.stop()
            self.accept()                       # gone: nobody can photograph it later
            return
        self.countdown.setText(f"This code disappears in {self._left}s.")
        self._left -= 1


# a person's links elsewhere: (short mark, colour, name)
LINK_MARKS = {
    "linkedin": ("in", "#0a66c2", "LinkedIn"), "orcid": ("iD", "#a6ce39", "ORCID"),
    "scholar": ("G", "#4285f4", "Google Scholar"), "researchgate": ("RG", "#00ccbb", "ResearchGate"),
    "facebook": ("f", "#1877f2", "Facebook"), "x": ("X", "#3a3a44", "X"), "web": ("\U0001f310", "#4b5563", "Website"),
}


class ActivityChart(QWidget):
    """Thirty small bars: someone's public GitHub activity per day."""

    def __init__(self, counts: list[int], color: str) -> None:
        super().__init__()
        self.counts, self.color = counts, QColor(color)
        self.setFixedHeight(46)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        n = max(len(self.counts), 1)
        top = max(self.counts or [1]) or 1
        w = self.width() / n
        for i, c in enumerate(self.counts):
            h = 3 if c == 0 else 6 + (self.height() - 8) * c / top
            col = QColor(self.color)
            col.setAlpha(60 if c == 0 else 230)
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(i * w + 1, self.height() - h, max(w - 2, 1), h), 1.5, 1.5)
        p.end()


class ShimmerBar(QWidget):
    """A slim loading bar: a pink-to-violet glow sweeping across a faint track."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(5)
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        self._t = (self._t + 0.012) % 1.0
        self.update()

    def stop(self) -> None:
        self._timer.stop()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0, 0.5, 0, -0.5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 28))
        p.drawRoundedRect(r, 2.5, 2.5)
        w = r.width() * 0.38
        x = -w + (r.width() + w) * (0.5 - 0.5 * math.cos(math.pi * self._t))   # eases in and out
        grad = QLinearGradient(x, 0, x + w, 0)
        grad.setColorAt(0.0, QColor(255, 111, 216, 0))
        grad.setColorAt(0.35, QColor("#ff6fd8"))
        grad.setColorAt(0.75, QColor("#7a5cff"))
        grad.setColorAt(1.0, QColor(122, 92, 255, 0))
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(x, r.top(), w, r.height()), 2.5, 2.5)
        p.end()


class ProfileView(QFrame):
    """Someone at a glance, unfolding right under the person you clicked: their
    two most active repos, their most-starred one, a 30-day activity chart, their
    interests and their links elsewhere. Then, if you like, GitHub to follow."""

    def __init__(self, panel: "MyGeekyPanel", login: str, theme: dict[str, Any]) -> None:
        super().__init__()
        self.login, self.theme, self.panel = login, theme, panel
        self.setObjectName("profileView")
        self.setStyleSheet(f"QFrame#profileView {{ background:{theme['card_bg']}; border:1px solid {theme['accent']}; "
                           f"border-radius:12px; }} QLabel {{ color:{theme['text']}; font-size:11.5px; background:transparent; }}")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(12, 10, 12, 12)
        self.lay.setSpacing(7)
        self.loading = QLabel(f"Looking up <b>{login}</b>\u2026")
        self.loading.setTextFormat(Qt.RichText)
        self.loading.setStyleSheet(f"color:{theme['muted']}; font-size:11px;")
        self.bar = ShimmerBar()
        self.lay.addWidget(self.loading)
        self.lay.addWidget(self.bar)
        self.setMaximumHeight(0)
        self._anim = QPropertyAnimation(self, b"maximumHeight", self)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self._settled)
        QTimer.singleShot(0, self, lambda: self._grow_to(self._content_height()))
        panel._run_async(lambda: self._fetch(login), self._show)

    # ---- unfolding
    def _content_height(self) -> int:
        self.lay.activate()
        # height-for-width only counts once something wraps; while loading nothing does
        return max(self.lay.totalHeightForWidth(max(self.width(), 200)), self.lay.totalSizeHint().height())

    def _grow_to(self, h: int, ms: int = 320) -> None:
        self._anim.stop()
        self._anim.setDuration(ms)
        self._anim.setStartValue(self.maximumHeight() if self.maximumHeight() < 16777215 else self.height())
        self._anim.setEndValue(h)
        self._anim.start()

    def _settled(self) -> None:
        if self._anim.endValue() and self._anim.endValue() > 60 and not self.bar.isVisible():
            self.setMaximumHeight(16777215)              # fully open: let it follow its content
            area = self.panel._scroll_area_of(self)
            if area is not None:
                area.ensureWidgetVisible(self, 0, 10)
        elif self._anim.endValue() == 0:
            self.deleteLater()

    def fold(self) -> None:
        """Close it again (it removes itself when folded)."""
        self.setMaximumHeight(self.height())
        self._grow_to(0, 220)

    # ---- content
    @staticmethod
    def _fetch(login: str) -> dict[str, Any]:
        try:
            card = logic.person_card(login)
        except Exception as exc:
            return {"error": str(exc)}
        try:
            import requests
            url = card.get("avatar", "")
            if url.startswith("https://"):
                r = requests.get(url + ("&" if "?" in url else "?") + "s=128", timeout=15)
                card["avatar_bytes"] = r.content if r.ok else b""
        except Exception:
            card["avatar_bytes"] = b""
        return card

    def _muted(self, text: str, size: float = 11) -> QLabel:
        lab = _plain(QLabel(text))          # bios, places, errors: a stranger's words
        lab.setWordWrap(True)
        lab.setStyleSheet(f"color:{self.theme['muted']}; font-size:{size}px;")
        return lab

    def _section(self, text: str) -> None:
        lab = QLabel(text)
        lab.setStyleSheet(f"color:{self.theme['muted']}; font-size:9.5px; font-weight:700; letter-spacing:1px; margin-top:4px;")
        self.lay.addWidget(lab)

    def _repo_row(self, r: dict[str, Any], right: str) -> None:
        import html as h
        lab = QLabel(f"<a href='{h.escape(r['url'])}' style='color:{self.theme['text']}; text-decoration:none'>"
                     f"<b>{h.escape(r['name'])}</b></a>"
                     f"<span style='color:{self.theme['muted']}'>  {h.escape(r.get('language') or '')}  {right}</span>"
                     + (f"<br><span style='color:{self.theme['muted']}; font-size:10.5px'>{h.escape(r['description'])}</span>"
                        if r.get("description") else ""))
        lab.setTextFormat(Qt.RichText)
        lab.setWordWrap(True)
        lab.setCursor(Qt.PointingHandCursor)
        lab.linkActivated.connect(lambda url: logic.open_link(url))
        box = QFrame()                              # real margins (CSS padding makes QLabel mis-measure its height)
        box.setObjectName("repoBox")
        box.setStyleSheet("QFrame#repoBox { background:rgba(255,255,255,0.05); border-radius:8px; }")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(9, 6, 9, 6)
        bl.addWidget(lab)
        self.lay.addWidget(box)

    def _show(self, card: dict[str, Any]) -> None:
        import html as h
        self.bar.stop()
        self.bar.hide()
        self.loading.hide()
        top = QHBoxLayout()
        if card.get("error"):
            top.addWidget(self._muted(card["error"]), 1)
            top.addWidget(self._close_btn())
            self.lay.addLayout(top)
            QTimer.singleShot(0, self, lambda: self._grow_to(self._content_height()))
            return
        pic = QLabel()
        pix = QPixmap()
        if card.get("avatar_bytes") and pix.loadFromData(card["avatar_bytes"]):
            pic.setPixmap(_circular_pixmap(pix, 48))
        pic.setFixedSize(48, 48)
        top.addWidget(pic, 0, Qt.AlignTop)
        names = QVBoxLayout()
        title = QLabel(f"<b style='font-size:14px'>{h.escape(card.get('name') or card['login'])}</b>"
                       + (f"  <span style='color:{self.theme['muted']}'>@{h.escape(card['login'])}</span>"
                          if card.get("name") else ""))
        title.setTextFormat(Qt.RichText)
        names.addWidget(title)
        meta = [m for m in (card.get("location"), card.get("company"),
                            f"{card.get('followers', 0):,} followers", f"{card.get('public_repos', 0)} repos",
                            f"since {card['since']}" if card.get("since") else "") if m]
        names.addWidget(self._muted("  \u00b7  ".join(meta), 10.5))
        top.addLayout(names, 1)
        top.addWidget(self._close_btn(), 0, Qt.AlignTop)
        self.lay.addLayout(top)
        if card.get("bio"):
            self.lay.addWidget(self._muted(card["bio"]))
        if card.get("links"):                          # only the ones they have
            row = QHBoxLayout()
            row.setSpacing(6)
            for link in card["links"]:
                mark, color, name = LINK_MARKS.get(link["kind"], LINK_MARKS["web"])
                b = QPushButton(mark)
                b.setFixedSize(30, 30)
                b.setCursor(Qt.PointingHandCursor)
                b.setToolTip(_tip(f"{name}: {link['url']}"))
                b.setStyleSheet(f"QPushButton {{ background:{color}; color:white; border:none; border-radius:15px; "
                                f"font-weight:800; font-size:11px; padding:0; }} QPushButton:hover {{ border:2px solid white; }}")
                b.clicked.connect(lambda checked=False, u=link["url"]: QDesktopServices.openUrl(QUrl(u))
                                  if u.startswith("https://") else None)
                row.addWidget(b)
            row.addStretch(1)
            self.lay.addLayout(row)
        if card.get("active"):
            self._section("MOST ACTIVE")
            for r in card["active"]:
                self._repo_row(r, f"pushed {_time_ago(r['pushed_at'])}" if r.get("pushed_at") else "")
        if card.get("top"):
            self._section("MOST STARRED")
            self._repo_row(card["top"], f"\u2605 {card['top']['stars']:,}")
        self._section(f"ACTIVITY, LAST 30 DAYS \u00b7 {sum(card.get('daily') or [])} public events")
        self.lay.addWidget(ActivityChart(card.get("daily") or [], self.theme["accent"]))
        if card.get("interests"):
            self._section("INTERESTS")
            chips = QLabel("".join(f"<span style='background:rgba(122,92,255,0.25); color:{self.theme['text']}'>"
                                   f"&nbsp;{h.escape(t)}&nbsp;</span>&nbsp; " for t in card["interests"]))
            chips.setTextFormat(Qt.RichText)
            chips.setWordWrap(True)
            self.lay.addWidget(chips)
        go = QPushButton("Open on GitHub to follow")
        go.setCursor(Qt.PointingHandCursor)
        go.setStyleSheet("QPushButton { background:#7a5cff; color:white; border:none; border-radius:8px; "
                         "padding:7px 12px; font-weight:700; font-size:11.5px; } QPushButton:hover { background:#8d73ff; }")
        go.clicked.connect(lambda: self.panel._opened_profile(card.get("url", "")))
        self.lay.addSpacing(2)
        self.lay.addWidget(go)
        # unfold to the full card (twice: word-wrapped labels only know their height once styled)
        QTimer.singleShot(0, self, lambda: self._grow_to(self._content_height(), 420))
        QTimer.singleShot(140, self, lambda: self._grow_to(self._content_height(), 280))

    def _close_btn(self) -> QPushButton:
        b = QPushButton("\u00d7")
        b.setFixedSize(26, 26)
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip("Fold it away")
        b.setStyleSheet(f"QPushButton {{ background:transparent; color:{self.theme['muted']}; border:none; font-size:16px; }}"
                        f"QPushButton:hover {{ color:{self.theme['text']}; }}")
        b.clicked.connect(self.panel._fold_profile)
        return b


class IdeaDialog(QDialog):
    """The 💡: an idea, a problem or a question, sent as a prefilled GitHub issue
    that the user submits themselves (nothing is sent from here)."""

    def __init__(self, parent: QWidget, theme: dict[str, Any]) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)   # in front of the always-on-top panel
        from ..ideas import KINDS
        self.setWindowTitle("Send an idea to myGeeKy")
        self.setMinimumWidth(380)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        intro = QLabel("Ideas, problems and questions go to myGeeKy's maker as a GitHub issue. Your browser opens "
                       "it ready to send. Click <b>Submit</b> there, with your GitHub account. It's public, so "
                       "don't include tokens or private data.<br>No GitHub account, or rather private? Use "
                       "<b>✉ Send by email</b>: the same message, ready in your own mail app.")
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.RichText)
        lay.addWidget(intro)
        kinds = QHBoxLayout()
        self.kind_buttons: dict[str, QRadioButton] = {}
        for key, (emoji, label, _) in KINDS.items():
            if key in ("report", "protocol"):   # sent from the listing or protocol itself, details filled in
                continue
            b = QRadioButton(f"{emoji} {label}")
            self.kind_buttons[key] = b
            kinds.addWidget(b)
        self.kind_buttons["idea"].setChecked(True)
        kinds.addStretch(1)
        lay.addLayout(kinds)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("In a few words")
        lay.addWidget(self.title_edit)
        self.details = QPlainTextEdit()
        self.details.setPlaceholderText("Details: what would help, or what happened and what you expected")
        self.details.setFixedHeight(110)
        lay.addWidget(self.details)
        self.with_version = QCheckBox("Include version info (myGeeKy, Python, Windows version; helps with problems)")
        self.with_version.setChecked(True)
        lay.addWidget(self.with_version)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Close")
        cancel.clicked.connect(self.reject)
        self.send = QPushButton("Open on GitHub ↗")
        self.send.clicked.connect(self._send)
        self.send_email = QPushButton("✉ Send by email")
        self.send_email.setToolTip("Opens your mail app with this message to support@mygeeky.org, ready to send")
        self.send_email.clicked.connect(self._send_by_email)
        row.addWidget(cancel)
        row.addWidget(self.send_email)
        row.addWidget(self.send)
        lay.addLayout(row)
        self.setStyleSheet(f"QDialog {{ background:#17171f; }} QLabel, QRadioButton, QCheckBox {{ color:{theme['text']}; "
                           f"font-size:11.5px; }} QLineEdit, QPlainTextEdit {{ background:#22222e; color:{theme['text']}; "
                           f"border:1px solid #34344a; border-radius:7px; padding:5px; }}"
                           f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['text']}; border:none; "
                           f"border-radius:7px; padding:6px 12px; }} QPushButton:hover {{ background:{theme['btn_hover']}; }}"
                           "QRadioButton::indicator { width:12px; height:12px; border-radius:7px; "
                           "border:2px solid #6b6b88; background:transparent; }"
                           f"QRadioButton::indicator:checked {{ background:{theme['accent']}; border-color:{theme['accent']}; }}")

    def kind(self) -> str:
        return next(k for k, b in self.kind_buttons.items() if b.isChecked())

    def _send(self) -> None:
        from ..ideas import issue_url
        if not self.title_edit.text().strip():
            self.status.setText("Give it a short title first.")
            return
        url = issue_url(self.kind(), self.title_edit.text(), self.details.toPlainText(), self.with_version.isChecked())
        # in the background: handing a long link to the browser can block for a while on some
        # Windows setups (e.g. while Windows asks which app should open it)
        import threading
        import webbrowser
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
        from ..achievements import log
        log("idea")
        self.status.setText("✓ Your browser opened it on GitHub: click <b>Submit new issue</b> there to send it. "
                            "Thank you!")

    def _send_by_email(self) -> None:
        from ..ideas import email_url
        if not self.title_edit.text().strip():
            self.status.setText("Give it a short title first.")
            return
        url = email_url(self.kind(), self.title_edit.text(), self.details.toPlainText(), self.with_version.isChecked())
        QDesktopServices.openUrl(QUrl(url))
        from ..achievements import log
        log("idea")
        self.status.setText("✓ Your mail app opened it, addressed to support@mygeeky.org: press <b>Send</b> there. "
                            "Thank you!")


class IdeaRow(QFrame):
    """One idea/problem/question in the admin inbox; clicking opens it."""

    def __init__(self, item: dict[str, Any], theme: dict[str, Any], on_open: Callable[[str], bool]) -> None:
        super().__init__()
        from ..ideas import KINDS
        self.setObjectName("ideaRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(8)
        emoji = QLabel(KINDS.get(item.get("kind", "idea"), KINDS["idea"])[0])
        emoji.setStyleSheet("font-size:14px; background:transparent;")
        lay.addWidget(emoji)
        box = QVBoxLayout()
        box.setSpacing(1)
        title = QLabel(item.get("title", ""))
        title.setTextFormat(Qt.PlainText)
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title.setStyleSheet(f"color:{theme['text']}; font-size:11.5px; font-weight:600; background:transparent;")
        box.addWidget(title)
        meta = QLabel(f"#{item.get('number')} · {item.get('author', '')} · {_time_ago(item.get('created_at', ''))}"
                      f" · 💬 {item.get('comments', 0)} · 👍 {item.get('reactions', 0)}")
        meta.setTextFormat(Qt.PlainText)
        meta.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")
        box.addWidget(meta)
        lay.addLayout(box, 1)
        self.setStyleSheet(f"QFrame#ideaRow {{ background:{theme['card_bg']}; border-radius:10px; }}"
                           f"QFrame#ideaRow:hover {{ background:{theme['btn_bg']}; }}")
        self.setCursor(Qt.PointingHandCursor)
        url = item.get("url", "")
        self.mousePressEvent = lambda ev: on_open(url)  # noqa: ARG005


class ProspectCard(QFrame):
    """Someone who might want myGeeKy: why, and what you can do. Nothing is
    ever sent from here: Email opens a draft in your mail app, Copy puts the
    invite on your clipboard, and you mark them once you've reached out."""

    def __init__(self, person: dict[str, Any], theme: dict[str, Any], on_action: Callable[[str, dict], None],
                 loader: "AvatarLoader | None" = None) -> None:
        super().__init__()
        self.setObjectName("prospectCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 7, 8, 7)
        outer.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(_avatar_widget(person.get("login", "?"), person.get("avatar", ""), 30, loader))
        box = QVBoxLayout()
        box.setSpacing(1)
        name = QLabel(person.get("name") or person.get("login", ""))
        name.setTextFormat(Qt.PlainText)
        name.setStyleSheet(f"color:{theme['text']}; font-size:12px; font-weight:600; background:transparent;")
        box.addWidget(name)
        why = QLabel(f"@{person.get('login', '')} · " + "; ".join(person.get("why", [])[:2]))
        why.setTextFormat(Qt.PlainText)
        why.setWordWrap(True)
        why.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        why.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")
        box.addWidget(why)
        if person.get("last_active"):
            n = person.get("events_30d", 0)
            act = QLabel(f"\U0001f525 {n} public event{'s' if n != 1 else ''} in 30 days \u00b7 "
                         f"last active {_time_ago(person['last_active'])}")
            act.setStyleSheet(f"color:{theme['good'] if n >= 5 else theme['muted']}; font-size:10px; background:transparent;")
            box.addWidget(act)
        if person.get("bio"):
            bio = QLabel(person["bio"][:110])
            bio.setTextFormat(Qt.PlainText)
            bio.setWordWrap(True)
            bio.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            bio.setStyleSheet(f"color:{theme['muted']}; font-size:10px; font-style:italic; background:transparent;")
            box.addWidget(bio)
        top.addLayout(box, 1)
        sc = QLabel(f"{person.get('score', 0):.1f}")
        sc.setToolTip("How likely they are to want myGeeKy (higher is better)")
        sc.setStyleSheet(f"color:{theme['accent']}; font-size:12px; font-weight:700; background:transparent;")
        top.addWidget(sc, 0, Qt.AlignTop)
        outer.addLayout(top)
        row = QHBoxLayout()
        row.setSpacing(4)
        style = (f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['text']}; border:none; "
                 f"border-radius:7px; padding:3px 8px; font-size:10.5px; }}"
                 f"QPushButton:hover {{ background:{theme['btn_hover']}; }}")
        actions = [("Profile ↗", "profile"), ("✉ Gmail" if person.get("email") else "⧉ Copy invite",
                                              "email" if person.get("email") else "copy"),
                   ("Invited ✓", "invited"), ("Not now", "declined")]
        for label, action in actions:
            b = QPushButton(label)
            b.setStyleSheet(style)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, a=action: on_action(a, person))
            row.addWidget(b)
        row.addStretch(1)
        outer.addLayout(row)
        self.setStyleSheet(f"QFrame#prospectCard {{ background:{theme['card_bg']}; border-radius:10px; }}")


class SuggestionCard(QFrame):
    """Clicking anywhere on the card opens the profile; the panel then drops
    the person from the suggestions (see MyGeekyPanel._on_suggestion_clicked)."""

    def __init__(self, item: dict[str, Any], score_key: str, theme: dict[str, Any],
                 on_click: Callable[[dict[str, Any]], None], loader: "AvatarLoader | None" = None) -> None:
        super().__init__()
        self.setObjectName("card")
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(8)
        row.addWidget(_avatar_widget(item.get("username", "?"), item.get("avatar_url", ""), 32, loader))

        body = QVBoxLayout()
        body.setSpacing(2)
        title_row = QHBoxLayout()
        name_label = _plain(QLabel(item.get("username", "")))
        name_label.setStyleSheet("font-weight:600; font-size:12.5px; background:transparent;")
        score = item.get(score_key)
        score_label = QLabel(f"{score:.2f}" if isinstance(score, (int, float)) else "")
        score_label.setStyleSheet(f"color:{theme['muted']}; font-size:12px; background:transparent;")
        title_row.addWidget(name_label)
        if item.get("explore"):
            title_row.addWidget(_explore_chip(theme))
        title_row.addStretch(1)
        title_row.addWidget(score_label)
        body.addLayout(title_row)

        bio_label = _plain(QLabel((item.get("bio") or "")[:80]))
        bio_label.setWordWrap(True)  # a long bio must not widen the card past the panel
        bio_label.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
        body.addWidget(bio_label)
        row.addLayout(body, 1)

        self.setStyleSheet(f"#card {{ background:{theme['card_bg']}; border-radius:10px; }}"
                           f"#card:hover {{ background:{theme['btn_bg']}; }}")
        self.setToolTip("Open profile")
        self.setCursor(Qt.PointingHandCursor)
        self.mousePressEvent = lambda ev: on_click(item)  # noqa: ARG005


class _ActivityRow(QFrame):
    """One event inside an expanded person card; clicking opens the repo."""

    def __init__(self, event: dict[str, Any], theme: dict[str, Any], on_open: Callable[[str], bool]) -> None:
        super().__init__()
        self.setObjectName("activityRow")
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(8)
        verb = event.get("verb", "")
        repo = event.get("repo", "")
        text = QLabel(html.escape(verb) + (f" in <b>{html.escape(repo)}</b>" if repo else ""))   # a branch name may hold < and >
        text.setTextFormat(Qt.RichText)
        text.setWordWrap(True)
        text.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        text.setStyleSheet(f"color:{theme['text']}; font-size:11px; background:transparent;")
        row.addWidget(text, 1)
        when = QLabel(_time_ago(event.get("created_at", "")))
        when.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")
        row.addWidget(when, 0, Qt.AlignTop)
        self.setStyleSheet(f"QFrame#activityRow {{ border-radius:6px; }}"
                           f"QFrame#activityRow:hover {{ background:{theme['btn_bg']}; }}")
        self.setCursor(Qt.PointingHandCursor)
        url = event.get("repo_url") or event.get("profile_url", "")
        self.mousePressEvent = lambda ev: on_open(url)  # noqa: ARG005


class ActivityGroup(QFrame):
    """One person in the Activity tab: avatar, name, a one-line summary of
    their latest event and how many there are. Clicking the header expands
    their full recent activity; the arrow button opens their profile."""

    toggled = Signal(str, bool)

    def __init__(self, group: dict[str, Any], theme: dict[str, Any], on_open: Callable[[str], bool],
                 loader: "AvatarLoader | None" = None, expanded: bool = False) -> None:
        super().__init__()
        self.setObjectName("activityGroup")
        self.actor = group.get("actor", "")
        events = group.get("events") or []
        latest = events[0] if events else {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 7, 8, 7)
        outer.setSpacing(4)

        self.header = QWidget()
        self.header.setCursor(Qt.PointingHandCursor)
        head = QHBoxLayout(self.header)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        head.addWidget(_avatar_widget(self.actor or "?", group.get("actor_avatar", ""), 30, loader))

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name = _plain(QLabel(self.actor))
        name.setStyleSheet(f"color:{theme['text']}; font-size:12px; font-weight:600; background:transparent;")
        name_row.addWidget(name)
        is_match = group.get("source") == "match"
        tag = QLabel("profile match" if is_match else "following")
        tag.setStyleSheet(
            f"color:{theme['text']}; background:{theme['section_btn'] if is_match else theme['btn_bg']}; "
            f"border-radius:7px; padding:1px 6px; font-size:9.5px;")
        tag.setFixedHeight(16)
        name_row.addWidget(tag)
        name_row.addStretch(1)
        text_box.addLayout(name_row)
        summary = latest.get("verb", "")
        if latest.get("repo"):
            summary += f" in {latest['repo'].split('/')[-1]}"
        self.summary_label = _plain(QLabel(f"{summary} · {_time_ago(latest.get('created_at', ''))}"))
        self.summary_label.setWordWrap(True)  # long branch names must not widen the card past the panel
        self.summary_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.summary_label.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
        text_box.addWidget(self.summary_label)
        head.addLayout(text_box, 1)

        count = QLabel(str(len(events)))
        count.setAlignment(Qt.AlignCenter)
        count.setMinimumWidth(22)
        count.setFixedHeight(18)
        count.setStyleSheet(f"color:{theme['text']}; background:{theme['btn_bg']}; border-radius:9px; "
                            f"padding:1px 6px; font-size:10.5px; font-weight:600;")
        count.setToolTip(f"{len(events)} recent update{'s' if len(events) != 1 else ''}")
        head.addWidget(count)
        self.chevron = QLabel()
        self.chevron.setStyleSheet(f"color:{theme['muted']}; font-size:12px; background:transparent;")
        head.addWidget(self.chevron)
        profile_btn = QPushButton("↗")
        profile_btn.setToolTip(f"Open {self.actor}'s GitHub profile")
        profile_btn.setCursor(Qt.PointingHandCursor)
        profile_btn.setFixedSize(24, 24)
        profile_btn.setStyleSheet(
            f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['text']}; border:none; "
            f"border-radius:12px; font-size:12px; }}"
            f"QPushButton:hover {{ background:{theme['btn_hover']}; }}")
        profile_url = group.get("profile_url", "")
        profile_btn.clicked.connect(lambda: on_open(profile_url))
        head.addWidget(profile_btn)
        outer.addWidget(self.header)

        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(30, 2, 0, 0)
        body.setSpacing(0)
        for event in events:
            body.addWidget(_ActivityRow(event, theme, on_open))
        outer.addWidget(self.body)

        self.setStyleSheet(f"QFrame#activityGroup {{ background:{theme['card_bg']}; border-radius:10px; }}")
        self.header.mousePressEvent = lambda ev: self.set_expanded(not self.expanded, notify=True)  # noqa: ARG005
        self.expanded = False
        self.set_expanded(expanded)

    def set_expanded(self, expanded: bool, notify: bool = False) -> None:
        self.expanded = expanded
        self.body.setVisible(expanded)
        self.summary_label.setVisible(not expanded)
        self.chevron.setText("▾" if expanded else "▸")
        if notify:
            self.toggled.emit(self.actor, expanded)


PANEL_GESTURES = ("thanks", "learn", "watching", "collab")  # "used" needs a repo: CLI only
GESTURE_TIPS = {
    "thanks": "Thank {who} for their work. Private: only they can read it, and no reply is expected.",
    "learn": "Tell {who} you learned from their work. Private, and no reply is expected.",
    "watching": "Let {who} know you're following their work. Private, and no reply is expected.",
    "collab": "Open to collaborating with {who}. They only find out if they choose it for you too; "
              "then you both see it. Otherwise nobody ever knows.",
}


class SignalCard(QFrame):
    """One person on the Signals tab: a signal they sent you, or a fellow
    myGeeKy user. The emoji buttons send a private signal; the arrow opens
    their profile; 🔇 mutes them (they're never told). Everything shown from
    someone's beacon is rendered as plain text."""

    def __init__(self, item: dict[str, Any], theme: dict[str, Any], on_open: Callable[[str], bool],
                 on_send: Callable[["SignalCard", str, str], None] | None,
                 loader: "AvatarLoader | None" = None,
                 on_mute: Callable[[str], None] | None = None) -> None:
        super().__init__()
        from ..beacon import GESTURES
        self.setObjectName("signalCard")
        self.login = item.get("from") or item.get("login") or ""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 7, 8, 7)
        outer.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(_avatar_widget(self.login or "?", item.get("avatar_url", ""), 30, loader))
        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name = QLabel(self.login)
        name.setTextFormat(Qt.PlainText)
        name.setStyleSheet(f"color:{theme['text']}; font-size:12px; font-weight:600; background:transparent;")
        name_row.addWidget(name)
        badge_text = "🤝 match" if item.get("mutual") else "signalled you" if item.get("signalled_you") else ""
        if badge_text:
            badge = QLabel(badge_text)
            badge.setStyleSheet(f"color:{theme['text']}; background:{theme['section_btn']}; "
                                f"border-radius:7px; padding:1px 6px; font-size:9.5px;")
            badge.setFixedHeight(16)
            name_row.addWidget(badge)
        name_row.addStretch(1)
        text_box.addLayout(name_row)

        if "text" in item:  # an incoming signal
            line = f"{item['text']} · {_time_ago(item.get('at', ''))}"
            if not item.get("mutual") and item.get("type") != "join":   # an answer to your call: reply as you like
                line += " · no reply needed"
        else:               # a fellow user
            shared = item.get("shared") or []
            line = " · ".join(x for x in (item.get("status", ""),
                                          f"shares {', '.join(shared[:4])}" if shared else
                                          ", ".join((item.get("interests") or [])[:4])) if x)
        sub = QLabel(line)
        sub.setTextFormat(Qt.PlainText)
        sub.setWordWrap(True)
        sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        sub.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
        text_box.addWidget(sub)
        head.addLayout(text_box, 1)

        profile_btn = QPushButton("↗")
        profile_btn.setToolTip(f"Open {self.login}'s GitHub profile")
        profile_btn.setCursor(Qt.PointingHandCursor)
        profile_btn.setFixedSize(24, 24)
        btn_style = (f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['text']}; border:none; "
                     f"border-radius:12px; font-size:12px; }}"
                     f"QPushButton:hover {{ background:{theme['btn_hover']}; }}"
                     f"QPushButton:disabled {{ color:{theme['muted']}; }}")
        profile_btn.setStyleSheet(btn_style)
        profile_url = item.get("profile_url", "")
        profile_btn.clicked.connect(lambda: on_open(profile_url))
        if on_mute is not None and "text" in item:
            mute_btn = QPushButton("🔇")
            mute_btn.setToolTip(f"Mute {self.login}: hide their signals. They're never told; "
                                "`mygeeky beacon unmute` brings them back.")
            mute_btn.setCursor(Qt.PointingHandCursor)
            mute_btn.setFixedSize(24, 24)
            mute_btn.setStyleSheet(btn_style)
            mute_btn.clicked.connect(lambda: on_mute(self.login))
            head.addWidget(mute_btn)
        head.addWidget(profile_btn)
        outer.addLayout(head)

        self.gesture_buttons: dict[str, QPushButton] = {}
        if on_send is not None and item.get("can_receive", True):
            row = QHBoxLayout()
            row.setContentsMargins(38, 0, 0, 0)
            row.setSpacing(4)
            for g in PANEL_GESTURES:
                emoji, verb = GESTURES[g]
                btn = QPushButton(emoji)
                btn.setFixedSize(28, 24)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setToolTip(GESTURE_TIPS[g].format(who=self.login))
                btn.setStyleSheet(btn_style)
                btn.clicked.connect(lambda checked=False, gg=g: on_send(self, self.login, gg))
                self.gesture_buttons[g] = btn
                row.addWidget(btn)
            row.addStretch(1)
            self.feedback = QLabel("")
            self.feedback.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")
            row.addWidget(self.feedback)
            outer.addLayout(row)

        self.setStyleSheet(f"QFrame#signalCard {{ background:{theme['card_bg']}; border-radius:10px; }}")

    def set_busy(self, busy: bool) -> None:
        for btn in self.gesture_buttons.values():
            btn.setEnabled(not busy)

UP_COLOR = "#34d399"
DOWN_COLOR = "#f87171"


def _fmt_count(n: float | None) -> str:
    if n is None:
        return "–"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return f"{n:.0f}"


class Sparkline(QWidget):
    """A tiny trend line with a soft fill, green when rising, red when falling."""

    def __init__(self, values: list[float], trend: str | None = None, width: int = 64, height: int = 22) -> None:
        super().__init__()
        self.setFixedSize(width, height)
        self._values = [float(v) for v in values]
        self._trend = trend

    def paintEvent(self, event) -> None:  # noqa: N802 -- Qt's own naming convention
        if len(self._values) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        lo, hi = min(self._values), max(self._values)
        span = (hi - lo) or 1.0
        n = len(self._values)
        pts = [QPointF(2 + i * (w - 4) / (n - 1), h - 2 - (v - lo) / span * (h - 4))
               for i, v in enumerate(self._values)]
        if self._trend is None:
            color = QColor(150, 150, 165)  # no comparable period: neutral
        else:
            color = QColor(UP_COLOR if self._trend == "up" else DOWN_COLOR)
        line = QPainterPath(pts[0])
        for p in pts[1:]:
            line.lineTo(p)
        area = QPainterPath(line)
        area.lineTo(pts[-1].x(), h)
        area.lineTo(pts[0].x(), h)
        area.closeSubpath()
        fill = QColor(color)
        fill.setAlpha(45)
        painter.fillPath(area, fill)
        painter.setPen(QPen(color, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(line)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(pts[-1], 2.2, 2.2)
        painter.end()


class MarketRow(QFrame):
    """One repo on the board: rank, movement since the last ranked day,
    name, stars (+ this week), PyPI downloads/week (+ change), commits and a
    sparkline. Clicking opens the repo."""

    def __init__(self, row: dict[str, Any], theme: dict[str, Any], on_open: Callable[[str], bool],
                 loader: "AvatarLoader | None" = None) -> None:
        super().__init__()
        self.setObjectName("marketRow")
        self.repo = row.get("repo", "")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(8)

        rank_box = QVBoxLayout()
        rank_box.setSpacing(0)
        rank = QLabel(f"#{row.get('rank', '?')}")
        rank.setAlignment(Qt.AlignCenter)
        rank.setStyleSheet(f"color:{theme['text']}; font-size:12px; font-weight:700; background:transparent;")
        rank_box.addWidget(rank)
        move = row.get("movement")
        if move == "new":
            move_text, move_color = "NEW", theme["accent"]
        elif isinstance(move, int) and move > 0:
            move_text, move_color = f"▲{move}", UP_COLOR
        elif isinstance(move, int) and move < 0:
            move_text, move_color = f"▼{-move}", DOWN_COLOR
        else:
            move_text, move_color = "–", theme["muted"]
        move_label = QLabel(move_text)
        move_label.setAlignment(Qt.AlignCenter)
        move_label.setStyleSheet(f"color:{move_color}; font-size:9.5px; font-weight:600; background:transparent;")
        rank_box.addWidget(move_label)
        rank_holder = QWidget()
        rank_holder.setLayout(rank_box)
        rank_holder.setFixedWidth(30)
        outer.addWidget(rank_holder)

        owner, _, name = self.repo.partition("/")
        outer.addWidget(_avatar_widget(owner or "?", row.get("avatar", ""), 26, loader))

        body = QVBoxLayout()
        body.setSpacing(1)
        title = QLabel(f"<b>{html.escape(name)}</b> <span style='color:{theme['muted']}'>{html.escape(owner)}</span>")
        title.setTextFormat(Qt.RichText)
        title_line = QHBoxLayout()
        title_line.setSpacing(5)
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title.setStyleSheet(f"color:{theme['text']}; font-size:11.5px; background:transparent;")
        title.setToolTip(_tip(row.get("description", "")))
        title_line.addWidget(title, 1)
        if row.get("paper"):
            title_line.addWidget(published_badge(row["paper"], on_open))
        if row.get("news"):
            title_line.addWidget(news_badge(row["news"], on_open))
        body.addLayout(title_line)

        bits = [f"★ {_fmt_count(row.get('stars'))}"]
        stars_week = row.get("stars_week")
        if stars_week:
            color = UP_COLOR if stars_week > 0 else DOWN_COLOR
            bits[0] += f" <span style='color:{color}'>{stars_week:+d}</span>"
        if row.get("downloads_week") is not None:
            dl = f"↓ {_fmt_count(row['downloads_week'])}/wk"
            change = row.get("downloads_change")
            if change is not None:
                color = UP_COLOR if change >= 0 else DOWN_COLOR
                dl += f" <span style='color:{color}'>{'▲' if change >= 0 else '▼'}{abs(change) * 100:.0f}%</span>"
            bits.append(dl)
        if row.get("commits_4w") is not None:
            bits.append(f"{row['commits_4w']} commits/4wk")
        stats = QLabel(" · ".join(bits))
        stats.setWordWrap(True)
        stats.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        stats.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
        body.addWidget(stats)
        outer.addLayout(body, 1)

        spark = Sparkline(row.get("spark") or [], row.get("trend"))
        spark.setToolTip("weekly PyPI downloads" if row.get("spark_kind") == "downloads" else "weekly commits")
        outer.addWidget(spark, 0, Qt.AlignVCenter)

        self.setStyleSheet(f"QFrame#marketRow {{ background:{theme['card_bg']}; border-radius:10px; }}"
                           f"QFrame#marketRow:hover {{ background:{theme['btn_bg']}; }}")
        self.setCursor(Qt.PointingHandCursor)
        url = row.get("url", "")
        self.mousePressEvent = lambda ev: on_open(url)  # noqa: ARG005


PH_ORANGE = "#ff6154"


class ModelRow(QFrame):
    """One Hugging Face model: name, what it does, likes, downloads, how hot it is."""

    def __init__(self, m: dict[str, Any], theme: dict[str, Any], on_open: Callable[[str], bool]) -> None:
        super().__init__()
        self.setObjectName("modelRow")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(8)
        icon = QLabel("\U0001f917")
        icon.setStyleSheet("font-size:15px; background:transparent;")
        outer.addWidget(icon, 0, Qt.AlignTop)
        body = QVBoxLayout()
        body.setSpacing(1)
        owner, _, name = m.get("id", "").partition("/")
        title = QLabel(f"<b>{html.escape(name)}</b> <span style='color:{theme['muted']}'>{html.escape(owner)}</span>")
        title.setTextFormat(Qt.RichText)
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title.setStyleSheet(f"color:{theme['text']}; font-size:11.5px; background:transparent;")
        body.addWidget(title)
        bits = [m["pipeline"].replace("-", " ")] if m.get("pipeline") else []
        bits += [f"\u2665 {_fmt_count(m.get('likes'))}", f"\u2193 {_fmt_count(m.get('downloads'))}"]
        if m.get("match"):
            bits.append("matches " + ", ".join(m["match"][:3]))
        sub = QLabel(" \u00b7 ".join(bits))
        sub.setTextFormat(Qt.PlainText)
        sub.setWordWrap(True)
        sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        sub.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")
        body.addWidget(sub)
        outer.addLayout(body, 1)
        hot = QLabel(f"\U0001f525 {_fmt_count(m.get('trending'))}")
        hot.setToolTip("Hugging Face's trending score: how fast it's gaining likes and downloads right now")
        hot.setStyleSheet(f"color:{theme['text']}; font-size:10.5px; font-weight:600; background:transparent;")
        outer.addWidget(hot, 0, Qt.AlignTop)
        self.setStyleSheet(f"QFrame#modelRow {{ background:{theme['card_bg']}; border-radius:10px; }}"
                           f"QFrame#modelRow:hover {{ background:{theme['btn_bg']}; }}")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(_tip(", ".join(m.get("tags") or [])[:300]))
        url = m.get("url", "")
        self.mousePressEvent = lambda ev: on_open(url)  # noqa: ARG005


class ProductHuntRow(QFrame):
    """One Product Hunt launch under the Market board: thumbnail, name,
    tagline, upvotes, and a 'your field' tag when it mentions your terms.
    Product Hunt text is someone else's, so it's always plain text.
    Clicking opens the launch page."""

    def __init__(self, post: dict[str, Any], theme: dict[str, Any], on_open: Callable[[str], bool],
                 loader: "AvatarLoader | None" = None) -> None:
        super().__init__()
        self.setObjectName("phRow")
        self.slug = post.get("slug", "")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(8)
        outer.addWidget(_avatar_widget(post.get("name") or "?", post.get("thumbnail", ""), 26, loader))

        body = QVBoxLayout()
        body.setSpacing(1)
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name = QLabel(post.get("name", ""))
        name.setTextFormat(Qt.PlainText)
        name.setStyleSheet(f"color:{theme['text']}; font-size:11.5px; font-weight:700; background:transparent;")
        name_row.addWidget(name)
        if post.get("match"):
            tag = QLabel("your field")
            tag.setToolTip("Mentions " + ", ".join(post["match"][:4]))
            tag.setStyleSheet(f"color:{theme['text']}; background:{theme['section_btn']}; "
                              f"border-radius:7px; padding:1px 6px; font-size:9.5px;")
            tag.setFixedHeight(16)
            name_row.addWidget(tag)
        name_row.addStretch(1)
        body.addLayout(name_row)
        tagline = QLabel(post.get("tagline", ""))
        tagline.setTextFormat(Qt.PlainText)
        tagline.setWordWrap(True)
        tagline.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        tagline.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
        body.addWidget(tagline)
        outer.addLayout(body, 1)

        if not post.get("from_feed"):          # the public feed has no vote counts
            votes = QLabel(f"▲ {_fmt_count(post.get('votes'))}")
            votes.setToolTip(f"{post.get('votes', 0)} upvotes · {post.get('comments', 0)} comments")
            votes.setStyleSheet(f"color:{PH_ORANGE}; font-size:11px; font-weight:700; background:transparent;")
            outer.addWidget(votes, 0, Qt.AlignVCenter)

        self.setStyleSheet(f"QFrame#phRow {{ background:{theme['card_bg']}; border-radius:10px; }}"
                           f"QFrame#phRow:hover {{ background:{theme['btn_bg']}; }}")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(", ".join(post.get("topics") or []))
        url = post.get("url", "")
        self.mousePressEvent = lambda ev: on_open(url)  # noqa: ARG005


class _ClickableLabel(QLabel):
    """A word-wrapping label that acts like a link button."""

    def __init__(self, text: str, on_click: Callable[[], Any]) -> None:
        super().__init__(text)
        self._on_click = on_click
        self.setTextFormat(Qt.PlainText)      # it shows issue titles: anyone on GitHub writes those
        self.setWordWrap(True)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event) -> None:  # noqa: N802 -- Qt's own naming convention
        self._on_click()


class RepoCard(QFrame):
    """One `mygeeky contribute` result: repo, why it fits, and its best
    starter issues. Every click only opens a GitHub page -- forking and the
    PR are always left to the user."""

    def __init__(self, item: dict[str, Any], theme: dict[str, Any], on_open: Callable[[str], bool],
                 loader: "AvatarLoader | None" = None) -> None:
        super().__init__()
        self.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(_avatar_widget(item.get("owner", "?"), item.get("owner_avatar_url", ""), 32, loader))
        body = QVBoxLayout()
        body.setSpacing(2)
        title_row = QHBoxLayout()
        name_label = _plain(QLabel(item.get("full_name", "")))
        name_label.setStyleSheet("font-weight:600; font-size:12.5px; background:transparent;")
        name_label.setToolTip(_tip(item.get("full_name", "")))
        name_label.setMinimumWidth(1)  # a long owner/name is clipped instead of widening the card
        score = item.get("score")
        score_label = QLabel(f"{score:.2f}" if isinstance(score, (int, float)) else "")
        score_label.setStyleSheet(f"color:{theme['muted']}; font-size:12px; background:transparent;")
        title_row.addWidget(name_label, 1)
        if item.get("paper"):
            title_row.addWidget(published_badge(item["paper"], on_open))
        if item.get("news"):
            title_row.addWidget(news_badge(item["news"], on_open))
        if item.get("explore"):
            title_row.addWidget(_explore_chip(theme))
        title_row.addWidget(score_label)
        body.addLayout(title_row)

        meta = [f"★{item.get('stars', 0)}"]
        if item.get("language"):
            meta.insert(0, item["language"])
        meta_label = QLabel(" · ".join(meta))
        meta_label.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
        body.addWidget(meta_label)
        row.addLayout(body, 1)
        outer.addLayout(row)

        if item.get("description"):
            desc = _plain(QLabel(item["description"][:120]))
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
            outer.addWidget(desc)
        if item.get("reasons"):
            why = QLabel("why: " + "; ".join(item["reasons"]))
            why.setWordWrap(True)
            why.setStyleSheet(f"color:{theme['accent']}; font-size:10.5px; background:transparent;")
            outer.addWidget(why)

        btn_style = (
            f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['text']}; border:none; "
            f"border-radius:7px; padding:5px 8px; font-size:11px; text-align:left; }}"
            f"QPushButton:hover {{ background:{theme['btn_hover']}; }}"
        )
        for issue in (item.get("starter_issues") or [])[:2]:
            title = issue.get("title") or ""
            # a wrapping label, not a QPushButton: button text never wraps, so a
            # long issue title would force the card wider than the panel
            issue_row = _ClickableLabel("→ " + (title[:97] + "…" if len(title) > 100 else title),
                                        lambda u=issue.get("url", ""): on_open(u))
            issue_row.setObjectName("issue")
            issue_row.setToolTip(_tip(title))
            issue_row.setStyleSheet(
                f"#issue {{ background:{theme['btn_bg']}; color:{theme['text']}; border-radius:7px; "
                f"padding:5px 8px; font-size:11px; }}"
                f"#issue:hover {{ background:{theme['btn_hover']}; }}"
            )
            outer.addWidget(issue_row)

        repo_url = item.get("repo_url", "")
        actions = QHBoxLayout()
        actions.addStretch(1)
        for label, url in (("Fork →", item.get("fork_url", "")), ("Open →", repo_url)):
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(lambda checked=False, u=url: on_open(u))
            actions.addWidget(btn)
        outer.addLayout(actions)

        self.setStyleSheet(f"#card {{ background:{theme['card_bg']}; border-radius:10px; }}")
        # Clicking the card body opens the repo; the issue/Fork/Open buttons
        # consume their own clicks first, so no double-trigger.
        self.setCursor(Qt.PointingHandCursor)
        self.mousePressEvent = lambda ev: on_open(repo_url)  # noqa: ARG005


class SpotlightCard(QFrame):
    """One slide in the Live tab's ticker: a photo + headline + detail,
    normalized from either an activity event or a suggestion (see
    MyGeekyPanel._build_spotlight_items)."""

    KIND_BADGES = {"activity": "LIVE", "suggestion": "SUGGESTED", "signal": "FOR YOU"}

    def __init__(self, item: dict[str, Any], theme: dict[str, Any],
                 on_open: Callable[[str], bool], loader: "AvatarLoader | None") -> None:
        super().__init__()
        self.setObjectName("card")
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)
        row.addWidget(_avatar_widget(item.get("username", "?"), item.get("avatar_url", ""), 40, loader))

        body = QVBoxLayout()
        body.setSpacing(1)
        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        badge = QLabel(self.KIND_BADGES.get(item.get("kind"), ""))
        badge.setStyleSheet(
            f"color:{theme['accent']}; font-size:9px; font-weight:800; letter-spacing:0.6px; background:transparent;"
        )
        name_label = _plain(QLabel(item.get("username", "")))
        name_label.setStyleSheet("font-weight:700; font-size:12.5px; background:transparent;")
        top_row.addWidget(badge)
        top_row.addWidget(name_label)
        top_row.addStretch(1)
        if item.get("time_text"):
            time_label = _plain(QLabel(item["time_text"]))
            time_label.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")
            top_row.addWidget(time_label)
        body.addLayout(top_row)

        headline = _plain(QLabel(item.get("headline", "")))
        headline.setWordWrap(True)
        headline.setStyleSheet(f"color:{theme['text']}; font-size:11.5px; background:transparent;")
        body.addWidget(headline)

        if item.get("detail"):
            detail = _plain(QLabel(item["detail"]))
            detail.setWordWrap(True)
            detail.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
            body.addWidget(detail)

        row.addLayout(body, 1)
        self.setStyleSheet(f"#card {{ background:{theme['card_bg']}; border-radius:12px; }}")
        self.setCursor(Qt.PointingHandCursor)
        profile_url = item.get("profile_url", "")
        self.mousePressEvent = lambda ev: on_open(profile_url)  # noqa: ARG005


class SpotlightTicker(QWidget):
    """A vertical news-feed strip: as many cards as the available height
    fits, stacked and all visible at once, scrolling up together on a
    timer -- the newest story rises in at the bottom while the oldest
    visible one scrolls off the top. Fills whatever space its parent
    layout gives it (see `_build_live_tab`'s stretch factor) rather than
    a fixed one-card height, so a taller panel shows more stories at once."""

    CARD_HEIGHT = 72
    CARD_SPACING = 8

    def __init__(self, on_open: Callable[[str], bool], loader: "AvatarLoader | None") -> None:
        super().__init__()
        self._on_open = on_open
        self._loader = loader
        self._theme: dict[str, Any] = THEMES["midnight"]
        self._items: list[dict[str, Any]] = []
        self._next_index = 0
        self._cards: list[SpotlightCard] = []
        self._anim_group: QParallelAnimationGroup | None = None
        self.setMinimumHeight(self.CARD_HEIGHT)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

    def _visible_count(self) -> int:
        step = self.CARD_HEIGHT + self.CARD_SPACING
        return max(1, (self.height() + self.CARD_SPACING) // step)

    def _slot_y(self, slot: int) -> int:
        return slot * (self.CARD_HEIGHT + self.CARD_SPACING)

    def _make_card(self, item: dict[str, Any]) -> SpotlightCard:
        card = SpotlightCard(item, self._theme, self._on_open, self._loader)
        card.setParent(self)
        return card

    def set_theme(self, theme: dict[str, Any]) -> None:
        self._theme = theme
        if self._items:
            self._fill()

    def set_items(self, items: list[dict[str, Any]]) -> None:
        self._items = items
        self._fill()

    def _fill(self) -> None:
        """(Re)populate every visible slot from scratch -- first load,
        theme change, and any resize (the slot count depends on height)."""
        for card in self._cards:
            card.hide()  # deleteLater only runs on a later event-loop turn
            card.deleteLater()
        self._cards = []
        if not self._items:
            return
        count = min(self._visible_count(), len(self._items))
        for slot in range(count):
            card = self._make_card(self._items[slot % len(self._items)])
            card.setGeometry(0, self._slot_y(slot), self.width(), self.CARD_HEIGHT)
            card.show()
            self._cards.append(card)
        self._next_index = count % len(self._items)

    def start(self, interval_ms: int) -> None:
        self._interval = max(1200, interval_ms)
        if len(self._items) > len(self._cards) and self.isVisible():
            self._timer.start(self._interval)
        else:
            self._timer.stop()

    def stop(self) -> None:
        self._interval = 0
        self._timer.stop()

    def is_running(self) -> bool:
        return self._timer.isActive()

    # Folded, hidden or minimised, nobody sees it turn: no new card and animation every few seconds
    # (docs/RESOURCES.md, plan 2). It picks up again when it's shown.
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if getattr(self, "_interval", 0) and len(self._items) > len(self._cards):
            self._timer.start(self._interval)

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        self._timer.stop()

    def _advance(self) -> None:
        if not self._cards or len(self._items) <= len(self._cards):
            return
        if not self.isVisible() or self.window().isMinimized():
            return

        departing = self._cards.pop(0)
        visible_n = len(self._cards) + 1  # slot count before this update

        incoming = self._make_card(self._items[self._next_index])
        self._next_index = (self._next_index + 1) % len(self._items)
        incoming.setGeometry(0, self._slot_y(visible_n), self.width(), self.CARD_HEIGHT)
        incoming.show()
        self._cards.append(incoming)

        group = QParallelAnimationGroup(self)

        anim_out = QPropertyAnimation(departing, b"pos", self)
        anim_out.setDuration(420)
        anim_out.setStartValue(departing.pos())
        anim_out.setEndValue(QPoint(0, -self.CARD_HEIGHT))
        anim_out.setEasingCurve(QEasingCurve.OutCubic)
        group.addAnimation(anim_out)

        for slot, card in enumerate(self._cards):
            anim = QPropertyAnimation(card, b"pos", self)
            anim.setDuration(420)
            anim.setStartValue(card.pos())
            anim.setEndValue(QPoint(0, self._slot_y(slot)))
            anim.setEasingCurve(QEasingCurve.OutCubic)
            group.addAnimation(anim)

        group.finished.connect(departing.deleteLater)
        self._anim_group = group  # keep a reference alive until it finishes
        group.start()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._items:
            self._fill()


_RGBA_RE = re.compile(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)")
_GRADIENT_STOP_RE = re.compile(r"stop:\s*([\d.]+)\s+((?:rgba?\([^)]*\))|#[0-9a-fA-F]{3,8})")


def _parse_color(spec: str, force_alpha: int | None = None) -> QColor:
    """THEMES colors are Qt-stylesheet strings, e.g. 'rgba(255,255,255,31)'
    (Qt's rgba() alpha is 0-255, not the 0-1 the CSS spec uses elsewhere) --
    QColor's own string constructor doesn't understand rgba(), only
    #rrggbb/#aarrggbb and SVG color names, so it has to be hand-parsed.

    force_alpha overrides whatever alpha the spec itself carries -- used to
    paint the outer panel fully opaque regardless of the theme's own baked-in
    glass alpha, so the Transparency slider (a plain setWindowOpacity
    multiplier) has real headroom: multiplying can only ever *reduce*
    opacity below what's painted, never raise it, so at 0% the content
    itself must already be fully solid or the slider could never reach it."""
    match = _RGBA_RE.match(spec.strip())
    if match:
        r, g, b = (int(float(match.group(i))) for i in (1, 2, 3))
        a = force_alpha if force_alpha is not None else (
            int(float(match.group(4))) if match.group(4) is not None else 255
        )
        return QColor(r, g, b, a)
    color = QColor(spec)
    if force_alpha is not None:
        color.setAlpha(force_alpha)
    return color


def _parse_bg_brush(spec: str, rect: QRectF, force_alpha: int | None = None) -> QBrush:
    """theme['bg'] is a Qt-stylesheet qlineargradient(...) string (shared with
    the QSS `background:` rule used elsewhere in this file). QColor can't
    read that either -- passing it straight through silently produced solid
    opaque black instead of the intended translucent glass gradient."""
    stops = _GRADIENT_STOP_RE.findall(spec)
    if not stops:
        return QBrush(_parse_color(spec, force_alpha))
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    for pos, color in stops:
        gradient.setColorAt(float(pos), _parse_color(color, force_alpha))
    return QBrush(gradient)


class RoundedPanel(QFrame):
    """A frameless-window background frame with genuinely curved corners.

    A stylesheet `border-radius` on a frame sitting directly on top of a
    WA_TranslucentBackground top-level window doesn't reliably zero out the
    alpha channel in the corner pixels on this Windows/Qt/DWM combination --
    they render opaque-square instead of see-through-rounded. Painting the
    shape by hand, explicitly clearing to transparent first, sidesteps that.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bg_spec = ""
        self._border_spec = ""
        self._radius = 0.0

    def set_style(self, bg: str, border: str, radius: float) -> None:
        self._bg_spec = bg
        self._border_spec = border
        self._radius = radius
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 -- Qt's own naming convention
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        # Painted fully opaque regardless of the theme's own glass alpha --
        # the window-level Transparency slider (setWindowOpacity) is the only
        # thing that should make this see-through; see _parse_color.
        painter.fillPath(path, _parse_bg_brush(self._bg_spec, rect, force_alpha=255))
        painter.setPen(QPen(_parse_color(self._border_spec, force_alpha=255), 1))
        painter.drawPath(path)
        painter.end()


HEART_COLORS = ("#ff6fa8", "#ff8fc0", "#ff5c8a", "#ffa3c9", "#e86fd8")


def _heart_path(size: float) -> QPainterPath:
    """A heart `size` wide, centred on (0, 0)."""
    s = size / 2.0
    path = QPainterPath(QPointF(0, s * 0.95))
    path.cubicTo(-s * 1.3, s * 0.05, -s * 0.75, -s * 1.15, 0, -s * 0.45)
    path.cubicTo(s * 0.75, -s * 1.15, s * 1.3, s * 0.05, 0, s * 0.95)
    return path


class HeartsOverlay(QWidget):
    """A see-through, click-through window above the folded icon that lets a
    few small hearts drift up like smoke: each rises, wobbles, shrinks and
    fades out within a few seconds. It's only on screen during a puff, so
    there's nothing to click by accident and nothing ticking in between."""

    W, H = 120, 190

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)    # macOS: don't vanish with another app active
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(self.W, self.H)
        self._particles: list[dict[str, float]] = []
        self._clock = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    def is_active(self) -> bool:
        return bool(self._particles)

    def puff(self, icon_rect, dock_side: str, count: int = 4) -> None:
        """Release `count` hearts from the top of `icon_rect` (global coords),
        drifting away from the screen edge the panel is docked to."""
        import random
        inward = 1.0 if dock_side.endswith("left") else -1.0
        x = icon_rect.center().x() - self.W // 2 + int(inward * 18)
        self.move(x, icon_rect.top() - self.H + icon_rect.height() // 3)
        for i in range(count):
            self._particles.append({
                "born": self._clock + i * random.uniform(0.35, 0.6),
                "life": random.uniform(2.6, 3.6),
                "x0": self.W / 2 + random.uniform(-8, 8) - inward * 18,
                "drift": inward * random.uniform(8, 26),
                "size": random.uniform(9, 14),
                "phase": random.uniform(0, math.tau),
                "color": random.randrange(len(HEART_COLORS)),
            })
        if not self.isVisible():
            self.show()
        self._timer.start()

    def _tick(self) -> None:
        self._clock += self._timer.interval() / 1000.0
        self._particles = [p for p in self._particles if self._clock - p["born"] < p["life"]]
        if not self._particles:
            self._timer.stop()
            self._clock = 0.0
            self.hide()
            return
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 -- Qt's own naming convention
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.setPen(Qt.NoPen)
        for p in self._particles:
            age = self._clock - p["born"]
            if age < 0:
                continue
            t = age / p["life"]
            ease = 1 - (1 - t) ** 2                     # quick start, slow drift at the end
            x = p["x0"] + p["drift"] * ease + math.sin(p["phase"] + t * 7) * 5 * (1 - t)
            y = self.H - 8 - ease * (self.H - 30)
            size = p["size"] * (1 - 0.65 * t)            # shrinks as it rises
            fade_in = min(1.0, age / 0.25)
            alpha = int(215 * fade_in * (1 - t) ** 1.4)
            color = QColor(HEART_COLORS[int(p["color"])])
            halo = QRadialGradient(QPointF(x, y), size * 1.4)   # a soft, smoky glow
            glow = QColor(color)
            glow.setAlpha(alpha // 4)
            halo.setColorAt(0.0, glow)
            glow.setAlpha(0)
            halo.setColorAt(1.0, glow)
            painter.setBrush(QBrush(halo))
            painter.drawEllipse(QPointF(x, y), size * 1.4, size * 1.4)
            color.setAlpha(alpha)
            painter.setBrush(color)
            painter.save()
            painter.translate(x, y)
            painter.rotate(math.sin(p["phase"] + t * 5) * 12)
            painter.drawPath(_heart_path(size))
            painter.restore()
        painter.end()


class RoundedButton(QPushButton):
    """A pill-shaped button with hand-painted, always-transparent corners.

    Same rationale as RoundedPanel -- used for the folded/collapsed state
    of the panel, which is just this one button standing in for the whole
    window.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._bg_spec = ""
        self._border_spec = ""
        self._text_color = QColor("#ffffff")
        self._radius = 18.0
        self._icon: QPixmap | None = None

    def set_icon(self, pixmap: QPixmap) -> None:
        """Icon-only mode: just the icon, filling the button, no pill behind it."""
        self._icon = pixmap
        self.update()

    def set_style(self, bg: str, border: str, text_color: str, radius: float = 18.0) -> None:
        self._bg_spec = bg
        self._border_spec = border
        self._text_color = QColor(text_color)
        self._radius = radius
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 -- Qt's own naming convention
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self._icon is not None and not self._icon.isNull():
            side = int(min(rect.width(), rect.height()))
            icon = self._icon.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(int(rect.center().x() - icon.width() / 2),
                               int(rect.center().y() - icon.height() / 2), icon)
            painter.end()
            return
        # This button doubles as the folded state: a narrow, full-height strip
        # docked to the screen edge, not a compact pill -- so the radius is a
        # small fixed value, never proportional to the (tall) widget height.
        radius = min(self._radius, rect.width() / 2.0, rect.height() / 2.0)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        # Painted fully opaque for the same reason as RoundedPanel -- the
        # window-level Transparency slider needs real headroom above 0%.
        painter.fillPath(path, _parse_bg_brush(self._bg_spec, rect, force_alpha=255))
        painter.setPen(QPen(_parse_color(self._border_spec, force_alpha=255), 1))
        painter.drawPath(path)

        painter.setPen(self._text_color)
        painter.setFont(self.font())
        painter.drawText(rect, Qt.AlignCenter, self.text())
        painter.end()


# name -> (icon, name shown when open / on hover)
TABS = {
    "home": ("\U0001f3e0", "Home"),
    "live": ("\u26a1", "Live"),
    "suggestions": ("\U0001f465", "People"),
    "repos": ("\U0001f4e6", "Repos"),
    "market": ("\U0001f4c8", "Market"),
    "news": ("\U0001f4f0", "News"),
    "activity": ("\U0001f552", "Activity"),
    "researchers": ("\U0001f4c4", "Researchers"),
    "signals": ("\U0001f4e1", "Signals"),
    "grow": ("\U0001f331", "Grow: rising skills, protocols and your wins"),
    "chances": ("\U0001f3af", "Chances: verified jobs, funding and conferences"),
    "model": ("\U0001f9e0", "Model"),
    "badges": ("\U0001f3c5", "Badges"),
    "admin": ("\U0001f6e1", "Admin"),
    "help": ("\u2753", "Help"),
}


# Tabs that, without a GitHub account, show nothing but the "add GitHub" card (_github_card): Activity reads who
# you follow, Signals lives in your own repo. People and Repos still find your field, so they stay where they are.
NEEDS_GITHUB_TABS = ("activity", "signals")


def tab_order(names: list[str], has_github: bool) -> list[str]:
    """You (the Model tab) first; then the usual order, except that without GitHub the tabs that would only
    say "add GitHub" go to the end -- so the first ones are the ones that work. The phone orders its planets
    by the same rule (lib/sections.ts ordered)."""
    rest = [n for n in names if n != "model"]
    if not has_github:
        rest = [n for n in rest if n not in NEEDS_GITHUB_TABS] + [n for n in rest if n in NEEDS_GITHUB_TABS]
    return (["model"] if "model" in names else []) + rest


# You → Admin's sections, as planets: (part, label, emoji) -- the phone has the same (components/admin-part.tsx)
ADMIN_PARTS = [("overview", "Overview", "\U0001f4ca"), ("review", "Review", "\U0001f4e5"), ("write", "Write", "\u270d"),
               ("inbox", "Inbox", "\U0001f4a1"), ("people", "People", "\U0001f91d"), ("settings", "Settings", "\u2699")]


# ⚙ Settings' pages (the phone's Settings parts, mobile/src/components/settings-parts.tsx): label, icon, what it holds
SETTINGS_PAGES: dict[str, tuple[str, str, str]] = {
    "accounts": ("Accounts", "\U0001f517", "What myGeeKy can use. Each one is optional, and you can change it any time."),
    "profile": ("Your profile", "\U0001f464", "What shapes your feeds: your papers and a CV."),
    "look": ("Look and window", "\U0001f3a8", "The theme, and how big, how see-through and where the panel is."),
    "notify": ("Notifications", "\U0001f514", "Off unless you switch them on. Only what is really worth it."),
    "data": ("Data & privacy", "\U0001f6e1", "How myGeeKy asks the internet, sharing your setup, your privacy, and leaving."),
}
# the tour's stops in ⚙ (data/tour.json "settings:…"), and the page each lives on
SETTINGS_PAGE_OF = {"look": "look", "place": "look", "papers": "profile", "cv": "profile", "wisep": "data", "packs": "data",
                    "setup": "accounts", "sync": "accounts"}


def panel_tree(has_github: bool, is_admin: bool) -> dict[str, Any]:
    """The panel's pages under the six groups (navtree.py): a tab, or a tab and one of its parts."""
    n = navtree.node
    G = {g["id"]: g for g in navtree.GROUPS}

    def modes(tab: str, table) -> list[dict[str, Any]]:
        return [n(f"{tab}:{m}", label.split(" ", 1)[1], icon=label.split(" ", 1)[0], tab=tab, part=m) for m, label in table]

    def group(gid: str, children: list[dict[str, Any]]) -> dict[str, Any]:
        return n(gid, G[gid]["label"], G[gid]["color"], children=children)

    def grow() -> list[dict[str, Any]]:              # Data has its own level: For you and the ten fields
        from .. import datasets
        data = n("grow:data", "Data", icon="\U0001f5c2", tab="grow", part="data", children=[
            n(f"grow:data:{p}", label, icon=emoji, tab="grow", part=f"data:{p}") for p, label, emoji, _ in datasets.FIELD_PARTS])
        return [data if c["id"] == "grow:data" else c for c in modes("grow", MyGeekyPanel.GROW_MODES)]
    from .researchers_ui import PARTS as RESEARCHER_PARTS
    circle = {"live": n("live", "Live", tab="live"), "suggestions": n("suggestions", "People", tab="suggestions"),
              "researchers": n("researchers", "Researchers", icon="\U0001f4c4", tab="researchers", children=[
                  n(f"researchers:{p}", label, icon=emoji, tab="researchers", part=p) for p, label, emoji in RESEARCHER_PARTS]),
              "activity": n("activity", "Activity", tab="activity"), "signals": n("signals", "Signals", tab="signals")}
    return navtree.finish(n("home", "Home", children=[
        n("feed", "Home", "#a78bfa", tab="home"),          # 🏠 the feed (feed.py): the first page, above the groups
        group("you", [n("model:month", "My month", icon="\U0001f396", tab="model", part="month"),
                      n("model:model", "Model", icon="\U0001f9e0", tab="model", part="model"),
                      n("model:cited", "Cited by", icon="\U0001f4d1", tab="model", part="cited"),
                      n("badges", "Badges", tab="badges")] + ([n("admin", "Admin", tab="admin", children=[
                          n(f"admin:{p}", label, icon=emoji, tab="admin", part=p) for p, label, emoji in ADMIN_PARTS])]
                                                              if is_admin else [])),
        group("grow", grow()),
        group("world", [n("news", "News", tab="news", children=[
            n("news:airace", "AI race", icon="\U0001f3c1", tab="news", part="airace"),
            n("news:headlines", "Headlines", icon="\U0001f5de", tab="news", part="headlines"),
            n("news:papers", "Papers & discussions", icon="\U0001f4ac", tab="news", part="papers")]),
            n("market:research", "Research", icon="\U0001f52c", tab="market", part="research"),
            n("market:models", "AI models", icon="\U0001f917", tab="market", part="models")]),
        group("circle", [circle[k] for k in navtree.ordered(list(circle), has_github, NEEDS_GITHUB_TABS)]),
        group("repos", [n("repos", "Help out", tab="repos"), n("market:repos", "Rising", icon="\U0001f4c8", tab="market", part="repos")]),
        group("chances", modes("chances", MyGeekyPanel.CHANCE_MODES)),
        # ⚙ Settings, the last: its pages (the ⚙ panel's, Accounts first) and ❓ Help (GeeKOc's tours and the answers)
        n("settings", "Settings", "#2dd4bf", children=[
            *(n(f"settings:{key}", label, icon=icon, tab="settings", part=key) for key, (label, icon, _about) in SETTINGS_PAGES.items()),
            n("help", "Help", icon="\u2753", tab="help")]),
    ]))


class MyGeekyPanel(QWidget):
    def __init__(self, cfg: MyGeekyConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.active_tab = "home"                 # 🏠 the feed is the first page
        # freshness (what you've seen): ready before any tab renders
        self._seen_dwell: dict[str, int] = {}
        self._seen_done: set[str] = set()
        self._seen_pending: set[str] = set()
        self._fresh_dirty: set[str] = set()
        self._fresh_waiting: dict[str, Any] = {}      # background results held while you read that tab
        self._workers: list[_Worker] = []
        self.avatar_loader = AvatarLoader()
        self._last_activity_events: list[dict[str, Any]] = []
        self._expanded_actors: set[str] = set()  # kept across refreshes
        self._last_suggestions: list[dict[str, Any]] = []
        self._picker: Any = None                 # the keyword picker, while somebody is part-way through it
        self._contrib_running = False
        self._market_running = False
        self._news_running = False
        self._sugg_running = False
        self._signals_running = False
        self._activity_running = False
        self._last_incoming: list[dict[str, Any]] = []
        self._signals_data: dict[str, Any] = {}       # the last Signals data (people for the send window)

        self.setWindowTitle("myGeeKy")
        if ICON_WINDOW.exists():
            self.setWindowIcon(QIcon(str(ICON_WINDOW)))
        flags = Qt.FramelessWindowHint | Qt.Tool
        if logic.layer(cfg) == "front":
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        # macOS hides Tool windows whenever another app is active; the panel must stay at the edge
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        # Blanket transparent default for every descendant widget -- QScrollArea's
        # internal viewport in particular paints an opaque background by default
        # in Qt regardless of the top-level window's own translucency, which
        # would otherwise cover most of the panel (it hosts the Suggestions and
        # Activity tabs). #panel/the folded tab button set their own background
        # explicitly (below) and, being more specific selectors, still win.
        self.setStyleSheet("QWidget { background: transparent; }")

        self._build_ui()
        self._apply_theme()
        self._screen_name = ""          # the monitor the panel lives on, remembered across sleep/unplug
        self._dock(folded=False)
        self._watch_screens()
        # the same you on every computer: sync with your private data repo now and then
        self._syncing = False
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._sync_now)
        if logic.sync_enabled(self.cfg):
            QTimer.singleShot(4000, self._sync_now)
            self._sync_timer.start(SYNC_EVERY_MS)

        self._load_status()
        from ..achievements import log_open_today
        log_open_today()                      # a day of use, for the Regular badge
        self._badges: dict[str, Any] = {}
        # each tab fills itself from saved data; one that fails must not stop the panel from
        # opening -- it's saved as a crash report (offered a few seconds later) and the rest opens
        for load in (self._refresh_badges, self._load_github_achievements, self._load_live_stats,
                     self._load_suggestions, self._load_contributions, lambda: self._refresh_activity(force=False),
                     self._load_model_history, self._load_market, self._load_research, self._style_market_switch,
                     self._load_news, lambda: self._refresh_signals(force=False), self._load_growth,
                     self._load_chances):
            self._load_safely(load)
        self.ticker.start(int(self.cfg.gui_live_rotate_seconds * 1000))

        self._activity_timer = QTimer(self)
        self._activity_timer.timeout.connect(lambda: self._refresh_activity(force=False))
        self._activity_timer.start(60_000)

        # WISEP's evening top-up: once an hour it looks whether the day's budget has some left worth spending
        from .. import wisep
        self._wisep_timer = QTimer(self)
        self._wisep_timer.timeout.connect(lambda: self._run_async(wisep.top_up, lambda _out: None))
        self._wisep_timer.start(3_600_000)

        # every 10 minutes (and once now): search again if the list ran empty
        # and the last search is old enough -- see suggestions_auto_refresh_due
        # the board snapshots once a day; check hourly (and once now) whether it's due
        self._market_timer = QTimer(self)
        self._market_timer.timeout.connect(self._maybe_refresh_market)
        self._market_timer.start(60 * 60_000)
        QTimer.singleShot(20_000, self._maybe_refresh_market)

        # news: shown from the cache now, re-fetched in the background when it's due
        self._news_timer = QTimer(self)
        self._news_timer.timeout.connect(self._maybe_refresh_news)
        self._news_timer.start(60 * 60_000)
        QTimer.singleShot(30_000, self._maybe_refresh_news)

        # re-reads beacons only once beacon_refresh_minutes have passed
        self._signals_timer = QTimer(self)
        self._signals_timer.timeout.connect(lambda: self._refresh_signals(force=False))
        self._signals_timer.start(5 * 60_000)

        # Grow and Chances: your wins once a day, the maker's lists every few hours (each checks if it's due)
        self._growth_timer = QTimer(self)
        self._growth_timer.timeout.connect(self._maybe_refresh_growth)
        self._growth_timer.start(60 * 60_000)
        QTimer.singleShot(40_000, self._maybe_refresh_growth)

        self.hearts = HeartsOverlay()
        self._hearts_timer = QTimer(self)
        self._hearts_timer.timeout.connect(self._maybe_puff_hearts)
        self._hearts_timer.start(max(30_000, int(self.cfg.gui_hearts_interval_minutes * 60_000)))

        # a newer myGeeKy on PyPI? (PyPI is asked at most once a day; see updates.py)
        self._update_info: dict[str, Any] = {}
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._check_for_update)
        self._update_timer.start(6 * 60 * 60_000)
        QTimer.singleShot(8_000, self._check_for_update)
        self._token_warnings: list[dict[str, Any]] = []
        self._update_timer.timeout.connect(self._check_tokens)
        QTimer.singleShot(10_000, self._check_tokens)

        self._sugg_timer = QTimer(self)
        self._sugg_timer.timeout.connect(self._maybe_auto_refresh_suggestions)
        self._sugg_timer.start(10 * 60_000)
        QTimer.singleShot(5_000, self._maybe_auto_refresh_suggestions)
        self._start_seen_tracker()
        QTimer.singleShot(800, lambda: self.home_page.shown() if self.active_tab == "home" else None)
        self._tour: Any = None
        self._tour_tries = 0
        QTimer.singleShot(2500, self._maybe_tour)          # GeeKOc's tour, the first time (never under tests or CI)

    # ------------------------------------------------------------------ UI construction
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Folded tab and full panel are siblings shown one at a time (not a
        # QStackedWidget: a stack is never smaller than its LARGEST page, so the
        # "folded" window could never actually get narrow).
        self.folded_widget = RoundedButton("")
        if ICON_FOLDED.exists():
            self.folded_widget.set_icon(QPixmap(str(ICON_FOLDED)))
        self.folded_widget.setToolTip("myGeeKy — click to open")
        self.folded_widget.setCursor(Qt.PointingHandCursor)
        self.folded_widget.setMinimumSize(1, 1)
        self.folded_widget.clicked.connect(self.unfold)
        self.folded_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.folded_widget.customContextMenuRequested.connect(self._folded_menu)
        self.folded_widget.installEventFilter(self)  # hover -> fully opaque
        outer.addWidget(self.folded_widget)

        self.panel_frame = RoundedPanel()
        self.panel_frame.setObjectName("panel")
        panel_layout = QVBoxLayout(self.panel_frame)
        panel_layout.setContentsMargins(16, 14, 16, 16)
        panel_layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(6)
        if ICON_HEADER.exists():
            icon_label = QLabel()
            icon_label.setPixmap(QPixmap(str(ICON_HEADER)))
            icon_label.setFixedSize(20, 20)
            icon_label.setScaledContents(True)
            header.addWidget(icon_label)
        logo = QLabel("myGeeKy")
        logo.setStyleSheet("font-weight:700; font-size:15px; background:transparent;")
        header.addWidget(logo)
        header.addStretch(1)

        self.idea_btn = QPushButton("\U0001f4a1")
        self.idea_btn.setFixedSize(26, 26)
        self.idea_btn.setCursor(Qt.PointingHandCursor)
        self.idea_btn.setToolTip("Send an idea, a problem or a question to myGeeKy's maker")
        self.idea_btn.clicked.connect(self._open_idea_dialog)
        header.addWidget(self.idea_btn)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(26, 26)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setToolTip("Settings — theme & transparency")
        self.settings_btn.clicked.connect(self._toggle_settings)
        header.addWidget(self.settings_btn)

        self.fold_btn = QPushButton("⟩")
        self.fold_btn.setFixedSize(26, 26)
        self.fold_btn.setCursor(Qt.PointingHandCursor)
        self.fold_btn.clicked.connect(self.fold)
        header.addWidget(self.fold_btn)
        panel_layout.addLayout(header)

        self.settings_panel = self._build_settings_panel()
        self._show_settings_page("accounts", load=False)
        self.settings_panel.setVisible(False)
        panel_layout.addWidget(self.settings_panel, 1)

        self.update_banner = self._build_update_banner()
        self.update_banner.setVisible(False)
        panel_layout.addWidget(self.update_banner)

        self.token_banner = self._build_token_banner()
        self.token_banner.setVisible(False)
        panel_layout.addWidget(self.token_banner)

        self.status_label = QLabel("Loading…")
        self.status_label.setWordWrap(True)
        panel_layout.addWidget(self.status_label)
        # Nothing set up yet, or a keyword-only profile being asked (four times over three months, then
        # never again) whether it wants a real account. Hidden the rest of the time.
        self.start_holder = QWidget()
        self.start_layout = QVBoxLayout(self.start_holder)
        self.start_layout.setContentsMargins(0, 0, 0, 0)
        self.start_layout.setSpacing(6)
        self.start_holder.setVisible(False)
        panel_layout.addWidget(self.start_holder)
        self.badge_strip = QFrame()
        self.badge_strip.setCursor(Qt.PointingHandCursor)
        self.badge_strip.setToolTip("Your badges: click to see them all")
        self.badge_strip_layout = QHBoxLayout(self.badge_strip)
        self.badge_strip_layout.setContentsMargins(0, 0, 0, 0)
        self.badge_strip_layout.setSpacing(4)
        self.badge_strip.mousePressEvent = lambda ev: self._switch_tab("badges")  # noqa: ARG005
        panel_layout.addWidget(self.badge_strip)

        self.tab_buttons: dict[str, QPushButton] = {}
        self._is_admin = logic.is_admin(self.cfg)
        tabs = tab_order([name for name in TABS if name != "admin" or self._is_admin], bool(self.cfg.github_username))
        self._badges_new = False
        # The dock: six groups as planets (navtree.py). Click one and its pages take the row, with a back planet
        # first; a page with parts opens the same way. The open page's planets swell (hover any for its name).
        self.nav_tree = panel_tree(bool(self.cfg.github_username), self._is_admin)
        self.nav_buttons: dict[str, PlanetButton] = {}
        for nd in navtree.walk(self.nav_tree)[1:]:
            if nd["parent"] is self.nav_tree:
                btn = PlanetButton(nd["color"], GROUP_ICONS[nd["id"]])
            elif nd["part"] or nd["tab"] not in PLANETS:
                btn = PlanetButton(nd["color"], "", emoji=nd["icon"] or "\u2022")
            else:
                btn = PlanetButton(PLANETS[nd["tab"]][0], PLANETS[nd["tab"]][1])
            btn.setToolTip(nd["label"])
            btn.setAccessibleName(nd["label"])
            # Qt's Windows style gives every push button a ~75px minimum width;
            # five of those made the panel wider than gui_expanded_width.
            btn.setMinimumWidth(1)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=nd["id"]: self._nav_tap(i))
            self.nav_buttons[nd["id"]] = btn
            if nd["tab"] in TABS and nd["tab"] not in self.tab_buttons:   # ("settings" opens the ⚙ panel: not a tab)
                self.tab_buttons[nd["tab"]] = btn          # the planet that carries the tab's count and dots
        self.nav_back = PlanetButton("#ff6fd8", BACK_ICON, solid=True)
        self.nav_back.setMinimumWidth(1)
        self.nav_back.setCursor(Qt.PointingHandCursor)
        self.nav_back.clicked.connect(lambda: self._nav_tap("back"))
        self._nav_at = "home"
        # above the row, inside a group: a clear "‹ Back to …" and where you are
        self.nav_head = QWidget()
        nh = QHBoxLayout(self.nav_head)
        nh.setContentsMargins(2, 0, 2, 0)
        nh.setSpacing(6)
        self.nav_back_text = QPushButton("")
        self.nav_back_text.setCursor(Qt.PointingHandCursor)
        self.nav_back_text.clicked.connect(lambda: self.rail_host.up() if hasattr(self, "rail_host") else None)
        self.nav_trail = QLabel("")
        self.nav_trail.setTextFormat(Qt.PlainText)
        nh.addWidget(self.nav_back_text)
        nh.addWidget(self.nav_trail, 1)
        # on the right: GitHub, ORCID, saving to your data repo, your beacon (signs.py), lit, faint or red
        self.status_signs = StatusSigns()
        self.status_signs.clicked.connect(self._toast)
        self._sync_error = ""
        nh.addWidget(self.status_signs)
        panel_layout.addWidget(self.nav_head)
        # the planet row is no longer shown (the side rail below replaces it), but its planets still carry each
        # place's count and dot, which the rail reads
        self.tab_bar = QFrame()
        self.tab_bar.setObjectName("tabBar")
        self.nav_row = QHBoxLayout(self.tab_bar)
        self.nav_row.setContentsMargins(3, 3, 3, 3)
        self.nav_row.setSpacing(1)
        self.tab_bar.hide()
        panel_layout.addWidget(self.tab_bar)

        self.content_stack = QStackedWidget()
        # the side rail (navrail.py): folded 46px with each group's count, open 128px; over the page unless pinned
        from .navrail import RailHost
        self.rail_host = RailHost(
            self.content_stack, self.nav_tree, open_node=self._nav_open, leaf=self._nav_leaf,
            count_of=lambda nid: getattr(self.nav_buttons.get(nid), "_count", 0),
            dot_of=lambda nid: bool(getattr(self.nav_buttons.get(nid), "_dot", False)),
            icon_of=self._rail_icon, theme=lambda: THEMES[self._theme_name()],
            pinned=bool(getattr(self.cfg, "gui_rail_pinned", False)),
            on_pin=lambda on: logic.set_rail_pinned(self.cfg, on), side=logic.rail_side(self.cfg),
            on_change=self._render_up_button)
        panel_layout.addWidget(self.rail_host, 1)
        self.width_grip = WidthGrip(self.panel_frame, self._resize_width_from_grip,
                                    lambda: logic.clamp_panel_width(self.cfg.gui_expanded_width),
                                    lambda: logic.dock_side(self.cfg))
        self.height_grip = HeightGrip(self._resize_from_grip, lambda: self.cfg.gui_panel_height_fraction)
        panel_layout.addWidget(self.height_grip, 0, Qt.AlignHCenter)

        # built in this fixed order (later builders may use what earlier ones made), shown in `tabs` order
        pages = {"home": self._build_home_tab(), "live": self._build_live_tab(), "suggestions": self._build_suggestions_tab(),
                 "repos": self._build_repos_tab(), "market": self._build_market_tab(),
                 "news": self._build_news_tab(), "activity": self._build_activity_tab(),
                 "researchers": self._build_researchers_tab(),
                 "signals": self._build_signals_tab(), "grow": self._build_grow_tab(),
                 "chances": self._build_chances_tab(), "model": self._build_you_tab(),
                 "badges": self._build_badges_tab(), "help": self._build_help_tab()}
        if self._is_admin:
            pages["admin"] = self._build_admin_tab()
        self._tab_order = [name for name in tabs if name in pages]
        for name in self._tab_order:
            self.content_stack.addWidget(pages[name])
        self.content_stack.setCurrentIndex(self._tab_order.index(self.active_tab))   # opens on Home

        outer.addWidget(self.panel_frame)
        self.folded_widget.hide()

    def _build_home_tab(self) -> QWidget:
        """🏠 Home (feed_ui.py): one scrolling feed of what the other pages found, learning what you enjoy."""
        from .feed_ui import HomePage

        def go(page_id: str) -> None:
            self._nav_open(navtree.find(self.nav_tree, page_id))

        def label(page_id: str) -> str:
            nd = navtree.find(self.nav_tree, page_id) if page_id else None
            return nd["label"] if nd else ""

        def color(card: dict[str, Any]) -> str:
            nd = navtree.find(self.nav_tree, card.get("page", "")) if card.get("page") else None
            return nd["color"] if nd else THEMES[self._theme_name()]["accent"]

        self.home_page = HomePage(self.cfg, lambda: THEMES[self._theme_name()], self._run_async, logic.open_link, go,
                                  label, color, lambda: self.panel_frame.isVisible() and self.isVisible())
        return self.home_page

    def _build_help_tab(self) -> QWidget:
        """❓ Help (help_ui.py): GeeKOc's tours again, and the answers to how and why myGeeKy works."""
        from .help_ui import HelpPage

        def label(main: str) -> str:
            nd = navtree.find(self.nav_tree, "feed" if main == "home" else main)
            return nd["label"] if nd else main.capitalize()

        self.help_page = HelpPage(self.cfg, lambda: THEMES[self._theme_name()], self.start_tour, label,
                                  lambda: logic.save_config(self.cfg))
        return self.help_page

    # ------------------------------------------------------------------ GeeKOc's tour (tour.py, tour_ui.py)
    TOUR_SETTINGS = {"look": "Theme", "place": "Place on screen", "papers": "Your papers", "cv": "From a CV",
                     "wisep": "How myGeeKy asks the internet", "packs": "Packs", "setup": "Accounts", "sync": "Saving your data"}

    def _maybe_tour(self) -> None:
        """The tour opens by itself the first time, and after an update with new stops; tour.auto says never under
        tests, on CI or with MYGEEKY_NO_TOUR. Folded or hidden: try again a little later."""
        from .. import tour
        steps = tour.auto(self.cfg.tour_seen, tour.kind_for(self.cfg), "desktop")
        if not steps or self._tour is not None:
            return
        if not (self.isVisible() and self.panel_frame.isVisible()):
            self._tour_tries += 1
            if self._tour_tries < 20:
                QTimer.singleShot(30_000, self._maybe_tour)
            return
        self._run_tour(steps, marks_seen=True)

    def start_tour(self, name: str) -> None:
        """Help's buttons: "start" (the one that fits you), "settings", or a main ("grow")."""
        from .. import tour
        self._run_tour(tour.stops(name, tour.kind_for(self.cfg), "desktop"), marks_seen=name == "start")

    def _run_tour(self, steps: list[str], marks_seen: bool) -> None:
        from .. import tour
        from .tour_ui import TourOverlay
        if self._tour is not None or not steps:
            return
        self._tour_rail = (self.rail_host.state.open, self.rail_host.state.pinned)
        self._tour = TourOverlay(self.panel_frame, self.cfg, tour.kind_for(self.cfg), steps, self.tour_go,
                                 self.tour_rect, self.tour_path, lambda finished: self._tour_done(marks_seen),
                                 lambda: logic.save_config(self.cfg))

    def _tour_done(self, marks_seen: bool) -> None:
        from .. import tour
        self._tour = None
        if marks_seen:                                    # done or skipped: it doesn't come back by itself
            self.cfg.tour_seen = max(self.cfg.tour_seen, tour.version())
            logic.save_config(self.cfg)
        if self.settings_panel.isVisible():
            self._toggle_settings()
        if not self._tour_rail[1]:                        # the rail was folded before: fold it again
            self.rail_host.fold()
        if hasattr(self, "help_page"):
            self.help_page.build()                        # the language may have been picked on the way

    def _tour_widget(self, part: str) -> QWidget | None:
        heads = getattr(getattr(self, "accounts_section", None), "headings", {})
        return {"look": getattr(self, "_tour_look", None), "place": getattr(self, "place_label", None),
                "papers": getattr(self, "whois_section", None), "cv": getattr(self, "doc_section", None),
                "wisep": getattr(self, "wisep_section", None), "packs": getattr(self, "pack_section", None),
                "setup": heads.get("setup"), "sync": heads.get("sync")}.get(part)

    def tour_go(self, target: str) -> None:
        """Move the app to a stop: ⚙, a part of ⚙ (scrolled into view), or a page, with the rail dropped down to
        it so the spotlight can sit on its line."""
        if target == "settings" or target.startswith("settings:"):
            if ":" in target:
                self._show_settings_page(SETTINGS_PAGE_OF.get(target.split(":", 1)[1], "accounts"))
            if not self.settings_panel.isVisible():
                self._toggle_settings()
            w = self._tour_widget(target.split(":", 1)[1]) if ":" in target else None
            if w is not None:                             # up or down only: ⚙ never scrolls sideways
                box = self.settings_scroll
                box.horizontalScrollBar().setValue(0)
                box.verticalScrollBar().setValue(max(0, w.mapTo(box.widget(), QPoint(0, 0)).y() - 60))
            return
        nd = navtree.find(self.nav_tree, target)
        if nd is None:
            return
        self._nav_open(navtree.first_leaf(nd))
        host, trail = self.rail_host, navtree.path(nd)
        if len(trail) <= 2:                               # Home or Help: the rail open on the groups
            host.state.open, host.state.open_group, host.state.open_page = True, None, None
            host.apply()
        else:
            host.open_at(trail[1]["id"])
            if nd["children"]:
                host.state.open_page = nd["id"]
                host.apply()

    def tour_rect(self, target: str) -> QRect | None:
        """Where the spotlight goes, in the panel's coordinates: the page's line in the rail, ⚙, or a part of ⚙."""
        from .navrail import RailRow
        frame = self.panel_frame

        def box(w: QWidget, pad: int = 3) -> QRect:
            return QRect(w.mapTo(frame, QPoint(0, 0)), w.size()).adjusted(-pad, -pad, pad, pad)
        if target == "settings":
            return box(self.settings_btn)
        if target.startswith("settings:"):
            w = self._tour_widget(target.split(":", 1)[1])
            if w is None or not w.isVisible():
                return None
            view = self.settings_scroll.viewport()
            area = QRect(view.mapTo(frame, QPoint(0, 0)), view.size())
            r = box(w)
            if isinstance(w, QLabel):                     # a heading: the band of settings under it
                r = QRect(area.left() + 2, r.top(), area.width() - 4, max(r.height() + 34, 44))
            r = r.intersected(area)
            return None if r.isEmpty() else r
        row = next((r for r in frame.findChildren(RailRow) if r.nd["id"] == target and r.isVisible()), None)
        return box(row, 2) if row is not None else None

    def tour_path(self, target: str) -> str:
        if target == "settings":
            return "⚙ Settings"
        if target.startswith("settings:"):
            return "⚙ Settings → " + self.TOUR_SETTINGS.get(target.split(":", 1)[1], "")
        nd = navtree.find(self.nav_tree, target)
        return " → ".join(n["label"] for n in navtree.path(nd)[1:]) if nd else ""

    def _build_researchers_tab(self) -> QWidget:
        """Circle → 📄 Researchers (researchers_ui.py): new work from the people you follow, following, suggestions."""
        from .researchers_ui import ResearchersPage
        self.researchers_page = ResearchersPage(lambda: THEMES[self._theme_name()], self._run_async, logic.open_link,
                                                lambda: logic.researcher_suggestions(self.cfg), lambda: logic.my_author(self.cfg),
                                                lambda: logic.lights_weights(self.cfg))
        return self.researchers_page

    def _build_live_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        self.stat_friends_label = QLabel("—")
        self.stat_new_label = QLabel("—")
        self.stat_rate_label = QLabel("—")
        for lbl in (self.stat_friends_label, self.stat_new_label, self.stat_rate_label):
            lbl.setStyleSheet("font-size:11px; font-weight:600; background:transparent;")
            stats_row.addWidget(lbl)
        stats_row.addStretch(1)
        layout.addLayout(stats_row)

        self.ticker = SpotlightTicker(self._on_ticker_clicked, self.avatar_loader)
        layout.addWidget(self.ticker, 1)

        hint = QLabel("Recent activity and top suggestions, scrolling live — click a card to open the profile.")
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size:10px; background:transparent;")
        layout.addWidget(hint)
        return page

    def _build_suggestions_tab(self) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)

        actions_row = QHBoxLayout()
        hint = QLabel("Click someone to see their card; follow them on GitHub from there (you always follow by hand).")
        hint.setWordWrap(True)
        self.refresh_sugg_btn = QPushButton("Refresh")
        self.refresh_sugg_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_sugg_btn.clicked.connect(self._on_refresh_suggestions)
        actions_row.addWidget(hint, 1)
        actions_row.addWidget(self.refresh_sugg_btn)
        layout.addLayout(actions_row)

        fb_header = QLabel("LIKELY TO FOLLOW BACK")
        fb_header.setStyleSheet("font-size:10.5px; font-weight:700; letter-spacing:0.5px; background:transparent;")
        layout.addWidget(fb_header)
        followback_container = QWidget()
        self.followback_area = QVBoxLayout(followback_container)
        self.followback_area.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(followback_container)

        dm_header = QLabel("DOMAIN-FIT HIGHLIGHTS")
        dm_header.setStyleSheet(
            "font-size:10.5px; font-weight:700; letter-spacing:0.5px; margin-top:8px; background:transparent;"
        )
        layout.addWidget(dm_header)
        domain_container = QWidget()
        self.domain_area = QVBoxLayout(domain_container)
        self.domain_area.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(domain_container)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        # QScrollArea's viewport paints an opaque background by default in
        # Qt, independent of the top-level window's translucency or any
        # stylesheet on the QScrollArea widget itself -- this is what was
        # actually covering most of the panel.
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setStyleSheet("background: transparent;")
        page.setAutoFillBackground(False)
        return scroll

    def _build_repos_tab(self) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)

        actions_row = QHBoxLayout()
        hint = QLabel("Repos you could improve — fork and send the PR yourself.")
        hint.setWordWrap(True)
        self.refresh_repos_btn = QPushButton("Refresh")
        self.refresh_repos_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_repos_btn.clicked.connect(self._on_refresh_contributions)
        actions_row.addWidget(hint, 1)
        actions_row.addWidget(self.refresh_repos_btn)
        layout.addLayout(actions_row)

        repos_container = QWidget()
        self.repos_area = QVBoxLayout(repos_container)
        self.repos_area.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(repos_container)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        # Same opaque-viewport workaround as the Suggestions tab.
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setStyleSheet("background: transparent;")
        page.setAutoFillBackground(False)
        return scroll

    def _build_market_tab(self) -> QWidget:
        """Your field's pulse, two ways: repos ranked by momentum, and research
        trends (rising papers, tools with papers, people behind them)."""
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 4, 0, 0)
        outer.setSpacing(6)
        switch = QHBoxLayout()
        switch.setSpacing(4)
        self.market_mode_buttons: dict[str, QPushButton] = {}
        for mode, label in (("repos", "Repos"), ("research", "Research"), ("models", "\U0001f917 Models")):
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, m=mode: self._set_market_mode(m))
            self.market_mode_buttons[mode] = b
            b.setVisible(False)                  # Rising lives under Repos, Research and AI models under World
            switch.addWidget(b)
        switch.addStretch(1)
        outer.addLayout(switch)
        self.market_stack = QStackedWidget()
        self.market_stack.addWidget(self._build_market_repos())
        self.market_stack.addWidget(self._build_research_view())
        self.market_stack.addWidget(self._build_models_view())
        outer.addWidget(self.market_stack, 1)
        self._market_mode = "repos"
        return container

    def _set_market_mode(self, mode: str) -> None:
        self._market_mode = mode
        self.market_stack.setCurrentIndex({"repos": 0, "research": 1, "models": 2}[mode])
        self._style_market_switch()
        self._nav_mark()
        if mode == "research" and logic.trends_due(self.cfg):
            self._refresh_research(force=False)
        if mode == "models":
            self._render_models(logic.get_hf_models(self.cfg))
            if logic.hf_models_due(self.cfg):
                self._refresh_models(force=False)

    def _style_market_switch(self) -> None:
        theme = THEMES[self._theme_name()]
        for mode, b in self.market_mode_buttons.items():
            active = mode == getattr(self, "_market_mode", "repos")
            b.setStyleSheet(f"QPushButton {{ background:{theme['tab_active'] if active else theme['card_bg']}; "
                            f"color:{theme['text']}; border:none; border-radius:8px; padding:4px 12px; "
                            f"font-size:11px; font-weight:{'700' if active else '400'}; }}")

    # ------------------------------------------------------------------ Hugging Face models
    def _build_models_view(self) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 4, 0)
        actions = QHBoxLayout()
        self.models_updated_label = QLabel("")
        self.refresh_models_btn = QPushButton("Refresh")
        self.refresh_models_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_models_btn.clicked.connect(lambda: self._refresh_models(force=True))
        actions.addWidget(self.models_updated_label, 1)
        actions.addWidget(self.refresh_models_btn)
        layout.addLayout(actions)
        self.models_hint = QLabel("Models trending on Hugging Face: first the ones in your field (from your "
                                  "interests), then the big picture. Click one to open it.")
        self.models_hint.setWordWrap(True)
        layout.addWidget(self.models_hint)
        box = QWidget()
        self.models_area = QVBoxLayout(box)
        self.models_area.setContentsMargins(0, 0, 0, 0)
        self.models_area.setSpacing(5)
        layout.addWidget(box)
        layout.addStretch(1)
        self._models_running = False
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        scroll.viewport().setAutoFillBackground(False)
        page.setAutoFillBackground(False)
        return scroll

    def _refresh_models(self, force: bool) -> None:
        if self._models_running:
            return
        self._models_running = True
        self.refresh_models_btn.setEnabled(False)
        self.models_updated_label.setText("updating\u2026")
        self._run_async(lambda: logic.refresh_hf_models(self.cfg, force=force), self._on_models_ready)

    def _on_models_ready(self, data: Any) -> None:
        self._models_running = False
        self.refresh_models_btn.setEnabled(True)
        self._render_models(data if isinstance(data, dict) else {})

    def _render_models(self, data: dict[str, Any]) -> None:
        theme = THEMES[self._theme_name()]
        _clear_layout(self.models_area)
        muted = f"color:{theme['muted']}; font-size:10.5px; background:transparent;"
        for lbl in (self.models_hint, self.models_updated_label):
            lbl.setStyleSheet(muted)
        self.refresh_models_btn.setStyleSheet(
            f"QPushButton {{ background:{theme['section_btn']}; color:{theme['text']}; border:none; "
            f"border-radius:8px; padding:6px 10px; font-size:11.5px; }}")
        if not self._models_running:
            updated = data.get("updated_at")
            self.models_updated_label.setText(data.get("error") or ("updated " + _time_ago(updated) if updated else ""))
        field, trending = data.get("field") or [], data.get("trending") or []
        if not field and not trending:
            msg = QLabel("No models yet. They load in the background (or click Refresh).")
            msg.setStyleSheet(muted)
            self.models_area.addWidget(msg)
            return
        tags = ", ".join(data.get("tags") or [])
        for label, group in (("IN YOUR FIELD" + (f" · {tags}" if tags else ""), field),
                             ("\U0001f30d TRENDING EVERYWHERE", trending)):
            if not group:
                continue
            head = QLabel(label)
            head.setWordWrap(True)
            head.setStyleSheet(f"color:{theme['text']}; font-size:10px; font-weight:700; letter-spacing:0.5px; "
                               "margin-top:6px; background:transparent;")
            self.models_area.addWidget(head)
            for m in _with_seen_earlier(freshness.arrange(self.cfg, "model", group, keep_seen=True)):
                self.models_area.addWidget(_mark_fresh(ModelRow(m, theme, self._opener("model", m)), m, theme))

    def _build_research_view(self) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 4, 0)
        actions_row = QHBoxLayout()
        self.research_updated_label = QLabel("")
        self.refresh_research_btn = QPushButton("Refresh")
        self.refresh_research_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_research_btn.clicked.connect(lambda: self._refresh_research(force=True))
        actions_row.addWidget(self.research_updated_label, 1)
        actions_row.addWidget(self.refresh_research_btn)
        layout.addLayout(actions_row)
        self.research_hint = QLabel("")
        self.research_hint.setWordWrap(True)
        layout.addWidget(self.research_hint)
        container = QWidget()
        self.research_area = QVBoxLayout(container)
        self.research_area.setContentsMargins(0, 0, 0, 0)
        self.research_area.setSpacing(6)
        layout.addWidget(container)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        scroll.viewport().setAutoFillBackground(False)
        page.setAutoFillBackground(False)
        return scroll

    def _build_market_repos(self) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 4, 0)

        actions_row = QHBoxLayout()
        self.market_updated_label = QLabel("")
        self.refresh_market_btn = QPushButton("Refresh")
        self.refresh_market_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_market_btn.clicked.connect(lambda: self._refresh_market(force=True))
        actions_row.addWidget(self.market_updated_label, 1)
        actions_row.addWidget(self.refresh_market_btn)
        layout.addLayout(actions_row)
        self.market_hint = QLabel("The popular, active repos in your field, ranked by momentum: stars gained, "
                                  "commits and PyPI downloads. ▲▼ = places moved since the last day ranked.")
        self.market_hint.setWordWrap(True)
        layout.addWidget(self.market_hint)

        market_container = QWidget()
        self.market_area = QVBoxLayout(market_container)
        self.market_area.setContentsMargins(0, 0, 0, 0)
        self.market_area.setSpacing(6)
        layout.addWidget(market_container)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        scroll.viewport().setAutoFillBackground(False)
        page.setAutoFillBackground(False)
        return scroll

    def _build_news_tab(self) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 4, 0)
        actions_row = QHBoxLayout()
        self.news_updated_label = QLabel("")
        self.refresh_news_btn = QPushButton("Refresh")
        self.refresh_news_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_news_btn.clicked.connect(lambda: self._refresh_news(force=True))
        actions_row.addWidget(self.news_updated_label, 1)
        actions_row.addWidget(self.refresh_news_btn)
        layout.addLayout(actions_row)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(4)
        self.news_mode_buttons: dict[str, QPushButton] = {}
        for mode, label in (("airace", "\U0001f3c1 AI race"), ("headlines", "Headlines"), ("papers", "Papers && discussions")):
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, m=mode: self._set_news_mode(m))
            self.news_mode_buttons[mode] = b
            b.setVisible(False)                  # the dock's planet row chooses the part now (navtree.py)
            mode_row.addWidget(b)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)
        self.news_hint = QLabel("")
        self.news_hint.setWordWrap(True)
        self.news_hint.setTextFormat(Qt.RichText)
        layout.addWidget(self.news_hint)
        # 🏁 the AI race (airace.py): the first part of News
        from .airace_ui import AiRacePage
        self.airace_page = AiRacePage(lambda: THEMES[self._theme_name()], self._load_ai_race)
        layout.addWidget(self.airace_page)
        headlines_box = QWidget()
        self.headlines_area = QVBoxLayout(headlines_box)
        self.headlines_area.setContentsMargins(0, 0, 0, 0)
        self.headlines_area.setSpacing(1)
        layout.addWidget(headlines_box)
        self.headlines_box = headlines_box
        container = QWidget()
        self.news_area = QVBoxLayout(container)
        self.news_area.setContentsMargins(0, 0, 0, 0)
        self.news_area.setSpacing(6)
        layout.addWidget(container)
        self.news_box = container
        self._news_mode = "airace"
        QTimer.singleShot(0, lambda: self._set_news_mode("airace"))
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        scroll.viewport().setAutoFillBackground(False)
        page.setAutoFillBackground(False)
        return scroll

    def _build_activity_tab(self) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)

        actions_row = QHBoxLayout()
        self.activity_updated_label = QLabel("")
        self.refresh_act_btn = QPushButton("Refresh")
        self.refresh_act_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_act_btn.clicked.connect(lambda: self._refresh_activity(force=True))
        actions_row.addWidget(self.activity_updated_label, 1)
        actions_row.addWidget(self.refresh_act_btn)
        layout.addLayout(actions_row)

        activity_container = QWidget()
        self.activity_area = QVBoxLayout(activity_container)
        self.activity_area.setContentsMargins(0, 0, 0, 0)
        self.activity_area.setSpacing(6)
        layout.addWidget(activity_container)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        # QScrollArea's viewport paints an opaque background by default in
        # Qt, independent of the top-level window's translucency or any
        # stylesheet on the QScrollArea widget itself -- this is what was
        # actually covering most of the panel.
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setStyleSheet("background: transparent;")
        page.setAutoFillBackground(False)
        return scroll

    def _build_signals_tab(self) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)

        actions_row = QHBoxLayout()
        self.signals_updated_label = QLabel("")
        self.refresh_signals_btn = QPushButton("Refresh")
        self.refresh_signals_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_signals_btn.clicked.connect(lambda: self._refresh_signals(force=True))
        actions_row.addWidget(self.signals_updated_label, 1)
        actions_row.addWidget(self.refresh_signals_btn)
        layout.addLayout(actions_row)
        self.signals_hint = QLabel("")
        self.signals_hint.setWordWrap(True)
        layout.addWidget(self.signals_hint)
        self.signals_quiet = QCheckBox("🔕 Not taking signals right now")
        self.signals_quiet.setToolTip("Others can't send you signals while this is on. Nobody is told why, "
                                      "and anything already sent waits for you.")
        self.signals_quiet.setChecked(self.cfg.beacon_quiet)
        self.signals_quiet.toggled.connect(self._on_quiet_toggled)
        layout.addWidget(self.signals_quiet)

        signals_container = QWidget()
        self.signals_area = QVBoxLayout(signals_container)
        self.signals_area.setContentsMargins(0, 0, 0, 0)
        self.signals_area.setSpacing(6)
        layout.addWidget(signals_container)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        # Same opaque-viewport workaround as the Suggestions tab.
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setStyleSheet("background: transparent;")
        page.setAutoFillBackground(False)
        return scroll

    # ------------------------------------------------------------------ 🌱 Grow and 🎯 Chances
    # Highlights last until there are many; 🤝 Collaborators (still drawn by "collab") hidden while few use Signals
    GROW_MODES = (("skills", "📈 Skills"), ("paths", "🧭 Protocols"), ("quiz", "🏆 Quiz"), ("learn", "📚 Learn"),
                  ("data", "🗂️ Data"), ("wins", "🎉 Wins"), ("highlights", "✨ Highlights"))
    CHANCE_MODES = (("seasons", "🗓 Seasons"), ("jobs", "💼 Jobs"), ("funding", "💶 Funding"),
                    ("conferences", "🎤 Conferences"))

    def _scroll_page(self, build: Callable[[QVBoxLayout], None]) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 4, 0)
        build(layout)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setStyleSheet("background: transparent;")
        page.setAutoFillBackground(False)
        return scroll

    def _mode_row(self, layout: QVBoxLayout, modes, on_pick: Callable[[str], None]) -> dict[str, QPushButton]:
        """One row of sections: each is its icon, and the one you are in also says its name.

        The panel is 380px wide. Six sections written out as pills wrapped onto three lines and ate about
        96px of a height there is never enough of; as icons they sit in one row of about 36px. The open one
        keeps its words, so nobody has to decode a small picture to know where they are, and every section
        stays one press away -- which is what a drop box would have taken in exchange for the same space.

        The label is split on its first space, so the sections stay written as "🗓 Seasons" in one place."""
        holder = QWidget()
        holder.setObjectName("modeRow")
        row = QHBoxLayout(holder)
        row.setContentsMargins(3, 3, 3, 3)
        row.setSpacing(3)
        buttons: dict[str, QPushButton] = {}
        for mode, label in modes:
            icon, _, name = str(label).partition(" ")
            b = QPushButton()
            b.setProperty("icon_only", icon)
            b.setProperty("full_name", name or icon)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(name or icon)              # the icon alone must still be able to say what it is
            b.setAccessibleName(name or icon)
            b.setMinimumHeight(30)
            b.clicked.connect(lambda checked=False, m=mode: on_pick(m))
            buttons[mode] = b
            row.addWidget(b)
        layout.addWidget(holder)
        holder.setVisible(False)          # the dock's planet row chooses the part now (navtree.py); kept for the code
        return buttons

    def _build_grow_tab(self) -> QScrollArea:
        self._grow_mode = "skills"
        self._growth: dict[str, Any] = {}
        self._collabs: dict[str, Any] = {}
        self._growth_running = False
        self._editing_protocol = ""
        self._building_protocol = False
        self._protocol_built: tuple[str, bool] | None = None   # (id, reviewed) of the one just built: says so once
        self._all_reviewed = False        # reviewed protocols: the few that fit you best, or all of them
        self._protocol_toasted = ""       # the built protocol already announced by the floating message
        self._open_protocol = ""          # the one protocol shown open; the others fold to one line
        self._open_step: dict[str, str] = {}
        # a quiz being taken, drawn inside the 🏆 Quiz tab (never a pop-up): the drawn questions, which one
        # you're on, your answers, and the attempt once it's marked
        self._quiz_run: dict[str, Any] | None = None

        def build(layout: QVBoxLayout) -> None:
            actions = QHBoxLayout()
            self.grow_updated_label = QLabel("")
            self.refresh_grow_btn = QPushButton("Refresh")
            self.refresh_grow_btn.setCursor(Qt.PointingHandCursor)
            self.refresh_grow_btn.clicked.connect(lambda: self._refresh_growth(force=True))
            actions.addWidget(self.grow_updated_label, 1)
            actions.addWidget(self.refresh_grow_btn)
            layout.addLayout(actions)
            self.grow_mode_buttons = self._mode_row(layout, self.GROW_MODES, self._set_grow_mode)
            self.grow_hint = QLabel("")
            self.grow_hint.setWordWrap(True)
            layout.addWidget(self.grow_hint)
            box = QWidget()
            self.grow_area = QVBoxLayout(box)
            self.grow_area.setContentsMargins(0, 0, 0, 0)
            self.grow_area.setSpacing(6)
            layout.addWidget(box)
        scroll = self._scroll_page(build)
        # Wrapped text is measured for the width it's drawn at. Cards drawn before the panel has its real
        # width (at start, or while Grow is hidden) would keep the wrong heights, so draw again whenever
        # the width they're shown at changes.
        self._grow_scroll = scroll
        self._grow_drawn_width = -1
        self._grow_refit = QTimer(self)
        self._grow_refit.setSingleShot(True)
        self._grow_refit.setInterval(120)
        self._grow_refit.timeout.connect(self._refit_grow)
        scroll.viewport().installEventFilter(self)
        return scroll

    def _refit_grow(self) -> None:
        width = self._grow_scroll.viewport().width()
        if self._grow_scroll.isVisible() and abs(width - self._grow_drawn_width) > 4:
            self._render_grow()

    def _build_chances_tab(self) -> QScrollArea:
        # 🗓 Seasons sits first in the row, but Chances still opens on Jobs: until more seasons have a
        # sentence found on their own page, landing there would show two cards and look empty.
        self._chance_mode = "jobs"
        self._chances: dict[str, Any] = {}
        self._seasons: dict[str, Any] = {}
        self._season_window = 0
        self._country = ""              # "" means anywhere

        def build(layout: QVBoxLayout) -> None:
            actions = QHBoxLayout()
            self.chances_updated_label = QLabel("")
            self.refresh_chances_btn = QPushButton("Refresh")
            self.refresh_chances_btn.setCursor(Qt.PointingHandCursor)
            self.refresh_chances_btn.clicked.connect(lambda: self._refresh_chances(force=True))
            actions.addWidget(self.chances_updated_label, 1)
            actions.addWidget(self.refresh_chances_btn)
            layout.addLayout(actions)
            # Where in the world, ABOVE the four kinds, because it holds across all of them: choose
            # Germany and it stays chosen through jobs, funding, conferences and seasons alike. Its
            # choices are built from every list at once for the same reason -- a filter that applies to
            # everything must not change its options as you move between tabs.
            self.country_picker = QComboBox()
            self.country_picker.setCursor(Qt.PointingHandCursor)
            self.country_picker.currentIndexChanged.connect(self._on_country_pick)
            self.country_picker.setVisible(False)
            layout.addWidget(self.country_picker)
            self.chance_mode_buttons = self._mode_row(layout, self.CHANCE_MODES, self._set_chance_mode)
            # the drop box of periods: shown only for 🗓 Seasons, and starts on the one we are in
            self.season_picker = QComboBox()
            self.season_picker.setCursor(Qt.PointingHandCursor)
            self.season_picker.currentIndexChanged.connect(self._on_season_window)
            self.season_picker.setVisible(False)
            layout.addWidget(self.season_picker)
            self.chances_hint = QLabel("")
            self.chances_hint.setWordWrap(True)
            layout.addWidget(self.chances_hint)
            box = QWidget()
            self.chances_area = QVBoxLayout(box)
            self.chances_area.setContentsMargins(0, 0, 0, 0)
            self.chances_area.setSpacing(6)
            layout.addWidget(box)
        return self._scroll_page(build)

    def _style_mode_row(self, buttons: dict[str, QPushButton], open_mode: str,
                        theme: dict[str, Any]) -> None:
        """The open section says its name and takes the room for it; the rest share what is left.

        Done here rather than at build time because it has to be redone every time the section changes,
        and again when the theme does."""
        from .growth_ui import segment_style, segment_track
        for mode, b in buttons.items():
            open_now = mode == open_mode
            icon = b.property("icon_only") or ""
            name = b.property("full_name") or ""
            b.setText(f"{icon}  {name}" if open_now else icon)
            b.setSizePolicy(QSizePolicy.Preferred if open_now else QSizePolicy.Expanding,
                            QSizePolicy.Fixed)
            b.setStyleSheet(segment_style(theme, open_now))
        if buttons:
            holder = next(iter(buttons.values())).parentWidget()
            if holder is not None:
                holder.setStyleSheet(segment_track(theme))

    def _style_grow_switches(self) -> None:
        theme = THEMES[self._theme_name()]
        self._style_mode_row(getattr(self, "grow_mode_buttons", {}), self._grow_mode, theme)
        self._style_mode_row(getattr(self, "chance_mode_buttons", {}), self._chance_mode, theme)
        btn = (f"QPushButton {{ background:{theme['section_btn']}; color:{theme['text']}; border:none; "
               f"border-radius:8px; padding:6px 10px; font-size:11.5px; }}")
        muted = f"color:{theme['muted']}; font-size:10.5px; background:transparent;"
        for w in ("refresh_grow_btn", "refresh_chances_btn"):
            if hasattr(self, w):
                getattr(self, w).setStyleSheet(btn)
        for w in ("grow_updated_label", "grow_hint", "chances_updated_label", "chances_hint"):
            if hasattr(self, w):
                getattr(self, w).setStyleSheet(muted)

    # ---- loading
    def _load_growth(self) -> None:
        if self._growth_running:
            return
        self._growth_running = True
        self.grow_updated_label.setText("reading your field…")
        self._run_async(lambda: logic.get_growth(self.cfg), self._on_growth_ready)

    def _refresh_growth(self, force: bool) -> None:
        if self._growth_running:
            return
        self._growth_running = True
        self.refresh_grow_btn.setEnabled(False)
        self.grow_updated_label.setText("updating…")
        self._run_async(lambda: logic.refresh_growth(self.cfg, force=force), self._on_growth_ready)
        if self._grow_mode == "collab":
            self._load_collaborators(force=True)

    def _maybe_refresh_growth(self) -> None:
        if logic.growth_due(self.cfg):
            self._refresh_growth(force=False)
        self._refresh_chances(force=False)       # fetches the maker's lists only when they're due

    def _on_growth_ready(self, data: Any) -> None:
        self._growth_running = False
        self.refresh_grow_btn.setEnabled(True)
        self._growth = data if isinstance(data, dict) else {}
        self._render_grow()

    COLLABS_FRESH_S = 300

    def _load_collaborators(self, force: bool = False) -> None:
        """Fellow users who complement you. The last list shows straight away; it's worked out again only
        when it's older than a few minutes, or when asked (Refresh, a 👎, Show them again)."""
        fresh = time.monotonic() - getattr(self, "_collabs_at", -1e9) < self.COLLABS_FRESH_S
        if getattr(self, "_collabs_running", False) or (self._collabs and fresh and not force):
            return
        self._collabs_running = True
        rising = (self._growth or {}).get("rising")
        self._run_async(lambda: logic.get_collaborators(self.cfg, rising), self._on_collaborators_ready)

    def _on_collaborators_ready(self, data: Any) -> None:
        self._collabs_running = False
        self._collabs_at = time.monotonic()
        self._collabs = data if isinstance(data, dict) else {}
        if self._grow_mode == "collab":
            self._render_grow()

    def _load_chances(self) -> None:
        self._run_async(lambda: logic.get_opportunities(self.cfg), self._on_chances_ready)

    def _refresh_chances(self, force: bool) -> None:
        if getattr(self, "_chances_running", False):
            return
        self._chances_running = True
        self.refresh_chances_btn.setEnabled(False)
        if force:
            self.chances_updated_label.setText("updating…")
        self._run_async(lambda: logic.refresh_opportunities(self.cfg, force=force), self._on_chances_ready)

    def _on_chances_ready(self, data: Any) -> None:
        self._chances_running = False
        self.refresh_chances_btn.setEnabled(True)
        self._chances = data if isinstance(data, dict) else {}
        self._render_chances()

    def _render_highlights(self, theme: dict[str, Any]) -> None:
        from .highlights_ui import HighlightCard
        self.grow_hint.setText("Research articles picked by the maker, each retold as a short news article in plain "
                               "words: what they found, who did it, what they did and with which tools. Tap one to "
                               "read it in your language.")
        items = logic.get_highlights()
        if not items:
            self._grow_note("No Highlights yet. They arrive with the lists, a few a week.", theme)
        for it in items:
            self.grow_area.addWidget(HighlightCard(it, theme, self._open_highlight))

    def _open_highlight(self, item: dict[str, Any], warnings: list[str] | None = None) -> None:
        from .highlights_ui import HighlightDialog
        if warnings is None:
            logic.read_highlight(item)
        HighlightDialog(item, THEMES[self._theme_name()], logic.open_link,
                        on_learn=None if warnings is not None else self._on_start_path, parent=self,
                        warnings=warnings).exec()

    def _set_grow_mode(self, mode: str) -> None:
        self._grow_mode = "data:for-you" if mode == "data" else mode     # Data opens on For you
        if mode == "collab":
            self._load_collaborators()
        self._render_grow()
        self._nav_mark()

    def _set_chance_mode(self, mode: str) -> None:
        self._chance_mode = mode
        self._render_chances()
        self._nav_mark()

    # ---- drawing
    def _grow_note(self, text: str, theme: dict[str, Any]) -> None:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.PlainText)
        lbl.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
        self.grow_area.addWidget(lbl)

    def _grow_header(self, text: str, theme: dict[str, Any], area=None) -> None:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size:10.5px; font-weight:700; letter-spacing:0.5px; margin-top:6px; "
                          f"color:{theme['text']}; background:transparent;")
        (area or self.grow_area).addWidget(lbl)

    def _render_grow(self) -> None:
        from .growth_ui import ResourceRow, SkillCard, WinRow
        theme = THEMES[self._theme_name()]
        self._style_grow_switches()
        _clear_layout(self.grow_area)
        self._grow_drawn_width = self._grow_scroll.viewport().width() if self._grow_scroll.isVisible() else -1
        data = self._growth
        if not self._growth_running:
            err = data.get("error") or ""
            updated = (data.get("rising") or {}).get("updated_at")
            self.grow_updated_label.setText(err or ("updated " + _time_ago(updated) if updated else ""))
        mode = self._grow_mode
        open_ = logic.open_link
        if mode == "highlights":
            self._render_highlights(theme)
        elif mode == "skills":
            self.grow_hint.setText("Skills growing in your field that your profile doesn't show yet, from the "
                                   "papers, repos, models and people myGeeKy follows for you. 👍 / 👎 teach it "
                                   "what to suggest; 🧭 turns a skill into steps.")
            rising = data.get("rising") or {}
            started = {p["skill"] for p in data.get("paths") or []}
            from .geek_loader import GeekLoader, Hold
            hold = self.__dict__.setdefault("_grow_hold", Hold())
            if not data:
                hold.shown()
                self.grow_area.addWidget(GeekLoader("Reading your field…", theme["muted"]))
                return
            if wait := hold.wait():                    # he only just appeared: let him be seen first
                self.grow_area.addWidget(GeekLoader("Reading your field…", theme["muted"]))
                QTimer.singleShot(wait, self._render_grow)
                return
            if rising.get("skills") or rising.get("directions"):
                from .. import skills as skills_mod
                from .skillviews_ui import SkillViews
                self.grow_area.addWidget(SkillViews(skills_mod.shapes(rising), theme, self._on_start_path, started))
                self._grow_header("ALL SUGGESTIONS", theme)
            if not rising.get("skills"):
                self._grow_note("No rising skills yet. They come from what myGeeKy has read about your field: "
                                "open News and Market (Research, Repos, Models) once, then Refresh.", theme)
            for s in rising.get("skills") or []:
                self.grow_area.addWidget(SkillCard(
                    s, theme, self._voter("skill", s["name"], s["name"], [s["name"]], rerender=True),
                    self._on_start_path, open_, s["name"] in started))
            if rising.get("hidden"):
                self._hidden_note(self.grow_area, rising["hidden"], "skill", theme)
            if rising.get("strengths"):
                self._grow_header("💪 YOUR STRENGTHS THAT ARE RISING TOO", theme)
                for s in rising["strengths"][:5]:
                    self.grow_area.addWidget(SkillCard(s, theme, lambda up: 0, self._on_start_path, open_,
                                                       True, strength=True))
        elif mode == "paths":
            self._render_protocols(data, theme)
        elif mode == "quiz":
            self._render_quizzes(theme)
        elif mode == "learn":
            self.grow_hint.setText("Free courses, books, tutorials and repos picked by myGeeKy's maker, matched "
                                   "to your work and the skills rising in your field. 👍 / 👎 teach it what helps you.")
            res = data.get("resources") or {}
            for r in (res.get("items") or [])[:30]:
                self.grow_area.addWidget(ResourceRow(r, theme, self._voter("resource", r["id"], r["title"],
                                                                           r.get("skills", []) + r.get("keywords", [])),
                                                     open_))
            if not res.get("items"):
                self._grow_note("No learning resources yet.", theme)
            if res.get("hidden"):
                self._hidden_note(self.grow_area, res["hidden"], "resource", theme)
        elif mode.startswith("data"):
            self.grow_hint.setText("Public datasets to practise and train on, across the sciences: open, documented, "
                                   "laptop-sized and downloadable without a login. Yours first: your field and the "
                                   "skills rising for you. 👍 / 👎 teach it what helps.")
            from .. import datasets
            from .datasets_ui import DatasetsSection
            d = data.get("datasets") or {}
            self.grow_area.addWidget(DatasetsSection(
                d.get("items") or [], d.get("weights") or {}, d.get("wanted") or [], theme,
                lambda ds, up: logic.vote("dataset", ds["id"], up, ds["title"], ds["skills"]), open_,
                datasets.field_for_part(mode), d.get("radar")))
        elif mode == "wins":
            self.grow_hint.setText("New stars and forks on your repos, and new citations of your papers "
                                   "(with the newest paper citing you). Checked once a day.")
            wins = data.get("wins") or []
            if data.get("wins_updated_at") and not self._growth_running:
                self.grow_updated_label.setText("checked " + _time_ago(data["wins_updated_at"]))
            if not wins:
                need = [] if data.get("has_github") else ["GitHub (for stars and forks)"]
                if not data.get("has_orcid"):
                    need.append("your ORCID (for citations)")
                self._grow_note("No wins in the last 30 days yet. The first check only sets the starting point; "
                                "from then on, every new star, fork and citation shows up here."
                                + (" Add " + " and ".join(need) + " in setup to see them." if need else ""), theme)
            for w in wins:
                self.grow_area.addWidget(WinRow(w, theme, open_, _time_ago(w.get("at", ""))))
        elif mode == "collab":
            self.grow_hint.setText("Fellow myGeeKy users whose skills complement yours: they bring what you "
                                   "don't, you bring what they don't. 🤝 is sealed: they only see it if they "
                                   "pick you too.")
            self._render_collaborators(theme)

    def _render_collaborators(self, theme: dict[str, Any]) -> None:
        from .growth_ui import CollaboratorCard
        if self._github_card(self.grow_area, "signals"):
            return
        data = self._collabs
        if not data:
            self._grow_note("Looking for people who complement you…", theme)
            return
        if not data.get("enabled"):
            self._grow_note("Collaborator matching uses Signals: turn it on in ⚙ Settings → Accounts, and "
                            "people who complement you show up here.", theme)
            return
        people = data.get("people") or []
        if not people:
            self._grow_note("Nobody on Signals complements you yet. As more people join myGeeKy, matches "
                            "show up here.", theme)
        for p in people:
            self.grow_area.addWidget(CollaboratorCard(
                p, theme, lambda login, url, size: _avatar_widget(login, url, size, self.avatar_loader),
                self._voter("collaborator", p["login"], " ; ".join(p.get("interests") or []), p.get("interests") or [],
                            rerender=True),
                self._on_ask_collab, logic.open_link, bool(data.get("can_send"))))
        if data.get("hidden"):
            self._hidden_note(self.grow_area, data["hidden"], "collaborator", theme)

    def _style_pickers(self, theme: dict[str, Any]) -> None:
        """Both drop boxes follow the theme, and follow it again when it is changed."""
        from .growth_ui import combo_style
        css = combo_style(theme)
        self.season_picker.setStyleSheet(css)
        self.country_picker.setStyleSheet(css)

    def _nothing_here(self, said: str, theme: dict[str, Any]) -> QLabel:
        """One way of saying a list is empty, so every reason for it reads the same."""
        lbl = QLabel(said)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
        return lbl

    def _on_country_pick(self, index: int) -> None:
        """A country chosen. Nothing is fetched: the listings are already here, so this only redraws."""
        if index < 0:
            return
        want = self.country_picker.itemData(index) or ""
        if want == self._country:
            return
        self._country = want
        self._render_chances()

    def _everywhere(self) -> list[str]:
        """Every country anything in 🎯 Chances is in, across all four kinds at once.

        Built from all of them rather than the kind on screen, because the filter sits above the kinds and
        holds across them: options that changed as you moved between tabs would make nonsense of that. A
        season's country is where it leads -- Japan for MEXT -- which is the same question a job's place
        answers. "Europe (or a third country, then Europe)" is not a country, so it resolves to none and
        such a season is never filtered out."""
        from .. import curated as _curated
        found = set()
        for kind in ("jobs", "funding", "conferences"):
            for it in (self._chances.get(kind) or {}).get("items") or []:
                if it.get("country"):
                    found.add(it["country"])
        for window in (self._seasons.get("windows") or []):
            for season in window["seasons"]:
                going = _curated.country_of(season.get("goes_to"))
                if going:
                    found.add(going)
        return sorted(found)

    def _in_country(self, season: dict[str, Any]) -> bool:
        """True if this season leads to the country chosen, or names no country at all."""
        from .. import curated as _curated
        if not self._country:
            return True
        going = _curated.country_of(season.get("goes_to"))
        return not going or going == self._country

    def _fill_countries(self, found: list[str]) -> None:
        """Offer every country there is something in, and keep the one already chosen."""
        wanted = ["", *found]
        if [self.country_picker.itemData(i) or "" for i in range(self.country_picker.count())] == wanted:
            return
        self.country_picker.blockSignals(True)      # filling it must not count as the user choosing
        self.country_picker.clear()
        self.country_picker.addItem("🌍 Anywhere", "")
        for name in found:
            self.country_picker.addItem(name, name)
        if self._country not in found:
            self._country = ""
        self.country_picker.setCurrentIndex(max(0, wanted.index(self._country)))
        self.country_picker.blockSignals(False)

    def _on_season_window(self, index: int) -> None:
        """A different period chosen in the drop box. Nothing is fetched: it is all already here."""
        if index < 0 or index == self._season_window:
            return
        self._season_window = index
        if self._chance_mode == "seasons":
            self._render_chances()

    def _render_seasons(self, theme: dict[str, Any]) -> None:
        """🗓 Seasons: one period's worth of scholarships, and what to get ready for each."""
        from .growth_ui import SeasonCard
        data = self._seasons or logic.get_seasons(self.cfg)
        self._seasons = data
        windows = data.get("windows") or []
        if self.season_picker.count() != len(windows):
            self.season_picker.blockSignals(True)      # filling it must not count as the user choosing
            self.season_picker.clear()
            for w in windows:
                note = " (now)" if w["now"] else " (just gone)" if w["past"] else ""
                self.season_picker.addItem(f"{w['label']}{note}")
            self._season_window = min(data.get("at", 0), max(len(windows) - 1, 0))
            self.season_picker.setCurrentIndex(self._season_window)
            self.season_picker.blockSignals(False)
        if not windows:
            lbl = QLabel("No seasons yet. They arrive with the lists, which myGeeKy checks every few hours.")
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
            self.chances_area.addWidget(lbl)
            return
        window = windows[min(self._season_window, len(windows) - 1)]
        span = QLabel(f"Opening {window['from']} to {window['opens_to']} · "
                      f"everything in it closed by {window['to']}")
        span.setWordWrap(True)
        span.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")
        self.chances_area.addWidget(span)
        showing = [s for s in window["seasons"] if self._in_country(s)]
        if not showing:
            self.chances_area.addWidget(self._nothing_here(
                f"Nothing in this period leads to {self._country}. Try another period, or 🌍 Anywhere.",
                theme))
        for season in showing:
            self.chances_area.addWidget(SeasonCard(season, theme, logic.open_link,
                                                   unverified=season.get("unverified", False)))
        left = data.get("unverified", 0)
        if left and logic.is_admin(self.cfg):
            note = QLabel(f"{left} season(s) have no sentence found on their own page yet, so only you see "
                          "them. Run the season check to confirm or drop them.")
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{theme['warn']}; font-size:10px; background:transparent;")
            self.chances_area.addWidget(note)

    def _render_chances(self) -> None:
        if getattr(self, "active_tab", None) != "chances" and not getattr(self, "_chances_drawn", False):
            # drawn the first time Chances is opened: its cards were over half the panel's widgets, built at
            # every start for a page many never open (docs/RESOURCES.md, plan 6); it shows no "new" count
            self._chances_pending = True
            return
        self._chances_drawn = True
        self._chances_pending = False
        from .growth_ui import OpportunityCard
        theme = THEMES[self._theme_name()]
        self._style_grow_switches()
        self._style_pickers(theme)
        _clear_layout(self.chances_area)
        data = self._chances
        mode = self._chance_mode
        self.season_picker.setVisible(mode == "seasons")
        if not self._seasons:
            # loaded whichever kind is open, not only on 🗓 Seasons: a filter that covers everything has to
            # know about everything from the start, or Japan would appear in it only after a visit there.
            # It reads the lists already on this computer, so this costs nothing.
            self._seasons = logic.get_seasons(self.cfg)
        # filled once from every kind at once, so the options do not shift as the kinds are switched
        self._fill_countries(self._everywhere())
        self.country_picker.setVisible(self.country_picker.count() > 1)
        if mode == "seasons":
            self.chances_hint.setText(
                "Scholarships, grants and programmes that come back every year. A window myGeeKy read on a "
                "page says \"open now\"; anything still to come says \"expected\", because no page can yet "
                "say when next year's round opens. The point is the weeks before it: start preparing early.")
            self._render_seasons(theme)
            return
        if not getattr(self, "_chances_running", False):
            self.chances_updated_label.setText(data.get("error") or "")
        hints = {
            "jobs": "Verified jobs: PhD places, postdocs, master's and research jobs that myGeeKy's maker checked "
                    "are real. Matched to you here, on your computer: nobody learns what you looked at. "
                    "Each one disappears after its deadline.",
            "funding": "Grants, fellowships, scholarships and travel grants, matched to your field. "
                       "Each one disappears after its deadline.",
            "conferences": "Conferences in your field, with the abstract deadline and what students get. "
                           "Each one disappears after its deadline.",
        }
        self.chances_hint.setText(hints.get(mode, "") + " 👍 / 👎 teach your model; 🚩 tells the maker one "
                                  "looks fake.")
        block = data.get(mode) or {}
        items = block.get("items") or []
        from .geek_loader import GeekLoader, Hold
        hold = self.__dict__.setdefault("_chances_hold", Hold())
        if not data or hold.wait():                    # loading, or he only just appeared: let him be seen first
            if not data:
                hold.shown()
            else:
                QTimer.singleShot(hold.wait(), self._render_chances)
            self.chances_area.addWidget(GeekLoader("Loading the lists…", theme["muted"]))
            return
        held_back = 0
        if self._country:
            kept = [it for it in items if it.get("country") == self._country]
            held_back = len(items) - len(kept)
            items = kept
        if not items:
            # a country was chosen and nothing here is in it: say so, rather than let the list look broken
            if held_back:
                self.chances_area.addWidget(self._nothing_here(
                    f"None of the {held_back} here are in {self._country}. Pick another country, or "
                    "🌍 Anywhere.", theme))
            else:
                self.chances_area.addWidget(self._nothing_here(
                    {"jobs": "No open verified jobs right now. New ones are added by hand as they're "
                             "checked; myGeeKy looks for them every few hours.",
                     "funding": "No open funding calls right now. New ones show up here by themselves.",
                     "conferences": "No upcoming conferences right now. New ones show up here by "
                                    "themselves."}[mode], theme))
        vote_kind = {"jobs": "job", "funding": "funding", "conferences": "conference"}[mode]
        for it in items:
            self.chances_area.addWidget(OpportunityCard(
                mode, it, theme, self._voter(vote_kind, it["id"], f"{it['title']} {it.get('summary', '')}",
                                             it.get("keywords", []), rerender_chances=True),
                logic.open_link, self._on_report))
        if block.get("hidden"):
            self._hidden_note(self.chances_area, block["hidden"], vote_kind, theme)

    def _hidden_note(self, area, n: int, kind: str, theme: dict[str, Any]) -> None:
        row = QHBoxLayout()
        lbl = QLabel(f"{n} hidden by your 👎.")
        lbl.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
        again = QPushButton("Show them again")
        again.setCursor(Qt.PointingHandCursor)
        again.setStyleSheet(f"QPushButton {{ background:transparent; color:{theme['link']}; border:none; "
                            "font-size:10.5px; text-decoration:underline; }")
        again.clicked.connect(lambda: self._unhide(kind))
        row.addWidget(lbl)
        row.addWidget(again)
        row.addStretch(1)
        holder = QWidget()
        holder.setLayout(row)
        row.setContentsMargins(0, 0, 0, 0)
        area.addWidget(holder)

    def _unhide(self, kind: str) -> None:
        logic.unhide(kind)
        if kind in ("job", "funding", "conference"):
            self._load_chances()
        elif kind == "collaborator":
            self._load_collaborators(force=True)
        else:
            self._load_growth()

    # ---- actions
    def _voter(self, kind: str, item_id: str, text: str, tags: list[str], rerender: bool = False,
               rerender_chances: bool = False) -> Callable[[bool], int]:
        """A thumb's handler: records the vote; a 👎 that hides something redraws the list."""
        def press(up: bool) -> int:
            v = logic.vote(kind, item_id, up, text, tags)
            if v < 0 and rerender:
                QTimer.singleShot(0, self._load_growth if kind != "collaborator"
                                  else lambda: self._load_collaborators(force=True))
            if v < 0 and rerender_chances:
                QTimer.singleShot(0, self._load_chances)
            return v
        return press

    # ---- protocols
    def _render_protocols(self, data: dict[str, Any], theme: dict[str, Any]) -> None:
        from .growth_ui import FlowRow, ProtocolCard
        from .signals_ui import _button_style
        self.grow_hint.setText("A protocol turns a skill into stages, e.g. R basics → statistics with R → data "
                               "analysis → a real project. A short check skips what you already know. Reviewed "
                               "ones are written by myGeeKy's maker; for any other skill myGeeKy builds one from "
                               "GitHub and papers. Change it as you like, then 📤 publish it for everyone.")
        new = QHBoxLayout()
        new.setSpacing(4)
        self.protocol_skill = QLineEdit()
        self.protocol_skill.setPlaceholderText("A skill, e.g. R, Nextflow, GWAS")
        self.protocol_goal = QLineEdit()
        self.protocol_goal.setPlaceholderText("for… (optional), e.g. data analysis")
        for w in (self.protocol_skill, self.protocol_goal):
            w.setMinimumWidth(0)
        style = (f"QLineEdit {{ background:{theme['card_bg']}; color:{theme['text']}; border:none; "
                 "border-radius:8px; padding:5px 8px; font-size:11px; }")
        for w in (self.protocol_skill, self.protocol_goal):
            w.setStyleSheet(style)
            w.returnPressed.connect(self._on_build_protocol)
        go = QPushButton("Building…" if self._building_protocol else "🧭 Build")
        go.setEnabled(not self._building_protocol)
        go.setCursor(Qt.PointingHandCursor)
        go.setStyleSheet(_button_style(theme, accent=True))
        go.clicked.connect(self._on_build_protocol)
        # two lines, so both boxes stay readable in a narrow panel
        self.grow_area.addWidget(self.protocol_skill)
        new.addWidget(self.protocol_goal, 1)
        new.addWidget(go)
        self.grow_area.addLayout(new)
        if self._building_protocol:
            self._grow_note("Searching GitHub and papers, and sorting what comes back into stages…", theme)
        mine = data.get("paths") or []
        built = next((p for p in mine if self._protocol_built and p["id"] == self._protocol_built[0]), None)
        if built:
            said = protocol_built_text(built["title"], built.get("total", 0), self._protocol_built[1])
            if self._protocol_toasted != built["id"]:      # float it once, as it's built; the line below stays
                self._protocol_toasted = built["id"]
                self._toast(said)
            done = QLabel(said)
            done.setWordWrap(True)
            done.setTextFormat(Qt.PlainText)
            done.setStyleSheet(f"color:{theme['good']}; font-size:12px; font-weight:700; background:transparent;")
            self.grow_area.addWidget(done)
        started = {p.get("based_on") or p["id"] for p in mine} | {p["id"] for p in mine}
        offer = [r for r in data.get("reviewed") or [] if r["id"] not in started]
        if offer:
            # best fit first (app.get_growth): a few, then "See all", so your own protocols aren't pushed down
            shown = offer if self._all_reviewed else offer[:REVIEWED_SHOWN]
            self._grow_header(reviewed_heading(len(shown) < len(offer)), theme)
            row = FlowRow()
            for r in shown:
                # A button can never be narrower than its own text, so a long title would make the whole
                # page wider than the panel and squeeze everything in it. Shorten it here; the full title
                # and summary stay in the tooltip.
                b = QPushButton(f"🧭 {_short(r['title'], 30)}")
                b.setToolTip(_tip((r["title"] + "\n\n" + (r.get("summary") or "")).strip()))
                b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet(f"QPushButton {{ background:{theme['card_bg']}; color:{theme['text']}; border:none; "
                                "border-radius:8px; padding:4px 9px; font-size:11px; }")
                b.clicked.connect(lambda checked=False, r=r: self._on_start_path(r["skill"], r.get("goal", "")))
                row.add(b)
            row.finish()
            self.grow_area.addWidget(row)
            if len(offer) > REVIEWED_SHOWN:
                more = QPushButton(see_all_text(len(offer), self._all_reviewed))
                more.setCursor(Qt.PointingHandCursor)
                more.setFlat(True)
                more.setStyleSheet(f"QPushButton {{ color:{theme['link']}; background:transparent; border:none; "
                                   "font-size:11px; font-weight:700; text-align:left; padding:2px 0; }")
                more.clicked.connect(self._toggle_all_reviewed)
                self.grow_area.addWidget(more)
        if not mine:
            self._grow_note("No protocols yet. Pick a reviewed one above, build one for any skill, or press 🧭 on "
                            "a skill in 📈 Skills.", theme)
            return
        self._grow_header("🧭 YOUR PROTOCOLS", theme)
        ids = [p["id"] for p in mine]
        if self._open_protocol not in ids and self._open_protocol != "-":
            self._open_protocol = next((p["id"] for p in mine if not p["finished"]), ids[0])
        for p in mine:
            pid = p["id"]
            self.grow_area.addWidget(ProtocolCard(
                p, theme, self._editing_protocol == pid,
                act=lambda action, *args, pid=pid: self._protocol_act(pid, action, *args),
                on_check=lambda st, pid=pid: self._on_level_check(pid, st),
                on_open=logic.open_link,
                on_edit=lambda pid=pid: self._toggle_protocol_edit(pid),
                on_publish=lambda p=p: self._on_publish_protocol(p),
                on_add_link=lambda sid, pid=pid: self._on_add_protocol_link(pid, sid),
                on_rename=lambda st, pid=pid: self._on_rename_stage(pid, st),
                on_add_stage=lambda pid=pid: self._on_add_stage(pid),
                vote_item=lambda it: self._voter("resource", it["url"], f"{it['title']} {it.get('note', '')}", []),
                vote_of=lambda it: logic.vote_of("resource", it["url"]),
                is_open=pid == self._open_protocol, selected=self._open_step.get(pid, ""),
                on_toggle=lambda pid=pid: self._toggle_protocol_open(pid),
                on_select=lambda sid, pid=pid: self._select_protocol_step(pid, sid),
                quiz=logic.quiz_state(self.cfg, pid),
                on_quiz=lambda pid=pid, title=p["title"]: self._on_take_quiz(pid, title),
                on_share=self._on_share_scores))

    # ---- 🏆 Quiz: every protocol's quiz in one place
    def _render_quizzes(self, theme: dict[str, Any]) -> None:
        from .growth_ui import QuizCard, QuizRunView
        if self._quiz_run:                        # a quiz is being taken: it lives here, in this tab
            run = self._quiz_run
            self.grow_hint.setText("Your answers stay on this computer. Pick an answer to see why it's right "
                                   "and the source it came from.")
            self.grow_area.addWidget(QuizRunView(
                run, theme, on_pick=self._quiz_pick, on_next=self._quiz_next, on_flag=self._quiz_flag,
                on_open=logic.open_link, on_close=self._quiz_close,
                on_share=self._on_share_scores if run.get("attempt") else None))
            return
        mix = logic.quiz_state(self.cfg)
        over = logic.quiz_overview(self.cfg)
        share = over["mix"]
        self.grow_hint.setText(
            f"Ten questions drawn at random from a protocol's own bank: {share['easy']} basics, "
            f"{share['medium']} applied and {share['tricky']} of the mistakes people really make. Every question "
            "comes from one of that protocol's links and shows you that source, with the sentence that proves the "
            f"answer, once you've answered. Pass at {round(over['pass_mark'] * 100)}%; only your best counts, one "
            "attempt a day. Your answers stay on this computer.")
        if over["taken"]:
            self._grow_header("🏆 YOUR SCORES", theme)
            line = (f"{over['taken']} quiz{'zes' if over['taken'] != 1 else ''} taken · "
                    f"average {round(over['average'] * 100)}%")
            if over["perfect"]:
                line += f" · {over['perfect']} at 100% 🏴"
            self._grow_note(line, theme)
        rows = over["rows"]
        if not rows:
            self._grow_note("No quizzes yet. Questions are written and checked on the maker's side and arrive "
                            "with the lists, so the reviewed protocols get them first. 🧭 Protocols still works "
                            "without them: each step has its links, and \"I can do these\" marks what you know.",
                            theme)
            return
        mine = [r for r in rows if r["mine"]]
        others = [r for r in rows if not r["mine"]]
        if mine:
            self._grow_header("🧭 YOUR PROTOCOLS", theme)
        for r in mine:
            self.grow_area.addWidget(QuizCard({**r, "per_attempt": over["per_attempt"],
                                               "pass_mark": over["pass_mark"]}, theme,
                                              on_take=lambda r=r: self._on_take_quiz(r["id"], r["title"]),
                                              on_start=lambda r=r: self._on_start_path(r["skill"]),
                                              on_share=self._on_share_scores))
        if others:
            self._grow_header("✓ REVIEWED PROTOCOLS WITH A QUIZ", theme)
        for r in others:
            self.grow_area.addWidget(QuizCard({**r, "per_attempt": over["per_attempt"],
                                               "pass_mark": over["pass_mark"]}, theme,
                                              on_take=lambda r=r: self._on_take_quiz(r["id"], r["title"]),
                                              on_start=lambda r=r: self._on_start_path(r["skill"]),
                                              on_share=None))
        if over.get("waiting"):
            n = len(over["waiting"])
            self._grow_note(f"{n} of your protocols {'have' if n != 1 else 'has'} no questions yet "
                            f"({', '.join(over['waiting'][:3])}{'…' if n > 3 else ''}). They're written and "
                            "checked on the maker's side, and arrive with the lists.", theme)
        if over["flagged"]:
            from .growth_ui import _pill_button
            back = _pill_button(f"🚩 {over['flagged']} question{'s' if over['flagged'] != 1 else ''} you flagged: "
                                "show them again", "They can come up in your next attempts", theme,
                                self._on_unflag_all)
            self.grow_area.addWidget(back)
        _ = mix

    def _on_unflag_all(self) -> None:
        n = logic.quiz_unflag_all()
        self._info("Flagged questions", f"{n} question{'s' if n != 1 else ''} can come up again.")
        self._render_grow()

    def _toggle_protocol_open(self, pid: str) -> None:
        self._open_protocol = "" if self._open_protocol == pid else pid
        if not self._open_protocol:
            self._open_protocol = "-"            # all folded (not reopened by default)
        self._render_grow()

    def _select_protocol_step(self, pid: str, sid: str) -> None:
        self._open_step[pid] = sid
        self._open_protocol = pid
        self._render_grow()

    def _on_start_path(self, skill: str, goal: str = "") -> None:
        """🧭 on a skill (or a reviewed protocol): start it, building one first if there's no reviewed one."""
        if self._building_protocol:
            return
        self._building_protocol = True
        self._protocol_built = None
        self._protocol_toasted = ""
        self._grow_mode = "paths"
        self._render_grow()
        self._run_async(lambda: logic.build_protocol(self.cfg, skill, goal), self._on_protocol_built)

    def _toggle_all_reviewed(self) -> None:
        self._all_reviewed = not self._all_reviewed
        self._render_grow()

    def _on_build_protocol(self) -> None:
        skill = self.protocol_skill.text().strip() if hasattr(self, "protocol_skill") else ""
        if skill:
            self._on_start_path(skill, self.protocol_goal.text().strip())

    def _on_protocol_built(self, result: Any) -> None:
        self._building_protocol = False
        if isinstance(result, dict) and result.get("id"):
            self._open_protocol = result["id"]          # the new one opens; the others fold
            self._protocol_built = (result["id"], bool(result.get("reviewed")))
        if isinstance(result, dict) and result.get("error"):
            self._info("Protocol", result["error"])
        self._load_growth()

    def _protocol_act(self, pid: str, action: str, *args: Any) -> None:
        if action == "stop":
            box = self._box("Stop this protocol", "Stop this protocol? Your progress and your changes to it are removed.")
            yes = box.addButton("Stop it", QMessageBox.DestructiveRole)
            box.addButton(QMessageBox.Cancel)
            box.exec()
            if box.clickedButton() is not yes:
                return
        self._protocol_built = None
        logic.protocol_action(self.cfg, action, pid, *args)
        self._load_growth()

    def _toggle_protocol_edit(self, pid: str) -> None:
        self._editing_protocol = "" if self._editing_protocol == pid else pid
        self._render_grow()

    def _dialog_css(self) -> str:
        return dialog_css(THEMES[self._theme_name()])

    def _box(self, title: str, text: str) -> QMessageBox:
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setTextFormat(Qt.PlainText)               # titles from web pages show as text, never as HTML
        box.setText(text)
        box.setStyleSheet(self._dialog_css())
        return box

    def _toast(self, text: str) -> None:
        """A line that floats over the bottom of the panel for TOAST_MS, then fades: seen wherever the page is
        scrolled, and it takes no clicks. The phone has the same (components/toast.tsx)."""
        theme = THEMES[self._theme_name()]
        lbl = getattr(self, "_toast_label", None)
        if lbl is None:
            lbl = self._toast_label = QLabel(self)
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.PlainText)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
            self._toast_fade = QGraphicsOpacityEffect(lbl)
            lbl.setGraphicsEffect(self._toast_fade)
            self._toast_anim = QPropertyAnimation(self._toast_fade, b"opacity", self)
            # hidden only once it has really faded out: a new message arriving mid-fade stays up
            self._toast_anim.finished.connect(lambda: lbl.hide() if self._toast_fade.opacity() < 0.01 else None)
            self._toast_timer = QTimer(self)
            self._toast_timer.setSingleShot(True)
            self._toast_timer.timeout.connect(lambda: self._fade_toast(0.0))
        lbl.setStyleSheet(f"QLabel {{ background:{theme['solid_bg']}; color:{theme['solid_text']}; "
                          f"border:1px solid {theme['good']}; border-radius:10px; padding:9px 12px; "
                          "font-size:12px; font-weight:700; }")
        lbl.setText(text)
        frame = self.panel_frame.geometry()            # the drawn panel, not the (taller, see-through) window
        lbl.setFixedWidth(max(frame.width() - 24, 120))
        lbl.adjustSize()
        lbl.move(frame.x() + 12, max(frame.y() + frame.height() - lbl.height() - 22, frame.y()))
        lbl.show()
        lbl.raise_()
        self._fade_toast(1.0)
        self._toast_timer.start(TOAST_MS)

    def _fade_toast(self, to: float) -> None:
        self._toast_anim.stop()
        self._toast_anim.setDuration(250)
        self._toast_anim.setStartValue(self._toast_fade.opacity())
        self._toast_anim.setEndValue(to)
        self._toast_anim.start()

    def _info(self, title: str, text: str) -> None:
        box = self._box(title, text)
        box.addButton(QMessageBox.Ok)
        box.exec()

    def _ask_text(self, title: str, label: str, value: str = "", echo=None) -> str:
        from PySide6.QtWidgets import QInputDialog
        dlg = QInputDialog(self)
        dlg.setWindowTitle(title)
        dlg.setLabelText(label)
        dlg.setTextValue(value)
        dlg.setTextEchoMode(echo if echo is not None else QLineEdit.Normal)
        dlg.setStyleSheet(self._dialog_css())
        return dlg.textValue().strip() if dlg.exec() == QDialog.Accepted else ""

    def _on_rename_stage(self, pid: str, st: dict[str, Any]) -> None:
        title = self._ask_text("Rename stage", "New name:", st["title"])
        if title:
            self._protocol_act(pid, "rename_stage", st["id"], title)

    def _on_add_stage(self, pid: str) -> None:
        title = self._ask_text("Add a stage", "Name of the new stage (e.g. Statistics with R):")
        if title:
            self._protocol_act(pid, "add_stage", title)

    def _on_add_protocol_link(self, pid: str, sid: str) -> None:
        url = self._ask_text("Add a link", "Link (https://…): a GitHub repo, a paper (doi.org) or a page")
        if not url:
            return
        if not url.startswith("https://"):
            self._info("Add a link", "Only https:// links can be added.")
            return
        title = self._ask_text("Add a link", "What is it? (a short title)") or url
        logic.protocol_action(self.cfg, "add_item", pid, sid, url, title)
        self._load_growth()

    def _on_level_check(self, pid: str, st: dict[str, Any]) -> None:
        """The level check for one stage: questions from the bank for that step, the ones written into
        the protocol itself, or 'I can do these' when there are none."""
        drawn = logic.quiz_draw(self.cfg, pid, st["id"])
        if drawn is not None:
            self._start_quiz(pid, drawn, stage=st["id"], stage_title=st["title"])
            return
        if st.get("quiz"):
            self._old_style_check(pid, st)
            return
        self._can_do_check(pid, st)

    def _can_do_check(self, pid: str, st: dict[str, Any]) -> None:
        """No questions for this step: tick what you can already do."""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Check: {st['title']}")
        dlg.setStyleSheet(self._dialog_css())
        lay = QVBoxLayout(dlg)
        intro = QLabel("Tick what you can already do. All ticked, and this stage is marked as known.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        boxes: list[QCheckBox] = []
        for c in st.get("can") or []:
            cb = QCheckBox(c)
            lay.addWidget(cb)
            boxes.append(cb)
        lay.addLayout(self._dialog_buttons(dlg, "Check"))
        if dlg.exec() == QDialog.Accepted and boxes and all(cb.isChecked() for cb in boxes):
            logic.protocol_action(self.cfg, "known", pid, st["id"], "self")
        self._load_growth()

    def _old_style_check(self, pid: str, st: dict[str, Any]) -> None:
        """Questions written into the protocol itself (reviewed protocols from before the bank)."""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Check: {st['title']}")
        dlg.setStyleSheet(self._dialog_css())
        lay = QVBoxLayout(dlg)
        intro = QLabel(f"{len(st['quiz'])} questions. Get 75% right and this stage is marked as known. "
                       "Your answers stay on this computer.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        groups: list[list[QRadioButton]] = []
        for n, q in enumerate(st["quiz"], 1):
            ql = QLabel(f"<b>{n}. {html.escape(q['q'])}</b>")
            ql.setWordWrap(True)
            lay.addWidget(ql)
            holder = QWidget()
            hl = QVBoxLayout(holder)
            hl.setContentsMargins(12, 0, 0, 4)
            opts = []
            for o in q["options"]:
                rb = QRadioButton(o)
                hl.addWidget(rb)
                opts.append(rb)
            lay.addWidget(holder)
            groups.append(opts)
        lay.addLayout(self._dialog_buttons(dlg, "Check"))
        if dlg.exec() != QDialog.Accepted:
            return
        answers = [next((i for i, rb in enumerate(g) if rb.isChecked()), -1) for g in groups]
        score = logic.protocol_action(self.cfg, "quiz", pid, st["id"], answers) or 0.0
        self._info("Check", f"{round(score * len(groups))} of {len(groups)} right." + (
            " You know this one: it's marked as known." if score >= 0.75 else
            " Not yet: this stage stays on your list. The links below it are a good place to start."))
        self._load_growth()

    def _dialog_buttons(self, dlg: QDialog, ok_text: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        ok = QPushButton(ok_text)
        cancel.clicked.connect(dlg.reject)
        ok.clicked.connect(dlg.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        return row

    # ---- taking a quiz: one question at a time, then the result
    def _on_take_quiz(self, pid: str, title: str) -> None:
        """🏁 Take the quiz. Wherever it was pressed, the quiz itself opens in the 🏆 Quiz tab."""
        state = logic.quiz_state(self.cfg, pid)
        if not state["counts"].get("total"):
            self._info("Quiz", "There are no questions for this protocol yet. They're written and checked on "
                               "the maker's side, and arrive with the lists — the reviewed protocols get them "
                               "first.")
            return
        if not state["can_try"]:
            self._info("Quiz", state["why"])
            return
        drawn = logic.quiz_draw(self.cfg, pid)
        if drawn is None:
            self._info("Quiz", "There are no questions left for this protocol that you haven't flagged.")
            return
        self._start_quiz(pid, drawn, stage="", stage_title="")

    def _start_quiz(self, pid: str, drawn: Any, stage: str, stage_title: str) -> None:
        """Begin an attempt and show it in the 🏆 Quiz tab."""
        self._quiz_run = {"pid": pid, "quiz": drawn, "stage": stage, "stage_title": stage_title,
                          "at": 0, "answers": [-1] * len(drawn.questions), "attempt": None,
                          "best_before": float((logic.quiz_state(self.cfg, pid)["best"] or {}).get("score") or 0.0)}
        self._grow_mode = "quiz"
        self._switch_tab("grow")
        self._render_grow()

    def _quiz_pick(self, i: int) -> None:
        run = self._quiz_run
        if not run:
            return
        q = run["quiz"].questions[run["at"]]
        if q.answered:
            return
        q.picked = i
        run["answers"][run["at"]] = i
        self._render_grow()

    def _quiz_next(self) -> None:
        run = self._quiz_run
        if not run:
            return
        if run["at"] < len(run["quiz"].questions) - 1:
            run["at"] += 1
        else:
            run["attempt"] = logic.quiz_mark(self.cfg, run["quiz"], run["answers"], run["stage"])
        self._render_grow()

    def _quiz_flag(self) -> None:
        """🚩 on the question you're looking at: left out of your next attempts, and the maker can be told."""
        run = self._quiz_run
        if not run:
            return
        q = run["quiz"].questions[run["at"]]
        on = logic.quiz_flag(q.id, not q.flagged)
        q.flagged = on
        if on:
            box = self._box("This question looks wrong", "Thanks: it's left out of your next attempts.\n\n"
                            "Tell the maker too? It opens a public GitHub issue, sent with your own account "
                            "when you press Submit. It holds the question, not your answers.")
            tell = box.addButton("Tell the maker", QMessageBox.AcceptRole)
            box.addButton(QMessageBox.Cancel)
            box.exec()
            if box.clickedButton() is tell:
                logic.open_link(logic.quiz_report(q))
        self._render_grow()

    def _quiz_close(self) -> None:
        """Leave the quiz: back to the list in this same tab. An unmarked attempt simply doesn't count."""
        self._quiz_run = None
        self._load_growth()

    # ---- showing a score on mygeeky.org (only if you ask for it)
    def _on_share_scores(self) -> None:
        """Two switches, exactly what would appear, and then your own `accept` on GitHub."""
        theme = THEMES[self._theme_name()]
        dlg = QDialog(self)
        dlg.setWindowTitle("Show my result on mygeeky.org")
        dlg.setStyleSheet(self._dialog_css())
        dlg.setMinimumWidth(460)
        lay = QVBoxLayout(dlg)
        intro = QLabel("Nothing about you is online. A score can follow you into a job application, so this "
                       "is yours to choose, in two parts, and you agree to it from your own GitHub account.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        name_box = QCheckBox("Show my name, my profile link and my GitHub photo")
        score_box = QCheckBox("Show my scores next to it")
        for cb in (name_box, score_box):
            lay.addWidget(cb)
        preview = QLabel("")
        preview.setWordWrap(True)
        preview.setStyleSheet(f"color:{theme['text']}; font-size:11px; background:{theme['card_bg']}; "
                              "border-radius:8px; padding:8px;")
        lay.addWidget(preview)
        row = QHBoxLayout()
        row.addStretch(1)
        later = QPushButton("Not now")
        go = QPushButton("Accept on GitHub")
        row.addWidget(later)
        row.addWidget(go)
        lay.addLayout(row)
        take_back = QPushButton("Take a shared score back (withdraw)")
        take_back.setCursor(Qt.PointingHandCursor)
        take_back.clicked.connect(lambda: logic.open_link(logic.withdraw_url(self.cfg)))
        lay.addWidget(take_back)

        def refresh() -> None:
            st = logic.share_state(self.cfg, name_box.isChecked(), score_box.isChecked())
            preview.setText("What would appear on the page:\n" + "\n".join(f"• {ln}" for ln in st["lines"])
                            + ("" if st["ok"] else f"\n\n{st['why']}"))
            go.setEnabled(st["ok"])
        for cb in (name_box, score_box):
            cb.toggled.connect(lambda checked=False: refresh())
        later.clicked.connect(dlg.reject)
        go.clicked.connect(dlg.accept)
        refresh()
        if dlg.exec() != QDialog.Accepted:
            return
        url = logic.share_url(self.cfg, name_box.isChecked(), score_box.isChecked())
        if not url:
            return
        box = self._box("Accept on GitHub", "This opens a public issue in mygeeky/myGeeKy-ideas holding exactly "
                        "what you just saw, with the word “accept” already written in it. Press Submit there and "
                        "it's your own account that says yes — that's the proof, and no email is involved.\n\n"
                        "The maker checks each entry before it appears, and you can write “withdraw” on the same "
                        "issue any time.")
        open_it = box.addButton("Open on GitHub", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        if box.clickedButton() is open_it:
            logic.open_link(url)

    def _on_publish_protocol(self, p: dict[str, Any]) -> None:
        box = self._box("Publish this protocol", f"Send “{p['title']}” to myGeeKy, for everyone?\n\n"
                    "This opens a public GitHub issue in mygeeky/myGeeKy-ideas, sent with your GitHub account "
                    "when you press Submit. It holds the protocol (its stages and links) and the links you "
                    "removed, so the maker can review it for everyone and improve the protocol model.\n\n"
                    "Your progress, your checks and your answers are not included.")
        go = box.addButton("Open on GitHub", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        if box.clickedButton() is go:
            out = logic.publish_protocol(self.cfg, p["id"])
            if out.get("clipboard"):
                QApplication.clipboard().setText(out["clipboard"])
                self._info("Publish this protocol",
                                        "It's too long for a link, so myGeeKy copied it for you. On the GitHub page "
                                        "that opens, paste it (Ctrl+V / ⌘V) where it says, then press Submit.")
            if out.get("url"):
                logic.open_link(out["url"])

    def _on_ask_collab(self, card) -> None:
        login = card.person["login"]
        card.ask.setEnabled(False)
        card.note.setText("sending…")
        self._run_async(lambda: logic.send_signal(self.cfg, login, "collab"),
                        lambda r: card.set_result(bool((r or {}).get("ok")),
                                                  "sent: you'll both know if they pick you too"
                                                  if (r or {}).get("ok") else f"couldn't send: {(r or {}).get('error', '')}")
                        if _alive(card) else None)

    def _on_report(self, kind: str, item: dict[str, Any]) -> None:
        links = logic.report_links(kind, item)
        box = self._box("Report a listing", f"Does “{item.get('title', '')}” look fake, or is it no longer real?\n\n"
                    "Tell myGeeKy's maker, who checks it and takes it down. A GitHub issue is public and "
                    "sent with your account; an email is private.")
        gh = box.addButton("Report on GitHub", QMessageBox.AcceptRole)
        mail = box.addButton("Email support", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        if box.clickedButton() is gh:
            logic.open_link(links["issue"])
        elif box.clickedButton() is mail:
            logic.open_link(links["email"])

    def _build_update_banner(self) -> QFrame:
        banner = QFrame()
        banner.setObjectName("updateBanner")
        layout = QVBoxLayout(banner)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        self.update_label = QLabel("")
        self.update_label.setWordWrap(True)
        layout.addWidget(self.update_label)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.update_btn = QPushButton("Update")
        self.update_btn.setObjectName("updateNow")
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.clicked.connect(self._on_update_clicked)
        self.whats_new_btn = QPushButton("What's new")
        self.whats_new_btn.setCursor(Qt.PointingHandCursor)
        self.whats_new_btn.clicked.connect(
            lambda: logic.open_link(self._update_info.get("releases_url", "")))
        self.later_btn = QPushButton("Later")
        self.later_btn.setCursor(Qt.PointingHandCursor)
        self.later_btn.clicked.connect(self._on_update_later)
        for b in (self.update_btn, self.whats_new_btn, self.later_btn):
            row.addWidget(b)
        row.addStretch(1)
        layout.addLayout(row)
        return banner

    def _check_for_update(self) -> None:
        self._run_async(lambda: logic.get_update_info(self.cfg), self._on_update_info)

    def _on_update_info(self, info: Any) -> None:
        info = info if isinstance(info, dict) else {}
        self._update_info = info
        if not info.get("show"):
            self.update_banner.setVisible(False)
            return
        if info.get("editable"):
            self.update_label.setText(f"✨ myGeeKy {info['latest']} is out. This is a developer install, "
                                      "so update it with git pull.")
            self.update_btn.setVisible(False)
        else:
            self.update_label.setText(f"✨ myGeeKy {info['latest']} is available (you have {info['current']}).")
            self.update_btn.setVisible(True)
        self.update_banner.setVisible(True)

    def _on_update_later(self) -> None:
        if self._update_info.get("latest"):
            logic.dismiss_update(self.cfg, self._update_info["latest"])
        self.update_banner.setVisible(False)

    def _on_update_clicked(self) -> None:
        for b in (self.update_btn, self.later_btn):
            b.setEnabled(False)
        self.update_label.setText("Updating myGeeKy… (about a minute; keep using it meanwhile)")
        self._run_async(logic.install_update, self._on_update_done)

    def _on_update_done(self, result: Any) -> None:
        result = result if isinstance(result, dict) else {"ok": False, "message": str(result)}
        if result.get("ok"):
            # "already the latest" is a success with nothing to restart for
            if "already the latest" in str(result.get("message", "")):
                self.update_label.setText(f"✓ {result['message']}")
                self.update_btn.setVisible(False)
                self.later_btn.setEnabled(True)
                return
            self.update_label.setText(f"✓ {result['message']} Restarting…")
            from .. import updates
            updates.relaunch_panel_after_exit()
            QTimer.singleShot(600, QApplication.instance().quit)
            return
        self._show_update_fallback(result)

    def _show_update_fallback(self, result: dict) -> None:
        """An update that could not be installed still has to leave the person somewhere.

        "Couldn't update" and a Try again button is a dead end when trying again cannot work: a
        Python that needs administrator rights will refuse every time, and a developer install is
        never meant to be replaced by pip. So the reason is said in plain words, and the way this
        particular install is updated by hand is offered next to it -- one button to copy the command,
        one to open the download page."""
        steps = result.get("steps") or {}
        why = str(result.get("message", "")) or "unknown error"
        what = str(steps.get("what", "")).strip()
        self.update_label.setText(f"Couldn't update: {why}" + (f"\n{what}" if what else ""))

        command = str(steps.get("command", ""))
        if command:
            self.update_btn.setText("Copy the command")
            self.update_btn.setToolTip(command)
            self.update_btn.setVisible(True)
            _reconnect(self.update_btn.clicked, lambda: self._copy_update_command(command))
        else:
            self.update_btn.setVisible(False)

        url = str(steps.get("url", ""))
        self.whats_new_btn.setText("How to update" if url else "What's new")
        _reconnect(self.whats_new_btn.clicked,
                   lambda: logic.open_link(url or self._update_info.get("releases_url", "")))
        for b in (self.update_btn, self.later_btn, self.whats_new_btn):
            b.setEnabled(True)

    def _copy_update_command(self, command: str) -> None:
        QApplication.clipboard().setText(command)
        self.update_label.setText(f"Copied. Run it in a terminal:\n{command}")

    def _build_token_banner(self) -> QFrame:
        banner = QFrame()
        banner.setObjectName("tokenBanner")
        layout = QVBoxLayout(banner)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        self.token_label = QLabel("")
        self.token_label.setWordWrap(True)
        layout.addWidget(self.token_label)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.renew_token_btn = renew = QPushButton("Renew on GitHub ↗")
        renew.setCursor(Qt.PointingHandCursor)
        from ..tokens import SETTINGS_URL
        renew.clicked.connect(lambda: logic.open_link(SETTINGS_URL))
        self.paste_token_btn = QPushButton("Paste new token")
        self.paste_token_btn.setCursor(Qt.PointingHandCursor)
        self.paste_token_btn.clicked.connect(self._on_paste_token)
        self.signin_again_btn = QPushButton("Sign in again")      # for a Sign-in-with-GitHub token
        self.signin_again_btn.setCursor(Qt.PointingHandCursor)
        self.signin_again_btn.clicked.connect(self._open_setup_window)
        self.signin_again_btn.hide()
        row.addWidget(renew)
        row.addWidget(self.paste_token_btn)
        row.addWidget(self.signin_again_btn)
        row.addStretch(1)
        layout.addLayout(row)
        return banner

    def _check_tokens(self) -> None:
        self._tokens_checked_at = time.monotonic()
        self._run_async(lambda: logic.get_token_warnings(self.cfg), self._on_token_warnings)

    def _recheck_tokens_if_warning(self) -> None:
        """You may have just signed in or pasted a new token elsewhere (the setup window, a
        terminal): while the warning shows, look again when you open the panel, so it goes
        away by itself instead of only after a restart. At most once a minute."""
        if self.token_banner.isVisible() and time.monotonic() - getattr(self, "_tokens_checked_at", 0) > 60:
            self._check_tokens()

    def _on_token_warnings(self, warnings: Any) -> None:
        self._token_warnings = warnings if isinstance(warnings, list) else []
        self._render_signs()
        if not self._token_warnings:
            self.token_banner.setVisible(False)
            return
        signin = any(w.get("signin") or w.get("renews") for w in self._token_warnings)
        lines = [w["message"].split(" Renew it")[0].split(" Make a new")[0].split(" Sign in again")[0]
                 .split(" needs you")[0] for w in self._token_warnings]
        lines.append("Sign in with GitHub again: from then on myGeeKy keeps it working by itself." if signin else
                     "On GitHub, open the token and click 'Regenerate token', then paste it here.")
        self.renew_token_btn.setVisible(not signin)
        self.paste_token_btn.setVisible(not signin)
        self.signin_again_btn.setVisible(signin)
        self.token_label.setText("\n".join(("⏳ " + ln) if i < len(lines) - 1 else ln for i, ln in enumerate(lines)))
        self.token_banner.setVisible(True)

    def _open_setup_window(self) -> None:
        """The setup window, where Sign in with GitHub is one click."""
        from .desktop import launch_command
        from .. import winproc
        python = launch_command()[0]
        winproc.popen([python, "-m", "mygeeky.gui.setup_wizard"], close_fds=True, cwd=str(Path.home()))

    def _on_paste_token(self) -> None:
        from PySide6.QtWidgets import QLineEdit
        if not self._token_warnings:
            return
        target = self._token_warnings[0]
        value = self._ask_text("myGeeKy", f"Paste your new {target['label']}:", echo=QLineEdit.Password)
        if not value:
            return
        self.paste_token_btn.setEnabled(False)
        self.token_label.setText("Checking the new token…")
        self._run_async(lambda: logic.replace_token(self.cfg, target["name"], value), self._on_token_replaced)

    def _on_token_replaced(self, result: Any) -> None:
        self.paste_token_btn.setEnabled(True)
        result = result if isinstance(result, dict) else {"ok": False, "message": str(result)}
        self.token_label.setText(("✓ " if result.get("ok") else "✗ ") + result.get("message", ""))
        if result.get("ok"):
            QTimer.singleShot(2500, self._check_tokens)   # another token still due? else the banner goes

    # ------------------------------------------------------------------ 💡 ideas
    def _open_idea_dialog(self) -> None:
        self._show_dialog("_idea_dialog", lambda: IdeaDialog(self, THEMES[self._theme_name()]))

    def _show_dialog(self, slot: str, make) -> None:
        """Open a small window WITHOUT locking the panel (a locking window that ends up behind the
        always-on-top panel made it look frozen); pressing again brings the open one to the front."""
        dlg = getattr(self, slot, None)
        if dlg is None or not _alive(dlg) or not dlg.isVisible():
            dlg = make()
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.setWindowModality(Qt.NonModal)
            setattr(self, slot, dlg)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    # ------------------------------------------------------------------ 🛡 admin (the maker only)
    def _build_admin_tab(self) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 4, 4)
        layout.setSpacing(8)
        actions = QHBoxLayout()
        self.admin_updated = QLabel("")
        self.admin_refresh_btn = QPushButton("Refresh")
        self.admin_refresh_btn.setCursor(Qt.PointingHandCursor)
        self.admin_refresh_btn.clicked.connect(self._refresh_admin)
        actions.addWidget(self.admin_updated, 1)
        self.admin_undo_btn = QPushButton("Undo")
        self.admin_undo_btn.setCursor(Qt.PointingHandCursor)
        self.admin_undo_btn.setToolTip("Didn't send it after all? Put them back on the list")
        self.admin_undo_btn.clicked.connect(self._undo_invite)
        self.admin_undo_btn.hide()
        actions.addWidget(self.admin_undo_btn)
        actions.addWidget(self.admin_refresh_btn)
        layout.addLayout(actions)
        # six sections, one at a time: the planets under You → Admin choose which (ADMIN_PARTS)
        self._admin_part = getattr(self, "_admin_part", "overview")
        self.admin_sections: dict[str, QWidget] = {}
        self.admin_section_heads: dict[str, QLabel] = {}

        def section(part: str) -> QVBoxLayout:
            box = QWidget()
            lay = QVBoxLayout(box)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(8)
            head = QLabel("")
            head.setWordWrap(True)
            lay.addWidget(head)
            self.admin_section_heads[part] = head
            self.admin_sections[part] = box
            layout.addWidget(box)
            return lay

        overview, review, write, inbox, people, settings = (section(p) for p, *_ in ADMIN_PARTS)
        self.admin_headers = [QLabel("\U0001f4c8 ADOPTION"), QLabel("\U0001f4ec IDEAS INBOX"),
                              QLabel("\U0001f3af PEOPLE TO INVITE")]
        # 📊 Overview: adoption, what's waiting, and exactly what Publish would send
        overview.addWidget(self.admin_headers[0])
        tiles = QHBoxLayout()
        tiles.setSpacing(6)
        self.admin_tiles = {k: StatTile(c) for k, c in (("pypi_week", "PyPI / week"), ("installer_downloads", "installs (.exe)"),
                                                        ("stars", "stars"), ("signals_users", "on Signals"))}
        for t_ in self.admin_tiles.values():
            tiles.addWidget(t_, 1)
        overview.addLayout(tiles)
        self.admin_funnel = QLabel("")
        self.admin_funnel.setWordWrap(True)
        overview.addWidget(self.admin_funnel)
        # what the ETag cache saved today: a 304 costs nothing against your limit (ghcache.py)
        self.admin_calls = QLabel("")
        self.admin_calls.setWordWrap(True)
        overview.addWidget(self.admin_calls)
        self.admin_wisep = QLabel("")                    # WISEP: what the open databases were asked today
        self.admin_wisep.setWordWrap(True)
        self.admin_wisep.setTextFormat(Qt.PlainText)
        overview.addWidget(self.admin_wisep)
        self.admin_waiting = QLabel("")
        self.admin_waiting.setWordWrap(True)
        self.admin_waiting.setTextFormat(Qt.PlainText)
        overview.addWidget(self.admin_waiting)
        self.admin_publish_btn = QPushButton("🚀 Publish")
        self.admin_publish_btn.setCursor(Qt.PointingHandCursor)
        self.admin_publish_btn.clicked.connect(self._on_scout_publish)
        overview.addWidget(self.admin_publish_btn, 0, Qt.AlignLeft)
        # 📥 Review: listings, Highlight drafts and quizzes, together
        self.admin_scout_header = QLabel("\U0001f3af LISTINGS TO REVIEW")
        review.addWidget(self.admin_scout_header)
        scout_box = QWidget()
        self.admin_scout = QVBoxLayout(scout_box)
        self.admin_scout.setContentsMargins(0, 0, 0, 0)
        self.admin_scout.setSpacing(6)
        review.addWidget(scout_box)
        from .highlights_ui import AdminHighlights
        self.admin_hl_header = QLabel("\u2728 HIGHLIGHTS TO REVIEW")
        review.addWidget(self.admin_hl_header)
        self.admin_highlights = AdminHighlights(lambda: THEMES[self._theme_name()], self._run_async,
                                                lambda it, warn: self._open_highlight(it, warn), self._on_scout_publish)
        review.addWidget(self.admin_highlights.drafts)
        self.admin_quiz_header = QLabel("\U0001f4dd QUIZZES")
        review.addWidget(self.admin_quiz_header)
        quiz_box = QWidget()
        self.admin_quiz = QVBoxLayout(quiz_box)
        self.admin_quiz.setContentsMargins(0, 0, 0, 0)
        self.admin_quiz.setSpacing(6)
        review.addWidget(quiz_box)
        # ✍ Write: Highlights from DOIs, and any answer written elsewhere
        self.admin_write_header = QLabel("\u2728 WRITE HIGHLIGHTS")
        write.addWidget(self.admin_write_header)
        write.addWidget(self.admin_highlights.form)
        self.admin_import_header = QLabel("\U0001f4e5 BRING YOUR OWN ANSWER")
        write.addWidget(self.admin_import_header)
        from .admin_ui import ImportBox
        self.admin_import = ImportBox(lambda: THEMES[self._theme_name()], self._run_async, logic.reviewed_protocols,
                                      lambda: self._render_admin())
        write.addWidget(self.admin_import)
        # 💡 Inbox: ideas and problems, and the words people want taught
        inbox.addWidget(self.admin_headers[1])
        inbox_box = QWidget()
        self.admin_inbox = QVBoxLayout(inbox_box)
        self.admin_inbox.setContentsMargins(0, 0, 0, 0)
        self.admin_inbox.setSpacing(5)
        inbox.addWidget(inbox_box)
        self.admin_kw_header = QLabel("\U0001f524 KEYWORDS TO TEACH")
        inbox.addWidget(self.admin_kw_header)
        self.admin_kw = QLabel("")
        self.admin_kw.setWordWrap(True)
        self.admin_kw.setTextFormat(Qt.RichText)
        inbox.addWidget(self.admin_kw)
        # 🤝 People to invite
        people.addWidget(self.admin_headers[2])
        self.admin_hint = QLabel("Ranked by how likely they are to want myGeeKy. Nothing is ever sent from here: "
                                 "Email opens a draft in your mail app, Copy puts the invite on your clipboard. "
                                 "Mark them once you've reached out (10 a day, at most).")
        self.admin_hint.setWordWrap(True)
        people.addWidget(self.admin_hint)
        prospect_box = QWidget()
        self.admin_prospects = QVBoxLayout(prospect_box)
        self.admin_prospects.setContentsMargins(0, 0, 0, 0)
        self.admin_prospects.setSpacing(6)
        people.addWidget(prospect_box)
        # ⚙ Settings: the DeepSeek key, the sites and field, the mailbox, GitHub's cache
        self.admin_settings_note = QLabel("")
        self.admin_settings_note.setWordWrap(True)
        settings.addWidget(self.admin_settings_note)
        self.admin_settings_btns = []
        for text, tip, fn in (("🔑 DeepSeek key", "Kept in this computer's credential store, never in a file",
                               self._on_scout_key),
                              ("🌐 Sites and field", "Which sites the scout looks through, and your field",
                               self._on_scout_sites),
                              ("📧 Job-alert mailbox", "One folder of your mailbox, read-only", self._on_scout_alerts),
                              ("🧹 Forget GitHub's answers", "Throw away what GitHub told us. Nothing is lost: the "
                               "next refresh asks again.", self._on_forget_cache)):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            settings.addWidget(b, 0, Qt.AlignLeft)
            self.admin_settings_btns.append(b)
        self._show_admin_part()
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        scroll.viewport().setAutoFillBackground(False)
        page.setAutoFillBackground(False)
        QTimer.singleShot(0, self._render_admin)
        return scroll

    def _render_admin(self, data: dict[str, Any] | None = None) -> None:
        theme = THEMES[self._theme_name()]
        data = data or logic.admin_data(self.cfg)
        adoption = data.get("adoption") or {}
        for key, tile in self.admin_tiles.items():
            v = adoption.get(key)
            tile.set_value(v or 0, (lambda x: "\u2013") if v is None else None)
            tile.apply_theme(theme)
        f = data.get("funnel") or {}
        self.admin_funnel.setText(f"Invites: {f.get('invited', 0)} sent · {f.get('joined', 0)} joined"
                                  + (f" ({round(100 * f['joined'] / f['invited'])}%)" if f.get("invited") else "")
                                  + f" · {f.get('new', 0)} to consider · {data.get('invited_today', 0)}/10 today")
        calls = logic.github_calls()
        self.admin_calls.setText(
            f"GitHub today: {calls['asked']} asked · {calls['saved']} free "
            f"({calls['not_modified']} unchanged, {calls['from_cache']} already known"
            + (f", {calls['offline']} while offline" if calls["offline"] else "") + ")"
            + (f" · {calls['share']}% saved" if calls["share"] else "")
            + f" · {calls['searches']} searches · {calls['entries']} answers kept")
        _clear_layout(self.admin_inbox)
        inbox = data.get("inbox") or []
        if not inbox:
            empty = QLabel("No ideas yet. They arrive from the \U0001f4a1 button in everyone's panel.")
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
            self.admin_inbox.addWidget(empty)
        for item in inbox[:15]:
            self.admin_inbox.addWidget(IdeaRow(item, theme, logic.open_link))
        _clear_layout(self.admin_prospects)
        people = data.get("prospects") or []
        if not people:
            empty = QLabel("No prospects yet: click Refresh.")
            empty.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
            self.admin_prospects.addWidget(empty)
        for person in people[:25]:
            self.admin_prospects.addWidget(ProspectCard(person, theme, self._on_prospect_action, self.avatar_loader))
        updated = data.get("fetched_at")
        if not getattr(self, "_admin_running", False):
            self.admin_updated.setText("updated " + _time_ago(updated) if updated else "")
        rows = data.get("keyword_requests") or []
        if rows:
            listed = " · ".join(
                f"<b>{html.escape(r['word'])}</b> <span style='color:{theme['muted']}'>"
                + (f"{r['people']} on Signals" if r["people"] else "")
                + (", " if r["people"] and r["suggested"] else "")
                + (f"{r['suggested']} suggested" if r["suggested"] else "") + "</span>"
                for r in rows[:30])
            self.admin_kw.setText(f"{listed}<br><span style='color:{theme['muted']}'>Teach them: run "
                                  "<code>mygeeky admin keywords build</code>, then publish a release.</span>")
        else:
            self.admin_kw.setText(f"<span style='color:{theme['muted']}'>No unknown keywords yet. They come "
                                  "from beacons and from the suggest button.</span>")
        self.admin_kw.setStyleSheet(f"color:{theme['text']}; font-size:10.5px; background:transparent;")
        self._render_scout()
        self._render_quizwriter()
        self.admin_highlights.render()
        self._render_admin_summary(theme, data)
        for lbl in self.admin_headers + [self.admin_kw_header, self.admin_scout_header, self.admin_quiz_header,
                                         self.admin_hl_header, self.admin_write_header, self.admin_import_header]:
            lbl.setStyleSheet(f"color:{theme['text']}; font-size:10.5px; font-weight:700; letter-spacing:0.5px; "
                              "margin-top:6px; background:transparent;")
        for lbl in (self.admin_funnel, self.admin_hint, self.admin_updated, self.admin_calls, self.admin_waiting, self.admin_wisep,
                    self.admin_settings_note):
            lbl.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
        self.admin_refresh_btn.setStyleSheet(
            f"QPushButton {{ background:{theme['section_btn']}; color:{theme['text']}; border:none; "
            f"border-radius:8px; padding:6px 10px; font-size:11.5px; }}")
        self.admin_undo_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{theme['link']}; border:none; padding:4px 6px; "
            f"font-size:11px; text-decoration:underline; }}")

    def _render_admin_summary(self, theme: dict[str, Any], data: dict[str, Any]) -> None:
        """Each section's heading with its count, what's waiting, and exactly what Publish would send."""
        from .. import highlights
        st = logic.scout_state()
        drafts = highlights.drafts("new")
        quiz = [pid for pid, b in (logic.quizwriter_state().get("batches") or {}).items() if not b.get("verdict")]
        counts = {"overview": "", "review": f"{len(st['new']) + len(drafts) + len(quiz)} waiting",
                  "write": "", "inbox": f"{len(data.get('inbox') or [])} ideas",
                  "people": f"{len(data.get('prospects') or [])} to consider", "settings": ""}
        for p, label, emoji in ADMIN_PARTS:
            head = self.admin_section_heads[p]
            head.setText(f"{emoji} {label.upper()}" + (f"  ·  {counts[p]}" if counts[p] else ""))
            head.setStyleSheet(f"color:{theme['text']}; font-size:13px; font-weight:800; background:transparent;")
        going = [f"{self.SCOUT_EMOJI.get(c['kind'], '')} {c['item']['title']}" for c in st["accepted"]] + \
                [f"✨ {d['item']['title']}" for d in highlights.accepted()]
        self.admin_waiting.setText(
            f"Waiting for you in Review: {len(st['new'])} listings, {len(drafts)} Highlights, {len(quiz)} quiz batches."
            + ("\n\nPublish would send these to everyone's lists:\n" + "\n".join(f"  {g}" for g in going[:20])
               + (f"\n  …and {len(going) - 20} more" if len(going) > 20 else "") if going
               else "\n\nNothing accepted yet, so Publish has nothing to send."))
        self.admin_publish_btn.setText(f"🚀 Publish {len(going)} to mygeeky.org" if going else "🚀 Publish")
        from .wisep_ui import summary as wisep_summary
        self.admin_wisep.setText("WISEP (every user has their own; yours is in ⚙ Settings → Data & privacy → How myGeeKy asks the "
                                 "internet): " + wisep_summary())
        self.admin_publish_btn.setEnabled(bool(going) and not getattr(self, "_scout_publishing", False))
        self.admin_publish_btn.setStyleSheet(
            f"QPushButton {{ background:{theme['accent'] if going else theme['section_btn']}; color:{theme['text']}; "
            "border:none; border-radius:8px; padding:6px 12px; font-size:11.5px; font-weight:700; }")
        self.admin_settings_note.setText(
            ("DeepSeek key: kept in this computer's credential store. " if st["has_key"] else
             "No DeepSeek key yet: the scout and the writers need one (✍ Write → Bring your own answer doesn't). ")
            + "Sites and field decide where the scout looks.")
        for b in self.admin_settings_btns:
            b.setStyleSheet(f"QPushButton {{ background:{theme['section_btn']}; color:{theme['text']}; border:none; "
                            "border-radius:8px; padding:6px 10px; font-size:11.5px; }")
        self.admin_import.apply_theme()

    def _set_admin_part(self, part: str) -> None:
        self._admin_part = part if part in {p for p, *_ in ADMIN_PARTS} else "overview"
        self._show_admin_part()
        self._nav_mark()

    def _show_admin_part(self) -> None:
        for p, box in getattr(self, "admin_sections", {}).items():
            box.setVisible(p == self._admin_part)

    def _on_forget_cache(self) -> None:
        n = logic.forget_github_cache()
        self._info("GitHub cache", f"{n} remembered answer{'s' if n != 1 else ''} thrown away. Nothing is lost: "
                                   "the next refresh asks GitHub for them again.")
        self._render_admin()

    # ---- 📝 quizzes (quizwriter.py): DeepSeek writes them from each protocol's own sources, myGeeKy
    # checks them, and the maker only reads five
    def _render_quizwriter(self) -> None:
        from .growth_ui import _label, _muted
        theme = THEMES[self._theme_name()]
        area = self.admin_quiz
        _clear_layout(area)
        st = logic.quizwriter_state()
        missing = st.get("missing") or []
        done = not missing
        head = (f"✅ All {st['protocols']} reviewed protocols have a quiz — {st['bank']} questions in all. "
                "Nothing to do here unless you want more."
                if done else
                f"{st['with_quiz']} of {st['protocols']} protocols have a quiz ({st['bank']} questions). "
                f"{len(missing)} still to write.")
        area.addWidget(_label(head, f"color:{theme['good'] if done else theme['text']}; font-size:11px; "
                                    "background:transparent;"))
        area.addWidget(_label("Writing more is optional: DeepSeek drafts them from a protocol's own links and must "
                              "quote the sentence that proves the answer; myGeeKy checks the quote is on the page, "
                              "runs the code, and a blind second read has to agree. You read five. Writing by hand "
                              "is the other way: tools/quiz/sources.py, then tools/quiz/add.py.",
                              _muted(theme, 10.5)))
        if not st["has_key"]:
            area.addWidget(_label("Add your DeepSeek key in ⚙ Settings: the writer uses the same key. Or paste questions written elsewhere in ✍ Write.",
                                  _muted(theme, 10.5)))
            return
        running = getattr(self, "_quizwriter_running", "")
        note = getattr(self, "_quizwriter_note", "")
        if note:
            area.addWidget(_label(note, _muted(theme, 10.5)))
        # Only what wants doing. Every protocol used to get its own row and its own button, so once they
        # all had enough -- fourteen here -- the tab became fourteen identical "More questions" buttons
        # sitting under a heading that said there was nothing to do. The settled ones fold into one line.
        waiting, settled = [], []
        for p in self._reviewed_protocols():
            n = sum((st["per_protocol"].get(p["id"]) or {}).values())
            batch = (st["batches"] or {}).get(p["id"]) or {}
            spot_check_due = bool(batch.get("questions") and not batch.get("verdict"))
            (waiting if n < st["ready"] or spot_check_due else settled).append(p)
        for p in waiting:
            area.addWidget(self._quiz_row(p, st, running, theme))
        if settled:
            area.addWidget(self._quiz_settled_line(settled, st, theme))
            if getattr(self, "_quiz_show_settled", False):
                for p in settled:
                    area.addWidget(self._quiz_row(p, st, running, theme))

    def _quiz_settled_line(self, settled: list[dict[str, Any]], st: dict[str, Any], theme: dict[str, Any]):
        """One line standing in for every protocol that needs nothing, with a way to open them anyway."""
        from .growth_ui import FlowRow, _label, _muted, _pill_button
        good = sum(1 for p in settled
                   if sum((st["per_protocol"].get(p["id"]) or {}).values()) >= st["good"])
        open_ = getattr(self, "_quiz_show_settled", False)
        row = FlowRow()
        row.add(_label(f"✅ {len(settled)} already have enough" + (f", {good} a good bank" if good else ""),
                       _muted(theme, 10.5), wrap=False))
        row.add(_pill_button("Hide them" if open_ else "Show them",
                             "These need nothing — open them only to write more questions anyway",
                             theme, self._on_quiz_toggle_settled))
        row.finish()
        return row

    def _on_quiz_toggle_settled(self) -> None:
        self._quiz_show_settled = not getattr(self, "_quiz_show_settled", False)
        self._render_quizwriter()

    def _quiz_row(self, p: dict[str, Any], st: dict[str, Any], running: str, theme: dict[str, Any]):
        from .growth_ui import FlowRow, _label, _muted, _pill_button
        pid = p["id"]
        have = st["per_protocol"].get(pid) or {}
        n = sum(have.values())
        batch = (st["batches"] or {}).get(pid) or {}
        mix = " · ".join(f"{have.get(lv, 0)} {lv}" for lv in ("easy", "medium", "tricky") if have.get(lv))
        # ✓ it can be taken (enough for an attempt), ✦ a good bank, ○ not enough yet
        mark, colour = ("○", theme["muted"]) if n < st["ready"] else \
            (("✓", theme["good"]) if n < st["good"] else ("✦", theme["good"]))
        row = FlowRow()
        # wrap=False, or the flow layout gives a wrapping label the whole line and the count and the
        # button are pushed off it -- these are short chips meant to sit side by side.
        row.add(_label(f"{mark} {_short(p['title'], 34)}",
                       f"color:{colour if n < st['ready'] else theme['text']}; font-size:10.5px; "
                       "background:transparent;", wrap=False))
        row.add(_label(f"{n} questions" + (f" ({mix})" if mix else ""), _muted(theme, 10), wrap=False))
        if batch.get("questions") and not batch.get("verdict"):
            row.add(_pill_button(f"👀 Spot-check {len(batch['spot_check'])}",
                                 "Read a few questions; one 👎 rewrites the batch", theme,
                                 lambda pid=pid: self._on_quiz_spot_check(pid), accent=True))
        else:
            write = _pill_button("Writing…" if running == pid else
                                 ("📝 Write questions" if n < st["ready"] else "➕ More"),
                                 "Asks DeepSeek, then checks every question (a few minutes). "
                                 "Optional once a protocol has enough to be taken.", theme,
                                 lambda pid=pid: self._on_quizwriter_run(pid))
            write.setEnabled(not running)
            row.add(write)
        row.finish()
        return row

    def _reviewed_protocols(self) -> list[dict[str, Any]]:
        from .. import curated, protocols
        return [{"id": x["id"], "title": x["title"]} for x in protocols.reviewed(curated.load())]

    def _on_quizwriter_run(self, pid: str) -> None:
        self._quizwriter_running = pid
        self._quizwriter_note = "Reading each source page and asking DeepSeek…"
        self._render_quizwriter()
        self._run_async(lambda: logic.quizwriter_run(self.cfg, pid),
                        lambda r: self._on_quizwriter_done(pid, r))

    def _on_quizwriter_done(self, pid: str, result: Any) -> None:
        self._quizwriter_running = ""
        result = result or {}
        if result.get("error"):
            self._quizwriter_note = ""
            self._info("Write questions", result["error"])
        else:
            why = "; ".join(f"{n}x {reason}" for reason, n in (result.get("reasons") or [])[:3])
            self._quizwriter_note = result.get("summary", "") + (f" - {why}" if why else "")
        self._render_quizwriter()

    def _on_quiz_spot_check(self, pid: str) -> None:
        """The maker's whole review: a few questions, 👍 or 👎 each. One 👎 and the batch is rewritten."""
        from .. import quizwriter
        from ..quiz import Question
        from .growth_ui import QuestionCard
        theme = THEMES[self._theme_name()]
        batch = (quizwriter.load()["batches"] or {}).get(pid) or {}
        wanted = set(batch.get("spot_check") or [])
        rows = [q for q in batch.get("questions") or [] if q["id"] in wanted]
        if not rows:
            self._info("Spot check", "Nothing to check for this protocol.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Spot check: {pid}")
        dlg.setStyleSheet(self._dialog_css())
        dlg.setMinimumWidth(480)
        outer = QVBoxLayout(dlg)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        holder = QWidget()
        body = QVBoxLayout(holder)
        scroll.setWidget(holder)
        outer.addWidget(scroll, 1)
        verdicts: dict[str, bool] = {}

        def marker(qid, good_btn, bad_btn):
            def mark(ok: bool) -> None:
                verdicts[qid] = ok
                good_btn.setChecked(ok)
                bad_btn.setChecked(not ok)
            return mark

        for raw in rows:
            q = Question.build(raw, 0, len(rows))
            q.picked = q.answer            # shown answered, so the reason and the source show too
            body.addWidget(QuestionCard(q, theme, lambda i: None, logic.open_link, locked=True))
            if raw.get("needs_eyes"):
                body.addWidget(QLabel("! the checks did not fully agree on this one"))
            good = QPushButton("👍 fine")
            bad = QPushButton("👎 wrong")
            for b in (good, bad):
                b.setCursor(Qt.PointingHandCursor)
                b.setCheckable(True)
            mark = marker(raw["id"], good, bad)
            good.clicked.connect(lambda checked=False, f=mark: f(True))
            bad.clicked.connect(lambda checked=False, f=mark: f(False))
            line = QHBoxLayout()
            line.addWidget(good)
            line.addWidget(bad)
            line.addStretch(1)
            holder_row = QWidget()
            holder_row.setLayout(line)
            body.addWidget(holder_row)
        body.addStretch(1)
        bar = QHBoxLayout()
        bar.addStretch(1)
        later = QPushButton("Later")
        done = QPushButton("Accept the batch")
        later.clicked.connect(dlg.reject)
        done.clicked.connect(dlg.accept)
        bar.addWidget(later)
        bar.addWidget(done)
        outer.addLayout(bar)
        if dlg.exec() != QDialog.Accepted:
            return
        if len(verdicts) < len(rows):
            self._info("Spot check", "Mark each question 👍 or 👎 first.")
            return
        if all(verdicts.values()):
            out = logic.quizwriter_accept(pid, "accepted")
            self._info("Spot check", out.get("error") or
                       f"{out.get('added', 0)} questions added to the bank ({out.get('total', 0)} in all). "
                       "Commit data/questions.json when you're ready.")
        else:
            logic.quizwriter_accept(pid, "rewrite")
            self._info("Spot check", "Thrown away: a question you marked 👎 means the whole batch is suspect. "
                                     "Press 📝 Write questions again for a fresh one.")
        self._render_quizwriter()

    # ---- 🎯 listings to review (scout.py): found with DeepSeek, checked, accepted by you, then published
    SCOUT_EMOJI = {"jobs": "💼", "funding": "💶", "conferences": "🎤"}

    def _render_scout(self) -> None:
        from .growth_ui import FlowRow, _label, _muted, _pill_button, _small_button, deadline_text
        theme = THEMES[self._theme_name()]
        area = self.admin_scout
        _clear_layout(area)
        st = logic.scout_state()
        tools = FlowRow()
        key_ok = st["has_key"]
        if not key_ok:                                 # the key and the sites live in ⚙ Settings
            tools.add(_pill_button("🔑 Add DeepSeek key", "Kept in this computer's credential store, never in a file",
                                   theme, self._on_scout_key))
        paste = _pill_button("📋 Paste a page", "For a site myGeeKy can't read: open it yourself and paste "
                             "the text", theme, self._on_scout_paste)
        paste.setEnabled(key_ok and not getattr(self, "_scout_running", False))
        tools.add(paste)
        box = logic.scout_mailbox()
        ready = bool(box.get("address")) and box.get("has_password")
        alerts = _pill_button("📧 Read my alerts" if ready else "📧 Set up my alerts",
                              "Reads the job-alert emails in one folder of your mailbox, read-only",
                              theme, self._on_scout_alerts)
        alerts.setEnabled(key_ok and not getattr(self, "_scout_running", False))
        tools.add(alerts)
        running = getattr(self, "_scout_running", False)
        find = _pill_button("Looking…" if running else "🔎 Find new listings",
                            "Reads the sites, asks DeepSeek, checks every answer (a few minutes)", theme,
                            self._on_scout_find, accent=key_ok and not running)
        find.setEnabled(key_ok and not running)
        tools.add(find)
        from .. import highlights
        n_acc = len(st["accepted"]) + len(highlights.accepted())
        pub = _pill_button(f"🚀 Publish {n_acc} to mygeeky.org" if n_acc else "🚀 Publish",
                           "Adds what you accepted to everyone's lists", theme, self._on_scout_publish, accent=n_acc > 0)
        pub.setEnabled(n_acc > 0 and not getattr(self, "_scout_publishing", False))
        tools.add(pub)
        area.addWidget(tools)
        note = getattr(self, "_scout_note", "") or st.get("last_run_text", "")
        if note:
            area.addWidget(_label(note, _muted(theme, 10.5)))
        if not key_ok:
            area.addWidget(_label("Add your DeepSeek key to start. It reads job, funding and conference pages on the "
                                  "sites you choose; myGeeKy checks every answer against the page; you accept what "
                                  "goes online.", _muted(theme, 10.5)))
        for c in st["accepted"]:
            row = QHBoxLayout()
            row.addWidget(_label(f"✅ {self.SCOUT_EMOJI.get(c['kind'], '')} {c['item']['title']}",
                                 f"color:{theme['good']}; font-size:10.5px; background:transparent;"), 1)
            row.addWidget(_small_button("Undo", "Back to the list to review", theme,
                                        lambda cid=c["id"]: self._on_scout_status(cid, "new")))
            area.addLayout(row)
        for c in st["new"][:40]:
            area.addWidget(self._scout_card(c, theme, _label, _muted, _pill_button, deadline_text))
        if key_ok and not st["new"] and not running:
            area.addWidget(_label("Nothing to review. Press 🔎 Find new listings.", _muted(theme, 10.5)))

    def _scout_card(self, c, theme, _label, _muted, _pill_button, deadline_text) -> QFrame:
        it = c["item"]
        card = QFrame()
        card.setObjectName("scoutCard")
        card.setStyleSheet(f"QFrame#scoutCard {{ background:{theme['card_bg']}; border-radius:10px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)
        sure = round(100 * c.get("score", 0))
        color = theme["good"] if sure >= 70 else theme["warn"] if sure >= 45 else theme["bad"]
        head = QHBoxLayout()
        title = _label(f"<b>{self.SCOUT_EMOJI.get(c['kind'], '')} {html.escape(it['title'])}</b>",
                       f"color:{theme['text']}; font-size:12px; background:transparent;", rich=True)
        title.setCursor(Qt.PointingHandCursor)
        title.setToolTip(_tip(it["url"]))
        title.mousePressEvent = lambda ev, u=it["url"]: logic.open_link(u)  # noqa: ARG005
        head.addWidget(title, 1)
        head.addWidget(_label(f"{sure}% sure", f"color:{color}; background:{color}22; border-radius:7px; "
                                                "padding:1px 7px; font-size:10px; font-weight:700;", wrap=False), 0, Qt.AlignTop)
        lay.addLayout(head)
        facts = [it.get("org", ""), it.get("place", ""), deadline_text(c.get("days_left")),
                 f"deadline {it.get('deadline', '')}", it.get("amount", ""), it.get("who", "")]
        lay.addWidget(_label(" · ".join(f for f in facts if f), _muted(theme, 10.5)))
        if it.get("summary"):
            lay.addWidget(_label(it["summary"], f"color:{theme['text']}; font-size:10.5px; background:transparent;"))
        if c.get("quote"):
            lay.addWidget(_label(f"“{c['quote']}”", f"color:{theme['muted']}; font-size:10px; font-style:italic; "
                                                    "background:transparent;"))
        checks = "   ".join(("✓ " if ok else "✗ ") + t for ok, t in c.get("checks") or [])
        lay.addWidget(_label(f"{checks}   · from {c.get('source', '')}", _muted(theme, 9.5)))
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(_pill_button("✓ Accept", "Goes online when you press Publish", theme,
                                   lambda: self._on_scout_status(c["id"], "accepted"), accent=True))
        row.addWidget(_pill_button("✏️ Edit", "Fix a field, then accept", theme, lambda: self._on_scout_edit(c)))
        row.addWidget(_pill_button("✕ Reject", "Never offered again", theme,
                                   lambda: self._on_scout_status(c["id"], "rejected")))
        row.addStretch(1)
        lay.addLayout(row)
        return card

    def _on_scout_key(self) -> None:
        key = self._ask_text("DeepSeek key", "Paste your DeepSeek API key (it starts with sk-). It's kept in this "
                             "computer's credential store, never in a file:", echo=QLineEdit.Password)
        if key:
            if not logic.scout_set_key(key):
                self._info("DeepSeek key", "That doesn't look like a DeepSeek key (they start with sk-).")
            self._render_scout()

    def _on_scout_sites(self) -> None:
        from PySide6.QtWidgets import QPlainTextEdit
        st = logic.scout_state()
        dlg = QDialog(self)
        dlg.setWindowTitle("Sites and field")
        dlg.setStyleSheet(self._dialog_css() + "QPlainTextEdit { background:#2a2640; color:#f0f0f5; border-radius:6px; }")
        dlg.resize(560, 460)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Your field (what counts as relevant):"))
        focus = QLineEdit(st["focus"])
        lay.addWidget(focus)
        intro = QLabel("Sites, one per line: kind | name | link. Kind is jobs, funding or conferences. "
                       "Put # in front of a line to skip that site.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        box = QPlainTextEdit("\n".join(f"{'' if s.get('on', True) else '# '}{s['kind']} | {s['name']} | {s['url']}"
                                       for s in st["sources"]))
        lay.addWidget(box, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel, ok = QPushButton("Cancel"), QPushButton("Save")
        cancel.clicked.connect(dlg.reject)
        ok.clicked.connect(dlg.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)
        if dlg.exec() != QDialog.Accepted:
            return
        sources = []
        for line in box.toPlainText().splitlines():
            on = not line.strip().startswith("#")
            parts = [p.strip() for p in line.strip().lstrip("#").split("|")]
            if len(parts) == 3:
                sources.append({"kind": parts[0].lower(), "name": parts[1], "url": parts[2], "on": on})
        logic.scout_set_sources(sources, focus.text())
        self._render_scout()

    def _on_scout_alerts(self) -> None:
        """Read the alerts, or ask for the mailbox first if it has not been set up."""
        box = logic.scout_mailbox()
        if not box.get("address") or not box.get("has_password"):
            self._on_scout_mailbox()
            return
        kind = self._ask_kind("Read my alerts", "Which kind of listing are these alerts about?")
        if not kind:
            return
        self._scout_running = True
        self._scout_note = f"Reading the alerts in {box.get('folder', 'INBOX')}…"
        self._render_scout()
        self._run_async(lambda: logic.scout_from_alerts(self.cfg, kind), self._on_scout_alerted)

    def _on_scout_alerted(self, out: Any) -> None:
        self._scout_running = False
        out = out if isinstance(out, dict) else {}
        if out.get("error"):
            self._scout_note = out["error"]
        else:
            said = (f"{out.get('messages', 0)} alert(s) · read {out.get('read', 0)} listing(s) · "
                    f"{out.get('added', 0)} to review · {out.get('dropped', 0)} dropped by the checks")
            if out.get("why"):
                said += " — " + "; ".join(out["why"][:3])
            self._scout_note = said
        self._render_scout()

    def _on_scout_mailbox(self) -> None:
        """Where the alerts are, and the password to get at them.

        myGeeKy opens ONE folder, read-only. The point of the folder is that a mail filter decides what
        lands in it: if the filter is wrong myGeeKy sees nothing, rather than everything."""
        box = logic.scout_mailbox()
        dlg = QDialog(self)
        dlg.setWindowTitle("My job alerts")
        dlg.setStyleSheet(self._dialog_css())
        dlg.resize(540, 400)
        lay = QVBoxLayout(dlg)
        intro = QLabel("Nature Careers, Science Careers, jobs.ac.uk and EURAXESS will email you their "
                       "listings — and so will LinkedIn, Indeed and Glassdoor, which won't let myGeeKy "
                       "read their sites. Subscribe to their alerts, then:\n\n"
                       "1. Make a mail filter that sends those alerts to their own label or folder.\n"
                       "2. Point myGeeKy at that folder. It opens nothing else, and only ever reads — it "
                       "cannot mark, move or delete your mail.\n"
                       "3. For Gmail, make an App Password (Google Account → Security → App passwords). "
                       "Your everyday password will not work, and an App Password can be revoked on its "
                       "own.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        lay.addWidget(QLabel("Your email address:"))
        address = QLineEdit(box.get("address", ""))
        address.setPlaceholderText("you@gmail.com")
        lay.addWidget(address)
        lay.addWidget(QLabel("The folder or label the alerts land in:"))
        folder = QLineEdit(box.get("folder", "INBOX"))
        folder.setPlaceholderText("myGeeKy-alerts")
        lay.addWidget(folder)
        lay.addWidget(QLabel("Mail server (left empty, myGeeKy works it out):"))
        host = QLineEdit(box.get("host", ""))
        host.setPlaceholderText(box.get("guessed_host", "") or "imap.example.com")
        lay.addWidget(host)
        note = QLabel("Password: kept in this computer's credential store, never in a file."
                      if not box.get("has_password") else
                      "Password: already kept in this computer's credential store.")
        note.setWordWrap(True)
        lay.addWidget(note)
        row = QHBoxLayout()
        pw = QPushButton("Change the password" if box.get("has_password") else "Add the password")
        pw.clicked.connect(lambda: self._ask_mail_password(note))
        row.addWidget(pw)
        if box.get("has_password"):
            forget = QPushButton("Forget it")
            forget.clicked.connect(lambda: (logic.scout_forget_mail_password(),
                                            note.setText("Password: forgotten.")))
            row.addWidget(forget)
        row.addStretch(1)
        shut = QPushButton("Cancel")
        shut.clicked.connect(dlg.reject)
        save = QPushButton("Save")
        save.setDefault(True)
        save.clicked.connect(dlg.accept)
        row.addWidget(shut)
        row.addWidget(save)
        lay.addLayout(row)
        if dlg.exec() == QDialog.Accepted:
            logic.scout_mailbox(address.text().strip(), host.text().strip(), folder.text().strip())
            self._render_scout()

    def _ask_mail_password(self, note: QLabel) -> None:
        got = self._ask_text("Mailbox password", "For Gmail this is an App Password, not your everyday "
                             "one. It is kept in this computer's credential store:",
                             echo=QLineEdit.Password)
        if got:
            ok = logic.scout_set_mail_password(got)
            note.setText("Password: kept in this computer's credential store." if ok else
                         "That looks too short to be a password.")

    def _ask_kind(self, title: str, question: str) -> str:
        """Which list something belongs to. The checks differ by kind, so it cannot be guessed."""
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setStyleSheet(self._dialog_css())
        lay = QVBoxLayout(dlg)
        label = _plain(QLabel(question))
        label.setWordWrap(True)
        lay.addWidget(label)
        picker = QComboBox()
        for value, said in (("jobs", "💼 Jobs, PhD places and postdocs"), ("funding", "💶 Funding and grants"),
                            ("conferences", "🎤 Conferences and courses")):
            picker.addItem(said, value)
        picker.setStyleSheet(self._combo_css())
        lay.addWidget(picker)
        row = QHBoxLayout()
        row.addStretch(1)
        shut = QPushButton("Cancel")
        shut.clicked.connect(dlg.reject)
        go = QPushButton("Read them")
        go.setDefault(True)
        go.clicked.connect(dlg.accept)
        row.addWidget(shut)
        row.addWidget(go)
        lay.addLayout(row)
        return str(picker.currentData()) if dlg.exec() == QDialog.Accepted else ""

    def _combo_css(self) -> str:
        from .growth_ui import combo_style
        return combo_style(THEMES[self._theme_name()])

    def _on_scout_paste(self) -> None:
        """A page the maker copied out of their browser, read as if myGeeKy had fetched it.

        Indeed, SimplyHired, Monster, ZipRecruiter and CareerBuilder all refuse a robot outright; LinkedIn
        and Glassdoor answer but forbid it; SuccessFactors portals answer with an empty shell. This is how
        a listing from any of them gets in, without myGeeKy pretending to be a browser."""
        from PySide6.QtWidgets import QPlainTextEdit
        dlg = QDialog(self)
        dlg.setWindowTitle("Paste a page")
        dlg.setStyleSheet(self._dialog_css()
                          + "QPlainTextEdit { background:#2a2640; color:#f0f0f5; border-radius:6px; }")
        dlg.resize(600, 520)
        lay = QVBoxLayout(dlg)
        intro = QLabel("For a site myGeeKy can't read by itself. Open the page in your browser, select "
                       "all of it, copy, and paste it below. One listing's own page works much better "
                       "than a page of search results.\n\nNothing is fetched, so nothing can block it — "
                       "and the checks are unchanged: the deadline sentence still has to be in what you "
                       "paste, word for word.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        lay.addWidget(QLabel("What is it?"))
        kind = QComboBox()
        for value, label in (("jobs", "💼 A job, PhD place or postdoc"), ("funding", "💶 Funding or a grant"),
                             ("conferences", "🎤 A conference or course")):
            kind.addItem(label, value)
        lay.addWidget(kind)
        lay.addWidget(QLabel("The page's link (so each listing has somewhere to point at):"))
        url = QLineEdit()
        url.setPlaceholderText("https://…")
        lay.addWidget(url)
        lay.addWidget(QLabel("The page, pasted:"))
        body = QPlainTextEdit()
        body.setPlaceholderText("Paste the whole page here…")
        lay.addWidget(body, 1)
        note = QLabel("")
        note.setWordWrap(True)
        lay.addWidget(note)
        row = QHBoxLayout()
        row.addStretch(1)
        shut = QPushButton("Cancel")
        shut.clicked.connect(dlg.reject)
        read = QPushButton("Read it")
        read.setDefault(True)

        def go() -> None:
            text, link = body.toPlainText().strip(), url.text().strip()
            if len(text) < 200:
                note.setText("That looks too short to be a page. Copy the whole listing and paste it again.")
                return
            if not link.startswith("https://"):
                note.setText("Paste the page's https link too, so each listing has somewhere to point at.")
                return
            dlg.accept()
            self._scout_running = True
            self._scout_note = "Reading what you pasted and checking every listing against it…"
            self._render_scout()
            chosen = kind.currentData()
            self._run_async(lambda: logic.scout_from_paste(self.cfg, chosen, text, link),
                            self._on_scout_pasted)

        read.clicked.connect(go)
        row.addWidget(shut)
        row.addWidget(read)
        lay.addLayout(row)
        dlg.exec()

    def _on_scout_pasted(self, out: Any) -> None:
        self._scout_running = False
        out = out if isinstance(out, dict) else {}
        if out.get("error"):
            self._scout_note = out["error"]
        else:
            said = (f"Found {out.get('found', 0)} in what you pasted · {out.get('added', 0)} to review · "
                    f"{out.get('dropped', 0)} dropped by the checks")
            if out.get("why"):
                said += " — " + "; ".join(out["why"][:3])
            self._scout_note = said
        self._render_scout()

    def _on_scout_find(self) -> None:
        self._scout_running = True
        self._scout_note = "Reading the sites and checking every listing. This takes a few minutes…"
        self._render_scout()
        self._run_async(lambda: logic.scout_find(self.cfg), self._on_scout_found)

    def _on_scout_found(self, out: Any) -> None:
        self._scout_running = False
        out = out if isinstance(out, dict) else {}
        if out.get("error"):
            self._scout_note = out["error"]
        else:
            self._scout_note = (f"Found {out.get('added', 0)} to review · {out.get('dropped', 0)} dropped by the checks"
                                + (f" · couldn't read: {', '.join(out['errors'])}" if out.get("errors") else ""))
        self._render_scout()

    def _on_scout_status(self, cid: str, status: str) -> None:
        logic.scout_set_status(cid, status)
        self._render_scout()

    def _on_scout_edit(self, c: dict[str, Any]) -> None:
        it = c["item"]
        fields = ["title", "org", "place", "deadline"] + {
            "jobs": ["type"], "funding": ["who", "amount"], "conferences": ["starts", "ends", "student"]}[c["kind"]] + \
            ["url", "summary"]
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit, then accept")
        dlg.setStyleSheet(self._dialog_css())
        dlg.resize(520, 0)
        lay = QVBoxLayout(dlg)
        edits = {}
        for f in fields + ["keywords"]:
            lay.addWidget(QLabel(f.capitalize() + (" (YYYY-MM-DD)" if f in ("deadline", "starts", "ends") else
                                                   " (comma separated)" if f == "keywords" else "")))
            e = QLineEdit(", ".join(it.get(f) or []) if f == "keywords" else str(it.get(f) or ""))
            lay.addWidget(e)
            edits[f] = e
        row = QHBoxLayout()
        row.addStretch(1)
        cancel, ok = QPushButton("Cancel"), QPushButton("Accept")
        cancel.clicked.connect(dlg.reject)
        ok.clicked.connect(dlg.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)
        if dlg.exec() != QDialog.Accepted:
            return
        changed = {f: e.text().strip() for f, e in edits.items()}
        changed["keywords"] = [k.strip() for k in changed["keywords"].split(",") if k.strip()]
        if not logic.scout_set_status(c["id"], "accepted", changed):
            self._info("Edit", "Something isn't right: the link must start with https:// and dates look like 2026-12-31.")
        self._render_scout()

    def _on_scout_publish(self) -> None:
        from .. import highlights
        st, n_hl = logic.scout_state(), len(highlights.accepted())
        what = " and ".join(x for x in (f"{len(st['accepted'])} listing(s) to everyone's Chances" if st["accepted"] else "",
                                        f"{n_hl} Highlight(s) to Grow" if n_hl else "") if x)
        from urllib.parse import urlsplit
        going = [(c["item"].get("title", ""), c["item"].get("url", "")) for c in st["accepted"]]
        going += [(h.get("title", ""), h.get("url", "")) for h in highlights.accepted()]
        listed = "\n".join(f"• {t[:70]}  →  {urlsplit(u).hostname or '?'}" for t, u in going[:15])
        more = f"\n…and {len(going) - 15} more" if len(going) > 15 else ""
        box = self._box("Publish to mygeeky.org",
                        f"Add {what}?\n\n{listed}{more}\n\n"
                        "Check each link goes where it should. This makes one commit to the curated lists on GitHub "
                        "(main), with your own git login. Every myGeeKy shows them within a few hours. Each one "
                        "disappears after its deadline.")
        go = box.addButton("Publish", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        if box.clickedButton() is not go:
            return
        self._scout_publishing = True
        self._scout_note = "Publishing…"
        self._render_scout()
        self._run_async(logic.scout_publish, self._on_scout_published)

    def _on_scout_published(self, out: Any) -> None:
        self._scout_publishing = False
        out = out if isinstance(out, dict) else {}
        self._scout_note = out.get("error") or f"Published {out.get('summary', '')} (commit {out.get('commit', '')})."
        self._render_scout()
        self.admin_highlights.render()

    def _refresh_admin(self) -> None:
        if getattr(self, "_admin_running", False):
            return
        self._admin_running = True
        self.admin_refresh_btn.setEnabled(False)
        self.admin_updated.setText("updating\u2026 (a minute or two)")
        self._run_async(lambda: logic.admin_refresh(self.cfg), self._on_admin_ready)

    def _on_admin_ready(self, data: Any) -> None:
        self._admin_running = False
        self.admin_refresh_btn.setEnabled(True)
        if isinstance(data, dict) and data.get("error"):
            self.admin_updated.setText(data["error"])
        self._render_admin()

    def _on_prospect_action(self, action: str, person: dict[str, Any]) -> None:
        login = person.get("login", "")
        if action == "profile":
            logic.open_link(f"https://github.com/{login}")
            return
        if action in ("email", "copy"):
            invite = logic.admin_invite(self.cfg, person)
            if action == "email" and invite.get("gmail"):
                # opening the email is inviting them: mark it now (within the daily limit)
                marked = logic.admin_mark(login, "invited")
                if not marked.get("ok"):
                    self.admin_updated.setText(marked.get("message", ""))
                    return
                QDesktopServices.openUrl(QUrl(invite["gmail"]))          # Gmail in your browser, filled in
                self._render_admin()
                self._last_invited = login
                self.admin_updated.setText(f"{login} marked as invited. Didn't send it?")
                self.admin_undo_btn.show()
            else:
                QApplication.clipboard().setText(f"{invite['subject']}\n\n{invite['body']}")
                logic.open_link(f"https://github.com/{login}")
                self.admin_updated.setText(f"Invite for {login} copied: paste it wherever you reach them.")
            return
        result = logic.admin_mark(login, action)
        if not result.get("ok"):
            self.admin_updated.setText(result.get("message", ""))
        self._render_admin()

    def _undo_invite(self) -> None:
        login = getattr(self, "_last_invited", "")
        self.admin_undo_btn.hide()
        if login:
            logic.admin_mark(login, "new")
            self._last_invited = ""
            self.admin_updated.setText(f"{login} is back on the list.")
            self._render_admin()

    def _build_settings_panel(self) -> QFrame:
        content = QWidget()
        content.setObjectName("settingsContent")
        main = QVBoxLayout(content)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(8)
        # its pages, as on the phone: buttons to move between them (the side menu steps aside while ⚙ is open), the
        # page's name and what it holds, then the page; only the open one is shown, so ⚙ is as tall as that page
        nav = QGridLayout()
        nav.setSpacing(4)
        self.settings_nav: dict[str, QPushButton] = {}
        for i, (key, (label, icon, _about)) in enumerate(SETTINGS_PAGES.items()):
            b = QPushButton(f"{icon} {label}".replace("&", "&&"))   # a single & would underline the next letter
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _checked=False, k=key: self._show_settings_page(k))
            self.settings_nav[key] = b
            nav.addWidget(b, i // 3, i % 3)
        main.addLayout(nav)
        self.settings_title = QLabel("")
        self.settings_title.setTextFormat(Qt.PlainText)
        self.settings_about = QLabel("")
        self.settings_about.setTextFormat(Qt.PlainText)
        self.settings_about.setWordWrap(True)
        main.addWidget(self.settings_title)
        main.addWidget(self.settings_about)
        self.settings_pages: dict[str, QWidget] = {}
        pages: dict[str, QVBoxLayout] = {}
        for key in SETTINGS_PAGES:
            page = QWidget()
            pages[key] = QVBoxLayout(page)
            pages[key].setContentsMargins(0, 0, 0, 0)
            pages[key].setSpacing(8)
            self.settings_pages[key] = page
            main.addWidget(page)
        main.addStretch(1)
        self._settings_page = "accounts"

        layout = pages["look"]
        theme_row = QHBoxLayout()
        theme_label = QLabel("Theme")
        self._tour_look = theme_label                     # where the Settings tour points for "how it looks"
        theme_label.setStyleSheet("font-size:11px; font-weight:600; background:transparent;")
        theme_row.addWidget(theme_label)
        theme_row.addStretch(1)
        self.swatch_buttons: dict[str, QPushButton] = {}
        for name in ("aurora", "midnight", "frosted"):
            btn = QPushButton()
            btn.setFixedSize(17, 17)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(name.capitalize())
            btn.clicked.connect(lambda checked=False, n=name: self._on_theme_clicked(n))
            self.swatch_buttons[name] = btn
            theme_row.addWidget(btn)
        layout.addLayout(theme_row)

        opacity_row = QHBoxLayout()
        opacity_label = QLabel("Transparency")
        opacity_label.setStyleSheet("font-size:11px; font-weight:600; background:transparent;")
        self.opacity_value_label = QLabel("")
        self.opacity_value_label.setStyleSheet("font-size:10.5px; background:transparent;")
        opacity_row.addWidget(opacity_label)
        opacity_row.addStretch(1)
        opacity_row.addWidget(self.opacity_value_label)
        layout.addLayout(opacity_row)

        # The slider reads as "Transparency": 0 = no transparency (fully
        # opaque) .. 100 = the most allowed (logic.MIN_OPACITY, never invisible). That's the inverse
        # of Qt's own windowOpacity (1.0 = opaque, 0.0 = invisible), so the
        # slider's own range is always a plain 0-100 regardless of the
        # opacity bounds in app.py -- see _slider_to_opacity/_opacity_to_slider.
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setCursor(Qt.PointingHandCursor)
        self.opacity_slider.setValue(self._opacity_to_slider(self.cfg.gui_opacity))
        self.opacity_slider.valueChanged.connect(self._on_opacity_preview)
        # a drag sends a value for nearly every pixel, and each opacity change makes the system
        # redraw the whole see-through window: apply the latest one at most ~30 times a second
        self._opacity_timer = QTimer(self)
        self._opacity_timer.setSingleShot(True)
        self._opacity_timer.setInterval(33)
        self._opacity_timer.timeout.connect(self._apply_opacity_preview)
        self.opacity_slider.sliderReleased.connect(self._on_opacity_committed)
        layout.addWidget(self.opacity_slider)

        height_row = QHBoxLayout()
        height_label = QLabel("Panel height")
        height_label.setStyleSheet("font-size:11px; font-weight:600; background:transparent;")
        self.height_value_label = QLabel("")
        self.height_value_label.setStyleSheet("font-size:10.5px; background:transparent;")
        height_row.addWidget(height_label)
        height_row.addStretch(1)
        height_row.addWidget(self.height_value_label)
        layout.addLayout(height_row)
        self.height_slider = QSlider(Qt.Horizontal)
        self.height_slider.setRange(int(logic.MIN_PANEL_HEIGHT * 100), int(logic.MAX_PANEL_HEIGHT * 100))
        self.height_slider.setCursor(Qt.PointingHandCursor)
        self.height_slider.setToolTip("How much of the screen's height the open panel takes "
                                      "(you can also drag its bottom edge)")
        self.height_slider.setValue(int(round(logic.clamp_panel_height(self.cfg.gui_panel_height_fraction) * 100)))
        self.height_value_label.setText(f"{self.height_slider.value()}% of the screen")
        self.height_slider.valueChanged.connect(self._on_height_preview)
        self.height_slider.sliderReleased.connect(self._on_height_committed)
        layout.addWidget(self.height_slider)

        width_row = QHBoxLayout()
        width_label = QLabel("Panel width")
        width_label.setStyleSheet("font-size:11px; font-weight:600; background:transparent;")
        self.width_value_label = QLabel("")
        self.width_value_label.setStyleSheet("font-size:10.5px; background:transparent;")
        width_row.addWidget(width_label)
        width_row.addStretch(1)
        width_row.addWidget(self.width_value_label)
        layout.addLayout(width_row)
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(logic.MIN_PANEL_WIDTH, logic.MAX_PANEL_WIDTH)
        self.width_slider.setSingleStep(10)
        self.width_slider.setPageStep(40)
        self.width_slider.setCursor(Qt.PointingHandCursor)
        self.width_slider.setToolTip("How wide the open panel is (you can also drag its inner edge)")
        self.width_slider.setValue(logic.clamp_panel_width(self.cfg.gui_expanded_width))
        self.width_value_label.setText(f"{self.width_slider.value()} px")
        self.width_slider.valueChanged.connect(self._on_width_preview)
        self.width_slider.sliderReleased.connect(self._on_width_committed)
        layout.addWidget(self.width_slider)

        self.hearts_check = QCheckBox("Floating hearts on the folded icon")
        self.hearts_check.setCursor(Qt.PointingHandCursor)
        self.hearts_check.setChecked(self.cfg.gui_hearts_enabled)
        self.hearts_check.toggled.connect(self._on_hearts_toggled)
        layout.addWidget(self.hearts_check)

        # Window: how the panel stacks with other windows, and where it lives on the screen
        self.layer_label = QLabel("Stay")
        self.layer_label.setStyleSheet("font-size:11px; font-weight:600; background:transparent;")
        layout.addWidget(self.layer_label)
        self.layer_switch = LayerSwitch(logic.layer(self.cfg))
        self.layer_switch.changed.connect(self._on_layer_changed)
        layout.addWidget(self.layer_switch)

        self.place_label = QLabel("Place on screen")
        self.place_label.setStyleSheet("font-size:11px; font-weight:600; background:transparent;")
        layout.addWidget(self.place_label)
        place_row = QHBoxLayout()
        place_row.setSpacing(10)
        self.screen_picker = ScreenPicker(logic.dock_side(self.cfg))
        self.screen_picker.picked.connect(self._on_side_picked)
        self.screen_picker.hovered.connect(self._on_side_hovered)
        place_row.addWidget(self.screen_picker)
        place_col = QVBoxLayout()
        place_col.setSpacing(6)
        self.place_name = QLabel("")
        self.place_hint = QLabel("")
        self.place_hint.setWordWrap(True)
        place_col.addWidget(self.place_name)
        place_col.addWidget(self.place_hint)
        place_col.addStretch(1)
        self.off_screen_btn = QPushButton("Off screen")
        self.off_screen_btn.setCursor(Qt.PointingHandCursor)
        self.off_screen_btn.setToolTip("Hide myGeeKy for now. It keeps up to date quietly; "
                                       "open myGeeKy again to bring it back.")
        self.off_screen_btn.clicked.connect(self._go_off_screen)
        place_col.addWidget(self.off_screen_btn)
        place_row.addLayout(place_col, 1)
        layout.addLayout(place_row)
        self._show_place(logic.dock_side(self.cfg))

        self.rail_side_label = QLabel("Menu side")
        self.rail_side_label.setStyleSheet("font-size:11px; font-weight:600; background:transparent;")
        layout.addWidget(self.rail_side_label)
        from .window_ui import RAIL_CHOICES
        self.rail_side_switch = LayerSwitch(getattr(self.cfg, "gui_rail_side", "auto"), choices=RAIL_CHOICES, name="Menu side")
        self.rail_side_switch.changed.connect(self._on_rail_side_changed)
        layout.addWidget(self.rail_side_switch)

        # 🔔 notifications: exactly what you agreed to (all off until you switch a kind on)
        layout = pages["notify"]
        from .notify_ui import NotifySettings
        self.notify_settings = NotifySettings(lambda: logic.notify_settings(self.cfg),
                                              lambda s: logic.set_notify(self.cfg, s), lambda: THEMES[self._theme_name()])
        layout.addWidget(self.notify_settings)

        # 🧠 How myGeeKy asks the internet: your own WISEP, its numbers and its switch (wisep.py)
        layout = pages["data"]
        from .wisep_ui import WisepSection
        self.wisep_section = WisepSection(lambda: THEMES[self._theme_name()], self._toast)
        layout.addWidget(self.wisep_section)

        # 📦 Packs: your setup as one to three QR codes a phone scans (packs.py)
        from .packs_ui import PackSection
        self.pack_section = PackSection(self.cfg, lambda: THEMES[self._theme_name()], QrWidget)
        layout.addWidget(self.pack_section)

        # 📄 "Is this you?": your OpenAlex author record, with no ORCID (whois.py)
        layout = pages["profile"]
        from .whois_ui import WhoisSection
        self.whois_section = WhoisSection(self.cfg, lambda: THEMES[self._theme_name()], self._run_async, self._toast)
        layout.addWidget(self.whois_section)

        # 📝 Drop a CV, thesis or abstract: your field, methods and co-authors from it (docread.py)
        from .docread_ui import DocSection
        self.doc_section = DocSection(self.cfg, lambda: THEMES[self._theme_name()], self._run_async, self._toast)
        layout.addWidget(self.doc_section)

        # 🔗 Accounts: GitHub and ORCID, then saving your data and Signals, then your phone (accounts.py)
        from .accounts_ui import AccountsSection
        self.accounts_section = AccountsSection(lambda: THEMES[self._theme_name()], self._account_action)
        pages["accounts"].addWidget(self.accounts_section)
        # what the setup summary and the Signals switch report into (no longer shown: the cards say it)
        self.setup_label = QLabel("")
        self.setup_label.setTextFormat(Qt.RichText)
        self.signals_btn = QPushButton("")
        self.pair_btn = QPushButton("\U0001f4f1 Connect your phone")

        layout = pages["data"]
        legal = QHBoxLayout()                              # Play asks for the privacy policy inside the app; the phone has it too
        self.legal_btns = []
        for text, url in (("Privacy policy \u2197", "https://mygeeky.org/privacy.html"),
                          ("Signals terms \u2197", "https://mygeeky.org/terms.html")):
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(url)
            b.clicked.connect(lambda checked=False, u=url: self._open_site(u))
            legal.addWidget(b)
            self.legal_btns.append(b)
        legal.addStretch(1)
        layout.addLayout(legal)

        bottom = QHBoxLayout()
        self.sync_label = QLabel("")
        self.sync_label.setWordWrap(True)
        bottom.addWidget(self.sync_label, 1)
        self.uninstall_btn = QPushButton("Uninstall\u2026")
        self.uninstall_btn.setCursor(Qt.PointingHandCursor)
        self.uninstall_btn.setToolTip("Remove myGeeKy from this computer (you choose whether to keep your data)")
        self.uninstall_btn.clicked.connect(self._uninstall)
        bottom.addWidget(self.uninstall_btn)
        self.quit_btn = QPushButton("Quit myGeeKy")
        self.quit_btn.setCursor(Qt.PointingHandCursor)
        self.quit_btn.setToolTip("Close the panel. Open it again from your apps menu or `mygeeky gui`.")
        self.quit_btn.clicked.connect(self._quit)
        bottom.addWidget(self.quit_btn)
        layout.addLayout(bottom)

        # ⚙ holds more than any panel is tall: it scrolls, and while open it has the panel to itself (_toggle_settings)
        # -- squeezed in beside the page, its rows were drawn on top of each other
        panel = QFrame()
        panel.setObjectName("settings")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content.setStyleSheet("QWidget#settingsContent { background:transparent; }")
        scroll.setWidget(content)
        scroll.viewport().setAutoFillBackground(False)
        scroll.setStyleSheet("QScrollArea { background:transparent; }")
        outer.addWidget(scroll)
        self.settings_scroll = scroll
        return panel

    # ------------------------------------------------------------------ ⚙ → Window
    def _show_place(self, side: str) -> None:
        name, hint = SIDE_LABELS.get(side, SIDE_LABELS["right"])
        self.place_name.setText(name)
        self.place_hint.setText(hint[:1].upper() + hint[1:] + ".")

    def _on_side_hovered(self, side: str) -> None:
        self._show_place(side or logic.dock_side(self.cfg))

    def _on_side_picked(self, side: str) -> None:
        if side == logic.dock_side(self.cfg):
            return
        logic.set_dock_side(self.cfg, side)
        self.screen_picker.set_side(side)
        self._show_place(side)
        self.rail_host.set_side(logic.rail_side(self.cfg))   # "screen edge": the menu follows the panel
        self._dock(self.folded_widget.isVisible())       # moves now; the settings stay open
        self.width_grip.place()

    def _on_rail_side_changed(self, value: str) -> None:
        if logic.set_rail_side(self.cfg, value):
            self.rail_side_switch.set_value(value)
            self.rail_host.set_side(logic.rail_side(self.cfg))

    def _on_layer_changed(self, value: str) -> None:
        if value == logic.layer(self.cfg):
            return
        logic.set_layer(self.cfg, value)
        self.layer_switch.set_value(value)
        self._apply_layer()

    def _apply_layer(self) -> None:
        """In front: the always-on-top flag (and the guard keeps it there). Normal and
        Behind: an ordinary window. Behind also sends the folded icon under the
        others; opened, the panel comes forward so you can use it."""
        want_top = logic.layer(self.cfg) == "front"
        if bool(self.windowFlags() & Qt.WindowStaysOnTopHint) != want_top:
            visible = self.isVisible()
            self.setWindowFlag(Qt.WindowStaysOnTopHint, want_top)    # Qt hides a window whose flags change
            if visible:
                self.show()
        if self.folded_widget.isVisible():
            self._settle_folded()
        else:
            self.raise_()

    def _settle_folded(self) -> None:
        """Folded and set to Behind: under every other window."""
        if logic.layer(self.cfg) != "behind" or not self.isVisible():
            return
        from . import topmost
        if not topmost.send_to_back(int(self.winId())):
            self.lower()

    def _go_off_screen(self) -> None:
        where = ("the Start menu or the desktop icon" if sys.platform == "win32"
                 else "Launchpad or the Applications folder" if sys.platform == "darwin"
                 else "your apps menu, or `mygeeky gui`")
        box = QMessageBox(QMessageBox.Question, "myGeeKy",
                          f"Hide myGeeKy for now?\n\nIt keeps up to date quietly. To bring it back, "
                          f"open myGeeKy again from {where}.", parent=self)
        box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        hide = box.addButton("Hide", QMessageBox.AcceptRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is hide:
            if self.settings_panel.isVisible():
                self._settings_mode(False)
            self.hearts.hide()
            self.hide()

    def _folded_menu(self, pos) -> None:
        """Right-click on the folded icon: the same choices as ⚙ → Window."""
        from PySide6.QtGui import QAction, QActionGroup
        from PySide6.QtWidgets import QMenu
        theme = THEMES[self._theme_name()]
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background:#1d1d2a; color:#f0f0f5; border:1px solid rgba(255,255,255,40); border-radius:8px; "
            f"padding:5px; font-size:12px; }}"
            f"QMenu::item {{ padding:5px 22px 5px 22px; border-radius:5px; }}"
            f"QMenu::item:selected {{ background:{theme['accent']}; color:#15151f; }}"
            f"QMenu::section {{ color:rgba(240,240,245,140); font-size:10.5px; font-weight:700; padding:6px 10px 2px; }}"
            f"QMenu::separator {{ height:1px; background:rgba(255,255,255,30); margin:5px 8px; }}")
        menu.addAction("Open myGeeKy", self.unfold)
        menu.addSection("Stay")
        layers = QActionGroup(menu)
        for key, label, tip in (("front", "In front", ""), ("normal", "Normal", ""), ("behind", "Behind", "")):
            act = QAction(label, menu, checkable=True, checked=logic.layer(self.cfg) == key)
            act.triggered.connect(lambda checked=False, k=key: self._on_layer_changed(k))
            layers.addAction(act)
            menu.addAction(act)
        menu.addSection("Place")
        sides = QActionGroup(menu)
        for key in ("right", "left", "bottom-right", "bottom-left"):
            act = QAction(SIDE_LABELS[key][0], menu, checkable=True, checked=logic.dock_side(self.cfg) == key)
            act.triggered.connect(lambda checked=False, k=key: self._on_side_picked(k))
            sides.addAction(act)
            menu.addAction(act)
        menu.addSeparator()
        menu.addAction("Off screen…", self._go_off_screen)
        menu.addAction("Quit myGeeKy", self._quit)
        menu.exec(self.folded_widget.mapToGlobal(pos))

    def _quit(self) -> None:
        if logic.sync_enabled(self.cfg) and not self._syncing:
            logic.sync_now(self.cfg)            # take the latest from this computer along
        QApplication.quit()

    # ------------------------------------------------------------------ sync between your computers
    def _sync_now(self) -> None:
        if self._syncing:
            return
        self._syncing = True
        self._run_async(lambda: logic.sync_now(self.cfg), self._on_synced)

    def _on_synced(self, result: Any) -> None:
        self._syncing = False
        result = result if isinstance(result, dict) else {}
        if result.get("skipped"):
            return
        was = getattr(self, "_sync_error", "")
        self._sync_error = logic.sync_access_error(result)
        self._render_signs()
        if was != self._sync_error and getattr(self, "_setup", None):
            self._render_setup(self._setup)
        if result.get("error"):
            self.sync_label.setText(f"Sync: {result['error'][:120]}")
            return
        self.sync_label.setText("Synced with your other devices " + datetime.now().strftime("%H:%M"))
        if result.get("changed"):
            self._apply_synced_data()

    def _render_signs(self) -> None:
        """The four signs from what the panel knows already (the daily token check, the last sync); a red one
        reminds you to renew, at most once a day (signs.reminder)."""
        if not hasattr(self, "status_signs"):
            return
        from .. import signs
        items = logic.status_signs(self.cfg, getattr(self, "_token_warnings", []), self._sync_error)
        self.status_signs.set_signs(items, THEMES[self._theme_name()])
        from .. import accounts                          # what needs you, counted on Settings → Accounts' line
        self._accounts_todo = accounts.todo(accounts.cards({s["key"]: s["state"] for s in items}, "desktop"))
        if hasattr(self, "nav_buttons"):
            self._update_group_counts()
        now = datetime.now(timezone.utc)
        msg = signs.reminder(items, self.cfg.signs_reminded, now)
        if msg:
            self.cfg.signs_reminded = now.isoformat()
            logic.save_config(self.cfg)
            self._toast(f"\u26a0 {msg}")

    def _apply_synced_data(self) -> None:
        """Another computer's changes arrived: use its settings and data here too."""
        from dataclasses import fields
        from ..config import load_config
        fresh = load_config()
        for f in fields(fresh):
            setattr(self.cfg, f.name, getattr(fresh, f.name))
        self._apply_theme()
        self._dock(self.folded_widget.isVisible())
        self._load_suggestions()
        if not self._contrib_running:
            self._load_contributions()
        self._render_brain()
        self._refresh_signals(force=False)

    def _on_hearts_toggled(self, enabled: bool) -> None:
        logic.set_hearts(self.cfg, enabled)
        if enabled and self.folded_widget.isVisible():
            self._puff_hearts()  # show what you just turned on

    def _maybe_puff_hearts(self) -> None:
        if (self.cfg.gui_hearts_enabled and self.folded_widget.isVisible() and self.isVisible()
                and logic.layer(self.cfg) != "behind"):      # behind other windows: hearts would float alone
            self._puff_hearts()

    def _puff_hearts(self) -> None:
        from PySide6.QtCore import QRect
        top_left = self.folded_widget.mapToGlobal(QPoint(0, 0))
        self.hearts.puff(QRect(top_left, self.folded_widget.size()), logic.dock_side(self.cfg))

    def _uninstall(self) -> None:
        """⚙ → Uninstall: opens the step-by-step uninstall wizard. The panel stays
        open until you confirm there (cancelling changes nothing)."""
        exe = sys.executable
        if exe.lower().endswith("python.exe") and os.path.exists(exe[:-len("python.exe")] + "pythonw.exe"):
            exe = exe[:-len("python.exe")] + "pythonw.exe"
        from .. import winproc
        winproc.popen([exe, "-m", "mygeeky.gui.uninstall_wizard"],
                      creationflags=0x00000008 if sys.platform == "win32" else 0, close_fds=True,
                      **({} if sys.platform == "win32" else {"start_new_session": True}))

    def _toggle_settings(self) -> None:
        opening = not self.settings_panel.isVisible()
        self._settings_mode(opening)
        if opening:
            self.settings_scroll.verticalScrollBar().setValue(0)
            self._load_setup()
            self.wisep_section.refresh()                  # today's numbers, as of now

    def _settings_mode(self, opening: bool) -> None:
        """⚙ open: it has the panel to itself, the page and the rows above it (who's signed in, the badges, where
        you are) step aside, so a short screen still shows the settings; closed, they come back as they were."""
        self.settings_panel.setVisible(opening)
        self.rail_host.setVisible(not opening)
        rows = (self.status_label, self.start_holder, self.badge_strip, self.nav_head, self.tab_bar)
        if opening:
            self._before_settings = {w: w.isVisibleTo(self) for w in rows}
            for w in rows:
                w.hide()
        else:
            for w, shown in (getattr(self, "_before_settings", None) or {}).items():
                w.setVisible(shown)
            self._before_settings = {}

    # ------------------------------------------------------------------ ⚙'s pages
    def _show_settings_page(self, key: str, load: bool = True) -> None:
        if key not in SETTINGS_PAGES:
            key = "accounts"
        self._settings_page = key
        for k, page in self.settings_pages.items():
            page.setVisible(k == key)
        label, icon, about = SETTINGS_PAGES[key]
        self.settings_title.setText(f"{icon} {label}")
        self.settings_about.setText(about)
        self._style_settings_nav()
        if hasattr(self, "settings_scroll"):
            self.settings_scroll.verticalScrollBar().setValue(0)
        if key == "accounts" and load:
            self._load_setup()

    def _style_settings_nav(self) -> None:
        if not hasattr(self, "settings_nav"):
            return
        t = THEMES[self._theme_name()]
        for k, b in self.settings_nav.items():
            on = k == getattr(self, "_settings_page", "accounts")
            bg, fg = (t["accent"], t["on_accent"]) if on else (t["btn_bg"], t["text"])
            b.setStyleSheet(f"QPushButton {{ background:{bg}; color:{fg}; border:none; border-radius:9px; padding:4px 6px; "
                            f"font-size:10.5px; font-weight:{800 if on else 600}; }} QPushButton:hover {{ background:{t['btn_hover']}; "
                            f"color:{t['text']}; }}")
        self.settings_title.setStyleSheet(f"color:{t['title']}; font-size:15px; font-weight:800; background:transparent; margin-top:4px;")
        self.settings_about.setStyleSheet(f"color:{t['muted']}; font-size:11px; background:transparent;")

    def _account_action(self, action: str) -> None:
        """A button on an Accounts card (gui/accounts_ui.py ACTIONS): what the panel already does for each."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        info = getattr(self, "_setup", None) or {}
        if action == "setup":
            self._open_setup_window()
            self._toast("The setup window is opening: sign in or set it up there, then come back.")
        elif action == "sync":
            self._sync_now()
            self._toast("Saving…")
        elif action == "signals_on":
            if info.get("beacon_token"):
                self._on_signals_switch()
            else:
                self._open_setup_window()
                self._toast("The setup window is opening: Signals is one of its steps.")
        elif action == "signals_off":
            self._on_signals_switch()
        elif action == "renew":
            from ..tokens import SETTINGS_URL
            QDesktopServices.openUrl(QUrl(SETTINGS_URL))
        elif action == "paste_beacon":
            from PySide6.QtWidgets import QLineEdit
            value = self._ask_text("myGeeKy", "Paste your new Signals token:", echo=QLineEdit.Password)
            if value:
                self._run_async(lambda: logic.replace_token(self.cfg, "beacon", value),
                                lambda r: (self._toast(r.get("message", "") if isinstance(r, dict) else str(r)), self._load_setup()))
        elif action == "pair":
            self._show_dialog("_pair_dialog", lambda: PairDialog(self, THEMES[self._theme_name()]))
        elif action in ("drive", "to_drive"):
            self._toast("Google's sign-in is opening in your browser: choose your account and allow myGeeKy's own "
                        "folder, then come back.")
            self._run_async(lambda: logic.saving_google_sign_in(), self._on_google_signed_in)
        elif action in ("github", "to_github"):
            default = self.cfg.sync_repo or (f"{self.cfg.github_username}/mygeeky-data" if self.cfg.github_username else "")
            repo = self._ask_text("Save in a GitHub repo",
                                  "Your private repo, as owner/name (made for you if it doesn't exist yet):", default)
            if repo:
                self._toast("Setting up your repo… Git may ask you to sign in to GitHub once.")
                self._run_async(lambda: logic.saving_use_github(self.cfg, repo), self._on_saving_done)

    def _on_google_signed_in(self, result: Any) -> None:
        result = result if isinstance(result, dict) else {"ok": False, "error": str(result)}
        if not result.get("ok"):
            self._toast(result.get("error") or "Google didn't sign you in. Try again.")
            return
        self._toast("Signed in with Google. Copying your settings and progress to Google Drive…")
        self._run_async(lambda: logic.saving_use_drive(self.cfg, sign_in=False), self._on_saving_done)

    def _on_saving_done(self, result: Any) -> None:
        result = result if isinstance(result, dict) else {"ok": False, "error": str(result)}
        from dataclasses import fields
        fresh = logic.load_config()               # into the same object: other parts (Is this you?, Packs) hold it
        for f in fields(fresh):
            setattr(self.cfg, f.name, getattr(fresh, f.name))
        if logic.sync_enabled(self.cfg) and not self._sync_timer.isActive():
            self._sync_timer.start(SYNC_EVERY_MS)
        if not result.get("ok"):
            self._toast(result.get("error") or "That didn't work. Try again.")
        else:
            self._sync_error = ""
            self._toast(result.get("message") or "Done.")
            if result.get("down"):
                self._apply_synced_data()
        self._render_signs()
        self._load_setup()

    def _account_cards(self, info: dict[str, Any]) -> list[dict]:
        """The Accounts cards from the setup summary (what's stored, each token's state) and the last sync."""
        from .. import accounts
        toks = {t["name"]: t["state"] for t in info.get("tokens", [])}
        broken = lambda name: toks.get(name) in ("expired", "invalid")              # noqa: E731
        saving = info.get("saving") or {}
        where = saving.get("where", "")
        states = {
            "github": "off" if not (info.get("user") and "read" in toks) else "bad" if broken("read") else "on",
            "orcid": "on" if info.get("orcid") else "off",
            "data": "off" if not where else "bad" if (getattr(self, "_sync_error", "")
                                                      or not saving.get("ready", True)) else "on",
            "beacon": "off" if not info.get("signals") else "bad" if broken("beacon") else "on",
        }
        items = accounts.cards(states, "desktop", {"user": info.get("user") or "", "orcid": info.get("orcid") or "",
                                                   "repo": info.get("sync") or "", "where": where})
        data = next(c for c in items if c["key"] == "data")
        if data["state"] == "on":
            other = ("Switch to GitHub", "to_github") if where == "drive" else ("Switch to Google Drive", "to_drive")
            data["title"] = f"Saving your data · {'Google Drive' if where == 'drive' else 'GitHub'}"
            data["actions"] = [("Sync now", "sync", "ghost"), (other[0], other[1], "ghost")]
        elif data["state"] == "bad" and "moved to" in getattr(self, "_sync_error", ""):
            data["why"] = self._sync_error           # another device switched: follow it
            data["actions"] = [("Switch to GitHub", "to_github", "bad") if where == "drive" else
                               ("Switch to Google Drive", "to_drive", "bad")]
        elif data["state"] == "bad":
            data["actions"] = ([("Sign in with Google again", "drive", "bad")] if where == "drive" else
                               [("Open the setup window", "setup", "bad")])
        return items

    # ------------------------------------------------------------------ your setup (in ⚙)
    def _load_setup(self) -> None:
        if not getattr(self, "_setup", None):
            self.setup_label.setText("Checking your setup\u2026")
        self._run_async(lambda: logic.setup_overview(self.cfg), self._render_setup)

    def _render_setup(self, info: dict[str, Any]) -> None:
        import html as h
        self._setup = info
        if hasattr(self, "accounts_section"):
            self.accounts_section.set_cards(self._account_cards(info))
        theme = THEMES[self._theme_name()]
        ok, off = theme["good"], theme["muted"]

        def row(name: str, value: str, color: str | None = None) -> str:
            return (f"<tr><td style='color:{theme['muted']}; padding:1px 10px 1px 0'>{name}</td>"
                    f"<td style='color:{color or theme['text']}'>{value}</td></tr>")
        rows = [row("GitHub", h.escape(info.get("user") or "not set"))]
        for t in info.get("tokens", []):
            label = "Token 1 (read)" if t["name"] == "read" else "Token 2 (Signals)" if t["name"] == "beacon" else t["name"]
            msg = t["message"].split(") ", 1)[-1] if ") " in t["message"] else t["message"]
            bad = t["state"] in ("expired", "invalid", "soon")
            rows.append(row(label, h.escape(msg or "stored"), theme["bad"] if bad else None))
        if info.get("signals"):
            rows.append(row("Signals", "\u2713 on: you send and receive", ok))
        else:
            rows.append(row("Signals", "off" + ("" if info.get("beacon_token") else " (needs token 2)"), off))
        saving_at = (info.get("saving") or {}).get("label", "")
        rows.append(row("Sync", f"\u2713 on: {h.escape(saving_at)}" if saving_at else "off: this computer only",
                        ok if saving_at else off))
        rows.append(row("ORCID", h.escape(info.get("orcid") or "not set"), None if info.get("orcid") else off))
        rows.append(row("Scholar", h.escape(info.get("scholar") or "not set"), None if info.get("scholar") else off))
        rows.append(row("CV", h.escape(info.get("cv") or "not set"), None if info.get("cv") else off))
        kws = info.get("keywords") or []
        rows.append(row("Keywords", h.escape(", ".join(kws[:6]) + ("\u2026" if len(kws) > 6 else "")) if kws
                        else "none yet (add them in the Model tab)", None if kws else off))
        rows.append(row("Version", h.escape(info.get("version", ""))))
        self.setup_label.setText(
            f"<div style='font-size:11px; font-weight:600; color:{theme['text']}; margin-bottom:4px'>Your setup</div>"
            f"<table style='font-size:10.5px'>{''.join(rows)}</table>")
        self.setup_label.setStyleSheet("background:transparent;")
        can = info.get("signals") or info.get("beacon_token")
        self.signals_btn.setVisible(bool(can))
        self.signals_btn.setEnabled(True)
        self.signals_btn.setText("Turn Signals off" if info.get("signals") else "Turn Signals on")
        self.signals_btn.setStyleSheet(
            f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['text']}; border:none; border-radius:7px; "
            f"padding:4px 10px; font-size:11px; }} QPushButton:hover {{ background:{theme['btn_hover']}; }}")

    @staticmethod
    def _open_site(url: str) -> None:
        """One of myGeeKy's own pages (mygeeky.org), in the browser."""
        if url.startswith("https://mygeeky.org/"):
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(url))

    def _signals_terms_ok(self) -> bool:
        """The Signals terms, agreed to once (again when they change), before turning Signals on or posting a call."""
        from .. import beacon as bc
        if bc.terms_accepted(self.cfg):
            return True
        box = QMessageBox(QMessageBox.Question, "Signals terms",
                          "Before you join Signals or post a call:\n\n" + "\n".join(f"• {p}" for p in bc.TERMS_POINTS)
                          + f"\n\nThe full terms: {bc.TERMS_URL}", parent=self)
        box.setTextFormat(Qt.PlainText)
        box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        agree = box.addButton("I agree", QMessageBox.AcceptRole)
        read = box.addButton("Read the terms", QMessageBox.HelpRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is read:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(bc.TERMS_URL))
            return False
        if box.clickedButton() is agree:
            bc.accept_terms(self.cfg)
            return True
        return False

    def _on_signals_switch(self) -> None:
        on = not self.cfg.beacon_enabled
        if on and not self._signals_terms_ok():
            return
        self.signals_btn.setEnabled(False)
        self.signals_btn.setText("Turning Signals on\u2026" if on else "Turning Signals off\u2026")

        def done(result: dict[str, Any]) -> None:
            if not result.get("ok"):
                self.setup_label.setText(self.setup_label.text() + f"<p style='color:{THEMES[self._theme_name()]['bad']}; font-size:10.5px'>"
                                         f"Couldn't turn Signals on: {result.get('error')}</p>")
            self._refresh_signals(force=True)
            self._load_setup()
        self._run_async(lambda: logic.set_signals_enabled(self.cfg, on), done)

    @staticmethod
    def _slider_to_opacity(value: int) -> float:
        return 1.0 - (value / 100.0) * (1.0 - logic.MIN_OPACITY)

    @staticmethod
    def _opacity_to_slider(opacity: float) -> int:
        return max(0, min(100, int(round((1.0 - opacity) / (1.0 - logic.MIN_OPACITY) * 100))))

    # ------------------------------------------------------------------ panel height
    def _on_height_preview(self, value: int) -> None:
        """Live while dragging the slider; saved on release."""
        self.cfg.gui_panel_height_fraction = logic.clamp_panel_height(value / 100)
        self.height_value_label.setText(f"{value}% of the screen")
        if not self.folded_widget.isVisible():
            self._dock(folded=False)

    # ------------------------------------------------------------------ panel width
    def _on_width_preview(self, value: int) -> None:
        """Live while dragging the slider; saved on release."""
        self.cfg.gui_expanded_width = logic.clamp_panel_width(value)
        self.width_value_label.setText(f"{self.cfg.gui_expanded_width} px")
        if not self.folded_widget.isVisible():
            self._dock(folded=False)

    def _on_width_committed(self) -> None:
        logic.set_panel_width(self.cfg, self.width_slider.value())

    def _resize_width_from_grip(self, dx: float, start_width: int, done: bool) -> None:
        """The inner-edge grip: dragging away from the screen edge makes the panel wider."""
        screen_w = self._home_screen().availableGeometry().width()
        width = min(logic.clamp_panel_width(start_width + dx), screen_w)
        self.cfg.gui_expanded_width = width
        self._dock(folded=False)
        if hasattr(self, "width_slider"):
            self.width_slider.blockSignals(True)
            self.width_slider.setValue(width)
            self.width_slider.blockSignals(False)
            self.width_value_label.setText(f"{width} px")
        if done:
            logic.set_panel_width(self.cfg, width)

    def _on_height_committed(self) -> None:
        logic.set_panel_height(self.cfg, self.height_slider.value() / 100)

    def _resize_from_grip(self, dy: float, start_fraction: float, done: bool) -> None:
        """The bottom-edge grip: the panel is centred on the screen edge, so it grows
        at the top and the bottom alike -- twice the drag, as a share of the screen."""
        screen_h = max(self._home_screen().availableGeometry().height(), 1)
        fraction = logic.clamp_panel_height(start_fraction + 2 * dy / screen_h)
        self.cfg.gui_panel_height_fraction = fraction
        self._dock(folded=False)
        if hasattr(self, "height_slider"):
            self.height_slider.blockSignals(True)
            self.height_slider.setValue(int(round(fraction * 100)))
            self.height_slider.blockSignals(False)
            self.height_value_label.setText(f"{int(round(fraction * 100))}% of the screen")
        if done:
            logic.set_panel_height(self.cfg, fraction)

    def _on_opacity_preview(self, value: int) -> None:
        """Shown live, at most ~30 times a second; a drag is saved once, on release."""
        self.opacity_value_label.setText(f"{value}%")
        if not self._opacity_timer.isActive():
            self._opacity_timer.start()

    def _apply_opacity_preview(self) -> None:
        opacity = self._slider_to_opacity(self.opacity_slider.value())
        if abs(self.windowOpacity() - opacity) > 0.004:
            self.setWindowOpacity(opacity)
        if not self.opacity_slider.isSliderDown():       # keys and the wheel never "release": save now
            logic.set_opacity(self.cfg, opacity)

    def _on_opacity_committed(self) -> None:
        self._opacity_timer.stop()
        self._apply_opacity_preview()

    def _build_model_tab(self) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 4, 4)
        layout.setSpacing(10)

        self.brain_title = QLabel("What myGeeKy knows about you")
        layout.addWidget(self.brain_title)
        self.brain_intro = QLabel("")
        self.brain_intro.setWordWrap(True)
        layout.addWidget(self.brain_intro)
        # as on the phone (You -> Model): with no data repo, what it learns stays on this computer
        self.local_only = QLabel(LOCAL_ONLY_TEXT)
        self.local_only.setWordWrap(True)
        self.local_only.setTextFormat(Qt.PlainText)
        self.local_only.setStyleSheet(f"color:{logic.readable('#ffc457', THEMES[self._theme_name()])}; font-size:11px; "
                                      "background:transparent;")
        layout.addWidget(self.local_only)

        self.map_header = QLabel("\U0001f9ed YOUR INTEREST MAP")
        layout.addWidget(self.map_header)
        self.interest_map = InterestMap()
        layout.addWidget(self.interest_map)
        self.map_legend = QLabel("")
        self.map_legend.setWordWrap(True)
        self.map_legend.setTextFormat(Qt.RichText)
        layout.addWidget(self.map_legend)

        # your keywords: green ones mean something to the model, red ones are plain words for now
        self.kw_header = QLabel("\U0001f524 YOUR KEYWORDS")
        layout.addWidget(self.kw_header)
        self.kw_chips = QLabel("")
        self.kw_chips.setWordWrap(True)
        self.kw_chips.setTextFormat(Qt.RichText)
        self.kw_chips.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        self.kw_chips.linkActivated.connect(self._on_keyword_link)
        self.kw_chips.linkHovered.connect(self._on_keyword_hover)
        layout.addWidget(self.kw_chips)
        kw_row = QHBoxLayout()
        kw_row.setSpacing(6)
        self.kw_input = QLineEdit()
        self.kw_input.setPlaceholderText("Add a keyword: AI, single cell, GWAS…")
        self.kw_input.returnPressed.connect(self._on_add_keyword)
        from .word_suggest import attach
        self.kw_suggest = attach(self.kw_input, many=False)   # the same suggestions as setup and the phone
        self.kw_add = QPushButton("Add")
        self.kw_add.setCursor(Qt.PointingHandCursor)
        self.kw_add.clicked.connect(self._on_add_keyword)
        kw_row.addWidget(self.kw_input, 1)
        kw_row.addWidget(self.kw_add)
        layout.addLayout(kw_row)
        self.kw_detail = QLabel("")
        self.kw_detail.setWordWrap(True)
        layout.addWidget(self.kw_detail)

        self.teach_header = QLabel("\U0001f9e0 WHAT TEACHES IT (LAST 30 DAYS)")
        layout.addWidget(self.teach_header)
        teach = QHBoxLayout()
        teach.setSpacing(6)
        self.teach_tiles = {key: StatTile(caption) for key, caption in (
            ("clicks", "clicks"), ("follows", "follows"), ("stars", "stars"), ("forks", "forks"))}
        for tile in self.teach_tiles.values():
            teach.addWidget(tile, 1)
        layout.addLayout(teach)
        self.teach_hint = QLabel("")
        self.teach_hint.setWordWrap(True)
        layout.addWidget(self.teach_hint)

        self.explore_header = QLabel("\U0001f52d ROOM TO EXPLORE")
        layout.addWidget(self.explore_header)
        explore_row = QHBoxLayout()
        explore_row.setSpacing(10)
        self.explore_donut = ExploreDonut()
        explore_row.addWidget(self.explore_donut)
        self.explore_label = QLabel("")
        self.explore_label.setWordWrap(True)
        explore_row.addWidget(self.explore_label, 1)
        layout.addLayout(explore_row)

        self.followback_header = QLabel("\U0001f465 WHO FOLLOWS YOU BACK")
        layout.addWidget(self.followback_header)
        hero = QHBoxLayout()
        hero.setSpacing(12)
        self.auc_gauge = AucGauge()
        hero.addWidget(self.auc_gauge)
        verdict_box = QVBoxLayout()
        verdict_box.setSpacing(4)
        verdict_box.addStretch(1)
        self.model_grade_label = QLabel("")
        self.model_summary_label = QLabel("Loading…")
        self.model_summary_label.setWordWrap(True)
        self.model_delta_label = QLabel("")
        for label in (self.model_grade_label, self.model_summary_label, self.model_delta_label):
            verdict_box.addWidget(label)
        verdict_box.addStretch(1)
        hero.addLayout(verdict_box, 1)
        layout.addLayout(hero)

        tiles = QHBoxLayout()
        tiles.setSpacing(6)
        self.model_tiles = {key: StatTile(caption) for key, caption in (
            ("examples", "examples"), ("positives", "follow-backs"),
            ("rate", "follow-back rate"), ("retrains", "retrains"))}
        for tile in self.model_tiles.values():
            tiles.addWidget(tile, 1)
        layout.addLayout(tiles)

        self.model_section_labels = [QLabel("WHAT IT HAS LEARNED"), QLabel("GETTING SHARPER?")]
        layout.addWidget(self.model_section_labels[0])
        self.weight_bars = WeightBars()
        layout.addWidget(self.weight_bars)
        self.weights_hint = QLabel("Right = makes a follow-back more likely; left = less likely.")
        self.weights_hint.setWordWrap(True)
        layout.addWidget(self.weights_hint)

        layout.addWidget(self.model_section_labels[1])
        self.chart = TrendChart()
        layout.addWidget(self.chart)
        self.model_footer_label = QLabel("")
        self.model_footer_label.setWordWrap(True)
        layout.addWidget(self.model_footer_label)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        scroll.viewport().setAutoFillBackground(False)
        page.setAutoFillBackground(False)
        return scroll

    # ------------------------------------------------------------------ theme
    def _theme_name(self) -> str:
        return self.cfg.gui_theme if self.cfg.gui_theme in THEME_NAMES else "midnight"

    def _apply_theme(self) -> None:
        theme = THEMES[self._theme_name()]
        self._render_signs()
        self._style_settings_nav()
        self.panel_frame.set_style(theme["bg"], theme["border"], radius=22.0)
        self.panel_frame.setStyleSheet(
            f"QLabel {{ color:{theme['text']}; }}"
            f"QScrollBar:vertical {{ background:transparent; width:6px; margin:2px 0; }}"
            f"QScrollBar::handle:vertical {{ background:{theme['btn_hover']}; border-radius:3px; min-height:24px; }}"
            f"QScrollBar::handle:vertical:hover {{ background:{theme['accent']}; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}"
            f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}"
        )
        self.folded_widget.set_style(theme["bg"], theme["border"], theme["text"])
        folded_font = self.folded_widget.font()
        folded_font.setBold(True)
        self.folded_widget.setFont(folded_font)
        self.status_label.setStyleSheet(f"font-size:11px; color:{theme['muted']}; background:transparent;")
        self.update_banner.setStyleSheet(
            f"QFrame#updateBanner {{ background:{theme['tab_active']}; border-radius:10px; }}"
            f"QLabel {{ color:{theme['text']}; font-size:11px; background:transparent; }}"
            f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['text']}; border:none; "
            f"border-radius:7px; padding:4px 9px; font-size:11px; }}"
            f"QPushButton:hover {{ background:{theme['btn_hover']}; }}"
            f"QPushButton#updateNow {{ background:{theme['accent']}; color:{theme['on_accent']}; font-weight:700; }}"
            f"QPushButton:disabled {{ color:{theme['muted']}; }}")
        self.token_banner.setStyleSheet(
            f"QFrame#tokenBanner {{ background:rgba(255,196,87,40); border:1px solid rgba(255,196,87,120); "
            f"border-radius:10px; }}"
            f"QLabel {{ color:{theme['text']}; font-size:11px; background:transparent; }}"
            f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['text']}; border:none; "
            f"border-radius:7px; padding:4px 9px; font-size:11px; }}"
            f"QPushButton:hover {{ background:{theme['btn_hover']}; }}")
        self.activity_updated_label.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")

        for lbl in (self.stat_friends_label, self.stat_new_label, self.stat_rate_label):
            lbl.setStyleSheet(f"font-size:11px; font-weight:600; color:{theme['text']}; background:transparent;")
        self.ticker.set_theme(theme)

        self.fold_btn.setStyleSheet(
            f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['text']}; border:none; "
            f"border-radius:8px; font-size:14px; }}"
            f"QPushButton:hover {{ background:{theme['btn_hover']}; }}"
        )
        for btn in (self.settings_btn, self.idea_btn):
            btn.setStyleSheet(
                f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['text']}; border:none; "
                f"border-radius:8px; font-size:13px; }}"
                f"QPushButton:hover {{ background:{theme['btn_hover']}; }}"
            )
        self.settings_panel.setStyleSheet(f"#settings {{ background:{theme['card_bg']}; border-radius:12px; }}")
        self.opacity_value_label.setStyleSheet(f"font-size:10.5px; color:{theme['muted']}; background:transparent;")
        self.hearts_check.setStyleSheet(f"QCheckBox {{ font-size:11px; color:{theme['text']}; background:transparent; }}")
        self.layer_switch.set_theme(theme)
        if hasattr(self, "rail_side_switch"):
            self.rail_side_switch.set_theme(theme)
        self.screen_picker.set_theme(theme)
        self.place_name.setStyleSheet(f"color:{theme['text']}; font-size:11.5px; font-weight:700; background:transparent;")
        self.place_hint.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
        self.off_screen_btn.setStyleSheet(f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['text']}; border:none; "
                                          f"border-radius:7px; padding:5px 10px; font-size:11px; }}"
                                          f"QPushButton:hover {{ background:{theme['btn_hover']}; }}")
        self.sync_label.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")
        self.pair_btn.setStyleSheet(f"QPushButton {{ background:{theme['section_btn']}; color:{theme['text']}; "
                                    f"border:none; border-radius:8px; padding:6px 10px; font-size:11.5px; }}"
                                    f"QPushButton:hover {{ background:{theme['btn_hover']}; }}")
        for b in getattr(self, "legal_btns", []):
            b.setStyleSheet(f"QPushButton {{ background:transparent; color:{logic.readable(theme['link'], theme)}; border:none; "
                            "padding:2px 4px; font-size:11px; } QPushButton:hover { text-decoration:underline; }")
        self.uninstall_btn.setStyleSheet(f"QPushButton {{ background:transparent; color:{theme['bad']}; border:none; "
                                         f"padding:4px 6px; font-size:11px; }} QPushButton:hover {{ text-decoration:underline; }}")
        self.quit_btn.setStyleSheet(f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['text']}; border:none; "
                                    f"border-radius:7px; padding:4px 10px; font-size:11px; }}"
                                    f"QPushButton:hover {{ background:{theme['btn_hover']}; }}")
        track = "rgba(255,255,255,40)" if theme.get("dark", True) else "rgba(0,0,0,40)"
        for slider in (self.opacity_slider, self.height_slider, self.width_slider):
            slider.setStyleSheet(                          # one look for ⚙'s sliders, its track visible on every theme
                f"QSlider::groove:horizontal {{ height:4px; background:{track}; border-radius:2px; }}"
                f"QSlider::sub-page:horizontal {{ background:{theme['accent']}; border-radius:2px; }}"
                f"QSlider::handle:horizontal {{ background:{theme['accent']}; width:14px; height:14px; "
                f"margin:-5px 0; border-radius:7px; }}"
            )
        for name, btn in self.swatch_buttons.items():
            active = name == self._theme_name()
            border = f"2px solid {theme['accent']}" if active else f"1px solid {theme['swatch_border']}"
            btn.setStyleSheet(
                f"QPushButton {{ background:{SWATCH_GRADIENTS[name]}; border-radius:7px; border:{border}; }}"
            )
        for btn in (self.refresh_sugg_btn, self.refresh_repos_btn, self.refresh_market_btn, self.refresh_act_btn,
                    self.refresh_signals_btn, self.refresh_news_btn, self.refresh_research_btn):
            btn.setStyleSheet(
                f"QPushButton {{ background:{theme['section_btn']}; color:{theme['text']}; border:none; "
                f"border-radius:8px; padding:6px 10px; font-size:11.5px; }}"
            )
        self.chart.set_theme_colors(theme["text"], theme["accent"])
        self.auc_gauge.set_theme_colors(theme["text"])
        self.weight_bars.set_theme_colors(theme["text"], theme["accent"])
        for tile in self.model_tiles.values():
            tile.apply_theme(theme)
        for label in self.model_section_labels:
            label.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; font-weight:600; "
                                f"background:transparent;")
        for label in (self.weights_hint, self.model_footer_label, self.model_delta_label):
            label.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
        self.model_summary_label.setStyleSheet(f"color:{theme['text']}; font-size:11.5px; background:transparent;")
        self._style_model_grade()
        self._update_tab_styles()
        if hasattr(self, "local_only"):
            self.local_only.setStyleSheet(f"color:{logic.readable('#ffc457', theme)}; font-size:11px; background:transparent;")
        if hasattr(self, "rail_host"):
            self.rail_host.restyle()

    # ------------------------------------------------------------------ the dock: groups → pages → parts
    def _nav_part(self, tab: str) -> str:
        """The part open in a tab, as the tree names it."""
        return {"news": getattr(self, "_news_mode", ""), "market": getattr(self, "_market_mode", ""),
                "grow": getattr(self, "_grow_mode", ""), "chances": getattr(self, "_chance_mode", ""),
                "model": getattr(self, "you_part", ""), "admin": getattr(self, "_admin_part", ""),
                "researchers": getattr(getattr(self, "researchers_page", None), "part", "")}.get(tab, "")

    def _nav_leaf(self) -> dict[str, Any] | None:
        tab = getattr(self, "active_tab", "")
        return navtree.leaf_for(self.nav_tree, tab, self._nav_part(tab))

    def _nav_tap(self, picked: str) -> None:
        leaf = self._nav_leaf()
        out = navtree.tap(self.nav_tree, self._nav_at, picked, leaf["id"] if leaf else "")
        self._nav_at = out["at"]
        if not leaf or out["open"] != leaf["id"]:
            self._nav_open(navtree.find(self.nav_tree, out["open"]))
        self._update_tab_styles()

    def _nav_open(self, nd: dict[str, Any] | None) -> None:
        """Open a page: its part first (so the row doesn't jump to where the tab's old part lives), then its tab."""
        if not nd or not nd["tab"]:
            return
        if nd["tab"] == "settings":                       # a Settings page: the ⚙ panel, open on that page
            self._show_settings_page(nd["part"] or "accounts")
            if not self.settings_panel.isVisible():
                self._toggle_settings()
            return
        tab, part = nd["tab"], nd["part"]
        if part:
            setter = {"news": self._set_news_mode, "market": self._set_market_mode, "grow": self._set_grow_mode,
                      "chances": self._set_chance_mode, "model": self._show_you_part,
                      "admin": self._set_admin_part, "researchers": self.researchers_page.set_part}.get(tab)
            if setter:
                self._nav_opening = True          # the part changes before the tab: don't move the row meanwhile
                try:
                    setter(part)
                finally:
                    self._nav_opening = False
        self._switch_tab(tab)

    def _rail_icon(self, nd: dict[str, Any]) -> tuple[str, str]:
        """(line icon path, emoji) for a place in the side rail: the same icons the planets drew."""
        if nd["parent"] is self.nav_tree:
            return GROUP_ICONS.get(nd["id"], ""), ""
        if nd["part"] or nd["tab"] not in PLANETS:
            return "", nd["icon"] or TABS.get(nd["tab"], ("\u2022",))[0]
        return PLANETS[nd["tab"]][1], ""

    def _nav_follow(self) -> None:
        """The open page changed from elsewhere (a notification, a link): show the level it lives on."""
        leaf, at = self._nav_leaf(), navtree.find(self.nav_tree, self._nav_at)
        if leaf and at not in navtree.path(leaf):
            self._nav_at = leaf["parent"]["id"]

    def _render_nav(self, theme: dict[str, Any]) -> None:
        at = navtree.find(self.nav_tree, self._nav_at) or self.nav_tree
        lvl = navtree.level(at)
        while self.nav_row.count():
            w = self.nav_row.takeAt(0).widget()
            if w is not None:
                w.hide()
        if lvl["back"]:
            back = lvl["back"]
            self.nav_back._color = QColor(back["color"])
            self.nav_back.setToolTip(f"Back to {back['label']}")
            self.nav_back.setAccessibleName(f"Back to {back['label']}")
            self.nav_row.addWidget(self.nav_back, 1)
            self.nav_back.show()
            self.nav_back.update()
        for i in lvl["items"]:
            self.nav_row.addWidget(self.nav_buttons[i], 1)
            self.nav_buttons[i].show()
        # always says where you are: the page that's open (its group › page › part)
        leaf = self._nav_leaf()
        self.nav_trail.setText(" \u203a ".join(n["label"] for n in navtree.path(leaf)[1:]) if leaf else "")
        # where you are, in the open page's colour, and beside it the way up a level
        color = logic.readable(leaf["color"], theme) if leaf else theme["text"]
        self.nav_trail.setStyleSheet(f"color:{color}; font-size:11.5px; font-weight:700; background:transparent;")
        if hasattr(self, "rail_host"):
            self.rail_host.refresh()
        self._render_up_button()

    def _render_up_button(self) -> None:
        """"‹ Grow" beside "Grow › Skills": up a level, as the menu's own back button (navrail.RailHost.up)."""
        if not hasattr(self, "nav_back_text"):
            return
        up = self.rail_host.up_target() if hasattr(self, "rail_host") else None
        self.nav_back_text.setVisible(bool(up))
        if up:
            c = QColor(up["color"]).darker(150).name()
            self.nav_back_text.setText(f"\u2039  {up['label']}")
            self.nav_back_text.setToolTip(f"Back to {up['label']}")
            self.nav_back_text.setAccessibleName(f"Back to {up['label']}")
            self.nav_back_text.setStyleSheet(f"QPushButton {{ background:{c}; color:#ffffff; border:none; border-radius:10px; "
                                             "padding:3px 10px; font-size:10.5px; font-weight:800; }")

    def _update_group_counts(self) -> None:
        """A group's (or a page's) planet counts what's new in the pages under it."""
        for nd in navtree.walk(self.nav_tree)[1:]:
            if not nd["children"]:
                continue
            btn = self.nav_buttons[nd["id"]]
            tabs = {x["tab"] for x in navtree.walk(nd) if x["tab"]}
            if tabs == {nd["tab"]} and self.tab_buttons.get(nd["tab"]) is btn:
                continue                     # a page whose parts are all its own tab (News): it keeps its own count
            btn.set_count(sum(self.tab_buttons[t]._count for t in tabs
                              if t in self.tab_buttons and self.tab_buttons[t] is not btn))
        todo = getattr(self, "_accounts_todo", 0)         # Settings → Accounts: what needs you
        if "settings:accounts" in self.nav_buttons:
            self.nav_buttons["settings:accounts"].set_count(todo)
            self.nav_buttons["settings"].set_count(self.nav_buttons["settings"]._count + todo)
        if hasattr(self, "rail_host"):
            self.rail_host.refresh()

    def _update_tab_styles(self) -> None:
        theme = THEMES[self._theme_name()]
        self.tab_bar.setStyleSheet(f"QFrame#tabBar {{ background:{theme['card_bg']}; border-radius:10px; }}")
        leaf = self._nav_leaf()
        if leaf and leaf["id"] != getattr(self, "_wisep_page", None):       # WISEP learns your day from what you open
            self._wisep_page = leaf["id"]
            try:
                from .. import wisep
                wisep.opened(leaf["id"])
            except Exception:
                pass
        on_path = {n["id"] for n in navtree.path(leaf)} if leaf else set()
        planet_bg = QColor("#1c1c2c") if theme["dark"] else QColor("#ffffff")
        for nid, btn in self.nav_buttons.items():
            btn.setStyleSheet("QPushButton { background: transparent; border: none; }")
            btn.set_planet_bg(planet_bg)
            btn.set_selected(nid in on_path)
        self.nav_back.setStyleSheet("QPushButton { background: transparent; border: none; }")
        self.nav_back.set_planet_bg(planet_bg)
        for name, btn in self.tab_buttons.items():
            active = name == self.active_tab
            icon, label = TABS[name]
            new_badge = name == "badges" and self._badges_new
            # the text isn't drawn (the planet is): it's for screen readers and the tests
            btn.setText(f"{icon}  {label}" if active else icon + ("\u2022" if new_badge else ""))
            btn.set_dot(new_badge)
        self._render_nav(theme)

    def _on_theme_clicked(self, name: str) -> None:
        if logic.set_theme(self.cfg, name):
            self._apply_theme()
            self._render_brain()
            self._render_suggestions_from_cache()
            self._load_market()
            self._load_news()
            self._set_news_mode(self._news_mode)
            self._render_models(logic.get_hf_models(self.cfg))
            self._restyle_rest()
            self._restyle_parts()

    def _restyle_parts(self) -> None:
        """Every part that knows how to restyle itself (an apply_theme() method: Home, Packs, notifications, WISEP,
        admin...) does it now, wherever it sits; a part added later only has to define apply_theme()."""
        done: set[int] = set()
        for w in [self, *self.findChildren(QWidget)]:
            fn = getattr(type(w), "apply_theme", None)
            if w is self or id(w) in done or not callable(fn):
                continue
            done.add(id(w))
            try:
                if fn.__code__.co_argcount == 1:          # apply_theme(self): it reads the theme itself
                    w.apply_theme()
            except Exception:                            # one part failing to restyle must not stop the rest
                pass
        if getattr(self, "_setup", None):                # ⚙'s sections, drawn when ⚙ was last opened
            try:
                self._render_setup(self._setup)
            except Exception:
                pass

    def _restyle_rest(self) -> None:
        """Everything else that was coloured when it was drawn, redrawn in the new
        theme -- or it keeps the old theme's text colour (dark text on dark)."""
        steps = [self._style_market_switch, self._render_badges, self._render_badge_strip,
                 self._render_keywords, self._update_tab_styles, self._fold_profile,
                 self._render_grow, self._render_chances]
        if self._is_admin:
            steps.append(self._render_admin)
        if self.settings_panel.isVisible() and getattr(self, "_setup", None):
            steps.append(lambda: self._render_setup(self._setup))
        for step in steps:
            try:
                step()
            except Exception:        # one part failing to restyle must not stop the rest
                pass

    def _render_suggestions_from_cache(self) -> None:
        # Re-render already-loaded cards so their theme-dependent styling updates too.
        self._load_suggestions()
        if not self._contrib_running:  # don't wipe the "Searching…" placeholder mid-search
            self._load_contributions()
        self._refresh_activity(force=False)
        self._refresh_signals(force=False)  # cached unless due: just re-renders

    # ------------------------------------------------------------------ fold/unfold/dock
    def _home_screen(self):
        """The monitor the panel belongs on: the one it was docked to, if it's
        connected (again); otherwise wherever it is now, or the primary one."""
        for screen in QGuiApplication.screens():
            if self._screen_name and screen.name() == self._screen_name:
                return screen
        return self.screen() or QGuiApplication.primaryScreen()

    def _docked_geometry(self, folded: bool, screen) -> QRect:
        rect = screen.availableGeometry()  # excludes the taskbar
        # the folded tab is sized purely by config; the full panel can't go
        # below what its content needs, so position it by that real size
        need = QSize(0, 0) if folded else self.panel_frame.minimumSizeHint()
        wide = 0
        if not folded and getattr(self, "active_tab", "") == "admin":     # Admin has room to work: the panel widens
            wide = logic.admin_width(rect.width())
        return QRect(*logic._panel_geometry(self.cfg, folded, rect, max(need.width(), wide), need.height()))

    def _dock(self, folded: bool, animate: bool = False) -> None:
        screen = self._home_screen()
        self._screen_name = screen.name()
        self._stop_dock_anim()
        corner = logic.dock_side(self.cfg).startswith("bottom")
        if animate and corner and self.isVisible():
            bottom = screen.availableGeometry().bottom() + 1
            if folded and self.panel_frame.isVisible():
                # sink: the open panel slides down to the corner, then becomes the icon there
                have = self.geometry()
                self._animate_to(QPoint(have.x(), bottom - have.height()), QEasingCurve.InCubic,
                                 lambda: self._dock(True))
                return
            if not folded and self.folded_widget.isVisible():
                # rise: the panel opens at the corner and slides up to the middle of the edge
                self._show_docked(False, screen)
                want = self.geometry()
                self.move(want.x(), bottom - want.height())
                self._animate_to(want.topLeft(), QEasingCurve.OutCubic)
                return
        self._show_docked(folded, screen)

    def _show_docked(self, folded: bool, screen) -> None:
        self.panel_frame.setVisible(not folded)
        self.folded_widget.setVisible(folded)
        self.setMinimumSize(0, 0)
        self.setGeometry(self._docked_geometry(folded, screen))
        self.setWindowOpacity(self.cfg.gui_folded_opacity if folded else max(self.cfg.gui_opacity, logic.MIN_OPACITY))
        if folded:
            self._settle_folded()

    def _animate_to(self, end: QPoint, curve, then=None) -> None:
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(DOCK_ANIM_MS)
        anim.setStartValue(self.pos())
        anim.setEndValue(end)
        anim.setEasingCurve(curve)
        if then is not None:
            anim.finished.connect(then)
        self._dock_anim = anim
        anim.start()

    def _stop_dock_anim(self) -> None:
        anim = getattr(self, "_dock_anim", None)
        self._dock_anim = None
        if anim is not None and anim.state() == QPropertyAnimation.Running:
            try:
                anim.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            anim.stop()

    def _dock_moving(self) -> bool:
        anim = getattr(self, "_dock_anim", None)
        return anim is not None and anim.state() == QPropertyAnimation.Running

    # The panel has no drag handle: it always belongs docked to its edge (and on
    # top: see topmost.py; the same check puts it back in front). But
    # Windows moves windows on its own -- when a monitor sleeps or is
    # unplugged, the PC locks or resumes, the resolution or scaling changes, a
    # remote-desktop session connects, or Explorer restarts -- and often parks
    # them in the middle of the main screen. So whenever screens change, and
    # every few seconds as a backstop, put it back where it belongs.
    def _watch_screens(self) -> None:
        app = QGuiApplication.instance()
        app.screenAdded.connect(self._on_screen_added)
        app.screenRemoved.connect(lambda s: self._redock_soon())
        app.primaryScreenChanged.connect(lambda s: self._redock_soon())
        for screen in QGuiApplication.screens():
            self._on_screen_added(screen)
        self._dock_guard = QTimer(self)
        self._dock_guard.timeout.connect(self._ensure_docked)
        self._dock_guard.start(DOCK_GUARD_MS)

    def _on_screen_added(self, screen) -> None:
        screen.availableGeometryChanged.connect(lambda r: self._redock_soon())
        screen.geometryChanged.connect(lambda r: self._redock_soon())
        self._redock_soon()

    def _redock_soon(self) -> None:
        # Windows finishes rearranging windows a moment after the screen event
        for delay in (400, 2500):
            QTimer.singleShot(delay, self._ensure_docked)

    def _ensure_docked(self) -> None:
        if not self.isVisible() or self.isMinimized() or self._dock_moving():
            return
        folded = self.folded_widget.isVisible()
        if logic.layer(self.cfg) == "front":
            # Windows also drops "always on top" now and then, leaving the icon behind other windows
            from . import topmost
            # our own windows (the QR code, the idea box, a token prompt, the hearts) may
            # sit over the panel: never lift the panel above them
            own = {int(w.winId()) for w in QApplication.topLevelWidgets()
                   if w is not self and w.isVisible() and w.isWindow()}
            topmost.keep_on_top(int(self.winId()), ignore=own)
        elif folded and not self.folded_widget.underMouse():
            self._settle_folded()
        want = self._docked_geometry(folded, self._home_screen())
        have = self.geometry()
        if abs(have.x() - want.x()) > 2 or abs(have.y() - want.y()) > 2                 or abs(have.width() - want.width()) > 2 or abs(have.height() - want.height()) > 2:
            self._dock(folded)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 -- Qt's own naming convention
        grow = getattr(self, "_grow_scroll", None)
        if grow is not None and obj is grow.viewport() and event.type() in (QEvent.Resize, QEvent.Show):
            self._grow_refit.start()           # Grow's width changed (or it came into view): fit the cards again
        if obj is self.folded_widget and self.folded_widget.isVisible():
            if event.type() == QEvent.Enter:
                self.setWindowOpacity(1.0)
            elif event.type() == QEvent.Leave:
                self.setWindowOpacity(self.cfg.gui_folded_opacity)
        return super().eventFilter(obj, event)

    def fold(self) -> None:
        self._dock(folded=True, animate=True)

    def unfold(self) -> None:
        self._dock(folded=False, animate=True)
        if logic.layer(self.cfg) != "front":       # opened on purpose: in front while you use it
            self.raise_()
            self.activateWindow()
        self.hearts.hide()
        self._recheck_tokens_if_warning()
        # opening the panel: show what's new since last time
        QTimer.singleShot(0, lambda: self._refresh_fresh_tab(self.active_tab))

    def closeEvent(self, event) -> None:  # noqa: N802 -- Qt's own naming convention
        self.hearts.close()  # a separate top-level window; it would outlive the panel
        super().closeEvent(event)

    # ------------------------------------------------------------------ native window effects
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # DWM's Acrylic system backdrop (DWMWA_SYSTEMBACKDROP_TYPE) was tried
        # here and confirmed, through isolated side-by-side testing, to
        # conflict with Qt's own WA_TranslucentBackground on this class of
        # setup: layering the DWM call on top of an otherwise genuinely
        # transparent Qt window made it render fully opaque instead --
        # reproduced with focus and without. Qt's own translucency (real,
        # working, see-through) is what actually ships; no DWM call here.

    # ------------------------------------------------------------------ async helper
    def _run_async(self, fn: Callable[[], Any], on_done: Callable[[Any], None]) -> None:
        worker = _Worker(fn)

        def _finish(result: Any) -> None:
            if worker in self._workers:
                self._workers.remove(worker)
            owner = getattr(on_done, "__self__", None)
            if isinstance(owner, QObject) and not shiboken6.isValid(owner):
                return                  # its widget was closed while this ran (e.g. a profile folded mid-load)
            on_done(result)

        worker.done.connect(_finish)
        self._workers.append(worker)
        worker.start()

    # ------------------------------------------------------------------ status / suggestions
    def _load_status(self) -> None:
        status = logic.get_status(self.cfg)
        if status["configured"]:
            extra = "" if status["token_present"] else " (no token set — run `mygeeky auth login`)"
            self.status_label.setText(f"Signed in as {status['github_username']}{extra}")
        elif status["profile_ready"]:
            who = f"ORCID {status['orcid_id']}" if status["orcid_id"] else "your topics"
            self.status_label.setText(f"Using {who}, without GitHub. Add GitHub for who'd follow "
                                      "you back, Activity, Signals and 🤝 Collab.")
        else:
            self.status_label.setText("myGeeKy doesn't know your field yet — no account needed.")
        self._render_start(status)

    # ------------------------------------------------------------------ starting from keywords alone
    def _render_start(self, status: dict[str, Any]) -> None:
        """The door, and the only thing ever said about making an account.

        With no profile at all this is the whole way in: five keywords at a time, no account anywhere. With
        a keyword-only profile it is the nudge instead -- four times over three months and then silence,
        because myGeeKy never stops working for not having an account, and a thing that stopped working
        would be a trial."""
        theme = THEMES[self._theme_name()]
        if not status.get("profile_ready"):
            # Never rebuild a picker somebody is in the middle of: a fresh one starts at round one with
            # nothing picked, so anything that redraws the status would quietly throw their chips away.
            if self._picker_alive():
                self.start_holder.setVisible(True)
                return
            _clear_layout(self.start_layout)
            self._picker = self._field_picker(theme)
            self.start_layout.addWidget(self._picker)
            self.start_holder.setVisible(True)
            return
        _clear_layout(self.start_layout)
        self._picker = None
        ask = logic.account_nudge(self.cfg)
        if not ask.get("ask"):
            self.start_holder.setVisible(False)
            return
        self.start_layout.addWidget(self._nudge_card(theme, ask))
        self.start_holder.setVisible(True)

    def _picker_alive(self) -> bool:
        """Is a keyword picker already on screen? `deleteLater` runs on a later turn of the event loop,
        so a cleared one is still a child for a while -- being in the layout is what counts."""
        picker = getattr(self, "_picker", None)
        if picker is None or not shiboken6.isValid(picker):
            return False
        return self.start_layout.indexOf(picker) >= 0

    def _field_picker(self, theme: dict[str, Any]):
        from .growth_ui import FieldPicker
        return FieldPicker(logic, theme, self._on_field_picked)

    def _on_field_picked(self, picked: list[str]) -> None:
        if not picked:
            return
        logic.field_keep(self.cfg, picked)
        self._picker = None                    # done with: _render_start may build a fresh one later
        self.start_holder.setVisible(False)
        self._load_status()
        self._switch_tab(getattr(self, "active_tab", "live"))      # the tabs have a field to work from now

    def _nudge_card(self, theme: dict[str, Any], ask: dict[str, Any]) -> QFrame:
        """Said once, plainly, and never twice.

        The last of the four asks is the honest one: the only thing a keyword-only profile truly cannot do
        is survive this computer. Everything else on the panel already works."""
        card = QFrame()
        card.setObjectName("nudgeCard")
        card.setStyleSheet(f"QFrame#nudgeCard {{ background:{theme['card_bg']}; border:1px dashed "
                           f"{theme['border']}; border-radius:10px; }} QLabel {{ background:transparent; "
                           f"color:{theme['text']}; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        said = _plain(QLabel(ask.get("why", "")))
        said.setWordWrap(True)
        said.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
        lay.addWidget(said)
        row = QHBoxLayout()
        add = QPushButton("Add an account…")
        add.setCursor(Qt.PointingHandCursor)
        add.setStyleSheet(f"QPushButton {{ background:{theme['accent']}; color:{theme['on_accent']}; "
                          f"border:none; border-radius:8px; padding:5px 12px; font-weight:700; }}")
        add.clicked.connect(self._open_setup_window)
        row.addWidget(add)
        shut = QPushButton("No thanks")
        shut.setCursor(Qt.PointingHandCursor)
        shut.setStyleSheet(f"QPushButton {{ background:transparent; color:{theme['muted']}; border:none; "
                           f"padding:5px 8px; }}")
        shut.clicked.connect(self._on_nudge_dismissed)
        row.addWidget(shut)
        row.addStretch(1)
        if ask.get("last"):
            final = QLabel("myGeeKy won't bring this up again.")
            final.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")
            row.addWidget(final)
        lay.addLayout(row)
        return card

    def _on_nudge_dismissed(self) -> None:
        logic.account_asked(self.cfg)
        self.start_holder.setVisible(False)

    def _load_live_stats(self) -> None:
        stats = logic.get_friend_stats(self.cfg)
        self.stat_friends_label.setText(f"👥 {stats['total_friends']} friends")
        self.stat_new_label.setText(f"🆕 {stats['new_this_week']} new this week")
        rate = stats["follow_back_rate"]
        self.stat_rate_label.setText(f"🔁 {rate:.0%} follow back" if rate is not None else "🔁 no data yet")

    def _load_suggestions(self) -> None:
        self._render_suggestions(logic.get_suggestions(self.cfg))

    @staticmethod
    def _load_safely(load: Callable[[], Any]) -> None:
        try:
            load()
        except Exception as exc:
            try:
                from .. import crashreport
                from ..config import LOG_DIR
                crashreport.write(LOG_DIR, f"panel start-up ({getattr(load, '__name__', 'a tab')})", exc)
            except Exception:
                pass

    # ------------------------------------------------------------------ freshness: what you've seen
    # A card that was mostly on screen for a moment, while the panel was open, counts as seen.
    # Seen ones make room for new ones -- but only when you open the panel or switch tabs,
    # never while you're reading (nothing jumps under the mouse).
    FRESH_TABS = ("suggestions", "repos", "market", "news", "activity")

    def _start_seen_tracker(self) -> None:
        tick = QTimer(self)
        tick.timeout.connect(self._track_seen)
        tick.start(SEEN_TICK_MS)
        flush = QTimer(self)
        flush.timeout.connect(self._flush_seen)
        flush.start(5_000)
        self._seen_timers = (tick, flush)
        repos = QTimer(self)
        repos.timeout.connect(self._maybe_top_up_repos)
        repos.start(30 * 60_000)
        QTimer.singleShot(90_000, self._maybe_top_up_repos)
        self._repos_topup_timer = repos

    def _reading(self, tab: str) -> bool:
        """Is this tab on screen right now (so it mustn't change under you)?"""
        return self.panel_frame.isVisible() and self.isVisible() and self.active_tab == tab

    def _track_seen(self) -> None:
        if not (self.panel_frame.isVisible() and self.isVisible()):
            self._seen_dwell.clear()
            return
        page = self.content_stack.currentWidget()
        if page is None:
            return
        on_screen = set()
        for card in page.findChildren(QFrame):
            key = card.property("fresh_key")
            if not key or key in self._seen_done or not card.isVisible():
                continue
            dot = card.findChild(QLabel, "freshDot", Qt.FindDirectChildrenOnly)
            if dot is not None and dot.x() != max(0, card.width() - 14):
                _place_dot(card, dot)                # the card was laid out (or resized) since
            area = card.width() * card.height()
            seen = card.visibleRegion().boundingRect()
            if area <= 0 or not (seen.width() * seen.height() >= SEEN_FRACTION * area or seen.height() >= 220):
                continue
            on_screen.add(key)
            self._seen_dwell[key] = self._seen_dwell.get(key, 0) + SEEN_TICK_MS
            if self._seen_dwell[key] >= SEEN_AFTER_MS:
                self._seen_done.add(key)
                self._seen_pending.add(key)
                self._fresh_dirty.add(self.active_tab)
                if dot is not None:
                    dot.hide()
        for key in list(self._seen_dwell):            # scrolled away before the moment was up
            if key not in on_screen:
                del self._seen_dwell[key]
        if on_screen & self._seen_done:
            self._update_fresh_counts()

    def _flush_seen(self) -> None:
        if self._seen_pending:
            keys, self._seen_pending = sorted(self._seen_pending), set()
            logic.mark_seen(keys)

    def _mark_clicked(self, item: dict[str, Any]) -> None:
        key = item.get("_key")
        if key:
            self._seen_done.add(key)
            logic.mark_seen([key], clicked=True)
            self._fresh_dirty.add(self.active_tab)

    def _update_fresh_counts(self) -> None:
        """The number on each planet: new things in that tab you haven't seen yet."""
        for tab in self.FRESH_TABS:
            btn = self.tab_buttons.get(tab)
            page = self.content_stack.widget(self._tab_order.index(tab)) if tab in self._tab_order else None
            if btn is None or page is None:
                continue
            # cards on their way out lost their key in _clear_layout; a card on another tab still counts
            n = len({card.property("fresh_key") for card in page.findChildren(QFrame)
                     if card.property("fresh_state") == "new" and card.property("fresh_key") not in self._seen_done})
            btn.set_count(n)
            btn.setToolTip(f"{TABS[tab][1]}: {n} new" if n else TABS[tab][1])
        self._update_group_counts()

    def _refresh_fresh_tab(self, tab: str) -> None:
        """Opening the panel or a tab: let what you've seen make room, and show what
        arrived in the background meanwhile."""
        waiting = self._fresh_waiting.pop(tab, None)
        if tab not in self._fresh_dirty and waiting is None:
            return
        self._fresh_dirty.discard(tab)
        self._flush_seen()
        if tab == "suggestions":
            self._render_suggestions(waiting if isinstance(waiting, dict) else logic.get_suggestions(self.cfg))
        elif tab == "repos":
            self._render_contributions(logic.get_contributions(self.cfg))
        elif tab == "market":
            self._load_market()
            self._load_research()
            self._render_models(logic.get_hf_models(self.cfg))
        elif tab == "news":
            self._render_news(logic.get_news(self.cfg))
            self._render_headlines(logic.get_headlines(self.cfg))
        elif tab == "activity":
            self._refresh_activity(force=False)

    def _maybe_auto_refresh_suggestions(self) -> None:
        if self._sugg_running or not logic.suggestions_auto_refresh_due(self.cfg):
            return
        if not getattr(self, "_last_suggestions", None):
            self._on_refresh_suggestions()          # nothing to show yet: search where you can see it
            return
        # running low on new faces: look for more quietly, and show them when you next open People
        self._sugg_running = True
        self._run_async(lambda: logic.refresh_suggestions(self.cfg), self._on_quiet_suggestions)

    def _on_quiet_suggestions(self, data: Any) -> None:
        self._sugg_running = False
        if not isinstance(data, dict) or (data.get("error") and "followback" not in data):
            return
        fresh = logic.get_suggestions(self.cfg)      # arranged: what's new first
        if self._reading("suggestions"):
            self._fresh_waiting["suggestions"] = fresh
            self.tab_buttons["suggestions"].set_count(fresh.get("new", 0))
        else:
            self._render_suggestions(fresh)

    def _maybe_top_up_repos(self) -> None:
        if self._contrib_running or not logic.contributions_top_up_due(self.cfg):
            return
        self._contrib_running = True
        self._run_async(lambda: logic.refresh_contributions(self.cfg), self._on_quiet_contributions)

    def _on_quiet_contributions(self, data: Any) -> None:
        self._contrib_running = False
        if isinstance(data, dict) and data.get("error"):
            return
        if self._reading("repos"):
            self._fresh_waiting["repos"] = True
        else:
            self._render_contributions(logic.get_contributions(self.cfg))

    def _on_refresh_suggestions(self) -> None:
        if self._sugg_running:
            return  # a search is already in flight; don't stack another
        self._sugg_running = True
        self.refresh_sugg_btn.setEnabled(False)
        theme = THEMES[self._theme_name()]
        _clear_layout(self.followback_area)
        loading = QLabel("Searching GitHub… this can take a minute.")
        loading.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
        self.followback_area.addWidget(loading)
        self._run_async(lambda: logic.refresh_suggestions(self.cfg), self._on_suggestions_ready)

    def _on_suggestions_ready(self, data: Any) -> None:
        self._sugg_running = False
        self.refresh_sugg_btn.setEnabled(True)
        if isinstance(data, dict) and data.get("error") and "followback" not in data:
            theme = THEMES[self._theme_name()]
            _clear_layout(self.followback_area)
            err = _plain(QLabel(str(data["error"])))
            err.setWordWrap(True)
            err.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
            self.followback_area.addWidget(err)
            return
        self._render_suggestions(data)

    def _github_card(self, layout, part: str, has_data: bool = False, field_only: bool = False) -> bool:
        """No GitHub username yet (and nothing to show): say what this part would show, with a
        way to add GitHub. True when the card was shown (the caller has nothing else to draw).

        `field_only` marks a part that is picked by searching your FIELD and never reads your account --
        Market and Repos. Those ask for a profile of any kind (keywords, a CV, an ORCID), not a username,
        so a card offering GitHub would be asking for something the part does not use."""
        if self.cfg.github_username or has_data:
            return False
        if field_only and profile_ready(self.cfg):
            return False
        # Remember this wall explained itself, but ONLY when that is new: this runs on every repaint, and
        # get_status() reads the keyring while account_asked() writes the config file. Neither belongs in
        # a draw.
        if part not in (getattr(self.cfg, "account_walls_asked", None) or []):
            logic.account_asked(self.cfg, wall=part)
        theme = THEMES[self._theme_name()]
        _clear_layout(layout)
        card = QFrame()
        card.setObjectName("githubCard")
        card.setStyleSheet(f"QFrame#githubCard {{ background:{theme['card_bg']}; border:1px dashed {theme['accent']}; "
                           f"border-radius:12px; }} QLabel {{ background:transparent; color:{theme['text']}; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        title = QLabel("🔓 <b>Add GitHub to see this</b>")
        title.setTextFormat(Qt.RichText)
        why = QLabel(GITHUB_UNLOCKS.get(part, ""))
        why.setWordWrap(True)
        why.setStyleSheet(f"color:{theme['muted']}; font-size:11px;")
        row = QHBoxLayout()
        add = QPushButton("Add GitHub…")
        add.setCursor(Qt.PointingHandCursor)
        add.setStyleSheet(f"QPushButton {{ background:{theme['accent']}; color:{theme['on_accent']}; border:none; "
                          f"border-radius:8px; padding:5px 12px; font-weight:700; }}")
        add.setToolTip("Opens setup: sign in with GitHub, or type your username")
        add.clicked.connect(self._open_setup_window)
        new = QLabel(f"<a href='https://github.com/signup' style='color:{theme['accent']}'>No account? Create one, free</a>")
        new.setTextFormat(Qt.RichText)
        new.setOpenExternalLinks(True)
        row.addWidget(add)
        row.addSpacing(8)
        row.addWidget(new)
        row.addStretch(1)
        lay.addWidget(title)
        lay.addWidget(why)
        lay.addLayout(row)
        layout.addWidget(card)
        return True

    def _render_suggestions(self, data: dict[str, Any] | None) -> None:
        """Two lists with two different requirements.

        The domain-fit list is people found by searching your field: it draws whether or not you have a
        GitHub account. The follow-back list is scored against your own account, so without one it is
        replaced by the card that says so -- rather than the whole tab being replaced, which hid people
        from the very users who have no GitHub to find them any other way."""
        theme = THEMES[self._theme_name()]
        followback = (data or {}).get("followback") or []
        domain = (data or {}).get("domain_highlights") or []
        if self._github_card(self.followback_area, "followback", bool(followback)):
            self._set_card_list(self.domain_area, domain, "domain_fit", theme)
            self._last_suggestions = []
            self._update_live_ticker()
            self._update_fresh_counts()
            return
        self._set_card_list(self.followback_area, followback, "score", theme)
        self._set_card_list(self.domain_area, domain, "domain_fit", theme)
        self._last_suggestions = followback
        self._update_live_ticker()
        self._update_fresh_counts()

    def _set_card_list(self, layout, items: list[dict[str, Any]], score_key: str, theme: dict[str, Any]) -> None:
        _clear_layout(layout)
        if not items:
            empty = QLabel("Nothing here yet — try Refresh.")
            empty.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
            layout.addWidget(empty)
            return
        for item in items:
            layout.addWidget(_mark_fresh(SuggestionCard(item, score_key, theme, self._on_suggestion_clicked,
                                                        self.avatar_loader), item, theme))

    def _on_suggestion_clicked(self, item: dict[str, Any]) -> None:
        logic.record_click(self.cfg, "person", item)
        self._mark_clicked(item)
        self._open_github(item.get("profile_url", ""))
        logic.mark_suggestion_seen(item.get("username", ""))
        # re-render on the next event-loop turn: the clicked card is still
        # inside its own mousePressEvent right now
        QTimer.singleShot(0, self._load_suggestions)

    def _opener(self, kind: str, item: dict[str, Any]) -> Callable[[str], bool]:
        """open_profile, plus: this click is an interest signal (and counts toward badges)."""
        def open_and_learn(url: str) -> bool:
            logic.record_click(self.cfg, kind, item)
            self._mark_clicked(item)
            QTimer.singleShot(0, self._refresh_badges)
            return logic.open_link(url)
        return open_and_learn

    # ------------------------------------------------------------------ badges
    STRIP_MAX = 7

    def _refresh_badges(self) -> None:
        self._badges = logic.get_badges(self.cfg)
        self._render_badge_strip()
        self._update_badge_tab_label()
        if self.active_tab == "badges":
            self._render_badges()

    def _load_github_achievements(self) -> None:
        self._run_async(lambda: logic.refresh_github_achievements(self.cfg), lambda r: self._refresh_badges())

    def _badge_icon(self, b: dict[str, Any], size: int = 22, locked: bool = False) -> QLabel:
        from ..achievements import TIER_COLORS
        icon = QLabel(b["emoji"])
        icon.setFixedSize(size, size)
        icon.setAlignment(Qt.AlignCenter)
        ring = "#55556a" if locked else TIER_COLORS.get(b["tier"], "#55556a")
        icon.setStyleSheet(f"background:{'rgba(255,255,255,0.04)' if locked else 'rgba(255,255,255,0.10)'}; "
                           f"border:2px solid {ring}; border-radius:{size // 2}px; font-size:{int(size * 0.5)}px;")
        return icon

    def _github_icon(self, a: dict[str, str], size: int = 22) -> QLabel:
        icon = QLabel()
        icon.setFixedSize(size, size)
        icon.setToolTip(f"GitHub achievement: {a.get('name', '')}")
        icon.setStyleSheet("background:transparent;")
        self.avatar_loader.request(a.get("image", ""), size, icon.setPixmap)
        return icon

    def _render_badge_strip(self) -> None:
        _clear_layout(self.badge_strip_layout)
        data = getattr(self, "_badges", {})
        mine, github = data.get("earned", []), data.get("github", [])
        shown = 0
        for b in mine:
            if shown >= self.STRIP_MAX:
                break
            icon = self._badge_icon(b)
            icon.setToolTip(f"{b['tier'].capitalize()} {b['name']}: {b['count']} {b['what']}")
            self.badge_strip_layout.addWidget(icon)
            shown += 1
        for a in github:
            if shown >= self.STRIP_MAX:
                break
            self.badge_strip_layout.addWidget(self._github_icon(a))
            shown += 1
        extra = len(mine) + len(github) - shown
        if extra > 0:
            more = QLabel(f"+{extra}")
            more.setStyleSheet(f"color:{THEMES[self._theme_name()]['muted']}; font-size:10.5px; "
                               "font-weight:700; background:transparent;")
            self.badge_strip_layout.addWidget(more)
        self.badge_strip_layout.addStretch(1)
        self.badge_strip.setVisible(bool(mine or github))

    def _update_badge_tab_label(self) -> None:
        seen = set(self.cfg.badges_seen)
        new = [b for b in getattr(self, "_badges", {}).get("earned", []) if f"{b['id']}:{b['tier']}" not in seen]
        btn = self.tab_buttons.get("badges")
        if btn is not None:
            self._badges_new = bool(new)
            self._update_tab_styles()
            btn.setToolTip(f"New badge: {new[0]['emoji']} {new[0]['name']}!" if new else "Your badges")

    def _build_you_tab(self) -> QWidget:
        """You (the Model tab), in two parts as on the phone: 🎖 My month first, then 🧠 Model."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.you_part = "month"
        self.you_buttons: dict[str, QPushButton] = {}
        for part, label in (("month", "\U0001f396  My month"), ("model", "\U0001f9e0  Model")):
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, part=part: self._show_you_part(part))
            self.you_buttons[part] = b
            b.setVisible(False)                  # the dock's planet row chooses the part now (navtree.py)
            row.addWidget(b, 1)
        lay.addLayout(row)
        self.you_stack = QStackedWidget()
        self.you_stack.addWidget(self._build_month_tab())
        self.you_stack.addWidget(self._build_model_tab())
        self.you_stack.addWidget(self._build_cited_tab())
        lay.addWidget(self.you_stack, 1)
        return box

    def _build_cited_tab(self) -> QScrollArea:
        """📑 Cited by (citedby.py): read the first time it's shown, then from OpenAlex once a day."""
        from .citedby_ui import CitedByPage
        self.cited_page = CitedByPage(lambda: THEMES[self._theme_name()], self._load_cited)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self.cited_page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        scroll.viewport().setAutoFillBackground(False)
        return scroll

    def _load_cited(self) -> None:
        self.cited_page.set_data(logic.cited_by(self.cfg))
        self._run_async(lambda: logic.cited_by(self.cfg, refresh=True), self.cited_page.set_data)

    def _show_you_part(self, part: str) -> None:
        self.you_part = part
        self.you_stack.setCurrentIndex({"month": 0, "model": 1, "cited": 2}.get(part, 0))
        self._nav_mark()
        theme = THEMES[self._theme_name()]
        for name, b in self.you_buttons.items():
            on = name == part
            b.setStyleSheet(f"QPushButton {{ background:{theme['tab_active'] if on else theme['btn_bg']}; color:{theme['text']}; "
                            f"border:none; border-radius:9px; padding:6px 8px; font-weight:{700 if on else 500}; }} "
                            f"QPushButton:hover {{ background:{theme['btn_hover']}; }}")
        if part == "month":
            self.month_page.show()
            self._rank_news()
        elif part == "cited":
            if self.cited_page.data is not None:
                self.cited_page.render()           # the theme may have changed
        else:              # re-read (it's a local file) and replay the entrance
            self._load_model_history()
            self._play_model_animations()

    def _build_month_tab(self) -> QScrollArea:
        from .month_ui import MonthPage
        self.month_page = MonthPage(self.cfg, lambda: THEMES[self._theme_name()], self._toast, self._run_async)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self.month_page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        scroll.viewport().setAutoFillBackground(False)
        self.month_page.setAutoFillBackground(False)
        QTimer.singleShot(9000, self._rank_news)
        # careful notifications: a look a minute after opening, then every NOTIFY_MINUTES (notify.py decides)
        QTimer.singleShot(60_000, self._notify_tick)
        self._notify_timer = QTimer(self)
        self._notify_timer.setInterval(NOTIFY_MINUTES * 60_000)
        self._notify_timer.timeout.connect(self._notify_tick)
        self._notify_timer.start()
        # a pending "Is this you?" search (OpenAlex was busy): tried again now and then, quietly
        self._whois_timer = QTimer(self)
        self._whois_timer.setInterval(WHOIS_MINUTES * 60_000)
        self._whois_timer.timeout.connect(self._whois_tick)
        self._whois_timer.start()
        QTimer.singleShot(90_000, self._whois_tick)
        return scroll

    def _whois_tick(self) -> None:
        if not (self.cfg.orcid_id or self.cfg.openalex_id) and isinstance(logic.whois_state().get("pending"), dict):
            self._run_async(lambda: logic.whois_retry(self.cfg), self._whois_found)

    def _whois_found(self, cands: Any) -> None:
        if isinstance(cands, list) and cands:
            self._toast("📄 We found your papers on OpenAlex: is this you? See ⚙ Settings → Your profile.")
            self.whois_section.render()

    def _notify_tick(self) -> None:
        if self.cfg.notify_kinds:                      # nothing switched on: nothing to look at, ever
            self._run_async(lambda: logic.notify_check(self.cfg), self._notified)

    def _notified(self, out: Any) -> None:
        if not isinstance(out, dict):
            return
        from .notify_ui import Notifier
        if getattr(self, "_notifier", None) is None:
            self._notifier = Notifier(QIcon(str(ICON_WINDOW)), self._open_from_notification)
        self._notifier.show(out["title"], out["body"], out["tab"])
        btn = self.tab_buttons.get(out["tab"])
        if btn is not None:
            btn.set_dot(True)
            self._notify_dots = getattr(self, "_notify_dots", set()) | {out["tab"]}

    def _open_from_notification(self, tab: str) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if tab in self.tab_buttons:
            self._switch_tab(tab)

    def _rank_news(self) -> None:
        """A promotion since you were last told: GeekOc says so (once)."""
        try:
            name = logic.rank_news(self.cfg)
        except Exception:
            return
        if name:
            self._toast(f"🎖  Promoted to {name}! See it in You → My month.")

    def _build_badges_tab(self) -> QScrollArea:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 4, 4)
        layout.setSpacing(8)
        self.badges_title = QLabel("Your badges")
        layout.addWidget(self.badges_title)
        self.badges_intro = QLabel("Earned by using myGeeKy: opening things, following people, coming back. "
                                   "Bronze, then silver, then gold.")
        self.badges_intro.setWordWrap(True)
        layout.addWidget(self.badges_intro)
        box = QWidget()
        self.badges_area = QVBoxLayout(box)
        self.badges_area.setContentsMargins(0, 0, 0, 0)
        self.badges_area.setSpacing(6)
        layout.addWidget(box)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        scroll.viewport().setAutoFillBackground(False)
        page.setAutoFillBackground(False)
        return scroll

    def _render_badges(self) -> None:
        from ..achievements import TIER_COLORS
        theme = THEMES[self._theme_name()]
        _clear_layout(self.badges_area)
        data = getattr(self, "_badges", None) or logic.get_badges(self.cfg)
        self.badges_title.setStyleSheet(f"color:{theme['text']}; font-size:15px; font-weight:700; background:transparent;")
        self.badges_intro.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")

        def header(text: str) -> None:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color:{theme['text']}; font-size:10.5px; font-weight:700; letter-spacing:0.5px; "
                              "margin-top:6px; background:transparent;")
            self.badges_area.addWidget(lbl)

        if data.get("github"):
            header("ON GITHUB")
            row = QHBoxLayout()
            row.setSpacing(10)
            for a in data["github"]:
                cell = QVBoxLayout()
                cell.setSpacing(2)
                cell.addWidget(self._github_icon(a, 44), 0, Qt.AlignHCenter)
                name = QLabel(a.get("name", ""))
                name.setTextFormat(Qt.PlainText)
                name.setStyleSheet(f"color:{theme['muted']}; font-size:9.5px; background:transparent;")
                cell.addWidget(name, 0, Qt.AlignHCenter)
                row.addLayout(cell)
            row.addStretch(1)
            self.badges_area.addLayout(row)

        header("ON MYGEEKY")
        for b in sorted(data.get("all", []), key=lambda b: (-b["level"], b["name"])):
            locked = not b["tier"]
            card = QFrame()
            card.setObjectName("badgeCard")
            lay = QHBoxLayout(card)
            lay.setContentsMargins(8, 6, 8, 6)
            lay.setSpacing(10)
            lay.addWidget(self._badge_icon(b, 36, locked=locked))
            body = QVBoxLayout()
            body.setSpacing(1)
            tier = "" if locked else f"  <span style='color:{logic.readable(TIER_COLORS[b['tier']], theme)}'>{b['tier']}</span>"
            name = QLabel(f"<b>{html.escape(b['name'])}</b>{tier}")
            name.setTextFormat(Qt.RichText)
            name.setStyleSheet(f"color:{theme['text'] if not locked else theme['muted']}; font-size:12px; "
                               "background:transparent;")
            body.addWidget(name)
            if b["single"]:
                status = "earned" if not locked else f"not yet: {b['what']}"
            elif b["next"] is None:
                status = f"{b['count']} {b['what']}: the top level!"
            else:
                status = f"{b['count']} of {b['next']} {b['what']}"
            sub = QLabel(status)
            sub.setTextFormat(Qt.PlainText)
            sub.setWordWrap(True)
            sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            sub.setStyleSheet(f"color:{theme['muted']}; font-size:10px; background:transparent;")
            body.addWidget(sub)
            if not b["single"] and b["next"] is not None:
                bar = QProgressBar()
                bar.setRange(0, b["next"])
                bar.setValue(min(b["count"], b["next"]))
                bar.setTextVisible(False)
                bar.setFixedHeight(4)
                bar.setStyleSheet(f"QProgressBar {{ background:rgba(255,255,255,0.08); border:none; border-radius:2px; }}"
                                  f"QProgressBar::chunk {{ background:{theme['accent']}; border-radius:2px; }}")
                body.addWidget(bar)
            lay.addLayout(body, 1)
            card.setStyleSheet(f"QFrame#badgeCard {{ background:{theme['card_bg']}; border-radius:10px; }}")
            self.badges_area.addWidget(card)

    _PROFILE_URL = re.compile(r"^https://github\.com/([A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38})/?$")

    def _open_github(self, url: str, anchor: tuple[QVBoxLayout, QWidget] | None = None) -> bool:
        """A person's profile unfolds their card right under what you clicked;
        repos and everything else open in the browser as before."""
        m = self._PROFILE_URL.match(url or "")
        if not m:
            return logic.open_profile(url)
        login = m.group(1)
        view = getattr(self, "_profile_view", None)
        if view is not None and _alive(view):
            same = view.login.lower() == login.lower()
            view.fold()
            self._profile_view = None
            if same:                                  # a second click on the same person folds it
                return True
        anchor = anchor or self._clicked_item()
        if anchor is None:
            return logic.open_profile(url)
        layout, item = anchor
        view = ProfileView(self, login, THEMES[self._theme_name()])
        layout.insertWidget(layout.indexOf(item) + 1, view)
        self._profile_view = view
        return True

    def _clicked_item(self) -> tuple[QVBoxLayout, QWidget] | None:
        """The list item under the mouse (a card in a scrolling list, or the Live
        spotlight), and the layout it sits in."""
        w = QApplication.widgetAt(QCursor.pos())
        page = self.content_stack.currentWidget()
        fallback = None
        while w is not None and w is not page:
            parent = w.parentWidget()
            lay = parent.layout() if parent is not None else None
            if isinstance(lay, QVBoxLayout) and lay.indexOf(w) >= 0:
                grand = parent.parentWidget()
                if grand is not None and isinstance(grand.parentWidget(), QScrollArea):
                    return lay, w                     # a card in a scrolling list
                if parent is page or (isinstance(page, QScrollArea) and parent is page.widget()):
                    fallback = (lay, w)               # e.g. the Live spotlight
            w = parent
        return fallback

    def _scroll_area_of(self, w: QWidget) -> QScrollArea | None:
        while w is not None:
            if isinstance(w, QScrollArea):
                return w
            w = w.parentWidget()
        return None

    def _fold_profile(self) -> None:
        view = getattr(self, "_profile_view", None)
        if view is not None and _alive(view):
            view.fold()
        self._profile_view = None

    def _opened_profile(self, url: str) -> None:
        """'Open on GitHub to follow' from a card."""
        logic.open_profile(url)
        suggestion = next((s for s in self._last_suggestions if s.get("profile_url") == url), None)
        if suggestion:
            logic.mark_suggestion_seen(suggestion.get("username", ""))
            QTimer.singleShot(0, self._load_suggestions)

    def _on_ticker_clicked(self, url: str) -> bool:
        opened = self._open_github(url)
        suggestion = next((s for s in self._last_suggestions if s.get("profile_url") == url), None)
        if suggestion:  # activity cards are people you already follow -- only suggestions get dropped
            logic.mark_suggestion_seen(suggestion.get("username", ""))
            QTimer.singleShot(0, self._load_suggestions)
        return opened

    # ------------------------------------------------------------------ repos (contribute)
    def _load_contributions(self) -> None:
        self._render_contributions(logic.get_contributions(self.cfg))

    def _on_refresh_contributions(self) -> None:
        if self._contrib_running:
            return  # a repo search is already in flight; don't stack another
        self._contrib_running = True
        self.refresh_repos_btn.setEnabled(False)
        theme = THEMES[self._theme_name()]
        _clear_layout(self.repos_area)
        loading = QLabel("Searching GitHub for repos… this can take a few minutes (rate-limited search API).")
        loading.setWordWrap(True)
        loading.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
        self.repos_area.addWidget(loading)
        self._run_async(lambda: logic.refresh_contributions(self.cfg), self._on_contributions_ready)

    def _on_contributions_ready(self, data: Any) -> None:
        self._contrib_running = False
        self.refresh_repos_btn.setEnabled(True)
        if isinstance(data, dict) and data.get("error"):
            theme = THEMES[self._theme_name()]
            _clear_layout(self.repos_area)
            err = _plain(QLabel(str(data["error"])))
            err.setWordWrap(True)
            err.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
            self.repos_area.addWidget(err)
            return
        self._render_contributions(data)

    def _render_contributions(self, items: list[dict[str, Any]] | None) -> None:
        theme = THEMES[self._theme_name()]
        if self._github_card(self.repos_area, "repos", bool(items), field_only=True):
            return
        _clear_layout(self.repos_area)
        if not items:
            empty = QLabel("No repo suggestions yet — click Refresh, or run `mygeeky contribute`.")
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
            self.repos_area.addWidget(empty)
            return
        mentions = logic.news_mentions([i.get("full_name", "") for i in items])
        if items and not any(i.get("_fresh") == "new" for i in items):
            self.repos_area.addWidget(_caught_up(theme, "You've seen these. myGeeKy looks for more repos in the "
                                                        "background; seen ones come back after a while."))
        for item in items:
            item = {**item, "news": mentions.get(item.get("full_name", ""))}
            self.repos_area.addWidget(_mark_fresh(RepoCard(item, theme, self._opener("repo", item), self.avatar_loader),
                                                  item, theme))
        self._update_fresh_counts()

    # ------------------------------------------------------------------ activity
    def _refresh_activity(self, force: bool) -> None:
        if self._activity_running:          # still busy (GitHub slow): the next tick tries again
            return
        self._activity_running = True
        self._run_async(lambda: logic.get_activity(self.cfg, force=force), self._on_activity_ready)

    def _on_activity_ready(self, data: Any) -> None:
        self._activity_running = False
        if self._github_card(self.activity_area, "activity", bool((data or {}).get("events"))):
            return
        theme = THEMES[self._theme_name()]
        events = (data or {}).get("events") or []
        fetched_at = (data or {}).get("fetched_at")
        same = (events == getattr(self, "_last_activity_events", None)
                and self._theme_name() == getattr(self, "_activity_theme", None))
        if same and self.activity_area.count():
            # the 60-second check found what's already shown: no rebuild of every card and avatar (plan 3)
            if fetched_at:
                self.activity_updated_label.setText("updated " + _time_ago(fetched_at))
            return
        self._activity_theme = self._theme_name()
        _clear_layout(self.activity_area)
        if not events:
            empty = QLabel("No recent activity from people you follow or your profile matches yet.")
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
            self.activity_area.addWidget(empty)
        else:
            groups = freshness.arrange(self.cfg, "activity", logic.group_activity(events), key=_activity_key)
            for group in groups:
                card = ActivityGroup(group, theme, self._open_github, self.avatar_loader,
                                     expanded=group["actor"].lower() in self._expanded_actors)
                card.toggled.connect(self._on_activity_group_toggled)
                self.activity_area.addWidget(_mark_fresh(card, group, theme))
            self._update_fresh_counts()
        fetched_at = (data or {}).get("fetched_at")
        if fetched_at:
            self.activity_updated_label.setText("updated " + _time_ago(fetched_at))
        self._last_activity_events = events
        if not (data or {}).get("cached"):
            self._load_suggestions()  # the refresh also re-read who you follow
        self._update_live_ticker()

    def _on_activity_group_toggled(self, actor: str, expanded: bool) -> None:
        if expanded:
            self._expanded_actors.add(actor.lower())
        else:
            self._expanded_actors.discard(actor.lower())

    # ------------------------------------------------------------------ signals
    def _refresh_signals(self, force: bool) -> None:
        if self._signals_running:
            return
        self._signals_running = True
        self._run_async(lambda: logic.get_signals(self.cfg, force=force), self._on_signals_ready)

    def _on_signals_ready(self, data: Any) -> None:
        self._signals_running = False
        data = data or {}
        if data == getattr(self, "_signals_data", None) and self._theme_name() == getattr(self, "_signals_theme", None):
            return                                   # the 5-minute check found nothing new: no rebuild (plan 3)
        self._signals_theme = self._theme_name()
        self._render_signals(data)
        self._last_incoming = data.get("incoming") or []
        self._update_live_ticker()

    def _render_signals(self, data: dict[str, Any]) -> None:
        from .signals_ui import FieldCard, MyCallCard
        theme = THEMES[self._theme_name()]
        self._signals_data = data
        _clear_layout(self.signals_area)
        muted = f"color:{theme['muted']}; font-size:10.5px; background:transparent;"
        self.signals_hint.setStyleSheet(muted)
        self.signals_updated_label.setStyleSheet(muted)
        self.signals_quiet.setStyleSheet(f"QCheckBox {{ color:{theme['muted']}; font-size:10.5px; "
                                         "background:transparent; }")
        if not data.get("enabled") and self._github_card(self.signals_area, "signals"):
            self.signals_hint.setText("")
            self.refresh_signals_btn.setEnabled(False)
            self.signals_quiet.setVisible(False)
            return
        if not data.get("enabled"):
            self.signals_hint.setText(
                "Send other myGeeKy users small private signals (🙏 📚 👀 🤝), see theirs to you, and invite "
                "people whose skills fit to help with your projects. To join, run `mygeeky beacon init` in a terminal.")
            self.refresh_signals_btn.setEnabled(False)
            self.signals_quiet.setVisible(False)
            return
        self.refresh_signals_btn.setEnabled(True)
        self.signals_quiet.setVisible(bool(data.get("can_send")))
        self.signals_quiet.blockSignals(True)
        self.signals_quiet.setChecked(bool(data.get("quiet")))
        self.signals_quiet.blockSignals(False)
        self.signals_hint.setText("🔒 Private: a signal can only be read by the person it's for, and no reply is "
                                  "ever expected.")
        fetched = data.get("fetched_at")
        self.signals_updated_label.setText(data.get("error") or ("updated " + _time_ago(fetched) if fetched else ""))
        on_send = (lambda card, login, gesture: self._open_send_signal(login, gesture)) if data.get("can_send") else None
        avatar = lambda login, url, size: _avatar_widget(login, url, size, self.avatar_loader)  # noqa: E731
        people = [x for x in data.get("people") or [] if not x.get("muted")]
        calls = data.get("calls") or []
        mine = data.get("my_calls") or []

        # Your field: the folded radar, and the two actions
        field = FieldCard(theme, self._open_invite, lambda: self._open_send_signal(), self.cfg.gui_signals_radar_open,
                          self._on_radar_folded)
        field.set_counts(len(people), len(calls))
        field.map.set_items(
            [{"id": f"c:{c['owner']}/{c['id']}", "login": c["owner"], "label": c["full_name"], "fit": c["fit"],
              "call": True} for c in calls]
            + [{"id": f"p:{x['login']}", "login": x["login"], "label": x["login"], "fit": x.get("fit", 0.0),
                "call": False} for x in people])

        def picked(dot_id: str) -> None:
            _clear_layout(field.picked_area)
            if dot_id.startswith("c:"):
                call = next((c for c in calls if f"c:{c['owner']}/{c['id']}" == dot_id), None)
                if call:
                    field.picked_area.addWidget(self._call_card(call, theme, avatar))
            elif dot_id.startswith("p:"):
                who = next((x for x in people if f"p:{x['login']}" == dot_id), None)
                if who:
                    field.picked_area.addWidget(SignalCard(who, theme, self._open_github, on_send, self.avatar_loader))
        field.map.picked.connect(picked)
        field.invite_btn.setEnabled(bool(data.get("can_send")))
        field.send_btn.setEnabled(bool(data.get("can_send")))
        self.signals_area.addWidget(field)

        def header(text: str, count: int | None = None) -> None:
            lbl = QLabel(text + (f"  <span style='color:{theme['muted']}'>{count}</span>" if count else ""))
            lbl.setTextFormat(Qt.RichText)
            lbl.setStyleSheet("font-size:10.5px; font-weight:700; letter-spacing:0.5px; "
                              f"margin-top:6px; color:{theme['text']}; background:transparent;")
            self.signals_area.addWidget(lbl)

        def empty(text: str) -> None:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(muted)
            self.signals_area.addWidget(lbl)

        incoming = data.get("incoming") or []
        header("FOR YOU", len(incoming))
        if data.get("quiet"):
            held = data.get("held") or 0
            empty("You're not taking signals right now." +
                  (f" {held} signal(s) are waiting for when you're back." if held else ""))
        elif not incoming:
            empty("Nothing yet. Signals here are small thank-yous: no reply is ever expected.")
        for item in incoming:
            if item.get("type") == "join" and item.get("skills"):
                item = {**item, "text": f"{item['text']} · their skills: {', '.join(item['skills'])}"}
            self.signals_area.addWidget(SignalCard(item, theme, self._open_github, on_send, self.avatar_loader,
                                                   on_mute=self._on_mute_signals))

        header("PROJECTS CALLING FOR YOU", len(calls))
        if not calls:
            empty("No calls fit your work right now. When someone invites contributors with your skills, "
                  "it shows here.")
        for call in calls:
            self.signals_area.addWidget(self._call_card(call, theme, avatar))

        header("YOUR CALLS", len(mine))
        for call in mine:
            self.signals_area.addWidget(MyCallCard(call, theme, avatar, self._on_close_call, self._open_github))
        if not mine:
            empty("Invite people whose skills fit to help with one of your repos: they say they're in, privately.")

        header("PEOPLE ON SIGNALS", len(people))
        if not people:
            empty("No other beacons found yet.")
        for item in people:
            self.signals_area.addWidget(SignalCard(item, theme, self._open_github, on_send, self.avatar_loader))

    def _call_card(self, call: dict[str, Any], theme: dict[str, Any], avatar) -> QWidget:
        from .signals_ui import CallCard
        return CallCard(call, theme, avatar, self._on_join_call, self._on_leave_call, self._on_hide_call,
                        self._open_github)

    def _on_radar_folded(self, unfolded: bool) -> None:
        self.cfg.gui_signals_radar_open = unfolded
        from ..config import save_config
        save_config(self.cfg)

    # ------------------------------------------------------------------ calls for contributors
    def _on_join_call(self, card) -> None:
        card.set_busy(True, "Sending…")

        def done(result: Any) -> None:
            if not _alive(card):
                return
            card.set_busy(False)
            if isinstance(result, dict) and result.get("ok"):
                card.set_joined(True)
            else:
                card.set_busy(False, (result or {}).get("error", "Not sent") if isinstance(result, dict) else "Not sent")
        self._run_async(lambda: logic.join_call(self.cfg, card.call), done)

    def _on_leave_call(self, card) -> None:
        card.set_busy(True, "Taking it back…")

        def done(result: Any) -> None:
            if not _alive(card):
                return
            card.set_busy(False)
            if isinstance(result, dict) and result.get("ok"):
                card.set_joined(False)
            else:
                card.set_busy(False, (result or {}).get("error", "Couldn't take it back") if isinstance(result, dict)
                              else "Couldn't take it back")
        self._run_async(lambda: logic.leave_call(self.cfg, card.call["owner"], card.call["id"]), done)

    def _on_hide_call(self, card) -> None:
        logic.hide_call(card.call["owner"], card.call["id"])
        card.hide()

    def _on_close_call(self, card, filled: bool) -> None:
        card.set_busy(True, "Marking it filled…" if filled else "Closing it…")

        def done(result: Any) -> None:
            if isinstance(result, dict) and result.get("ok"):
                self._refresh_signals(force=False)
            elif _alive(card):
                card.set_busy(False, (result or {}).get("error", "Couldn't change it") if isinstance(result, dict)
                              else "Couldn't change it")
        self._run_async(lambda: logic.close_call(self.cfg, card.call["id"], filled), done)

    def _open_invite(self) -> None:
        from .signals_ui import InviteWindow
        theme = THEMES[self._theme_name()]
        open_calls = len([c for c in self._signals_data.get("my_calls") or [] if not c.get("filled")])
        self._show_dialog("_invite_window", lambda: InviteWindow(self, theme, self._on_publish_call, open_calls))
        win = self._invite_window

        def got(repos: Any) -> None:
            if _alive(win):
                win.set_repos(repos if isinstance(repos, list) else [])
        self._run_async(lambda: logic.list_repos_for_call(self.cfg), got)

    def _on_publish_call(self, win, payload: dict[str, Any]) -> None:
        if not self._signals_terms_ok():
            win.set_busy(False, "Agree to the Signals terms to post a call.", error=True)
            return
        win.set_busy(True, "Publishing in your beacon…")

        def done(result: Any) -> None:
            if not _alive(win):
                return
            if isinstance(result, dict) and result.get("ok"):
                win.set_busy(True, "Published. From now on it reaches people whose skills fit.")
                QTimer.singleShot(1400, lambda: _alive(win) and win.close())
                self._refresh_signals(force=False)
            else:
                win.set_busy(False, (result or {}).get("error", "Not published") if isinstance(result, dict)
                             else "Not published", error=True)
        self._run_async(lambda: logic.create_call(self.cfg, **payload), done)

    def _open_send_signal(self, to: str | None = None, gesture: str | None = None) -> None:
        from .signals_ui import SendSignalWindow
        theme = THEMES[self._theme_name()]
        people = list(self._signals_data.get("people") or [])
        if to and not any(x["login"] == to for x in people):      # e.g. someone who signalled you
            people.append({"login": to, "can_receive": True, "fit": 0.0, "interests": [], "shared": []})
        old = getattr(self, "_send_window", None)
        if old is not None and _alive(old):
            old.close()           # a new pick replaces the open one
        self._show_dialog("_send_window", lambda: SendSignalWindow(self, theme, people, self._on_send_from_window,
                                                                   self._load_their_repos, to, gesture))

    def _load_their_repos(self, win, login: str) -> None:
        def got(repos: Any) -> None:
            if _alive(win):
                win.set_repos(login, [r["full_name"] for r in repos] if isinstance(repos, list) else [])
        self._run_async(lambda: logic.list_repos_for_call(self.cfg, login), got)

    def _on_send_from_window(self, win, to: str, gesture: str, repo: str | None) -> None:
        win.set_busy(True, "Sending…")

        def done(result: Any) -> None:
            if not _alive(win):
                return
            if isinstance(result, dict) and result.get("ok"):
                win.set_busy(True, f"Sent privately to {to}. Only they can read it.")
                QTimer.singleShot(1400, lambda: _alive(win) and win.close())
                self._refresh_signals(force=False)
            else:
                win.set_busy(False, (result or {}).get("error", "Not sent") if isinstance(result, dict) else "Not sent",
                             error=True)
        self._run_async(lambda: logic.send_signal(self.cfg, to, gesture, repo), done)

    def _on_quiet_toggled(self, quiet: bool) -> None:
        self.signals_quiet.setEnabled(False)

        def done(result: Any) -> None:
            self.signals_quiet.setEnabled(True)
            if not (isinstance(result, dict) and result.get("ok")):
                self.signals_quiet.blockSignals(True)
                self.signals_quiet.setChecked(not quiet)
                self.signals_quiet.blockSignals(False)
                self.signals_updated_label.setText((result or {}).get("error", "Couldn't change it")
                                                   if isinstance(result, dict) else "Couldn't change it")
            self._refresh_signals(force=False)
        self._run_async(lambda: logic.set_signals_quiet(self.cfg, quiet), done)

    def _on_mute_signals(self, login: str) -> None:
        logic.mute_signals(self.cfg, login, True)
        self.signals_updated_label.setText(f"Muted {login}. They're not told.")
        self._refresh_signals(force=False)

    # ------------------------------------------------------------------ market
    NEWS_HINTS = {
        "airace": "",
        "headlines": "What's happening across your work, as titles: AI labs, journals and the tech press, ranked by "
                     "your interests. \U0001f30d = the big picture.<br>" + BADGE_LEGEND,
        "papers": "New papers and discussions about your interests, from arXiv, bioRxiv and Hacker News. "
                  "\U0001f52d = outside your usual interests, on purpose.<br>" + BADGE_LEGEND,
    }

    def _nav_mark(self) -> None:
        """A part changed inside a page: the planets on its path swell (if the row exists yet)."""
        if getattr(self, "_nav_opening", False):
            return
        if hasattr(self, "nav_buttons") and hasattr(self, "active_tab") and hasattr(self, "content_stack"):
            self._nav_follow()
            self._update_tab_styles()

    def _load_ai_race(self) -> None:
        """The AI race, the first time it's seen: what we have at once, then the newest from GitHub (once a day)."""
        self.airace_page.set_data(logic.ai_race())
        self._run_async(lambda: logic.ai_race(refresh=True), self.airace_page.set_data)

    def _set_news_mode(self, mode: str) -> None:
        self._news_mode = mode
        self._nav_mark()
        self.headlines_box.setVisible(mode == "headlines")
        self.news_box.setVisible(mode == "papers")
        self.airace_page.setVisible(mode == "airace")
        self.news_hint.setText(self.NEWS_HINTS[mode])
        self.news_hint.setVisible(bool(self.NEWS_HINTS[mode]))
        if mode == "airace" and self.airace_page.data is not None:
            self.airace_page.render()              # the theme may have changed
        theme = THEMES[self._theme_name()]
        for m, b in self.news_mode_buttons.items():
            active = m == mode
            b.setStyleSheet(f"QPushButton {{ background:{theme['tab_active'] if active else theme['btn_bg']}; "
                            f"color:{theme['text']}; border:none; border-radius:8px; padding:4px 10px; "
                            f"font-size:11px; font-weight:{'600' if active else '400'}; }}")

    def _load_news(self) -> None:
        self._render_news(logic.get_news(self.cfg))
        self._render_headlines(logic.get_headlines(self.cfg))

    def _render_headlines(self, data: dict[str, Any]) -> None:
        theme = THEMES[self._theme_name()]
        _clear_layout(self.headlines_area)
        items = data.get("items") or []
        if data.get("error") or not items:
            msg = _plain(QLabel(data.get("error") or "No headlines yet. They load in the background (or click Refresh)."))
            msg.setWordWrap(True)
            msg.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
            self.headlines_area.addWidget(msg)
        items = _with_seen_earlier(freshness.arrange(self.cfg, "headline", items, keep_seen=True))
        if items and not any(i.get("_fresh") == "new" for i in items):
            self.headlines_area.addWidget(_caught_up(theme, "You're all caught up. New headlines arrive every few hours."))
        mine = [x for x in items if not x.get("explore")]
        wide = [x for x in items if x.get("explore")]
        for label, group in (("FOR YOUR WORK", mine), ("\U0001f30d THE BIG PICTURE", wide)):
            if not group:
                continue
            head = QLabel(label)
            head.setStyleSheet(f"color:{theme['text']}; font-size:10px; font-weight:700; letter-spacing:0.5px; "
                               "margin-top:6px; background:transparent;")
            self.headlines_area.addWidget(head)
            for item in group:
                self.headlines_area.addWidget(_mark_fresh(HeadlineRow(item, theme, self._opener("headline", item)),
                                                          item, theme))
        self._update_fresh_counts()

    def _maybe_refresh_news(self) -> None:
        if logic.news_refresh_due(self.cfg):
            self._refresh_news(force=False)

    def _refresh_news(self, force: bool) -> None:
        if self._news_running:
            return
        self._news_running = True
        self.refresh_news_btn.setEnabled(False)
        self.news_updated_label.setText("updating\u2026")
        self._run_async(lambda: logic.refresh_news_and_headlines(self.cfg, force=force), self._on_news_ready)

    def _on_news_ready(self, data: Any) -> None:
        self._news_running = False
        self.refresh_news_btn.setEnabled(True)
        data = data if isinstance(data, dict) else {}
        self._render_news(data.get("news") or {})
        self._render_headlines(data.get("headlines") or {})

    def _render_news(self, data: dict[str, Any]) -> None:
        theme = THEMES[self._theme_name()]
        _clear_layout(self.news_area)
        items = data.get("items") or []
        if data.get("error") or not items:
            msg = _plain(QLabel(data.get("error") or "No news yet. It loads in the background (or click Refresh)."))
            msg.setWordWrap(True)
            msg.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
            self.news_area.addWidget(msg)
        items = _with_seen_earlier(freshness.arrange(self.cfg, "news", items, keep_seen=True))
        for item in items:
            self.news_area.addWidget(_mark_fresh(NewsCard(item, theme, self._opener("news", item)), item, theme))
        self._update_fresh_counts()
        updated = data.get("updated_at")
        if not self._news_running:
            self.news_updated_label.setText("updated " + _time_ago(updated) if updated else "")
        for lbl in (self.news_hint, self.news_updated_label):
            lbl.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")

    def _load_market(self) -> None:
        self._render_market(logic.get_market(self.cfg))

    def _maybe_refresh_market(self) -> None:
        if logic.market_refresh_due(self.cfg):
            self._refresh_market(force=False)
        if logic.trends_due(self.cfg):
            self._refresh_research(force=False)

    # ------------------------------------------------------------------ research trends
    def _load_research(self) -> None:
        self._render_research(logic.get_trends(self.cfg))

    def _refresh_research(self, force: bool) -> None:
        if getattr(self, "_research_running", False):
            return
        self._research_running = True
        self.refresh_research_btn.setEnabled(False)
        self.research_updated_label.setText("updating\u2026 (about a minute)")
        self._run_async(lambda: logic.refresh_trends(self.cfg, force=force), self._on_research_ready)

    def _on_research_ready(self, data: Any) -> None:
        self._research_running = False
        self.refresh_research_btn.setEnabled(True)
        self._render_research(data if isinstance(data, dict) else {})

    def _render_research(self, data: dict[str, Any]) -> None:
        theme = THEMES[self._theme_name()]
        _clear_layout(self.research_area)
        topics = ", ".join(t["name"] for t in (data.get("topics") or [])[:4])
        self.research_hint.setText(
            "What's moving in research in your field, from OpenAlex: papers gaining citations fastest, new tools "
            "with their code on GitHub, and who leads them. Click a paper for its repo and the people on it."
            + (f"\nYour topics: {topics}." if topics else ""))

        def header(text: str) -> None:
            lbl = QLabel(text)
            lbl.setStyleSheet("font-size:10.5px; font-weight:700; letter-spacing:0.5px; margin-top:6px; "
                              f"color:{theme['text']}; background:transparent;")
            self.research_area.addWidget(lbl)

        if data.get("error") or not (data.get("rising") or data.get("tools")):
            msg = _plain(QLabel(data.get("error") or "No research trends yet. They load in the background "
                                              "(or click Refresh)."))
            msg.setWordWrap(True)
            msg.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
            self.research_area.addWidget(msg)
        if data.get("rising"):
            header("\U0001f525 RISING IN YOUR FIELD")
            for p in _with_seen_earlier(freshness.arrange(self.cfg, "paper", data["rising"], keep_seen=True)):
                self.research_area.addWidget(_mark_fresh(self._research_card(p, theme, "rising"), p, theme))
        if data.get("tools"):
            header("\U0001f6e0\ufe0f TOOLS WITH PAPERS")
            for p in _with_seen_earlier(freshness.arrange(self.cfg, "paper", data["tools"], keep_seen=True)):
                self.research_area.addWidget(_mark_fresh(self._research_card(p, theme, "tool"), p, theme))
        if data.get("people"):
            header("\U0001f469\u200d\U0001f52c PEOPLE BEHIND THE TRENDS")
            for person in data["people"]:
                self.research_area.addWidget(ResearcherRow(person, theme, logic.open_link))
        updated = data.get("updated_at")
        if not getattr(self, "_research_running", False):
            self.research_updated_label.setText("updated " + _time_ago(updated) if updated else "")
        for lbl in (self.research_hint, self.research_updated_label):
            lbl.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")

    def _research_card(self, paper: dict[str, Any], theme: dict[str, Any], kind: str) -> "ResearchCard":
        repo_item = {"full_name": (paper.get("repos") or [""])[0], "description": paper.get("title", "")}
        return ResearchCard(paper, theme, self._opener("news", paper), self._opener("repo", repo_item),
                            self._on_research_people, self.avatar_loader, kind=kind)

    def _on_research_people(self, card: "ResearchCard", repo: str) -> None:
        def show(people: Any) -> None:
            if shiboken6.isValid(card):                  # Research may have been rebuilt meanwhile
                card.set_people(people if isinstance(people, list) else [], self._opener("person", {"username": repo}))
        self._run_async(lambda: logic.repo_people(self.cfg, repo), show)

    def _refresh_market(self, force: bool) -> None:
        if self._market_running:
            return  # a snapshot is already running; it takes a few minutes
        self._market_running = True
        self.refresh_market_btn.setEnabled(False)
        self.market_updated_label.setText("updating… (a few minutes)")
        self._run_async(lambda: logic.refresh_market(self.cfg, force=force), self._on_market_ready)

    def _on_market_ready(self, data: Any) -> None:
        self._market_running = False
        self.refresh_market_btn.setEnabled(True)
        self._render_market(data or {})

    def _render_market(self, data: dict[str, Any]) -> None:
        theme = THEMES[self._theme_name()]
        rows = data.get("rows") or []
        _clear_layout(self.market_area)
        if data.get("error") or not rows:
            msg = _plain(QLabel(data.get("error") or "No board yet — it builds itself in the background "
                                              "(or click Refresh). The first run takes a few minutes."))
            msg.setWordWrap(True)
            msg.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
            self.market_area.addWidget(msg)
        rows = freshness.arrange(self.cfg, "market", rows)            # seen ones move down for a while
        mentions = logic.news_mentions([r.get("repo", "") for r in rows])
        for row in rows:
            row = {**row, "news": mentions.get(row.get("repo", ""))}
            self.market_area.addWidget(_mark_fresh(MarketRow(row, theme, self._opener("repo", row), self.avatar_loader),
                                                   row, theme))
        self._render_producthunt(data, theme)
        collecting = rows and all(r.get("stars_week") is None for r in rows)
        self.market_hint.setText(
            "The popular, active repos in your field, ranked by momentum: stars gained, commits and PyPI "
            "downloads. ▲▼ = places moved since the last day ranked."
            + (" Star gains appear once there's a day of snapshots." if collecting else ""))
        updated = data.get("updated_at")
        if not self._market_running:
            self.market_updated_label.setText("updated " + _time_ago(updated) if updated else "")
        self.market_hint.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
        self.market_updated_label.setStyleSheet(f"color:{theme['muted']}; font-size:11px; background:transparent;")
        self._update_fresh_counts()

    def _render_producthunt(self, data: dict[str, Any], theme: dict[str, Any]) -> None:
        posts = data.get("producthunt") or []
        header = QLabel("PRODUCT HUNT · LAUNCHES IN YOUR FIELD")
        header.setStyleSheet("font-size:10.5px; font-weight:700; letter-spacing:0.5px; "
                             f"margin-top:8px; color:{theme['text']}; background:transparent;")
        self.market_area.addWidget(header)
        if not posts:
            hint = QLabel("No launches yet. They load with the next board refresh (or click Refresh).")
            hint.setWordWrap(True)
            hint.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
            self.market_area.addWidget(hint)
            return
        for post in posts:
            self.market_area.addWidget(ProductHuntRow(post, theme, logic.open_link, self.avatar_loader))

    # ------------------------------------------------------------------ live spotlight ticker
    def _update_live_ticker(self) -> None:
        items = _build_spotlight_items(self._last_activity_events, self._last_suggestions,
                                       getattr(self, "_last_incoming", []))
        was_running = self.ticker.is_running()
        self.ticker.set_items(items)
        if was_running:
            self.ticker.start(int(self.cfg.gui_live_rotate_seconds * 1000))

    # ------------------------------------------------------------------ model
    def _load_model_history(self) -> None:
        self._render_model(logic.get_model_history())

    def _render_model(self, history: list[dict[str, Any]]) -> None:
        latest = history[-1] if history else {}
        prev = history[-2] if len(history) > 1 else {}
        auc = latest.get("auc")
        grade, explanation = logic.auc_verdict(auc)
        self._model_auc = auc
        self.auc_gauge.set_auc(auc)
        self.model_grade_label.setText(grade)
        self.model_summary_label.setText(explanation)
        self._style_model_grade()

        if auc is not None and prev.get("auc") is not None:
            diff = auc - prev["auc"]
            arrow = "▲" if diff > 0.001 else "▼" if diff < -0.001 else "●"
            self.model_delta_label.setText(f"{arrow} {diff:+.3f} since the previous retrain")
        else:
            self.model_delta_label.setText("")

        n_train, n_pos = latest.get("n_train") or 0, latest.get("n_pos") or 0
        self.model_tiles["examples"].set_value(n_train)
        self.model_tiles["positives"].set_value(n_pos)
        self.model_tiles["rate"].set_value(100 * n_pos / n_train if n_train else 0, lambda v: f"{v:.0f}%")
        self.model_tiles["retrains"].set_value(len(history))

        self.weight_bars.set_weights(logic.get_model_weights())
        self._render_brain()
        self.chart.set_history(history)
        if latest.get("timestamp"):
            self.model_footer_label.setText(
                f"Last retrained {_time_ago(latest['timestamp'])}. Follow people you like, then run "
                f"mygeeky learn -- every follow-back you get teaches it more. Hover the chart for details.")
        else:
            self.model_footer_label.setText("No retrains yet -- run mygeeky bootstrap, then mygeeky learn.")

    def _render_brain(self) -> None:
        brain = logic.get_brain(self.cfg)
        theme = THEMES[self._theme_name()]
        self.interest_map.set_data(brain["user"], brain["field"], brain["learned"], brain["explore"])
        self.brain_intro.setText("Four models shape what you see: your research field, what you've been into "
                                 "lately, room to explore, and who's likely to follow you back.")
        self.local_only.setVisible(not logic.sync_enabled(self.cfg))
        dot = lambda c: f"<span style='color:{c}; font-size:13px'>\u25cf</span>"  # noqa: E731
        ring = f"<span style='color:{MAP_EXPLORE}; font-size:13px'>\u25cc</span>"
        self.map_legend.setText(
            f"{dot(MAP_FIELD)} your research field &nbsp; {dot(MAP_LEARNED)} what you're into lately "
            f"(bigger = stronger) &nbsp; {ring} new territory today. Hover a point for more."
            + ("" if brain["learned"] else "<br><i>Nothing learned yet: click people, repos and news, "
                                           "or follow, star and fork on GitHub, and your map grows.</i>"))
        for key, tile in self.teach_tiles.items():
            tile.set_value(brain["taught"][key])
        self.teach_hint.setText(
            (f"Each action fades to half after {brain['half_life']:g} days, so your map follows where your "
             "work is going. Forks count most, then follows and stars, then clicks.")
            if brain["learning"] else "Learning is off (mygeeky config set interest_learning true).")
        self.explore_donut.set_share(brain["explore_share"])
        share = round(brain["explore_share"] * 100)
        self.explore_label.setText(
            (f"{share}% of every list (People, Repos, News, Research) is kept for things outside your usual "
             "interests, marked 🔭." + (f" Today: {', '.join(brain['explore'])}." if brain["explore"] else ""))
            if share else "Exploration is off (mygeeky config set explore_share 0.2 turns it on).")
        self.brain_title.setStyleSheet(f"color:{theme['text']}; font-size:15px; font-weight:700; background:transparent;")
        for lbl in (self.brain_intro, self.map_legend, self.teach_hint, self.explore_label):
            lbl.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
        for lbl in (self.map_header, self.teach_header, self.explore_header, self.followback_header):
            lbl.setStyleSheet(f"color:{theme['text']}; font-size:10.5px; font-weight:700; letter-spacing:0.5px; "
                              "margin-top:8px; background:transparent;")
        self.interest_map.set_theme_colors(theme["text"], theme["explore"])
        self.explore_donut.set_theme_colors(theme["text"])
        for tile in self.teach_tiles.values():
            tile.apply_theme(theme)
        self._render_keywords()

    # ------------------------------------------------------------------ your keywords
    KW_HINT = ("<span style='color:#34d399'>● green</span>: myGeeKy knows what it means and also looks "
               "for what goes with it. <span style='color:#f87171'>● red</span>: used as a plain word "
               "for now, and passed on so the next dictionary learns it. Click a keyword to see more.")

    def _render_keywords(self) -> None:
        theme = THEMES[self._theme_name()]
        data = logic.get_keywords(self.cfg)
        self._kw_rows = data["rows"]
        if not self._kw_rows:
            chips = f"<span style='color:{theme['muted']}'>No keywords yet. Add a few: they shape every list.</span>"
        else:
            parts = []
            for i, row in enumerate(self._kw_rows):
                color = "#34d399" if row["known"] else "#f87171"
                parts.append(f"<a href='kw:{i}' style='color:{color}; text-decoration:none'>● "
                             f"{html.escape(row['word']).replace(' ', '&nbsp;')}</a>&nbsp;<a href='rm:{i}' style='color:{theme['muted']}; "
                             f"text-decoration:none'>✕</a>")
            chips = " &nbsp;&nbsp; ".join(parts)
        self.kw_chips.setText(f"<span style='font-size:12px'>{chips}</span>")
        self.kw_detail.setText(self.KW_HINT)
        self.kw_detail.setTextFormat(Qt.RichText)
        self.kw_header.setStyleSheet(f"color:{theme['text']}; font-size:10.5px; font-weight:700; "
                                     "letter-spacing:0.5px; margin-top:8px; background:transparent;")
        self.kw_detail.setStyleSheet(f"color:{theme['muted']}; font-size:10.5px; background:transparent;")
        self.kw_input.setStyleSheet(f"QLineEdit {{ background:{theme['card_bg']}; color:{theme['text']}; "
                                    f"border:1px solid {theme['btn_bg']}; border-radius:7px; padding:4px 6px; }}")
        self.kw_add.setStyleSheet(f"QPushButton {{ background:{theme['section_btn']}; color:{theme['text']}; "
                                  "border:none; border-radius:7px; padding:5px 10px; }")

    def _keyword_at(self, link: str) -> tuple[str, dict[str, Any]] | None:
        try:
            action, idx = link.split(":", 1)
            return action, self._kw_rows[int(idx)]
        except (ValueError, IndexError, AttributeError):
            return None

    def _on_keyword_hover(self, link: str) -> None:
        hit = self._keyword_at(link) if link else None
        if hit is None or hit[0] != "kw":
            self.kw_detail.setText(self.KW_HINT)
            return
        self.kw_detail.setText(self._keyword_explained(hit[1]))

    def _keyword_explained(self, row: dict[str, Any]) -> str:
        word = html.escape(row["word"])
        if row["known"]:
            related = ", ".join(html.escape(r) for r in row["related"]) or "its own topic"
            return f"<b>{word}</b> also brings in: {related}."
        return (f"<b>{word}</b> isn't in the dictionary yet, so it's matched as a plain word. "
                "Click it to suggest it to myGeeKy's maker (a GitHub issue you submit).")

    def _on_keyword_link(self, link: str) -> None:
        hit = self._keyword_at(link)
        if hit is None:
            return
        action, row = hit
        if action == "rm":
            words = [r["word"] for r in self._kw_rows if r is not row]
            self._save_keywords(words)
        elif row["known"]:
            self.kw_detail.setText(self._keyword_explained(row))
        else:
            logic.suggest_keyword(row["word"])
            self.kw_detail.setText(f"Your browser opened a suggestion for <b>{html.escape(row['word'])}</b>: "
                                   "click <b>Submit new issue</b> there to send it. Thank you!")

    def _on_add_keyword(self) -> None:
        word = " ".join(self.kw_input.text().split())
        if not word:
            return
        self.kw_input.clear()
        self._save_keywords([r["word"] for r in getattr(self, "_kw_rows", [])] + [word])

    def _save_keywords(self, words: list[str]) -> None:
        self.kw_add.setEnabled(False)

        def done(result: Any) -> None:
            self.kw_add.setEnabled(True)
            self._render_keywords()
            if isinstance(result, dict) and result.get("note"):
                self.kw_detail.setText(html.escape(result["note"]))
        self._run_async(lambda: logic.set_keywords(self.cfg, words), done)

    def _style_model_grade(self) -> None:
        color = _auc_color(getattr(self, "_model_auc", None)).name()
        self.model_grade_label.setStyleSheet(
            f"color:{color}; font-size:20px; font-weight:700; background:transparent;")

    def _play_model_animations(self) -> None:
        for widget in (self.auc_gauge, self.weight_bars, self.chart, *self.model_tiles.values(),
                       self.interest_map, self.explore_donut, *self.teach_tiles.values()):
            widget.play()

    # ------------------------------------------------------------------ tabs
    def _switch_tab(self, name: str) -> None:
        if getattr(self, "settings_panel", None) is not None and self.settings_panel.isVisible():
            self._toggle_settings()                       # a page asked for (a notification, a link): ⚙ steps aside
        # TABS is every tab there is; _tab_order is the ones this panel actually built -- Admin only
        # exists for a maker. The tab buttons already filter on that, so this cannot be reached by
        # clicking; it guards the two lists drifting apart, which would otherwise be a ValueError on a
        # name straight out of the public table.
        if name not in self._tab_order:
            return
        previous = getattr(self, "active_tab", None)
        self.active_tab = name
        if previous and previous != name:
            self._fresh_dirty.add(previous)           # what you saw there makes room next time
        QTimer.singleShot(0, lambda: self._refresh_fresh_tab(name))
        self.content_stack.setCurrentIndex(self._tab_order.index(name))
        if "admin" in (previous, name) and previous != name and self.panel_frame.isVisible():
            self._dock(folded=False)                  # wide for Admin, back to your own width when you leave it
        self._nav_follow()
        self._update_tab_styles()
        if name == "badges":
            self._render_badges()
            logic.mark_badges_seen(self.cfg, [f"{b['id']}:{b['tier']}" for b in self._badges.get("earned", [])])
            self._update_badge_tab_label()
        if name == "model":
            self._show_you_part(self.you_part)
        if name == "researchers":
            self.researchers_page.shown()
        if name == "home":
            self.home_page.shown()
        if name == "chances" and getattr(self, "_chances_pending", False):
            self._render_chances()
        if name in getattr(self, "_notify_dots", set()):     # the notification's dot: seen now
            self._notify_dots.discard(name)
            self.tab_buttons[name].set_dot(False)
