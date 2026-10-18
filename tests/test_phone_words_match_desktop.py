"""The phone suggests field words from its own copy of the keyword dictionary (mobile/src/data/field-words.json).
It must be the desktop dictionary's words, so both apps offer the same field."""

import json

import pytest

from mygeeky import keywords


@pytest.mark.skipif(not keywords.PHONE_COPY.exists(), reason="the phone's code isn't here")
def test_the_phone_ships_the_same_words_as_the_desktop():
    desktop = json.loads(keywords.BUNDLED.read_text(encoding="utf-8"))
    phone = json.loads(keywords.PHONE_COPY.read_text(encoding="utf-8"))
    assert phone == keywords.phone_words(desktop), "run: mygeeky admin keywords build (or save) to refresh the phone copy"


def test_each_keyword_brings_its_closest_related_words_written_as_words():
    words = keywords.phone_words({"version": 1, "terms": {
        "single-cell": {"related": [["scrna-seq", 1.0], ["seurat", 0.8], ["scanpy", 0.7], ["umap", 0.5],
                                    ["clustering", 0.4], ["anndata", 0.3]]}}})
    assert words["related"]["single cell"] == ["scrna seq", "seurat", "scanpy", "umap", "clustering"]
    assert "anndata" in words["words"] and "single cell" in words["words"]
