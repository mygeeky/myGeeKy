"""The maker's quiz writer: DeepSeek writes questions from a protocol's own sources, and myGeeKy checks them.

Maker side only (the admin tab, 📝 Quizzes), like the listing scout. The key
lives in the system's credential store, never in a file, and never ships in
the app.

The point is **little review from the maker**. A question only survives if it
passes checks a computer can make:

  1. **Written from one real source.** Each question is written against one
     link in that protocol's step (a repo page, a paper, a lab protocol) and
     must quote the sentence from it that proves the answer. myGeeKy fetches
     the page and checks the quote is really on it (`quoted`).
  2. **Answered blind, twice.** A second call gets the question without the
     answer, with the options shuffled differently each time. It has to pick
     the right one **both** times, and to agree the question is clear and has
     exactly one right answer. Anything else is dropped: one disagreement out
     of two is enough.
  3. **Code is run.** A question whose answer is what a snippet prints is
     actually run (Python here; R only if R is installed) and compared.
  4. **Rules in code.** Four options, no "all of the above", no "which is
     NOT", options of similar length, no near-duplicate of a question
     already in the bank, and the level mix.
  5. **Nothing myGeeKy doesn't cover** (safety.py): it teaches analysis, so a
     source that describes bench work gives no questions at all.

What's left goes to the maker as a **spot check**: five random questions
plus any where the checks disagreed. One 👎 and the batch is rewritten.

State: quizwriter.json (this computer only): the batches, their checks and
what the maker said. Never synced.
"""

from __future__ import annotations

import json
import random
import re
import subprocess          # noqa: F401 - only for its exception types; commands go through winproc.run
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable

import requests

from . import curated, quiz, safety, scout
from .config import DATA_DIR, ensure_dirs
from .files import read_json, write_json

WRITER_FILE = DATA_DIR / "quizwriter.json"
PER_PROTOCOL = 60            # the most a single writing run will keep
# What a bank needs to be worth taking. An attempt is 10 questions, so 10 is the floor and twice that
# gives a different draw each time -- which is what "ready" means in the admin tab.
READY = 10
GOOD = 20
PER_CALL = 6                 # questions asked for in one call (small, so a bad batch costs little)
SPOT_CHECK = 5               # questions the maker actually reads
PAGE_CHARS = 12_000
MIN_OPTION_CHARS = 1          # "6" is a fine answer to a code question
NEAR_DUPLICATE = 0.82        # how similar two question texts may be
_BANNED = re.compile(r"all of the above|none of the above|both a and b|which .{0,20}\bnot\b|except\b", re.I)
_CODE_FENCE = re.compile(r"```[a-z]*\n?|```")


# --------------------------------------------------------------------------- what DeepSeek is told
WRITE_SYSTEM = """You write quiz questions for myGeeKy, for researchers learning a skill.

You get ONE source (a page's text) and the step of a protocol it belongs to. Write {n} multiple-choice
questions that can be answered from THAT TEXT ALONE.

Hard rules:
- Every question must be answerable from the text you were given. Never use outside knowledge.
- For each question, quote the exact sentence or phrase from the text that proves the answer, copied word
  for word, in "quote".
- Exactly 4 options. Exactly one is right. The wrong ones must be plausible to someone still learning,
  and roughly the same length as the right one.
- Never write "all of the above", "none of the above", or a question phrased with NOT or EXCEPT.
- Say in "why", in one or two plain sentences, why the right answer is right.
- Levels: "easy" (do you know the basics), "medium" (apply it to a small case), "tricky" (a mistake people
  really make at this step -- a real pitfall, never confusing wording).
- "kind": "code" if the answer is what a snippet prints or does (put the snippet in "code", and make the
  right answer its exact output); otherwise "choice".
- Plain words. No jargon the text doesn't use. Nothing about the source itself ("what does this paper say").

{rules}

Answer as JSON: {{"questions": [{{"q": "...", "options": ["..","..","..",".."], "answer": <0-3>,
"why": "...", "quote": "...", "level": "easy|medium|tricky", "kind": "choice|code",
"code": "<only for kind=code, else ''>"}}]}}"""

ANSWER_SYSTEM = """You are answering one quiz question for a check. You do not know the intended answer.

Answer as JSON:
{"answer": <the number of the option you believe is right, 0-based>,
 "one_right": true only if exactly ONE option is right,
 "clear": true only if the question is clear and not ambiguous or trick-worded,
 "confidence": 0-1}"""


def write_batch(key: str, step: dict[str, Any], source: dict[str, Any], text: str, n: int = PER_CALL,
                post=None) -> list[dict[str, Any]]:
    """Ask DeepSeek for `n` questions about one source page."""
    user = (f"SKILL: {step['skill']}\nSTEP: {step['title']} ({step.get('role', '')})\n"
            f"SOURCE: {source.get('title', '')} ({source.get('url', '')})\n\nTEXT:\n{text[:PAGE_CHARS]}")
    out = scout.ask(key, WRITE_SYSTEM.format(n=n, rules=safety.prompt_rules()), user, post)
    rows = out.get("questions")
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def answer_blind(key: str, q: dict[str, Any], options: list[str], post=None) -> dict[str, Any]:
    """A second opinion, without the answer: which option, and is the question sound?"""
    body = q["q"] + (f"\n\nCODE:\n{q['code']}" if q.get("code") else "")
    listed = "\n".join(f"[{i}] {o}" for i, o in enumerate(options))
    return scout.ask(key, ANSWER_SYSTEM, f"QUESTION:\n{body}\n\nOPTIONS:\n{listed}", post)


# --------------------------------------------------------------------------- the checks myGeeKy makes itself
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _same_option(text: str) -> str:
    """Two options count as the same only if they read the same. Digits, signs and decimal points are
    kept, so "1.50" and "-1.50" stay different answers (they are opposite ones)."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def rules_ok(q: dict[str, Any]) -> str:
    """The plain rules, in code. "" when they all hold, else why not."""
    opts = [str(o or "").strip() for o in q.get("options") or []]
    if len(opts) != quiz.OPTIONS or len({_same_option(o) for o in opts}) != quiz.OPTIONS:
        return f"needs {quiz.OPTIONS} different options"
    if any(len(o) < MIN_OPTION_CHARS for o in opts):
        return "an option is empty"
    try:
        a = int(q.get("answer"))
    except (TypeError, ValueError):
        return "no answer"
    if not 0 <= a < quiz.OPTIONS:
        return "the answer isn't one of the options"
    if _BANNED.search(str(q.get("q") or "")) or any(_BANNED.search(o) for o in opts):
        return "trick wording or an 'all of the above' option"
    lengths = sorted(len(o) for o in opts)
    if lengths[-1] > max(28, lengths[0] * 4):          # the right answer must not stand out by length
        return "the options are very different lengths"
    if not str(q.get("why") or "").strip():
        return "doesn't say why"
    if str(q.get("level") or "") not in quiz.LEVELS:
        return "no level"
    if str(q.get("kind") or "") not in quiz.KINDS:
        return "no kind"
    if q.get("kind") == "code" and not str(q.get("code") or "").strip():
        return "a code question with no code"
    why = safety.blocked(f"{q.get('q', '')} {' '.join(opts)} {q.get('why', '')}")
    return why or ""


def quoted(quote: str, text: str) -> bool:
    """Is the quote really on the page? (Whitespace and punctuation are ignored, as in scout.check.)"""
    q = _norm(quote)
    return len(q) > 12 and q in _norm(text)


def too_similar(text: str, others: list[str]) -> bool:
    n = _norm(text)
    return any(SequenceMatcher(None, n, _norm(o)).ratio() >= NEAR_DUPLICATE for o in others)


# ---- questions a computer can mark
def run_python(code: str, timeout: float = 8.0) -> str | None:
    """What this snippet prints, run apart from myGeeKy.

    `-I` keeps the snippet from importing anything next to it, and it runs in an empty temporary
    folder, so a file in the working directory can never be picked up instead of a real module."""
    import tempfile

    from . import winproc                    # no console window flashing up on Windows
    try:
        with tempfile.TemporaryDirectory(prefix="mygeeky-quiz-") as box:
            r = winproc.run([sys.executable, "-I", "-c", code], capture_output=True, text=True,
                            timeout=timeout, cwd=box)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def run_r(code: str, timeout: float = 20.0) -> str | None:
    """The same for R, when R is installed (else None: the question is left to the blind check)."""
    exe = None
    for name in ("Rscript", "Rscript.exe"):
        from shutil import which
        exe = exe or which(name)
    if not exe:
        return None
    from . import winproc
    try:
        r = winproc.run([exe, "--vanilla", "-e", code], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    # Rscript prints "[1] 6": the value is what follows
    lines = [re.sub(r"^\s*\[\d+\]\s*", "", ln).strip() for ln in r.stdout.strip().splitlines() if ln.strip()]
    return "\n".join(lines)


def code_check(q: dict[str, Any]) -> tuple[bool | None, str]:
    """Run a code question for real. (None: couldn't run it -- not a failure.)"""
    code = _CODE_FENCE.sub("", str(q.get("code") or "")).strip()
    if not code:
        return None, ""
    low = code.lower()
    looks_r = bool(re.search(r"<-|\bc\(|\blibrary\(|\bdata\.frame\(|\bprint\(paste", code)) and "def " not in low
    out = run_r(code) if looks_r else run_python(code)
    if out is None:
        return None, "couldn't be run here"
    want = str((q.get("options") or [""])[int(q["answer"])]).strip()
    got = out.strip()
    ok = _norm(got) == _norm(want) or _norm(want) in _norm(got)
    return ok, f"it printed {got[:60]!r}" if not ok else "the code really prints that"


@dataclass
class Checked:
    """One question with everything myGeeKy could tell about it."""
    question: dict[str, Any]
    passed: bool
    reason: str                   # why it was dropped, or "" when it's in
    checks: list[tuple[bool, str]]
    needs_eyes: bool              # the checks disagreed: the maker should look at this one


def check_question(raw: dict[str, Any], source: dict[str, Any], text: str, step: dict[str, Any],
                   key: str | None = None, others: list[str] | None = None, post=None,
                   rng: random.Random | None = None) -> Checked:
    """Every check, in order of cost: the rules, the quote, running it, then the blind second opinion."""
    rng = rng or random.Random()
    checks: list[tuple[bool, str]] = []
    bad = rules_ok(raw)
    if bad:
        return Checked(raw, False, bad, checks, False)
    checks.append((True, "four fair options, no trick wording"))
    # A code question is proved by running it (below); everything else must quote its source.
    self_proving = raw.get("kind") == "code"
    on_page = quoted(str(raw.get("quote") or ""), text)
    if not self_proving:
        checks.append((on_page, "the sentence it quotes is on the source page"))
        if not on_page:
            return Checked(raw, False, "the quote isn't on the source page", checks, False)
    elif on_page:
        checks.append((True, "the sentence it quotes is on the source page"))
    if too_similar(str(raw.get("q")), others or []):
        return Checked(raw, False, "almost the same as a question already in the bank", checks, False)
    ran, note = code_check(raw)
    if ran is False:
        return Checked(raw, False, f"the code doesn't do that ({note})", checks + [(False, note)], False)
    if ran is True:
        checks.append((True, note))
    # the blind second opinion, twice, with the options in a different order each time
    agree = 0
    sound = True
    if key:
        for _ in range(2):
            order = list(range(quiz.OPTIONS))
            rng.shuffle(order)
            opts = [raw["options"][i] for i in order]
            ans = answer_blind(key, raw, opts, post)
            try:
                picked = order[int(ans.get("answer"))]
            except (TypeError, ValueError, IndexError):
                picked = -1
            agree += 1 if picked == int(raw["answer"]) else 0
            sound = sound and bool(ans.get("one_right")) and bool(ans.get("clear"))
        checks.append((agree == 2, "answered the same way both times, blind"))
        checks.append((sound, "one right answer, clearly worded"))
        if agree < 2:
            return Checked(raw, False, "a blind second read didn't pick the same answer both times", checks, False)
        if not sound:
            return Checked(raw, False, "a blind second read called it unclear or ambiguous", checks, False)
    needs = ran is None and raw.get("kind") == "code"
    return Checked(raw, True, "", checks, needs)


# --------------------------------------------------------------------------- a run over one protocol
def _page_text(url: str, session: requests.Session | None = None) -> str:
    """A source's page as plain text (the scout's reader, so a GitHub repo page reads as its README)."""
    if "github.com/" in url and "/blob/" not in url:
        parts = url.rstrip("/").split("github.com/", 1)[-1].split("/")
        if len(parts) >= 2:
            for branch in ("main", "master"):
                raw = f"https://raw.githubusercontent.com/{parts[0]}/{parts[1]}/{branch}/README.md"
                try:
                    r = (session or requests).get(raw, timeout=25, headers=scout.UA)
                    if r.status_code == 200 and len(r.text) > 200:
                        return r.text
                except requests.RequestException:
                    continue
    try:
        return scout.page(url, session)["text"]
    except Exception:  # noqa: BLE001 - a source that won't open gives no questions, that's all
        return ""


def sources_of(proto: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """[(step, link)] for every link worth writing questions from (bench sources are dropped above)."""
    out = []
    for st in proto["stages"]:
        if st["role"] == "use":
            continue
        for it in st["items"]:
            if "github.com/search" in it["url"]:
                continue
            out.append(({"id": st["id"], "title": st["title"], "role": st["role"], "skill": proto["skill"]}, it))
    return out


def write_for(proto: dict[str, Any], key: str, want: int = PER_PROTOCOL, session: requests.Session | None = None,
              post=None, progress: Callable[[str], None] | None = None, rng: random.Random | None = None,
              existing: list[str] | None = None) -> dict[str, Any]:
    """Write and check a batch of questions for one protocol.

    {"questions": [...kept], "dropped": [(why, question text)], "spot_check": [...], "asked": n}"""
    say = progress or (lambda _m: None)
    rng = rng or random.Random()
    ok, why = safety.allowed(proto["skill"], proto.get("goal", ""))
    if not ok:
        return {"questions": [], "dropped": [(why, proto["skill"])], "spot_check": [], "asked": 0}
    kept: list[dict[str, Any]] = []
    dropped: list[tuple[str, str]] = []
    texts = list(existing or [])
    pairs = [(step, src) for step, src in sources_of(proto) if not safety.blocked_source(src["url"])]
    rng.shuffle(pairs)
    asked = 0
    for step, source in pairs:
        if len(kept) >= want:
            break
        say(f"{source['title'][:50]}…")
        text = _page_text(source["url"], session)
        if len(text) < 400:
            dropped.append(("the source page gave no usable text", source["url"]))
            continue
        asked += 1
        for raw in write_batch(key, step, source, text, PER_CALL, post):
            if len(kept) >= want:
                break
            res = check_question(raw, source, text, step, key, texts, post, rng)
            if not res.passed:
                dropped.append((res.reason, str(raw.get("q", ""))[:80]))
                continue
            n = len([q for q in kept if q["stage"] == step["id"]]) + 1
            q = quiz.clean_question({
                "id": f"{proto['id']}.{step['id']}.{n:02d}", "protocol": proto["id"], "stage": step["id"],
                "level": raw.get("level"), "kind": raw.get("kind"), "q": raw.get("q"),
                "code": _CODE_FENCE.sub("", str(raw.get("code") or "")).strip(),
                "options": raw.get("options"), "answer": raw.get("answer"), "why": raw.get("why"),
                "source": {"title": source.get("title", ""), "url": source["url"],
                           "kind": source.get("kind", "website"), "quote": raw.get("quote")},
                "checks": [t for ok_, t in res.checks if ok_]})
            if not q:
                dropped.append(("didn't survive the shape check", str(raw.get("q", ""))[:80]))
                continue
            q["needs_eyes"] = res.needs_eyes
            kept.append(q)
            texts.append(q["q"])
    return {"questions": kept, "dropped": dropped, "spot_check": spot_check(kept, rng), "asked": asked}


def spot_check(questions: list[dict[str, Any]], rng: random.Random | None = None) -> list[str]:
    """The ids the maker actually reads: the ones the checks disagreed on, then a random few."""
    rng = rng or random.Random()
    eyes = [q["id"] for q in questions if q.get("needs_eyes")]
    rest = [q["id"] for q in questions if q["id"] not in eyes]
    rng.shuffle(rest)
    return (eyes + rest)[:max(SPOT_CHECK, len(eyes))]


def mix_of(questions: list[dict[str, Any]]) -> dict[str, int]:
    return {lv: sum(1 for q in questions if q["level"] == lv) for lv in quiz.LEVELS}


def balance(questions: list[dict[str, Any]], want: int = PER_PROTOCOL) -> list[dict[str, Any]]:
    """Trim a batch towards the MIX, so an attempt can always be drawn in the right shape."""
    out: list[dict[str, Any]] = []
    for lv in quiz.LEVELS:
        rows = [q for q in questions if q["level"] == lv]
        out.extend(rows[:max(3, round(want * quiz.MIX[lv]))])
    return out


# --------------------------------------------------------------------------- state and the bank file
def load() -> dict[str, Any]:
    data = read_json(WRITER_FILE, {}) or {}
    data.setdefault("batches", {})           # protocol id -> the last batch and what the maker said
    return data


def save(state: dict[str, Any]) -> None:
    ensure_dirs()
    write_json(WRITER_FILE, state)


def keep_batch(pid: str, batch: dict[str, Any]) -> None:
    state = load()
    state["batches"][pid] = {**batch, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "verdict": ""}
    save(state)


def set_verdict(pid: str, verdict: str) -> None:
    """"accepted" or "rewrite" (one 👎 in the spot check)."""
    state = load()
    if pid in state["batches"]:
        state["batches"][pid]["verdict"] = verdict
        save(state)


def bank_path() -> Path:
    return quiz.BUNDLED


def add_to_bank(questions: list[dict[str, Any]], path: Path | None = None) -> dict[str, Any]:
    """Put accepted questions into the shipped bank (the maker's own checkout). {"added", "total"}"""
    path = path or bank_path()
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"version": "", "questions": []}
    have = {q["id"] for q in data.get("questions") or []}
    added = 0
    for q in questions:
        row = quiz.hide_answer({k: v for k, v in q.items() if k != "needs_eyes"})
        if row["id"] in have:
            continue
        data.setdefault("questions", []).append(row)
        have.add(row["id"])
        added += 1
    data["version"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    problems = quiz.problems(data)
    if problems:
        raise ValueError("the bank wouldn't pass its check: " + "; ".join(problems[:3]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"added": added, "total": len(data["questions"])}


def retire(ids: list[str], path: Path | None = None) -> int:
    """Drop questions people flagged, or that the best quiz-takers keep missing."""
    path = path or bank_path()
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    before = len(data.get("questions") or [])
    data["questions"] = [q for q in data.get("questions") or [] if q.get("id") not in set(ids)]
    data["version"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return before - len(data["questions"])


def summary(batch: dict[str, Any]) -> str:
    mix = mix_of(batch.get("questions") or [])
    return (f"{len(batch.get('questions') or [])} kept ("
            + ", ".join(f"{n} {lv}" for lv, n in mix.items() if n)
            + f"), {len(batch.get('dropped') or [])} dropped by the checks")


def reasons(batch: dict[str, Any], top: int = 6) -> list[tuple[str, int]]:
    """Why questions were dropped, most common first (the maker's only report)."""
    counts: dict[str, int] = {}
    for why, _ in batch.get("dropped") or []:
        counts[why] = counts.get(why, 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])[:top]
