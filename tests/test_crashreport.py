import os
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from mygeeky import crashreport


def _boom():
    raise ValueError("bad feed date")


def _exc():
    try:
        _boom()
    except ValueError as exc:
        return exc


@pytest.fixture
def hooks():
    """install() replaces the process-wide hooks: put them back afterwards."""
    saved = sys.excepthook, threading.excepthook
    yield
    sys.excepthook, threading.excepthook = saved
    import faulthandler
    faulthandler.disable()
    if crashreport._fatal_handle:
        crashreport._fatal_handle.close()
        crashreport._fatal_handle = None


def test_nothing_personal_leaves_the_computer(monkeypatch):
    monkeypatch.setattr(crashreport, "_safe_user", lambda: "jdoe")
    home = str(Path.home())
    text = (f'File "{home}\\AppData\\mygeeky\\x.py", line 3\n'
            "token ghp_" + "a" * 36 + " and github_pat_" + "B" * 40 + "\n"
            "mail jane.doe@uni.edu, user JDoe, login octo-dev\n")
    clean = crashreport.redact(text, login="octo-dev")
    for secret in (home, "ghp_", "github_pat_", "jane.doe@uni.edu", "JDoe", "octo-dev"):
        assert secret not in clean
    assert "~" in clean and "<token>" in clean and "<email>" in clean and "<you>" in clean


def test_the_issue_is_prefilled_titled_and_short_enough(tmp_path):
    path = crashreport.write(tmp_path, "panel", _exc())
    report = path.read_text(encoding="utf-8")
    assert "where: panel" in report and "myGeeKy" in report and "ValueError: bad feed date" in report
    url = crashreport.issue_url(report + "\n" + "x = 1\n" * 3000, note="I clicked News")
    q = parse_qs(urlparse(url).query)
    assert url.startswith("https://github.com/mygeeky/myGeeKy/issues/new?")
    assert q["title"] == ["💥 ValueError in _boom"] and q["labels"] == ["crash"]
    assert q["body"][0].startswith("I clicked News") and len(url) <= crashreport.MAX_URL


def test_errors_on_any_thread_become_one_report_each(tmp_path, hooks):
    got = []
    crashreport.install(tmp_path, on_report=got.append)
    exc = _exc()
    sys.excepthook(type(exc), exc, exc.__traceback__)
    sys.excepthook(type(exc), exc, exc.__traceback__)            # the same error again: not a second report
    t = threading.Thread(target=_boom, name="news-refresh")
    t.start(); t.join()                                           # noqa: E702
    where = sorted(p.read_text(encoding="utf-8").splitlines()[0] for p in got)
    assert len(got) == 2 and where == ["where: background task (news-refresh)", "where: panel"]


def test_reports_are_offered_once_and_old_ones_not_at_all(tmp_path):
    new = crashreport.write(tmp_path, "panel", _exc())
    old = tmp_path / "error-20200101-000000.txt"
    old.write_text("old", encoding="utf-8")
    os.utime(old, (0, 0))
    assert crashreport.pending(tmp_path) == [new]
    crashreport.mark_offered(tmp_path, [new.name])
    assert crashreport.pending(tmp_path) == []


def test_a_hard_crash_is_reported_on_the_next_start(tmp_path, hooks):
    # a real crash: the process dies outright, no Python exception to catch
    code = ("import sys, faulthandler; sys.path.insert(0, sys.argv[2]); from mygeeky import crashreport; "
            "from pathlib import Path; crashreport.install(Path(sys.argv[1])); faulthandler._sigsegv()")
    src = str(Path(crashreport.__file__).parents[1])
    r = subprocess.run([sys.executable, "-c", code, str(tmp_path), src], capture_output=True)
    assert r.returncode != 0 and crashreport.pending(tmp_path) == []
    crashreport.install(tmp_path)                                  # the next start
    [report] = crashreport.pending(tmp_path)
    text = report.read_text(encoding="utf-8")
    assert "hard crash" in text and ("Fatal Python error" in text or "Windows fatal exception" in text)
    crashreport.install(tmp_path)                                  # and only once
    assert len(list(tmp_path.glob("crash-*.txt"))) == 1


def test_what_windows_handles_itself_or_a_clean_end_is_not_a_crash():
    head = "--- started 2026-10-23T10:00:00 · myGeeKy 0.36.0 · Windows-11\n"
    stack = 'Current thread 0x00000d7c (most recent call first):\n  File "splash.py", line 117 in start\n'
    com = head + "Windows fatal exception: code 0x8001010d\n\n" + stack       # the Windows 11 report
    assert crashreport.fatal_crash(com) == "", "COM's own exception, handled by Windows: the panel carried on"
    assert crashreport.fatal_crash(com + crashreport.ENDED + " 2026-10-23T11:00:00\n") == ""
    real = head + "Windows fatal exception: access violation\n\n" + stack
    assert crashreport.fatal_crash(real), "a real crash is still reported"
    assert crashreport.fatal_crash(head + "Windows fatal exception: code 0xc0000409\n\n" + stack)
    assert crashreport.fatal_crash(com + "Fatal Python error: Aborted\n\n" + stack), "COM first, then a real one"
    ended = head + "Windows fatal exception: access violation\n\n" + stack + crashreport.ENDED + " later\n"
    assert crashreport.fatal_crash(ended) == "", "it happened, but the panel went on and closed normally"
    assert crashreport.fatal_crash(ended + "Fatal Python error: Aborted\n"), "an abort while closing still counts"
    assert crashreport.fatal_crash("old run\nFatal Python error: x\n\n" + head) == "", "only the last run"


def test_a_clean_close_is_written_down(tmp_path, hooks):
    crashreport.install(tmp_path)
    crashreport.clean_fatal_log(tmp_path)
    text = (tmp_path / crashreport.FATAL_LOG).read_text(encoding="utf-8")
    assert text.rstrip().splitlines()[-1].startswith(crashreport.ENDED)
    assert crashreport.fatal_crash(text) == ""


def test_a_hard_crash_carries_what_qt_said_just_before_it(tmp_path, hooks):
    # Qt (or the C library) prints its reason to stderr, then aborts: with no terminal, that line was lost
    code = ("import os, sys; sys.path.insert(0, sys.argv[2]); from mygeeky import crashreport; "
            "from pathlib import Path; log = Path(sys.argv[1]); crashreport.install(log, keep_stderr=True); "
            "(log / 'qt.log').write_text('2026-10-12 09:00:00 QtCriticalMsg: QPainter::begin: no device'); "
            "os.write(2, b'QThread: Destroyed while thread is still running'); os.abort()")
    src = str(Path(crashreport.__file__).parents[1])
    r = subprocess.run([sys.executable, "-c", code, str(tmp_path), src], capture_output=True)
    assert r.returncode != 0
    crashreport.install(tmp_path)                                  # the next start
    [report] = crashreport.pending(tmp_path)
    text = report.read_text(encoding="utf-8")
    assert "QThread: Destroyed while thread is still running" in text      # the reason, kept
    assert "Fatal Python error" in text and "QPainter::begin: no device" in text


def test_the_crash_window_shows_the_cleaned_report_without_locking(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from mygeeky.gui.crash_dialog import CrashDialog
    monkeypatch.setattr(crashreport, "_safe_user", lambda: "jdoe")
    path = crashreport.write(tmp_path, "panel", _exc(), text="token ghp_" + "z" * 36 + " for jdoe\n")
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))
    dlg = CrashDialog(None, [path], tmp_path, login="me")
    shown = dlg.view.toPlainText()
    assert "ghp_" not in shown and "jdoe" not in shown and dlg.isModal() is False
    assert crashreport.pending(tmp_path) == []                     # "Not now" doesn't bring it back
    dlg._send()
    for t in threading.enumerate():
        if t is not threading.current_thread() and t.daemon:
            t.join(2)
    assert opened and "issues/new" in opened[0] and "ghp_" not in opened[0]
    dlg._email()                                                   # no GitHub: the same, as an email
    for t in threading.enumerate():
        if t is not threading.current_thread() and t.daemon:
            t.join(2)
    assert opened[-1].startswith("mailto:support@mygeeky.org?") and "ghp_" not in opened[-1] and "jdoe" not in opened[-1]
    dlg._copy()
    copied = QApplication.clipboard().text()
    assert copied == dlg.view.toPlainText(), "the whole cleaned report, as shown"
    assert "ghp_" not in copied and "jdoe" not in copied
    dlg.close()


def test_the_email_is_short_enough_for_mail_apps_and_keeps_the_error():
    from urllib.parse import unquote
    home = str(Path.home())
    report = ("where: panel\nmyGeeKy 1.0 · Python 3.12\n\nTraceback (most recent call last):\n"
              + f'File "{home}/x.py", line 3, in _render_news\n    x = 1\n' * 400
              + "ValueError: bad news from jdoe@example.org\n")
    url = crashreport.email_url(report + "\n\n=====\n\n" + report, login="", note="I clicked News")
    assert len(url) <= crashreport.MAX_MAILTO + 400 and url.startswith("mailto:support@mygeeky.org?subject=")
    text = unquote(url)
    assert "💥 ValueError in _render_news" in text and "I clicked News" in text
    assert "ValueError: bad news from <email>" in text and "where: panel" in text and f"{home}/x.py" not in text


def test_two_errors_in_the_same_instant_are_two_reports(tmp_path, monkeypatch):
    class Frozen:                                   # Windows' clock often repeats a microsecond
        @staticmethod
        def now(tz=None):
            from datetime import datetime as real
            return real(2026, 10, 9, 12, 0, 0, 123456)
    monkeypatch.setattr(crashreport, "datetime", Frozen)
    a = crashreport.write(tmp_path, "panel", _exc())
    b = crashreport.write(tmp_path, "background task (x)", _exc())
    assert a != b and a.read_text(encoding="utf-8").startswith("where: panel")


def test_a_long_hard_crash_keeps_its_cause_and_the_crashed_thread():
    # issue #5: a fatal dump with many threads lost its first lines ("Fatal Python error") to the trimming
    site = "~\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\mygeeky"
    thread = "".join(f'  File "{site}\\{f}", line {n} in {fn}\n' for f, n, fn in [
        ("github_client.py", 117, "_get"), ("github_client.py", 193, "list_user_events"),
        ("activity.py", 137, "get_matched_activity"), ("gui\\app.py", 558, "get_activity"),
        ("gui\\qt_panel.py", 5400, "<lambda>"), ("gui\\qt_panel.py", 348, "run")])
    report = ("where: hard crash (the program closed)\nmyGeeKy 0.21.4 · Python 3.12\n\n"
              "Fatal Python error: Aborted\n\n"
              + "".join(f"Thread 0x{i:08x} (most recent call first):\n{thread}\n" for i in range(30))
              + f'Current thread 0x000089c0 (most recent call first):\n  File "{site}\\gui\\app.py", line 1215 in _main\n')
    url = crashreport.issue_url(report)
    body = parse_qs(urlparse(url).query)["body"][0]
    assert "Fatal Python error: Aborted" in body and "Current thread" in body and "…" in body
    assert len(url) <= crashreport.MAX_URL


def _block(version: str, command: str, func: str, what: str, lines: int = 90) -> str:
    """One report file's worth of text: a six-line header, then a traceback of its own."""
    return (f"myGeeKy {version} (command line)\nPython 3.12.10 at ~\\python.exe\n"
            f"Windows-11-10.0.26200-SP0\nCommand: ~\\mygeeky\\__main__.py {command}\n\n"
            f"What went wrong: {what}\n\n"
            + "Traceback (most recent call last):\n"
            + "".join(f'  File "~\\mygeeky\\cli.py", line {1000 + i} in middle_{i}\n' for i in range(lines))
            + f'  File "~\\mygeeky\\cli.py", line 1418, in {func}\n    click.echo(something)\n{what}\n')


def test_a_burst_of_reports_keeps_each_header_with_its_own_traceback():
    """issue #6: the newest report's header sat above an older report's traceback.

    The header said `profile show` and the traceback below it was in `interests_cmd`, so the report
    named a command that had not failed -- and the diagnosis started in the wrong place."""
    newest = _block("0.25.0", "interests", "interests_cmd", "OSError: [Errno 22] Invalid argument")
    older = _block("0.24.0", "profile show", "profile_show", "UnicodeEncodeError: 'charmap' codec")
    url = crashreport.issue_url(newest + "\n\n=====\n\n" + older)
    body = parse_qs(urlparse(url).query)["body"][0]

    assert len(url) <= crashreport.MAX_URL
    for shown in [b for b in body.split("=====") if "Command:" in b]:
        command = [ln for ln in shown.splitlines() if ln.startswith("Command:")][0]
        if "interests_cmd" in shown:
            assert command.endswith("interests"), f"header does not match its traceback:\n{command}"
            assert "profile_show" not in shown, "two different crashes in one block"
        if "profile_show" in shown:
            assert command.endswith("profile show"), f"header does not match its traceback:\n{command}"


def test_an_older_report_is_dropped_whole_rather_than_spliced():
    """When it will not all fit, a whole report goes -- never a header without its traceback."""
    blocks = [_block("0.25.0", f"cmd{i}", f"func_{i}", f"Error number {i}", lines=400) for i in range(3)]
    url = crashreport.issue_url("\n\n=====\n\n".join(blocks))
    body = parse_qs(urlparse(url).query)["body"][0]

    assert len(url) <= crashreport.MAX_URL
    assert "Command: ~\\mygeeky\\__main__.py cmd0" in body, "the newest report is the one to keep"
    assert "func_0" in body, "the newest report lost its own traceback"
    assert "left out to keep this link short" in body, "silently dropped the older reports"
