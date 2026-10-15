"""The maker's quiz writer: the rules in code, the quote check, running code, redoing sums, and the spot check."""

import json
from pathlib import Path

import pytest

from mygeeky import quiz, quizwriter, safety

PAGE = ("There are three interrelated rules that make a dataset tidy: each variable is a column. "
        "Each observation is a row; each row is an observation. Values are cells.")


def _raw(**kw):
    row = {"q": "In tidy data, what does one row hold?",
           "options": ["One observation", "One variable", "One treatment group", "One whole table"],
           "answer": 0, "why": "Rows are observations: one measured thing per row.", "level": "easy",
           "kind": "choice", "quote": "Each observation is a row; each row is an observation.", "code": ""}
    row.update(kw)
    return row


STEP = {"id": "deeper", "title": "A tidy table, not a tidy-looking one", "role": "deeper", "skill": "R"}
SOURCE = {"title": "R for Data Science", "url": "https://r4ds.hadley.nz/data-tidy", "kind": "book"}


# --------------------------------------------------------------------------- the plain rules
def test_four_fair_options_are_required():
    assert quizwriter.rules_ok(_raw()) == ""
    assert "4 different options" in quizwriter.rules_ok(_raw(options=["a", "b", "c"]))
    assert "4 different options" in quizwriter.rules_ok(_raw(options=["same", "same", "b", "c"]))
    assert "answer" in quizwriter.rules_ok(_raw(answer=7))


def test_trick_wording_and_all_of_the_above_are_refused():
    assert "trick" in quizwriter.rules_ok(_raw(q="Which of these is NOT a tidy table?"))
    assert "trick" in quizwriter.rules_ok(_raw(options=["All of the above", "b option", "c option", "d option"]))
    assert "trick" in quizwriter.rules_ok(_raw(q="Every rule holds, except which one?"))


def test_the_right_answer_must_not_stand_out_by_length():
    long_one = "a very long and unusually detailed answer that is clearly the one the writer cared about"
    assert "lengths" in quizwriter.rules_ok(_raw(options=[long_one, "no", "yes", "maybe"]))


def test_numbers_are_allowed_as_short_options():
    row = _raw(kind="code", code="print(6)", options=["6", "5", "12", "0"], answer=0)
    assert quizwriter.rules_ok(row) == ""


def test_a_question_must_say_why_and_carry_a_level_and_kind():
    assert "why" in quizwriter.rules_ok(_raw(why=""))
    assert "level" in quizwriter.rules_ok(_raw(level="easyish"))
    assert "kind" in quizwriter.rules_ok(_raw(kind="guesswork"))
    assert "no code" in quizwriter.rules_ok(_raw(kind="code", code=""))


# --------------------------------------------------------------------------- the quote has to be real
def test_the_quote_must_be_on_the_page_whatever_the_spacing():
    assert quizwriter.quoted("Each observation is a row; each row is an observation.", PAGE)
    assert quizwriter.quoted("each   observation is a row  each row is an observation", PAGE)
    assert not quizwriter.quoted("Each observation is a column.", PAGE)
    assert not quizwriter.quoted("short", PAGE)             # too short to mean anything


def test_a_question_whose_quote_is_not_on_the_page_is_dropped():
    out = quizwriter.check_question(_raw(quote="Something the page never said about tables."), SOURCE, PAGE, STEP)
    assert not out.passed and "quote" in out.reason


def test_a_near_duplicate_of_what_is_already_there_is_dropped():
    out = quizwriter.check_question(_raw(), SOURCE, PAGE, STEP,
                                    others=["In tidy data, what does one row hold?"])
    assert not out.passed and "almost the same" in out.reason


def test_a_question_that_passes_everything_comes_back_with_its_checks():
    out = quizwriter.check_question(_raw(), SOURCE, PAGE, STEP)
    assert out.passed and out.reason == ""
    assert any("quotes" in text for _ok, text in out.checks)


# --------------------------------------------------------------------------- code is actually run
def test_code_questions_are_run_and_a_wrong_answer_is_caught():
    ok, _note = quizwriter.code_check({"code": "print(2 + 2)", "options": ["4", "5", "22", "0"], "answer": 0})
    assert ok is True
    ok, note = quizwriter.code_check({"code": "print(2 + 2)", "options": ["5", "4", "22", "0"], "answer": 0})
    assert ok is False and "printed" in note


def test_code_that_will_not_run_is_not_counted_against_it():
    ok, note = quizwriter.code_check({"code": "this is not python at all(", "options": ["a", "b", "c", "d"],
                                      "answer": 0})
    assert ok is None and note


def test_a_code_question_whose_code_lies_is_dropped():
    row = _raw(kind="code", code="print(5)", options=["4", "5", "6", "7"], answer=0, quote="")
    out = quizwriter.check_question(row, SOURCE, PAGE, STEP)
    assert not out.passed and "code" in out.reason


def test_a_code_question_needs_no_quote():
    row = _raw(kind="code", code="print(4)", options=["4", "5", "6", "7"], answer=0, quote="")
    assert quizwriter.check_question(row, SOURCE, PAGE, STEP).passed


# --------------------------------------------------------------------------- nothing from a bench
def test_a_question_about_bench_work_is_refused_outright():
    row = _raw(q="How long do you incubate the membrane in blocking buffer?",
               options=["One hour", "Five minutes", "Overnight", "Ten seconds"], quote="")
    assert quizwriter.rules_ok(row)                       # the rules alone already refuse it
    out = quizwriter.check_question(row, SOURCE, PAGE, STEP)
    assert not out.passed


def test_a_bench_source_gives_no_questions_at_all():
    proto = {"id": "p1", "skill": "R", "goal": "", "stages": [
        {"id": "basics", "title": "Basics", "role": "basics",
         "items": [{"title": "A protocol", "url": "https://www.protocols.io/view/x", "kind": "website"},
                   {"title": "Bio-protocol", "url": "https://bio-protocol.org/e1", "kind": "website"}]}]}
    out = quizwriter.write_for(proto, key="sk-test")
    assert out["questions"] == [] and out["asked"] == 0


# --------------------------------------------------------------------------- the blind second read
def _blind(pick_right: bool, sound: bool = True):
    """A fake blind read: it finds the option it believes in by reading the shuffled list, as a reader would."""
    def post(url, json=None, timeout=None, headers=None):
        lines = [ln for ln in json["messages"][1]["content"].splitlines() if ln.startswith("[")]
        right = next(i for i, ln in enumerate(lines) if "One observation" in ln)
        said = {"answer": right if pick_right else (right + 1) % 4, "one_right": sound, "clear": sound,
                "confidence": 0.9}

        class Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            @staticmethod
            def json():
                import json as _json
                return {"choices": [{"message": {"content": _json.dumps(said)}}]}
        return Resp()
    return post


def test_a_blind_second_read_that_disagrees_drops_the_question():
    """The second read gets the options shuffled, so it answers by its own reading, not by position."""
    out = quizwriter.check_question(_raw(), SOURCE, PAGE, STEP, key="sk-test", post=_blind(False))
    assert not out.passed and "blind" in out.reason


def test_a_blind_second_read_that_agrees_twice_keeps_it():
    out = quizwriter.check_question(_raw(), SOURCE, PAGE, STEP, key="sk-test", post=_blind(True))
    assert out.passed and not out.needs_eyes


def test_a_question_the_second_read_calls_unclear_is_dropped():
    """It picks the right answer both times, but calls the question ambiguous: that is enough."""
    out = quizwriter.check_question(_raw(), SOURCE, PAGE, STEP, key="sk-test", post=_blind(True, sound=False))
    assert not out.passed and "unclear" in out.reason


def test_the_spot_check_puts_the_doubtful_ones_first():
    rows = [{"id": f"p.{i}", "needs_eyes": i == 3} for i in range(10)]
    picked = quizwriter.spot_check(rows)
    assert picked[0] == "p.3" and len(picked) == quizwriter.SPOT_CHECK


# --------------------------------------------------------------------------- what myGeeKy leaves alone
def test_bench_work_is_refused_and_analysis_is_welcome():
    """myGeeKy teaches analysis. Anything done at a bench is refused, whatever it is."""
    for name, goal in (("qPCR", "gene expression"), ("PCR", ""), ("Cell culture", "keeping a line healthy"),
                       ("Western blot", "quantifying bands"), ("R", "a western blot protocol")):
        ok, why = safety.allowed(name, goal)
        assert not ok, f"{name} {goal} should be refused"
        assert "computer" in why and "laboratory protocols" in why
    for name, goal in (("R", "data analysis"), ("Python", "machine learning"), ("Statistics basics", ""),
                       ("Image quantification", "measuring images you already have"),
                       ("Git", "working with others"), ("R", "your first analysis of your own data")):
        assert safety.allowed(name, goal)[0], f"{name} {goal} should be allowed"


def test_a_skill_marked_as_bench_work_is_refused_even_if_it_came_back():
    ok, why = safety.allowed("Something nobody has written down", "", lab=True)
    assert not ok and "computer" in why


def test_work_that_needs_containment_or_approvals_is_refused_whatever_the_skill():
    assert not safety.allowed("Python", "work at biosafety level 3")[0]
    assert not safety.allowed("R", "a human challenge trial")[0]
    assert safety.blocked("a protocol for a select agent")
    assert safety.blocked("increase the transmissibility of the strain")
    assert safety.blocked("") == ""


def test_the_rules_are_in_the_prompt_the_writer_sends():
    prompt = quizwriter.WRITE_SYSTEM.format(n=3, rules=safety.prompt_rules())
    assert "laboratory bench" in prompt and "write nothing at all" in prompt
    assert "NOT or EXCEPT" in quizwriter.WRITE_SYSTEM


def test_a_blocked_skill_gets_no_questions_written():
    out = quizwriter.write_for({"id": "p1", "skill": "PCR", "goal": "gene expression", "stages": []},
                               key="sk-test")
    assert out["questions"] == [] and out["dropped"]


def test_the_sites_that_publish_bench_protocols_are_refused():
    for url in ("https://www.protocols.io/view/x", "https://bio-protocol.org/e123",
                "https://openwetware.org/wiki/PCR", "https://www.neb.com/protocols/x",
                "https://www.jove.com/v/123", "https://www.thermofisher.com/x"):
        assert safety.blocked_source(url), url
    assert safety.blocked_source("https://doi.org/10.1/x", "https://openalex.org/S4210212477")   # STAR Protocols
    for url in ("https://r4ds.hadley.nz/", "https://github.com/x/y", "https://imagej.net/software/fiji/"):
        assert not safety.blocked_source(url), url


# --------------------------------------------------------------------------- the bank file
def test_accepted_questions_are_written_to_the_bank_and_flagged_ones_can_be_retired(tmp_path):
    path = tmp_path / "questions.json"
    rows = [{**quiz.clean_question({"id": "p1.basics.01", "protocol": "p1", "stage": "basics", "level": "easy",
                                    "kind": "choice", "q": "A question?",
                                    "options": ["right one", "second one", "third one", "fourth one"], "answer": 0,
                                    "why": "because", "source": {"title": "s", "url": "https://example.org/a",
                                                                 "kind": "website", "quote": "a quoted sentence here"}}),
             "needs_eyes": True}]
    out = quizwriter.add_to_bank(rows, path)
    assert out == {"added": 1, "total": 1}
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert "needs_eyes" not in saved["questions"][0]           # the maker's note doesn't ship
    assert quizwriter.add_to_bank(rows, path)["added"] == 0    # the same id twice is kept once
    assert quizwriter.retire(["p1.basics.01"], path) == 1
    assert json.loads(path.read_text(encoding="utf-8"))["questions"] == []


def test_the_bank_is_balanced_towards_the_mix():
    rows = [{"id": f"p.{lv}.{i}", "level": lv} for lv in quiz.LEVELS for i in range(40)]
    kept = quizwriter.balance(rows, want=20)
    mix = {lv: sum(1 for q in kept if q["level"] == lv) for lv in quiz.LEVELS}
    assert mix["easy"] == 10 and mix["medium"] == 7 and mix["tricky"] == 3


def test_a_batch_summary_and_its_reasons_read_plainly():
    batch = {"questions": [{"id": "a", "level": "easy"}, {"id": "b", "level": "tricky"}],
             "dropped": [("the quote isn't on the source page", "q1"), ("the quote isn't on the source page", "q2"),
                         ("trick wording", "q3")]}
    assert "2 kept" in quizwriter.summary(batch) and "1 easy" in quizwriter.summary(batch)
    assert quizwriter.reasons(batch)[0] == ("the quote isn't on the source page", 2)


def test_the_writer_never_sees_the_real_key(monkeypatch):
    """The key lives in the keyring; a test must never read it (conftest already blanks it)."""
    from mygeeky import scout
    assert scout.get_key() is None
