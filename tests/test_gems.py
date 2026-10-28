"""GEMS (gems.py, docs/GEMS.md): the games' pack passes its own checks, a round picks from your field and brings
back what you got wrong, scores and levels add up, the Model and the badges learn from play -- and the phone's
lib/gems.ts answers exactly the same on the same inputs (its real TypeScript, run in Node)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import phone
from mygeeky import gems

ROOT = Path(__file__).resolve().parents[1]
PACK = json.loads((ROOT / "src/mygeeky/data/games.json").read_text(encoding="utf-8"))
TODAY = "2026-10-27"


def test_the_pack_is_valid_and_the_same_on_both_apps():
    assert gems.validate(PACK) == []
    assert (ROOT / "mobile/src/data/games.json").read_bytes() == (ROOT / "src/mygeeky/data/games.json").read_bytes()
    kinds = {it["kind"] for it in PACK["items"]}
    for g in gems.GAMES:                                      # every game has something to play
        assert any(k in kinds or k == "question" for k in g["kinds"]), g["id"]


def test_every_game_has_its_icon_on_both_apps():
    for g in gems.GAMES:
        assert (ROOT / f"src/mygeeky/gui/assets/game_{g['id']}.png").is_file(), g["id"]
        assert (ROOT / f"mobile/assets/games/{g['id']}.png").is_file(), g["id"]


def test_validate_names_what_is_wrong():
    bad = copy.deepcopy(PACK)
    bad["items"][0]["source"]["url"] = "http://not-https.example"
    bad["items"][1]["id"] = bad["items"][0]["id"]
    cmd = next(it for it in bad["items"] if it["kind"] == "command")
    cmd["right"] = [cmd["right"][0], cmd["right"][0]]
    probs = " | ".join(gems.validate(bad))
    assert "https link" in probs and "id used twice" in probs and "two right commands" in probs
    assert gems.validate({"items": []}) == ["the pack has no items"]


def test_pick_mixes_your_field_new_territory_and_what_came_back():
    items = gems.items_of(PACK, "year")
    weights = {"gwas": 3.0, "single-cell": 2.0}
    first = gems.pick(items, 10, gems.empty_progress(), weights, TODAY, seed=7)
    assert len(first) == 10 and len({it["id"] for it in first}) == 10
    assert sum(1 for it in first if gems.relevance(it, weights) > 0) >= 3          # your field first
    assert all(it["level"] == 1 for it in first)                                  # level 1 unlocks easy items only
    prog = gems.empty_progress()
    wrong = first[0]
    prog["items"][wrong["id"]] = {"box": 0, "right": 0, "wrong": 1, "due": TODAY, "seen": "2026-10-26"}
    again = gems.pick(items, 10, prog, weights, TODAY, seed=8)
    assert wrong["id"] in {it["id"] for it in again}                               # what you got wrong comes back
    assert gems.pick(items, 10, gems.empty_progress(), weights, TODAY, seed=7) == first   # a seed picks alike


def test_record_scores_levels_and_spaced_repetition():
    answers = [{"id": "yr-01", "right": True, "level": 1, "terms": ["python"]},
               {"id": "yr-11", "right": False, "level": 1, "terms": ["gwas"]}]
    prog, s = gems.record(None, "first", answers, 61.4, TODAY)
    assert s["points"] == 10 and s["stars"] == 0 and s["accuracy"] == 0.5 and s["new_best"]
    assert prog["items"]["yr-01"]["box"] == 1 and prog["items"]["yr-01"]["due"] == "2026-10-29"
    assert prog["items"]["yr-11"]["box"] == 0 and prog["items"]["yr-11"]["due"] == "2026-10-28"
    assert prog["topics"]["gwas"]["wrong"] == 1 and prog["games"]["first"]["seconds"] == 61
    for _ in range(20):                                       # play on: the game levels up, and so do you
        prog, s = gems.record(prog, "first", [dict(a, right=True) for a in answers], 30, TODAY)
    assert s["level"] > 1 and gems.level_of(prog["games"]["first"]["xp"]) == s["level"]
    assert gems.badge_counts(prog) == {"player": 21, "sharp": 41, "levelup": s["level"] - 1}
    assert gems.max_item_level(1) == 1 and gems.max_item_level(3) == 2 and gems.max_item_level(6) == 3


def test_the_model_learns_from_right_answers_and_playing_time():
    ans = [{"id": "a", "right": True, "level": 1, "terms": ["gwas", "statistics"]},
           {"id": "b", "right": False, "level": 1, "terms": ["single-cell"]}]
    short, long = gems.model_terms(ans, 30), gems.model_terms(ans, 600)
    assert set(short) == {"gwas", "statistics", "single-cell"}
    assert long["single-cell"] > short["single-cell"]                              # ten minutes say more than one
    assert short["single-cell"] > short["gwas"]                                    # a whole wrong item vs half a right one
    prog = gems.empty_progress()
    for _ in range(4):
        prog, _ = gems.record(prog, "hunter", [{"id": "x", "right": True, "level": 1, "terms": ["gwas"]},
                                                {"id": "y", "right": False, "level": 1, "terms": ["single-cell"]}], 20, TODAY)
    assert gems.mastery(prog) == {"knows": ["gwas"], "learning": ["single-cell"]}


def test_the_interest_log_takes_play_rounds(monkeypatch, tmp_path):
    from mygeeky import interests
    from mygeeky.config import MyGeekyConfig
    interests.record_terms("play", {"gwas": 0.5, "statistics": 0.2}, source="game:first", cfg=MyGeekyConfig())
    ev = interests.load_events()[-1]
    assert ev["kind"] == "play" and ev["terms"] == {"gwas": 0.5, "statistics": 0.2}
    assert interests.KIND_WEIGHTS["play"] > 0


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+")
def test_the_phone_answers_the_same():
    years = gems.items_of(PACK, "year")
    weights = {"gwas": 3.0, "single-cell": 2.0, "python": 1.0}
    prog = gems.empty_progress()
    prog["items"]["yr-03"] = {"box": 0, "right": 0, "wrong": 1, "due": TODAY, "seen": "2026-10-20"}
    answers = [{"id": "yr-01", "right": True, "level": 2, "terms": ["python", "programming"]},
               {"id": "yr-11", "right": False, "level": 1, "terms": ["gwas"]},
               {"id": "yr-12", "right": True, "level": 3, "terms": ["sequencing"]}]
    bad = copy.deepcopy(PACK)
    bad["items"][2]["level"] = 7
    bad["items"][5]["terms"] = ["GWAS"]
    py = {
        "valid": gems.validate(PACK), "bad": gems.validate(bad),
        "picks": [[it["id"] for it in gems.pick(years, n, prog, weights, TODAY, seed, lv)]
                  for n, seed, lv in ((10, 1, 1), (6, 99, 4), (12, 12345, 7))],
        "dice": [round(gems.Dice(42).next(), 12) for _ in range(1)], "seed": gems.seed_of("2026-10-27:hunter ünï"),
        "record": gems.record(copy.deepcopy(prog), "first", answers, 95.5, TODAY, bonus=7),
        "terms": gems.model_terms(answers, 333), "levels": [gems.level_of(x) for x in (0, 149, 150, 449, 450, 99999)],
        "player": [gems.player_level(x) for x in (0, 299, 300, 900, 5000)],
    }
    prog2, _ = py["record"]
    py["mastery"], py["badges"], py["summary"] = gems.mastery(prog2, 1), gems.badge_counts(prog2), gems.summary_of(prog2)
    said = phone.run("""
import * as G from './lib/gems.ts';
const { pack, bad, years, prog, answers, weights, today } = INPUT;
const rec = G.record(structuredClone(prog), 'first', answers, 95.5, today, 7);
out({
  valid: G.validate(pack), bad: G.validate(bad),
  picks: [[10, 1, 1], [6, 99, 4], [12, 12345, 7]].map(([n, s, l]) => G.pick(years, n, prog, weights, today, s, l).map((it) => it.id)),
  dice: [Math.round(new G.Dice(42).next() * 1e12) / 1e12], seed: G.seedOf('2026-10-27:hunter ünï'),
  record: rec, terms: G.modelTerms(answers, 333), levels: [0, 149, 150, 449, 450, 99999].map((x) => G.levelOf(x)),
  player: [0, 299, 300, 900, 5000].map((x) => G.playerLevel(x)),
  mastery: G.mastery(rec[0], 1), badges: G.badgeCounts(rec[0]), summary: G.summaryOf(rec[0]),
});
""", {"pack": PACK, "bad": bad, "years": years, "prog": prog, "answers": answers, "weights": weights, "today": TODAY}, name="gems")
    py = json.loads(json.dumps(py))
    for key in py:
        assert said[key] == py[key], key
