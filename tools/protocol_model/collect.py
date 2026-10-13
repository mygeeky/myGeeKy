"""Collect training candidates for the protocol model (maker side, not shipped).

For each skill below, run the same searches the app runs when it builds a
protocol (protomodel.github_queries / article_queries), plus a plain
"most-starred" search that brings in libraries and tools (the "none" class),
and write every hit once to candidates.jsonl:

    python tools/protocol_model/collect.py            # uses myGeeKy's saved read-only GitHub token

The token is read from the system keyring the app stored it in, and never printed.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from mygeeky import auth, protomodel, skills  # noqa: E402
from mygeeky.config import load_config  # noqa: E402
from mygeeky.github_client import GitHubClient, RateLimited  # noqa: E402

OUT = Path(__file__).with_name("candidates.jsonl")

# (skill, a goal people learn it for)
SKILLS = [
    ("R", "data analysis"), ("Python", "data analysis"), ("Julia", ""), ("Rust", ""), ("SQL", ""), ("Bash", ""),
    ("Git", ""), ("Docker", ""), ("Conda", ""), ("Slurm", "HPC"), ("Nextflow", ""), ("Snakemake", ""),
    ("Galaxy", ""), ("Jupyter", ""), ("Quarto", ""), ("R Markdown", ""), ("Reproducible research", ""),
    ("pandas", ""), ("NumPy", ""), ("scikit-learn", ""), ("tidyverse", ""), ("ggplot2", ""), ("Shiny", ""),
    ("Data visualization", ""), ("DuckDB", ""), ("PyTorch", ""), ("Machine learning", ""), ("Deep learning", ""),
    ("Large language models", ""), ("Graph neural networks", ""), ("NLP", ""), ("Bayesian statistics", ""),
    ("Stan", ""), ("Causal inference", ""), ("Mixed models", ""), ("Survival analysis", ""), ("Time series", ""),
    ("Meta-analysis", ""), ("Genomics", ""), ("GWAS", ""), ("Fine-mapping", ""), ("Mendelian randomization", ""),
    ("Population genetics", ""), ("Phylogenetics", ""), ("Variant calling", ""), ("RNA-seq", ""),
    ("Single-cell RNA-seq", ""), ("Spatial transcriptomics", ""), ("Metagenomics", ""), ("Proteomics", ""),
    ("Bioconductor", ""), ("Epidemiology", ""), ("Biostatistics", ""), ("GIS", ""), ("LaTeX", ""),
]


def main() -> int:
    cfg = load_config()
    token = auth.get_token(cfg.github_username) if cfg.github_username else None
    client = GitHubClient(token, search_pause=2.2)
    session = requests.Session()
    seen, finished = set(), set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                seen.add(row["id"])
                if row.get("how") == "plain":
                    finished.add(row["skill"])
    with OUT.open("a", encoding="utf-8") as f:
        for name, goal in SKILLS:
            s = skills.find(name) or {"name": name, "kind": "", "aliases": [name.lower()]}
            if s["name"] in finished:
                continue
            n = 0
            queries = [(q, "learn") for q in protomodel.github_queries(s["name"], s.get("kind", ""), goal)]
            queries.append((protomodel._term(s["name"]), "plain"))
            for q, how in queries:
                hits = None
                for _ in range(4):
                    try:
                        hits = protomodel.search_github(client, q, per_page=25)
                        break
                    except RateLimited:
                        wait = max(5.0, client._blocked_until - time.time()) + 3
                        print(f"  waiting {wait:.0f}s for GitHub's search limit", flush=True)
                        time.sleep(wait)
                        client._blocked_until = 0.0
                    except Exception as exc:  # noqa: BLE001
                        print(f"  ! {q}: {type(exc).__name__}", flush=True)
                        break
                if hits is None:
                    continue
                time.sleep(2.5)
                for c in hits:
                    if c["id"] in seen:
                        continue
                    seen.add(c["id"])
                    f.write(json.dumps({**c, "skill": s["name"], "query": q, "how": how}, ensure_ascii=False) + "\n")
                    n += 1
            for search, filt in protomodel.article_queries(s["name"], goal):
                try:
                    hits = protomodel.search_openalex(session, search, filt, per_page=15)
                except Exception as exc:  # noqa: BLE001
                    print(f"  ! {search}: {type(exc).__name__}", flush=True)
                    continue
                for c in hits:
                    if c["id"] in seen:
                        continue
                    seen.add(c["id"])
                    f.write(json.dumps({**c, "skill": s["name"], "query": f"{search} [{filt}]", "how": "article"},
                                       ensure_ascii=False) + "\n")
                    n += 1
            f.flush()
            print(f"{s['name']}: +{n}", flush=True)
    print(f"total {len(seen)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
