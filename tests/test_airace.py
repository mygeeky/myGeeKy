"""The AI race: building it from Epoch's files, reading it safely, what the page shows, and the phone agreeing."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pytest

import phone
from mygeeky import airace

ROOT = Path(__file__).resolve().parents[1]


def epoch_files() -> dict[str, str]:
    """A tiny Epoch download: four models, two benchmarks (one coding, one math)."""
    meta = ("benchmark,in_eci,source_file,score_column,scale,random_baseline,score_ceiling,release_date,superseded_by\n"
            "SWE-Bench verified,True,swe.csv,Best score (across scorers),1.0,0.0,1.0,2024-08-13,\n"
            "MATH level 5,True,math.csv,Best score (across scorers),1.0,0.0,1.0,2021-03-05,\n"
            "Aider polyglot,False,aider.csv,Percent correct,0.01,0,1.0,2024-12-01,\n")
    models = ("model_version,model_group,date,display_name,organization,country,accessibility,training_compute_flop\n"
              "a-1,Alpha 1,2026-09-01,,Lab A,,,\nb-1,Beta 1,2026-08-01,,Lab B,,,\nc-1,Gamma Open,2026-07-01,,Lab C,,,\n"
              "old-1,Old One,2023-01-01,,Lab A,,,\n")
    eci = ("Model,Display name,eci,eci_ci_low,eci_ci_high,date,Organization,Country (of organization),Model accessibility,"
           "Accessibility group,model_versions\n"
           "Alpha 1,Alpha 1,160,155,165,2026-09-01,Lab A,US,API access,Closed weights,\n"
           "Beta 1,Beta 1,150,145,155,2026-08-01,\"Lab B,Uni X\",US,API access,Closed weights,\n"
           "Gamma Open,Gamma Open,140,135,145,2026-07-01,Lab C,CN,Open weights,Open weights,\n"
           "Old One,Old One,100,95,105,2023-01-01,Lab A,US,API access,Closed weights,\n")
    swe = "Model version,Best score (across scorers),Release date\na-1,0.8,x\nb-1,0.6,x\nc-1,0.7,x\nold-1,0.2,x\n"
    math = "Model version,Best score (across scorers),Release date\na-1,0.9,x\nb-1,0.95,x\nc-1,0.5,x\n"
    aider = "Model version,Percent correct,Release date\na-1,70,x\nb-1,40,x\nc-1,55,x\n"
    return {"benchmark_metadata.csv": meta, "model_metadata.csv": models, "epoch_capabilities_index/eci_scores.csv": eci,
            "swe.csv": swe, "math.csv": math, "aider.csv": aider}


def test_build_scores_groups_from_a_guess_to_the_ceiling():
    d = airace.build(epoch_files(), date(2026, 10, 1))
    by = {m["model"]: m for m in d["models"]}
    assert by["Alpha 1"]["groups"]["Coding"]["score"] == 0.75        # (0.8 + 0.70) / 2
    assert by["Beta 1"]["groups"]["Math"]["score"] == 0.95
    assert by["Gamma Open"]["open"] is True and by["Beta 1"]["org"] == "Lab B,Uni X"
    assert "Coding" not in by["Old One"]["groups"], "a model from years ago isn't ranked within a skill"
    assert d["groups"]["Coding"]["top"][0]["model"] == "Alpha 1" and d["groups"]["Coding"]["ranked"] == 3
    assert by["Alpha 1"]["best"] == "", "best at needs results in at least three skills"


def test_build_reads_the_zip_epoch_publishes():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in epoch_files().items():
            z.writestr(name, text)
    assert len(airace.build_from_zip(buf.getvalue(), date(2026, 10, 1))["models"]) == 4


def test_what_comes_from_the_internet_is_cleaned():
    d = airace.clean({"version": "2026-10-01<script>", "models": [
        {"model": "X", "eci": "nan", "date": "2026-01-01"}, {"model": "Y", "eci": 120, "date": "soon"},
        {"model": "Z" * 200, "eci": 130, "date": "2026-02-01", "open": "yes", "best": "Hacking",
         "groups": {"Coding": {"score": 4, "pct": -1}, "Evil": {"score": 1, "pct": 1}}}, "junk"],
        "groups": {"Coding": {"top": [{"model": "Z", "score": 2}], "benchmarks": [1, "B"]}}})
    assert d["version"] == "" and len(d["models"]) == 1
    z = d["models"][0]
    assert len(z["model"]) == 80 and z["open"] is False and z["best"] == ""
    assert z["groups"] == {"Coding": {"score": 1.0, "pct": 0.0}}
    assert d["groups"]["Coding"]["top"] == [{"model": "Z", "score": 1.0, "n": 0}] and d["groups"]["Coding"]["benchmarks"] == ["B"]


def test_the_shipped_file_is_the_phones_too():
    assert (ROOT / "src/mygeeky/data/ai_race.json").read_bytes() == (ROOT / "mobile/src/data/ai_race.json").read_bytes()
    s = airace.stats(airace.load(force=True))
    assert not s["empty"] and s["count"] > 100 and s["leader"]["eci"] >= s["best_open"]["eci"]


def test_the_page_numbers():
    s = airace.stats(airace.clean(airace.build(epoch_files(), date(2026, 10, 1))))
    assert s["leader"] == {"model": "Alpha 1", "org": "Lab A", "eci": 160.0}
    assert s["runner_up"] == {"org": "Lab B", "eci": 150.0} and s["best_open"]["model"] == "Gamma Open"
    assert s["months"][0] == "2024-01-31" and s["months"][-1] == "2026-09-30"
    assert s["recent"][0]["model"] == "Alpha 1" and s["recent"][0]["rank"] == 1 and s["recent"][0]["fresh"]
    assert s["recent"][2]["fresh"] is False, "July is more than two weeks before the newest release"
    assert s["behind_now"] == 1 and s["closed"][-1] == 160.0     # 140 open (Jul); closed first got there in Aug


EDGE = {"version": "2026-03-01", "models": [
    {"model": "Closed A", "eci": 120, "date": "2025-01-15", "org": "A"},
    {"model": "Open B", "eci": 118, "date": "2025-06-30", "org": "B", "open": True},
    {"model": "Closed C", "eci": 130, "date": "2025-11-02", "org": "A"},
    {"model": "Open D", "eci": 125, "date": "2026-02-27", "org": "D, Uni", "open": True,
     "groups": {"Coding": {"score": .8, "pct": 1}, "Math": {"score": .5, "pct": .2}, "Vision": {"score": .7, "pct": .9}},
     "best": "Coding"},
    {"model": "Closed E", "eci": 131, "date": "2026-02-28", "org": "",
     "groups": {"Coding": {"score": .6, "pct": .5}, "Math": {"score": .9, "pct": 1}, "Vision": {"score": .7, "pct": .9}},
     "best": "Math"}],
    "groups": {"Coding": {"top": [{"model": "Open D", "score": .8, "n": 2}], "ranked": 2, "benchmarks": ["S"]}}}


def test_months_behind_counts_from_when_closed_got_there():
    s = airace.stats(airace.clean(EDGE))
    # Open D (125, Feb 2026): closed first reached 125 with Closed C in Nov 2025, three months before
    assert s["behind"][-1] == 3 and s["behind_now"] == 3
    assert airace.race(airace.clean(EDGE), "2026-02-28")[0] == {"org": "Not given", "model": "Closed E", "eci": 131.0,
                                                               "open": False}
    assert airace.pick(airace.clean(EDGE), ["Coding", "Vision"])[0]["model"] == "Open D"


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_shows_the_same_race():
    shipped = json.loads((ROOT / "src/mygeeky/data/ai_race.json").read_text())
    cases = [shipped, EDGE, airace.build(epoch_files(), date(2026, 10, 1)), {"models": "x"}, {}]
    said = phone.run("""
import { clean, stats, race, pick } from './lib/ai-race.ts';
out(INPUT.map((d: any) => { const c = clean(d); const s = stats(c);
  return { clean: c, stats: s, race: s.empty ? [] : race(c, s.months[s.months.length - 1]),
           pick: [pick(c, ['Coding', 'Math']), pick(c, ['Vision']), pick(c, ['Nope'])] }; }));
""", cases)
    for case, got in zip(cases, said):
        c = airace.clean(case)
        s = airace.stats(c)
        assert json.loads(json.dumps(c)) == got["clean"]
        assert json.loads(json.dumps(s)) == got["stats"]
        assert json.loads(json.dumps(airace.race(c, s["months"][-1]) if not s["empty"] else [])) == got["race"]
        assert json.loads(json.dumps([airace.pick(c, ["Coding", "Math"]), airace.pick(c, ["Vision"]),
                                      airace.pick(c, ["Nope"])])) == got["pick"]
