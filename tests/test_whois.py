""""Is this you?": candidates found, ranked and described the same on the desktop and the phone; busy is busy."""
from __future__ import annotations

import json

import pytest

import phone
from mygeeky import whois


def _author(i, name, inst="", cc="", works=10, cited=50, topics=(), orcid=""):
    return {"id": f"https://openalex.org/A{i}", "display_name": name, "works_count": works, "cited_by_count": cited,
            "last_known_institutions": [{"display_name": inst, "country_code": cc}] if inst else [],
            "topics": [{"display_name": t} for t in topics], "orcid": orcid}


AUTHORS = {"results": [
    _author(5001, "Samman Mahmoud", "Lund University", "SE", 40, 900, ["Statistical genetics", "GWAS", "Plant breeding", "x"]),
    _author(5002, "Samman M. Alsamman", "International Center for Agricultural Research in the Dry Areas", "LB", 120, 2400),
    _author(5003, "S. Mahmoud", "Cairo University", "EG", 3, 4),
    _author(5004, "Mahmoud Samman", "Ain Shams University", "EG", 8, 10),
    _author(5005, "Sámman Mahmoud", "Lunds universitet", "SE", 1, 0),
    _author(5006, "Someone Else", "Lund University", "SE", 300, 9000),
    {"id": "not-an-id", "display_name": "Bad"}, "junk"]}
WORKS = {"results": [
    {"title": "GWAS of drought tolerance", "publication_year": 2025,
     "authorships": [{"author": {"id": "https://openalex.org/A5001"}}, {"author": {"id": "https://openalex.org/A5002"}}]},
    {"title": "Older paper", "publication_year": 2019, "authorships": [{"author": {"id": "https://openalex.org/A5001"}}]},
    {"title": "GWAS of drought tolerance", "publication_year": 2025, "authorships": [{"author": {"id": "https://openalex.org/A5001"}}]},
    {"title": "Third", "publication_year": 2023, "authorships": [{"author": {"id": "https://openalex.org/A5001"}}]},
    {"title": "Fourth", "publication_year": 2021, "authorships": [{"author": {"id": "https://openalex.org/A5001"}}]},
    {"title": "", "publication_year": 2024, "authorships": [{"author": {"id": "https://openalex.org/A5003"}}]}]}
QUERIES = [["Samman Mahmoud", "Lund University"], ["S Mahmoud", ""], ["samman mahmoud", "someone@med.lu.se"],
           ["Mahmoud", "Lund"], ["Sámman MAHMOUD", "lunds"], ["Nobody Here", ""]]


def _desktop():
    out = []
    for name, hint in QUERIES:
        h = whois.domain_hint(hint) if "@" in hint else hint
        ranked = whois.rank(whois.parse_authors(AUTHORS), name, h)
        out.append({"hint": h, "ranked": whois.add_titles(ranked, WORKS) if ranked else []})
    return out


def test_finding_you():
    best = _desktop()[0]["ranked"]
    assert best[0]["id"] == "A5001" and best[0]["titles"][0] == "GWAS of drought tolerance (2025)"
    assert len(best[0]["titles"]) == 3 and best[0]["topics"] == ["Statistical genetics", "GWAS", "Plant breeding"]
    assert "A5006" not in [c["id"] for c in best]                     # a different person at the same place
    assert whois.name_score("S Mahmoud", "Samman Mahmoud") > 0 and whois.name_score("Mahmoud Samman", "Mahmoud Ali") == 0
    assert whois.domain_hint("a.b@med.uni-heidelberg.de") == "uni heidelberg"
    assert _desktop()[-1]["ranked"] == []
    assert whois.busy(429) and whois.busy(503) and not whois.busy(200) and not whois.busy(404)
    assert whois.next_try(1000, 10) == 1000 + whois.RETRY_MIN_SECONDS and whois.next_try(0, 9999) == 9999


class _R:
    def __init__(self, status, data=None, headers=None):
        self.status_code, self._d, self.headers = status, data, headers or {}

    def json(self):
        return self._d

    def raise_for_status(self):
        pass


def test_busy_carries_on_and_says_when_to_try_again():
    class Busy:
        def get(self, url, **_):
            return _R(429, headers={"retry-after": "7200"})
    out = whois.search("Samman Mahmoud", "Lund", Busy())
    assert out["status"] == "busy" and out["retry_after"] == 7200

    class Ok:
        def get(self, url, **_):
            return _R(200, AUTHORS if "/authors" in url else WORKS)
    found = whois.search("Samman Mahmoud", "Lund University", Ok())
    assert found["status"] == "found" and found["candidates"][0]["id"] == "A5001"
    assert whois.search("Samman", "", Ok())["status"] == "none"


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+")
def test_the_phone_finds_you_exactly_as_the_desktop():
    said = phone.run("""
import * as W from './lib/whois.ts';
const [authors, works, queries] = INPUT;
out(queries.map(([name, hint]: string[]) => { const h = hint.includes('@') ? W.domainHint(hint) : hint;
  const ranked = W.rank(W.parseAuthors(authors), name, h); return { hint: h, ranked: ranked.length ? W.addTitles(ranked, works) : [] }; }));
""", [AUTHORS, WORKS, QUERIES])
    assert said == json.loads(json.dumps(_desktop()))
