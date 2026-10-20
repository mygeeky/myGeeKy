"""Starting myGeeKy from keywords alone -- no GitHub, no ORCID, no account anywhere.

The three things that could quietly go wrong, and so are held here:

  * THE ROUNDS FUNNEL. If every suggestion comes from the last pick's own neighbourhood, one tap on "16s"
    leaves somebody looking at amplicon sequencing forever. Three near and two far is the fix, and "far"
    has to really be far.
  * THE BAR BECOMES A GATE. Nothing here may stop anyone starting. The bar says what would sharpen the
    profile; it never withholds the app.
  * THE NUDGE BECOMES A TRIAL. Four asks over three months, then silence -- and never, at any point, less
    app than before. If it ever took something away it would be a trial, and "yours, on your computer"
    would stop being true.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from mygeeky import fieldstart as fs
from mygeeky import keywords
from mygeeky.config import MyGeekyConfig, profile_ready


# --------------------------------------------------------------------------- the opening question
def test_the_first_five_are_hubs_far_apart():
    chips = fs.opening()
    assert len(chips) == fs.PER_ROUND
    topics = [c["topic"] for c in chips]
    assert len(set(topics)) == len(topics)
    for i, a in enumerate(topics):                 # no chip is a neighbour of another: five worlds, not one
        for b in topics[i + 1:]:
            assert b not in fs._neighbours(a), f"{a} and {b} are the same corner of the field"


def test_the_first_five_are_the_same_five_every_time():
    """A picker that reshuffled on every repaint would be unusable, and untestable."""
    assert [c["topic"] for c in fs.opening()] == [c["topic"] for c in fs.opening()]


def test_every_chip_says_what_it_covers():
    """Nobody can say whether "16s" is them; everybody can say whether "microbiome, dada2" is."""
    said = [c for c in fs.opening() if c["means"]]
    assert len(said) >= fs.PER_ROUND - 1          # a hub with no relations at all is possible, but rare


# --------------------------------------------------------------------------- near and far
def test_a_round_is_three_near_and_two_far():
    chips = fs.suggest(["machine-learning"])
    assert len(chips) == fs.PER_ROUND
    near_pool = fs._neighbours("machine-learning")
    near = [c["topic"] for c in chips if c["topic"] in near_pool]
    far = [c["topic"] for c in chips if c["topic"] not in near_pool]
    assert len(near) == fs.NEAR and len(far) == fs.FAR


def test_the_far_chips_really_are_far():
    """The whole point: one wrong first tap must stay recoverable."""
    picked = ["machine-learning", "deep-learning"]
    around = set(picked) | {r for t in picked for r in fs._neighbours(t)}
    for chip in fs.suggest(picked):
        if chip["topic"] in around:
            continue                                # that one is a near suggestion, by design
        assert not (fs._neighbours(chip["topic"]) & around), f"{chip['topic']} is not actually far away"


def test_waving_a_chip_away_rules_out_its_whole_neighbourhood():
    offered = {c["topic"] for c in fs.suggest(["bioinformatics"], dismissed=["react"])}
    assert "react" not in offered
    assert not (offered & fs._neighbours("react")), "dismissing react still offered its neighbours"


def test_a_round_never_repeats_what_was_already_shown():
    picked, shown = [], []
    for _ in range(5):
        chips = fs.suggest(picked, shown=shown)
        topics = [c["topic"] for c in chips]
        assert not (set(topics) & set(shown)), "a round offered something already seen"
        shown += topics
        picked.append(topics[0])
    assert len(shown) == len(set(shown))


# --------------------------------------------------------------------------- spread, not count
def test_six_keywords_from_one_corner_are_not_enough():
    one_corner = ["machine-learning", "deep-learning", "pytorch", "tensorflow", "computer-vision", "ai"]
    assert fs.areas(one_corner) == 1
    assert not fs.ready(one_corner)["ok"], "six words from one corner read as a whole field"


def test_six_keywords_across_three_areas_are_enough():
    spread = ["metagenomics", "economics", "robotics", "microbiome", "finance", "ros"]
    assert fs.areas(spread) >= fs.ENOUGH_AREAS
    assert fs.ready(spread)["ok"]


def test_the_bar_fills_towards_ten_without_requiring_it():
    state = fs.ready(["metagenomics", "economics", "robotics", "microbiome", "finance", "ros"])
    assert state["ok"] and state["bar"] < 1.0, "ready at six, and honest that ten would be better"
    assert state["goal"] == fs.GOAL


def test_the_picks_become_far_more_than_themselves():
    """Six picks that rank against thirty-odd phrases is the whole reason the dictionary is used."""
    picked = ["metagenomics", "economics", "robotics"]
    assert fs.ready(picked)["terms"] > len(picked) * 3


def test_nothing_is_ever_a_gate():
    """`ready` reports; it must not be the thing that lets somebody in."""
    cfg = MyGeekyConfig()
    fs.keep(cfg, ["metagenomics"])                 # one keyword: nowhere near "ready"
    assert not fs.ready(cfg.keywords)["ok"]
    assert profile_ready(cfg), "one keyword is a real profile, however thin"


# --------------------------------------------------------------------------- words we do not know
def test_a_word_we_know_comes_back_as_itself():
    offer = fs.offer_for("deep learning")
    assert offer["known"] and offer["keep"] == "deep learning"


def test_a_word_we_do_not_know_is_still_kept():
    """An unknown keyword ranks on itself (keywords.expand), so it is a thinner match, never a refusal."""
    offer = fs.offer_for("marker assisted selection")
    assert not offer["known"]
    assert offer["keep"] == "marker assisted selection"
    assert "still counts" in offer["note"]
    assert keywords.expand([offer["keep"]])        # it really does reach the ranking


def test_a_near_miss_is_offered_the_thing_we_do_know():
    assert "metagenomics" in [a["topic"] for a in fs.alternatives("metagenomic")]


def test_a_wrong_alternative_is_worse_than_none():
    """A loose match once offered "image classification" for "marker assisted selection". A wrong chip
    gets picked, and then everything is ranked against it."""
    assert fs.alternatives("marker assisted selection") == []


def test_asking_openalex_never_raises(monkeypatch):
    monkeypatch.setattr("mygeeky.wisep.get", lambda *a, **k: (_ for _ in ()).throw(OSError("no network")))
    assert fs.topics_like("wheat breeding") == []
    assert fs.offer_for("wheat breeding", online=True)["keep"] == "wheat breeding"


def test_openalex_fills_the_gap_our_dictionary_has(monkeypatch):
    """Our 300 terms were built from software topics, so they are thin on the bench. OpenAlex names
    topics the way papers do, which is exactly the missing half."""
    class Said:
        status_code = 200

        @staticmethod
        def json():
            return {"results": [{"display_name": "Genetic Mapping and Diversity in Plants",
                                 "hint": "plant breeding"}]}

    monkeypatch.setattr("mygeeky.wisep.get", lambda *a, **k: Said())
    found = fs.offer_for("marker assisted selection", online=True)["alternatives"]
    assert found and found[0]["from"] == "openalex"
    assert "Genetic Mapping" in found[0]["label"]


# --------------------------------------------------------------------------- keeping the picks
def test_picks_are_merged_never_replaced():
    """Somebody who later signs in with ORCID must not watch the field they described get overwritten."""
    cfg = MyGeekyConfig(keywords=["snakemake"])
    fs.keep(cfg, ["metagenomics", "SNAKEMAKE"])
    assert cfg.keywords == ["snakemake", "metagenomics"], "a duplicate was added, or the old one lost"


def test_keeping_remembers_when_the_keyword_start_happened():
    cfg = MyGeekyConfig()
    fs.keep(cfg, ["metagenomics"])
    assert fs.started(cfg)
    first = fs.started(cfg)
    fs.keep(cfg, ["economics"])
    assert fs.started(cfg) == first, "the clock restarted, which would restart the asking too"


# --------------------------------------------------------------------------- the ask for an account
START = date(2026, 1, 1)


def _begun(asks_done: int = 0) -> MyGeekyConfig:
    cfg = MyGeekyConfig(keywords=["metagenomics"])
    cfg.field_started_at = START.isoformat()
    cfg.account_asks = asks_done
    return cfg


@pytest.mark.parametrize("day, asks_done, expected", [
    (0, 0, False),      # day one: say nothing
    (6, 0, False),
    (7, 0, True),       # the first ask
    (8, 1, False),      # answered: quiet again
    (20, 1, False),
    (21, 1, True),      # the second
    (44, 2, False),
    (45, 2, True),      # the third
    (89, 3, False),
    (90, 3, True),      # the fourth and last
])
def test_the_ask_is_four_times_over_three_months_not_weekly(day, asks_done, expected):
    """Weekly for three months is twelve interruptions about one decision. These are four."""
    said = fs.nudge(_begun(asks_done), today=START + timedelta(days=day))
    assert said["ask"] is expected, said["reason"]


def test_a_profile_that_predates_this_never_gets_asked_at_all():
    """Somebody already running on keywords made their choice before myGeeKy could ask. No start date
    means no asking, rather than a new nag appearing on an old install."""
    old = MyGeekyConfig(keywords=["metagenomics"])
    assert not fs.nudge(old, today=date(2030, 1, 1))["ask"]


def test_after_three_months_it_stops_asking_and_keeps_working():
    cfg = _begun(len(fs.ASK_ON_DAYS))
    far_future = START + timedelta(days=5000)
    said = fs.nudge(cfg, today=far_future)
    assert not said["ask"]
    assert "keeps working" in said["reason"]
    assert profile_ready(cfg), "nothing may be taken away for not having an account"


def test_the_last_ask_is_the_honest_one():
    cfg = _begun(len(fs.ASK_ON_DAYS) - 1)
    said = fs.nudge(cfg, today=START + timedelta(days=fs.ASK_ON_DAYS[-1]))
    assert said["ask"] and said["last"]
    assert "survives a new laptop" in said["why"], "the real cost is backup, so say that and nothing else"


def test_a_wall_explains_itself_once_and_then_never_again():
    cfg = MyGeekyConfig(keywords=["metagenomics"])
    first = fs.nudge(cfg, wall="signals")
    assert first["ask"] and "account" in first["why"]
    fs.asked(cfg, wall="signals")
    assert not fs.nudge(cfg, wall="signals")["ask"]
    assert fs.nudge(cfg, wall="activity")["ask"], "a different wall is a different thing to explain"


def test_every_wall_says_what_still_works_without_an_account():
    for wall in ("signals", "collab", "followback", "activity", "phone"):
        assert fs.nudge(MyGeekyConfig(keywords=["x"]), wall=wall)["why"]


def test_signing_in_ends_the_asking_immediately():
    for cfg in (MyGeekyConfig(github_username="me"), MyGeekyConfig(orcid_id="0000-0002-1825-0097")):
        cfg.field_started_at = "2026-01-01"
        assert not fs.nudge(cfg, today=date(2030, 1, 1))["ask"]
        assert not fs.nudge(cfg, wall="signals")["ask"]


def test_days_left_counts_down_to_silence():
    cfg = _begun()
    assert fs.days_left(cfg, today=START) == fs.ASK_ON_DAYS[-1]
    assert fs.days_left(cfg, today=date(2027, 1, 1)) == 0
    assert fs.days_left(MyGeekyConfig()) is None


# --------------------------------------------------------------------------- what the panel is told
def test_the_summary_says_what_needs_an_account_and_nothing_more():
    cfg = MyGeekyConfig(keywords=["metagenomics", "economics", "robotics"])
    said = fs.summary(cfg)
    assert said["keywords"] and not said["has_account"]
    assert said["asks_left"] == len(fs.ASK_ON_DAYS)
    assert set(said["needs_account"]) == {"signals", "collab", "followback", "activity", "phone"}


# --------------------------------------------------------------------------- found by using it for real
def test_every_offered_chip_is_a_real_dictionary_entry():
    """A term can appear in another term's `related` list without being an entry itself -- only 21% are.
    Offering one of those gave a chip with nothing to judge it by, no neighbourhood to wave away, and
    nothing for `areas` to place it in. Driving the real picker is what caught it."""
    terms = fs._terms()
    for seed in (["machine-learning"], ["bioinformatics"], ["economics"], ["16s"], ["a11y"], ["robotics"]):
        picked, shown = list(seed), []
        for _ in range(6):
            chips = fs.suggest(picked, shown=shown)
            for chip in chips:
                assert chip["topic"] in terms, f"{chip['topic']} is not a dictionary entry"
                assert chip["means"], f"{chip['topic']} has nothing to judge it by"
            shown += [c["topic"] for c in chips]
            picked.append(chips[0]["topic"])


def test_dismissing_any_offered_chip_really_removes_its_area():
    """The consequence of the bug above: a chip with no entry has no neighbours, so waving it away did
    nothing at all. Every chip must be dismissable in the way the button promises."""
    picked = ["machine-learning", "deep-learning"]
    for chip in fs.suggest(picked):
        topic = chip["topic"]
        after = {c["topic"] for c in fs.suggest(picked, dismissed=[topic])}
        assert not (after & (fs._neighbours(topic) | {topic})), f"dismissing {topic} left its area behind"


def test_a_short_word_is_not_matched_on_spelling_alone():
    """"health" scores 0.727 against "wheat" -- they share h, e, a, t. Close enough for a fuzzy match,
    nowhere near close enough to put in somebody's research profile. Found by running `mygeeky init`."""
    assert "health" not in [a["topic"] for a in fs.alternatives("wheat")]
    assert "metagenomics" in [a["topic"] for a in fs.alternatives("metagenomic")],         "tightening it must not break a real near-miss, which shares a whole word"


def test_an_openalex_hint_is_cut_down_to_a_line(monkeypatch):
    """They are whole paragraphs; a chip has one line, and the terminal printed a wall of text."""
    class Said:
        status_code = 200

        @staticmethod
        def json():
            return {"results": [{"display_name": "Wheat and Barley Genetics",
                                 "hint": "This cluster of papers focuses on the genetic diversity, "
                                         "breeding, and genomics of wheat, with an emphasis on disease "
                                         "resistance and yield. It covers many further topics besides."}]}

    monkeypatch.setattr("mygeeky.wisep.get", lambda *a, **k: Said())
    means = fs.topics_like("wheat breeding")[0]["means"]
    assert len(means) <= 111, means
    assert "It covers" not in means, "more than the first sentence survived"


def test_the_terminal_picker_splits_on_commas_not_spaces():
    """"wheat breeding" became the two keywords "wheat" and "breeding", neither of which anybody meant.
    A row of bare numbers is the one case where a space really is a separator."""
    from mygeeky.cli import _pick_field  # noqa: F401 -- the parsing rule is what is under test

    def parts(said: str) -> list[str]:
        chunks = said.split() if all(p.strip("x").isdigit() for p in said.split()) else said.split(",")
        return [p.strip() for p in chunks if p.strip()]

    assert parts("wheat breeding") == ["wheat breeding"]
    assert parts("1 4") == ["1", "4"]
    assert parts("1,4") == ["1", "4"]
    assert parts("x3") == ["x3"]
    assert parts("single cell, wheat breeding") == ["single cell", "wheat breeding"]
