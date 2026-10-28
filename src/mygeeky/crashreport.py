"""Crash reports you can send to myGeeKy's GitHub issues, after seeing them.

Every failure is caught and saved as a report in myGeeKy's logs folder:
  * errors in the panel (sys.excepthook) and in its background threads
    (threading.excepthook);
  * hard crashes that kill the program outright (faulthandler writes the
    stack of every thread to fatal.log; offered on the next start);
  * Qt's own critical/fatal messages (qt.log).

Nothing is ever sent by itself. myGeeKy offers the report, shows exactly what
it contains, and "Report on GitHub" opens a prefilled issue that you submit
yourself (like the 💡). No GitHub? "Email it" opens the same report as a
ready-made email to SUPPORT_EMAIL in your own mail app, and you press Send.
Before it's shown, tokens, email addresses, your username and your home folder
are removed from it.

Standard library only (the frozen installer can import it too).
"""

from __future__ import annotations

import getpass
import json
import platform
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from .files import write_json

REPO = "mygeeky/myGeeKy"
SUPPORT_EMAIL = "support@mygeeky.org"   # the same inbox as the 💡's email (ideas.py)
MAX_URL = 7500                     # browsers and GitHub cope with this length
MAX_MAILTO = 1800                  # some mail apps cut a mailto: link near 2000 characters
OFFERED_FILE = "crash-offered.json"
FATAL_LOG = "fatal.log"
MAX_PER_RUN = 20
OFFER_DAYS = 14                    # older reports are kept in the folder but not offered

_TOKEN = re.compile(r"\b(github_pat_[A-Za-z0-9_]{20,}|gh[opsu]_[A-Za-z0-9._\-]{20,}|ph_[A-Za-z0-9]{20,})")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def redact(text: str, login: str = "") -> str:
    """Remove anything personal before a report leaves the computer."""
    text = _TOKEN.sub("<token>", text)
    text = _EMAIL.sub("<email>", text)
    home = str(Path.home())
    for variant in {home, home.replace("\\", "/"), home.replace("\\", "\\\\")}:
        if variant and len(variant) > 3:
            text = text.replace(variant, "~")
    names = {n for n in (login, _safe_user()) if n and len(n) >= 3}
    for name in names:
        text = re.sub(re.escape(name), "<you>", text, flags=re.I)
    return text


def _safe_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return ""


def environment() -> str:
    """Version and system line, the same in every report."""
    try:
        from . import __version__ as version
    except Exception:
        version = "?"
    qt = ""
    try:
        from PySide6 import __version__ as qt
        qt = f", PySide6 {qt}"
    except Exception:
        pass
    frozen = " (installer)" if getattr(sys, "frozen", False) else ""
    return f"myGeeKy {version}{frozen} · Python {platform.python_version()}{qt} · {platform.platform()}"


def write(log_dir: Path, where: str, exc: BaseException | None = None, text: str = "") -> Path | None:
    """Save one report (the full traceback, nothing removed yet: it stays on this computer)."""
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        body = text or ("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if exc else "")
        stamp = f"crash-{datetime.now():%Y%m%d-%H%M%S-%f}"
        for n in range(1000):     # Windows' clock can give two errors the same microsecond: never overwrite
            path = log_dir / (f"{stamp}.txt" if n == 0 else f"{stamp}-{n}.txt")
            try:
                with open(path, "x", encoding="utf-8") as fh:
                    fh.write(f"where: {where}\n{environment()}\n\n{body}")
                return path
            except FileExistsError:
                continue
        return None
    except OSError:
        return None


def headline(report: str) -> str:
    """'ValueError in _render_news' from a report, for the issue title."""
    exc_line = next((l for l in reversed(report.splitlines()) if re.match(r"^[A-Za-z_][\w.]*(Error|Exception|Warning|Exit|Interrupt)\b", l)), "")
    exc = exc_line.split(":")[0].split(".")[-1] if exc_line else ""
    frames = re.findall(r'File "[^"]*", line \d+, in (\w+)', report)
    func = frames[-1] if frames else ""
    if "Fatal Python error" in report or "Windows fatal exception" in report:
        exc = exc or "Crash"
    return (f"{exc} in {func}" if exc and func else exc or func or "Crash").strip()


SEPARATOR = "\n\n=====\n\n"        # how a burst of reports arrives here, newest first


def _shortened(report: str, login: str, build, limit: int) -> str:
    """The longest honest link `build(report_text)` makes within `limit`.

    Every report is trimmed inside its own boundaries. A burst of errors arrives as several reports
    joined by `=====`; this used to keep the first six lines of the whole lot and the last seventy,
    which spliced the *first* report's header onto the *last* report's traceback with a '…' between
    them. Issue #6 came in that shape: the header said `profile show` while the traceback below it
    was in `interests_cmd`, and the version named was not the version that crashed either. A report
    that cannot be trusted to say which command failed costs more time than the trimming saves, so a
    whole older report is dropped rather than half of one."""
    clean = redact(report, login)
    blocks = [b.strip() for b in clean.split(SEPARATOR.strip("\n")) if b.strip()] or [clean]

    def trim(block: str) -> str:
        lines = block.splitlines()
        head, rest = lines[:6], lines[6:]             # where, version, command, a hard crash's cause
        kept = rest[-70:] if len(rest) > 70 else rest  # the end: the error, or the thread that crashed
        return "\n".join(head + (["…"] if len(kept) < len(rest) else []) + kept)

    newest, others = trim(blocks[0]), [trim(b) for b in blocks[1:]]
    while True:
        left_out = len(blocks) - 1 - len(others)
        tail_note = f"{SEPARATOR}(and {left_out} earlier report(s), left out to keep this link short)" \
            if left_out else ""
        url = build(SEPARATOR.join([newest] + others) + tail_note)
        if len(url) <= limit:
            return url
        if others:
            others.pop()                              # a whole older report goes, never part of one
            continue
        lines = newest.splitlines()
        if len(lines) <= 10:
            return url                                # as short as this can honestly be made
        head, rest = lines[:6], lines[6:]             # its own header stays with its own traceback
        newest = "\n".join(head + ["…"] + rest[len(rest) // 4:])


def issue_url(report: str, login: str = "", note: str = "") -> str:
    """A prefilled 'new issue' page with the cleaned report (you submit it)."""
    intro = (note.strip() + "\n\n") if note.strip() else "**What were you doing when it happened?**\n\n\n"

    def build(body_report: str) -> str:
        body = f"{intro}**Crash report** (sent from myGeeKy, personal details removed):\n```\n{body_report}\n```"
        return f"https://github.com/{REPO}/issues/new?" + urlencode(
            {"title": f"💥 {headline(report)}", "body": body, "labels": "crash"})
    return _shortened(report, login, build, MAX_URL)


def email_url(report: str, login: str = "", note: str = "") -> str:
    """The same cleaned report as a ready-made email to SUPPORT_EMAIL (you send it from your own mail app):
    for people without GitHub, or who'd rather not post it in public. Plain text, and short enough for
    mail apps, so it keeps the header and the end of the newest traceback; "Copy report" has the rest."""
    intro = (note.strip()[:500] + "\n\n") if note.strip() else "What were you doing when it happened?\n\n\n"
    enc = lambda s: quote(s, safe="!~*'()")  # noqa: E731

    def build(body_report: str) -> str:
        body = f"{intro}Crash report (sent from myGeeKy, personal details removed):\n\n{body_report}\n"
        return f"mailto:{SUPPORT_EMAIL}?subject={enc(f'💥 {headline(report)}')}&body={enc(body)}"
    return _shortened(report, login, build, MAX_MAILTO)


# --------------------------------------------------------------------------- which reports to offer
def _offered(log_dir: Path) -> set[str]:
    try:
        return set(json.loads((log_dir / OFFERED_FILE).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def mark_offered(log_dir: Path, names: list[str]) -> None:
    try:
        seen = sorted(_offered(log_dir) | set(names))[-200:]
        write_json((log_dir / OFFERED_FILE), seen)
    except OSError:
        pass


def pending(log_dir: Path) -> list[Path]:
    """Recent reports not offered yet, newest first."""
    if not log_dir.exists():
        return []
    seen = _offered(log_dir)
    cutoff = datetime.now().timestamp() - OFFER_DAYS * 86400
    # crash-*: the panel's errors; error-*: a panel that couldn't start, or a failed command
    out = [p for pat in ("crash-*.txt", "error-*.txt") for p in log_dir.glob(pat)
           if p.name not in seen and p.stat().st_mtime > cutoff]
    return sorted(out, key=lambda p: p.stat().st_mtime, reverse=True)


ENDED = "--- ended cleanly"
# Windows raises these inside its own COM / accessibility layer and handles them itself, but faulthandler
# writes down every error-level exception it sees, handled or not. A run that only logged these didn't crash.
# 0x8001010d (RPC_E_CANTCALLOUT_ININPUTSYNCCALL) arrived from a Windows 11 user as a "hard crash" while the
# intro was being shown, and the panel had carried on.
HANDLED_BY_WINDOWS = {"0x8001010d", "0x8001010e", "0x80010108", "0x800706ba", "0x800706be", "0xe06d7363"}
_WIN_EXC = re.compile(r"Windows fatal exception: (?:code )?(\S+)")


def fatal_crash(log: str) -> str:
    """The last hard crash in fatal.log ('' if the last run ended cleanly).

    Only what came after a clean end counts (Qt can still abort while the program closes), and a run whose only
    trouble is exceptions Windows handles itself isn't a crash."""
    last_run = log.rsplit("\n--- started ", 1)[-1]
    after = last_run.rsplit(f"\n{ENDED}", 1)[-1] if f"\n{ENDED}" in last_run else last_run
    real = "Fatal Python error" in after or any(code.lower() not in HANDLED_BY_WINDOWS
                                                 for code in _WIN_EXC.findall(after))
    return last_run if real else ""


def offer_key(path: Path) -> str:
    return path.name


# --------------------------------------------------------------------------- catching
_fatal_handle: Any = None


def install(log_dir: Path, on_report=None, keep_stderr: bool = False) -> None:
    """Catch errors everywhere in this process. `on_report(path)` is called (on
    whatever thread failed) when a new report was saved. `keep_stderr` (the panel):
    error output goes into fatal.log too, so a hard crash says why."""
    global _fatal_handle
    import faulthandler
    import threading
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        fatal = log_dir / FATAL_LOG
        # the last run died outright (no Python error to catch): turn it into a report first
        crash = fatal_crash(fatal.read_text(encoding="utf-8", errors="replace")) if fatal.exists() else ""
        if crash:
            write(log_dir, "hard crash (the program closed)", text=crash.split("\n", 1)[-1] + _qt_tail(log_dir))
        _fatal_handle = open(log_dir / FATAL_LOG, "a", encoding="utf-8")   # kept open for the process lifetime
        _fatal_handle.write(f"\n--- started {datetime.now(timezone.utc).isoformat()} · {environment()}\n")
        _fatal_handle.flush()
        faulthandler.enable(file=_fatal_handle, all_threads=True)
        if keep_stderr:
            _keep_last_words(_fatal_handle)
    except OSError:
        pass

    seen_here: dict[str, int] = {}

    def saved(where: str, exc: BaseException) -> None:
        # the same error over and over (e.g. in a timer) is one report, and a run writes at most 20
        sig = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)[-3:])
        seen_here[sig] = seen_here.get(sig, 0) + 1
        if seen_here[sig] > 1 or len(seen_here) > MAX_PER_RUN:
            return
        path = write(log_dir, where, exc)
        if path and on_report:
            try:
                on_report(path)
            except Exception:
                pass

    def main_hook(kind, exc, tb):
        if issubclass(kind, KeyboardInterrupt):
            return sys.__excepthook__(kind, exc, tb)
        saved("panel", exc.with_traceback(tb))

    def thread_hook(args):
        if args.exc_type is SystemExit:
            return
        saved(f"background task ({getattr(args.thread, 'name', '?')})", args.exc_value.with_traceback(args.exc_traceback))

    sys.excepthook = main_hook
    threading.excepthook = thread_hook


def _keep_last_words(handle) -> None:
    """Started from a menu or at sign-in there's no terminal, so what the C++ side prints
    just before it aborts ("QThread: Destroyed while...", "free(): invalid pointer") was lost.
    Send this process's error output (file descriptor 2) into fatal.log instead: a hard
    crash then carries its reason. Left alone when a terminal is there to show it."""
    import os
    try:
        if sys.stderr is not None and sys.stderr.isatty():
            return
    except (OSError, ValueError, AttributeError):
        pass
    try:
        sys.stderr is not None and sys.stderr.flush()
        os.dup2(handle.fileno(), 2)
    except (OSError, ValueError, AttributeError):
        pass


def _qt_tail(log_dir: Path, lines: int = 12) -> str:
    """Qt's last critical messages, for a hard-crash report."""
    try:
        text = (log_dir / "qt.log").read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except OSError:
        return ""
    return ("\nQt's last messages:\n" + "\n".join(text) + "\n") if text else ""


def qt_message_handler(log_dir: Path):
    """For qInstallMessageHandler: keep Qt's critical and fatal messages in qt.log."""
    def handler(mode, context, message):
        try:
            from PySide6.QtCore import QtMsgType
            if mode in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
                with open(log_dir / "qt.log", "a", encoding="utf-8") as fh:
                    fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {mode.name}: {message}\n")
                if mode == QtMsgType.QtFatalMsg:
                    write(log_dir, "Qt fatal error", text=f"Qt fatal error: {message}\n")
        except Exception:
            pass
    return handler


def clean_fatal_log(log_dir: Path) -> None:
    """The panel closed normally: say so in fatal.log (what Windows logged before this wasn't a crash), and keep
    the file small."""
    try:
        if _fatal_handle is not None and not _fatal_handle.closed:
            _fatal_handle.write(f"{ENDED} {datetime.now(timezone.utc).isoformat()}\n")
            _fatal_handle.flush()
    except (OSError, ValueError):
        pass
    try:
        for log in (log_dir / FATAL_LOG, log_dir / "qt.log"):      # Qt's critical messages are kept, but not forever
            if log.exists() and log.stat().st_size > 200_000:
                log.write_text(log.read_text(encoding="utf-8", errors="replace")[-50_000:], encoding="utf-8")
    except OSError:
        pass
