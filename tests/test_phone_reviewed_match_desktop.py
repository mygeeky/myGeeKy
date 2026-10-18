"""The Protocols tab shows the 3 reviewed protocols that fit you best, then "See all" -- the same 3 on both apps.

The phone's ordering (mobile/src/lib/reviewed-fit.ts) is a port of protocols.by_fit; this runs the phone's real
TypeScript in Node on the real reviewed list and several profiles, and holds its order against the Python.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from mygeeky import curated, protocols
from mygeeky.gui.qt_panel import reviewed_heading, see_all_text

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
WORK = MOBILE / ".crosscheck"
PROFILES = {
    "gwas": {"gwas": 1.0, "genetics": 0.6, "statistics": 0.5},
    "nextflow": {"nextflow": 1.0, "pipelines": 0.7},
    "web": {"javascript": 1.0, "web": 0.8},
    "imaging": {"microscopy": 1.0, "image analysis": 0.8},
    "nothing known": {"medieval poetry": 1.0},
    "empty": {},
}
SCRIPT = """
import { byFit, REVIEWED_SHOWN, reviewedHeading, seeAllText } from './reviewed-fit.ts';
import { readFileSync } from 'node:fs';
const list = JSON.parse(readFileSync(process.argv[2], 'utf-8')).protocols;
const profiles = JSON.parse(process.argv[3]);
const order = Object.fromEntries(Object.entries(profiles).map(([k, w]) => [k, byFit(list, w).map((p) => p.id)]));
console.log(JSON.stringify({ order, shown: REVIEWED_SHOWN, words: [reviewedHeading(true), reviewedHeading(false),
  seeAllText(14, false), seeAllText(14, true)] }));
"""


def _node() -> bool:
    if not shutil.which("node"):
        return False
    v = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip().lstrip("v").split(".")
    return len(v) > 1 and v[0].isdigit() and v[1].isdigit() and (int(v[0]), int(v[1])) >= (22, 6)   # runs TypeScript


def test_the_best_fit_comes_first_and_ties_keep_the_makers_order():
    data = curated.load()
    ids = [p["id"] for p in protocols.reviewed(data)]
    gwas = [p["id"] for p in protocols.by_fit(protocols.reviewed(data), PROFILES["gwas"])]
    assert gwas[0] == "gwas" and sorted(gwas) == sorted(ids)
    assert [p["id"] for p in protocols.by_fit(protocols.reviewed(data), {})] == ids     # nothing to go on: as listed


@pytest.mark.skipif(not _node(), reason="needs Node 23+")
def test_the_phone_picks_the_same_ones_in_the_same_order_and_says_the_same():
    WORK.mkdir(exist_ok=True)
    for name in ("interests", "reviewed-fit"):          # the real files; Node wants the .ts on each import
        src = (MOBILE / "src" / "lib" / f"{name}.ts").read_text(encoding="utf-8")
        (WORK / f"{name}.ts").write_text(re.sub(r"from '\./interests'", "from './interests.ts'", src), encoding="utf-8")
    runner = WORK / "reviewed-side.ts"
    runner.write_text(SCRIPT, encoding="utf-8")
    lists = ROOT / "mobile" / "src" / "data" / "curated.json"
    out = subprocess.run(["node", "--experimental-strip-types", str(runner), str(lists), json.dumps(PROFILES)],
                         capture_output=True, text=True, cwd=MOBILE, timeout=60)
    assert out.returncode == 0, out.stderr
    phone = json.loads(out.stdout)
    reviewed = protocols.reviewed(curated.load())
    for name, weights in PROFILES.items():
        assert phone["order"][name] == [p["id"] for p in protocols.by_fit(reviewed, weights)], name
    assert phone["shown"] == protocols.REVIEWED_SHOWN
    assert phone["words"] == [reviewed_heading(True), reviewed_heading(False), see_all_text(14, False),
                              see_all_text(14, True)]


def test_the_panel_shows_the_best_three_then_all_of_them(monkeypatch):
    pytest.importorskip("PySide6")
    from mygeeky.config import MyGeekyConfig
    from tests.test_freshness import _close, _quiet_panel
    monkeypatch.setattr("mygeeky.gui.app.growth_due", lambda cfg: False)
    app, panel = _quiet_panel(monkeypatch, MyGeekyConfig(github_username="me", keywords=["gwas"]))
    try:
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtWidgets import QPushButton

        def buttons() -> list[str]:
            for w in list(panel._workers):
                w.wait(5000)
            app.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            return [b.text() for b in panel.grow_area.parentWidget().findChildren(QPushButton)]

        panel._switch_tab("grow")
        panel._set_grow_mode("paths")
        texts = buttons()
        n = len(protocols.reviewed(curated.load()))
        reviewed = [t for t in texts if t.startswith("🧭 ") and t != "🧭 Build"]
        assert len([t for t in reviewed if not t.startswith("🧭 Build")]) <= protocols.REVIEWED_SHOWN + 1
        assert see_all_text(n, False) in texts and any("Genome-wide association" in t for t in texts)
        panel._toggle_all_reviewed()
        texts = buttons()
        assert "Show fewer" in texts
        assert sum(1 for t in texts if t.startswith("🧭 ") and "Build" not in t) >= n
    finally:
        _close(panel)
