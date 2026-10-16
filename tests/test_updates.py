import json
from datetime import datetime, timedelta, timezone

import pytest

from mygeeky import updates


def test_version_comparison():
    assert updates.is_newer("0.4.10", "0.4.9")
    assert updates.is_newer("1.0", "0.9.9")
    assert not updates.is_newer("0.4.3", "0.4.3")
    assert not updates.is_newer("0.4.2", "0.4.3")
    assert not updates.is_newer(None, "0.4.3")


def test_check_uses_a_fresh_cache_and_refreshes_a_stale_one(monkeypatch):
    calls = []
    monkeypatch.setattr(updates, "latest_version", lambda timeout=4.0: calls.append(1) or "99.0.0")
    first = updates.check()
    assert first["newer"] and first["latest"] == "99.0.0" and calls == [1]
    updates.check()                       # within a day: no second request
    assert calls == [1]
    stale = {"latest": "99.0.0", "checked_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()}
    updates.UPDATE_CHECK_FILE.write_text(json.dumps(stale), encoding="utf-8")
    updates.check()
    assert calls == [1, 1]


def test_a_failed_request_keeps_the_last_answer(monkeypatch):
    monkeypatch.setattr(updates, "latest_version", lambda timeout=4.0: "99.0.0")
    updates.check(force=True)
    monkeypatch.setattr(updates, "latest_version", lambda timeout=4.0: None)
    assert updates.check(force=True)["latest"] == "99.0.0"


def _an_update_is_waiting(monkeypatch, latest="99.0.0"):
    """run_upgrade() asks whether there is anything to do first, so a test about *how* it updates
    has to say that there is."""
    monkeypatch.setattr(updates, "check", lambda *a, **k: {
        "current": updates.__version__, "latest": latest, "newer": True, "checked_at": None})


def test_developer_installs_are_never_pip_upgraded(monkeypatch):
    _an_update_is_waiting(monkeypatch)
    monkeypatch.setattr(updates, "is_editable", lambda: True)
    monkeypatch.setattr(updates.subprocess, "run", lambda *a, **k: pytest.fail("pip must not run"))
    ok, message = updates.run_upgrade()
    assert not ok and "git pull" in message


def test_nothing_to_do_is_said_as_success_not_as_a_failed_update(monkeypatch):
    """The banner can sit on screen for hours. If the copy was updated some other way meanwhile,
    clicking Update must not report a failure for something that is already done."""
    monkeypatch.setattr(updates, "check", lambda *a, **k: {
        "current": updates.__version__, "latest": updates.__version__, "newer": False,
        "checked_at": None})
    monkeypatch.setattr(updates.subprocess, "run", lambda *a, **k: pytest.fail("pip must not run"))
    ok, message = updates.run_upgrade()
    assert ok, message
    assert "already the latest" in message and updates.__version__ in message


def test_upgrade_runs_pip_for_this_python(monkeypatch):
    _an_update_is_waiting(monkeypatch)
    monkeypatch.setattr(updates, "is_editable", lambda: False)
    monkeypatch.setattr(updates, "installed_version", lambda: "99.0.0")
    seen = []

    class Done:
        returncode, stdout, stderr = 0, "Successfully installed mygeeky-99.0.0", ""
    monkeypatch.setattr(updates.subprocess, "run", lambda cmd, **k: seen.append(cmd) or Done())
    ok, message = updates.run_upgrade()
    assert ok and "99.0.0" in message
    assert seen[0][1:] == ["-m", "pip", "install", "--upgrade", "--disable-pip-version-check", "mygeeky"]


def test_update_command(monkeypatch):
    from click.testing import CliRunner

    import mygeeky.cli as cli
    monkeypatch.setattr(updates, "check", lambda force=False, **k: {"current": "0.4.3", "latest": "0.5.0",
                                                                    "newer": True, "checked_at": "x"})
    monkeypatch.setattr(updates, "run_upgrade", lambda: (True, "Updated to myGeeKy 0.5.0."))
    result = CliRunner().invoke(cli.main, ["update"])
    assert result.exit_code == 0 and "Updated to myGeeKy 0.5.0." in result.output
    result = CliRunner().invoke(cli.main, ["update", "--check"])
    assert "0.5.0 is available" in result.output and "Updating" not in result.output
    monkeypatch.setattr(updates, "check", lambda force=False, **k: {"current": "0.4.3", "latest": "0.4.3",
                                                                    "newer": False, "checked_at": "x"})
    assert "latest myGeeKy" in CliRunner().invoke(cli.main, ["update"]).output


def test_update_notice_never_appears_in_scripts(monkeypatch, capsys):
    import mygeeky.cli as cli
    monkeypatch.setattr(updates, "check", lambda **k: pytest.fail("no check outside a terminal"))
    monkeypatch.setattr("sys.argv", ["mygeeky", "run", "--json"])
    cli._maybe_announce_update()     # not a tty, and --json: silent, no network
    assert capsys.readouterr().err == ""


def test_banner_shows_hides_and_remembers_later(monkeypatch):
    pytest.importorskip("PySide6")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])

    from mygeeky.config import MyGeekyConfig, load_config, save_config
    from mygeeky.gui import app as logic
    from mygeeky.gui.qt_panel import MyGeekyPanel

    monkeypatch.setattr(logic, "get_contributions", lambda cfg: [])
    monkeypatch.setattr(logic, "get_suggestions", lambda cfg: {"followback": [], "domain_highlights": []})
    monkeypatch.setattr(logic, "get_activity", lambda cfg, force=False: {"events": []})
    monkeypatch.setattr(logic, "get_model_history", lambda: [])
    monkeypatch.setattr(logic, "get_friend_stats", lambda cfg: {
        "total_friends": 0, "new_this_week": 0, "follow_back_rate": None, "total_labeled": 0})
    save_config(MyGeekyConfig())
    panel = MyGeekyPanel(load_config())
    try:
        info = {"show": True, "latest": "0.5.0", "current": "0.4.3", "editable": False,
                "releases_url": updates.RELEASES_URL}
        panel._on_update_info(info)
        assert not panel.update_banner.isHidden() and "0.5.0" in panel.update_label.text()
        assert not panel.update_btn.isHidden()
        panel._on_update_info({**info, "editable": True})
        assert panel.update_btn.isHidden() and "git pull" in panel.update_label.text()
        panel._on_update_later()
        assert panel.update_banner.isHidden() and load_config().update_dismissed == "0.5.0"
        # A failure offers the way out for this install, not just "Try again" -- trying again cannot
        # work when the Python needs administrator rights, or when pip must not touch this copy.
        panel._on_update_done({"ok": False, "message": "no internet",
                               "steps": {"how": "pip", "what": "myGeeKy is a pip package.",
                                         "command": "python -m pip install --upgrade mygeeky",
                                         "url": updates.INSTALL_URL}})
        said = panel.update_label.text()
        assert "no internet" in said and "pip package" in said
        assert panel.update_btn.text() == "Copy the command"
        assert panel.update_btn.toolTip() == "python -m pip install --upgrade mygeeky"
        assert panel.whats_new_btn.text() == "How to update"
        panel.update_btn.click()                    # the one thing that always works: give them it
        from PySide6.QtWidgets import QApplication as _QApp
        assert _QApp.clipboard().text() == "python -m pip install --upgrade mygeeky"

        # Already up to date is a success with nothing to restart for, and no button left to press
        panel._on_update_done({"ok": True, "message": "myGeeKy 9.9.9 is already the latest."})
        assert "already the latest" in panel.update_label.text()
        assert panel.update_btn.isHidden()
    finally:
        panel.ticker.stop()
        for t in (panel._activity_timer, panel._signals_timer, panel._update_timer):
            t.stop()
        for w in list(panel._workers):
            w.wait(2000)
        panel.close()
        panel.deleteLater()


def test_a_uv_tool_install_updates_with_uv_tool_upgrade(monkeypatch, tmp_path):
    from mygeeky.gui import bootstrap
    monkeypatch.setattr(updates.sys, "prefix", str(tmp_path))
    (tmp_path / "uv-receipt.toml").write_text("[tool]\n")
    monkeypatch.setattr(bootstrap, "find_uv", lambda: "/usr/local/bin/uv")
    assert updates.upgrade_command() == ["/usr/local/bin/uv", "tool", "upgrade", "mygeeky"]
    (tmp_path / "uv-receipt.toml").unlink()                     # a plain `uv venv`, no pip in it
    monkeypatch.setattr(bootstrap, "_has_pip", lambda: False)
    assert updates.upgrade_command()[:4] == ["/usr/local/bin/uv", "pip", "install", "--python"]
    monkeypatch.setattr(bootstrap, "_has_pip", lambda: True)    # a normal Python keeps using pip
    assert updates.upgrade_command()[1:4] == ["-m", "pip", "install"]


# --------------------------------------------------------------------------- when it cannot be done
def test_every_kind_of_install_has_a_way_to_update_by_hand(monkeypatch):
    """"Couldn't update" must never be the last word: each install has its own way forward."""
    monkeypatch.setattr(updates, "is_editable", lambda: True)
    steps = updates.manual_steps()
    assert steps["how"] == "git pull" and steps["command"] == "git pull"
    assert "developer install" in steps["what"]

    monkeypatch.setattr(updates, "is_editable", lambda: False)
    monkeypatch.setattr(updates, "is_uv_tool", lambda: True)
    steps = updates.manual_steps()
    assert steps["command"] == "uv tool upgrade mygeeky" and steps["url"]

    monkeypatch.setattr(updates, "is_uv_tool", lambda: False)
    steps = updates.manual_steps()
    assert "-m pip install --upgrade mygeeky" in steps["command"], steps["command"]
    assert steps["url"] and steps["how"] == "pip"


def test_the_failures_people_actually_hit_are_said_in_plain_words():
    cases = [
        ("Could not fetch URL https://pypi.org/simple/mygeeky/: Max retries exceeded", "internet"),
        ("ERROR: Could not install packages due to an OSError: [WinError 5] Access is denied", "administrator"),
        ("/usr/bin/python3: No module named pip", "no pip"),
        ("OSError: [Errno 28] No space left on device", "disk space"),
        ("ERROR: No matching distribution found for mygeeky", "did not offer"),
    ]
    for output, expected in cases:
        said = updates.explain_failure(output)
        assert expected in said, f"{output!r} -> {said!r}"
    assert updates.explain_failure("something nobody has seen before") == ""
    assert updates.explain_failure("") == ""


def test_a_pip_failure_is_explained_rather_than_pasted(monkeypatch):
    _an_update_is_waiting(monkeypatch)
    monkeypatch.setattr(updates, "is_editable", lambda: False)

    class Refused:
        returncode = 1
        stdout = ""
        stderr = "ERROR: Could not install packages due to an OSError: [WinError 5] Access is denied"
    monkeypatch.setattr(updates.subprocess, "run", lambda *a, **k: Refused())
    ok, message = updates.run_upgrade()
    assert not ok
    assert "administrator" in message
    assert "WinError" not in message, "pip's own words were pasted instead of being explained"


def test_an_unrecognised_pip_failure_still_shows_what_pip_said(monkeypatch):
    _an_update_is_waiting(monkeypatch)
    monkeypatch.setattr(updates, "is_editable", lambda: False)

    class Odd:
        returncode = 1
        stdout = ""
        stderr = "ERROR: something nobody has seen before\nand a second line\nand a third"
    monkeypatch.setattr(updates.subprocess, "run", lambda *a, **k: Odd())
    ok, message = updates.run_upgrade()
    assert not ok and "something nobody has seen before" in message


def test_the_panel_is_given_the_manual_steps_with_every_result(monkeypatch):
    """So the panel can offer a button instead of only "Try again"."""
    from mygeeky.gui import app as gui_app
    monkeypatch.setattr(updates, "check", lambda *a, **k: {
        "current": updates.__version__, "latest": "99.0.0", "newer": True, "checked_at": None})
    monkeypatch.setattr(updates, "is_editable", lambda: True)
    result = gui_app.install_update()
    assert not result["ok"] and result["editable"] is True
    assert result["steps"]["command"] == "git pull"
    assert result["current"] == updates.__version__
