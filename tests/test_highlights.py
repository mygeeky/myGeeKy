"""Highlights: research articles told as stories. The desktop and the phone read them the same way, the facts
come from OpenAlex, one paste is split per article, DeepSeek's story is checked against the text, and
accepted ones join the curated lists."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from mygeeky import curated, highlights, highlight_shape as shape

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"

BODY = [
    "About 3% of human genes are so important that almost nobody carries a broken copy of them. A team that "
    "read the genomes of 141,456 people found these genes by looking for the variants that are missing, not the "
    "ones that are there. The catalogue tells doctors which broken genes are likely to matter when they read a "
    "patient's genome, and tells researchers which genes to look at first.",
    "The work was led by Ada Lovelace at the Broad Institute and appeared in Nature in May 2020. It was a large "
    "collaboration: 12 institutions in 4 countries pooled sequencing data that had been collected for other "
    "studies. Pooling it was the only way to reach a sample big enough to see variants that are very rare.",
    "Earlier catalogues of human variation held tens of thousands of people at most. That was too few to tell "
    "a gene that can't be broken from one where breaking variants are simply rare by chance, so lists of "
    "essential genes were guesses built from small numbers.",
    "The team sequenced 141,456 people and used Hail, a tool for very large genetic datasets, and VEP, which "
    "predicts what a variant does to a gene. They counted, gene by gene, how many breaking variants they saw "
    "against how many they would expect if breaking it did no harm.",
    "Genes that can't be broken were often linked to disease, and many had no known role before. Most of the "
    "people studied were of European ancestry, which the authors say limits what can be concluded for others; "
    "they call for more diverse samples.",
]
GOOD = {"id": "hl-genes-that-cannot-break-abc123", "kind": "article", "title": "  Some genes   can't be broken ",
        "hook": "A catalogue of 141,456 people shows it.", "url": "https://doi.org/10.1038/s41586-020-2308-7",
        "doi": "10.1038/s41586-020-2308-7", "added": "2026-10-18", "coverage": "full", "body": BODY + ["", "  "],
        "meta": {"journal": "Nature", "published": "2020-05-27", "lead": "Ada Lovelace", "authors": ["A", "B", "a"],
                 "institutions": ["Broad Institute"], "countries": ["United States", "Finland"], "open_access": True},
        "tools": ["Hail", "VEP", "hail"], "skills": ["GWAS", "Python"], "keywords": ["Genetics"],
        "translations": {"ar": {"name": "العربية", "rtl": True, "title": "بعض الجينات لا تنكسر", "hook": "",
                                "body": ["حوالي 3% من الجينات البشرية مهمة جدًا.", "قاد العمل آدا لوفلايس.",
                                         "كانت الكتالوجات السابقة صغيرة.", "درس الفريق 141,456 شخصًا.",
                                         "ارتبطت هذه الجينات بالأمراض، ومعظم المشاركين من أصل أوروبي."]},
                         "es": {"title": "Algunos genes", "body": ["solo uno", "dos", "tres"]},
                         "fr": {"title": ""}, "xx-yy-zz": {"title": "bad code"}}}
ENTRIES = [GOOD, {**GOOD, "id": "hl-older-one", "added": "2026-01-02", "coverage": "nope", "doi": "not a doi"},
           {**GOOD, "id": "Bad Id"}, {**GOOD, "id": "hl-no-url", "url": "http://x.org"},
           {**GOOD, "id": "hl-few", "body": ["one", "two"]}, GOOD, "junk"]


def _node() -> bool:
    if not shutil.which("node"):
        return False
    v = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=120).stdout.strip().lstrip("v").split(".")
    return len(v) > 1 and v[0].isdigit() and v[1].isdigit() and (int(v[0]), int(v[1])) >= (22, 6)


def test_a_highlight_is_checked_and_trimmed():
    out = shape.clean_all(ENTRIES)
    assert [h["id"] for h in out] == ["hl-genes-that-cannot-break-abc123", "hl-older-one"]
    h = out[0]
    assert h["title"] == "Some genes can't be broken" and h["tools"] == ["Hail", "VEP"]
    assert h["meta"]["authors"] == ["A", "B"] and h["skills"] == ["gwas", "python"]
    assert h["body"] == BODY and list(h["translations"]) == ["ar", "es"] and h["translations"]["ar"]["rtl"]
    assert out[1]["coverage"] == "abstract" and out[1]["doi"] == ""
    ar = shape.read_in(h, "ar")
    assert ar["body"][0].startswith("حوالي 3%") and len(ar["body"]) == len(BODY) == 5
    assert ar["labels"]["read"] == "اقرأ المقال" and shape.read_in(h, "zz")["code"] == "en"
    es = shape.read_in(h, "es")
    assert es["title"] == "Algunos genes" and es["body"] == BODY      # 3 paragraphs for 6: they don't line up
    assert shape.languages(h) == [("en", "English"), ("ar", "العربية"), ("es", "Español")]
    assert curated.clean({"highlights": ENTRIES})["highlights"] == out
    assert any("hl-few" in p for p in curated.problems({"highlights": ENTRIES}))


@pytest.mark.skipif(not _node(), reason="needs Node 22.6+")
def test_the_phone_reads_highlights_exactly_as_the_desktop():
    work = MOBILE / ".crosscheck"
    work.mkdir(exist_ok=True)
    shutil.copy(MOBILE / "src" / "lib" / "highlight-shape.ts", work / "highlight-shape.ts")
    (work / "hl-side.ts").write_text(
        "import { readFileSync } from 'node:fs';\n"
        "import { cleanAll, languages, readIn } from './highlight-shape.ts';\n"
        "const out = cleanAll(JSON.parse(readFileSync(0, 'utf8')));\n"
        "console.log(JSON.stringify({ out, ar: readIn(out[0], 'ar'), es: readIn(out[0], 'es'), zz: readIn(out[0], 'zz'),\n"
        "  langs: languages(out[0]) }));\n",
        encoding="utf-8")
    run = subprocess.run(["node", "--experimental-strip-types", str(work / "hl-side.ts")], input=json.dumps(ENTRIES),
                         capture_output=True, text=True, cwd=MOBILE, timeout=60)
    assert run.returncode == 0, run.stderr[-800:]
    phone = json.loads(run.stdout)
    desktop = shape.clean_all(ENTRIES)
    assert phone["out"] == desktop
    for code in ("ar", "es", "zz"):
        assert phone[code] == shape.read_in(desktop[0], code), code
    assert [tuple(x) for x in phone["langs"]] == shape.languages(desktop[0])
    labels = (MOBILE / "src" / "lib" / "highlight-shape.ts").read_text(encoding="utf-8")
    for code, words in shape.LABELS.items():          # every label, in every language, on the phone too
        assert all(w in labels for w in words.values()), code


WORK = {"title": "The mutational constraint spectrum", "publication_date": "2020-05-27",
        "primary_location": {"source": {"display_name": "Nature"}}, "open_access": {"is_oa": True},
        "abstract_inverted_index": {"Genes": [0], "can": [1], "break": [2], "3%": [3]},
        "authorships": [
            {"author": {"display_name": "First Author"}, "is_corresponding": True,
             "institutions": [{"display_name": "Broad Institute", "country_code": "US"}]},
            {"author": {"display_name": "Ada Lovelace"},
             "institutions": [{"display_name": "University of Helsinki", "country_code": "FI"},
                              {"display_name": "Broad Institute", "country_code": "US"}]}]}


def test_the_facts_come_from_openalex():
    f = highlights.facts(WORK, "10.1/x")
    assert f["lead"] == "Ada Lovelace" and f["corresponding"] == "First Author"
    assert f["institutions"] == ["Broad Institute", "University of Helsinki"] and f["institution_count"] == 2
    assert f["countries"] == ["United States", "Finland"] and f["journal"] == "Nature" and f["open_access"]
    assert f["abstract"] == "Genes can break 3%" and f["url"] == "https://doi.org/10.1/x"


def test_dois_links_and_one_paste_split_per_article():
    pasted = "https://doi.org/10.1038/ABC.1). see also https://www.biorxiv.org/content/10.1101/2024.01.02.5v1/full\nhttps://x.org/page"
    assert highlights.find_dois(pasted) == ["10.1038/abc.1", "10.1101/2024.01.02.5v1"]
    assert highlights.links(pasted)[-1] == "https://x.org/page"
    text = "Journal header\nDeep learning for GWAS: a new way\nWe found 3.5% of x.\nSingle-cell atlases of the gut\nmore"
    parts = highlights.split_text(text, [{"doi": "a", "title": "Deep learning for GWAS - a new way"},
                                         {"doi": "b", "title": "Single-cell atlases of the gut"},
                                         {"doi": "c", "title": "Not in the paste"}])
    assert parts["a"].startswith("Deep learning") and "3.5%" in parts["a"] and parts["b"].endswith("more")
    assert "c" not in parts


class _Resp:
    def __init__(self, data, status=200):
        self.status_code, self._data = status, data

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


def test_a_draft_is_written_translated_checked_and_merged(monkeypatch, tmp_path):
    monkeypatch.setattr(highlights, "STATE_FILE", tmp_path / "highlights.json")
    story = {"title": "Some genes can't be broken", "hook": "A big catalogue shows it.",
             "body": BODY[:3] + ["One line.", BODY[3], "About 3% of genes, and 42% more, in 2020."],
             "tool_names": ["Hail", "Seurat"], "skills": ["gwas"], "keywords": ["genetics"], "coverage": "abstract"}
    asked = []

    def post(url, json=None, **_kw):                    # a stand-in for DeepSeek
        asked.append(json["messages"][0]["content"])
        if "The language:" in json["messages"][0]["content"]:
            return _Resp({"choices": [{"message": {"content": __import__("json").dumps(
                {"title": "Titre", "hook": "Accroche", "body": ["Un", "Deux", "Trois", "Environ 3%"]})}}]})
        return _Resp({"choices": [{"message": {"content": __import__("json").dumps(story)}}]})

    class Session:
        def get(self, url, **_kw):
            return _Resp(WORK)

    out = highlights.draft("10.1038/s41586-020-2308-7", "", abstract_only=True, key="k", post=post,
                           session=Session(), languages=("fr",))
    assert out["errors"] == [] and len(out["drafts"]) == 1
    d = highlights.drafts("new")[0]
    it = d["item"]
    assert it["coverage"] == "abstract" and it["meta"]["lead"] == "Ada Lovelace"
    assert len(it["body"]) == 4 and it["body"][3].startswith("One line. The team")   # a line joins the next paragraph
    assert all(len(p.split()) >= highlights.MIN_PARAGRAPH_WORDS for p in it["body"])
    assert it["translations"]["fr"]["body"][-1] == "Environ 3%"
    assert any("42%" in w for w in d["warnings"]) and any("Seurat" in w for w in d["warnings"])
    assert not any("2020" in w for w in d["warnings"])           # the year is in the looked-up facts
    assert "Use only what FACTS and TEXT say" in asked[0] and "The language: French" in asked[1]
    highlights.set_status(it["id"], "accepted")
    merged, added = highlights.merge({"version": "1", "jobs": []}, highlights.accepted())
    again, twice = highlights.merge(merged, highlights.accepted())
    assert added == 1 and twice == 0 and curated.problems(merged) == []
    assert curated.clean(merged)["highlights"][0]["id"] == it["id"]


def test_the_article_skill_has_both_steps():
    write, translate = highlights.skill()
    for rule in ("ONE idea", "Leave a paragraph out", "copied", "No hype", "The lead", "The limits", "\"tool_names\""):
        assert rule in write, rule
    assert "Keep exactly as they are" in translate and "same number of paragraphs" in translate
    assert "What you write" not in translate


def test_lines_join_into_paragraphs():
    out = highlights.paragraphs(["Short.", "Also short.", " ".join(["word"] * 40), "", "A tail."])
    assert len(out) == 1 and out[0].startswith("Short. Also short. word") and out[0].endswith("A tail.")
    assert highlights.paragraphs(BODY) == BODY                    # real paragraphs are left alone


def test_the_same_languages_as_chances():
    from mygeeky import scout
    assert highlights.LANGUAGES == scout.SAY_LANGUAGES                      # what DeepSeek translates into
    assert {c: v for c, v in shape.NAMES.items()} == curated.LANGUAGES      # the buttons' names and directions
    assert set(shape.LABELS) == {"en", *curated.LANGUAGES}                  # the words around a story
    phone = (MOBILE / "src" / "lib" / "highlight-shape.ts").read_text(encoding="utf-8")
    for code, (name, _rtl) in curated.LANGUAGES.items():
        assert f"{code}: ['{name}'" in phone, code


def test_the_skill_ships_with_the_package():
    import tomllib
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]["package-data"]
    assert any(p.endswith("data/*.md") for p in data["mygeeky"]), "data/article_skill.md must be in the wheel"
