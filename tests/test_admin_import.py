"""Admin → bring your own answer: a pasted answer goes through the same checks as DeepSeek's, into the same queue."""

import json
from datetime import date

from mygeeky import admin_import, highlights, quizwriter, scout
from tests.test_highlights import BODY, WORK, _Resp
from tests.test_paste_and_country import FOUND, LINK, PAGE


def test_the_json_is_found_however_it_was_pasted():
    want = {"a": [1, 2]}
    for pasted in ('{"a": [1, 2]}', 'Sure! Here it is:\n```json\n{"a": [1, 2]}\n```\nHope it helps.',
                   'Here: {"a": [1, 2]} -- done.'):
        assert admin_import.extract_json(pasted) == want, pasted
    for bad in ("", "no json here at all"):
        try:
            admin_import.extract_json(bad)
            raise AssertionError(bad)
        except ValueError:
            pass


def test_every_kind_has_a_prompt_to_copy_and_a_shape():
    assert "Use only what FACTS and TEXT say" in admin_import.prompt("highlight")
    assert "deadline_quote" in admin_import.prompt("jobs") and "TEXT:" in admin_import.prompt("funding")
    assert '"quote"' in admin_import.prompt("quiz")
    for kind in admin_import.KINDS:
        json.loads(admin_import.shape(kind))
        assert kind in admin_import.NEEDS


def test_pasted_listings_are_checked_against_the_page_and_queued_like_the_scouts():
    out = admin_import.import_answer("jobs", "```json\n" + json.dumps(FOUND) + "\n```", LINK, PAGE,
                                     today=date(2026, 10, 15))
    assert out == {"added": 1, "dropped": 0, "why": [], "found": 1}
    c = list(scout.load()["candidates"].values())[0]
    assert c["status"] == "new" and c["from"] == "imported" and all(ok for ok, _ in c["checks"])
    invented = {"listings": [dict(FOUND["listings"][0], title="A job that is not on the page at all")]}
    scout.save({"candidates": {}, "rejected": [], "sources": scout.SOURCES, "focus": scout.DEFAULT_FOCUS})
    admin_import.import_answer("jobs", json.dumps(invented), LINK, PAGE, today=date(2026, 10, 15))
    bad = list(scout.load()["candidates"].values())
    assert not bad or not all(ok for ok, _ in bad[0]["checks"])          # the same ✗ a DeepSeek answer would get
    assert "link" in admin_import.import_answer("jobs", json.dumps(FOUND), "", PAGE)["error"]
    assert "text" in admin_import.import_answer("jobs", json.dumps(FOUND), LINK, "short")["error"]


def test_a_pasted_highlight_gets_its_facts_from_openalex_and_its_checks(monkeypatch, tmp_path):
    monkeypatch.setattr(highlights, "STATE_FILE", tmp_path / "highlights.json")

    class Session:
        def get(self, url, **_kw):
            return _Resp(WORK)

    story = {"doi": "10.1038/s41586-020-2308-7", "title": "Some genes can't be broken", "hook": "A big catalogue.",
             "body": BODY[:3] + [BODY[3] + " About 42% more were found."], "tool_names": ["Seurat"],
             "skills": ["gwas"], "keywords": ["genetics"],
             "translations": {"fr": {"title": "Titre", "hook": "Accroche", "body": ["Un", "Deux", "Trois", "Quatre"]},
                              "xx": {"title": "nope", "body": ["x"]}}}
    out = admin_import.import_answer("highlight", json.dumps(story), session=Session())
    assert out["added"] == 1 and out["why"] == []
    d = highlights.drafts("new")[0]
    assert d["from"] == "imported" and d["item"]["meta"]["lead"] == "Ada Lovelace"       # the facts are OpenAlex's
    assert d["item"]["coverage"] == "abstract" and set(d["item"]["translations"]) == {"fr"}
    assert any("42%" in w for w in d["warnings"]) and any("Seurat" in w for w in d["warnings"])
    no_doi = admin_import.import_answer("highlight", json.dumps({**story, "doi": ""}), session=Session())
    assert no_doi["added"] == 0 and "no DOI" in no_doi["why"][0]


SOURCE_TEXT = ("R is a language for statistics. " * 20 + "The function mean() returns the average of a vector. "
               + "Use library() to load a package. " * 10)
PROTO = {"id": "r-basics", "skill": "R", "goal": "", "stages": [
    {"id": "basics", "title": "R basics", "role": "basics",
     "items": [{"title": "An R intro", "url": "https://example.org/r-intro", "kind": "tutorial"}]}]}
Q = {"q": "What does mean() return?", "options": ["The average of a vector", "The largest value", "The sum of a vector",
                                                  "The number of values"],
     "answer": 0, "why": "mean() averages.", "quote": "The function mean() returns the average of a vector.",
     "level": "easy", "kind": "choice", "code": ""}


def test_pasted_quiz_questions_must_quote_their_source_and_wait_for_the_maker(monkeypatch):
    monkeypatch.setattr("mygeeky.protocols.reviewed", lambda data=None: [PROTO])
    monkeypatch.setattr(quizwriter, "_page_text", lambda url, session=None: SOURCE_TEXT)
    made_up = dict(Q, q="Which package is fastest?", quote="data.table is the fastest package.")
    out = admin_import.import_answer("quiz", json.dumps({"questions": [Q, made_up]}), pid="r-basics",
                                     link="https://example.org/r-intro")
    assert out["added"] == 1 and out["dropped"] == 1 and "quote" in out["why"][0]
    batch = quizwriter.load()["batches"]["r-basics"]
    assert batch["verdict"] == "" and batch["questions"][0]["needs_eyes"] is True     # no blind second read
    again = admin_import.import_answer("quiz", json.dumps([dict(Q, q="What is the average of a vector called?")]),
                                       pid="r-basics", link="https://example.org/r-intro")
    assert again["added"] == 1 and len(quizwriter.load()["batches"]["r-basics"]["questions"]) == 2   # added on
    assert "source" in admin_import.import_answer("quiz", json.dumps([Q]), pid="r-basics",
                                                  link="https://elsewhere.org")["error"]
    assert "protocol" in admin_import.import_answer("quiz", json.dumps([Q]), pid="nope", link="x")["error"]
