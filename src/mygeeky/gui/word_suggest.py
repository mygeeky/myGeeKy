"""Word suggestions under a text box while you type your field (keywords.suggest), as on the phone.

`attach(box)` for a comma-separated list ("gwas, single cell, "): picking a word replaces the one being typed and
leaves the box ready for the next, which then suggests the picked word's closest relatives. `attach(box,
many=False)` for a box that takes one keyword at a time.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QStringListModel, Qt
from PySide6.QtWidgets import QCompleter, QLineEdit

from .. import keywords


class WordSuggest(QObject):
    def __init__(self, box: QLineEdit, many: bool = True) -> None:
        super().__init__(box)
        self.box, self.many = box, many
        self.model = QStringListModel(self)
        self.completer = QCompleter(self.model, self)
        self.completer.setWidget(box)                      # not box.setCompleter: that would replace the whole text
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setMaxVisibleItems(6)
        self.completer.activated[str].connect(self._picked)
        box.textEdited.connect(self.refresh)

    def words(self) -> list[str]:
        text = self.box.text()
        return keywords.suggest(text if self.many else text.replace(",", " "))

    def refresh(self, *_: object) -> None:
        words = self.words()
        self.model.setStringList(words)
        if words and self.box.hasFocus():
            self.completer.complete()
        else:
            self.completer.popup().hide()

    def _picked(self, word: str) -> None:
        self.box.setText(keywords.pick(self.box.text(), word) if self.many else word)
        self.box.setFocus()
        if self.many:
            self.refresh()                                 # the picked word's relatives come up next


def attach(box: QLineEdit, many: bool = True) -> WordSuggest:
    return WordSuggest(box, many)
