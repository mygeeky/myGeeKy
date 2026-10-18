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


INPUTS = ["sing", "gwas, stat", "single cell, ", "py", "r", "", "GWAS, gwas", "rna-seq", "Single-cell", "micro",
          "stats, machine lear", "phylo", "x", "bio, bio"]
SUGGEST_SCRIPT = """
import { pick, suggest } from './word-suggest.ts';
const inputs = JSON.parse(process.argv[2]);
console.log(JSON.stringify({ suggest: inputs.map((t) => suggest(t)), pick: pick('gwas, sta', 'statistics') }));
"""


def _node() -> bool:
    import shutil
    import subprocess
    if not shutil.which("node"):
        return False
    v = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip().lstrip("v").split(".")
    return len(v) > 1 and v[0].isdigit() and v[1].isdigit() and (int(v[0]), int(v[1])) >= (22, 6)


@pytest.mark.skipif(not _node(), reason="needs Node 22.6+")
def test_the_phone_suggests_the_same_words_in_the_same_order(monkeypatch):
    """lib/word-suggest.ts and keywords.suggest: the same words, in the same order, for the same typing."""
    import re
    import shutil
    import subprocess
    root = keywords.PHONE_COPY.parents[3]
    work = root / "mobile" / ".crosscheck"
    (work / "data").mkdir(parents=True, exist_ok=True)
    src = (root / "mobile" / "src" / "lib" / "word-suggest.ts").read_text(encoding="utf-8")
    src = re.sub(r"from '\.\./data/([a-z-]+)\.json';", r"from './data/\1.json' with { type: 'json' };", src)
    (work / "word-suggest.ts").write_text(src, encoding="utf-8")
    for name in ("field-words.json", "skills.json"):
        shutil.copy(root / "mobile" / "src" / "data" / name, work / "data" / name)
    (work / "suggest-side.ts").write_text(SUGGEST_SCRIPT, encoding="utf-8")
    out = subprocess.run(["node", "--experimental-strip-types", str(work / "suggest-side.ts"), json.dumps(INPUTS)],
                         capture_output=True, text=True, cwd=root / "mobile", timeout=60)
    assert out.returncode == 0, out.stderr[-800:]
    phone = json.loads(out.stdout)
    # the desktop reads the dictionary shipped with it (a newer download could hold more words than the phone)
    monkeypatch.setattr(keywords, "load", lambda force=False: json.loads(keywords.BUNDLED.read_text(encoding="utf-8")))
    monkeypatch.setattr(keywords, "_suggest_words", None)
    for text, said in zip(INPUTS, phone["suggest"]):
        assert said == keywords.suggest(text), text
    assert phone["pick"] == keywords.pick("gwas, sta", "statistics") == "gwas, statistics, "


def test_the_setup_box_fills_in_a_pick_and_then_offers_its_relatives(monkeypatch):
    pytest.importorskip("PySide6")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLineEdit
    app = QApplication.instance() or QApplication([])
    from mygeeky.gui.word_suggest import attach
    box = QLineEdit()
    many = attach(box)
    box.setText("gwas, sing")
    assert many.words()[0] == "single cell"
    many._picked("single cell")
    assert box.text() == "gwas, single cell, "
    assert many.model.stringList() == keywords.suggest("gwas, single cell, ")   # its relatives come up next
    one = attach(QLineEdit(), many=False)
    one.box.setText("sing")
    one._picked("single cell")
    assert one.box.text() == "single cell"                                     # one keyword at a time: no comma
    box.deleteLater()
    app.processEvents()
