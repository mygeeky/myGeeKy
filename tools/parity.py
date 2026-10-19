"""The desktop <-> phone map, as code: which files must change together, which side changed alone, which pairs
have a matching test. The map itself is the table in .claude/skills/mygeeky-platforms/SKILL.md (one source).

    python tools/parity.py drift [BASE]   # shared files changed on one side only since BASE (default origin/main)
    python tools/parity.py coverage       # each pair, and the test that checks both sides agree (if any)
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "mygeeky-platforms" / "SKILL.md"
PHONE_DIR, DESK_DIR = "mobile/src/", "src/mygeeky/"
_CODE = re.compile(r"`([^`]+)`")


def _phone_path(name: str) -> str:
    """A name from the table as a path: written with its folder, or found in lib/, components/ or app/."""
    if name.startswith(("components/", "app/", "lib/")):
        return PHONE_DIR + name
    for folder in ("lib/", "components/", "app/"):
        if (ROOT / PHONE_DIR / folder / name).exists():
            return PHONE_DIR + folder + name
    return PHONE_DIR + "lib/" + name


def pairs() -> list[tuple[list[str], list[str]]]:
    """[(phone files, desktop files)] from the skill's table: one row each."""
    text = SKILL.read_text(encoding="utf-8")
    table = text.split("## Desktop ↔ phone: files that must change together", 1)[1].split("\n## ", 1)[0]
    out = []
    for line in table.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 2 or not cells[0].startswith("`"):
            continue
        phone = [_phone_path(c) for c in _CODE.findall(cells[0]) if c.endswith((".ts", ".tsx"))]
        desk = [DESK_DIR + c for c in _CODE.findall(cells[1]) if c.endswith(".py")]
        if phone and desk:
            out.append((phone, desk))
    return out


def phone_only() -> set[str]:
    text = SKILL.read_text(encoding="utf-8")
    line = next((l for l in text.splitlines() if l.startswith("Phone-only plumbing")), "")
    return {_phone_path(c) for c in _CODE.findall(line)}


def unlisted() -> list[str]:
    """Phone lib files in neither the table nor the phone-only line."""
    known = {p for ph, _ in pairs() for p in ph} | phone_only()
    return sorted(str(f.relative_to(ROOT)) for f in (ROOT / PHONE_DIR / "lib").glob("*.ts")
                  if str(f.relative_to(ROOT)) not in known)


def changed(base: str) -> set[str]:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], cwd=ROOT, capture_output=True, text=True)
    local = subprocess.run(["git", "diff", "--name-only", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return {l for l in (out.stdout + local.stdout).splitlines() if l}


def drift(files: set[str]) -> list[str]:
    """One line per pair where only one side is among `files`."""
    lines = []
    for phone, desk in pairs():
        p, d = [f for f in phone if f in files], [f for f in desk if f in files]
        if p and not d:
            lines.append(f"phone changed ({', '.join(p)}) but not the desktop ({', '.join(desk)}): and the desktop?")
        elif d and not p:
            lines.append(f"desktop changed ({', '.join(d)}) but not the phone ({', '.join(phone)}): and the phone?")
    return lines


def coverage() -> list[tuple[str, str]]:
    tests = {t.name: t.read_text(encoding="utf-8") for t in (ROOT / "tests").glob("test_*.py")
             if t.name != "test_parity_map.py"}
    out = []
    for phone, _desk in pairs():
        stems = [Path(p).stem for p in phone]
        hit = sorted(n for n, body in tests.items()
                     if any(re.search(rf"\b{re.escape(s)}\.tsx?\b|lib/{re.escape(s)}\b|/{re.escape(s)}\.ts", body) for s in stems))
        out.append((", ".join(Path(p).name for p in phone), ", ".join(hit) or "-- no matching test yet"))
    return out


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "drift"
    if cmd == "coverage":
        for pair, test in coverage():
            print(f"{pair:55} {test}")
        return 0
    lines = drift(changed(argv[1] if len(argv) > 1 else "origin/main"))
    for line in lines:
        print(f"::warning::{line}" if "--github" in argv else f"⚠ {line}")
    if not lines:
        print("Both sides changed together (or nothing shared changed).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
