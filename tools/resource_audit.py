"""myGeeKy's resource audit: what the program takes from the computer, and whether it keeps taking more.

    python tools/resource_audit.py storage          # your real folders, read-only: data, caches, the synced repo, beacon
    python tools/resource_audit.py leak [rounds]    # every page, round after round: memory and Qt objects must level off
    python tools/resource_audit.py idle [seconds]   # CPU while nothing happens, shown and hidden, and the live timers
    python tools/resource_audit.py startup          # time and RAM to open the panel
    python tools/resource_audit.py all --json       # everything (CI: .github/workflows/resources.yml)

leak / idle / startup run in a throwaway profile (temporary data and settings folders, network blocked), so they never
touch your data. Each check compares against BUDGETS and says PASS / WARN / FAIL. The protocol, the budgets and how to
read the numbers: docs/RESOURCES.md and the `mygeeky-resources` skill. The phone has its own steps (adb), in the skill.
"""

from __future__ import annotations

import gc
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

# What "efficient" means here, in numbers. A WARN is worth a look; a FAIL is a bug.
BUDGETS = {
    "data_working_mb": 40,        # files in the synced data folder (your history, settings, CV text)
    "data_git_mb": 300,           # its git history, packed
    "data_loose_mb": 200,         # unpacked copies git hasn't packed yet (sync packs past this)
    "local_mb": 120,              # live databases beside it (GitHub cache, WISEP)
    "avatar_mb": 30,
    "logs_mb": 20,
    "syncs_per_day": 60,          # each sync is a commit in your history and a push
    "beacon_kb": 64,              # your public beacon.json
    "leak_kb_per_round": 512,     # Python memory still growing after the first rounds
    "leak_widgets_per_round": 2,  # Qt widgets still growing after the first rounds
    "idle_cpu_pct": 2.0,          # shown, nothing happening
    "hidden_cpu_pct": 0.5,        # hidden: animations must stop
    "startup_s": 8.0,
    "rss_mb": 450,                # the panel's RAM after visiting every page
}


def _verdict(value: float, budget: float, warn_at: float = 0.8) -> str:
    return "FAIL" if value > budget else "WARN" if value > budget * warn_at else "PASS"


def _du(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += (Path(root) / f).stat().st_size
            except OSError:
                pass
    return total


def _rss_mb() -> float:
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1e6
    except Exception:
        pass
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1e3
    except OSError:
        pass
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / 1e6 if sys.platform == "darwin" else peak / 1e3     # bytes on macOS, KB elsewhere (a peak)


# --------------------------------------------------------------------------- storage (read-only, your real folders)
def storage() -> dict:
    from mygeeky import config
    data, local = Path(config.DATA_DIR), Path(getattr(config, "LOCAL_DIR", config.DATA_DIR))
    git = data / ".git"
    out: dict = {"paths": {"data": str(data), "local": str(local), "config": str(config.CONFIG_DIR)}}
    working = _du(data) - _du(git)
    out["data_working_mb"] = round(working / 1e6, 2)
    out["local_mb"] = round(_du(local) / 1e6, 2) if local != data else 0.0
    out["avatar_mb"] = round(_du(Path(config.AVATAR_CACHE_DIR)) / 1e6, 2)
    out["logs_mb"] = round(_du(Path(config.LOG_DIR)) / 1e6, 2)
    out["config_kb"] = round(_du(Path(config.CONFIG_DIR)) / 1e3, 1)
    stray = sorted({p.name for p in data.glob("*.sqlite*")} | {p.name for p in data.glob("*.broken-*")})
    out["stray_in_data"] = stray                       # databases or damaged copies inside the synced folder
    biggest = sorted(((p.stat().st_size, p.name) for p in data.iterdir() if p.is_file()), reverse=True)[:8]
    out["biggest_files"] = [{"name": n, "mb": round(s / 1e6, 2)} for s, n in biggest]
    if git.exists():
        def g(*a: str) -> str:
            return subprocess.run(["git", "-C", str(data), *a], capture_output=True, text=True, timeout=120).stdout
        counts = dict(line.split(": ", 1) for line in g("count-objects", "-v").splitlines() if ": " in line)
        out["data_loose_mb"] = round(int(counts.get("size", 0)) / 1e3, 1)
        out["data_git_mb"] = round(int(counts.get("size-pack", 0)) / 1e3, 1)
        out["syncs_per_day"] = len(g("log", "--since=1 day ago", "--format=%h").split())
        tracked = [p for p in g("ls-files", "-ci", "--exclude-standard").splitlines() if p]
        out["tracked_but_ignored"] = tracked             # an older version committed these; sync untracks them
        out["unpushed_commits"] = len(g("log", "--format=%h", "@{u}..HEAD").split()) if g("rev-parse", "--abbrev-ref",
                                                                                            "@{u}").strip() else None
    beacon = Path(getattr(config, "MY_BEACON_FILE", data / "beacon.json"))
    out["beacon_kb"] = round(beacon.stat().st_size / 1e3, 2) if beacon.exists() else 0.0
    checks = {k: _verdict(out[k], BUDGETS[k]) for k in ("data_working_mb", "local_mb", "avatar_mb", "logs_mb", "beacon_kb")}
    for k in ("data_git_mb", "data_loose_mb", "syncs_per_day"):
        if k in out:
            checks[k] = _verdict(out[k], BUDGETS[k])
    if stray:
        checks["stray_in_data"] = "WARN"
    if out.get("tracked_but_ignored"):
        checks["tracked_but_ignored"] = "FAIL"
    out["checks"] = checks
    return out


# --------------------------------------------------------------------------- a throwaway profile for the live checks
def _isolate() -> Path:
    """Temporary data and settings folders for every OS, set before myGeeKy is imported, and no network."""
    root = Path(tempfile.mkdtemp(prefix="mygeeky-audit-"))
    for k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "APPDATA", "LOCALAPPDATA"):
        os.environ[k] = str(root / k.lower())
    if sys.platform == "darwin":
        os.environ["HOME"] = str(root / "home")         # macOS keeps app data under ~/Library
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    real = socket.socket.connect

    def connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and (host in ("localhost", "::1") or host.startswith("127.")):
            return real(self, address)
        raise OSError("the audit runs offline")
    socket.socket.connect = connect
    return root


def _panel():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv[:1])
    from mygeeky.config import MyGeekyConfig
    from mygeeky.gui.qt_panel import MyGeekyPanel
    cfg = MyGeekyConfig(github_username="audit", keywords=["gwas", "genomics", "machine learning", "snakemake"],
                        topics=["bioinformatics"])
    t = time.perf_counter()
    panel = MyGeekyPanel(cfg)
    panel.show()
    app.processEvents()
    return app, panel, time.perf_counter() - t


def _spin(app, seconds: float) -> None:
    """Pump events as the real main loop would, including the deletions deleteLater() queued (processEvents alone
    never delivers those, which would look like a leak that the running app doesn't have)."""
    from PySide6.QtCore import QCoreApplication, QEvent
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.01)


def startup() -> dict:
    before = _rss_mb()
    app, panel, took = _panel()
    _spin(app, 1.0)
    out = {"startup_s": round(took, 2), "rss_mb_after_open": round(_rss_mb(), 1), "rss_mb_before": round(before, 1)}
    out["checks"] = {"startup_s": _verdict(took, BUDGETS["startup_s"])}
    panel.close()
    return out


def leak(rounds: int = 8) -> dict:
    """Visit every page `rounds` times. The first two rounds fill caches; after that, memory and widgets must level off
    (like Valgrind's "definitely lost": what keeps growing with each identical round is a leak)."""
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication
    app, panel, _ = _panel()
    tabs = list(getattr(panel, "tab_buttons", {}).keys())
    tracemalloc.start(25)
    rows = []
    for r in range(rounds):
        for name in tabs:
            try:
                panel._switch_tab(name)
            except Exception:
                pass
            _spin(app, 0.05)
        gc.collect()
        _spin(app, 0.2)
        cur, _peak = tracemalloc.get_traced_memory()
        rows.append({"round": r + 1, "py_kb": round(cur / 1e3), "widgets": len(QApplication.allWidgets()),
                     "qobjects": len(panel.findChildren(QObject)), "rss_mb": round(_rss_mb(), 1)})
        if r == 1:
            base = tracemalloc.take_snapshot()
    steady = rows[2:] or rows
    span = max(1, len(steady) - 1)
    kb_per = (steady[-1]["py_kb"] - steady[0]["py_kb"]) / span
    w_per = (steady[-1]["widgets"] - steady[0]["widgets"]) / span
    top = []
    if rounds > 2:
        diff = tracemalloc.take_snapshot().compare_to(base, "lineno")
        top = [{"where": str(s.traceback[0]), "kb": round(s.size_diff / 1e3, 1), "blocks": s.count_diff}
               for s in diff[:8] if s.size_diff > 0]
    tracemalloc.stop()
    out = {"tabs": tabs, "rounds": rows, "kb_per_round": round(kb_per, 1), "widgets_per_round": round(w_per, 2),
           "growing_most": top, "rss_mb": rows[-1]["rss_mb"]}
    out["checks"] = {"leak_kb_per_round": _verdict(kb_per, BUDGETS["leak_kb_per_round"]),
                     "leak_widgets_per_round": _verdict(w_per, BUDGETS["leak_widgets_per_round"]),
                     "rss_mb": _verdict(rows[-1]["rss_mb"], BUDGETS["rss_mb"])}
    panel.close()
    return out


def _timers(app) -> list[dict]:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    seen, out = set(), []
    for w in QApplication.topLevelWidgets():
        for t in w.findChildren(QTimer):
            if t.isActive() and id(t) not in seen:
                seen.add(id(t))
                parent = t.parent()
                out.append({"ms": t.interval(), "single": t.isSingleShot(), "owner": type(parent).__name__ if parent else "",
                            "name": t.objectName()})
    return sorted(out, key=lambda x: x["ms"])


def idle(seconds: float = 20.0) -> dict:
    app, panel, _ = _panel()
    _spin_quiet(app, 45.0)          # the opening work: market, news and growth start 20-40 s in (qt_panel singleShots)

    def cpu(window: float) -> float:
        c0, t0 = time.process_time(), time.perf_counter()
        _spin_quiet(app, window)
        return 100 * (time.process_time() - c0) / max(1e-6, time.perf_counter() - t0)
    shown = cpu(seconds)
    timers_shown = _timers(app)
    panel.hide()
    _spin(app, 1.0)
    hidden = cpu(seconds)
    timers_hidden = _timers(app)
    out = {"idle_cpu_pct": round(shown, 2), "hidden_cpu_pct": round(hidden, 2),
           "timers_shown": timers_shown, "timers_hidden": timers_hidden,
           "fast_timers_hidden": [t for t in timers_hidden if t["ms"] < 1000 and not t["single"]]}
    out["checks"] = {"idle_cpu_pct": _verdict(shown, BUDGETS["idle_cpu_pct"]),
                     "hidden_cpu_pct": _verdict(hidden, BUDGETS["hidden_cpu_pct"])}
    if out["fast_timers_hidden"]:
        out["checks"]["fast_timers_hidden"] = "WARN"     # something repaints or polls under a second while hidden
    panel.close()
    return out


def _spin_quiet(app, seconds: float) -> None:
    """Run the event loop without busy-waiting (so the CPU measured is the program's own)."""
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec()


def main(argv: list[str]) -> int:
    what = argv[1] if len(argv) > 1 else "all"
    as_json = "--json" in argv
    nums = [a for a in argv[2:] if a.replace(".", "", 1).isdigit()]
    report: dict = {"platform": sys.platform, "python": sys.version.split()[0]}
    if what in ("storage", "all") and "--isolated" not in argv:
        report["storage"] = storage()
    if what in ("leak", "idle", "startup", "all"):
        _isolate()
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        if what in ("startup", "all"):
            report["startup"] = startup()
        if what in ("leak", "all"):
            report["leak"] = leak(int(nums[0]) if nums and what == "leak" else 8)
        if what in ("idle", "all"):
            report["idle"] = idle(float(nums[0]) if nums and what == "idle" else 20.0)
    worst = "PASS"
    for part in report.values():
        if isinstance(part, dict):
            for v in part.get("checks", {}).values():
                worst = "FAIL" if "FAIL" in (v, worst) else "WARN" if "WARN" in (v, worst) else worst
    report["verdict"] = worst
    if as_json:
        print(json.dumps(report, indent=1, default=str))
    else:
        for name, part in report.items():
            if isinstance(part, dict):
                print(f"== {name}")
                for k, v in part.items():
                    if k not in ("rounds", "timers_shown", "timers_hidden"):
                        print(f"  {k}: {v}")
        print("verdict:", worst)
    return 1 if worst == "FAIL" and "--strict" in argv else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
