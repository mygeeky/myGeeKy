"""Fetch a protocol's own sources and print sentences worth quoting (maker side, not shipped).

    python tools/quiz/sources.py git-github-teamwork          # one protocol
    python tools/quiz/sources.py --list                        # what there is to write for

Questions must be answerable from the source and must quote the sentence that proves the answer
(docs/QUIZZES.md), so this is the first step whether the questions are written by hand or by DeepSeek:
it puts the real text in front of whoever is writing.

Pages are cached under tools/quiz/.cache so rewriting a batch costs nothing.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from mygeeky import curated, protocols, quiz, quizwriter, safety  # noqa: E402

CACHE = Path(__file__).with_name(".cache")
MIN, MAX = 45, 260          # a sentence worth quoting: long enough to prove something, short enough to show


def page_text(url: str, session: requests.Session) -> str:
    CACHE.mkdir(exist_ok=True)
    f = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:20] + ".txt")
    if f.exists():
        return f.read_text(encoding="utf-8")
    text = quizwriter._page_text(url, session)
    f.write_text(text, encoding="utf-8")
    return text


def sentences(text: str) -> list[str]:
    out, seen = [], set()
    for raw in re.split(r"(?<=[.!?])\s+|\n{2,}", re.sub(r"[ \t]+", " ", text)):
        s = " ".join(raw.split())
        if not MIN <= len(s) <= MAX or s.lower() in seen:
            continue
        if s.count("|") > 2 or s.count("#") > 2 or "cookie" in s.lower():
            continue
        if not re.search(r"[a-z]{4}", s):
            continue
        seen.add(s.lower())
        out.append(s)
    return out


def main() -> int:
    data = curated.load()
    reviewed = {p["id"]: p for p in protocols.reviewed(data)}
    have = {}
    for q in quiz.bank()["questions"]:
        have[q["protocol"]] = have.get(q["protocol"], 0) + 1
    if "--list" in sys.argv or len(sys.argv) < 2:
        for pid, p in reviewed.items():
            print(f"  {have.get(pid, 0):3d} questions  {pid:26s} {p['title']}")
        return 0
    pid = sys.argv[1]
    proto = reviewed.get(pid)
    if not proto:
        print(f"no reviewed protocol '{pid}'")
        return 2
    want = sys.argv[2] if len(sys.argv) > 2 else ""
    print(f"### {proto['id']}: {proto['title']}  ({have.get(pid, 0)} questions so far)\n")
    with requests.Session() as session:
        for st in proto["stages"]:
            if st["role"] == "use":
                continue
            print(f"\n== STEP {st['id']}: {st['title']}")
            for it in st["items"]:
                if safety.blocked_source(it["url"]):
                    continue
                text = page_text(it["url"], session)
                rows = sentences(text)
                if want:
                    rows = [s for s in rows if want.lower() in s.lower()]
                print(f"\n-- {it['title']}  <{it['url']}>  ({len(text)} chars, {len(rows)} usable)")
                for s in rows[:28]:
                    print(f"   {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
