"""Every text on the panel must be readable in every theme -- started in it, or switched to it from Midnight.

tools/theme_audit.py opens every page and part, and compares each label's and button's text colour with the colour
really painted behind it. White text left behind on Frosted, a group's bright pink on a light page, a button whose
text matches its accent background: each is reported by name."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_readable_darkens_on_light_themes_and_lightens_on_dark_ones():
    from mygeeky.gui.app import THEMES, contrast_ratio, readable
    for name, t in THEMES.items():
        for color in ("#ffc457", "#f472b6", "#4ade80", "#7fd8ff", "#15151f", "#ffffff"):
            out = readable(color, t)
            assert contrast_ratio(out, t["solid_bg"]) >= 3.5, (name, color, out)
    assert readable("#241f1a", THEMES["frosted"]) == "#241f1a"          # already readable: left alone


def test_every_text_is_readable_in_the_light_theme():
    pytest.importorskip("PySide6")
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "theme_audit.py"), "frosted", "--json"],
                         capture_output=True, text=True, timeout=600, cwd=ROOT,
                         env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"})
    assert out.returncode == 0, out.stderr[-800:]
    found = json.loads(out.stdout)
    assert found == [], "\n".join(f"{f['how']} {f['tab']}: {f['text']} ({f['fg']} on {f['bg']}, {f['contrast']})" for f in found)
