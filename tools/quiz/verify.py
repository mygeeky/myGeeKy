"""Check the shipped question bank the same way the writer does (maker side).

    python tools/quiz/verify.py                 # the bundled bank
    python tools/quiz/verify.py path.json       # another file

For every question: the shape rules, the quote really on its source page, code
actually run, sums redone, and the bank's own checks (`quiz.problems`). It is
the test that catches a source page that has changed since a question was
written, so run it before a release.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from mygeeky import quiz, quizwriter, safety  # noqa: E402


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else quiz.BUNDLED
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("questions") or []
    print(f"{len(rows)} questions in {path.name}")
    bad = 0
    pages: dict[str, str] = {}
    with requests.Session() as session:
        for raw in rows:
            notes = []
            # the shipped bank hides the answer behind a hash: read it back before checking anything
            q = quiz.clean_question(raw)
            if q is None:
                print(f"  !  {raw.get('id', '?'):34s} not a usable question (its answer doesn't match any option?)")
                bad += 1
                continue
            why = quizwriter.rules_ok(q)
            if why:
                notes.append(why)
            url = (q.get("source") or {}).get("url") or ""
            quote = (q.get("source") or {}).get("quote") or ""
            if quote:
                if url not in pages:
                    pages[url] = quizwriter._page_text(url, session)
                if not pages[url]:
                    notes.append("source page wouldn't open (kept: check it by hand)")
                elif not quizwriter.quoted(quote, pages[url]):
                    notes.append("the quote is NOT on the source page any more")
            elif q.get("kind") != "code":
                notes.append("no quote, and not a question a computer can check")
            text = " ".join([q.get("q", ""), *(q.get("options") or []), q.get("why", ""),
                             (q.get("source") or {}).get("quote", "")])
            if safety.is_bench(text) or safety.blocked_source((q.get("source") or {}).get("url", "")):
                notes.append("it is about laboratory work, which myGeeKy doesn't teach")
            ran, note = quizwriter.code_check(q)
            if ran is False:
                notes.append(f"the code doesn't do that ({note})")
            elif ran is None and q.get("kind") == "code":
                notes.append("code couldn't be run here (needs R, or check by hand)")
            mark = "ok " if not notes else "!  "
            if notes:
                bad += 1
            print(f"  {mark}{q['id']:34s} {q.get('level', ''):7s} {q.get('kind', ''):6s} "
                  + ("; ".join(notes) if notes else ""))
    problems = quiz.problems(data)
    for p in problems:
        print(f"  ! {p}")
    per: dict[str, dict[str, int]] = {}
    for q in quiz.clean_bank(data)["questions"]:
        per.setdefault(q["protocol"], {lv: 0 for lv in quiz.LEVELS})[q["level"]] += 1
    for pid, c in sorted(per.items()):
        print(f"  {pid}: " + ", ".join(f"{n} {lv}" for lv, n in c.items())
              + f"  (weight {quiz.weight_of(pid, None, quiz.clean_bank(data))})")
    print(f"{bad} question(s) to look at, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
