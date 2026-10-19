"""The desktop <-> phone map stays complete, and the drift check notices a one-sided change."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import parity  # noqa: E402


def test_every_phone_file_is_mapped_or_phone_only():
    assert parity.unlisted() == [], "add them to the table in .claude/skills/mygeeky-platforms/SKILL.md"


def test_the_map_points_at_real_files():
    root = parity.ROOT
    for phone, desk in parity.pairs():
        for f in phone + desk:
            assert (root / f).exists(), f


def test_a_one_sided_change_is_flagged_and_a_paired_one_is_not():
    lines = parity.drift({"src/mygeeky/seasons.py"})
    assert any("seasons.py" in l and "and the phone?" in l for l in lines)
    assert parity.drift({"src/mygeeky/seasons.py", "mobile/src/lib/seasons.ts"}) == []
    assert any("and the desktop?" in l for l in parity.drift({"mobile/src/lib/month.ts"}))
