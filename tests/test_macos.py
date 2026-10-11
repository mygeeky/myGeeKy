"""macOS: the app bundle, opening at login, the weekly launchd agent, and small touches.
Most of it is files and plists, so it's checked on every OS; what needs a real
Mac is marked and runs in the macOS CI job."""

import plistlib
import struct
import sys

import pytest

from mygeeky import auth, scheduler
from mygeeky.gui import desktop, macos

mac_only = pytest.mark.skipif(sys.platform != "darwin", reason="needs macOS")


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(desktop, "is_mac", lambda: True)
    monkeypatch.setattr(desktop, "_quiet", lambda cmd: None)          # no lsregister / launchctl here
    monkeypatch.setattr(desktop.os, "getuid", lambda: 501, raising=False)
    return tmp_path


def _png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def test_the_icon_is_a_real_icns_with_every_size():
    data = desktop.make_icns()
    assert data[:4] == b"icns" and struct.unpack(">I", data[4:8])[0] == len(data)
    sizes, pos = {}, 8
    while pos < len(data):
        tag, length = data[pos:pos + 4].decode(), struct.unpack(">I", data[pos + 4:pos + 8])[0]
        sizes[tag] = _png_size(data[pos + 8:pos + length])
        pos += length
    assert pos == len(data)
    # each tag holds exactly the size macOS expects for it
    assert sizes == {t: (s, s) for t, s in desktop.ICNS_ENTRIES}


def test_the_app_bundle_has_the_name_icon_and_launcher(home):
    app = desktop.app_bundle_path()
    assert app == home / "Applications" / "myGeeKy.app"
    desktop.build_app_bundle(app)
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundleName"] == info["CFBundleDisplayName"] == "myGeeKy"
    assert info["CFBundleExecutable"] == "myGeeKy" and info["CFBundleIconFile"] == "myGeeKy"
    assert info["CFBundlePackageType"] == "APPL" and info["CFBundleIdentifier"] == "org.mygeeky.panel"
    launcher = (app / "Contents" / "MacOS" / "myGeeKy").read_text(encoding="utf-8")
    assert launcher.startswith("#!/bin/sh\n") and f'exec "{desktop.launch_command()[0]}" -m mygeeky.gui.app' in launcher
    assert (app / "Contents" / "Resources" / "myGeeKy.icns").read_bytes()[:4] == b"icns"
    if sys.platform != "win32":
        assert (app / "Contents" / "MacOS" / "myGeeKy").stat().st_mode & 0o111      # executable


def test_install_adds_the_app_and_login_through_it_and_remove_takes_both_back(home):
    notes = desktop.install_menu_entry(autostart=True)
    assert desktop.app_bundle_path().exists() and any("Launchpad" in n for n in notes)
    agent = plistlib.loads(desktop.login_agent_path().read_bytes())
    assert agent["Label"] == "org.mygeeky.panel.login" and agent["RunAtLoad"] is True
    assert agent["ProgramArguments"] == ["/usr/bin/open", "-a", str(desktop.app_bundle_path())]
    assert desktop.autostart_enabled()
    assert desktop.install_menu_entry() == []                        # nothing changed: nothing said
    desktop.disable_autostart()
    assert not desktop.login_agent_path().exists() and desktop.app_bundle_path().exists()
    removed = desktop.remove_menu_entry()
    assert str(desktop.app_bundle_path()) in removed and not desktop.app_bundle_path().exists()


def test_the_weekly_run_on_a_mac_is_a_launchd_agent_not_cron(monkeypatch, tmp_path):
    monkeypatch.setattr(scheduler.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(scheduler.platform, "system", lambda: "Darwin")
    monkeypatch.setattr("os.getuid", lambda: 501, raising=False)          # not on Windows
    calls = []

    class Ok:
        returncode, stdout, stderr = 0, "", ""
    monkeypatch.setattr(scheduler, "_launchctl", lambda *a: calls.append(a) or Ok())
    monkeypatch.setattr(scheduler, "_remove_cron_line", lambda: True)          # an older myGeeKy left one
    msg = scheduler.install(confirmed=True)
    agent = plistlib.loads(scheduler.launch_agent_path().read_bytes())
    assert agent["StartCalendarInterval"] == {"Weekday": 1, "Hour": 9, "Minute": 0}
    assert agent["ProgramArguments"][1:] == ["-m", "mygeeky", "pipeline"]
    assert agent["StandardOutPath"].endswith("weekly.log")
    assert any(c[0] == "bootstrap" for c in calls) and "launchd" in msg and "old cron line" in msg
    assert "launchd" in scheduler.describe()
    assert "Removed" in scheduler.remove() and not scheduler.launch_agent_path().exists()


def test_a_mac_terminal_is_told_to_paste_with_command_v(monkeypatch):
    monkeypatch.setattr(auth.sys, "platform", "darwin")
    assert auth.paste_hint().startswith("⌘V")
    monkeypatch.setattr(auth.sys, "platform", "linux")
    assert "Ctrl+Shift+V" in auth.paste_hint()


def test_the_name_fix_does_nothing_off_a_mac():
    if sys.platform != "darwin":
        assert macos.set_app_name() is False and macos.bundle_name() is None


def test_uninstalling_a_uv_tool_uses_uv(monkeypatch, tmp_path):
    from mygeeky.gui import bootstrap, setup_wizard
    (tmp_path / "bin").mkdir()
    (tmp_path / "uv-receipt.toml").write_text("[tool]\n")
    monkeypatch.setattr(bootstrap, "find_uv", lambda: "/opt/homebrew/bin/uv")
    assert setup_wizard.uninstall_command(str(tmp_path / "bin" / "python")) == \
        ["/opt/homebrew/bin/uv", "tool", "uninstall", "mygeeky"]


# --------------------------------------------------------------- on a real Mac (CI: macos-latest)
@mac_only
def test_on_a_mac_the_menu_bar_name_becomes_mygeeky():
    assert macos.set_app_name() is True
    assert macos.bundle_name() == "myGeeKy"


@mac_only
def test_on_a_mac_the_bundle_passes_apples_own_checks(tmp_path, monkeypatch):
    import subprocess
    app = tmp_path / "myGeeKy.app"
    desktop.build_app_bundle(app)
    assert subprocess.run(["plutil", "-lint", str(app / "Contents" / "Info.plist")]).returncode == 0
    out = tmp_path / "check.iconset"
    assert subprocess.run(["iconutil", "-c", "iconset", str(app / "Contents" / "Resources" / "myGeeKy.icns"),
                           "-o", str(out)]).returncode == 0
    assert len(list(out.glob("*.png"))) >= 5


def test_on_a_mac_the_panel_starts_through_the_app(home, monkeypatch):
    desktop.build_app_bundle(desktop.app_bundle_path())
    seen = {}
    monkeypatch.setattr(desktop.subprocess, "Popen", lambda cmd, **kw: seen.update(cmd=cmd, **kw))
    desktop.launch_detached(home / "logs" / "panel.log")
    assert seen["cmd"][:3] == ["/usr/bin/open", "-a", str(desktop.app_bundle_path())]
    assert "--stdout" in seen["cmd"] and "--stderr" in seen["cmd"]
