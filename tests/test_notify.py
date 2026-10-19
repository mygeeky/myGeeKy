"""Careful notifications: off until switched on, only what's worth it, each thing once, one line at most once a
day (or week), never in quiet hours -- and the phone (lib/notify.ts) decides exactly as the desktop."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from mygeeky import notify

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
TODAY = "2026-10-19"
SEASONS = [
    {"id": "daad", "title": "DAAD research grants for doctoral candidates and young academics", "when": {"state": "soon", "days_to_open": 12, "opens": "2026-10-31"}},
    {"id": "fulbright", "title": "Fulbright", "when": {"state": "open", "confirmed": True, "days_to_open": 0, "opens": "2026-10-01"}},
    {"id": "guess", "title": "Expected open", "when": {"state": "open", "confirmed": False, "days_to_open": 0, "opens": "2026-10-02"}},
    {"id": "later", "title": "Later", "when": {"state": "later", "days_to_open": 60, "opens": "2026-12-18"}},
]
RANKED = {"jobs": [{"id": "j1", "title": "Postdoc in GWAS", "score": 0.82, "days_left": 20},
                   {"id": "j2", "title": "PhD in ecology", "score": 0.71, "days_left": None},
                   {"id": "j3", "title": "Weak fit", "score": 0.4, "days_left": 5}],
          "funding": [{"id": "f1", "title": "Travel grant", "score": 0.9, "days_left": 3}],
          "conferences": [{"id": "c1", "title": "ISMB", "score": 0.69, "days_left": 40}]}
PAPERS = [{"id": "W1", "title": "New and rising", "date": "2026-10-01"}, {"id": "W2", "title": "Old", "date": "2025-01-01"},
          {"id": "W3", "title": "Recent", "date": "2026-09-10"}, {"id": "W4", "title": "Fourth, not top 3", "date": "2026-10-10"}]
HIGHLIGHTS = [{"id": "hl-a", "title": "Some genes", "added": "2026-10-18"}, {"id": "hl-b", "title": "Old one", "added": "2026-09-01"}]
SETTINGS = [{"kinds": ["jobs", "seasons", "nonsense"], "every": "weekly", "quiet": [23, 7]},
            {"kinds": ["papers", "highlights", "funding", "conferences", "jobs", "seasons"]},
            {"kinds": ["highlights"], "quiet": [8, 8]}, {}, "junk", {"kinds": ["jobs"], "quiet": [True, 30], "every": "hourly"}]


def _node() -> bool:
    if not shutil.which("node"):
        return False
    v = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip().lstrip("v").split(".")
    return len(v) > 1 and v[0].isdigit() and v[1].isdigit() and (int(v[0]), int(v[1])) >= (22, 6)


def _desktop() -> list:
    out = []
    cands = notify.candidates(TODAY, SEASONS, RANKED, PAPERS, HIGHLIGHTS)
    for raw in SETTINGS:
        s = notify.clean_settings(raw)
        chosen = notify.pick(cands, ["jobs:j2"], s)
        out.append({"s": s, "describe": notify.describe(s), "chosen": chosen, "summary": notify.summary(chosen),
                    "told": notify.remember(["x"], chosen),
                    "due": [notify.due(s, last, f"{TODAY}T{h:02d}:00", h)
                            for last in ("", "2026-10-18", "2026-10-12", "bad") for h in (3, 12, 23)]})
    return out


def test_off_until_switched_on_and_quiet_by_design():
    s = notify.clean_settings({})
    assert s["kinds"] == [] and not notify.due(s, "", "2026-10-19T12:00", 12)
    assert notify.describe(s).startswith("All off")
    on = notify.clean_settings({"kinds": ["jobs"], "quiet": [22, 8]})
    assert notify.due(on, "", "x", 12) and not notify.due(on, "", "x", 23) and not notify.due(on, "", "x", 3)
    assert not notify.due(on, "2026-10-19", "2026-10-19T12:00", 12)         # once a day at most
    weekly = notify.clean_settings({"kinds": ["jobs"], "every": "weekly"})
    assert not notify.due(weekly, "2026-10-14", "2026-10-19T12:00", 12) and notify.due(weekly, "2026-10-12", "2026-10-19", 12)


def test_only_what_is_worth_it_once_and_in_one_line():
    cands = notify.candidates(TODAY, SEASONS, RANKED, PAPERS, HIGHLIGHTS)
    ids = {c["id"] for c in cands}
    assert "season:daad:2026-10-31" in ids and "season:fulbright:2026-10-01" in ids
    assert not any(i.startswith(("season:guess", "season:later")) for i in ids)          # a guess isn't news
    assert "jobs:j1" in ids and "jobs:j3" not in ids and "conferences:c1" not in ids      # only very good fits
    assert {"paper:W1", "paper:W3"} <= ids and "paper:W2" not in ids and "paper:W4" not in ids
    assert "highlight:hl-a" in ids and "highlight:hl-b" not in ids
    s = notify.clean_settings({"kinds": ["jobs", "seasons", "funding"]})
    chosen = notify.pick(cands, ["jobs:j2"], s)
    assert [c["id"] for c in chosen][:2] == ["season:fulbright:2026-10-01", "funding:f1"]   # the most urgent first
    out = notify.summary(chosen)
    assert out["body"] == "🗓 2 Seasons open soon · 💶 1 funding call fits you · 💼 1 job fits you"
    assert out["tab"] == "chances" and notify.summary([]) is None
    told = notify.remember(["jobs:j2"], chosen)
    assert notify.pick(cands, told, s) == []                                             # never the same thing twice


@pytest.mark.skipif(not _node(), reason="needs Node 22.6+")
def test_the_phone_decides_exactly_as_the_desktop():
    work = MOBILE / ".crosscheck"
    work.mkdir(exist_ok=True)
    shutil.copy(MOBILE / "src" / "lib" / "notify.ts", work / "notify.ts")
    (work / "notify-side.ts").write_text(
        "import { readFileSync } from 'node:fs';\n"
        "import { candidates, cleanSettings, describe, due, pick, remember, summary } from './notify.ts';\n"
        "const [today, seasons, ranked, papers, highlights, all] = JSON.parse(readFileSync(0, 'utf8'));\n"
        "const cands = candidates(today, seasons, ranked, papers, highlights);\n"
        "console.log(JSON.stringify(all.map((raw) => { const s = cleanSettings(raw); const chosen = pick(cands, ['jobs:j2'], s);\n"
        "  return { s, describe: describe(s), chosen, summary: summary(chosen), told: remember(['x'], chosen),\n"
        "    due: ['', '2026-10-18', '2026-10-12', 'bad'].flatMap((last) => [3, 12, 23].map((h) =>\n"
        "      due(s, last, `${today}T${String(h).padStart(2, '0')}:00`, h))) }; })));\n", encoding="utf-8")
    run = subprocess.run(["node", "--experimental-strip-types", str(work / "notify-side.ts")],
                         input=json.dumps([TODAY, SEASONS, RANKED, PAPERS, HIGHLIGHTS, SETTINGS]),
                         capture_output=True, text=True, cwd=MOBILE, timeout=60)
    assert run.returncode == 0, run.stderr[-800:]
    assert json.loads(run.stdout) == json.loads(json.dumps(_desktop()))
