"""Grow -> Highlights: research articles retold as short news articles by the maker, and a window to read one
in any of its languages (highlight_shape.py says what a Highlight holds; the phone shows the same in
components/highlights-view.tsx). Everything is plain text: a story comes from the internet's lists.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from .. import highlight_shape as shape
from .app import readable
from .growth_ui import FlowRow


def meta_line(item: dict[str, Any]) -> str:
    """'Nature · 2026-10-02 · open access · led by …' from what was looked up."""
    m = item.get("meta") or {}
    bits = [m.get("journal", ""), m.get("published", ""), "open access" if m.get("open_access") else "",
            f"led by {m['lead']}" if m.get("lead") else ""]
    return " · ".join(b for b in bits if b)


def _label(text: str, css: str, rtl: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.PlainText)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(css)
    if rtl:
        lbl.setLayoutDirection(Qt.RightToLeft)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignAbsolute | Qt.AlignTop)   # absolute: right-to-left would flip it
    return lbl


class HighlightCard(QFrame):
    """One story in the list: its headline, hook and where it was published. Clicking it opens the story."""

    def __init__(self, item: dict[str, Any], theme: dict[str, Any], on_open: Callable[[dict[str, Any]], None]) -> None:
        super().__init__()
        self.setObjectName("hlCard")
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)
        kind = "✨ " + (shape.LABELS["en"]["full"] if item["coverage"] == "full" else shape.LABELS["en"]["abstract"])
        lay.addWidget(_label(kind, f"color:{readable('#ff6fd8', theme)}; font-size:9.5px; font-weight:700; "
                                   "background:transparent;"))
        lay.addWidget(_label(item["title"], f"color:{theme['text']}; font-size:13px; font-weight:700; background:transparent;"))
        if item.get("hook"):
            lay.addWidget(_label(item["hook"], f"color:{theme['text']}; font-size:11px; background:transparent;"))
        if meta_line(item):
            lay.addWidget(_label(meta_line(item), f"color:{theme['muted']}; font-size:10px; background:transparent;"))
        langs = len(shape.languages(item))
        if langs > 1:
            lay.addWidget(_label(f"🌍 readable in {langs} languages", f"color:{theme['muted']}; font-size:10px; "
                                                                      "background:transparent;"))
        self.setStyleSheet(f"#hlCard {{ background:{theme['card_bg']}; border-radius:10px; border-left:3px solid #ff6fd8; }}")
        self.mousePressEvent = lambda ev: on_open(item)  # noqa: ARG005


class HighlightDialog(QDialog):
    """The story: language buttons, the headline and hook, each section under its heading, the tools, and
    a button to the article itself. `on_learn(skill)` turns a skill into a protocol (Grow)."""

    def __init__(self, item: dict[str, Any], theme: dict[str, Any], on_open: Callable[[str], Any],
                 on_learn: Callable[[str], Any] | None = None, parent: QWidget | None = None,
                 warnings: list[str] | None = None) -> None:
        super().__init__(parent)
        self.item, self.theme, self.on_open, self.on_learn = item, theme, on_open, on_learn
        self.setWindowTitle("Highlight")
        self.resize(560, 720)
        self.setStyleSheet(f"QDialog {{ background:{theme.get('solid_bg', '#1c1c2a')}; }}")
        outer = QVBoxLayout(self)
        chips = FlowRow()
        self.chips: dict[str, QPushButton] = {}
        for code, name in shape.languages(item):
            b = QPushButton(name)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{ background:{theme['btn_bg']}; color:{theme['muted']}; border:none; border-radius:9px; "
                f"padding:3px 9px; font-size:10.5px; }} QPushButton:checked {{ background:{theme['section_btn']}; "
                f"color:{theme['text']}; font-weight:700; }}")
            b.clicked.connect(lambda _=False, c=code: self.show_language(c))
            self.chips[code] = b
            chips.add(b)
        outer.addWidget(chips)
        if warnings:
            outer.addWidget(_label("⚠ Check before accepting: " + "; ".join(warnings),
                                   f"color:{readable('#ffc457', theme)}; font-size:11px; background:transparent;"))
        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self.body)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        scroll.viewport().setAutoFillBackground(False)
        self.body.setObjectName("hlBody")
        self.body.setStyleSheet("#hlBody { background:transparent; }")
        outer.addWidget(scroll, 1)
        read = QPushButton("")
        read.setCursor(Qt.PointingHandCursor)
        read.clicked.connect(lambda: on_open(item["url"]))
        read.setStyleSheet("QPushButton { background:#7a5cff; color:#ffffff; border:none; border-radius:10px; "
                           "padding:8px; font-weight:700; }")
        self.read = read
        outer.addWidget(read)
        self.show_language("en")

    def show_language(self, code: str) -> None:
        for c, b in self.chips.items():
            b.setChecked(c == code)
        story = shape.read_in(self.item, code)
        rtl, t, labels = story["rtl"], self.theme, story["labels"]
        while self.body_lay.count():
            w = self.body_lay.takeAt(0).widget()
            if w:
                w.hide()                         # gone at once, not only when Qt gets round to deleting it
                w.deleteLater()
        cover = labels["full"] if self.item["coverage"] == "full" else labels["abstract"]
        self.body_lay.addWidget(_label("✨ " + cover, "color:#ff6fd8; font-size:10px; font-weight:700; background:transparent;", rtl))
        self.body_lay.addWidget(_label(story["title"], f"color:{t['text']}; font-size:18px; font-weight:800; background:transparent;", rtl))
        if story["hook"]:
            self.body_lay.addWidget(_label(story["hook"], f"color:{t['text']}; font-size:13px; font-style:italic; "
                                                          "background:transparent;", rtl))
        if meta_line(self.item):
            self.body_lay.addWidget(_label(meta_line(self.item), f"color:{t['muted']}; font-size:10.5px; background:transparent;"))
        for i, para in enumerate(story["body"]):          # a news article: one idea a paragraph, no headings
            size = "13.5px" if i == 0 else "12.5px"       # the lead a little larger, as papers set it
            self.body_lay.addWidget(_label(para, f"color:{t['text']}; font-size:{size}; line-height:150%; "
                                                 "margin-top:4px; background:transparent;", rtl))
        if self.item.get("skills") and self.on_learn:
            self.body_lay.addWidget(_label(labels["learn"].upper(), "color:#7fd8ff; font-size:10px; font-weight:700; "
                                                                     "margin-top:6px; background:transparent;", rtl))
            row = FlowRow()
            for skill in self.item["skills"]:
                b = QPushButton(f"🧭 {skill}")
                b.setCursor(Qt.PointingHandCursor)
                b.setToolTip("Make it a protocol in Grow")
                b.setStyleSheet(f"QPushButton {{ background:{t['btn_bg']}; color:{t['text']}; border:none; "
                                "border-radius:9px; padding:4px 10px; font-size:11px; }")
                b.clicked.connect(lambda _=False, s=skill: (self.on_learn(s), self.accept()))
                row.add(b)
            self.body_lay.addWidget(row)
        self.body_lay.addStretch(1)
        self.read.setText(f"{labels['read']} ↗")
        self.body.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)


# --------------------------------------------------------------------------- the maker's side (admin tab)
class _DropBox(QWidget):
    """A text box that also takes a dropped PDF (its text is added at the end)."""

    def __init__(self, placeholder: str, on_pdf: Callable[[str], None]) -> None:
        from PySide6.QtWidgets import QPlainTextEdit
        super().__init__()
        self.on_pdf = on_pdf
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setMinimumHeight(120)
        self.edit.setAcceptDrops(False)
        lay.addWidget(self.edit)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, ev) -> None:          # noqa: N802 (Qt)
        if any(u.toLocalFile().lower().endswith(".pdf") for u in ev.mimeData().urls()):
            ev.acceptProposedAction()

    def dropEvent(self, ev) -> None:               # noqa: N802 (Qt)
        for u in ev.mimeData().urls():
            if u.toLocalFile().lower().endswith(".pdf"):
                self.on_pdf(u.toLocalFile())


class EditHighlight(QDialog):
    """Change a draft's English words before accepting it (translations stay as they were written)."""

    def __init__(self, item: dict[str, Any], parent: QWidget | None = None) -> None:
        from PySide6.QtWidgets import QDialogButtonBox, QLineEdit, QPlainTextEdit
        super().__init__(parent)
        self.item = item
        self.setWindowTitle("Edit the Highlight")
        self.resize(560, 720)
        outer = QVBoxLayout(self)
        body = QWidget()
        lay = QVBoxLayout(body)
        self.title, self.hook = QLineEdit(item["title"]), QLineEdit(item.get("hook", ""))
        lay.addWidget(QLabel("Headline"))
        lay.addWidget(self.title)
        lay.addWidget(QLabel("Hook"))
        lay.addWidget(self.hook)
        lay.addWidget(QLabel("The article (a blank line between paragraphs, one idea each)"))
        self.body = QPlainTextEdit("\n\n".join(item["body"]))
        self.body.setMinimumHeight(380)
        lay.addWidget(self.body)
        lay.addWidget(_label("Translations are kept as they were written: write it again for new ones.",
                             "color:#ffc457; font-size:11px;"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def edited(self) -> dict[str, Any]:
        out = dict(self.item)
        out.update(title=self.title.text().strip(), hook=self.hook.text().strip(),
                   body=[p.strip() for p in self.body.toPlainText().split("\n\n") if p.strip()])
        return out


class AdminHighlights(QWidget):
    """Write Highlights: DOIs or links in, the articles' text (or PDFs, or abstracts only), DeepSeek writes and
    translates with the article skill (highlights.py), the maker reads, edits, accepts; Publish sends them."""

    def __init__(self, theme: Callable[[], dict[str, Any]], run_async: Callable[..., None],
                 on_read: Callable[[dict[str, Any], list[str]], None], on_publish: Callable[[], None]) -> None:
        from PySide6.QtWidgets import QCheckBox, QPlainTextEdit
        super().__init__()
        self.theme, self.run_async, self.on_read, self.on_publish = theme, run_async, on_read, on_publish
        self.running = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        # the writing form and the drafts are two widgets, so the admin dashboard can put the form in ✍ Write
        # and the drafts in 📥 Review
        self.form = QWidget()
        lay = QVBoxLayout(self.form)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.links = QPlainTextEdit()
        self.links.setPlaceholderText("DOIs or links to the articles, one per line (doi.org, a journal's page…)")
        self.links.setMaximumHeight(80)
        lay.addWidget(self.links)
        row = QHBoxLayout()
        self.open_btn = QPushButton("🌐 Open the articles")
        self.open_btn.setToolTip("Opens each article's page in your browser, to copy its text")
        self.open_btn.clicked.connect(self.open_all)
        self.pdf_btn = QPushButton("📄 Add a PDF…")
        self.pdf_btn.clicked.connect(self.pick_pdf)
        self.abstract_only = QCheckBox("Abstract only")
        self.abstract_only.setToolTip("No time to copy? Write from each article's abstract (OpenAlex)")
        for w in (self.open_btn, self.pdf_btn, self.abstract_only):
            row.addWidget(w)
        row.addStretch(1)
        lay.addLayout(row)
        self.text = _DropBox("Paste the articles' text here: all of them, one after another (each is found by its "
                             "title). Or drop PDFs here.", self.add_pdf)
        lay.addWidget(self.text)
        self.write_btn = QPushButton("✍ Write the Highlights")
        self.write_btn.clicked.connect(self.write)
        lay.addWidget(self.write_btn)
        self.note = _label("", "font-size:10.5px;")
        lay.addWidget(self.note)
        self.drafts = QWidget()
        self.list = QVBoxLayout(self.drafts)
        self.list.setContentsMargins(0, 0, 0, 0)
        self.list.setSpacing(6)
        outer.addWidget(self.form)
        outer.addWidget(self.drafts)

    # ---- the inputs
    def open_all(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from .. import highlights
        pages = highlights.links(self.links.toPlainText())
        for url in pages[:12]:
            QDesktopServices.openUrl(QUrl(url))
        self.say(f"Opened {min(len(pages), 12)} page(s). Copy each article's text into the box below."
                 if pages else "Paste a DOI or a link first.")

    def pick_pdf(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(self, "Articles as PDF", "", "PDF (*.pdf)")
        for p in paths:
            self.add_pdf(p)

    def add_pdf(self, path: str) -> None:
        from ..text_utils import load_cv_text
        try:
            text = load_cv_text(path)
        except Exception as exc:
            self.say(f"Couldn't read that PDF: {exc}")
            return
        self.text.edit.appendPlainText("\n\n" + text)
        self.say(f"Added {len(text):,} characters from {path.rsplit('/', 1)[-1]}.")

    def say(self, text: str) -> None:
        self.note.setText(text)

    # ---- writing
    def write(self) -> None:
        from .. import highlights
        if self.running:
            return
        links, text, only = self.links.toPlainText(), self.text.edit.toPlainText(), self.abstract_only.isChecked()
        if not highlights.find_dois(links):
            self.say("Paste at least one DOI or a link that holds one.")
            return
        self.running = True
        self.say("Writing… about a minute for each article (the story, then each language).")
        self.render()

        def job() -> dict[str, Any]:
            try:
                return highlights.draft(links, text, only)
            except Exception as exc:
                return {"drafts": [], "errors": [str(exc)]}
        self.run_async(job, self.written)

    def written(self, out: Any) -> None:
        self.running = False
        out = out if isinstance(out, dict) else {}
        made, errors = out.get("drafts") or [], out.get("errors") or []
        self.say((f"Wrote {len(made)} draft(s). " if made else "") + ("; ".join(errors[:4]) if errors else ""))
        if made:
            self.links.clear()
            self.text.edit.clear()
        self.render()

    # ---- the drafts
    def render(self) -> None:
        from .. import highlights
        t = self.theme()
        while self.list.count():
            w = self.list.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.write_btn.setEnabled(not self.running)
        self.write_btn.setText("Writing…" if self.running else "✍ Write the Highlights")
        for b in (self.open_btn, self.pdf_btn, self.write_btn):
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ background:{t['btn_bg']}; color:{t['text']}; border:none; border-radius:9px; "
                            f"padding:5px 10px; }} QPushButton:hover {{ background:{t['btn_hover']}; }}")
        self.note.setStyleSheet(f"color:{t['muted']}; font-size:10.5px; background:transparent;")
        self.abstract_only.setStyleSheet(f"color:{t['text']}; background:transparent;")
        for d in highlights.drafts("new"):
            self.list.addWidget(self._row(d, t))
        n_acc = len(highlights.accepted())
        if n_acc:
            pub = QPushButton(f"🚀 Publish ({n_acc} Highlight{'' if n_acc == 1 else 's'} accepted)")
            pub.setCursor(Qt.PointingHandCursor)
            pub.clicked.connect(self.on_publish)
            pub.setStyleSheet("QPushButton { background:#7a5cff; color:#ffffff; border:none; border-radius:9px; "
                              "padding:6px 10px; font-weight:700; }")
            self.list.addWidget(pub)

    def _row(self, d: dict[str, Any], t: dict[str, Any]) -> QFrame:
        from .. import highlights
        it, warnings = d["item"], d.get("warnings") or []
        frame = QFrame()
        frame.setObjectName("hlDraft")
        frame.setStyleSheet(f"#hlDraft {{ background:{t['card_bg']}; border-radius:10px; }}")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.addWidget(_label(it["title"], f"color:{t['text']}; font-size:12px; font-weight:700; background:transparent;"))
        lay.addWidget(_label(f"{meta_line(it)} · {len(shape.languages(it))} languages · "
                             + ("full text" if it["coverage"] == "full" else "abstract only"),
                             f"color:{t['muted']}; font-size:10px; background:transparent;"))
        if warnings:
            lay.addWidget(_label("⚠ " + "; ".join(warnings[:3]) + (" …" if len(warnings) > 3 else ""),
                                 "color:#ffc457; font-size:10.5px; background:transparent;"))
        row = QHBoxLayout()

        def act(label: str, fn: Callable[[], Any]) -> None:
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ background:{t['btn_bg']}; color:{t['text']}; border:none; border-radius:8px; "
                            "padding:4px 9px; font-size:11px; }")
            b.clicked.connect(fn)
            row.addWidget(b)

        def edit() -> None:
            dlg = EditHighlight(it, self)
            if dlg.exec() and not highlights.set_status(it["id"], "new", dlg.edited()):
                self.say(f"That edit left it too short to show (it needs a headline and {shape.MIN_PARAGRAPHS} paragraphs).")
            self.render()
        act("📖 Read", lambda: self.on_read(it, warnings))
        act("✏ Edit", edit)
        act("✓ Accept", lambda: (highlights.set_status(it["id"], "accepted"), self.render()))
        act("✕ Reject", lambda: (highlights.set_status(it["id"], "rejected"), self.render()))
        row.addStretch(1)
        lay.addLayout(row)
        return frame
