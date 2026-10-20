"""Drop a CV, thesis or abstract: what's found in it, and the phone finding exactly the same (tests/phone.py)."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

import phone
from mygeeky import docread, keywords
from mygeeky.text_utils import docx_text, load_cv_text

ROOT = Path(__file__).resolve().parents[1]
WORDS = list(json.loads((ROOT / "mobile" / "src" / "data" / "field-words.json").read_text())["related"])

CV = """Mahmoud Samman
Postdoctoral researcher in statistical genetics, Lund University
Research interests: GWAS, fine-mapping, single-cell RNA-seq, Mendelian randomization, autoimmune disease (lupus).

EDUCATION
PhD in Bioinformatics, Lund University, 2021. Thesis: Genetic architecture of systemic lupus erythematosus.

SKILLS
R (tidyverse, ggplot2, Bioconductor), Python (pandas, scikit-learn), Snakemake, Docker, Slurm on HPC, Git.
Statistical genetics, bioinformatics, genomics, machine learning, mixed models.

PUBLICATIONS
Samman M, Doe A, Lee K. Fine-mapping lupus risk loci with single-cell RNA-seq. Nat Genet. 2023.
Samman M, Lee K, Ortiz R, Doe A. A GWAS of autoimmune disease in 40,000 people. Am J Hum Genet. 2022.
J. Smith, M. Samman and A. Doe. Mendelian randomization of immune traits. Bioinformatics, 2021.
Ortiz, R., Samman, M., & Lee, K. (2020). Genomics of lupus. PLoS Genetics.
"""

ABSTRACT = """Coastal wetlands and climate change: a remote sensing study of salt marsh loss.
We used Landsat and Sentinel-2 satellite imagery with random forests to map salt marsh extent along the Baltic
coast from 1990 to 2024. Marsh loss was linked to sea level rise and land use. Our GIS workflow (QGIS, Python)
is open. Results inform conservation and biodiversity planning under climate change."""

PROPOSAL = """Thesis proposal: Language contact and code-switching among Arabic–Swedish bilingual teenagers.
This project combines sociolinguistics and corpus linguistics. I will record semi-structured interviews and
focus groups in Malmö schools, transcribe them, and use thematic analysis and corpus analysis in R
(R package quanteda, R scripts on GitHub). Questions concern identity, linguistics of the classroom and
multilingualism. Ethics approval: Lund University."""

ODD = """Müller J, Øster K, Nuñez-Garcia P. Café au lait spots in neurofibromatosis. 2019.
Müller J, Øster K. Follow-up of neurofibromatosis, Lancet. 2020.
Smith J and Brown T and White Q
Just a sentence with In R. And Python R. No authors here."""

WRAPPED = """PUBLICATIONS Samman M, Doe A, Lee K. Fine-mapping lupus risk loci with
single-cell RNA-seq. Nat Genet. 2023. Samman M, Lee K, Ortiz R, Doe A. A GWAS of
autoimmune disease in 40,000 people. Am J Hum Genet. 2022. J. Smith, M.
Samman and A. Doe. Mendelian randomization of immune traits. Bioinformatics,
2021. Ortiz, R., Samman, M., & Lee, K. (2020). Genomics of lupus. PLoS Genetics."""

TEXTS = {"cv": CV, "wrapped": WRAPPED, "abstract": ABSTRACT, "proposal": PROPOSAL, "odd": ODD, "empty": "", "names": CV}
OWN = {"names": "Mahmoud Samman", "odd": "Jonas Müller"}
MERGE = [["GWAS", "single cell"], ["Single-cell", "gwas", "Lupus", "", "lupus", "R"]]


def test_kept_words_join_yours_without_doubles():
    assert docread.merge_words(*MERGE) == ["GWAS", "single cell", "Lupus", "R"]


def test_a_cv_gives_topics_methods_and_coauthors_without_you():
    found = docread.read(CV, WORDS)
    assert {"lupus", "statistical genetics", "single cell", "genomics"} <= set(found["keywords"])
    assert "rna" not in found["keywords"], "a word inside RNA-seq is not a topic of its own"
    assert {"GWAS", "Mendelian randomization", "Python", "R", "Snakemake", "Mixed models"} <= set(found["methods"])
    assert found["coauthors"][:2] == ["A. Doe", "K. Lee"] and "M. Samman" not in found["coauthors"]


def test_author_lists_wrapped_by_a_pdf_still_leave_you_out():
    found = docread.read(WRAPPED, WORDS)
    assert "M. Samman" not in found["coauthors"]
    assert found["coauthors"][:3] == ["A. Doe", "K. Lee", "R. Ortiz"]


def test_a_short_abstract_counts_every_mention():
    found = docread.read(ABSTRACT, WORDS)
    assert {"climate change", "conservation", "biodiversity"} <= set(found["keywords"])
    assert {"Remote sensing", "GIS", "Machine learning", "Python"} <= set(found["methods"])
    assert found["coauthors"] == []


def test_a_first_year_proposal_still_finds_a_field():
    found = docread.read(PROPOSAL, WORDS)
    assert {"Interviews", "Thematic analysis", "Corpus linguistics", "R"} <= set(found["methods"])
    assert "linguistics" in found["keywords"]


def test_r_is_only_r_when_it_is_the_language():
    assert "R" not in docread.read("Smith R, Jones R. R is a letter. Ortiz R.", WORDS)["methods"]
    assert "R" in docread.read("Statistics in R, R packages, and R scripts.", WORDS)["methods"]


def test_your_own_name_is_never_a_coauthor():
    found = docread.read(ODD, WORDS, own_name="Jonas Müller")
    assert "J. Muller" not in found["coauthors"] and "K. Oster" not in found["coauthors"]
    assert {"P. Nunez-Garcia", "T. Brown", "Q. White"} <= set(found["coauthors"])


def test_the_vocabulary_is_the_phone_word_list():
    assert sorted(docread.vocabulary()) == sorted(WORDS) or keywords.load()["version"] != json.loads(
        (ROOT / "mobile" / "src" / "data" / "field-words.json").read_text())["version"]
    assert (ROOT / "src/mygeeky/data/docread.json").read_bytes() == \
        (ROOT / "mobile/src/data/docread.json").read_bytes(), "the phone's docread.json is a copy"


def test_word_documents_are_read():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", '<w:document><w:body><w:p><w:r><w:t>GWAS &amp; lupus</w:t></w:r></w:p>'
                                         '<w:p><w:r><w:t>Lund</w:t><w:tab/><w:t>2024</w:t></w:r></w:p></w:body></w:document>')
    assert docx_text(buf.getvalue()).split("\n")[:2] == ["GWAS & lupus", "Lund 2024"]


def test_files_by_type(tmp_path):
    (tmp_path / "a.md").write_text("# GWAS\nlupus", encoding="utf-8")
    assert "lupus" in load_cv_text(str(tmp_path / "a.md"))


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_finds_exactly_the_same():
    said = phone.run("""
import { mergeWords, read, vocabulary } from './lib/doc-read.ts';
const [texts, own, words, merge] = INPUT;
out({ found: Object.fromEntries(Object.entries(texts).map(([k, t]) => [k, read(t as string, words, own[k] ?? '')])),
      vocab: vocabulary().length, merged: mergeWords(...(merge as [string[], string[]])) });
""", [TEXTS, OWN, WORDS, MERGE])
    for k, t in TEXTS.items():
        assert docread.read(t, WORDS, OWN.get(k, "")) == said["found"][k], k
    assert said["vocab"] == len(WORDS)
    assert said["merged"] == docread.merge_words(*MERGE)


# --------------------------------------------------------------------------- the phone reading files itself
def make_pdf() -> bytes:
    """A small PDF made by hand: a plain page, and a compressed page in a two-byte font with a ToUnicode map
    (as Word, LibreOffice and journals make them) whose data ends in a line-ending byte."""
    import zlib
    page2 = "Mendelian randomization of autoimmune disease in human genetics, and single cell genomics"
    codes = {ch: i + 1 for i, ch in enumerate(sorted(set(page2)))}
    cmap = ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /T def\n"
            "1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
            f"{len(codes)} beginbfchar\n" + "".join(f"<{c:04X}> <{ord(ch):04X}>\n" for ch, c in codes.items())
            + "endbfchar endcmap CMapName currentdict /CMap defineresource pop end end")
    hexed = "".join(f"{codes[ch]:04X}" for ch in page2)
    pad = ""
    while True:                                    # make the compressed data end in a line-ending byte
        content2 = zlib.compress(f"BT /F2 12 Tf 72 720 Td <{hexed}> Tj ET{pad}".encode())
        if content2[-1] in (10, 13):
            break
        pad += " "
    content1 = (b"BT /F1 12 Tf 72 720 Td (Statistical genetics and GWAS of lupus, with \\(R\\) and Python.) Tj "
                b"0 -14 Td [(single) -300 (cell RNA-seq)] TJ 0 -14 Td (Smith J, Doe A, Lee K.) Tj ET")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F2 7 0 R >> >> /Contents 8 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(content1) + content1 + b"\nendstream",
        b"<< /Type /Font /Subtype /Type0 /BaseFont /X /Encoding /Identity-H /DescendantFonts [10 0 R] /ToUnicode 9 0 R >>",
        b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(content2) + content2 + b"\nendstream",
        b"<< /Length %d >>\nstream\n" % len(cmap) + cmap.encode() + b"\nendstream",
        b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /X /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity)"
        b" /Supplement 0 >> /DW 500 >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % x for x in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def word_doc() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", '<w:document><w:body><w:p><w:r><w:t>Thesis: GWAS &amp; lupus</w:t></w:r></w:p>'
                   '<w:p><w:r><w:t>Single-cell RNA-seq in R</w:t><w:tab/><w:t>&#233;tude</w:t></w:r></w:p></w:body></w:document>')
    return buf.getvalue()


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_reads_pdf_and_word_files_like_the_desktop(tmp_path):
    pdf, docx = tmp_path / "cv.pdf", tmp_path / "cv.docx"
    pdf.write_bytes(make_pdf())
    docx.write_bytes(word_doc())
    said = phone.run("""
import { documentText, readable } from './lib/doc-text.ts';
out(INPUT.map((f: string) => documentText(new Uint8Array(readFileSync(f)), f)).concat([
  { ok: readable('\\u0003\\u0004 %% ## 12 34'), text: '' }]));
""", [str(pdf), str(docx)])
    p, d, junk = said
    assert "GWAS of lupus, with (R) and Python." in p["text"] and "single cell RNA-seq" in p["text"]
    assert "Mendelian randomization of autoimmune disease" in p["text"], "the two-byte font's map is used"
    assert d["text"] == docx_text(word_doc()) and junk["ok"] is False
    desk = load_cv_text(str(pdf))
    for k in ("keywords", "methods", "coauthors"):
        assert docread.read(desk, WORDS)[k] == docread.read(p["text"], WORDS)[k], k
