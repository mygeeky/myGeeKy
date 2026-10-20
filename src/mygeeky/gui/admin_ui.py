"""Admin → ✍ Write → 📥 Bring your own answer: paste (or import a .json / .txt file holding) an answer written
anywhere, for a Highlight, listings or quiz questions. admin_import.py checks it exactly like a DeepSeek answer
and queues what passes in Review. The box shows the JSON shape each kind expects and copies the very prompt
myGeeKy gives DeepSeek, so any AI can be asked the same way. Pasted text is never shown as HTML.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QVBoxLayout, QWidget)

from .. import admin_import


def _label(text: str, css: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.PlainText)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(css + " background:transparent;")
    return lbl


class ImportBox(QWidget):
    """Kind, what to paste beside the answer, the answer itself, then Check: the result says what was queued."""

    def __init__(self, theme: Callable[[], dict[str, Any]], run_async: Callable[..., None],
                 protocols: Callable[[], list[tuple[str, str]]], on_done: Callable[[], None]) -> None:
        super().__init__()
        self.theme, self.run_async, self.protocols, self.on_done = theme, run_async, protocols, on_done
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        self.hint = _label("Paste an answer written anywhere (another AI, a colleague, by hand) or import a .json / "
                           ".txt file. It goes through the same checks as DeepSeek's and waits in Review. "
                           "No DeepSeek key needed.", "font-size:10.5px;")
        lay.addWidget(self.hint)
        row = QHBoxLayout()
        self.kind = QComboBox()
        for k, label in admin_import.KINDS.items():
            self.kind.addItem(label, k)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        row.addWidget(self.kind, 1)
        self.copy_btn = QPushButton("📋 Copy the prompt")
        self.copy_btn.setToolTip("The prompt myGeeKy gives DeepSeek for this kind: paste it into any AI")
        self.copy_btn.clicked.connect(self.copy_prompt)
        row.addWidget(self.copy_btn)
        lay.addLayout(row)
        self.protocol = QComboBox()
        lay.addWidget(self.protocol)
        self.link = QLineEdit()
        lay.addWidget(self.link)
        self.source = QPlainTextEdit()
        self.source.setMaximumHeight(90)
        lay.addWidget(self.source)
        self.shape = QPlainTextEdit()
        self.shape.setReadOnly(True)
        self.shape.setMaximumHeight(110)
        self.shape.setToolTip("The JSON the answer must have")
        lay.addWidget(self.shape)
        self.answer = QPlainTextEdit()
        self.answer.setPlaceholderText("The answer: JSON shaped as above (text around it, or a ```json block, is fine)")
        self.answer.setMaximumHeight(140)
        lay.addWidget(self.answer)
        row = QHBoxLayout()
        self.file_btn = QPushButton("📂 Import a file…")
        self.file_btn.clicked.connect(self.pick_file)
        self.check_btn = QPushButton("✓ Check and add to Review")
        self.check_btn.clicked.connect(self.check)
        row.addWidget(self.file_btn)
        row.addStretch(1)
        row.addWidget(self.check_btn)
        lay.addLayout(row)
        self.note = _label("", "font-size:10.5px;")
        lay.addWidget(self.note)
        self._kind_changed()
        self.apply_theme()

    def kind_id(self) -> str:
        return str(self.kind.currentData())

    def _kind_changed(self) -> None:
        k = self.kind_id()
        needs = admin_import.NEEDS[k]
        self.protocol.setVisible(k == "quiz")
        if k == "quiz" and not self.protocol.count():
            for pid, title in self.protocols():
                self.protocol.addItem(title, pid)
        self.link.setPlaceholderText("The source page's https link (one of the protocol's sources)" if k == "quiz"
                                     else needs[0][0])
        self.source.setVisible(k != "quiz")
        self.source.setPlaceholderText(needs[1][0] if len(needs) > 1 else "")
        self.shape.setPlainText(admin_import.shape(k))

    def copy_prompt(self) -> None:
        QApplication.clipboard().setText(admin_import.prompt(self.kind_id()))
        self.say("The prompt is on your clipboard. Paste it into any AI, add the page or article text where it "
                 "says TEXT:, and paste its answer below.")

    def pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "An answer", "", "Answers (*.json *.txt *.md);;All files (*)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                self.answer.setPlainText(f.read(400_000))
            self.say("Loaded. Press ✓ Check and add to Review.")
        except OSError as exc:
            self.say(f"Couldn't read that file: {exc}")

    def say(self, text: str) -> None:
        self.note.setText(text)

    def check(self) -> None:
        k, answer = self.kind_id(), self.answer.toPlainText()
        link, text = self.link.text().strip(), self.source.toPlainText()
        pid = str(self.protocol.currentData() or "")
        self.check_btn.setEnabled(False)
        self.say("Checking…")

        def done(out: dict[str, Any]) -> None:
            self.check_btn.setEnabled(True)
            if out.get("error"):
                self.say(out["error"])
                return
            why = "; ".join(out.get("why") or [])
            self.say(f"{out.get('found', 0)} found · {out.get('added', 0)} added to Review · "
                     f"{out.get('dropped', 0)} dropped" + (f" ({why})" if why else ""))
            if out.get("added"):
                self.answer.clear()
                self.on_done()

        self.run_async(lambda: admin_import.import_answer(k, answer, link, text, pid), done)

    def apply_theme(self) -> None:
        t = self.theme()
        field = (f"background:{t.get('input_bg', 'rgba(128,128,128,30)')}; color:{t['text']}; border:1px solid "
                 f"rgba(128,128,128,60); border-radius:6px; padding:4px; font-size:10.5px;")
        for w in (self.link, self.source, self.answer, self.kind, self.protocol):
            w.setStyleSheet(field)
        self.shape.setStyleSheet(field + " font-family:monospace;")
        for b in (self.copy_btn, self.file_btn, self.check_btn):
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ background:{t['section_btn']}; color:{t['text']}; border:none; "
                            "border-radius:8px; padding:5px 10px; font-size:11px; }")
        for lbl in (self.hint, self.note):
            lbl.setStyleSheet(f"color:{t['muted']}; font-size:10.5px; background:transparent;")
