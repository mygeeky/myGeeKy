"""Noticing new myGeeKy releases, and updating in place.

The check is one read-only request to PyPI's public JSON API, at most once a
day (cached in UPDATE_CHECK_FILE), sending nothing about you. Updating is a
`pip install --upgrade mygeeky` for the very Python myGeeKy runs on (`uv tool
upgrade mygeeky` for one installed with uv). A
developer (editable) install is never touched -- that's `git pull`.

Turn it off with `mygeeky config set check_for_updates false`.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from . import winproc
from . import __version__
from .config import UPDATE_CHECK_FILE, ensure_dirs
from .files import write_json

PYPI_URL = "https://pypi.org/pypi/mygeeky/json"
RELEASES_URL = "https://github.com/mygeeky/myGeeKy/releases/latest"


def parse_version(v: str) -> tuple[int, ...]:
    """'0.4.10' -> (0, 4, 10). Anything after the numbers (rc1, .dev0) is ignored;
    PyPI's 'latest' is always a final release."""
    nums = re.findall(r"\d+", (v or "").split("+")[0])[:3]
    return tuple(int(n) for n in nums) + (0,) * (3 - len(nums))


def is_newer(latest: str | None, current: str = __version__) -> bool:
    return bool(latest) and parse_version(latest) > parse_version(current)


def latest_version(timeout: float = 4.0) -> str | None:
    try:
        r = requests.get(PYPI_URL, timeout=timeout, headers={"User-Agent": f"mygeeky/{__version__}"})
        if r.status_code != 200:
            return None
        v = (r.json().get("info") or {}).get("version")
        return v if isinstance(v, str) and re.fullmatch(r"\d+(\.\d+){0,3}", v) else None
    except (requests.RequestException, ValueError):
        return None


def _load_cache() -> dict[str, Any]:
    try:
        return json.loads(UPDATE_CHECK_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def check(force: bool = False, max_age_hours: float = 24.0, timeout: float = 4.0) -> dict[str, Any]:
    """{"current", "latest", "newer", "checked_at"} -- from the cache when it's
    fresh, otherwise from PyPI (a failed request keeps the old answer)."""
    cache = _load_cache()
    try:
        fresh = (datetime.now(timezone.utc) - datetime.fromisoformat(cache["checked_at"])
                 < timedelta(hours=max_age_hours))
    except (KeyError, ValueError, TypeError):
        fresh = False
    if force or not fresh:
        latest = latest_version(timeout)
        if latest:
            cache = {"latest": latest, "checked_at": datetime.now(timezone.utc).isoformat()}
            try:
                ensure_dirs()
                write_json(UPDATE_CHECK_FILE, cache)
            except OSError:
                pass
    latest = cache.get("latest")
    return {"current": __version__, "latest": latest, "newer": is_newer(latest),
            "checked_at": cache.get("checked_at")}


def is_editable() -> bool:
    """True for a developer install (`pip install -e .`), which pip must not replace."""
    try:
        from importlib.metadata import distribution
        info = json.loads(distribution("mygeeky").read_text("direct_url.json") or "{}")
        return bool((info.get("dir_info") or {}).get("editable"))
    except Exception:
        return False


def is_uv_tool() -> bool:
    """Installed with `uv tool install` (uv leaves a receipt in the tool's environment)."""
    return (Path(sys.prefix) / "uv-receipt.toml").exists()


def upgrade_command() -> list[str]:
    from .gui.bootstrap import _has_pip, find_uv
    uv = find_uv()
    if uv and is_uv_tool():
        return [uv, "tool", "upgrade", "mygeeky"]        # keeps what it was installed --with (Qt)
    if uv and not _has_pip():                          # a `uv venv`: no pip in it
        return [uv, "pip", "install", "--python", sys.executable, "--upgrade", "mygeeky"]
    return [sys.executable, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check", "mygeeky"]


INSTALL_URL = "https://mygeeky.org/#get"


def manual_steps() -> dict[str, str]:
    """How *this* install is updated by hand, for when the button cannot do it.

    An update that fails has to end somewhere other than "Couldn't update". Whatever went wrong --
    no network, a Python that needs administrator rights to write to, a pip that isn't there -- the
    person still has a way forward, and it is not the same way for every install, so it is worked out
    from the install rather than written into the message."""
    if is_editable():
        return {"how": "git pull",
                "what": "This copy is a developer install, which pip must never overwrite.",
                "command": "git pull",
                "url": ""}
    if is_uv_tool():
        return {"how": "uv",
                "what": "myGeeKy was installed with uv.",
                "command": "uv tool upgrade mygeeky",
                "url": INSTALL_URL}
    return {"how": "pip",
            "what": "myGeeKy is a pip package for the Python it runs on.",
            "command": f'"{sys.executable}" -m pip install --upgrade mygeeky',
            "url": INSTALL_URL}


def explain_failure(output: str) -> str:
    """Say what pip's failure means, in words that suggest what to do about it.

    pip's last three lines are written for people who already know pip. These are the failures that
    actually happen on other people's computers, and each one has a different answer."""
    said = (output or "").lower()
    if any(w in said for w in ("temporary failure in name resolution", "max retries", "read timed out",
                               "connection refused", "network is unreachable", "failed to establish",
                               "proxyerror", "sslerror", "certificate verify failed")):
        return ("Couldn't reach PyPI to download the update. Check your internet connection -- and if "
                "you are on a work network, it may be blocking pypi.org.")
    if any(w in said for w in ("permission denied", "access is denied", "winerror 5", "errno 13",
                               "consider using the `--user` option", "could not install packages due to"
                               " an environmentror")):
        return ("This Python needs administrator rights to change, so pip was not allowed to write the "
                "update.")
    if "no module named pip" in said or "no such file or directory: 'pip'" in said:
        return "The Python myGeeKy runs on has no pip, so it cannot update itself."
    if "no space left" in said or "not enough space" in said:
        return "There is not enough free disk space to download and unpack the update."
    if "no matching distribution" in said or "could not find a version" in said:
        return "PyPI did not offer a version this Python can install."
    return ""


def run_upgrade() -> tuple[bool, str]:
    """Upgrade in place. (ok, message) -- never raises."""
    # "Nothing to do" comes first, and is not a failure: a banner can sit on screen for hours, and by
    # the time it is clicked this copy may already have been updated some other way (a `git pull`, a
    # pip run in a terminal, another computer's sync). Telling someone their update failed when they
    # already have the new version is the worst of the three answers.
    if not check().get("newer"):
        return True, f"myGeeKy {__version__} is already the latest."
    if is_editable():
        return False, ("This is a developer install (pip install -e). Update it with `git pull` in your "
                       "myGeeKy folder instead.")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = winproc.run(upgrade_command(), capture_output=True, text=True, timeout=900,
                           creationflags=flags, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return False, ("The update took too long and was stopped, so nothing was changed. This is "
                       "usually a very slow connection.")
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Couldn't run the updater: {exc}"
    if r.returncode != 0:
        output = (r.stderr or "") + "\n" + (r.stdout or "")
        why = explain_failure(output)
        tail = "\n".join(output.strip().splitlines()[-3:])
        return False, (why or "Couldn't update myGeeKy:\n" + tail)
    installed = installed_version()
    return True, f"Updated to myGeeKy {installed}." if installed else "Updated."


def installed_version() -> str | None:
    """The version pip has on disk now (this process still runs the old one)."""
    try:
        r = winproc.run([sys.executable, "-c", "import mygeeky; print(mygeeky.__version__)"],
                           capture_output=True, text=True, timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def relaunch_panel_after_exit(delay: float = 2.0) -> None:
    """Start a fresh panel a moment after this one quits (the single-panel lock
    is released on exit), so it runs the newly installed code."""
    pythonw = sys.executable
    if pythonw.lower().endswith("python.exe"):
        candidate = pythonw[:-len("python.exe")] + "pythonw.exe"
        import os
        if os.path.exists(candidate):
            pythonw = candidate
    code = (f"import time, subprocess; time.sleep({delay}); "
            f"subprocess.Popen([{pythonw!r}, '-m', 'mygeeky.gui.app'])")
    subprocess.Popen([pythonw, "-c", code], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                     | getattr(subprocess, "DETACHED_PROCESS", 0), close_fds=True)
