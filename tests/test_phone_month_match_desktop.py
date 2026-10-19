"""My month and ranks: the desktop (month.py) and the phone (lib/month.ts) count the same month the same way,
draw the same card and ladder, and both apps count the things you do."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from mygeeky import month

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"


def _at(day: str) -> str:
    return f"{day}T10:00:00+00:00"


USAGE = [
    {"at": _at("2026-08-30"), "what": "open"},
    {"at": _at("2026-08-30"), "what": "click", "kind": "paper"},
    {"at": _at("2026-09-02"), "what": "step"},
    {"at": _at("2026-09-15"), "what": "quiz"},
    {"at": _at("2026-10-01"), "what": "open"},
    {"at": _at("2026-10-01"), "what": "click", "kind": "headline", "cat": "ai"},
    {"at": _at("2026-10-02"), "what": "click", "kind": "paper"},
    {"at": _at("2026-10-02"), "what": "click", "kind": "model", "explore": True},
    {"at": _at("2026-10-03"), "what": "build"},
    {"at": _at("2026-10-03"), "what": "step"},
    {"at": _at("2026-10-05"), "what": "skill"},
    {"at": _at("2026-10-09"), "what": "quiz"},
    {"at": _at("2026-10-11"), "what": "share"},
    {"at": _at("2026-10-14"), "what": "idea"},
    {"at": _at("2026-10-20"), "what": "chance"},
    {"at": _at("2026-10-31"), "what": "click", "kind": "person"},      # earns nothing, and isn't a day by itself
    {"at": _at("2026-11-01"), "what": "click", "kind": "paper"},       # next month: not in October
    {"at": "not a date", "what": "open"},
    "not a line",
]
EVENTS = [{"at": _at("2026-10-07"), "kind": "follow"}, {"at": _at("2026-10-08"), "kind": "star"}]
WINS = [{"kind": "stars", "count": 3, "at": _at("2026-10-09")}, {"kind": "citations", "at": _at("2026-10-12")},
        {"kind": "forks", "count": 2, "at": _at("2026-10-12")}]
MONTHS = [(2026, 10), (2026, 9), (2026, 8), (2026, 2), (2025, 12), (2026, 11)]
LADDER = [0, 49, 50, 208, 740, 3499, 3500, 9000]


def _node() -> bool:
    if not shutil.which("node"):
        return False
    v = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip().lstrip("v").split(".")
    return len(v) > 1 and v[0].isdigit() and v[1].isdigit() and (int(v[0]), int(v[1])) >= (22, 6)


def test_a_month_adds_up():
    s = month.summary(USAGE, EVENTS, WINS, 2026, 10)
    assert s["counts"] == {"share": 1, "idea": 1, "step": 1, "build": 1, "quiz": 1, "skill": 1, "paper": 1,
                           "news": 1, "repo": 1, "topic": 1, "chance": 1, "friend": 1, "star": 3, "cite": 1}
    assert s["active"] == 9                       # the days you did something (not the wins, not just coming by)
    assert s["active"] == sum(1 for d in s["days"] if set(d) - {"star", "cite"})
    assert s["month_points"] == 8 + 6 + 5 + 10 + 4 + 10 + 2 + 1 + 1 + 3 + 2 + 3
    assert s["points"] == s["month_points"] + 2 + 5 + 4
    assert s["highlights"][0][2] and s["highlights"][0][0] in ("build", "skill")   # a first, worth the most
    assert "quiz" not in [h[0] for h in s["highlights"] if h[2]]                   # you'd taken one in September
    assert s["rank_name"] == "Corporal" and s["promoted"]
    assert s["days"][8] == ["quiz", "star"]


def test_a_rank_never_goes_down_and_wins_earn_no_points():
    quiet = month.summary(USAGE, EVENTS, WINS, 2026, 12)
    assert quiet["active"] == 0 and quiet["month_points"] == 0 and quiet["points"] >= 50
    assert quiet["rank_name"] == "Corporal" and not quiet["promoted"]
    only_wins = month.summary([], [], WINS * 50, 2026, 10)
    assert only_wins["points"] == 0 and only_wins["counts"]["star"] == 150
    assert [month.rank_of(p) for p in LADDER] == [0, 0, 1, 2, 4, 6, 7, 7]


def test_the_card_draws_every_month():
    for y, m in MONTHS:
        s = month.summary(USAGE, EVENTS, WINS, y, m)
        svg = month.card_svg(s, month.geekoc(month.card_pose(s)), ["chance"])
        assert svg.startswith("<svg") and svg.endswith("</svg>") and f"My {s['month_name']}" in svg
    assert month.geekoc("cheer").startswith("<defs>")


@pytest.mark.skipif(not _node(), reason="needs Node 22.6+")
def test_the_phone_counts_and_draws_exactly_as_the_desktop():
    work = MOBILE / ".crosscheck"
    work.mkdir(exist_ok=True)
    src = (MOBILE / "src" / "lib" / "month.ts").read_text(encoding="utf-8")
    (work / "month.ts").write_text(src.replace("from '../data/ranks.json';", "from './ranks.json' with { type: 'json' };"),
                                   encoding="utf-8")
    shutil.copy(MOBILE / "src" / "data" / "ranks.json", work / "ranks.json")
    (work / "month-side.ts").write_text(
        "import { readFileSync } from 'node:fs';\n"
        "import { cardPose, cardSvg, ladderSvg, summary, firstMonth } from './month.ts';\n"
        "const [usage, events, wins, months, ladder, geekoc] = JSON.parse(readFileSync(0, 'utf8'));\n"
        "const out = months.map(([y, m]) => { const s = summary(usage, events, wins, y, m);\n"
        "  return { s, pose: cardPose(s), card: cardSvg(s, geekoc[cardPose(s)] ?? '', ['chance', 'star']) }; });\n"
        "console.log(JSON.stringify({ out, first: firstMonth(usage, events),\n"
        "  ladder: ladder.map((p) => [ladderSvg(p), ladderSvg(p, true)]) }));\n", encoding="utf-8")
    poses = json.loads((MOBILE / "src" / "data" / "geekoc.json").read_text(encoding="utf-8"))["poses"]
    out = subprocess.run(["node", "--experimental-strip-types", str(work / "month-side.ts")],
                         input=json.dumps([USAGE, EVENTS, WINS, MONTHS, LADDER, poses]),
                         capture_output=True, text=True, cwd=MOBILE, timeout=60)
    assert out.returncode == 0, out.stderr[-800:]
    phone = json.loads(out.stdout)
    for (y, m), said in zip(MONTHS, phone["out"]):
        s = month.summary(USAGE, EVENTS, WINS, y, m)
        assert s == said["s"], (y, m)
        assert month.card_pose(s) == said["pose"]
        assert month.card_svg(s, month.geekoc(month.card_pose(s)), ["chance", "star"]) == said["card"], (y, m)
    assert list(month.first_month(USAGE, EVENTS)) == phone["first"]
    for p, (dark, light) in zip(LADDER, phone["ladder"]):
        assert month.ladder_svg(p) == dark and month.ladder_svg(p, True) == light, p


def test_the_rules_and_geekoc_are_the_same_files_on_both():
    for name in ("ranks.json", "geekoc.json"):
        assert (ROOT / "src" / "mygeeky" / "data" / name).read_bytes() == (MOBILE / "src" / "data" / name).read_bytes()


def test_both_apps_count_what_you_do():
    app = (ROOT / "src" / "mygeeky" / "gui" / "app.py").read_text(encoding="utf-8")
    for what in ("build", "step", "skill", "quiz", "share", "chance"):
        assert f'did("{what}")' in app, what
    phone = "".join(p.read_text(encoding="utf-8") for p in (MOBILE / "src").rglob("*.tsx"))
    for what in ("build", "step", "skill", "quiz", "share", "chance", "idea"):
        assert re.search(rf"logDid\('{what}'\)", phone), what


# --------------------------------------------------------------------------- the eight drawings
def _viz_inputs() -> dict:
    def at(d: int, h: int = 10, mi: int = 0, mo: int = 10) -> str:
        return f"2026-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:00+00:00"
    repos = ["me/a", "me/b", "me/c", "other/x"]
    terms = ["single cell", "gwas", "nextflow", "statistics", "spatial omics", "protein folding", "llm agents", "ecology"]
    gh = [{"at": at(d), "type": "PushEvent", "repo": repos[(d * 7 + k) % 4], "n": (d + k) % 4 + 1}
          for d in range(1, 32) for k in range(d % 4)]
    gh += [{"at": at(d), "type": "PullRequestEvent", "action": "opened", "repo": "me/a"} for d in (3, 9, 17, 24)]
    gh += [{"at": at(5), "type": "PullRequestEvent", "action": "closed", "repo": "me/a"},
           {"at": at(2, mo=9), "type": "PushEvent", "repo": "me/a", "n": 9}]
    events = [{"at": at(d), "kind": "news", "terms": {terms[d % 8]: round(0.1 + (d % 7) / 10, 2), terms[d % 5]: 0.4}}
              for d in range(1, 32)]
    events += [{"at": at(d, mo=9), "kind": "repo", "terms": {(terms[:5] + ["plant breeding"])[d % 6]: 0.6}}
               for d in range(1, 30)]
    events += [{"at": at(d), "kind": "follow", "terms": {"gwas": 0.3}} for d in (6, 14, 20)]
    usage = [{"at": at(1 + k % 31, (9, 10, 14, 20, 21, 22, 23, 0)[k % 8], (k * 13) % 60), "what": "click", "kind": "paper"}
             for k in range(120)]
    return {"has_github": True, "github": gh, "repo_langs": {"me/a": "Python", "me/b": "R", "me/c": "TypeScript"},
            "wins": [{"kind": "stars", "count": d % 5 + 1, "at": at(d)} for d in (2, 3, 5, 8, 11, 15, 19, 22, 27, 30)]
            + [{"kind": "citations", "count": 1, "at": at(d)} for d in (4, 12, 23)]
            + [{"kind": "forks", "count": 1, "at": at(d)} for d in (6, 18)],
            "events": events, "usage": usage,
            "protocols": [{"title": "R for data analysis", "steps": [["R basics", True], ["Statistics with R", True],
                                                                   ["Tidy data", True], ["A real project", False]]},
                          {"title": "Nextflow pipelines", "steps": [["First pipeline", True], ["Channels", False]]}],
            "badges": [["🔭", "Explorer", "silver"], ["📰", "News Reader", "gold"], ["🤝", "Networker", "bronze"]],
            "sent": [{"at": at(3), "type": "thanks"}, {"at": at(9), "type": "learn"}, {"at": at(12), "type": "collab"}],
            "received": [{"at": at(5), "type": "thanks"}, {"at": at(20), "type": "join"}]}


VIZ_MONTHS = [(2026, 10, 0), (2026, 10, 120), (2026, 9, -300), (2026, 2, 0)]


def test_the_drawings_count_the_month():
    from mygeeky import monthviz
    s = monthviz.stats(_viz_inputs(), 2026, 10)
    assert s["github"]["total"] == sum(s["github"]["days"]) and s["github"]["prs"][2] and not s["github"]["prs"][4]
    assert [name for name, _ in s["languages"]][-1] == "Other" and sum(p for _, p in s["languages"]) in (99, 100, 101)
    assert s["wins"][0] == [2, 3, 0, 0] and len(s["wins"]) == 15
    assert s["give"] == [["thank-yous", 2, 1], ["invites", 1, 1], ["follows", 3, None]]
    assert sum(s["hours"]) == 120 and s["topics"][0][1] == 100
    assert any(new for _, _, new in s["topics"]) and s["shift"]
    empty = monthviz.stats({}, 2026, 10)
    for _, _, _, draw in monthviz.DIVES:
        assert draw(empty, {}).startswith("<svg")          # nothing yet still draws (a line saying so)


@pytest.mark.skipif(not _node(), reason="needs Node 22.6+")
def test_the_phone_draws_the_eight_exactly_as_the_desktop():
    from mygeeky import monthviz
    work = MOBILE / ".crosscheck"
    work.mkdir(exist_ok=True)
    src = (MOBILE / "src" / "lib" / "month.ts").read_text(encoding="utf-8")
    (work / "month.ts").write_text(src.replace("from '../data/ranks.json';", "from './ranks.json' with { type: 'json' };"),
                                   encoding="utf-8")
    shutil.copy(MOBILE / "src" / "data" / "ranks.json", work / "ranks.json")
    viz = (MOBILE / "src" / "lib" / "month-viz.ts").read_text(encoding="utf-8").replace("from './month';", "from './month.ts';")
    (work / "month-viz.ts").write_text(viz, encoding="utf-8")
    (work / "viz-side.ts").write_text(
        "import { readFileSync } from 'node:fs';\n"
        "import { DIVES, say, stats } from './month-viz.ts';\n"
        "const [inputs, months, gk] = JSON.parse(readFileSync(0, 'utf8'));\n"
        "console.log(JSON.stringify(months.map(([y, m, tz]) => { const s = stats(inputs, y, m, tz);\n"
        "  return { s, svgs: DIVES.map(([k, , , draw]) => [k, draw(s, gk), say(s, k)]) }; })));\n", encoding="utf-8")
    poses = json.loads((MOBILE / "src" / "data" / "geekoc.json").read_text(encoding="utf-8"))["poses"]
    inputs = _viz_inputs()
    out = subprocess.run(["node", "--experimental-strip-types", str(work / "viz-side.ts")],
                         input=json.dumps([inputs, VIZ_MONTHS, poses]), capture_output=True, text=True, cwd=MOBILE, timeout=60)
    assert out.returncode == 0, out.stderr[-800:]
    for (y, m, tz), phone in zip(VIZ_MONTHS, json.loads(out.stdout)):
        s = monthviz.stats(inputs, y, m, tz)
        assert json.loads(json.dumps(s)) == phone["s"], (y, m)
        for (key, _, _, draw), (pkey, svg, said) in zip(monthviz.DIVES, phone["svgs"]):
            assert key == pkey and monthviz.say(s, key) == said, key
            assert draw(s, poses) == svg, (y, m, key)
