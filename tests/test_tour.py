"""GeeKOc's tours and Help (tour.py, data/tour.json): the data is whole, every tour goes where it says on both apps,
it never opens by itself under tests or CI, and the phone (mobile/src/lib/tour.ts) answers like the desktop."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mygeeky import tour
from tests import phone

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "src" / "mygeeky" / "data"
MOBILE = ROOT / "mobile" / "src" / "data"
LANGS = ("en", "fr", "ar", "zh")


def test_the_phone_has_the_same_tours_and_the_same_moving_geekoc():
    for name in ("tour.json", "geekoc_moves.json"):
        assert (DESK / name).read_bytes() == (MOBILE / name).read_bytes(), f"{name}: copy it to mobile/src/data/"


def test_every_text_is_written_in_all_four_languages():
    d = tour.load()
    assert tuple(d["langs"]) == LANGS
    for key, words in d["ui"].items():
        assert all(words.get(lang) for lang in LANGS), key
    for sid, s in d["stops"].items():
        texts = list(s["by_kind"].values()) if "by_kind" in s else [s["t"]]
        if "by_kind" in s:
            assert set(s["by_kind"]) == set(tour.KINDS), sid
        for words in texts + ([s["phrase"]] if "phrase" in s else []):
            assert all(words.get(lang, "").strip() for lang in LANGS), sid
    for e in d["faq"]:
        assert all(e["q"].get(lang) and e["a"].get(lang) for lang in LANGS)


def test_every_stop_in_a_tour_exists_and_every_pose_can_move():
    d, moves = tour.load(), json.loads((DESK / "geekoc_moves.json").read_text(encoding="utf-8"))["poses"]
    named = [ids for t in d["tours"].values() for ids in (t.values() if isinstance(t, dict) else [t])]
    for ids in named:
        assert all(s in d["stops"] for s in ids), ids
    for sid, s in d["stops"].items():
        assert s["pose"] in moves, sid
        assert set(s.get("at", {})) <= {"desktop", "phone"}, sid
    for name, p in moves.items():
        frames = ["".join(p["parts"][i] for i in f) for f in p["frames"]]
        assert len(frames) >= 6 and len(set(frames)) == len(frames), name        # every frame differs: he moves


def test_every_general_tour_shows_seasons_and_jobs_then_ends_with_more_the_never_list_and_the_motto():
    for k in tour.KINDS:
        for platform in ("desktop", "phone"):
            ids = tour.stops("start", k, platform)
            assert ids[:4] == ["welcome", "home", "seasons", "jobs"], (k, ids)
            assert ids[-3:] == ["more", "never", "end"], (k, ids)
            assert len(ids) <= 12
    assert tour.phrase("end", "en") == "Your geeky friend who helps you grow, quietly."
    assert "Five things I'll never do" in tour.text("never", "en")
    assert "ORCID" in tour.text("more", "en", "github") and "GitHub" in tour.text("more", "en", "orcid")


def test_help_has_a_tour_for_settings_and_for_every_main_but_itself():
    assert set(tour.MAINS) | {"settings", "start"} == set(tour.load()["tours"])
    assert "help" not in tour.MAINS
    assert tour.stops("world", "none", "phone")[-2] == "launches"          # the phone's own page
    assert "launches" not in tour.stops("world", "none", "desktop")         # the desktop has none: skipped
    assert "set_place" not in tour.stops("settings", "none", "phone")       # placing the panel: desktop only


def test_the_kind_follows_what_the_user_gave():
    assert tour.kind(True, True, True) == "both"
    assert tour.kind(True, False, True) == "github"
    assert tour.kind(False, True, False) == "orcid"
    assert tour.kind(False, False, True) == "cv"
    assert tour.kind(False, False, False) == "none"


def test_the_desktop_stops_open_real_pages():
    from mygeeky import navtree
    from mygeeky.gui.qt_panel import panel_tree
    pages = {n["id"] for n in navtree.walk(panel_tree(True, False))}
    for sid in tour.load()["stops"]:
        target = tour.at(sid, "desktop")
        if target.startswith("settings:"):
            assert target.split(":", 1)[1] in tour.SETTINGS_PARTS, sid
        elif target:
            assert target in pages | {"settings"}, (sid, target)


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and mobile/node_modules")
def test_the_phone_stops_open_real_pages():
    pages = set(phone.run("import { phoneTree, walk } from './lib/nav-tree.ts';\n"
                          "out(walk(phoneTree(true, false)).map((n) => n.id));"))
    for sid in tour.load()["stops"]:
        target = tour.at(sid, "phone")
        if target.startswith("settings:"):
            assert target.split(":", 1)[1] in tour.SETTINGS_PARTS, sid
        elif target:
            assert target in pages, (sid, target)


def test_it_never_opens_by_itself_under_tests_or_ci():
    assert tour.blocked()                                     # this very run: pytest sets PYTEST_CURRENT_TEST
    assert tour.blocked({"CI": "true"}) and tour.blocked({"MYGEEKY_NO_TOUR": "1"})
    assert not tour.blocked({}) and not tour.blocked({"CI": "", "MYGEEKY_NO_TOUR": "0"})
    assert tour.auto(0, "github", "desktop") == []            # under pytest: nothing, even the first time


def test_it_opens_whole_the_first_time_and_only_for_new_stops_after_an_update():
    env = {}
    assert tour.auto(0, "orcid", "desktop", env) == tour.stops("start", "orcid", "desktop")
    assert tour.auto(tour.version(), "orcid", "desktop", env) == []
    d = tour.load()
    d["stops"]["cited"]["since"] = tour.version() + 1                        # a stop that arrives in the next one
    d["version"] += 1
    try:
        assert tour.auto(tour.version() - 1, "orcid", "desktop", env) == ["welcome_new", "cited", "end"]
        assert tour.auto(tour.version() - 1, "github", "desktop", env) == []  # not in a GitHub user's tour
    finally:
        tour.load.cache_clear()


def test_a_language_it_does_not_have_falls_back_to_english():
    assert tour.text("home", "de") == tour.text("home", "en")
    assert tour.rtl("ar") and not tour.rtl("fr")
    assert tour.ui("main_tour", "fr", name="Grow") == "Visite de Grow"


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and mobile/node_modules")
def test_the_phone_picks_the_same_tours_and_says_the_same_words():
    cases = [(name, k) for name in tour.load()["tours"] for k in tour.KINDS]
    got = phone.run("""
import * as T from './lib/tour.ts';
const [cases, langs] = INPUT;
out({
  stops: cases.map(([n, k]) => T.stops(n, k)),
  words: cases.map(([n, k]) => langs.map((l) => T.stops(n, k).map((s) => [T.text(s, l, k), T.phrase(s, l), T.at(s)]))),
  auto: [0, 1, 5].map((seen) => ['github', 'none'].map((k) => T.auto(seen, k))),
  kinds: [[1, 1, 0], [1, 0, 1], [0, 1, 0], [0, 0, 1], [0, 0, 0]].map(([g, o, c]) => T.kind(!!g, !!o, !!c)),
  faq: langs.map((l) => T.faq(l)), ui: langs.map((l) => T.ui('main_tour', l, { name: 'Grow' })),
  rtl: langs.map((l) => T.rtl(l)), version: T.version(),
});
""", [cases, list(LANGS) + ["de"]])
    langs = list(LANGS) + ["de"]
    assert got["stops"] == [tour.stops(n, k, "phone") for n, k in cases]
    assert got["words"] == [[[[tour.text(s, lang, k), tour.phrase(s, lang), tour.at(s, "phone")]
                              for s in tour.stops(n, k, "phone")] for lang in langs] for n, k in cases]
    assert got["auto"] == [[tour.auto(seen, k, "phone", {}) for k in ("github", "none")] for seen in (0, 1, 5)]
    assert got["kinds"] == [tour.kind(*map(bool, x)) for x in ([1, 1, 0], [1, 0, 1], [0, 1, 0], [0, 0, 1], [0, 0, 0])]
    assert got["faq"] == [[list(x) for x in tour.faq(lang)] for lang in langs]
    assert got["ui"] == [tour.ui("main_tour", lang, name="Grow") for lang in langs]
    assert got["rtl"] == [tour.rtl(lang) for lang in langs] and got["version"] == tour.version()
