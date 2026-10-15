"""Draft reviewed protocols, the maker's way (not shipped).

For each (skill, goal) below it runs exactly what the app runs when it builds
a protocol -- the same GitHub and OpenAlex searches, the same model
(protomodel.py) -- then **checks every link actually opens**, drops the dead
ones and the GitHub-search placeholders, and writes the result to
drafts.json for the maker to read, trim and paste into
src/mygeeky/data/curated.json under "protocols".

    python tools/protocols/draft.py                 # all of the list
    python tools/protocols/draft.py pcr qpcr        # only these ids

Nothing is published: a protocol only becomes "reviewed" once the maker has
read it and put it in curated.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from mygeeky import auth, protocols, safety, skills  # noqa: E402
from mygeeky.config import load_config  # noqa: E402
from mygeeky.github_client import GitHubClient, RateLimited  # noqa: E402

OUT = Path(__file__).with_name("drafts.json")
UA = {"User-Agent": "Mozilla/5.0 (compatible; myGeeKy protocol draft; +https://mygeeky.org)"}

# (id, skill, goal, title, summary) -- the three groups myGeeKy is for
WANTED = [
    # 💻 computer science
    ("git-github-teamwork", "Git", "working with others on GitHub", "Git and GitHub for working with others",
     "Branches, pull requests and reviews: how a team actually works on one repo without stepping on each other."),
    ("algorithms-interviews", "Algorithms and data structures", "technical interviews",
     "Algorithms and data structures, for interviews and for real work",
     "The handful of patterns most questions come from, and how to practise them without grinding for months."),
    ("first-web-app", "Backend development", "your first web app", "Your first web app, start to finish",
     "One small app with a database behind it, put online: the shape every later project reuses."),
    ("ml-in-practice", "Machine learning", "real projects", "Machine learning that works outside a notebook",
     "Getting from a tutorial model to one that holds up: honest validation, leakage, and putting it somewhere."),
    ("open-source-first-pr", "Open source contribution", "your first pull request",
     "Your first pull request to someone else's project",
     "Finding a good first issue, reading a codebase you didn't write, and getting a change merged."),

    # 🧪 at the bench
    ("pcr-and-gel", "PCR", "checking your product on a gel", "PCR and gel electrophoresis",
     "A reaction that works and a gel you can read: the controls, the usual failures, and what each band means."),
    ("qpcr-ddct", "qPCR", "gene expression with the ΔΔCt analysis", "qPCR, from the plate to ΔΔCt",
     "Primers, controls and a plate plan, then the Ct values turned into fold changes you can defend."),
    ("cell-culture-basics", "Cell culture", "keeping a line healthy", "Cell culture basics",
     "Aseptic work, passaging, counting and freezing: keeping a line alive, clean and comparable."),
    ("western-blot-quant", "Western blot", "quantifying your bands", "Western blot, and quantifying it honestly",
     "From lysate to a blot that can be measured, and the quantification rules reviewers look for."),
    ("microscopy-quantification", "Image quantification", "measuring what you see",
     "Microscopy images into numbers, with Fiji",
     "Acquiring images you're allowed to compare, then measuring them in Fiji without fooling yourself."),

    # 🧬 bench → analysis: the group with the least data analysis so far
    ("excel-to-r", "R", "your first analysis of your own lab data", "From Excel to R, with your own lab data",
     "Your own spreadsheet, read into R and plotted: the gentlest possible start, with no programming before."),
    ("stats-for-the-bench", "Statistics basics", "choosing and running the right test",
     "Statistics for the bench: which test, and why",
     "t-test, ANOVA and their assumptions, in the words of an experiment: replicates, controls and what p means."),
    ("figures-for-papers", "Scientific plotting", "publication-quality figures",
     "Figures your reviewers won't ask you to redo",
     "One script that makes the figure, so it can be remade when the data changes: axes, colour, and honesty."),
    ("plate-reader-to-plot", "Plate reader assays", "from the plate to a plot",
     "Plate-reader data into a plot you can publish",
     "Raw wells to a tidy table to a curve: blanks, replicates, standard curves and the plot at the end."),
]


def alive(url: str, session: requests.Session) -> bool:
    """Does this link actually open? (A HEAD, then a GET for sites that dislike HEAD.)"""
    for method in (session.head, session.get):
        try:
            r = method(url, timeout=25, headers=UA, allow_redirects=True)
            if r.status_code < 400:
                return True
            if r.status_code in (405, 403, 429):      # the site dislikes us, not the link
                continue
        except requests.RequestException:
            continue
    return False


def main() -> int:
    only = {a.lower() for a in sys.argv[1:]}
    cfg = load_config()
    token = auth.get_token(cfg.github_username) if cfg.github_username else None
    client = GitHubClient(token, search_pause=2.2)
    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    with requests.Session() as session:
        for pid, skill, goal, title, summary in WANTED:
            if (only and pid not in only) or pid in out:
                continue
            s = skills.find(skill)
            ok, why = safety.allowed(s["name"] if s else skill, goal, lab=bool(s and s.get("kind") == "lab"))
            if not ok:
                print(f"{pid}: left out ({why})")
                continue
            for attempt in range(4):
                try:
                    proto = protocols.build(cfg, skill, goal, client=client, session=session)
                    break
                except RateLimited:
                    wait = max(5.0, client._blocked_until - time.time()) + 3
                    print(f"  waiting {wait:.0f}s for GitHub's search limit", flush=True)
                    time.sleep(wait)
                    client._blocked_until = 0.0
            else:
                print(f"{pid}: gave up on GitHub's limit")
                continue
            proto.update(id=pid, title=title, summary=summary)
            kept = 0
            for st in proto["stages"]:
                items = []
                for it in st["items"]:
                    if "github.com/search" in it["url"]:
                        continue
                    if alive(it["url"], session):
                        items.append(it)
                    else:
                        print(f"  dead: {it['url']}")
                st["items"] = items[:3]
                st["quiz"] = []
                kept += len(st["items"])
            out[pid] = proto
            OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"{pid}: {len(proto['stages'])} stages, {kept} links that open", flush=True)
    print(f"{len(out)} drafts -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
