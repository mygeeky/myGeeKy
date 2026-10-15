"""Check a hand-written batch of questions and add it to the shipped bank (maker side).

    python tools/quiz/add.py batch.json            # check only, say what's wrong
    python tools/quiz/add.py batch.json --write    # check, then add to src/mygeeky/data/questions.json

A batch is a JSON list of questions in the plain form (`answer` as a position). Every one is put through
the same checks the DeepSeek writer uses -- the shape rules, the quote really on the source page, code
actually run, nothing about laboratory work -- and the answers are hashed on the way into the bank, so the
file never shows which option is right (docs/QUIZZES.md).

Nothing is written unless every question passes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from mygeeky import curated, protocols, quiz, quizwriter, safety  # noqa: E402

MOBILE = ROOT / "mobile" / "src" / "data" / "questions.json"
CACHE = Path(__file__).with_name(".cache")


def page(url: str, session: requests.Session) -> str:
    """The same text sources.py cached, so a check costs no requests."""
    import hashlib
    f = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:20] + ".txt")
    if f.exists():
        return f.read_text(encoding="utf-8")
    CACHE.mkdir(exist_ok=True)
    text = quizwriter._page_text(url, session)
    f.write_text(text, encoding="utf-8")
    return text


def main() -> int:
    path = Path(sys.argv[1])
    write = "--write" in sys.argv
    batch = json.loads(path.read_text(encoding="utf-8"))
    bank = quiz.bank()
    known = {q["q"] for q in bank["questions"]}
    reviewed = {p["id"]: p for p in protocols.reviewed(curated.load())}
    bad = 0
    with requests.Session() as session:
        for raw in batch:
            notes = []
            proto = reviewed.get(raw.get("protocol", ""))
            if not proto:
                notes.append("no such reviewed protocol")
            elif raw.get("stage") not in {st["id"] for st in proto["stages"]}:
                notes.append(f"no step '{raw.get('stage')}' in that protocol")
            else:
                # the protocol links a book's front page; a question may quote a chapter of that same book
                host = safety._host(raw["source"]["url"])
                links = [it["url"] for st in proto["stages"] for it in st["items"]]
                if not any(u == raw["source"]["url"] or raw["source"]["url"].startswith(u.rstrip("/") + "/")
                           or safety._host(u) == host for u in links):
                    notes.append("its source isn't one of that protocol's own links (nor a page of one)")
            why = quizwriter.rules_ok(raw)
            if why:
                notes.append(why)
            text = " ".join([raw.get("q", ""), *(raw.get("options") or []), raw.get("why", ""),
                             raw["source"].get("quote", "")])
            if safety.is_bench(text) or safety.blocked_source(raw["source"]["url"]):
                notes.append("laboratory work: myGeeKy doesn't teach it")
            quote = raw["source"].get("quote") or ""
            if quote:
                body = page(raw["source"]["url"], session)
                if not body:
                    notes.append("the source page wouldn't open (check the quote by hand)")
                elif not quizwriter.quoted(quote, body):
                    notes.append("the quote is NOT on the source page")
            elif raw.get("kind") != "code":
                notes.append("no quote, and not a question a computer can check")
            ran, note = quizwriter.code_check(raw)
            if ran is False:
                notes.append(f"the code doesn't do that ({note})")
            if quizwriter.too_similar(raw.get("q", ""), list(known)):
                notes.append("almost the same as a question already in the bank")
            if not quiz.clean_question(raw):
                notes.append("wouldn't survive the shape check")
            print(f"  {'ok ' if not notes else '!  '}{raw.get('id', '?'):34s} {raw.get('level', ''):7s} "
                  + ("; ".join(notes) if notes else ""))
            bad += 1 if notes else 0
    print(f"{len(batch)} questions, {bad} to fix")
    if bad or not write:
        return 1 if bad else 0
    added = quizwriter.add_to_bank([dict(q) for q in batch])
    data = Path(quiz.BUNDLED).read_text(encoding="utf-8")
    MOBILE.write_text(data, encoding="utf-8")
    print(f"added {added['added']}, the bank now holds {added['total']} (phone copy updated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
