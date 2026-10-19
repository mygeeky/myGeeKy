"""Shared rules the two apps must agree on, run through the phone's real code (tests/phone.py) and the desktop's on
the same inputs: curated-list cleaning and deadlines, your 👍/👎 taste, quiz banks, protocol shapes, token expiry."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

import phone
from mygeeky import curated, protocols, quiz, taste, tokens

pytestmark = pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+")


def norm(x):
    """Both sides' answers as plain JSON (tuples become lists, and so on)."""
    return json.loads(json.dumps(x, default=str))


# --------------------------------------------------------------------------- curated lists
LISTS = {"version": "1", "jobs": [
    {"id": "postdoc-gwas", "title": "Postdoc in statistical genetics", "url": "https://example.org/j1",
     "summary": "Work on GWAS.", "keywords": ["GWAS", "gwas", "Genetics"], "deadline": "2026-11-02",
     "org": "Lund", "place": "Lund, Sweden", "type": "postdoc", "remote": True,
     "translations": {"fr": {"title": "Postdoc", "summary": "Travail"}, "xx": {"summary": "no title"}}},
    {"id": "Bad Id", "title": "x", "url": "https://example.org", "deadline": "2026-11-02"},
    {"id": "no-deadline", "title": "Research engineer", "url": "https://example.org/j2"},
    {"id": "http-link", "title": "Research engineer", "url": "http://example.org/j3", "deadline": "2026-12-01"},
    {"id": "french-only", "title": "Ingénieur de recherche en bioinformatique pour le laboratoire",
     "summary": "Le poste est dans une équipe de recherche avec des données de génomique", "url": "https://e.org/f",
     "deadline": "2026-12-01"},
    {"id": "past-deadline", "title": "Old job", "url": "https://example.org/old", "deadline": "2026-01-01",
     "type": "nonsense", "place": "Boston, MA"}],
    "funding": [{"id": "travel-grant", "title": "Travel grant", "url": "https://example.org/f1",
                 "deadline": "2026-10-20", "amount": "€1,000", "who": "PhD students"}],
    "conferences": [{"id": "ismb", "title": "ISMB 2027", "url": "https://example.org/c1", "deadline": "2027-01-15",
                     "starts": "2027-07-10", "ends": "2027-07-14", "place": "Paris, France"}],
    "resources": [{"id": "r-course", "title": "R for data science", "url": "https://r4ds.hadley.nz",
                   "type": "book", "level": "beginner", "skills": ["R", "dplyr"], "free": False},
                  {"id": "odd-type", "title": "Something", "url": "https://x.org", "type": "podcast", "level": "guru"}]}


def test_curated_lists_are_cleaned_the_same():
    said = phone.run("""
import * as C from './lib/curated.ts';
const lists = C.clean(INPUT);
const items = [...lists.jobs, ...lists.funding, ...lists.conferences];
out({ jobs: lists.jobs, funding: lists.funding, conferences: lists.conferences, resources: lists.resources,
  days: items.map((it) => C.daysLeft(it, '2026-10-19')),
  report: C.reportLinks('jobs', lists.jobs[0]) });
""", LISTS)
    d = curated.clean(LISTS)
    for kind in ("jobs", "funding", "conferences", "resources"):
        assert norm(d[kind]) == said[kind], kind
    items = d["jobs"] + d["funding"] + d["conferences"]
    assert [curated.days_left(it, date(2026, 10, 19)) for it in items] == said["days"]
    desk = curated.report_links("jobs", d["jobs"][0])
    from urllib.parse import parse_qs, urlsplit

    def read(url: str) -> dict:          # what the person sees, without the phone's own "sent from" footer
        q = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        return {k: v.split("\n\n---\n")[0].strip() for k, v in q.items()}
    for k in ("issue", "email"):
        assert read(desk[k]) == read(said["report"][k]), k


# --------------------------------------------------------------------------- taste: your 👍 / 👎
VOTES = {"job:a": {"vote": -1, "at": "2026-10-01T10:00:00+00:00", "terms": ["wet-lab", "pipetting", "cell culture"]},
         "job:b": {"vote": 1, "at": "2026-09-01T10:00:00+00:00", "terms": ["gwas", "statistics"]},
         "skill:c": {"vote": 1, "at": "2025-01-01T10:00:00+00:00", "terms": ["rust"]},
         "resource:d": {"vote": -1, "at": "2026-10-18T10:00:00+00:00", "terms": ["video", "statistics"]}}
TEXTS = [["A wet-lab postdoc with cell culture and pipetting", ["Biology"]],
         ["Statistical genetics: GWAS and fine-mapping, R and Python", ["gwas", "Statistics"]],
         ["", []], ["Rust for HPC", ["rust"]]]


def test_taste_learns_and_leans_the_same(monkeypatch):
    now = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
    said = phone.run("""
import * as T from './lib/taste.ts';
const [votes, texts, now] = INPUT;
const w = T.weights(votes, undefined, now), wj = T.weights(votes, ['job'], now);
out({ terms: texts.map(([t, tags]) => T.termsOf(t, tags)), w, wj,
  lean: texts.map(([t, tags]) => [T.lean(t, tags, w), T.lean(t, tags, wj)]),
  key: T.keyOf('job', '  ABC '), vote: T.voteOf(votes, 'job', 'A') });
""", [VOTES, TEXTS, now.timestamp() * 1000])
    monkeypatch.setattr(taste, "load", lambda: json.loads(json.dumps(VOTES)))
    w, wj = taste.weights(now=now), taste.weights(["job"], now=now)
    assert [taste.terms_of(t, tags) for t, tags in TEXTS] == said["terms"]
    assert norm(w) == pytest.approx(said["w"]) and norm(wj) == pytest.approx(said["wj"])
    desk = [x for t, g in TEXTS for x in (taste.lean(t, g, w), taste.lean(t, g, wj))]
    assert desk == pytest.approx([x for pair in said["lean"] for x in pair])
    assert taste.key_of("job", "  ABC ") == said["key"] and taste.vote_of("job", "A") == said["vote"]


# --------------------------------------------------------------------------- quiz banks
BANK = {"version": "q1", "questions": [
    {"id": "q-1", "protocol": "r-basics", "stage": "s1", "level": "easy", "question": "What does <- do in R?",
     "options": ["Assigns a value", "Compares", "Loops", "Prints"], "answer": 0, "source": "https://r4ds.hadley.nz",
     "why": "It's assignment."},
    {"id": "q-2", "protocol": "r-basics", "level": "tricky", "question": "Short?", "options": ["a", "b"], "answer": 5},
    {"id": "q-3", "protocol": "r-basics", "level": "nonsense", "question": "Which is a vector function in R?",
     "options": ["c()", "v()", "vec()"], "answer": 0},
    {"id": "", "protocol": "x", "question": "no id", "options": ["a", "b"], "answer": 0}, "junk"]}


def test_quiz_banks_and_draw_shares_are_the_same():
    said = phone.run("""
import * as Q from './lib/quiz.ts';
out({ bank: Q.cleanBank(INPUT), share: [10, 7, 3, 1].map((n) => Q.share(n)),
  token: Q.answerToken('q-1', 'Assigns a value'), one: INPUT.questions.map((q: any) => Q.cleanQuestion(q)) });
""", BANK)
    assert norm(quiz.clean_bank(BANK)) == said["bank"]
    assert [quiz.share(n) for n in (10, 7, 3, 1)] == said["share"]
    assert quiz.answer_token("q-1", "Assigns a value") == said["token"]
    assert norm([quiz.clean_question(q) for q in BANK["questions"]]) == said["one"]


# --------------------------------------------------------------------------- protocol shapes
PROTOS = [
    {"id": "r-data", "skill": "R for data analysis", "title": "R for data analysis", "goal": "Analyse data in R",
     "stages": [{"id": "basics", "title": "R basics", "role": "basics",
                 "items": [{"title": "R for Data Science", "url": "https://r4ds.hadley.nz", "kind": "book"},
                           {"title": "bad link", "url": "javascript:alert(1)"}],
                 "quiz": [{"question": "Q?", "options": ["a", "b"], "answer": 1}]},
                {"title": "", "role": "deeper"}, {"title": "A real project", "role": "nonsense"}]},
    {"id": "pipetting", "skill": "Pipetting", "title": "Pipetting technique", "stages": [{"title": "Hold the pipette"}]},
    {"skill": "", "title": "no skill", "stages": [{"title": "x"}]}, "junk"]


def test_protocols_are_cleaned_the_same():
    said = phone.run("""
import * as P from './lib/protocol-shape.ts';
out(INPUT.map((p: any) => [P.cleanProtocol(p, false), P.cleanProtocol(p, true)]));
""", PROTOS)
    assert norm([[protocols.clean_protocol(p, False), protocols.clean_protocol(p, True)] for p in PROTOS]) == said


# --------------------------------------------------------------------------- token expiry
EXPIRY = ["2026-11-02 10:00:00 UTC", "2026-10-21 08:30:00 +0200", "2026-10-21 08:30:00 -0500", "", "soon",
          "2026-13-40 10:00:00 UTC"]


def test_token_expiry_is_read_and_warned_the_same():
    now = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
    said = phone.run("""
import * as K from './lib/tokens.ts';
const [values, now] = INPUT;
out(values.map((v: string) => { const d = K.parseExpiry(v); const iso = d ? d.toISOString() : null;
  const s = K.describe('data', { state: 'ok', expiresAt: iso }, now); return [iso, s.warn]; }));
""", [EXPIRY, now.timestamp() * 1000])
    for value, (iso, warn) in zip(EXPIRY, said):
        d = tokens.parse_expiry(value)
        assert (d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z") if d else None) == iso, value
        entry = {"name": "read", "state": "ok", "expires_at": d.isoformat() if d else None}
        assert tokens.describe(entry, now)["warn"] == warn, value
