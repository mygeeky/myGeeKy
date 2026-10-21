"""tools/play_check.py: the 16 KB rule is read from the native libraries themselves (no NDK needed)."""

import importlib.util
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("play_check", ROOT / "tools" / "play_check.py")
play_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(play_check)


def _elf(aligns):
    """A minimal 64-bit ELF header with one program header per alignment (LOAD segments)."""
    phoff, phentsize = 64, 56
    head = bytearray(64)
    head[:5] = b"\x7fELF\x02"
    struct.pack_into("<Q", head, 0x20, phoff)
    struct.pack_into("<HH", head, 0x36, phentsize, len(aligns) + 1)
    body = bytearray()
    for a in aligns:
        ph = bytearray(phentsize)
        struct.pack_into("<I", ph, 0, 1)                 # PT_LOAD
        struct.pack_into("<Q", ph, 48, a)
        body += ph
    note = bytearray(phentsize)
    struct.pack_into("<I", note, 0, 4)                   # PT_NOTE: not counted
    struct.pack_into("<Q", note, 48, 4)
    return bytes(head + body + note)


def test_load_segments_are_read_and_others_ignored():
    assert play_check.elf_load_aligns(_elf([0x4000, 0x10000])) == [0x4000, 0x10000]
    assert play_check.elf_load_aligns(_elf([0x1000])) == [0x1000]
    assert play_check.elf_load_aligns(b"not an elf") == []


def test_the_rules_it_enforces_are_the_ones_the_skill_lists():
    skill = (ROOT / ".claude" / "skills" / "mygeeky-play" / "SKILL.md").read_text(encoding="utf-8")
    assert f"Target API {play_check.MIN_TARGET_SDK}" in skill
    assert "android.permission.QUERY_ALL_PACKAGES" in play_check.FORBIDDEN
