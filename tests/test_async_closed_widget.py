"""A slow lookup must not crash when its widget closes first (issue #4: a
profile folded while the person was still loading)."""
import sys
import threading

import pytest

pytest.importorskip("PySide6", reason="PySide6 (the 'gui' extra) is not installed")

from mygeeky.gui import app as logic
from test_window_place import _close, _panel, _wait, no_save, qapp  # noqa: F401


def test_a_profile_closed_mid_load_is_skipped_quietly(qapp, monkeypatch, no_save):
    import shiboken6
    from mygeeky.gui.app import THEMES
    from mygeeky.gui.qt_panel import ProfileView
    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda *exc: errors.append(exc[1]))   # Qt slots report here
    release = threading.Event()
    monkeypatch.setattr(logic, "person_card", lambda login: release.wait(5) and {"error": "late"})
    panel = _panel(monkeypatch)
    try:
        view = ProfileView(panel, "someone", THEMES["midnight"])
        shiboken6.delete(view)                     # folded and gone before the answer arrives
        release.set()
        for w in list(panel._workers):
            w.wait(5000)
        _wait(qapp, 0.3)                           # the answer lands: no RuntimeError
        assert not errors and not panel._workers
    finally:
        _close(panel)


def test_activity_refreshes_never_pile_up(qapp, monkeypatch, no_save):
    # issue #5: the 60 s timer started a new Activity fetch while the last was still waiting on GitHub
    release = threading.Event()
    calls = []
    panel = _panel(monkeypatch)
    monkeypatch.setattr(logic, "get_activity", lambda cfg, force=False: calls.append(1) or release.wait(5) and {"events": []})
    try:
        for w in list(panel._workers):
            w.wait(5000)
        _wait(qapp, 0.2)
        calls.clear()
        panel._refresh_activity(force=False)
        panel._refresh_activity(force=False)
        panel._refresh_activity(force=True)
        _wait(qapp, 0.2)
        assert len(calls) == 1                     # one at a time
        release.set()
        for w in list(panel._workers):
            w.wait(5000)
        _wait(qapp, 0.2)
        panel._refresh_activity(force=False)       # finished: the next tick runs again
        for w in list(panel._workers):
            w.wait(5000)
        assert len(calls) == 2
    finally:
        _close(panel)


def test_leaving_with_work_running_records_no_crash(monkeypatch):
    import faulthandler
    import os
    from mygeeky.gui import app as gui_app
    disabled = []
    monkeypatch.setattr(faulthandler, "disable", lambda: disabled.append(1))
    monkeypatch.setattr(sys, "platform", "linux")              # skip the Windows TerminateProcess here
    monkeypatch.setattr(os, "_exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
    with pytest.raises(SystemExit):
        gui_app._leave_now()
    assert disabled                                            # Qt's abort at exit is no longer a "crash"
