"""Protocols: a skill turned into ordered stages, with a level check, built from GitHub and articles.

    R for data analysis
      1. R basics             -> a course repo, a beginner book, a tutorial article
      2. Statistics with R    -> a statistics-in-R repo, a review/tutorial paper
      3. R for data analysis  -> a tidyverse/analysis repo, a worked case study
      4. A real project       -> an open analysis repo from your field, to read and rerun
      5. Your own work        -> ticks itself when one of your repos shows the skill

**Reviewed protocols** are written by myGeeKy's maker and ship in
data/curated.json ("protocols"), like the verified jobs. **For any other
skill the app builds one** (build()): it searches GitHub and OpenAlex with
the stages' own words, and the small protocol model (protomodel.py) sorts
what comes back into stages. It is labelled *auto-built, not reviewed*.

**The level check.** Each stage can be marked as known, three ways:
  - evidence: your own repos and profile ("6 of your repos are in R"), which
    you can overrule ("not really");
  - a short quiz (reviewed protocols), passed at 75%;
  - "I can do these": a few can-do statements you tick yourself.
The first stage you don't know yet is where you start.

**Yours to change.** Reorder, rename, add and remove stages and links. Then
📤 publish it: a prefilled issue in the public ideas repo, sent by you from
your own GitHub account (no token passes through myGeeKy). It carries the
protocol and the links you removed from an auto-built one -- never your quiz
answers, progress or anything else. The maker harvests published protocols
(`python -m mygeeky.protocols harvest`): they become reviewed protocols and
training data for the next model.

State lives in learning_paths.json (synced): {"paths": {protocol id: {"started_at",
"protocol", "done", "known", "quiz", "removed", "edited"}}}. Paths saved before
protocols ({"paths": {skill: {"started_at", "done"}}}) become protocols as they're read.
"""

from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from urllib.parse import quote_plus, urlencode

from . import curated, protomodel, skills, taste
from .config import PATHS_FILE, MyGeekyConfig, ensure_dirs
from .files import read_json, write_json

ROLES = ("basics", "deeper", "applied", "project", "use")
ITEM_KINDS = {"repo": "📦", "article": "📄", "website": "🌐", "course": "🎓", "book": "📖", "tutorial": "🧭",
              "video": "🎬", "guide": "📘"}
PASS = 0.75
PER_STAGE = {"basics": 3, "deeper": 3, "applied": 3, "project": 2}
ARTICLES_PER_STAGE = 1
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,79}$")
_SID = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
PUBLISH_KIND = "protocol"
MAX_STAGES = 10
MAX_ITEMS = 8


# --------------------------------------------------------------------------- the shape, checked
def slug(text: str, n: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:n].strip("-")
    return s if len(s) >= 3 else (s + "-protocol")[:n]


def _clean_quiz(raw: Any) -> list[dict[str, Any]]:
    out = []
    for q in raw if isinstance(raw, list) else []:
        if not isinstance(q, dict):
            continue
        opts = [curated._text(o, 140) for o in q.get("options") or [] if curated._text(o, 140)][:5]
        try:
            answer = int(q.get("answer"))
        except (TypeError, ValueError):
            continue
        text = curated._text(q.get("q"), 220)
        if text and 2 <= len(opts) and 0 <= answer < len(opts):
            out.append({"q": text, "options": opts, "answer": answer})
    return out[:8]


def clean_item(raw: Any) -> dict[str, Any] | None:
    """One checked link, or None. A bench protocol's home is refused here, which is the one door every
    link comes through: a protocol myGeeKy builds, a reviewed one, or one another user published."""
    from . import safety
    if not isinstance(raw, dict):
        return None
    url = curated._https(raw.get("url"))
    title = curated._text(raw.get("title"), 160)
    if not url or not title:
        return None
    if safety.blocked_source(url) or safety.is_bench(f"{title} {raw.get('note') or ''}"):
        return None
    kind = str(raw.get("kind") or "website").lower()
    out = {"title": title, "url": url, "kind": kind if kind in ITEM_KINDS else "website",
           "note": curated._text(raw.get("note"), 200)}
    for k in ("stars", "cited", "year"):                 # facts shown on the link's card (optional)
        try:
            n = int(raw.get(k) or 0)
        except (TypeError, ValueError):
            n = 0
        if 0 < n < 10_000_000:
            out[k] = n
    for k, n in (("lang", 40), ("updated", 10), ("venue", 80)):
        v = curated._text(raw.get(k), n)
        if v:
            out[k] = v
    return out


def clean_stage(raw: Any, i: int = 0) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    title = curated._text(raw.get("title"), 80)
    if not title:
        return None
    sid = str(raw.get("id") or "").lower()
    role = str(raw.get("role") or "applied").lower()
    seen: set[str] = set()
    items = []
    for it in (raw.get("items") if isinstance(raw.get("items"), list) else [])[:MAX_ITEMS]:
        c = clean_item(it)
        if c and c["url"] not in seen:
            seen.add(c["url"])
            items.append(c)
    return {"id": sid if _SID.match(sid) else f"s{i + 1}", "title": title,
            "role": role if role in ROLES else "applied", "query": curated._text(raw.get("query"), 60),
            "skills": curated._words(raw.get("skills"), 6), "can": [curated._text(c, 160) for c in raw.get("can") or []
                                                                    if curated._text(c, 160)][:6],
            "quiz": _clean_quiz(raw.get("quiz")), "items": items}


def clean_protocol(raw: Any, reviewed: bool = False) -> dict[str, Any] | None:
    """A checked protocol, or None. `reviewed` is only ever set by the caller, never by the file.

    A protocol about laboratory work is refused outright, wherever it came from -- the curated file, a
    user's published one, or one built here (safety.py)."""
    from . import safety
    if not isinstance(raw, dict):
        return None
    skill = curated._text(raw.get("skill"), 60)
    title = curated._text(raw.get("title"), 100)
    if not skill or not title:
        return None
    if safety.is_bench(f"{skill} {title} {curated._text(raw.get('goal'), 60)} "
                       f"{curated._text(raw.get('summary'), 300)}"):
        return None
    pid = str(raw.get("id") or "").lower()
    stages, seen = [], set()
    for i, s in enumerate((raw.get("stages") if isinstance(raw.get("stages"), list) else [])[:MAX_STAGES]):
        st = clean_stage(s, i)
        if st:
            while st["id"] in seen:
                st["id"] = f"{st['id']}-{len(seen) + 1}"[:40]
            seen.add(st["id"])
            stages.append(st)
    if not stages:
        return None
    source = str(raw.get("source") or "").lower()
    return {"id": pid if _ID.match(pid) else slug(title), "skill": skill, "goal": curated._text(raw.get("goal"), 60),
            "title": title, "summary": curated._text(raw.get("summary"), 300), "stages": stages,
            "reviewed": bool(reviewed),
            "source": "reviewed" if reviewed else (source if source in ("auto", "mine") else "mine"),
            "by": curated._text(raw.get("by"), 40), "based_on": curated._text(raw.get("based_on"), 80)}


def reviewed(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = curated.load() if data is None else data
    return list(data.get("protocols") or [])


def _same(a: str, b: str) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower()


def find_reviewed(skill: str, goal: str = "", data: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The reviewed protocol for this skill (and goal, if one fits), else None."""
    s = skills.find(skill)
    name = s["name"] if s else skill
    mine = [p for p in reviewed(data) if _same(p["skill"], name)]
    if goal:
        exact = [p for p in mine if _same(p.get("goal", ""), goal)]
        if exact:
            return exact[0]
    return mine[0] if mine else None


# --------------------------------------------------------------------------- a new protocol from scratch
def _can(role: str, name: str, goal: str) -> list[str]:
    g = goal or "a real analysis"
    return {
        "basics": [f"I can explain what {name} is for and when to use it",
                   f"I've followed a beginner tutorial on {name} from start to end",
                   "I can do the everyday tasks without looking everything up"],
        "deeper": [f"I know the main ideas behind {name}, not only the commands",
                   f"I can read someone else's {name} work and follow it",
                   "I know the common mistakes and how to avoid them"],
        "applied": [f"I've used {name} for {g} from start to finish",
                    f"I can choose the right approach in {name} for a new problem"],
        "project": [f"I've read and rerun a real {name} project from my field"],
    }.get(role, [])


def template(skill: str, goal: str = "") -> dict[str, Any]:
    """The stages of a protocol for any skill, before anything is found for them."""
    s = skills.find(skill)
    name = s["name"] if s else curated._text(skill, 60)
    kind = s.get("kind", "") if s else ""
    goal = curated._text(goal, 60)
    stats = kind == "language" and "analy" in goal.lower()
    stages = [
        {"id": "basics", "title": f"{name} basics", "role": "basics"},
        {"id": "deeper", "title": f"Statistics with {name}" if stats else f"{name} in depth", "role": "deeper",
         "query": "statistics" if stats else ""},
        {"id": "applied", "title": f"{name} for {goal}" if goal else f"Using {name} on real data",
         "role": "applied", "query": goal},
        {"id": "project", "title": "A real project to rerun", "role": "project", "query": goal or "analysis"},
        {"id": "use", "title": "Use it in your own work", "role": "use"},
    ]
    for st in stages:
        st.setdefault("query", "")
        st.update(skills=[name.lower()], can=_can(st["role"], name, goal), quiz=[], items=[])
    title = f"{name} for {goal}" if goal else f"Learning {name}"
    return {"id": slug(f"{name} {goal}" if goal else name), "skill": name, "goal": goal, "title": title,
            "summary": "", "stages": stages, "reviewed": False, "source": "auto", "by": "", "based_on": ""}


def _search_link(name: str, words: str) -> dict[str, Any]:
    q = f"{name} {words}".strip()
    return {"title": f"Search GitHub: {q}", "url": f"https://github.com/search?q={quote_plus(q)}&type=repositories&s=stars",
            "kind": "repo", "note": "Nothing picked yet: the most-starred matches"}


def _aliases(name: str) -> list[str]:
    s = skills.find(name)
    return sorted({name.lower(), *(s["aliases"] if s else [])})


def _from_resource(r: dict[str, Any]) -> dict[str, Any]:
    kind = r.get("type", "website")
    return {"title": r["title"], "url": r["url"], "kind": kind if kind in ITEM_KINDS else "website",
            "note": r.get("summary", "")[:200]}


_LEVEL_ROLE = {"beginner": "basics", "": "basics", "intermediate": "deeper", "advanced": "deeper"}


def _kind_of(c: dict[str, Any]) -> str:
    """What a candidate is shown as: a 📘 guide, or whatever it came as."""
    if c["kind"] == "repo":
        return "repo"
    if protomodel.is_guide(c.get("url", "")):
        return "guide"
    return c["kind"]


def candidates_for(proto: dict[str, Any], client=None, session=None, limit_queries: int = 10) -> list[dict[str, Any]]:
    """Everything worth considering for this protocol: GitHub and OpenAlex hits, tagged with the stage that asked."""
    name, goal = proto["skill"], proto.get("goal", "")
    s = skills.find(name)
    kind = s.get("kind", "") if s else ""
    asks: list[tuple[str, str, str]] = []           # (where, query, stage id)
    if client is not None:
        for q in protomodel.github_queries(name, kind, goal)[:6]:
            asks.append(("gh", q, ""))
        for st in proto["stages"]:
            if st.get("query") and st["role"] in PER_STAGE:
                asks.append(("gh", f"{protomodel._term(name)} {st['query']}", st["id"]))
    out, seen = [], set()
    n = 0
    for where, q, sid in asks:
        if n >= limit_queries:
            break
        n += 1
        try:
            hits = protomodel.search_github(client, q, per_page=20)
        except Exception:  # noqa: BLE001 - offline or rate-limited: use what we have
            break
        for c in hits:
            if c["id"] not in seen:
                seen.add(c["id"])
                out.append({**c, "asked_by": sid})
    if session is not None:
        searches = protomodel.article_queries(name, goal)
        for st in proto["stages"]:
            if st.get("query") and st["role"] in ("deeper", "applied"):
                searches.append((f"{name} {st['query']} tutorial", ""))
        for search, filt in searches[:6]:
            try:
                hits = protomodel.search_openalex(session, search, filt, per_page=12)
            except Exception:  # noqa: BLE001
                continue
            for c in hits:
                if c["id"] not in seen:
                    seen.add(c["id"])
                    out.append({**c, "asked_by": ""})
    return out


def fill(proto: dict[str, Any], cands: list[dict[str, Any]], data: dict[str, Any] | None = None,
         model: dict[str, Any] | None = None, lean_weights: dict[str, float] | None = None,
         today: date | None = None) -> dict[str, Any]:
    """Put the best candidates into the protocol's empty stages, with the model deciding which stage fits."""
    name = proto["skill"]
    aliases = _aliases(name)
    lean_weights = taste.weights(["resource"]) if lean_weights is None else lean_weights
    by_role: dict[str, list[tuple[float, dict[str, Any]]]] = {r: [] for r in PER_STAGE}
    s = skills.find(name)
    for r in curated.for_skill(name, s["aliases"] if s else [name.lower()], data):
        by_role[_LEVEL_ROLE.get(r.get("level", ""), "basics")].append((2.0, _from_resource(r)))
    stage_of = {st["id"]: st["role"] for st in proto["stages"]}
    for c in cands:
        if c.get("archived"):
            continue
        p = protomodel.predict(c, aliases, model, today)
        role = max(PER_STAGE, key=lambda r: p.get(r, 0.0))
        if p.get(role, 0.0) < max(0.35, p.get("none", 0.0)):
            continue
        boost = 1 + (0.15 * math.log10(1 + c.get("stars", 0)) if c["kind"] == "repo"
                     else 0.1 * math.log10(1 + c.get("cited", 0)))
        if stage_of.get(c.get("asked_by", "")) == role:
            boost += 0.25
        tilt = taste.lean(f"{c['title']} {c.get('text', '')}", c.get("topics") or [], lean_weights)
        item = clean_item({"title": c["title"], "url": c["url"], "kind": _kind_of(c), "note": c.get("text") or "",
                           "stars": c.get("stars"), "lang": c.get("language"), "updated": c.get("updated"),
                           "year": c.get("year"), "cited": c.get("cited"), "venue": c.get("venue")})
        if not item:
            continue
        by_role[role].append((p[role] * boost + 0.25 * tilt, item))
    used: set[str] = set()
    out = json.loads(json.dumps(proto))
    for st in out["stages"]:
        if st["role"] not in PER_STAGE or st["items"]:
            used.update(i["url"] for i in st["items"])
            continue
        picked, articles = [], 0
        for _, it in sorted(by_role[st["role"]], key=lambda x: -x[0]):
            if it["url"] in used or len(picked) >= PER_STAGE[st["role"]]:
                continue
            if it["kind"] == "article":
                if articles >= ARTICLES_PER_STAGE:
                    continue
                articles += 1
            picked.append(it)
            used.add(it["url"])
        st["items"] = picked or [_search_link(name, st.get("query") or {"basics": "tutorial", "deeper": "awesome",
                                                                          "applied": "tutorial",
                                                                          "project": "analysis"}[st["role"]])]
    return out


def _field_projects(proto: dict[str, Any], docs: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Real repos from your field (already read by myGeeKy) that use the skill: good projects to rerun."""
    s = skills.find(proto["skill"])
    if not s:
        return []
    docs = skills.field_documents() if docs is None else docs
    out = []
    for d in docs:
        if d["source"] in ("repo", "contribute", "tool") and str(d.get("url", "")).startswith("https://") \
                and s["pattern"].search(d["text"]):
            out.append({"title": d["title"][:160], "url": d["url"], "kind": "repo", "note": "From your field"})
    return out[:2]


def build(cfg: MyGeekyConfig, skill: str, goal: str = "", client=None, session=None,
          data: dict[str, Any] | None = None, docs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The reviewed protocol if there is one, else one built now from GitHub, OpenAlex and the model.

    Raises ValueError, with a reason in plain words, for work myGeeKy doesn't cover (safety.py)."""
    from . import safety
    s = skills.find(skill)
    ok, why = safety.allowed(s["name"] if s else skill, goal, lab=bool(s and s.get("kind") == "lab"))
    if not ok:
        raise ValueError(why)                     # myGeeKy teaches analysis, never bench work
    found = find_reviewed(skill, goal, data)
    proto = json.loads(json.dumps(found)) if found else template(skill, goal)
    if not found:
        proto = fill(proto, candidates_for(proto, client, session), data)
    for st in proto["stages"]:
        if st["role"] == "project" and not [i for i in st["items"] if "github.com/search" not in i["url"]]:
            near = _field_projects(proto, docs)
            if near:
                st["items"] = near + [i for i in st["items"] if "github.com/search" not in i["url"]]
    return proto


# --------------------------------------------------------------------------- the level check
def evidence(cfg: MyGeekyConfig, proto: dict[str, Any], repos: list[dict[str, Any]] | None = None,
             mine: str | None = None) -> dict[str, dict[str, Any]]:
    """{stage id: {"known": bool, "why": str}} from your own repos and profile. A hint you can overrule."""
    from . import wins
    repos = wins.load_my_repos() if repos is None else repos
    s = skills.find(proto["skill"])
    name = s["name"] if s else proto["skill"]

    def uses(r: dict[str, Any]) -> bool:
        return (r.get("language") or "").lower() == name.lower() or bool(s and s["pattern"].search(skills.repos_text([r])))

    with_skill = [r for r in repos if uses(r)]
    profile = mine if mine is not None else " ; ".join(cfg.topics + cfg.keywords + cfg.languages)
    try:
        if mine is None:
            from .config import CV_TEXT_FILE
            profile += "\n" + CV_TEXT_FILE.read_text(encoding="utf-8", errors="ignore")[:200_000]
    except OSError:
        pass
    in_profile = bool(s and s["pattern"].search(profile)) or name.lower() in [x.lower() for x in cfg.languages]
    n = len(with_skill)
    out = {}
    for st in proto["stages"]:
        words = [w for w in re.findall(r"[a-z0-9-]{3,}", (st.get("query") or "").lower()) if w != "analysis"] or \
            (["analysis", "analyses", "pipeline"] if st.get("query") else [])
        about = [r for r in with_skill if words and any(w in skills.repos_text([r]).lower() for w in words)]
        role = st["role"]
        if role == "basics":
            known = n >= 2 or (n >= 1 and in_profile)
            why = f"{n} of your repos use {name}" if n else (f"{name} is in your profile" if in_profile else "")
        elif role == "deeper":
            known = n >= 5 or len(about) >= 2
            why = (f"{len(about)} of your {name} repos are about {words[0]}" if about else
                   f"{n} of your repos use {name}" if n else "")
        elif role in ("applied", "project"):
            need = 2 if role == "applied" else 3
            known = len(about) >= need or n >= 8
            why = f"{len(about)} of your {name} repos look like {st.get('query') or 'real work'}" if about else ""
        else:  # use
            known = n >= 1 or in_profile
            why = (f"it's in {n} of your repos" if n else "it's in your profile") if known else \
                f"Push a repo that uses {name}: this ticks itself"
        out[st["id"]] = {"known": known, "why": why}
    return out


def quiz_score(stage: dict[str, Any], answers: list[int]) -> float:
    qs = stage.get("quiz") or []
    if not qs:
        return 0.0
    right = sum(1 for q, a in zip(qs, answers) if a == q["answer"])
    return right / len(qs)


# --------------------------------------------------------------------------- how a protocol is shown
ROLE_LABEL = {"basics": "Learn the basics", "deeper": "Go deeper", "applied": "Apply it",
              "project": "Practise on a real project", "use": "Use it in your own work"}
STATUS_LABEL = {"done": "Done", "known": "You know this", "current": "Start here", "todo": "Still to do"}
STATUS_ICON = {"done": "✓", "known": "🎓", "current": "▶", "todo": ""}
# kind: (icon, what it is, the button)
RESOURCE_KINDS = {
    "repo": ("📦", "GitHub repo", "Open on GitHub"),
    "article": ("📄", "Paper", "Read the paper"),
    "book": ("📖", "Free book", "Read the book"),
    "course": ("🎓", "Course", "Start the course"),
    "tutorial": ("🧭", "Tutorial", "Follow the tutorial"),
    "video": ("🎬", "Video", "Watch it"),
    "guide": ("📘", "Guide", "Read the guide"),       # a project's or tool's own documentation
    "website": ("🌐", "Website", "Open the site"),
    "search": ("🔎", "GitHub search", "Search GitHub"),
}


def _short(n: int) -> str:
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def _host(url: str) -> str:
    from urllib.parse import urlsplit
    host = urlsplit(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


@dataclass
class Resource:
    """One link inside a step, as it's shown: what it is, its name, the facts that help you choose, and
    one clear button. A repo shows its owner, stars, language and last update; a paper its year and
    citations; a book, course or site where it lives."""
    kind: str            # repo, article, book, course, tutorial, video, website, search
    icon: str
    label: str           # "GitHub repo", "Paper", "Free book"...
    title: str           # the name to show (a repo's own name, without its owner)
    subtitle: str        # "by hadley · ⭐ 4.9k · R · updated 2025", "2014 · cited 6.1k", "r4ds.hadley.nz"
    blurb: str           # one or two lines on what it is
    action: str          # "Open on GitHub", "Read the paper"...
    url: str

    @classmethod
    def from_link(cls, it: dict[str, Any]) -> "Resource":
        url = it["url"]
        kind = "search" if url.startswith("https://github.com/search?") else it.get("kind", "website")
        icon, label, action = RESOURCE_KINDS.get(kind, RESOURCE_KINDS["website"])
        title, facts = it["title"], []
        if kind == "repo":
            owner, _, name = it["title"].partition("/") if "/" in it["title"] and " " not in it["title"] else ("", "", "")
            if name:
                title = name.replace("-", " ").replace("_", " ")
                facts.append(f"by {owner}")
            if it.get("stars"):
                facts.append(f"⭐ {_short(int(it['stars']))}")
            if it.get("lang"):
                facts.append(it["lang"])
            if it.get("updated"):
                facts.append(f"updated {str(it['updated'])[:4]}")
        elif kind in ("article", "protocol"):
            if it.get("venue"):                      # "Bio-protocol", "STAR Protocols", the journal
                facts.append(it["venue"])
            if it.get("year"):
                facts.append(str(it["year"]))
            if it.get("cited"):
                facts.append(f"cited {_short(int(it['cited']))}×")
            if not it.get("venue"):
                facts.append(_host(url).replace("doi.org", "DOI"))
        elif kind == "search":
            title = it["title"].replace("Search GitHub: ", "")
            facts.append("nothing picked yet: the most-starred matches")
        else:
            facts.append(_host(url))
        blurb = "" if kind == "search" else (it.get("note") or "")
        return cls(kind, icon, label, title, " · ".join(f for f in facts if f), blurb, action, url)


@dataclass
class Step:
    """One stage of a protocol, as it's shown: its number, what kind of step it is, where you stand
    (done, you know this, start here, still to do) and why, what you can do, and its resources."""
    number: int
    id: str
    title: str
    role: str
    role_label: str      # "Learn the basics", "Go deeper"...
    status: str          # done, known, current, todo
    status_label: str
    icon: str            # ✓ 🎓 ▶ or the number
    why: str             # "From your work: 6 of your repos use R"
    how: str             # quiz, self, evidence or ""
    score: float | None
    overruled: bool
    can_check: bool      # a quiz or "I can do these" is there
    auto: bool           # the last step: it ticks itself
    resources: list[Resource] = field(default_factory=list)

    @classmethod
    def from_stage(cls, st: dict[str, Any], number: int) -> "Step":
        status = st["status"]
        why = st.get("why") or ""
        if st["role"] == "use":
            why = f"Done: {why}" if status in ("done", "known") else (why or "Ticks itself when one of your repos shows the skill")
        elif st.get("how") == "evidence" and why:
            why = f"From your work: {why}"
        elif st.get("how") == "quiz" and st.get("score") is not None:
            why = f"You passed the check ({round(st['score'] * 100)}%)"
        elif st.get("how") == "self":
            why = "You said you can do this"
        elif st.get("overruled"):
            why = f"{why or 'Your work suggests you know this'}, but you said not yet"
        else:
            why = ""
        return cls(number=number, id=st["id"], title=st["title"], role=st["role"],
                   role_label=ROLE_LABEL.get(st["role"], "Step"), status=status,
                   status_label=STATUS_LABEL.get(status, ""), icon=STATUS_ICON.get(status) or str(number),
                   why=why, how=st.get("how", ""), score=st.get("score"), overruled=bool(st.get("overruled")),
                   can_check=bool(st.get("quiz") or st.get("can")) and status not in ("done", "known")
                   and st["role"] != "use",
                   auto=st["role"] == "use", resources=[Resource.from_link(it) for it in st.get("items") or []])


# --------------------------------------------------------------------------- your protocols
def _load() -> dict[str, dict[str, Any]]:
    data = read_json(PATHS_FILE, {}) or {}
    paths = data.get("paths") if isinstance(data, dict) else None
    return paths if isinstance(paths, dict) else {}


def _save(state: dict[str, dict[str, Any]]) -> None:
    ensure_dirs()
    write_json(PATHS_FILE, {"paths": state})


def _migrate(key: str, entry: dict[str, Any], cfg: MyGeekyConfig | None,
             data: dict[str, Any] | None) -> dict[str, Any]:
    """A learning path from before protocols (four steps per skill) becomes a protocol, its ticks kept."""
    if isinstance(entry.get("protocol"), dict):
        return entry
    proto = find_reviewed(key, "", data)
    proto = json.loads(json.dumps(proto)) if proto else fill(template(key), [], data)
    old = {"basics": "basics", "deeper": "deeper", "practice": "project"}
    done = [old[d] for d in entry.get("done") or [] if d in old]
    return {"started_at": entry.get("started_at") or date.today().isoformat(), "protocol": proto,
            "done": [st["id"] for st in proto["stages"] if st["role"] in done], "known": {}, "quiz": {},
            "removed": [], "edited": False}


def mine(cfg: MyGeekyConfig | None = None, data: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    state = _load()
    out = {}
    for key, entry in state.items():
        if not isinstance(entry, dict):
            continue
        e = _migrate(key, entry, cfg, data)
        p = clean_protocol(e["protocol"], reviewed=bool(e["protocol"].get("reviewed")) and not e.get("edited"))
        if p:
            out[p["id"]] = {**e, "protocol": p}
    return out


def _store(cfg: MyGeekyConfig | None, change) -> dict[str, dict[str, Any]]:
    state = mine(cfg)
    change(state)
    _save(state)
    return state


def start(cfg: MyGeekyConfig, proto: dict[str, Any]) -> str:
    """Keep this protocol as one of yours. Returns its id (made unique if one of yours already has it)."""
    p = clean_protocol(proto, reviewed=bool(proto.get("reviewed")))
    if not p:
        return ""

    def change(state):
        pid = p["id"]
        if pid in state and state[pid]["protocol"] != p:
            k = 2
            while f"{pid}-{k}"[:80] in state:
                k += 1
            pid = f"{pid}-{k}"[:80]
            p["id"] = pid
        state.setdefault(pid, {"started_at": date.today().isoformat(), "protocol": p, "done": [], "known": {},
                               "quiz": {}, "removed": [], "edited": False})
    _store(cfg, change)
    return p["id"]


def stop(cfg: MyGeekyConfig, pid: str) -> None:
    _store(cfg, lambda state: state.pop(pid, None))


def _stage(entry: dict[str, Any], sid: str) -> dict[str, Any] | None:
    return next((s for s in entry["protocol"]["stages"] if s["id"] == sid), None)


def tick(cfg: MyGeekyConfig, pid: str, sid: str, done: bool = True) -> None:
    def change(state):
        e = state.get(pid)
        if e:
            e["done"] = [x for x in e["done"] if x != sid] + ([sid] if done else [])
    _store(cfg, change)


def mark_known(cfg: MyGeekyConfig, pid: str, sid: str, how: str | None) -> None:
    """how: "self" (I can do these), "no" (overrule the evidence), or None (back to the evidence)."""
    def change(state):
        e = state.get(pid)
        if not e:
            return
        known = dict(e.get("known") or {})
        if how in ("self", "no"):
            known[sid] = how
        else:
            known.pop(sid, None)
        e["known"] = known
    _store(cfg, change)


def answer_quiz_score(cfg: MyGeekyConfig, pid: str, sid: str, score: float) -> float:
    """Keep a score for one stage, already marked elsewhere (quiz.py draws and marks the bank's questions)."""
    def change(state):
        e = state.get(pid)
        if e:
            e["quiz"] = {**(e.get("quiz") or {}), sid: round(float(score), 2)}
    _store(cfg, change)
    return round(float(score), 2)


def answer_quiz(cfg: MyGeekyConfig, pid: str, sid: str, answers: list[int]) -> float:
    score = 0.0

    def change(state):
        nonlocal score
        e = state.get(pid)
        st = _stage(e, sid) if e else None
        if st:
            score = quiz_score(st, answers)
            e["quiz"] = {**(e.get("quiz") or {}), sid: round(score, 2)}
    _store(cfg, change)
    return score


# ---- editing
def _edit(cfg: MyGeekyConfig, pid: str, fn) -> bool:
    ok = False

    def change(state):
        nonlocal ok
        e = state.get(pid)
        if not e:
            return
        before = json.dumps(e["protocol"], sort_keys=True)
        fn(e)
        if json.dumps(e["protocol"], sort_keys=True) != before:
            if e["protocol"].get("reviewed"):
                e["protocol"]["based_on"] = e["protocol"]["id"]
            e["protocol"]["reviewed"] = False
            e["protocol"]["source"] = "mine"
            e["edited"] = True
            ok = True
    _store(cfg, change)
    return ok


def move_stage(cfg: MyGeekyConfig, pid: str, sid: str, delta: int) -> bool:
    def fn(e):
        st = e["protocol"]["stages"]
        i = next((k for k, s in enumerate(st) if s["id"] == sid), None)
        if i is not None and 0 <= i + delta < len(st):
            st[i], st[i + delta] = st[i + delta], st[i]
    return _edit(cfg, pid, fn)


def rename_stage(cfg: MyGeekyConfig, pid: str, sid: str, title: str) -> bool:
    title = curated._text(title, 80)

    def fn(e):
        st = _stage(e, sid)
        if st and title:
            st["title"] = title
    return _edit(cfg, pid, fn)


def add_stage(cfg: MyGeekyConfig, pid: str, title: str, after: str | None = None) -> bool:
    title = curated._text(title, 80)

    def fn(e):
        st = e["protocol"]["stages"]
        if not title or len(st) >= MAX_STAGES:
            return
        ids = {s["id"] for s in st}
        sid = slug(title, 30)
        while sid in ids:
            sid = f"{sid[:34]}-{len(ids) + 1}"
        new = {"id": sid, "title": title, "role": "applied", "query": "", "skills": [e["protocol"]["skill"].lower()],
               "can": [], "quiz": [], "items": []}
        i = next((k + 1 for k, s in enumerate(st) if s["id"] == after), len(st) - (1 if st and st[-1]["role"] == "use" else 0))
        st.insert(i, new)
    return _edit(cfg, pid, fn)


def remove_stage(cfg: MyGeekyConfig, pid: str, sid: str) -> bool:
    def fn(e):
        st = e["protocol"]["stages"]
        if len(st) > 1:
            gone = _stage(e, sid)
            if gone:
                e["removed"] = list(dict.fromkeys((e.get("removed") or []) + [i["url"] for i in gone["items"]]))[-60:]
            e["protocol"]["stages"] = [s for s in st if s["id"] != sid]
    return _edit(cfg, pid, fn)


def move_item(cfg: MyGeekyConfig, pid: str, sid: str, url: str, delta: int) -> bool:
    """Up/down within its stage; past the top or bottom it moves to the stage before or after."""
    def fn(e):
        stages = e["protocol"]["stages"]
        k = next((n for n, s in enumerate(stages) if s["id"] == sid), None)
        if k is None:
            return
        items = stages[k]["items"]
        i = next((n for n, it in enumerate(items) if it["url"] == url), None)
        if i is None:
            return
        j = i + delta
        if 0 <= j < len(items):
            items[i], items[j] = items[j], items[i]
            return
        t = k + (1 if delta > 0 else -1)
        if 0 <= t < len(stages) and len(stages[t]["items"]) < MAX_ITEMS:
            it = items.pop(i)
            stages[t]["items"].insert(0 if delta > 0 else len(stages[t]["items"]), it)
    return _edit(cfg, pid, fn)


def remove_item(cfg: MyGeekyConfig, pid: str, sid: str, url: str) -> bool:
    def fn(e):
        st = _stage(e, sid)
        if st and any(i["url"] == url for i in st["items"]):
            st["items"] = [i for i in st["items"] if i["url"] != url]
            if "github.com/search" not in url:
                e["removed"] = list(dict.fromkeys((e.get("removed") or []) + [url]))[-60:]
    return _edit(cfg, pid, fn)


def add_item(cfg: MyGeekyConfig, pid: str, sid: str, url: str, title: str = "", note: str = "") -> bool:
    item = clean_item({"url": url.strip(), "title": title.strip() or url.strip(), "note": note,
                       "kind": "repo" if "github.com/" in url else "article" if "doi.org/" in url else "website"})
    if not item:
        return False

    def fn(e):
        st = _stage(e, sid)
        if st and len(st["items"]) < MAX_ITEMS and all(i["url"] != item["url"] for i in st["items"]):
            st["items"].append(item)
            e["removed"] = [u for u in e.get("removed") or [] if u != item["url"]]
    return _edit(cfg, pid, fn)


# ---- progress
def view(cfg: MyGeekyConfig, entry: dict[str, Any], ev: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """A protocol with each stage's status: done, known (how), current or todo."""
    proto = entry["protocol"]
    ev = evidence(cfg, proto) if ev is None else ev
    known_by = entry.get("known") or {}
    scores = entry.get("quiz") or {}
    stages, current = [], None
    for st in proto["stages"]:
        e = ev.get(st["id"], {"known": False, "why": ""})
        how = ""
        if st["role"] == "use":
            how = "evidence" if e["known"] else ""
        elif known_by.get(st["id"]) == "self":
            how = "self"
        elif scores.get(st["id"], 0) >= PASS:
            how = "quiz"
        elif e["known"] and known_by.get(st["id"]) != "no":
            how = "evidence"
        done = st["id"] in entry.get("done", []) or (st["role"] == "use" and bool(how))
        status = "done" if done else "known" if how else "todo"
        if status == "todo" and current is None:
            current, status = st["id"], "current"
        stages.append({**st, "status": status, "how": how, "why": e["why"], "score": scores.get(st["id"]),
                       "overruled": known_by.get(st["id"]) == "no"})
    n = sum(1 for s in stages if s["status"] in ("done", "known"))
    steps = [Step.from_stage(st, i) for i, st in enumerate(stages, 1)]
    return {**proto, "stages": stages, "steps": steps, "current": current, "done": n, "total": len(stages),
            "finished": n == len(stages), "started_at": entry.get("started_at", ""), "edited": entry.get("edited")}


def views(cfg: MyGeekyConfig, data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    out = [view(cfg, e) for e in mine(cfg, data).values()]
    return sorted(out, key=lambda p: (p["finished"], p["started_at"]))


# --------------------------------------------------------------------------- publishing yours, harvesting all
MAX_URL = 7000          # browsers and GitHub cope with ~8k (as ideas.MAX_URL)


def publish_payload(entry: dict[str, Any]) -> dict[str, Any]:
    """What a published protocol carries: its stages and links, and the links you removed. Nothing else --
    not your progress, checks or answers. Quiz and can-do lists stay out: they're the maker's, not editable."""
    p = entry["protocol"]
    payload = {k: p[k] for k in ("id", "skill", "goal", "title", "summary", "based_on")}
    payload["stages"] = [{"id": s["id"], "title": s["title"], "role": s["role"], "query": s.get("query", ""),
                          "items": [{k: it[k] for k in ("title", "url", "kind", "note")} for it in s["items"]]}
                         for s in p["stages"]]
    payload["removed"] = list(entry.get("removed") or [])
    return payload


def _json_block(payload: dict[str, Any]) -> str:
    return ("<details><summary>For myGeeKy (don't edit)</summary>\n\n```json\n"
            + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n```\n</details>\n")


def _readable(p: dict[str, Any], links: bool = True) -> str:
    lines = [f"A protocol for **{p['skill']}**" + (f" ({p['goal']})" if p.get("goal") else "")
             + (f", changed from `{p['based_on']}`" if p.get("based_on") else "") + ":", ""]
    for i, s in enumerate(p["stages"], 1):
        lines.append(f"{i}. **{s['title']}**")
        if links:
            lines.extend(f"   - [{it['title']}]({it['url']})" for it in s["items"])
    return "\n".join(lines) + "\n\n"


def _issue_url(title: str, body: str) -> str:
    from . import ideas
    return f"https://github.com/{ideas.IDEAS_REPO}/issues/new?" + urlencode(
        {"title": f"🧭 Protocol: {title}"[:120], "body": body, "labels": PUBLISH_KIND})


def publish(entry: dict[str, Any]) -> dict[str, str]:
    """{"url": a prefilled issue in the public ideas repo, sent with your own GitHub account when you
    press Submit; "clipboard": the protocol to paste there, when it's too long for a link (else "")}."""
    p = entry["protocol"]
    payload = publish_payload(entry)
    tries = [(True, False), (False, False), (False, True)]        # (readable links, drop notes)
    for links, no_notes in tries:
        pl = json.loads(json.dumps(payload))
        if no_notes:
            for s in pl["stages"]:
                for it in s["items"]:
                    it["note"] = ""
        url = _issue_url(p["title"], _readable(p, links) + _json_block(pl))
        if len(url) <= MAX_URL:
            return {"url": url, "clipboard": ""}
    text = _json_block(payload)
    return {"url": _issue_url(p["title"], _readable(p, False) + "**Paste the protocol here** (myGeeKy copied it "
                                                                "for you: Ctrl+V / ⌘V):\n\n"),
            "clipboard": text}


def publish_url(entry: dict[str, Any]) -> str:
    return publish(entry)["url"]


_JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.S)


def parse_issue(issue: dict[str, Any]) -> dict[str, Any] | None:
    """A published protocol out of an issue (someone else's text: cleaned like any other)."""
    if not str(issue.get("title") or "").startswith("🧭"):
        return None
    m = _JSON_BLOCK.search(str(issue.get("body") or ""))
    if not m:
        return None
    try:
        raw = json.loads(m.group(1))
    except ValueError:
        return None
    p = clean_protocol({**raw, "source": "mine", "by": (issue.get("user") or {}).get("login", "")})
    if not p:
        return None
    removed = [u for u in (curated._https(x) for x in (raw.get("removed") or [])[:60]) if u]
    return {"protocol": p, "removed": removed, "issue": issue.get("number"), "url": issue.get("html_url", ""),
            "state": issue.get("state", "")}


def harvest(client, limit_pages: int = 5) -> list[dict[str, Any]]:
    """Every protocol published to the ideas repo (open and closed)."""
    from . import ideas
    out = []
    for page in range(1, limit_pages + 1):
        resp = client._get(f"/repos/{ideas.IDEAS_REPO}/issues",
                           params={"state": "all", "per_page": 100, "page": page})
        if resp.status_code != 200:
            break
        rows = resp.json()
        out.extend(x for x in (parse_issue(i) for i in rows if "pull_request" not in i) if x)
        if len(rows) < 100:
            break
    return out


def main(argv: list[str] | None = None) -> int:
    """python -m mygeeky.protocols harvest [out.jsonl]   (maker side)"""
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] != "harvest":
        print(main.__doc__)
        return 2
    from pathlib import Path
    from .github_client import GitHubClient
    found = harvest(GitHubClient(None))
    out = Path(args[1]) if len(args) > 1 else Path("tools/protocol_model/published.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in found), encoding="utf-8")
    print(f"{len(found)} published protocols -> {out}")
    for x in found:
        p = x["protocol"]
        print(f"  #{x['issue']} {p['title']} by {p['by'] or '?'}: {len(p['stages'])} stages, {len(x['removed'])} removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
