"""Helpers to run `mygeeky pipeline` (learn + run) automatically once a week.

myGeeKy never registers a scheduled task by itself. `mygeeky schedule show`
always just prints the exact command for your platform; `mygeeky schedule
install` only registers it if you pass `--yes`, since creating a recurring
OS-level task is the kind of change that should be an explicit, visible
choice you make, not something a library does quietly on your behalf.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

from . import winproc

TASK_NAME = "myGeeKyWeeklyRun"


def _python_and_module() -> tuple[str, str]:
    return sys.executable, "mygeeky.cli"


def windowless_python() -> str:
    """pythonw.exe next to this Python: the same Python, without a console window."""
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return str(w if exe.name.lower() == "python.exe" and w.exists() else exe)


def windows_command() -> str:
    return (
        f'schtasks /Create /SC WEEKLY /D MON /ST 09:00 /TN "{TASK_NAME}" '
        f'/TR "\\"{windowless_python()}\\" -m mygeeky pipeline" /F'
    )


def is_installed() -> bool:
    if platform.system() != "Windows":
        return False
    return winproc.run(f'schtasks /Query /TN "{TASK_NAME}"', shell=True, capture_output=True, text=True).returncode == 0


def make_windowless() -> bool:
    """Tasks made before 0.15.2 ran python.exe, which opens a console window every
    Monday; switch an existing one to pythonw (same schedule). True if changed."""
    if platform.system() != "Windows":
        return False
    q = winproc.run(f'schtasks /Query /TN "{TASK_NAME}" /V /FO LIST', shell=True, capture_output=True, text=True)
    if q.returncode != 0 or "pythonw.exe" in q.stdout.lower() or "python.exe" not in q.stdout.lower():
        return False
    return winproc.run(windows_command(), shell=True, capture_output=True, text=True).returncode == 0


CRON_MARK = "-m mygeeky pipeline"     # how our line is recognised, old formats included


def cron_line() -> str:
    """Paths quoted (a space in a folder name broke it), the log folder made first (a
    missing one made cron skip the run), and the session bus given, so the keyring
    holding the GitHub token can be reached from cron."""
    import os
    import shlex
    from .config import LOG_DIR
    python, _ = _python_and_module()
    env = ""
    if hasattr(os, "getuid") and Path(f"/run/user/{os.getuid()}/bus").exists():
        env = f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{os.getuid()}/bus "
    log = shlex.quote(str(LOG_DIR / "weekly.log"))
    return (f"0 9 * * 1 mkdir -p {shlex.quote(str(LOG_DIR))} && {env}{shlex.quote(python)} "
            f"{CRON_MARK} >> {log} 2>&1")


def catch_up_settings() -> bool:
    """Windows: a run missed while the PC was off or asleep starts as soon as it's back,
    and it runs on battery too (schtasks' defaults skip both). True if the task has them."""
    if platform.system() != "Windows":
        return False
    script = (f"$t = Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction Stop; "
              "if ($t.Settings.StartWhenAvailable -and -not $t.Settings.DisallowStartIfOnBatteries) { 'ok'; exit } "
              "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries; "
              f"Set-ScheduledTask -TaskName '{TASK_NAME}' -Settings $s | Out-Null; 'set'")
    try:
        r = winproc.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                        capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and r.stdout.strip() in ("ok", "set")


def describe() -> str:
    system = platform.system()
    if system == "Windows":
        return (
            "Windows Task Scheduler (runs every Monday at 09:00):\n\n"
            f"  {windows_command()}\n\n"
            "Run that in an elevated PowerShell/cmd yourself, or re-run this command with\n"
            "`mygeeky schedule install --yes` to have myGeeKy run it for you."
        )
    if system == "Darwin":
        return (
            "launchd (runs every Monday at 09:00, or as soon as the Mac wakes if it was asleep):\n\n"
            f"  a LaunchAgent at {launch_agent_path()}\n\n"
            "Re-run this command with `mygeeky schedule install --yes` to have myGeeKy create and load it."
        )
    return (
        "cron (runs every Monday at 09:00) -- add this line via `crontab -e`:\n\n"
        f"  {cron_line()}\n\n"
        "Or re-run this command with `mygeeky schedule install --yes` to have myGeeKy\n"
        "append it to your crontab for you."
    )


# --------------------------------------------------------------------------- macOS: launchd
LAUNCH_AGENT_ID = "org.mygeeky.weekly"


def launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_ID}.plist"


def launch_agent_plist() -> bytes:
    """cron is deprecated on macOS and needs Full Disk Access to touch some folders;
    launchd is the native way, and it runs a missed time when the Mac wakes up."""
    import plistlib
    from .config import LOG_DIR
    python, _ = _python_and_module()
    return plistlib.dumps({
        "Label": LAUNCH_AGENT_ID,
        "ProgramArguments": [python, "-m", "mygeeky", "pipeline"],
        "StartCalendarInterval": {"Weekday": 1, "Hour": 9, "Minute": 0},      # Monday 09:00
        "StandardOutPath": str(LOG_DIR / "weekly.log"),
        "StandardErrorPath": str(LOG_DIR / "weekly.log"),
        "ProcessType": "Background",
        "LowPriorityIO": True,
    })


def _launchctl(*args: str) -> subprocess.CompletedProcess:
    return winproc.run(["launchctl", *args], capture_output=True, text=True)


def _remove_cron_line() -> bool:
    """An older myGeeKy put a cron line on Macs too: take it out (True if there was one)."""
    result = subprocess.run("crontab -l", shell=True, capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""
    if CRON_MARK not in existing:
        return False
    new_crontab = "\n".join(l for l in existing.splitlines() if CRON_MARK not in l) + "\n"
    return subprocess.run("crontab -", shell=True, input=new_crontab, capture_output=True, text=True).returncode == 0


def install_mac() -> str:
    import os
    from .config import LOG_DIR
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = launch_agent_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    domain = f"gui/{os.getuid()}"
    _launchctl("bootout", domain, str(path))             # reload a changed one
    path.write_bytes(launch_agent_plist())
    loaded = _launchctl("bootstrap", domain, str(path))
    if loaded.returncode != 0:                           # older macOS, or no GUI session
        loaded = _launchctl("load", "-w", str(path))
    note = " (also removed the old cron line)" if _remove_cron_line() else ""
    if loaded.returncode != 0:
        return (f"Wrote {path}, but launchd didn't load it yet ({(loaded.stderr or loaded.stdout).strip()}). "
                f"It loads at your next login{note}.")
    return (f"Added a launchd agent ({path}). myGeeKy will run `mygeeky pipeline` every Monday at 09:00, "
            f"or as soon as your Mac wakes if it was asleep then{note}.")


def remove_mac() -> str:
    import os
    path = launch_agent_path()
    had_cron = _remove_cron_line()
    if not path.exists():
        return "Removed myGeeKy's old cron entry." if had_cron else "No weekly run was set up -- nothing to do."
    _launchctl("bootout", f"gui/{os.getuid()}", str(path))
    path.unlink()
    return "Removed myGeeKy's weekly run (launchd agent)."


def install(confirmed: bool) -> str:
    if not confirmed:
        return describe() + "\n\n(Nothing was installed -- pass --yes to actually install it.)"

    system = platform.system()
    if system == "Darwin":
        return install_mac()
    if system == "Windows":
        cmd = windows_command()
        result = winproc.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            return f"Failed to create scheduled task:\n{result.stderr or result.stdout}"
        catch_up_settings()
        return (f"Scheduled task '{TASK_NAME}' created. It will run `mygeeky pipeline` every Monday at 09:00 "
                "(or as soon as the computer is on, if it was off then).")

    line = cron_line()
    result = subprocess.run("crontab -l", shell=True, capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""
    if line in existing.splitlines():
        return "That cron entry already exists -- nothing to do."
    kept = [l for l in existing.splitlines() if CRON_MARK not in l]     # an older myGeeKy line is replaced
    new_crontab = "\n".join(kept).rstrip("\n") + f"\n{line}\n"
    proc = subprocess.run("crontab -", shell=True, input=new_crontab, capture_output=True, text=True)
    if proc.returncode != 0:
        return f"Failed to update crontab:\n{proc.stderr}"
    return f"Added to your crontab. myGeeKy will run `mygeeky pipeline` every Monday at 09:00.\n  {line}"


def remove() -> str:
    system = platform.system()
    if system == "Windows":
        result = winproc.run(f'schtasks /Delete /TN "{TASK_NAME}" /F', shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            return f"Could not remove scheduled task (maybe it wasn't installed):\n{result.stderr or result.stdout}"
        return f"Scheduled task '{TASK_NAME}' removed."
    if system == "Darwin":
        return remove_mac()

    result = subprocess.run("crontab -l", shell=True, capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""
    if CRON_MARK not in existing:
        return "No matching cron entry found -- nothing to do."
    new_crontab = "\n".join(l for l in existing.splitlines() if CRON_MARK not in l) + "\n"
    proc = subprocess.run("crontab -", shell=True, input=new_crontab, capture_output=True, text=True)
    if proc.returncode != 0:
        return f"Failed to update crontab:\n{proc.stderr}"
    return "Removed myGeeKy's cron entry."
