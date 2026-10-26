"""Draft the 🌟 Leading lights lists: living people who lead a field, each with why (a badge and its source).

    python tools/lights_build.py                     # writes a draft and a review table; nothing is published

Three free sources, asked politely (spaced, batched):
  * Wikidata: winners of the prizes in PRIZES since MIN_YEAR, with no date of death; Wikidata often already has their
    ORCID, OpenAlex id, Google Scholar id and GitHub login.
  * OpenAlex: the most cited authors on each topic in TOPICS, and the authors of each tool's paper in TOOLS (first and
    last author). Everyone is looked up 50 at a time by id (1 credit a batch), never one name search per person.
  * Everyone must still be publishing (a work in the last ACTIVE_YEARS years): it also leaves out people who retired.

The maintainer reads the review table (tools/lights_review.md) and removes anyone wrong before the list is used
(src/mygeeky/data/lights.json, and the identical mobile/src/data/lights.json). A run costs about 50-100 OpenAlex
credits, once.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from mygeeky import lights  # noqa: E402

OPENALEX = "https://api.openalex.org"
WIKIDATA = "https://query.wikidata.org/sparql"
UA = {"User-Agent": "mygeeky-lights-builder (https://mygeeky.org; mailto:support@mygeeky.org)"}
MIN_YEAR = 2005
ACTIVE_YEARS = 3
PER_TOPIC = 12

# prize (Wikidata item) -> (what the badge says, the field it belongs to)
PRIZES = {
    "Q80061": ("Nobel Prize in Physiology or Medicine", "Biology & medicine"),
    "Q44585": ("Nobel Prize in Chemistry", "Chemistry"),
    "Q185667": ("Turing Award", "Computer science & AI"),
}
# OpenAlex topic id -> field (an id, not a search: a search can land on the wrong topic, and costs 10 credits)
TOPICS = {"T10308": "Biology & medicine",          # Systemic Lupus Erythematosus Research
          "T10261": "Genetics & genomics"}         # Genetic Associations and Epidemiology (GWAS)
# authors OpenAlex matched wrongly to a tool paper, found in review
NOT_THEM = {"Jianhua Zhang"}
# tool -> (the title of its main paper, field)
TOOLS = {
    "scikit-learn": ("Scikit-learn: Machine Learning in Python", "Computer science & AI"),
    "Seurat": ("Integrated analysis of multimodal single-cell data", "Genetics & genomics"),
    "PLINK": ("PLINK: A Tool Set for Whole-Genome Association and Population-Based Linkage Analyses",
              "Genetics & genomics"),
    "Bioconductor": ("Bioconductor: open software development for computational biology and bioinformatics",
                     "Genetics & genomics"),
}

session = requests.Session()
session.headers.update(UA)


def _get(url: str, **params) -> dict:
    for attempt in range(3):
        r = session.get(url, params=params, timeout=60)
        if r.status_code == 200:
            time.sleep(0.3)
            return r.json()
        time.sleep(2 + attempt * 3)
    raise RuntimeError(f"{url} answered {r.status_code}")


def prize_winners() -> list[dict]:
    values = " ".join(f"wd:{q}" for q in PRIZES)
    query = f"""
SELECT ?p ?pLabel ?award ?year ?orcid ?oa ?gs ?gh WHERE {{
  VALUES ?award {{ {values} }}
  ?p p:P166 ?st . ?st ps:P166 ?award . ?st pq:P585 ?when .
  BIND(YEAR(?when) AS ?year) FILTER(?year >= {MIN_YEAR})
  FILTER NOT EXISTS {{ ?p wdt:P570 ?died }}
  OPTIONAL {{ ?p wdt:P496 ?orcid }} OPTIONAL {{ ?p wdt:P10283 ?oa }}
  OPTIONAL {{ ?p wdt:P1960 ?gs }} OPTIONAL {{ ?p wdt:P2037 ?gh }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}"""
    rows = _get(WIKIDATA, query=query, format="json")["results"]["bindings"]
    out: dict[str, dict] = {}
    for b in rows:
        v = {k: b[k]["value"] for k in b}
        qid = v["p"].rsplit("/", 1)[-1]
        award = v["award"].rsplit("/", 1)[-1]
        name, field = PRIZES[award]
        p = out.setdefault(qid, {"wikidata": qid, "name": v.get("pLabel", ""), "badge": "nobel" if "Nobel" in name else "prize",
                                 "why": f"{name} {v.get('year', '')}".strip(), "source": f"https://www.wikidata.org/wiki/{qid}",
                                 "field": field})
        p["orcid"] = p.get("orcid") or v.get("orcid", "")
        p["openalex"] = p.get("openalex") or v.get("oa", "")
        p["scholar"] = p.get("scholar") or (f"https://scholar.google.com/citations?user={v['gs']}" if v.get("gs") else "")
        p["github"] = p.get("github") or v.get("gh", "")
    return list(out.values())


def most_cited(tid: str, field: str) -> list[dict]:
    found = [_get(f"{OPENALEX}/topics/{tid}")]                  # by id: free
    authors = _get(f"{OPENALEX}/authors", filter=f"topics.id:{tid}", sort="cited_by_count:desc",
                   **{"per-page": PER_TOPIC * 2})["results"]
    return [{"openalex": a["id"].rsplit("/", 1)[-1], "name": a["display_name"], "badge": "cited",
             "why": f"Among the most cited in {found[0]['display_name']}",
             "source": f"https://openalex.org/{tid}", "field": field} for a in authors]


def tool_builders(tool: str, title: str, field: str) -> list[dict]:
    works = _get(f"{OPENALEX}/works", filter=f"title.search:{title}", sort="cited_by_count:desc", **{"per-page": 1})["results"]
    if not works:
        return []
    w = works[0]
    names = [a for a in w.get("authorships") or [] if (a.get("author") or {}).get("id")]
    pick = names[:1] + names[-1:] if len(names) > 1 else names
    return [{"openalex": a["author"]["id"].rsplit("/", 1)[-1], "name": a["author"]["display_name"], "badge": "tool",
             "why": f"Behind {tool} ({w.get('cited_by_count', 0):,} citations)", "source": w["id"], "field": field}
            for a in pick if a["author"]["display_name"] not in NOT_THEM]


def enrich(people: list[dict]) -> list[dict]:
    """Fill in each person from OpenAlex, 50 at a time by OpenAlex id or ORCID, and keep only those still publishing."""
    by_oa = [p for p in people if p.get("openalex")]
    by_orcid = [p for p in people if not p.get("openalex") and p.get("orcid")]
    found: dict[str, dict] = {}
    for group, key, field in ((by_oa, "openalex", "openalex"), (by_orcid, "orcid", "orcid")):
        ids = list(dict.fromkeys(p[key] for p in group))
        for i in range(0, len(ids), 50):
            for a in _get(f"{OPENALEX}/authors", filter=f"{field}:{'|'.join(ids[i:i + 50])}", **{"per-page": 50})["results"]:
                aid = a["id"].rsplit("/", 1)[-1]
                found[aid] = a
                if a.get("orcid"):
                    found["orcid:" + a["orcid"].rsplit("/", 1)[-1]] = a
    year, out = date.today().year, []
    for p in people:
        a = found.get(p.get("openalex", "")) or found.get("orcid:" + p.get("orcid", ""))
        if not a:
            print(f"  not found on OpenAlex, left out: {p['name']}", file=sys.stderr)
            continue
        recent = sum(c.get("works_count", 0) for c in a.get("counts_by_year") or [] if c.get("year", 0) > year - ACTIVE_YEARS)
        if not recent:
            print(f"  nothing in {ACTIVE_YEARS} years, left out: {p['name']}", file=sys.stderr)
            continue
        inst = (a.get("last_known_institutions") or [{}])[0].get("display_name", "")
        orcid = (a.get("orcid") or "").rsplit("/", 1)[-1] or p.get("orcid", "")
        out.append({"id": a["id"].rsplit("/", 1)[-1], "name": a["display_name"] or p["name"], "badge": p["badge"],
                    "why": p["why"], "source": p["source"], "field": p["field"],
                    "topics": [t["display_name"] for t in (a.get("topics") or [])[:6]], "institution": inst,
                    "orcid": orcid, "scholar": p.get("scholar", ""), "github": p.get("github", ""),
                    "cited": a.get("cited_by_count", 0), "h": (a.get("summary_stats") or {}).get("h_index", 0)})
    return out


def main() -> None:
    people = prize_winners()
    print(f"Wikidata: {len(people)} living prize winners since {MIN_YEAR}", file=sys.stderr)
    for topic, field in TOPICS.items():
        got = most_cited(topic, field)
        print(f"OpenAlex: {len(got)} most cited on {topic}", file=sys.stderr)
        people += got
    for tool, (title, field) in TOOLS.items():
        got = tool_builders(tool, title, field)
        print(f"OpenAlex: {len(got)} behind {tool}", file=sys.stderr)
        people += got
    rows = enrich(people)
    best: dict[str, dict] = {}
    rank = {"nobel": 0, "prize": 1, "tool": 2, "cited": 3}
    for r in rows:                                     # one person found twice keeps the strongest reason
        if r["id"] not in best or rank[r["badge"]] < rank[best[r["id"]]["badge"]]:
            best[r["id"]] = r
    cited = {}
    for r in sorted(best.values(), key=lambda r: -r["cited"]):    # most cited: a few per topic
        if r["badge"] == "cited":
            cited.setdefault(r["why"], []).append(r)
    keep = [r for r in best.values() if r["badge"] != "cited"] + [r for v in cited.values() for r in v[:PER_TOPIC]]
    data = lights.clean({"version": date.today().isoformat(), "people": keep})
    draft = ROOT / "tools" / "lights_draft.json"
    draft.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["| keep | name | badge | why | institution | topics | scholar |", "|---|---|---|---|---|---|---|"]
    for p in data["people"]:
        lines.append(f"| ☐ | {p['name']} | {p['badge']} | {p['why']} | {p['institution']} | "
                     f"{', '.join(p['topics'][:3])} | {'yes' if p['scholar'] else ''} |")
    (ROOT / "tools" / "lights_review.md").write_text("# Leading lights: draft to review\n\n" + "\n".join(lines) + "\n",
                                                    encoding="utf-8")
    print(f"{len(data['people'])} people: {draft} and tools/lights_review.md", file=sys.stderr)


if __name__ == "__main__":
    main()
