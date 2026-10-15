"""Quizzes: a protocol's questions, how they're picked and marked, and how a score is shown.

A protocol (protocols.py) turns a skill into stages. A **quiz** draws
questions from a bank for one protocol and marks them here, on your
computer. Nothing is sent anywhere unless you choose to share a score
(leaderboard.py).

**The questions.** The bank ships with myGeeKy (data/questions.json) and is
refreshed from the repo like the curated lists. Each question belongs to one
protocol and one of its stages, and carries the **source** that proves its
answer -- a repo page, a paper, a lab protocol -- and the **sentence quoted
from it**. Every question was written against that source and checked
(tools/quiz/), never from memory.

**The mix.** Each attempt is 10 questions, drawn at random in a fixed mix:

    easy    50%   do you know the basics
    medium  35%   apply it to a small case
    tricky  15%   a mistake people really make

Tricky means a real pitfall ("a band in the no-template control"), never
confusing wording. A new attempt draws different questions, so the bank
can't be memorised in one sitting.

**Your score.** Only your best score per protocol counts, and one attempt
per protocol per day. Protocols differ in difficulty, so a *weighted* score
exists too (`weight_of`): the harder a protocol turns out to be for
everyone, the more it's worth. That's for the leaderboard, and it's for fun.

**Wrong questions.** Every question has a 🚩. Flags are kept here and sent
with your report; the maker's side drops a question that enough different
people flag, or that the best quiz-takers keep missing (tools/quiz/).

State lives in quiz.json (synced):
    {"best": {protocol id: {"score", "at", "questions", "right"}},
     "attempts": [{"protocol", "at", "score"}],      # the last few, for the daily limit
     "flags": [question id], "seen": {question id: n}}
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

from . import curated
from .config import QUESTIONS_FILE, QUIZ_FILE, ensure_dirs
from .files import read_json, write_json

BUNDLED = Path(__file__).parent / "data" / "questions.json"
REMOTE_URL = "https://raw.githubusercontent.com/mygeeky/myGeeKy/main/src/mygeeky/data/questions.json"
CHECK_EVERY_HOURS = 12

LEVELS = ("easy", "medium", "tricky")
MIX = {"easy": 0.50, "medium": 0.35, "tricky": 0.15}      # of one attempt; settings, not law
PER_ATTEMPT = 10
OPTIONS = 4
PASS = 0.75                 # a stage counts as known at this score (protocols.PASS)
PER_DAY = 1                 # attempts per protocol per day
KEEP_ATTEMPTS = 60
LEVEL_LABEL = {"easy": "Basics", "medium": "Applied", "tricky": "Watch out"}
LEVEL_ICON = {"easy": "🟢", "medium": "🔵", "tricky": "🟠"}
# how a question is answered, and how it was checked when it was written
KINDS = {
    "choice": ("🔤", "Multiple choice"),
    "code": ("💻", "What does this code do?"),
}
_QID = re.compile(r"^[a-z0-9][a-z0-9.-]{3,79}$")
ANSWER_CHARS = 16          # of the hex digest: enough that no two options of one question collide


def answer_token(qid: str, option: str) -> str:
    """A short fingerprint of one option, tied to its question.

    The shipped bank stores the *hash* of the right answer, not its position, so the file doesn't
    hand the answers to anyone who opens it. **This is obfuscation, not security**: there are only four
    options, so anyone willing to write five lines of code can hash all four and compare -- and a
    question's own `why` and its quoted sentence usually give the answer away in any case. The honest
    protections are the random draw from a growing bank, one attempt a day, and the maker approving
    anything that reaches the website. A score that cannot be faked needs marking somewhere the person
    can't reach, which myGeeKy has no server for (docs/QUIZZES.md says so plainly)."""
    text = " ".join(str(option or "").split()).strip().lower()
    return hashlib.sha256(f"{qid}\x1f{text}".encode()).hexdigest()[:ANSWER_CHARS]


def hide_answer(q: dict[str, Any]) -> dict[str, Any]:
    """One question with its answer as a hash, the way it is written to the shipped bank."""
    out = {k: v for k, v in q.items() if k != "answer"}
    out["answer_hash"] = answer_token(q["id"], q["options"][int(q["answer"])])
    return out


def share(n: int = PER_ATTEMPT) -> dict[str, int]:
    """How many questions of each level one attempt holds. They always add up to `n`: the shares are
    cut by largest remainder, so 10 questions are 5 easy, 4 medium and 1 tricky, and 20 are 10, 7 and 3."""
    floors = {lv: int(n * MIX[lv]) for lv in LEVELS}
    left = n - sum(floors.values())
    order = sorted(LEVELS, key=lambda lv: (-(n * MIX[lv] - floors[lv]), LEVELS.index(lv)))
    for lv in order[:left]:
        floors[lv] += 1
    return floors


# --------------------------------------------------------------------------- one question, checked
def clean_question(raw: Any) -> dict[str, Any] | None:
    """One checked question, or None. Someone else's text by the time it reaches you."""
    if not isinstance(raw, dict) or not _QID.match(str(raw.get("id", ""))):
        return None
    text = curated._text(raw.get("q"), 400)
    opts = [curated._text(o, 200) for o in raw.get("options") or [] if curated._text(o, 200)][:OPTIONS]
    if not text or len(opts) != OPTIONS or len({o.lower() for o in opts}) != OPTIONS:
        return None
    if raw.get("answer_hash"):                 # the shipped form: the answer is a hash of the option
        want = str(raw["answer_hash"]).strip().lower()
        answer = next((i for i, o in enumerate(opts) if answer_token(str(raw["id"]), o) == want), -1)
    else:                                      # a question being written, before it is hidden
        try:
            answer = int(raw.get("answer"))
        except (TypeError, ValueError):
            return None
    if not 0 <= answer < OPTIONS:
        return None
    level = str(raw.get("level") or "easy").lower()
    kind = str(raw.get("kind") or "choice").lower()
    src = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    return {"id": raw["id"], "protocol": curated._text(raw.get("protocol"), 80),
            "stage": curated._text(raw.get("stage"), 40), "level": level if level in LEVELS else "easy",
            "kind": kind if kind in KINDS else "choice", "q": text,
            "code": str(raw.get("code") or "")[:600] if raw.get("code") else "",
            "options": opts, "answer": answer, "why": curated._text(raw.get("why"), 400),
            "source": {"title": curated._text(src.get("title"), 160), "url": curated._https(src.get("url")),
                       "kind": str(src.get("kind") or "website").lower(), "quote": curated._text(src.get("quote"), 400)},
            "checks": [curated._text(c, 60) for c in raw.get("checks") or []][:8]}


def clean_bank(data: Any) -> dict[str, Any]:
    """The whole bank, checked: {"version", "questions": [...]}"""
    out: dict[str, Any] = {"version": curated._text((data or {}).get("version") if isinstance(data, dict) else "", 40),
                           "questions": []}
    seen: set[str] = set()
    for raw in ((data.get("questions") if isinstance(data, dict) else None) or [])[:20_000]:
        q = clean_question(raw)
        if q and q["id"] not in seen:
            seen.add(q["id"])
            out["questions"].append(q)
    return out


_bank: dict[str, Any] | None = None


def bank(force: bool = False) -> dict[str, Any]:
    """The newest question bank we have: the one shipped, or a newer one fetched since."""
    global _bank
    if _bank is not None and not force:
        return _bank
    options = []
    for fetched, path in ((False, BUNDLED), (True, QUESTIONS_FILE)):
        data = read_json(path, None)
        if isinstance(data, dict):
            options.append((clean_bank(data.get("bank") if fetched else data), fetched))
    _bank = max(options, key=lambda c: (c[0].get("version", ""), c[1]))[0] if options else clean_bank({})
    return _bank


def refresh_if_due(force: bool = False, now: datetime | None = None, timeout: float = 20.0) -> bool:
    """Fetch the newest bank, at most every CHECK_EVERY_HOURS. True if it changed."""
    global _bank
    now = now or datetime.now(timezone.utc)
    cached = read_json(QUESTIONS_FILE, {}) or {}
    if not force:
        try:
            checked = datetime.fromisoformat(cached.get("checked_at", ""))
            if (now - checked).total_seconds() < CHECK_EVERY_HOURS * 3600:
                return False
        except (TypeError, ValueError):
            pass
    r = requests.get(REMOTE_URL, timeout=timeout, headers={"User-Agent": "mygeeky"})
    if getattr(r, "status_code", 200) == 404:          # not published yet: what shipped is all there is
        ensure_dirs()
        write_json(QUESTIONS_FILE, {**(cached if isinstance(cached, dict) else {}),
                                    "checked_at": now.isoformat(timespec="seconds")})
        return False
    r.raise_for_status()
    if len(r.content) > 8_000_000:
        raise ValueError("the question bank is unexpectedly large")
    fresh = clean_bank(r.json())
    changed = fresh != clean_bank(cached.get("bank")) if isinstance(cached, dict) else True
    ensure_dirs()
    write_json(QUESTIONS_FILE, {"checked_at": now.isoformat(timespec="seconds"), "bank": fresh})
    _bank = None
    return changed


def for_protocol(pid: str, based_on: str = "", data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Every question for this protocol (a protocol you changed keeps the questions of the one it came from)."""
    rows = (data or bank())["questions"]
    ids = {x for x in (pid, based_on) if x}
    return [q for q in rows if q["protocol"] in ids]


def counts(pid: str, based_on: str = "", data: dict[str, Any] | None = None) -> dict[str, int]:
    """How many questions there are, per level: {"easy": n, ..., "total": n}."""
    qs = for_protocol(pid, based_on, data)
    out = {lv: sum(1 for q in qs if q["level"] == lv) for lv in LEVELS}
    out["total"] = len(qs)
    return out


# --------------------------------------------------------------------------- how a question is shown
@dataclass
class Question:
    """One question as it's shown: what kind it is and how hard, the question (with its code or
    numbers set apart), four answers, and -- once you've answered -- whether you were right, why,
    and the source that proves it, with the sentence quoted from it."""
    id: str
    number: int                 # its place in this attempt (1..10)
    of: int
    protocol: str
    stage: str
    stage_title: str            # the step it belongs to, in words
    level: str                  # easy, medium, tricky
    level_label: str            # "Basics", "Applied", "Watch out"
    level_icon: str
    kind: str                   # choice or code
    kind_icon: str
    kind_label: str
    text: str
    code: str                   # shown as code, when there is any
    options: list[str]
    answer: int                 # the right one, in the order shown
    picked: int | None = None   # what you chose, once you have
    why: str = ""               # why that answer is right, shown after you answer
    source_title: str = ""
    source_url: str = ""
    source_kind: str = "website"
    source_quote: str = ""
    flagged: bool = False

    @property
    def answered(self) -> bool:
        return self.picked is not None

    @property
    def right(self) -> bool:
        return self.picked == self.answer

    @property
    def source(self):
        """The source as a Resource card, like a protocol's links (protocols.Resource)."""
        from .protocols import Resource
        if not self.source_url:
            return None
        # the quote is shown above the card in its own right, so the card itself stays plain
        return Resource.from_link({"title": self.source_title or self.source_url, "url": self.source_url,
                                   "kind": self.source_kind, "note": ""})

    @classmethod
    def build(cls, q: dict[str, Any], number: int, of: int, order: list[int] | None = None,
              stage_title: str = "", flagged: bool = False) -> "Question":
        """One question, its options in the order they'll be shown (`order`: shuffled by Quiz)."""
        order = list(order) if order else list(range(len(q["options"])))
        src = q.get("source") or {}
        return cls(id=q["id"], number=number, of=of, protocol=q["protocol"], stage=q["stage"],
                   stage_title=stage_title or q["stage"], level=q["level"],
                   level_label=LEVEL_LABEL[q["level"]], level_icon=LEVEL_ICON[q["level"]], kind=q["kind"],
                   kind_icon=KINDS[q["kind"]][0], kind_label=KINDS[q["kind"]][1], text=q["q"],
                   code=q.get("code", ""), options=[q["options"][i] for i in order],
                   answer=order.index(q["answer"]), why=q.get("why", ""), source_title=src.get("title", ""),
                   source_url=src.get("url", ""), source_kind=src.get("kind", "website"),
                   source_quote=src.get("quote", ""), flagged=flagged)


@dataclass
class Quiz:
    """One attempt at a protocol: the questions drawn for it, in the mix, with their options shuffled."""
    protocol: str
    title: str
    questions: list[Question] = field(default_factory=list)
    pass_mark: float = PASS

    @property
    def total(self) -> int:
        return len(self.questions)

    @classmethod
    def draw(cls, proto: dict[str, Any], data: dict[str, Any] | None = None, n: int = PER_ATTEMPT,
             rng: random.Random | None = None, flags: Iterable[str] = (), stage: str = "") -> "Quiz":
        """Draw a quiz for a protocol: `n` questions in the MIX, from its own bank.

        `stage`: only that step's questions (the level check for one stage). Flagged questions are
        left out. If a level runs short, the rest is filled from the other levels, so a small bank
        still gives a full quiz."""
        rng = rng or random.Random()
        flagged = set(flags)
        titles = {st["id"]: st["title"] for st in proto.get("stages") or []}
        pool = [q for q in for_protocol(proto["id"], proto.get("based_on", ""), data)
                if q["id"] not in flagged and (not stage or q["stage"] == stage)]
        by_level: dict[str, list[dict[str, Any]]] = {lv: [] for lv in LEVELS}
        for q in pool:
            by_level[q["level"]].append(q)
        for rows in by_level.values():
            rng.shuffle(rows)
        picked: list[dict[str, Any]] = []
        for lv, want in share(n).items():
            picked.extend(by_level[lv][:want])
        rest = [q for lv in LEVELS for q in by_level[lv][len([p for p in picked if p["level"] == lv]):]]
        rng.shuffle(rest)
        picked.extend(rest[:max(0, n - len(picked))])
        picked = picked[:n]
        rng.shuffle(picked)
        questions = []
        for i, q in enumerate(picked, 1):
            order = list(range(len(q["options"])))
            rng.shuffle(order)
            questions.append(Question.build(q, i, len(picked), order, titles.get(q["stage"], ""), False))
        return cls(protocol=proto["id"], title=proto.get("title") or proto["id"], questions=questions)


@dataclass
class Attempt:
    """What you scored: the questions with your answers, the score, and how each step went."""
    protocol: str
    title: str
    questions: list[Question]
    right: int
    total: int
    score: float                 # 0..1
    passed: bool
    best: float                  # your best score for this protocol, after this attempt
    improved: bool
    by_stage: list[dict[str, Any]] = field(default_factory=list)
    by_level: list[dict[str, Any]] = field(default_factory=list)

    @property
    def percent(self) -> int:
        return round(self.score * 100)

    @property
    def perfect(self) -> bool:
        return self.total > 0 and self.right == self.total


def mark(quiz: Quiz, answers: list[int], best_before: float = 0.0) -> Attempt:
    """Mark an attempt. `answers`: what was picked per question (-1 for none)."""
    for q, a in zip(quiz.questions, list(answers) + [-1] * len(quiz.questions)):
        q.picked = None if a is None or a < 0 else int(a)
    right = sum(1 for q in quiz.questions if q.right)
    total = len(quiz.questions)
    score = right / total if total else 0.0
    groups: dict[str, dict[str, Any]] = {}
    for q in quiz.questions:
        g = groups.setdefault(q.stage, {"stage": q.stage, "title": q.stage_title, "right": 0, "total": 0})
        g["total"] += 1
        g["right"] += 1 if q.right else 0
    levels = []
    for lv in LEVELS:
        rows = [q for q in quiz.questions if q.level == lv]
        if rows:
            levels.append({"level": lv, "label": LEVEL_LABEL[lv], "icon": LEVEL_ICON[lv],
                           "right": sum(1 for q in rows if q.right), "total": len(rows)})
    return Attempt(protocol=quiz.protocol, title=quiz.title, questions=quiz.questions, right=right, total=total,
                   score=round(score, 4), passed=score >= quiz.pass_mark, best=round(max(score, best_before), 4),
                   improved=score > best_before, by_stage=list(groups.values()), by_level=levels)


# --------------------------------------------------------------------------- your scores (this computer, synced)
def _load() -> dict[str, Any]:
    data = read_json(QUIZ_FILE, {}) or {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("best", {})
    data.setdefault("attempts", [])
    data.setdefault("flags", [])
    data.setdefault("seen", {})
    return data


def _save(state: dict[str, Any]) -> None:
    ensure_dirs()
    write_json(QUIZ_FILE, state)


def best(pid: str = "") -> Any:
    """Your best score for one protocol ({"score", "at", ...} or None), or all of them."""
    rows = _load()["best"]
    return rows.get(pid) if pid else rows


def flags() -> list[str]:
    return list(_load()["flags"])


def attempts_today(pid: str, today: date | None = None) -> int:
    today = (today or date.today()).isoformat()
    return sum(1 for a in _load()["attempts"] if a.get("protocol") == pid and str(a.get("at", ""))[:10] == today)


def can_try(pid: str, today: date | None = None) -> tuple[bool, str]:
    """May you try this protocol now? One attempt a day, so a score means something."""
    if attempts_today(pid, today) < PER_DAY:
        return True, ""
    return False, "You've already taken this quiz today. Your best score counts, so try again tomorrow."


def record(attempt: Attempt, today: date | None = None) -> dict[str, Any]:
    """Keep an attempt: the best score per protocol, and the attempt itself (for the daily limit)."""
    state = _load()
    now = (today or date.today()).isoformat()
    row = state["best"].get(attempt.protocol) or {}
    if attempt.score >= float(row.get("score") or 0.0):
        state["best"][attempt.protocol] = {"score": attempt.score, "at": now, "title": attempt.title,
                                           "right": attempt.right, "questions": attempt.total}
    state["attempts"] = (state["attempts"] + [{"protocol": attempt.protocol, "at": now,
                                               "score": attempt.score}])[-KEEP_ATTEMPTS:]
    for q in attempt.questions:
        state["seen"][q.id] = int(state["seen"].get(q.id) or 0) + 1
    _save(state)
    return state["best"][attempt.protocol]


def flag(qid: str, on: bool = True) -> bool:
    """🚩 this question looks wrong (or take the flag back). It's left out of your next attempts."""
    state = _load()
    have = set(state["flags"])
    if on:
        have.add(qid)
    else:
        have.discard(qid)
    state["flags"] = sorted(have)[:500]
    _save(state)
    return qid in have


def report_question(q: Question, reason: str = "") -> str:
    """A prefilled issue telling the maker a question is wrong (you press Submit, your own account)."""
    from . import ideas
    body = (f"This quiz question looks wrong.\n\n- question: `{q.id}`\n- protocol: `{q.protocol}`\n"
            f"- step: {q.stage_title}\n\n> {q.text}\n\n"
            f"Answers shown: {'; '.join(q.options)}\n\nWhat's wrong: {reason or ''}\n")
    return ideas.issue_url("report", f"Quiz question looks wrong: {q.text[:70]}", body, include_version=False)


# --------------------------------------------------------------------------- comparing protocols, for fun
def weight_of(pid: str, difficulty: dict[str, float] | None = None, data: dict[str, Any] | None = None) -> float:
    """How much a protocol counts, 1.0-2.0. Harder protocols count more.

    `difficulty` is the average score everyone gets on each protocol (from the published leaderboard,
    when there is one): the lower it is, the heavier the protocol. Until there's enough of that, the
    share of tricky questions in its bank stands in for it."""
    avg = (difficulty or {}).get(pid)
    if avg is None:
        c = counts(pid, "", data)
        avg = 0.85 - 0.5 * (c["tricky"] / c["total"]) if c["total"] else 0.8
    return round(1.0 + max(0.0, min(1.0, (0.9 - float(avg)) / 0.5)), 2)


def weighted(scores: dict[str, float], difficulty: dict[str, float] | None = None,
             data: dict[str, Any] | None = None) -> float:
    """Someone's score across protocols, weighted by how hard each one is. For the leaderboard."""
    if not scores:
        return 0.0
    total = sum(s * weight_of(pid, difficulty, data) for pid, s in scores.items())
    return round(total / sum(weight_of(pid, difficulty, data) for pid in scores), 4)


# --------------------------------------------------------------------------- the maker's side
def problems(data: Any) -> list[str]:
    """What's wrong with a hand-edited bank, in plain words (empty: all good). Used by tools/quiz."""
    if not isinstance(data, dict):
        return ["The file must hold one JSON object."]
    out, ids = [], set()
    rows = data.get("questions")
    if not isinstance(rows, list):
        return ["'questions' must be a list."]
    for i, raw in enumerate(rows):
        label = f"questions[{i}]"
        q = clean_question(raw)
        if not q:
            out.append(f"{label}: not a usable question (needs an id, a question, {OPTIONS} different "
                       "options and the number of the right one)")
            continue
        label = f"question '{q['id']}'"
        if q["id"] in ids:
            out.append(f"{label}: the same id appears twice")
        ids.add(q["id"])
        if not q["protocol"]:
            out.append(f"{label}: no protocol")
        if not q["source"]["url"]:
            out.append(f"{label}: no source")
        # A code question proves itself when it is run; everything else must quote the sentence on its
        # source page that proves the answer.
        elif not q["source"]["quote"] and q["kind"] != "code":
            out.append(f"{label}: no sentence quoted from its source")
        if not q["why"]:
            out.append(f"{label}: doesn't say why the answer is right")
    return out[:50]


def main(argv: list[str] | None = None) -> int:
    """python -m mygeeky.quiz check [questions.json]   (maker side)"""
    import sys
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] != "check":
        print(main.__doc__)
        return 2
    path = Path(args[1]) if len(args) > 1 else BUNDLED
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    found = problems(data)
    cleaned = clean_bank(data)
    print(f"{len(cleaned['questions'])} questions in {path}")
    per = {}
    for q in cleaned["questions"]:
        per.setdefault(q["protocol"], {lv: 0 for lv in LEVELS})[q["level"]] += 1
    for pid, c in sorted(per.items()):
        print(f"  {pid}: " + ", ".join(f"{n} {lv}" for lv, n in c.items()) + f"  (weight {weight_of(pid, None, cleaned)})")
    for p in found:
        print(f"  ! {p}")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
