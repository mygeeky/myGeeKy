"""Desktop integration: run the panel in the background, and give it a place in
the applications menu (with its icon), optionally at sign-in too.

* Linux: a .desktop entry in the applications menu, icons in the hicolor theme,
  and an autostart .desktop file for sign-in.
* macOS: a small ~/Applications/myGeeKy.app bundle (so it's in Launchpad,
  Spotlight and the Dock with its name and icon), and a LaunchAgent that opens
  it at login.

Everything here is per-user (~/.local/share, ~/.config, ~/Applications,
~/Library/LaunchAgents) -- no sudo, nothing system-wide -- and `mygeeky desktop
remove` takes it all back. Windows gets its Start-menu entry from the installer.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import struct
import subprocess
import sys
from pathlib import Path

APP_ID = "mygeeky"            # also the Qt desktop file name, so the dock shows the right icon
APP_NAME = "myGeeKy"
BUNDLE_ID = "org.mygeeky.panel"
LOGIN_AGENT_ID = "org.mygeeky.panel.login"
ASSETS = Path(__file__).parent / "assets"
ICON_SIZES = (64, 128, 256)
LSREGISTER = ("/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework"
              "/Support/lsregister")


def is_mac() -> bool:
    return sys.platform == "darwin"


def _xdg(var: str, default: str) -> Path:
    return Path(os.environ.get(var) or Path.home() / default)


def entry_path() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share") / "applications" / f"{APP_ID}.desktop"


def autostart_path() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / "autostart" / f"{APP_ID}.desktop"


def _icon_dir(size: int) -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share") / "icons" / "hicolor" / f"{size}x{size}" / "apps"


def launch_command() -> list[str]:
    """How to start the panel without a console window."""
    exe = Path(sys.executable)
    if sys.platform == "win32":
        pythonw = exe.with_name("pythonw.exe")
        if pythonw.exists():
            exe = pythonw
    return [str(exe), "-m", "mygeeky.gui.app"]


def desktop_entry(autostart: bool = False) -> str:
    exec_line = " ".join(f'"{a}"' if " " in a else a for a in launch_command())
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        "Name=myGeeKy",
        "GenericName=Research network panel",
        "Comment=Find friends, collaborate, away from noise",
        f"Exec={exec_line}",
        f"Icon={APP_ID}",
        "Terminal=false",
        "Categories=Network;Science;Education;",
        "Keywords=github;research;science;network;papers;",
        f"StartupWMClass={APP_ID}",
    ]
    if autostart:
        lines += ["X-GNOME-Autostart-enabled=true", "X-GNOME-Autostart-Delay=10"]
    return "\n".join(lines) + "\n"


def _refresh_menus() -> None:
    """Ask the desktop to notice the new entry (optional tools; fine if missing)."""
    for cmd in (["update-desktop-database", str(entry_path().parent)],
                ["gtk-update-icon-cache", "-q", "-t", str(_icon_dir(64).parents[1])]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, capture_output=True, check=False)


def install_menu_entry(autostart: bool | None = None) -> list[str]:
    """Add (or update) the applications-menu entry and icons. Returns what changed."""
    if is_mac():
        return install_mac_app(autostart=autostart)
    if not sys.platform.startswith("linux"):
        return []
    changed = []
    for size in ICON_SIZES:
        src = ASSETS / f"icon_{size}.png"
        if src.exists():
            dst = _icon_dir(size) / f"{APP_ID}.png"
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists() or dst.read_bytes() != src.read_bytes():
                shutil.copyfile(src, dst)
    entry = desktop_entry()
    path = entry_path()
    if not path.exists() or path.read_text(encoding="utf-8") != entry:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry, encoding="utf-8")
        path.chmod(0o755)
        changed.append(f"Added myGeeKy to your applications menu ({path}).")
    if autostart is not None:
        auto = autostart_path()
        if autostart:
            auto.parent.mkdir(parents=True, exist_ok=True)
            auto.write_text(desktop_entry(autostart=True), encoding="utf-8")
            changed.append("myGeeKy will open when you sign in.")
        elif auto.exists():
            auto.unlink()
            changed.append("myGeeKy won't open at sign-in any more.")
    elif autostart_path().exists():          # keep the sign-in entry pointing at this Python too
        autostart_path().write_text(desktop_entry(autostart=True), encoding="utf-8")
    if changed:
        _refresh_menus()
    return changed


def remove_menu_entry() -> list[str]:
    if is_mac():
        return remove_mac_app()
    removed = []
    for p in [entry_path(), autostart_path()] + [_icon_dir(s) / f"{APP_ID}.png" for s in ICON_SIZES]:
        if p.exists():
            p.unlink()
            removed.append(str(p))
    if removed:
        _refresh_menus()
    return removed


# --------------------------------------------------------------------------- macOS
def app_bundle_path() -> Path:
    return Path.home() / "Applications" / f"{APP_NAME}.app"


def login_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LOGIN_AGENT_ID}.plist"


# an .icns file is a list of PNGs, each tagged with the size macOS uses it for
ICNS_ENTRIES = (("ic11", 32), ("ic12", 64), ("ic07", 128), ("ic13", 256), ("ic08", 256),
                ("ic14", 512), ("ic09", 512))


def make_icns() -> bytes:
    """The app icon as .icns, built from the PNG icons we already ship (no iconutil
    needed, so it's the same on every machine)."""
    pngs = {32: "icon_32.png", 64: "icon_64.png", 128: "icon_128.png", 256: "icon_256.png", 512: "icon.png"}
    chunks = b""
    for tag, size in ICNS_ENTRIES:
        data = (ASSETS / pngs[size]).read_bytes()
        chunks += tag.encode("ascii") + struct.pack(">I", 8 + len(data)) + data
    return b"icns" + struct.pack(">I", 8 + len(chunks)) + chunks


def info_plist() -> bytes:
    from .. import __version__
    return plistlib.dumps({
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleExecutable": APP_NAME,
        "CFBundleIconFile": APP_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
        "CFBundleInfoDictionaryVersion": "6.0",
        "LSMinimumSystemVersion": "11.0",
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "MIT License",
    })


def launcher_script() -> str:
    """The bundle's executable: runs myGeeKy's own Python. `exec` keeps the process
    the app's, so the Dock and the menu bar treat it as myGeeKy."""
    python, module = launch_command()[0], launch_command()[2]
    return ("#!/bin/sh\n"
            f"# myGeeKy's launcher (written by `mygeeky desktop install`; it runs {python})\n"
            "cd \"$HOME\" || exit 1\n"
            f"exec \"{python}\" -m {module} \"$@\"\n")


def build_app_bundle(app: Path) -> None:
    """Write the bundle at `app` (any platform: tests build it in a temp folder)."""
    contents = app / "Contents"
    (contents / "MacOS").mkdir(parents=True, exist_ok=True)
    (contents / "Resources").mkdir(parents=True, exist_ok=True)
    (contents / "Info.plist").write_bytes(info_plist())
    (contents / "PkgInfo").write_text("APPL????", encoding="ascii")
    exe = contents / "MacOS" / APP_NAME
    exe.write_text(launcher_script(), encoding="utf-8")
    exe.chmod(0o755)
    (contents / "Resources" / f"{APP_NAME}.icns").write_bytes(make_icns())


def login_agent_plist() -> bytes:
    """Open myGeeKy at login, through the app (so it starts as myGeeKy, with its icon)."""
    args = (["/usr/bin/open", "-a", str(app_bundle_path())] if app_bundle_path().exists()
            else launch_command())
    return plistlib.dumps({
        "Label": LOGIN_AGENT_ID,
        "ProgramArguments": args,
        "RunAtLoad": True,
        "LimitLoadToSessionType": "Aqua",       # only in a real login with a screen, never over SSH
        "ProcessType": "Interactive",
    })


def _quiet(cmd: list[str]) -> None:
    if Path(cmd[0]).exists() or shutil.which(cmd[0]):
        subprocess.run(cmd, capture_output=True, check=False)


def install_mac_app(autostart: bool | None = None) -> list[str]:
    changed = []
    app = app_bundle_path()
    before = (app / "Contents" / "MacOS" / APP_NAME).read_text(encoding="utf-8") if app.exists() else None
    build_app_bundle(app)            # always rewritten: cheap, and keeps the version and the Python current
    _quiet([LSREGISTER, "-f", str(app)])      # Launchpad and Spotlight notice it now, not at the next login
    if before != launcher_script():
        changed.append(f"Added myGeeKy to your Applications ({app}): find it in Launchpad or Spotlight.")
    agent = login_agent_path()
    if autostart:
        agent.parent.mkdir(parents=True, exist_ok=True)
        agent.write_bytes(login_agent_plist())
        changed.append("myGeeKy will open when you log in.")
    elif autostart is False and agent.exists():
        _quiet(["launchctl", "bootout", f"gui/{os.getuid()}", str(agent)])
        agent.unlink()
        changed.append("myGeeKy won't open at login any more.")
    elif autostart is None and agent.exists():   # keep it pointing at this install
        agent.write_bytes(login_agent_plist())
    return changed


def remove_mac_app() -> list[str]:
    removed = []
    agent = login_agent_path()
    if agent.exists():
        _quiet(["launchctl", "bootout", f"gui/{os.getuid()}", str(agent)])
        agent.unlink()
        removed.append(str(agent))
    app = app_bundle_path()
    if app.exists():
        _quiet([LSREGISTER, "-u", str(app)])
        shutil.rmtree(app, ignore_errors=True)
        removed.append(str(app))
    return removed


def autostart_enabled() -> bool:
    return (login_agent_path() if is_mac() else autostart_path()).exists()


def disable_autostart() -> None:
    if is_mac():
        install_mac_app(autostart=False)
    elif autostart_path().exists():
        autostart_path().unlink()


def launch_detached(log_file: Path) -> subprocess.Popen:
    """Start the panel as its own process, free of this terminal: closing the
    terminal (or Ctrl+C) doesn't close myGeeKy. Its output goes to `log_file`."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    if is_mac() and app_bundle_path().exists():
        # through the app, so macOS starts it as myGeeKy (Dock, menu bar), not as "Python"
        return subprocess.Popen(["/usr/bin/open", "-a", str(app_bundle_path()),
                                 "--stdout", str(log_file), "--stderr", str(log_file)],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = open(log_file, "ab")
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": out, "stderr": out, "close_fds": True,
                    "cwd": str(Path.home())}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000   # DETACHED | NEW_GROUP | NO_WINDOW
    else:
        kwargs["start_new_session"] = True                             # survives the terminal closing
    return subprocess.Popen(launch_command(), **kwargs)
