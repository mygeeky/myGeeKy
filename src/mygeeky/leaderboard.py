"""Quiz scores on mygeeky.org -- only for people who ask for it, and only what they agreed to.

A score could follow someone into a job application, so **nothing about you
goes online unless you say so**, and you say it from your own GitHub
account, which is what makes it provable.

How it works:

  1. **You choose.** In the app: *share my name and profile* and *share my
     scores* are two separate switches, both off to begin with. The app
     shows exactly what would appear.
  2. **You accept, from your own account.** The app opens a prefilled issue
     in the public ideas repo holding that exact text, and you write
     `accept` and submit it. GitHub records who wrote it and when: that is
     the proof, and there is no email anywhere in this.
  3. **A GitHub Action reads it** (`consent` below): it checks the `accept`
     came from the account being shown -- nobody can accept for anyone else
     -- that the entry still matches, and that it isn't the maker's own
     account (`EXCLUDED`: the maker tests this, so the maker never ranks).
  4. **The maker approves** before anything appears.
  5. **You can withdraw** with `withdraw` on the same issue, or a button in
     the app. The page is rebuilt without you, and because the leaderboard
     is kept on its own branch that is **rewritten** (not added to) on every
     withdrawal, no old copy of your score stays in the repo's history.

Each new score needs its own `accept`: agreeing to show 90% is not agreeing
to show 100%.

What the website shows, and nothing else: name, profile link, photo (your
GitHub avatar), the protocol and -- if you shared scores -- the score. Never
an affiliation, never an email address, never a low score: only the top 3 of
the month and the first people to finish a protocol.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Iterable

from . import curated, ideas, quiz

TOP = 3                    # people on the month's board
PROTOCOL_PEOPLE = 5        # the first to reach 100% on a protocol, shown on it
PERFECT = 1.0
MIN_SHOWN = 0.8            # a score below this is never shown anywhere, even with consent
EXCLUDED = {"alsammanalsamman"}          # the maker tests this; the maker never ranks
TITLE = "🏆"            # every one of these issues starts with it (ideas.KINDS["score"])
_ACCEPT = re.compile(r"^\s*accept\s*\.?\s*$", re.I | re.M)
_WITHDRAW = re.compile(r"^\s*withdraw\s*\.?\s*$", re.I | re.M)
_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")


# --------------------------------------------------------------------------- what you'd be sharing
@dataclass
class Share:
    """Exactly what would appear on mygeeky.org, shown to you before you agree to it."""
    login: str
    name: str                      # how you'd be named (your GitHub name, or your login)
    profile_url: str
    avatar_url: str
    share_name: bool               # show the name, link and photo
    share_scores: bool             # show the scores next to it
    scores: dict[str, float] = field(default_factory=dict)      # protocol id -> your best score
    titles: dict[str, str] = field(default_factory=dict)        # protocol id -> its title

    @property
    def shown_scores(self) -> dict[str, float]:
        """Only strong results travel: a low score is never shown, agreed or not."""
        if not self.share_scores:
            return {}
        return {p: s for p, s in self.scores.items() if s >= MIN_SHOWN}

    def lines(self) -> list[str]:
        """What you'd see on the page, in plain words."""
        out = []
        if self.share_name:
            out.append(f"your name “{self.name}”, a link to {self.profile_url}, and your GitHub photo")
        else:
            out.append("nothing that names you (so you can't appear on the page at all)")
        shown = self.shown_scores
        if shown:
            out.extend(f"{self.titles.get(p, p)}: {round(s * 100)}%" for p, s in sorted(shown.items()))
        elif self.share_scores:
            out.append("no scores yet high enough to show (only 80% and above is ever shown)")
        else:
            out.append("no scores")
        out.append("never your affiliation, your email address, or anything else")
        return out

    def payload(self) -> dict[str, Any]:
        """The machine-readable part of the issue (what the Action checks against)."""
        return {"login": self.login, "name": self.name if self.share_name else "",
                "profile": self.profile_url if self.share_name else "",
                "avatar": self.avatar_url if self.share_name else "",
                "share_name": self.share_name, "share_scores": self.share_scores,
                "scores": {p: round(s, 4) for p, s in sorted(self.shown_scores.items())}}


def share_of(cfg, share_name: bool, share_scores: bool, name: str = "", avatar: str = "",
             data: dict[str, Any] | None = None) -> Share:
    """What you'd be sharing, built from your own best scores (quiz.json)."""
    login = (cfg.github_username or "").strip()
    best = quiz.best()
    titles = {p["id"]: p["title"] for p in (data or curated.load()).get("protocols") or []}
    titles.update({pid: str(row.get("title") or pid) for pid, row in best.items()})
    return Share(login=login, name=(name or login), profile_url=f"https://github.com/{login}" if login else "",
                 avatar_url=avatar or (f"https://github.com/{login}.png" if login else ""),
                 share_name=bool(share_name), share_scores=bool(share_scores),
                 scores={pid: float(row.get("score") or 0.0) for pid, row in best.items()},
                 titles=titles)


def can_share(share: Share) -> tuple[bool, str]:
    """May this go online at all? (Nothing to show is a plain no, not an error.)"""
    if not share.login:
        return False, "Add your GitHub account first: it's how you prove the choice is yours."
    if share.login.lower() in EXCLUDED:
        return False, "myGeeKy's maker is left off the board (that's where the tests happen)."
    if not share.share_name:
        return False, "Nothing would be shown without your name, so there's nothing to share yet."
    if not share.shown_scores:
        return False, (f"No score of yours is high enough yet ({round(MIN_SHOWN * 100)}% and above is shown). "
                       "Take a quiz again tomorrow: your best score counts.")
    return True, ""


# --------------------------------------------------------------------------- asking for it, provably
def _block(payload: dict[str, Any]) -> str:
    return ("<details><summary>For myGeeKy (don't edit)</summary>\n\n```json\n"
            + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n```\n</details>\n")


def accept_body(share: Share) -> str:
    """The issue you'd send: what it would show, and the one word that agrees to it."""
    lines = "\n".join(f"- {ln}" for ln in share.lines())
    return (f"I'd like my quiz result shown on mygeeky.org.\n\n**What would appear:**\n{lines}\n\n"
            "**To agree, write `accept` on its own line below and submit.** It's your GitHub account that "
            "says it, which is the proof — no email needed.\n\n"
            "You can take it back any time by writing `withdraw` here, or with the button in myGeeKy. "
            "The page is rebuilt without you, and the branch holding it is rewritten, so no old copy stays.\n\n"
            "accept\n\n" + _block(share.payload()))


def accept_url(share: Share) -> str:
    """The prefilled issue (you press Submit, with your own account)."""
    return ideas.issue_url("score", f"Quiz score: {share.name}", accept_body(share), include_version=False)


# --------------------------------------------------------------------------- the maker's side: reading consent
_JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.S)


def _clean_entry(raw: Any, login: str) -> dict[str, Any] | None:
    """One checked leaderboard entry (someone else's text, like everything else that arrives)."""
    if not isinstance(raw, dict) or not _LOGIN.match(login or ""):
        return None
    if not raw.get("share_name"):
        return None
    scores = {}
    for pid, value in (raw.get("scores") or {}).items():
        try:
            s = float(value)
        except (TypeError, ValueError):
            continue
        if curated._ID.match(str(pid)) and MIN_SHOWN <= s <= 1.0:
            scores[str(pid)] = round(s, 4)
    if not scores:
        return None
    return {"login": login, "name": curated._text(raw.get("name"), 60) or login,
            "profile": curated._https(raw.get("profile")) or f"https://github.com/{login}",
            "avatar": curated._https(raw.get("avatar")) or f"https://github.com/{login}.png",
            "scores": scores}


def consent(issue: dict[str, Any], comments: Iterable[dict[str, Any]] = ()) -> dict[str, Any] | None:
    """What one issue says: {"login", "action": "accept"|"withdraw", "entry", "at", "issue"} or None.

    The `accept` (or `withdraw`) must be written by the same account the entry is about: that is the
    whole proof. A comment from anyone else is ignored, however it's worded. The maker is excluded."""
    if not str(issue.get("title") or "").startswith(TITLE):
        return None
    login = str((issue.get("user") or {}).get("login") or "")
    if not _LOGIN.match(login) or login.lower() in EXCLUDED:
        return None
    m = _JSON_BLOCK.search(str(issue.get("body") or ""))
    if not m:
        return None
    try:
        raw = json.loads(m.group(1))
    except ValueError:
        return None
    entry = _clean_entry(raw, login)
    if not entry:
        return None
    if str(raw.get("login") or login).lower() != login.lower():     # the entry must be about its author
        return None
    # the newest word from that same account wins: the issue body, then their own comments in order
    action, when = "", str(issue.get("created_at") or "")
    if _ACCEPT.search(str(issue.get("body") or "")):
        action = "accept"
    for c in comments:
        if str((c.get("user") or {}).get("login") or "").lower() != login.lower():
            continue
        text = str(c.get("body") or "")
        if _WITHDRAW.search(text):
            action, when = "withdraw", str(c.get("created_at") or when)
        elif _ACCEPT.search(text):
            action, when = "accept", str(c.get("created_at") or when)
    if not action:
        return None
    return {"login": login, "action": action, "entry": entry, "at": when[:19],
            "issue": issue.get("number"), "url": issue.get("html_url", "")}


def harvest(client, limit_pages: int = 5, with_comments: bool = True) -> list[dict[str, Any]]:
    """Everyone who asked for the board, newest word per person (maker side)."""
    out: dict[str, dict[str, Any]] = {}
    for page in range(1, limit_pages + 1):
        resp = client._get(f"/repos/{ideas.IDEAS_REPO}/issues",
                           params={"state": "all", "per_page": 100, "page": page})
        if resp.status_code != 200:
            break
        rows = resp.json()
        for issue in rows:
            if "pull_request" in issue or not str(issue.get("title") or "").startswith(TITLE):
                continue
            comments: list[dict[str, Any]] = []
            if with_comments and int(issue.get("comments") or 0):
                c = client._get(f"/repos/{ideas.IDEAS_REPO}/issues/{issue['number']}/comments",
                                params={"per_page": 100})
                if c.status_code == 200:
                    comments = c.json()
            said = consent(issue, comments)
            if said and said["at"] >= out.get(said["login"], {}).get("at", ""):
                out[said["login"]] = said
        if len(rows) < 100:
            break
    return sorted(out.values(), key=lambda s: s["at"])


# --------------------------------------------------------------------------- the board itself
def board(entries: Iterable[dict[str, Any]], data: dict[str, Any] | None = None,
          difficulty: dict[str, float] | None = None, month: str = "") -> dict[str, Any]:
    """The board as the website shows it, from approved entries.

    {"month", "top": [...3], "protocols": {pid: [...first 5 to 100%]}, "hall": [...all-time]}"""
    rows = []
    for e in entries:
        if e.get("action") != "accept" or e.get("login", "").lower() in EXCLUDED:
            continue
        entry = e["entry"]
        scores = entry["scores"]
        rows.append({**entry, "at": e.get("at", ""),
                     "weighted": quiz.weighted(scores, difficulty, data),
                     "perfect": sorted(p for p, s in scores.items() if s >= PERFECT)})
    month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    this_month = [r for r in rows if str(r["at"])[:7] == month]
    top = sorted(this_month, key=lambda r: (-r["weighted"], r["at"]))[:TOP]
    people: dict[str, list[dict[str, Any]]] = {}
    for r in sorted(rows, key=lambda r: r["at"]):          # first come, first listed
        for pid in r["perfect"]:
            people.setdefault(pid, [])
            if len(people[pid]) < PROTOCOL_PEOPLE and all(x["login"] != r["login"] for x in people[pid]):
                people[pid].append({"login": r["login"], "name": r["name"], "profile": r["profile"],
                                    "avatar": r["avatar"], "at": r["at"][:10],
                                    "pathfinder": not people[pid]})      # the first one to finish it
    hall = sorted(rows, key=lambda r: (-r["weighted"], r["at"]))[:12]
    return {"month": month, "top": top, "protocols": people, "hall": hall,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def difficulty_of(entries: Iterable[dict[str, Any]]) -> dict[str, float]:
    """How hard each protocol turned out to be: the average shared score. Feeds quiz.weight_of."""
    totals: dict[str, list[float]] = {}
    for e in entries:
        if e.get("action") != "accept":
            continue
        for pid, s in (e["entry"]["scores"] or {}).items():
            totals.setdefault(pid, []).append(float(s))
    return {pid: round(sum(v) / len(v), 4) for pid, v in totals.items() if len(v) >= 3}


# --------------------------------------------------------------------------- "is this a real researcher?"
PROFILE_SYSTEM = """You help myGeeKy's maker check whether a GitHub account looks like a real person doing
real work, before their name is shown on a public page. You get only public facts about the account.

Answer as JSON:
{"looks_real": true or false,
 "why": "one short sentence, from the facts given",
 "confidence": 0-1}

Say false only if the facts suggest an empty or throwaway account (made days ago, no repositories, no
activity). Few followers is not a reason: early-career researchers have few. Never guess about the person
themselves, only about the account."""


def facts_of(client, login: str) -> dict[str, Any]:
    """The public facts the check is allowed to use. Nothing private, nothing from the app."""
    r = client._get(f"/users/{login}")
    if getattr(r, "status_code", 200) != 200:
        return {}
    u = r.json()
    return {"login": u.get("login", ""), "created_at": str(u.get("created_at") or "")[:10],
            "public_repos": int(u.get("public_repos") or 0), "followers": int(u.get("followers") or 0),
            "bio": curated._text(u.get("bio"), 300), "name": curated._text(u.get("name"), 80),
            "company": "", "blog": curated._https(u.get("blog")) or ""}


def looks_real(client, login: str, key: str | None = None, post=None, today: date | None = None) -> dict[str, Any]:
    """{"looks_real", "why", "confidence", "facts"} -- a note for the maker, never a gate.

    Without a key it still answers from the plain facts: an account older than six months with public
    repositories is enough to show the maker something. The maker decides, always."""
    facts = facts_of(client, login)
    if not facts:
        return {"looks_real": False, "why": "the account couldn't be read", "confidence": 0.0, "facts": {}}
    today = today or date.today()
    try:
        age_days = (today - date.fromisoformat(facts["created_at"])).days
    except ValueError:
        age_days = 0
    plain = age_days >= 180 and facts["public_repos"] >= 1
    out = {"looks_real": plain, "confidence": 0.5,
           "why": (f"account is {age_days // 30} months old with {facts['public_repos']} public repositories"
                   if plain else f"account is {age_days} days old with {facts['public_repos']} public repositories"),
           "facts": facts}
    if not key:
        return out
    from . import scout
    try:
        said = scout.ask(key, PROFILE_SYSTEM, json.dumps(facts, ensure_ascii=False), post)
    except Exception:  # noqa: BLE001 - the plain answer above still stands
        return out
    if "looks_real" in said:
        out.update(looks_real=bool(said.get("looks_real")) and plain,
                   why=curated._text(said.get("why"), 200) or out["why"],
                   confidence=max(0.0, min(1.0, float(said.get("confidence") or 0))))
    return out


def problems(data: Any) -> list[str]:
    """What's wrong with a board file, in plain words (empty: all good)."""
    if not isinstance(data, dict):
        return ["The board must be one JSON object."]
    out = []
    for who in list(data.get("top") or []) + list(data.get("hall") or []):
        if not isinstance(who, dict) or not _LOGIN.match(str(who.get("login", ""))):
            out.append("an entry without a GitHub account")
            continue
        if str(who["login"]).lower() in EXCLUDED:
            out.append(f"{who['login']} must not be on the board")
        if any(float(s) < MIN_SHOWN for s in (who.get("scores") or {}).values()):
            out.append(f"{who['login']}: a score below {round(MIN_SHOWN * 100)}% must never be shown")
        for field_ in ("affiliation", "email", "org"):
            if who.get(field_):
                out.append(f"{who['login']}: '{field_}' must not be on the board")
    return out[:30]


def withdraw_names(entries: Iterable[dict[str, Any]]) -> list[str]:
    """Everyone who took it back: the board is rebuilt without them, and the branch rewritten."""
    return sorted({e["login"] for e in entries if e.get("action") == "withdraw"})


def main(argv: list[str] | None = None) -> int:
    """python -m mygeeky.leaderboard harvest [out.json]   (maker side)"""
    import sys
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] != "harvest":
        print(main.__doc__)
        return 2
    from pathlib import Path

    from .github_client import GitHubClient
    said = harvest(GitHubClient(None))
    diff = difficulty_of(said)
    out = board(said, difficulty=diff)
    path = Path(args[1]) if len(args) > 1 else Path("website/data/leaderboard.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(said)} people said something; {len(out['top'])} on this month's board -> {path}")
    for w in withdraw_names(said):
        print(f"  withdrawn: {w} (rewrite the board branch)")
    for p in problems(out):
        print(f"  ! {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
