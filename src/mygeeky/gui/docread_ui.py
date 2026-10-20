"""⚙ → 📝 From a CV, thesis or abstract: drop a file on it (or choose one), tick what's right, add it to your profile
(docread.py does the finding; the phone has the same in You → Settings, components/doc-drop.tsx). The file is read
on this computer and not kept: only the words you keep are saved, in your keywords and co-authors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFileDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from . import app as logic

TYPES = (".pdf", ".docx", ".txt", ".md", ".tex")


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.hide()
            w.deleteLater()
        elif item.layout():
            _clear(item.layout())


class DocSection(QWidget):
    def __init__(self, cfg, theme: Callable[[], dict[str, Any]], run_async: Callable[..., None],
                 toast: Callable[[str], None]) -> None:
        super().__init__()
        self.cfg, self.theme, self.run_async, self.toast = cfg, theme, run_async, toast
        self.checks: list[tuple[str, QCheckBox]] = []
        self.setAcceptDrops(True)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 6, 0, 0)
        self.lay.setSpacing(4)
        self.render()

    def _label(self, text: str, css: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.PlainText)
        lbl.setStyleSheet(css)
        self.lay.addWidget(lbl)
        return lbl

    def _button(self, text: str, fn: Callable[[], Any]) -> QPushButton:
        t = self.theme()
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(f"QPushButton {{ background:{t['btn_bg']}; color:{t['text']}; border:none; border-radius:9px; "
                        f"padding:5px 10px; text-align:left; }} QPushButton:hover {{ background:{t['btn_hover']}; }}")
        b.clicked.connect(fn)
        self.lay.addWidget(b)
        return b

    def _css(self) -> tuple[str, str]:
        t = self.theme()
        return (f"color:{t['text']}; font-size:10.5px; font-weight:700; letter-spacing:0.5px; background:transparent;",
                f"color:{t['muted']}; font-size:11px; background:transparent;")

    def render(self, note: str = "", chooser: bool = True) -> None:
        _clear(self.lay)
        self.checks = []
        head, muted = self._css()
        self._label("\U0001f4dd FROM A CV, THESIS OR ABSTRACT", head)
        if self.cfg.coauthors:
            self._label("\U0001f465 People you've written with: " + ", ".join(self.cfg.coauthors), muted)
        self._label("Drop a PDF, Word or text file here, or choose one: your field, methods and co-authors are picked "
                    "out, and you keep what's right. Read on this computer; the file isn't kept.", muted)
        self.note = self._label(note, muted)
        self.note.setVisible(bool(note))
        if chooser:
            self._button("\U0001f4c4  Choose a file…", self._choose)

    # ---- a file in
    def _choose(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Your CV, thesis or abstract", str(Path.home()),
                                              "Documents (*.pdf *.docx *.txt *.md *.tex)")
        if path:
            self.read(path)

    def _dropped_path(self, event) -> str:
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        path = urls[0].toLocalFile() if urls else ""
        return path if path.lower().endswith(TYPES) else ""

    def dragEnterEvent(self, event) -> None:  # noqa: N802 -- Qt's naming
        if self._dropped_path(event):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        path = self._dropped_path(event)
        if path:
            self.read(path)

    def read(self, path: str) -> None:
        self.render("Reading it…", chooser=False)
        self.run_async(lambda: logic.doc_read(path), self.show_found)

    # ---- what was found
    def show_found(self, result: Any) -> None:
        result = result if isinstance(result, dict) else {}
        if not result.get("ok"):
            self.render(result.get("error") or "This file couldn't be read. Try a PDF or .docx.")
            return
        self.render("Here's what I found. Untick anything that isn't you:", chooser=False)
        head, muted = self._css()
        t = self.theme()
        for title, kind in (("\U0001f52c Your field", "keywords"), ("\U0001f6e0 Methods and tools", "methods"),
                            ("\U0001f465 People you've written with", "coauthors")):
            words = result["found"].get(kind) or []
            if not words:
                continue
            self._label(title, muted)
            for w in words:
                box = QCheckBox(w)               # plain text: what a document says is never shown as HTML
                box.setChecked(True)
                box.setStyleSheet(       # the box drawn in the theme's colours, so an unticked one shows on dark too
                    f"QCheckBox {{ color:{t['text']}; font-size:11px; background:transparent; spacing:7px; }}"
                    f"QCheckBox::indicator {{ width:14px; height:14px; border:1.5px solid {t['muted']}; border-radius:4px; "
                    f"background:transparent; }}"
                    "QCheckBox::indicator:checked { background:#7a5cff; border-color:#7a5cff; }")
                self.lay.addWidget(box)
                self.checks.append((kind, box))
        self._button("✓  Add to my profile", self._keep)
        self._button("Cancel", lambda: self.render())

    def _keep(self) -> None:
        kept: dict[str, list[str]] = {"keywords": [], "methods": [], "coauthors": []}
        for kind, box in self.checks:
            if box.isChecked():
                kept[kind].append(box.text())
        added = logic.doc_keep(self.cfg, kept["keywords"], kept["methods"], kept["coauthors"])
        msg = f"✓ Added {added} words to your profile" + (
            f" and {len(kept['coauthors'])} co-authors." if kept["coauthors"] else ".")
        self.toast(msg)
        self.render(msg)
