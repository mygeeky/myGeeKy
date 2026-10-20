"""Small text-loading helpers (CV ingestion)."""

from __future__ import annotations

from pathlib import Path


DOCUMENT_TYPES = ("pdf", "docx", "txt", "md", "tex")
MAX_PAGES = 80            # a thesis's field shows long before page 80 (the phone reads as many: lib/doc-text.ts)


def docx_text(data: bytes) -> str:
    """The text of a Word document: its paragraphs, one per line (a .docx is a zip of XML)."""
    import html
    import io
    import re
    import zipfile
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    xml = re.sub(r"</w:p>|<w:br\s*/>|<w:cr\s*/>", "\n", xml)
    xml = re.sub(r"<w:tab\s*/>", " ", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


def load_cv_text(path: str) -> str:
    """Load a CV, thesis or abstract as text: .pdf, .docx (Word), or plain text (.txt, .md, .tex)."""
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"CV file not found: {p}")

    if p.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError(
                "Reading a .pdf CV needs pypdf, which normally comes with myGeeKy.\n"
                "Install it with: pip install pypdf\n"
                "Or export your CV as .txt/.md and point mygeeky at that instead."
            ) from exc
        reader = PdfReader(str(p))
        return "\n".join(page.extract_text() or "" for page in reader.pages[:MAX_PAGES])

    if p.suffix.lower() == ".docx":
        return docx_text(p.read_bytes())
    return p.read_text(encoding="utf-8", errors="ignore")
