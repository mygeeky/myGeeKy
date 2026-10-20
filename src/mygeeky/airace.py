"""The AI race (News → 🏁 AI race): who leads, how far open models trail, what's new, and what each model is best at.

The numbers come from Epoch AI's open Benchmarking Hub (CC BY 4.0; credited wherever they're shown). Once a day a
GitHub Action (.github/workflows/ai-race.yml) downloads Epoch's data, `build()` turns it into one small file,
data/ai_race.json, and every myGeeKy reads that file from GitHub (`refresh_if_due`), falling back to the copy it
shipped with. No key and no server.

Skill groups are myGeeKy's own, not Epoch's: each benchmark is scored from a random guess (0) to its ceiling (1),
a group averages its benchmarks, and models are ranked within a group only if they're from the last 18 months and
have enough results there. A model is "best at" the group where it ranks highest against the others.

`stats()` works out everything the page shows; the phone does the same (lib/ai-race.ts), and
tests/test_airace.py checks both give the same answers on the same file.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR, ensure_dirs
from .files import read_json, write_json

BUNDLED = Path(__file__).parent / "data" / "ai_race.json"
PHONE_COPY = Path(__file__).resolve().parents[2] / "mobile" / "src" / "data" / "ai_race.json"
CACHE_FILE = DATA_DIR / "ai_race.json"
REMOTE_URL = "https://raw.githubusercontent.com/mygeeky/myGeeKy/main/src/mygeeky/data/ai_race.json"
EPOCH_ZIP = "https://epoch.ai/data/benchmark_data.zip"
SOURCE = "Epoch AI, Benchmarking Hub (CC BY 4.0)"
CHECK_EVERY_HOURS = 24
RECENT_MONTHS = 18          # only models this new are ranked within a skill
FRESH_DAYS = 14             # "NEW" on a release this recent
SINCE = "2024-01"           # the race and the gap start here
TOP_PER_GROUP = 8

# the skills, in a fixed order (the fingerprints colour them in this order), and Epoch's benchmarks in each
GROUPS: dict[str, list[str]] = {
    "Reasoning": ["ARC-AGI", "ARC-AGI-2", "SimpleBench", "Mystery Game Puzzles", "Chess Puzzles", "BBH"],
    "Coding": ["SWE-Bench verified", "Aider polyglot", "Terminal Bench", "FrontierCode", "DeepSWE", "FrontierSWE",
               "MirrorCode", "GSO-Bench", "WeirdML"],
    "Math": ["FrontierMath-Tiers-1-3-v2-Private", "FrontierMath-Tier-4-v2-Private", "MATH level 5",
             "OTIS Mock AIME 2024-2025", "GSM8K", "ProofBench"],
    "Science": ["GPQA diamond", "HLE", "ScienceQA", "Surface Evolver Bench"],
    "Agents": ["OSWorld", "OSWorld 2.0", "The Agent Company", "APEX-Agents", "METR Time Horizons", "Remote Labor Index",
               "GDPval", "Balrog", "PostTrainBench", "DeepResearch Bench"],
    "Knowledge": ["SimpleQA Verified", "MMLU", "TriviaQA"],
    "Writing": ["Lech Mazur Writing", "Fiction.LiveBench", "CL-bench", "CL-bench Life"],
    "Vision": ["VPCT", "GeoBench", "CadEval"],
    "Security": ["Cybench", "ExploitBench"],
}
SKILLS = list(GROUPS)       # the skills in order (the fingerprints colour them in this order)
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_loaded: dict[str, Any] | None = None


# --------------------------------------------------------------------------- building it (the daily Action)
def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def build(files: dict[str, str], today: date | None = None) -> dict[str, Any]:
    """Epoch's CSV files (name -> text) to the page's data."""
    today = today or date.today()
    rows = lambda name: list(csv.DictReader(io.StringIO(files.get(name, ""))))  # noqa: E731
    version_of = {r["model_version"]: r["model_group"] for r in rows("model_metadata.csv") if r.get("model_version")}
    eci = {r["Model"]: r for r in rows("epoch_capabilities_index/eci_scores.csv") if r.get("Model")}
    meta = {b["benchmark"]: b for b in rows("benchmark_metadata.csv") if b.get("source_file")}
    recent = (today - timedelta(days=round(RECENT_MONTHS * 30.44))).isoformat()

    scores: dict[str, dict[str, float]] = defaultdict(dict)
    have: Counter = Counter()
    for names in GROUPS.values():
        for name in names:
            b = meta.get(name)
            if not b:
                continue
            scale, base, ceil = _num(b["scale"]) or 1.0, _num(b["random_baseline"]) or 0.0, _num(b["score_ceiling"]) or 1.0
            if ceil <= base:
                continue
            for r in rows(b["source_file"]):
                model, s = version_of.get(r.get("Model version", "")), _num(r.get(b["score_column"]))
                if model in eci and s is not None:
                    v = max(0.0, min(1.0, (s * scale - base) / (ceil - base)))   # scale: 0.01 for a %
                    scores[model][name] = max(v, scores[model].get(name, 0.0))
                    have[name] += 1

    groups_out: dict[str, Any] = {}
    by_model: dict[str, dict[str, Any]] = defaultdict(dict)
    for group, names in GROUPS.items():
        used = [n for n in names if have[n]]
        need = 2 if len(used) > 3 else 1
        ranked = []
        for model, s in scores.items():
            if (eci[model].get("date") or "") < recent:
                continue
            got = [s[n] for n in used if n in s]
            if len(got) >= need:
                ranked.append((round(sum(got) / len(got), 3), len(got), model))
        ranked.sort(key=lambda r: (-r[0], -r[1], r[2]))
        for i, (v, _, m) in enumerate(ranked):
            by_model[m][group] = {"score": v, "pct": round(1 - i / (len(ranked) - 1), 3) if len(ranked) > 1 else 1.0}
        groups_out[group] = {"benchmarks": used, "ranked": len(ranked),
                             "top": [{"model": m, "score": v, "n": k} for v, k, m in ranked[:TOP_PER_GROUP]]}

    models = []
    for m, r in eci.items():
        e, d = _num(r.get("eci")), r.get("date") or ""
        if e is None or not _DATE.match(d):
            continue
        gs = by_model.get(m, {})
        best = max(gs.items(), key=lambda kv: (kv[1]["pct"], kv[1]["score"], kv[0]))[0] if len(gs) >= 3 else ""
        models.append({"model": m, "eci": round(e, 2), "date": d, "org": (r.get("Organization") or "").strip(),
                       "open": r.get("Accessibility group") == "Open weights", "best": best, "groups": gs})
    models.sort(key=lambda x: (x["date"], x["model"]))
    return {"version": today.isoformat(), "source": SOURCE, "models": models, "groups": groups_out}


def build_from_zip(data: bytes, today: date | None = None) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        files = {n: z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith(".csv")}
    return build(files, today)


def save(data: dict[str, Any], path: Path = BUNDLED) -> Path:
    """Write the page's data, and the phone's identical copy next to it."""
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    if path == BUNDLED and PHONE_COPY.parent.is_dir():
        PHONE_COPY.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- reading it (untrusted: from the internet)
def _clean_model(m: Any) -> dict[str, Any] | None:
    if not isinstance(m, dict):
        return None
    name, e, d = str(m.get("model") or "").strip()[:80], _num(m.get("eci")), str(m.get("date") or "")
    if not name or e is None or not _DATE.match(d):
        return None
    groups = {}
    for g, v in (m.get("groups") or {}).items() if isinstance(m.get("groups"), dict) else []:
        s, p = _num((v or {}).get("score")) if isinstance(v, dict) else None, _num((v or {}).get("pct")) if isinstance(v, dict) else None
        if g in GROUPS and s is not None and p is not None:
            groups[g] = {"score": max(0.0, min(1.0, s)), "pct": max(0.0, min(1.0, p))}
    best = str(m.get("best") or "")
    return {"model": name, "eci": e, "date": d, "org": str(m.get("org") or "").strip()[:80], "open": m.get("open") is True,
            "best": best if best in groups else "", "groups": groups}


def clean(data: Any) -> dict[str, Any]:
    data = data if isinstance(data, dict) else {}
    models = [c for c in (_clean_model(m) for m in (data.get("models") or [])[:2000] if isinstance(data.get("models"), list)) if c]
    models.sort(key=lambda x: (x["date"], x["model"]))
    groups = {}
    raw = data.get("groups") if isinstance(data.get("groups"), dict) else {}
    for g in GROUPS:
        v = raw.get(g) if isinstance(raw.get(g), dict) else {}
        top = []
        for t in (v.get("top") or [])[:TOP_PER_GROUP] if isinstance(v.get("top"), list) else []:
            s = _num((t or {}).get("score")) if isinstance(t, dict) else None
            if s is not None and str(t.get("model") or "").strip():
                top.append({"model": str(t["model"]).strip()[:80], "score": max(0.0, min(1.0, s)), "n": int(_num(t.get("n")) or 0)})
        groups[g] = {"benchmarks": [str(b)[:60] for b in (v.get("benchmarks") or [])[:30] if isinstance(b, str)]
                     if isinstance(v.get("benchmarks"), list) else [],
                     "ranked": int(_num(v.get("ranked")) or 0), "top": top}
    version = str(data.get("version") or "")
    return {"version": version if _DATE.match(version) else "", "source": SOURCE, "models": models, "groups": groups}


def load(force: bool = False) -> dict[str, Any]:
    """The newest race data we have: the one shipped with myGeeKy, or a newer one fetched since."""
    global _loaded
    if _loaded is not None and not force:
        return _loaded
    shipped = clean(read_json(BUNDLED, {}))
    fetched = clean((read_json(CACHE_FILE, {}) or {}).get("data"))
    _loaded = fetched if fetched["models"] and fetched["version"] >= shipped["version"] else shipped
    return _loaded


def refresh_if_due(force: bool = False, now: datetime | None = None, timeout: float = 20.0) -> bool:
    """Fetch the newest race data from GitHub, at most once a day. True if a newer one arrived."""
    global _loaded
    import requests
    now = now or datetime.now(timezone.utc)
    cached = read_json(CACHE_FILE, {}) or {}
    if not force:
        try:
            if (now - datetime.fromisoformat(cached.get("checked_at", ""))).total_seconds() < CHECK_EVERY_HOURS * 3600:
                return False
        except (TypeError, ValueError):
            pass
    r = requests.get(REMOTE_URL, timeout=timeout, headers={"User-Agent": "mygeeky"})
    ensure_dirs()
    if getattr(r, "status_code", 200) != 200 or len(r.content) > 3_000_000:
        write_json(CACHE_FILE, {**(cached if isinstance(cached, dict) else {}), "checked_at": now.isoformat(timespec="seconds")})
        return False
    data = clean(r.json())
    old = clean(cached.get("data")) if isinstance(cached, dict) else clean({})
    write_json(CACHE_FILE, {"checked_at": now.isoformat(timespec="seconds"), "data": data})
    _loaded = None
    return data["version"] > old["version"]


# --------------------------------------------------------------------------- what the page shows
def _month_end(y: int, m: int) -> str:
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    return (nxt - timedelta(days=1)).isoformat()


def _round(x: float, places: int = 0) -> float:
    """Rounded as JavaScript's Math.round does (halves up), so both apps agree."""
    k = 10 ** places
    return math.floor(x * k + 0.5) / k


def org_of(m: dict[str, Any]) -> str:
    return (m.get("org") or "").split(",")[0].strip() or "Not given"


def months_between(first: str, last: str) -> list[str]:
    y, mo = int(first[:4]), int(first[5:7])
    out = []
    while True:
        end = _month_end(y, mo)
        out.append(end)
        if end >= last:
            return out
        y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)


def _best(models: list[dict[str, Any]], until: str, open_: bool | None = None) -> dict[str, Any] | None:
    best = None
    for m in models:
        if m["date"] <= until and (open_ is None or m["open"] == open_) and (best is None or m["eci"] > best["eci"]):
            best = m
    return best


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def race(data: dict[str, Any], until: str, lanes: int = 6) -> list[dict[str, Any]]:
    """Each lab's best model up to `until`, the leaders first."""
    best: dict[str, dict[str, Any]] = {}
    for m in data["models"]:
        o = org_of(m)
        if m["date"] <= until and (o not in best or m["eci"] > best[o]["eci"]):
            best[o] = m
    rows = sorted(best.items(), key=lambda kv: (-kv[1]["eci"], kv[0]))[:lanes]
    return [{"org": o, "model": m["model"], "eci": m["eci"], "open": m["open"]} for o, m in rows]


def pick(data: dict[str, Any], skills: list[str], n: int = 5) -> list[dict[str, Any]]:
    """The models best for a mix of skills: their average over those skills, among models with all of them."""
    skills = [s for s in skills if s in GROUPS]
    if not skills:
        return []
    rows = [{"model": m["model"], "open": m["open"],
             "score": _round(sum(m["groups"][s]["score"] for s in skills) / len(skills), 3)}
            for m in data["models"] if all(s in m["groups"] for s in skills)]
    rows.sort(key=lambda r: (-r["score"], r["model"]))
    return rows[:n]


def stats(data: dict[str, Any]) -> dict[str, Any]:
    """Everything the page shows, worked out once."""
    models = data["models"]
    if not models:
        return {"empty": True}
    by_eci = sorted(models, key=lambda m: (-m["eci"], m["model"]))
    leader = by_eci[0]
    best_open = next((m for m in by_eci if m["open"]), None)
    newest = models[-1]["date"]
    months = months_between(min(m["date"] for m in models), newest)
    closed = [_best(models, e, False) for e in months]
    opened = [_best(models, e, True) for e in months]
    behind = []
    for i, o in enumerate(opened):
        if o is None:
            behind.append(None)
            continue
        j = next((k for k, c in enumerate(closed) if c and c["eci"] >= o["eci"]), -1)
        behind.append(0 if j < 0 or j > i else int(_round(_days(months[j], months[i]) / 30.44)))
    ago = _best(models, months[max(0, len(months) - 13)])
    orgs: dict[str, float] = {}
    for m in models:
        orgs[org_of(m)] = max(orgs.get(org_of(m), 0.0), m["eci"])
    runner = sorted(((o, e) for o, e in orgs.items() if o != org_of(leader)), key=lambda kv: (-kv[1], kv[0]))
    rank = {m["model"]: i + 1 for i, m in enumerate(by_eci)}
    recent = []
    for m in sorted(models, key=lambda m: (m["date"], m["model"]), reverse=True)[:6]:
        recent.append({"model": m["model"], "date": m["date"], "org": org_of(m), "open": m["open"], "best": m["best"],
                       "rank": rank[m["model"]], "fresh": _days(m["date"], newest) <= FRESH_DAYS})
    start = next((i for i, e in enumerate(months) if e[:7] >= SINCE), 0)
    counts = Counter(m["best"] for m in models if m["best"])
    best_at = []
    for g in sorted(GROUPS, key=lambda g: (-counts[g], list(GROUPS).index(g))):
        mine = sorted((m for m in models if m["best"] == g), key=lambda m: (-m["eci"], m["model"]))
        best_at.append({"group": g, "models": [{"model": m["model"], "open": m["open"]} for m in mine],
                        "top": [{**t, "open": next((m["open"] for m in models if m["model"] == t["model"]), False)}
                                for t in data["groups"].get(g, {}).get("top", [])[:5]]})
    prints = [{"model": m["model"], "eci": m["eci"], "best": m["best"], "groups": m["groups"]}
              for m in by_eci if len(m["groups"]) >= 3][:6]
    return {
        "empty": False, "version": data.get("version", ""), "count": len(models), "open_count": sum(m["open"] for m in models),
        "leader": {"model": leader["model"], "org": org_of(leader), "eci": leader["eci"]},
        "runner_up": {"org": runner[0][0], "eci": runner[0][1]} if runner else None,
        "best_open": {"model": best_open["model"], "org": org_of(best_open), "eci": best_open["eci"]} if best_open else None,
        "rise": _round(leader["eci"] - ago["eci"], 1) if ago else 0.0,
        "behind_now": behind[-1] or 0,
        "months": months[start:], "closed": [c["eci"] if c else None for c in closed[start:]],
        "open": [o["eci"] if o else None for o in opened[start:]], "behind": behind[start:],
        "recent": recent, "best_at": best_at, "prints": prints, "newest": newest,
    }


def main(argv: list[str] | None = None) -> int:
    """`python -m mygeeky.airace build`: download Epoch's data and write data/ai_race.json (the daily Action)."""
    import sys

    import requests
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] != ["build"]:
        print("usage: python -m mygeeky.airace build")
        return 2
    r = requests.get(EPOCH_ZIP, timeout=120, headers={"User-Agent": "mygeeky"})
    r.raise_for_status()
    data = build_from_zip(r.content)
    if len(data["models"]) < 50:
        print(f"only {len(data['models'])} models: Epoch's files may have changed shape; keeping the old data")
        return 1
    old = clean(read_json(BUNDLED, {}))
    if [m for m in old["models"]] == data["models"] and old["groups"] == clean(data)["groups"]:
        print("no change")
        return 0
    save(data)
    print(f"wrote {BUNDLED}: {len(data['models'])} models")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
