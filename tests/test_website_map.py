"""The website's map of scientists (website/scientists.json, read by website/build.py): only checked entries reach
the page, and nothing in them can close the <script> they sit in."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _build(tmp_path, monkeypatch, scientists):
    spec = importlib.util.spec_from_file_location("site_build", ROOT / "website" / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    site = tmp_path / "website"
    site.mkdir()
    (site / "scientists.json").write_text(json.dumps({"scientists": scientists}), encoding="utf-8")
    real = mod.ROOT
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "src").symlink_to(real / "src")
    return mod


GOOD = {"name": "Ada Example", "role": "PhD student", "place": "Lund", "link": "https://orcid.org/0000-0002-1825-0097",
        "fields": ["GWAS", "R"], "since": "2026-10"}


def test_the_shipped_list_is_valid_and_the_page_has_its_place():
    assert isinstance(json.loads((ROOT / "website/scientists.json").read_text(encoding="utf-8"))["scientists"], list)
    page = (ROOT / "website/index.html").read_text(encoding="utf-8")
    assert '{{MAP_DATA}}' in page and 'id="scientists"' in page and 'id="get"' in page
    spec = importlib.util.spec_from_file_location("site_build", ROOT / "website" / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    data = json.loads(mod.map_data().replace("<\\/", "</"))
    assert isinstance(data["scientists"], list) and len(data["fields"]) >= 10


def test_a_good_entry_passes_and_text_cannot_close_the_script(tmp_path, monkeypatch):
    mod = _build(tmp_path, monkeypatch, [{**GOOD, "role": "</script><script>alert(1)</script>"}])
    text = mod.map_data()
    assert "</script>" not in text
    assert json.loads(text.replace("<\\/", "</"))["scientists"][0]["name"] == "Ada Example"


@pytest.mark.parametrize("bad", [
    {**GOOD, "link": "http://example.org"},                 # not https
    {**GOOD, "link": "javascript:alert(1)"},
    {**GOOD, "fields": []},                                 # a field at least
    {**GOOD, "fields": ["a"] * 7},                          # at most six
    {**GOOD, "name": ""},                                   # a name
    {**GOOD, "name": "x" * 81},
    {**GOOD, "role": 5},
])
def test_a_wrong_entry_stops_the_build(tmp_path, monkeypatch, bad):
    mod = _build(tmp_path, monkeypatch, [bad])
    with pytest.raises(SystemExit):
        mod.scientists()
