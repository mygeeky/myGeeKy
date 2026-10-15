"""Quizzes: the bank's shape, drawing in the right mix, marking, the daily limit, flags and difficulty."""

import json
from datetime import date
from pathlib import Path

import pytest

from mygeeky import curated, protocols, quiz

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 10, 14)


def _q(qid, protocol="p1", stage="basics", level="easy", kind="choice", answer=0, **kw):
    row = {"id": qid, "protocol": protocol, "stage": stage, "level": level, "kind": kind,
           "q": f"Question {qid}?", "options": ["right one here", "second option", "third option", "fourth option"],
           "answer": answer, "why": "because the source says so",
           "source": {"title": "A source", "url": "https://example.org/a", "kind": "website",
                      "quote": "the sentence that proves it"}}
    row.update(kw)
    return row


def _bank(rows):
    return quiz.clean_bank({"version": "2026-10-14T00:00:00Z", "questions": rows})


def _proto(pid="p1", stages=("basics", "deeper")):
    return {"id": pid, "title": "A protocol", "skill": "R", "based_on": "",
            "stages": [{"id": s, "title": s.title()} for s in stages]}


# --------------------------------------------------------------------------- shape
def test_a_question_needs_four_different_options_and_a_real_answer():
    assert quiz.clean_question(_q("a.b.01")) is not None
    assert quiz.clean_question(_q("a.b.02", options=["one", "two", "three"])) is None       # only three
    assert quiz.clean_question(_q("a.b.03", options=["same", "same", "b", "c"])) is None    # a repeat
    assert quiz.clean_question(_q("a.b.04", answer=9)) is None                              # no such option
    assert quiz.clean_question(_q("BAD ID")) is None
    assert quiz.clean_question({"id": "a.b.05"}) is None


def test_a_level_or_kind_it_does_not_know_falls_back():
    q = quiz.clean_question(_q("a.b.06", level="impossible", kind="telepathy"))
    assert q["level"] == "easy" and q["kind"] == "choice"


def test_the_bank_drops_repeats_and_keeps_the_first():
    bank = _bank([_q("a.b.01"), _q("a.b.01", q="A different question?"), _q("a.b.02")])
    assert [q["id"] for q in bank["questions"]] == ["a.b.01", "a.b.02"]
    assert bank["questions"][0]["q"] == "Question a.b.01?"


def test_problems_names_what_is_missing():
    rows = [_q("a.b.01", protocol=""), _q("a.b.02", source={"title": "", "url": "", "kind": "website", "quote": ""}),
            _q("a.b.03", why="")]
    found = " ".join(quiz.problems({"questions": rows}))
    assert "no protocol" in found and "no source" in found and "why" in found


def test_a_question_the_computer_checks_needs_no_quote():
    """Code that is run, and sums that are redone, prove themselves; everything else must quote its source."""
    code = _q("a.b.01", kind="code", code="print(6)", source={"title": "s", "url": "https://example.org/a",
                                                              "kind": "website", "quote": ""})
    choice = _q("a.b.02", source={"title": "s", "url": "https://example.org/a", "kind": "website", "quote": ""})
    assert quiz.problems({"questions": [code]}) == []
    assert any("quoted" in p for p in quiz.problems({"questions": [choice]}))


# --------------------------------------------------------------------------- drawing
def test_a_quiz_is_drawn_in_the_mix_with_the_options_shuffled():
    import random
    rows = []
    for lv in quiz.LEVELS:
        rows += [_q(f"p1.{lv}.{i:02d}", level=lv) for i in range(20)]
    q = quiz.Quiz.draw(_proto(), _bank(rows), n=10, rng=random.Random(1))
    assert len(q.questions) == 10
    mix = {lv: sum(1 for x in q.questions if x.level == lv) for lv in quiz.LEVELS}
    assert mix == {"easy": 5, "medium": 4, "tricky": 1}        # 50% / 35% / 15%, always adding up to 10
    assert quiz.share(20) == {"easy": 10, "medium": 7, "tricky": 3}
    assert all(sum(quiz.share(k).values()) == k for k in (5, 10, 12, 20))
    # the right answer is not always option A
    shown = {x.answer for x in q.questions}
    assert len(shown) > 1


def test_a_short_bank_still_gives_a_full_quiz():
    import random
    rows = [_q(f"p1.easy.{i:02d}", level="easy") for i in range(8)] + [_q("p1.tricky.01", level="tricky")]
    q = quiz.Quiz.draw(_proto(), _bank(rows), n=10, rng=random.Random(2))
    assert len(q.questions) == 9                      # everything there is, and nothing invented


def test_drawing_leaves_out_what_you_flagged_and_can_stick_to_one_step():
    import random
    rows = [_q(f"p1.basics.{i:02d}", stage="basics") for i in range(4)] + \
           [_q(f"p1.deeper.{i:02d}", stage="deeper") for i in range(4)]
    q = quiz.Quiz.draw(_proto(), _bank(rows), n=10, rng=random.Random(3), stage="deeper")
    assert {x.stage for x in q.questions} == {"deeper"}
    q2 = quiz.Quiz.draw(_proto(), _bank(rows), n=10, rng=random.Random(3), flags=["p1.deeper.00"])
    assert "p1.deeper.00" not in {x.id for x in q2.questions}


def test_a_protocol_you_changed_keeps_the_questions_of_the_one_it_came_from():
    import random
    rows = [_q(f"r-data-analysis.basics.{i:02d}", protocol="r-data-analysis") for i in range(4)]
    mine = {**_proto("r-data-analysis-2"), "based_on": "r-data-analysis"}
    q = quiz.Quiz.draw(mine, _bank(rows), n=10, rng=random.Random(4))
    assert len(q.questions) == 4


def test_a_step_with_its_own_title_shows_it():
    import random
    q = quiz.Quiz.draw(_proto(), _bank([_q("p1.basics.01")]), n=1, rng=random.Random(5))
    assert q.questions[0].stage_title == "Basics"


# --------------------------------------------------------------------------- marking
def _drawn(rows, n=4, seed=7):
    import random
    return quiz.Quiz.draw(_proto(), _bank(rows), n=n, rng=random.Random(seed))


def test_marking_counts_the_right_ones_and_groups_by_step_and_level():
    rows = [_q("p1.basics.01", stage="basics", level="easy"), _q("p1.basics.02", stage="basics", level="medium"),
            _q("p1.deeper.01", stage="deeper", level="tricky"), _q("p1.deeper.02", stage="deeper", level="easy")]
    q = _drawn(rows)
    answers = [x.answer for x in q.questions]
    answers[0] = (answers[0] + 1) % 4                     # get the first one wrong
    attempt = quiz.mark(q, answers)
    assert attempt.right == 3 and attempt.total == 4 and attempt.score == 0.75
    assert attempt.passed and not attempt.perfect and attempt.percent == 75
    assert sum(g["total"] for g in attempt.by_stage) == 4
    assert sum(lv["total"] for lv in attempt.by_level) == 4


def test_an_unanswered_question_is_simply_wrong():
    q = _drawn([_q("p1.basics.01"), _q("p1.basics.02")], n=2)
    attempt = quiz.mark(q, [-1, -1])
    assert attempt.right == 0 and attempt.score == 0.0 and not attempt.passed


def test_the_best_score_is_kept_and_a_worse_one_does_not_replace_it():
    q = _drawn([_q("p1.basics.01"), _q("p1.basics.02")], n=2)
    good = quiz.mark(q, [x.answer for x in q.questions])
    quiz.record(good, TODAY)
    assert quiz.best("p1")["score"] == 1.0
    q2 = _drawn([_q("p1.basics.01"), _q("p1.basics.02")], n=2)
    bad = quiz.mark(q2, [-1, -1], best_before=1.0)
    quiz.record(bad, TODAY)
    assert quiz.best("p1")["score"] == 1.0 and bad.best == 1.0 and not bad.improved


def test_one_attempt_a_day():
    q = _drawn([_q("p1.basics.01")], n=1)
    assert quiz.can_try("p1", TODAY) == (True, "")
    quiz.record(quiz.mark(q, [0]), TODAY)
    ok, why = quiz.can_try("p1", TODAY)
    assert not ok and "today" in why
    assert quiz.can_try("p1", date(2026, 10, 15))[0]


def test_flagging_a_question_and_taking_it_back():
    assert quiz.flag("p1.basics.01") is True
    assert quiz.flags() == ["p1.basics.01"]
    assert quiz.flag("p1.basics.01", False) is False
    assert quiz.flags() == []


def test_reporting_a_question_opens_an_issue_without_your_answers():
    q = _drawn([_q("p1.basics.01")], n=1).questions[0]
    q.picked = 2
    url = quiz.report_question(q, "the answer is out of date")
    assert url.startswith("https://github.com/mygeeky/myGeeKy-ideas/issues/new?")
    assert "p1.basics.01" in url and "out+of+date" in url
    assert "picked" not in url and "answer%3D2" not in url


# --------------------------------------------------------------------------- comparing protocols, for fun
def test_a_harder_protocol_counts_for_more():
    easy = _bank([_q(f"p1.basics.{i:02d}", level="easy") for i in range(10)])
    hard = _bank([_q(f"p2.basics.{i:02d}", protocol="p2", level="tricky") for i in range(5)]
                 + [_q(f"p2.basics.1{i}", protocol="p2", level="easy") for i in range(5)])
    assert quiz.weight_of("p1", None, easy) < quiz.weight_of("p2", None, hard)
    # once people's real scores are in, they decide instead
    assert quiz.weight_of("p1", {"p1": 0.4}, easy) > quiz.weight_of("p1", {"p1": 0.95}, easy)


def test_a_weighted_score_across_protocols_sits_between_them():
    bank = _bank([_q("p1.basics.01"), _q("p2.basics.01", protocol="p2")])
    out = quiz.weighted({"p1": 1.0, "p2": 0.8}, {"p1": 0.9, "p2": 0.4}, bank)
    assert 0.8 < out < 1.0


# --------------------------------------------------------------------------- the shipped bank
def test_the_shipped_bank_is_clean_and_every_question_belongs_to_a_reviewed_protocol():
    data = json.loads((ROOT / "src" / "mygeeky" / "data" / "questions.json").read_text(encoding="utf-8"))
    assert quiz.problems(data) == []
    bank = quiz.clean_bank(data)
    assert bank["questions"], "the shipped bank should not be empty"
    reviewed = {p["id"]: p for p in protocols.reviewed(curated.load())}
    for q in bank["questions"]:
        assert q["protocol"] in reviewed, f"{q['id']} is for a protocol that isn't reviewed"
        steps = {st["id"] for st in reviewed[q["protocol"]]["stages"]}
        assert q["stage"] in steps, f"{q['id']} is for a step {q['stage']} that doesn't exist"
        assert q["source"]["url"], q["id"]


def test_the_phone_bundles_the_same_questions():
    desktop = json.loads((ROOT / "src" / "mygeeky" / "data" / "questions.json").read_text(encoding="utf-8"))
    phone = json.loads((ROOT / "mobile" / "src" / "data" / "questions.json").read_text(encoding="utf-8"))
    assert phone == desktop, "mobile/src/data/questions.json is out of date: copy it from src/mygeeky/data/"


def test_a_question_source_is_a_link_the_panel_will_open():
    """Every source must be a link the app is allowed to open, or the card's button does nothing."""
    from mygeeky.gui import app as logic
    data = quiz.clean_bank(json.loads((ROOT / "src" / "mygeeky" / "data" / "questions.json").read_text(encoding="utf-8")))
    for q in data["questions"]:
        assert q["source"]["url"].startswith("https://"), q["id"]
    assert logic._curated_link("https://github.com/mygeeky/myGeeKy-ideas/issues/new?title=x")


# --------------------------------------------------------------------------- the panel's own numbers
def test_the_level_check_uses_the_bank_and_marks_the_step_known(monkeypatch, tmp_path):
    from mygeeky.config import MyGeekyConfig
    from mygeeky.gui import app as logic
    cfg = MyGeekyConfig(github_username="someone")
    proto = protocols.fill(protocols.template("R", "data analysis"), [], {"resources": []})
    pid = protocols.start(cfg, proto)
    rows = [_q(f"{pid}.basics.{i:02d}", protocol=pid, stage="basics") for i in range(4)]
    monkeypatch.setattr(quiz, "_bank", _bank(rows))
    drawn = logic.quiz_draw(cfg, pid, "basics")
    assert drawn is not None and len(drawn.questions) == 4
    attempt = logic.quiz_mark(cfg, drawn, [x.answer for x in drawn.questions], stage="basics")
    assert attempt.passed
    view = protocols.view(cfg, protocols.mine(cfg)[pid])
    basics = next(st for st in view["stages"] if st["id"] == "basics")
    assert basics["how"] == "quiz" and basics["status"] in ("known", "done")


def test_quiz_state_says_what_there_is_and_whether_you_may_try(monkeypatch):
    from mygeeky.config import MyGeekyConfig
    from mygeeky.gui import app as logic
    cfg = MyGeekyConfig(github_username="someone")
    pid = protocols.start(cfg, protocols.fill(protocols.template("R"), [], {"resources": []}))
    monkeypatch.setattr(quiz, "_bank", _bank([_q(f"{pid}.basics.01", protocol=pid)]))
    st = logic.quiz_state(cfg, pid)
    assert st["counts"]["total"] == 1 and st["can_try"] and st["per_attempt"] == quiz.PER_ATTEMPT


def test_a_404_means_the_questions_are_not_published_yet(monkeypatch, tmp_path):
    """Before the bank is on main, the app must not treat the 404 as an error."""
    class Resp:
        status_code = 404

        def raise_for_status(self):
            raise AssertionError("a 404 must not be raised")

    monkeypatch.setattr(quiz.requests, "get", lambda *a, **k: Resp())
    assert quiz.refresh_if_due(force=True) is False


# --------------------------------------------------------------------------- the answer isn't in plain sight
def test_the_shipped_bank_stores_the_answer_as_a_hash():
    """Opening questions.json must not show which option is right. (Obfuscation, not security: see
    docs/QUIZZES.md -- four options can be hashed and compared by anyone who wants to.)"""
    raw = json.loads((ROOT / "src" / "mygeeky" / "data" / "questions.json").read_text(encoding="utf-8"))
    assert raw["questions"], "the shipped bank should not be empty"
    for q in raw["questions"]:
        assert "answer" not in q, f"{q['id']} still ships the answer's position"
        assert len(q.get("answer_hash", "")) == quiz.ANSWER_CHARS, q["id"]


def test_a_hashed_answer_is_read_back_as_the_right_option():
    q = _q("a.b.01", answer=2)
    hidden = quiz.hide_answer(q)
    assert "answer" not in hidden and hidden["answer_hash"]
    back = quiz.clean_question(hidden)
    assert back["answer"] == 2 and back["options"][2] == q["options"][2]


def test_a_hash_belongs_to_its_own_question_only():
    """The question's id goes into the hash, so the same option in another question looks different."""
    one, two = _q("a.b.01"), _q("a.b.02")
    assert quiz.hide_answer(one)["answer_hash"] != quiz.hide_answer(two)["answer_hash"]
    assert quiz.clean_question({**two, "answer_hash": quiz.hide_answer(one)["answer_hash"],
                                "answer": None}) is None        # a hash from elsewhere matches nothing


def test_an_option_edited_after_it_was_hashed_makes_the_question_unusable():
    hidden = quiz.hide_answer(_q("a.b.01"))
    hidden["options"] = ["something else entirely", *hidden["options"][1:]]
    assert quiz.clean_question(hidden) is None


def test_spacing_and_case_do_not_change_the_hash():
    assert quiz.answer_token("a.b.01", "One observation") == quiz.answer_token("a.b.01", "  one   OBSERVATION ")


def test_a_question_written_but_not_yet_hidden_still_works():
    """The writer keeps the plain position until the maker accepts the batch; both forms are read."""
    assert quiz.clean_question(_q("a.b.01", answer=1))["answer"] == 1


def test_the_phone_hashes_answers_the_same_way():
    ts = (ROOT / "mobile" / "src" / "lib" / "quiz.ts").read_text(encoding="utf-8")
    assert "answerToken" in ts and "answer_hash" in ts
    assert f"ANSWER_CHARS = {quiz.ANSWER_CHARS}" in ts
    assert "u001f" in ts, "the phone must join id and option with the same separator"
