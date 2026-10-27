"""📰 What's new (whatsnew_shape.py / lib/whatsnew-shape.ts): the published AI and tech news is checked again on
reading, as untrusted, the same way on both apps, ranked the same, and shown first in News on both."""
from __future__ import annotations

from datetime import date

import pytest

import phone
from mygeeky import curated, whatsnew_shape

TODAY = date(2026, 10, 27)
ITEMS = [
    {"id": "tr-aaaaaaaa", "title": "A 1B model beats 70B models at maths", "summary": "Example Labs released it.",
     "why": "Cheaper to run.", "url": "https://www.youtube.com/watch?v=abc", "added": "2026-10-26",
     "sources": ["https://example-labs.ai/blog", "javascript:alert(1)", "https://www.nature.com@evil.example/x"],
     "topic": "Small Language Models", "keywords": ["llm", "LLM", "small models"]},
    {"id": "tr-bbbbbbbb", "title": "AlphaFold 4 predicts protein complexes", "url": "https://deepmind.google/x",
     "added": "2026-10-27", "topic": "protein structure", "keywords": ["alphafold", "genomics"]},
    {"id": "tr-cccccccc", "title": "Too old to show", "url": "https://example.org/old", "added": "2026-09-01"},
    {"id": "bad id", "title": "Bad id", "url": "https://example.org/x", "added": "2026-10-27"},
    {"id": "tr-dddddddd", "title": "A lookalike link", "url": "https://www.nature.com@evil.example/x", "added": "2026-10-27"},
    {"id": "tr-eeeeeeee", "title": "<img src=x> markup stays text", "url": "https://example.org/y", "added": "2026-10-25"},
    {"id": "tr-aaaaaaaa", "title": "A duplicate id", "url": "https://example.org/z", "added": "2026-10-27"},
]
WEIGHTS = {"genomics": 1.0, "llm": 0.4}


def test_it_is_checked_on_reading():
    out = whatsnew_shape.clean_all(ITEMS, TODAY)
    assert [x["id"] for x in out] == ["tr-bbbbbbbb", "tr-aaaaaaaa", "tr-eeeeeeee"]           # newest first
    first = next(x for x in out if x["id"] == "tr-aaaaaaaa")
    assert first["sources"] == ["https://www.youtube.com/watch?v=abc", "https://example-labs.ai/blog"]
    assert first["topic"] == "small language models" and first["keywords"] == ["llm", "small models"]
    assert curated.clean({"whatsnew": ITEMS})["whatsnew"] == whatsnew_shape.clean_all(ITEMS)  # part of the lists


def test_ranking_nudges_toward_your_field():
    items = whatsnew_shape.clean_all(ITEMS, TODAY)
    assert [x["id"] for x in whatsnew_shape.ranked(items, WEIGHTS, TODAY)][0] == "tr-bbbbbbbb"
    assert [x["id"] for x in whatsnew_shape.ranked(items, {"llm": 1.0}, TODAY)][:2] == ["tr-aaaaaaaa", "tr-bbbbbbbb"]


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+")
def test_the_phone_says_the_same():
    said = phone.run("""
import { cleanAll, ranked } from './lib/whatsnew-shape.ts';
const today = new Date(INPUT.today + 'T12:00:00Z');
const items = cleanAll(INPUT.items, today);
out({ items, ranked: ranked(items, INPUT.weights, today).map((x) => x.id), llm: ranked(items, { llm: 1 }, today).map((x) => x.id) });
""", {"items": ITEMS, "today": TODAY.isoformat(), "weights": WEIGHTS}, name="whatsnew")
    want = whatsnew_shape.clean_all(ITEMS, TODAY)
    assert said["items"] == want
    assert said["ranked"] == [x["id"] for x in whatsnew_shape.ranked(want, WEIGHTS, TODAY)]
    assert said["llm"] == [x["id"] for x in whatsnew_shape.ranked(want, {"llm": 1.0}, TODAY)]


def test_publishing_merges_checked_items_once():
    data, added = whatsnew_shape.merge({"whatsnew": []}, ITEMS, TODAY)
    assert added == 3 and len(data["whatsnew"]) == 3
    data, added = whatsnew_shape.merge(data, ITEMS[:2], TODAY)
    assert added == 0
