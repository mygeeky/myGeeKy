"""Re-applying the theme (every sync does) keeps the app's font list the same size. It used to add the theme's
fonts in front of the last list each time; after a few hundred names Qt stopped finding ⚙ and ⟩, and the header's
Settings and fold buttons showed empty boxes (Windows and Linux)."""
from __future__ import annotations

from mygeeky.config import MyGeekyConfig


def test_applying_the_theme_again_and_again_keeps_one_font_list(qapp_offscreen):
    from PySide6.QtWidgets import QApplication
    from mygeeky.gui.app import THEMES
    from mygeeky.gui.qt_panel import MyGeekyPanel
    p = MyGeekyPanel(MyGeekyConfig(keywords=["gwas"]))
    try:
        p._apply_theme()
        first = QApplication.instance().font().families()
        for _ in range(30):
            p._apply_theme()                       # what _apply_synced_data does after each sync
        assert QApplication.instance().font().families() == first
        assert len(first) == len(set(first))       # no name twice
        theme_fonts = THEMES[p._theme_name()].get("font") or []
        assert first[:len(theme_fonts)] == list(dict.fromkeys(theme_fonts))
    finally:
        p.close()
