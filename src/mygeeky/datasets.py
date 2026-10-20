"""Grow → 🗂️ Data: public datasets to practise and train on, across the sciences.

A hand-checked core (data/datasets_core.json) plus records harvested from trusted sources -- the Galaxy Training
Network and field searches on Zenodo, GEO's curated DataSets, and OpenML's vetted CC18 suite -- all passing the
same rules (`accept`, written out in .claude/skills/mygeeky-datasets/SKILL.md): open licence, one click with no
login, laptop-sized, common formats, documented, stable, validated or used, no personal data, and saying what to
practise. `build()` (run weekly by .github/workflows/datasets.yml) writes data/datasets.json and the phone's
identical copy; every myGeeKy reads the newest from GitHub at most once a day (`refresh_if_due`), falling back to
the copy it shipped with. `rank()` orders them for you: your field, the skills rising for you, easy ones first.
The phone does the same (lib/datasets.ts; tests/test_datasets.py checks both agree).
"""

from __future__ import annotations

import html
import json
import math
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from .config import DATA_DIR, ensure_dirs
from .files import read_json, write_json

BUNDLED = Path(__file__).parent / "data" / "datasets.json"
CORE = Path(__file__).parent / "data" / "datasets_core.json"
PHONE_COPY = Path(__file__).resolve().parents[2] / "mobile" / "src" / "data" / "datasets.json"
CACHE_FILE = DATA_DIR / "datasets.json"
REMOTE_URL = "https://raw.githubusercontent.com/mygeeky/myGeeKy/main/src/mygeeky/data/datasets.json"
CHECK_EVERY_HOURS = 24
UA = {"User-Agent": "mygeeky-datasets (https://mygeeky.org)"}

FIELDS = ["Biology & genomics", "Plants & agriculture", "Medicine & health", "Neuroscience", "Ecology & environment",
          "Earth & climate", "Chemistry & materials", "Physics & astronomy", "Social science & economics",
          "Machine learning & AI"]
LEVELS = ("beginner", "intermediate", "advanced")
MAX_TOTAL_MB = 5000          # rule 3: a laptop can hold it ...
MAX_STARTER_MB = 1000        # ... and one file is enough to begin
MIN_ABOUT = 120              # rule 5: says what it is
MIN_DOWNLOADS = 300          # rule 7, for harvested records that aren't curated by their source
OPEN_LICENCES = ("cc0", "cc-by", "cc-by-sa", "odbl", "odc-by", "pddl", "public domain", "mit", "bsd", "apache",
                 "cc-pddc", "etalab")
FORMATS = {"csv", "tsv", "txt", "json", "xlsx", "xls", "parquet", "h5", "h5ad", "hdf5", "loom", "mtx", "fasta", "fa",
           "fna", "faa", "fastq", "fastqsanger", "fq", "vcf", "bed", "gff", "gff3", "gtf", "pdb", "cif", "mmcif",
           "soft", "arff", "fits", "nc", "netcdf", "png", "jpg", "jpeg", "tif", "tiff", "bam", "sam", "rds", "rdata",
           "npz", "npy", "xpt", "nifti", "nii", "idx", "python pickle", "tabular", "counts", "zip", "tar", "biom",
           "mzml", "sdf", "smi", "mol2", "xml", "md", "newick", "nwk", "phy", "aln", "sra"}
GATED = re.compile(r"\b(dbgap|uk ?biobank|mimic|kaggle\.com|ega-archive|controlled access|data access committee|"
                   r"upon request|on request|registration required)\b", re.I)

# words that place a harvested record in a field (first match wins, in this order)
FIELD_WORDS: list[tuple[str, str]] = [
    ("Neuroscience", r"neuro|brain|fmri|eeg|neuron|cortex"),
    ("Plants & agriculture", r"plant|arabidopsis|rice|maize|wheat|crop|soybean|tomato|agricultur|barley|leaf|leaves"),
    ("Medicine & health", r"patient|clinical|cancer|tumou?r|disease|covid|sars|infection|health|diabet|cardio"),
    ("Ecology & environment", r"ecolog|biodiversity|species|microbiome|metagenom|soil|ocean|marine|environment"),
    ("Earth & climate", r"climate|weather|temperature|earthquake|hydrolog|atmospher|glacier"),
    ("Chemistry & materials", r"molecul|chemi|compound|crystal|material|spectr|catalys"),
    ("Physics & astronomy", r"astro|galax|star|black hole|gravitational|particle|physics|cosmolog|planet"),
    ("Social science & economics", r"social|econom|survey|census|election|income|education"),
    ("Machine learning & AI", r"machine learning|deep learning|benchmark|classification|neural network|image dataset"),
    ("Biology & genomics", r"genom|rna-seq|transcript|protein|gene|sequenc|cell|bacteri|yeast|mouse|zebrafish"),
]


# --------------------------------------------------------------------------- the rules
def licence_ok(licence: str) -> tuple[bool, bool]:
    """(open?, non-commercial?) for a licence name or id ("cc-by-4.0", "CC0-1.0", "Public domain"...)."""
    s = (licence or "").lower().replace("_", "-").replace(" ", "-").replace("-sa-", "-sa-")
    s = s.replace("public-domain", "public domain")
    if not s:
        return False, False
    nc = "-nc" in s
    if nc and s.startswith("cc-by"):
        return True, True
    return any(s.startswith(o) or o in s for o in OPEN_LICENCES) and "-nd" not in s, False


def _https(value: Any) -> str:
    url = str(value or "").strip()
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    return url[:600] if parts.scheme == "https" and parts.netloc and " " not in url else ""


def accept(r: dict[str, Any]) -> list[str]:
    """The rules a record breaks (empty = it may be shown). `r` is a record before cleaning: it may carry
    `about` (description), `starter_mb`, `curated` (validated by its source) and `gated`."""
    broken = []
    if not licence_ok(str(r.get("license") or ""))[0]:
        broken.append("1 open licence")
    text = " ".join(str(r.get(k) or "") for k in ("title", "about", "url", "download"))
    if r.get("gated") or GATED.search(text):
        broken.append("2 one click, no gate")
    if not (_https(r.get("download")) or _https(r.get("url"))):
        broken.append("2 a download or landing page")
    size, starter = r.get("size_mb"), r.get("starter_mb", r.get("size_mb"))
    if not isinstance(size, (int, float)) or size <= 0 or (size > MAX_TOTAL_MB and not r.get("starter")) \
            or (isinstance(starter, (int, float)) and starter > MAX_STARTER_MB):
        broken.append("3 laptop-sized")
    formats = [str(f).lower() for f in r.get("formats") or []]
    if not formats or not any(f in FORMATS for f in formats):
        broken.append("4 common formats")
    if len(str(r.get("about") or "")) < MIN_ABOUT and not r.get("core"):
        broken.append("5 documented")
    if not (r.get("doi") or r.get("core") or r.get("curated") or _https(r.get("url"))):
        broken.append("6 stable and citable")
    if not (r.get("core") or r.get("curated") or int(r.get("uses") or 0) >= MIN_DOWNLOADS):
        broken.append("7 validated or used")
    if re.search(r"\b(identifiable|personal data|names and addresses)\b", text, re.I):
        broken.append("8 no personal data")
    if not str(r.get("why") or "").strip() or r.get("level") not in LEVELS:
        broken.append("9 says what to practise")
    if r.get("field") not in FIELDS:
        broken.append("10 one field")
    return broken


def field_of(text: str, default: str = "Biology & genomics") -> str:
    for field, words in FIELD_WORDS:
        if re.search(words, text, re.I):
            return field
    return default


def _plain(raw: Any, n: int) -> str:
    """Text from the internet as plain text: tags out, entities decoded, spaces squeezed."""
    s = html.unescape(re.sub(r"<[^>]+>", " ", str(raw or "")))
    return " ".join(s.split())[:n]


def _formats(names: Iterable[str]) -> list[str]:
    out = []
    for n in names:
        parts = n.lower().split(".")
        while parts and parts[-1] in ("gz", "bz2", "xz", "zip", "tgz", "tar") and len(parts) > 2:
            parts.pop()
        ext = parts[-1] if len(parts) > 1 else ""
        if ext and ext not in out:
            out.append(ext)
    return out[:6] or ["zip"]


def _skills_of(text: str, named: Iterable[str] = ()) -> list[str]:
    from . import skills
    known = {s["name"] for s in skills.vocabulary()}
    out = [s for s in named if s in known]
    text = re.sub(r"\(?https?://\S+|\b[\w.-]+\.(?:org|com|net|us|io|edu|gov)\b\S*", " ", text)   # not the links
    for s in sorted(skills.skills_in(text)):
        if s not in out:
            out.append(s)
    return out[:6]


# --------------------------------------------------------------------------- harvesting (the weekly Action)
def galaxy_why(title: str) -> str:
    """"the data for a Galaxy tutorial on From peaks to genes", from a Galaxy Training Network record's title."""
    name = re.sub(r"\([^)]*\)|\b(?:galaxy\s+)?training\s+(?:network|material|materials|data|dataset|date)\b|"
                  r"\bfor\s+galaxy\s+training\s+network\s+tutorials?\s+on\b|\btutorials?\b|\bgalaxy\b|"
                  r"^\s*(?:for|of)\b", " ", title, flags=re.I)
    name = re.sub(r"^\W*(?:for|of)\W+", "", " ".join(name.split())).strip(" -:'\"").strip()
    return f"the data for a Galaxy tutorial on {name}" if len(name) > 3 else "the data for a Galaxy tutorial"


def _zenodo_record(h: dict[str, Any], galaxy: bool) -> dict[str, Any]:
    m = h.get("metadata") or {}
    files = h.get("files") or []
    sizes = [f.get("size", 0) / 1e6 for f in files]
    title = _plain(m.get("title"), 160)
    about = _plain(m.get("description"), 2000)
    keywords = [_plain(k, 40) for k in (m.get("keywords") or [])[:8]]
    tutorial = next((_https(r.get("identifier")) for r in m.get("related_identifiers") or []
                     if "training.galaxyproject.org" in str(r.get("identifier", ""))), "")
    text = f"{title} {about} {' '.join(keywords)}"
    one = files[0]["links"].get("self", "") if len(files) == 1 else ""
    return {"id": f"zenodo-{h.get('id')}", "title": title, "about": about,
            "field": field_of(text), "level": "beginner" if galaxy else "intermediate",
            "why": (galaxy_why(title) if galaxy
                    else f"{', '.join(keywords[:3]) or title.split(':')[0]}: practise on {len(files)} file"
                         f"{'s' if len(files) != 1 else ''}"),
            "skills": _skills_of(text), "source": "Zenodo · Galaxy Training Network" if galaxy else "Zenodo",
            "url": _https((h.get("links") or {}).get("self_html")), "download": _https(one),
            "size_mb": round(sum(sizes), 1), "starter_mb": round(min(sizes), 1) if sizes else 0,
            "formats": _formats(f.get("key", "") for f in files), "license": (m.get("license") or {}).get("id", ""),
            "doi": str(h.get("doi") or ""), "tutorial": tutorial, "uses": int((h.get("stats") or {}).get("downloads") or 0),
            "curated": galaxy}


ZENODO_SEARCHES = {
    "Biology & genomics": ["single-cell training dataset", "RNA-seq tutorial dataset", "genomics benchmark dataset"],
    "Plants & agriculture": ["plant phenotyping dataset", "crop genomics dataset"],
    "Medicine & health": ["medical imaging benchmark dataset", "clinical machine learning dataset open"],
    "Neuroscience": ["EEG dataset open", "neuroscience benchmark dataset"],
    "Ecology & environment": ["species occurrence dataset", "biodiversity benchmark dataset", "ecology tutorial dataset",
                              "camera trap dataset"],
    "Earth & climate": ["climate dataset training", "remote sensing benchmark dataset", "weather benchmark dataset",
                        "hydrology dataset tutorial"],
    "Chemistry & materials": ["molecular property benchmark dataset", "materials science dataset machine learning"],
    "Physics & astronomy": ["astronomy machine learning dataset", "physics benchmark dataset"],
    "Social science & economics": ["survey dataset open", "economics dataset replication"],
    "Machine learning & AI": ["machine learning benchmark dataset", "image classification dataset"],
}


ZENODO_PAGE = 25            # the most Zenodo gives a guest per page


def _english(rec: dict[str, Any]) -> bool:
    from .curated import english_enough
    return english_enough(rec["title"], rec["about"][:600])


def harvest_zenodo(session, galaxy_max: int = 150, per_search: int = ZENODO_PAGE) -> list[dict[str, Any]]:
    out = []
    base = "https://zenodo.org/api/records"
    for page in range(1, galaxy_max // ZENODO_PAGE + 1):
        r = session.get(base, headers=UA, timeout=60, params={"communities": "galaxy-training", "type": "dataset",
                                                              "sort": "mostviewed", "size": ZENODO_PAGE, "page": page})
        out += [rec for rec in (_zenodo_record(h, True) for h in (r.json().get("hits") or {}).get("hits") or [])
                if _english(rec)]
        time.sleep(2.5)
    for field, queries in ZENODO_SEARCHES.items():
        for q in queries:
            r = session.get(base, headers=UA, timeout=60, params={"q": q, "type": "dataset", "sort": "mostviewed",
                                                                  "size": per_search})
            for h in (r.json().get("hits") or {}).get("hits") or []:
                rec = _zenodo_record(h, False)
                if field_of(f"{rec['title']} {rec['about']}", "") in (field, "") and _english(rec):   # on topic
                    rec["field"] = field
                    out.append(rec)
            time.sleep(2.5)
    return out


GEO_SEARCHES = [("Medicine & health", "Homo sapiens[ORGN] AND (cancer OR disease)"),
                ("Biology & genomics", "Mus musculus[ORGN]"), ("Biology & genomics", "Saccharomyces cerevisiae[ORGN]"),
                ("Biology & genomics", "Escherichia coli[ORGN]"), ("Plants & agriculture", "Arabidopsis thaliana[ORGN]"),
                ("Plants & agriculture", "Oryza sativa[ORGN]"), ("Neuroscience", "brain"),
                ("Biology & genomics", "Drosophila melanogaster[ORGN]")]


def harvest_geo(session, per_search: int = 12) -> list[dict[str, Any]]:
    eu = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    out = []
    for field, q in GEO_SEARCHES:
        ids = session.get(f"{eu}/esearch.fcgi", headers=UA, timeout=60, params={
            "db": "gds", "term": f"GDS[ETYP] AND {q}", "retmax": per_search, "retmode": "json"}).json()
        ids = (ids.get("esearchresult") or {}).get("idlist") or []
        time.sleep(0.5)
        if not ids:
            continue
        res = session.get(f"{eu}/esummary.fcgi", headers=UA, timeout=60,
                          params={"db": "gds", "id": ",".join(ids), "retmode": "json"}).json().get("result") or {}
        time.sleep(0.5)
        for i in ids:
            s = res.get(i) or {}
            acc = str(s.get("accession") or "")
            if not re.fullmatch(r"GDS\d+", acc):
                continue
            ftp = str(s.get("ftplink") or "").replace("ftp://", "https://")
            soft = f"{ftp.rstrip('/')}/soft/{acc}.soft.gz" if ftp else ""
            size = 0.0
            try:
                head = session.head(soft, headers=UA, timeout=30, allow_redirects=True)
                size = round(int(head.headers.get("Content-Length") or 0) / 1e6, 1)
            except Exception:
                pass
            title, about = _plain(s.get("title"), 160), _plain(s.get("summary"), 2000)
            n, taxon = s.get("n_samples") or "?", _plain(s.get("taxon"), 60)
            out.append({"id": f"geo-{acc.lower()}", "title": f"{title} ({acc})", "about": about, "field": field,
                        "level": "intermediate",
                        "why": f"differential expression on {n} {taxon} samples, curated by NCBI",
                        "skills": _skills_of(f"{title} {about}", ["Bioconductor", "R"]), "source": "GEO DataSets (NCBI)",
                        "url": f"https://www.ncbi.nlm.nih.gov/sites/GDSbrowser?acc={acc}", "download": _https(soft),
                        "size_mb": size, "formats": ["soft"], "license": "Public domain", "doi": "", "tutorial": "",
                        "uses": 0, "curated": True})
    return out


def harvest_openml(session) -> list[dict[str, Any]]:
    api = "https://www.openml.org/api/v1/json"
    listed = session.get(f"{api}/data/list/tag/OpenML-CC18/limit/100", headers=UA, timeout=60).json()
    out = []
    for d in ((listed.get("data") or {}).get("dataset") or []):
        q = {x["name"]: x["value"] for x in d.get("quality") or []}
        try:
            desc = session.get(f"{api}/data/{d['did']}", headers=UA, timeout=60).json()["data_set_description"]
        except Exception:
            continue
        time.sleep(0.3)
        rows, cols = int(float(q.get("NumberOfInstances") or 0)), int(float(q.get("NumberOfFeatures") or 0))
        name = _plain(d.get("name"), 80)
        about = _plain(desc.get("description"), 2000)
        out.append({"id": f"openml-{d['did']}", "title": f"{name} (OpenML {d['did']})", "about": about,
                    "field": field_of(f"{name} {about}", "Machine learning & AI"), "level": "beginner" if rows < 20000 else "intermediate",
                    "why": f"classification on {rows:,} rows and {cols} features (a vetted OpenML-CC18 task)",
                    "skills": _skills_of(f"{name} {about}", ["Machine learning"]), "source": "OpenML",
                    "url": f"https://www.openml.org/d/{d['did']}", "download": _https(desc.get("url")),
                    "size_mb": max(0.01, round(rows * max(cols, 1) * 8 / 1e6, 2)), "formats": ["arff"],
                    "license": "Public domain" if str(desc.get("licence") or "").strip().lower() == "public"
                    else str(desc.get("licence") or ""), "doi": "", "tutorial": "", "uses": 0, "curated": True})
    return out


def _url_alive(session, url: str) -> bool:
    try:
        r = session.head(url, headers=UA, timeout=30, allow_redirects=True)
        if r.status_code in (403, 405, 501):            # some servers refuse HEAD: ask for the first byte
            r = session.get(url, headers={**UA, "Range": "bytes=0-0"}, timeout=30, stream=True)
        return r.status_code < 400
    except Exception:
        return False


def build(today: date | None = None, session=None, harvest: bool = True) -> dict[str, Any]:
    import requests
    session = session or requests.Session()
    today = today or date.today()
    core = []
    for r in (read_json(CORE, {}) or {}).get("datasets") or []:
        r = {**r, "core": True}
        link = r.get("download") or r.get("url")
        if link and not _url_alive(session, link):
            print(f"datasets: core link down, kept out: {r['id']} ({link})", file=sys.stderr)
            continue
        core.append(r)
    found = []
    if harvest:
        for name, fn in (("Zenodo", harvest_zenodo), ("GEO", harvest_geo), ("OpenML", harvest_openml)):
            try:
                got = fn(session)
                print(f"datasets: {name}: {len(got)} looked at", file=sys.stderr)
                found += got
            except Exception as exc:
                print(f"datasets: {name} skipped ({exc})", file=sys.stderr)
    rows, seen, refused = [], set(), {}
    for r in core + found:
        key = re.sub(r"[^a-z0-9]", "", r["title"].lower())[:50]
        if r["id"] in seen or key in seen:
            continue
        broken = accept(r)
        if broken:
            for b in broken:
                refused[b] = refused.get(b, 0) + 1
            continue
        seen |= {r["id"], key}
        rows.append(clean_item({**r, "checked": today.isoformat()}))
    print(f"datasets: {len(rows)} accepted; refused for {refused}", file=sys.stderr)
    return {"version": today.isoformat(), "datasets": [r for r in rows if r]}


def save(data: dict[str, Any], path: Path = BUNDLED) -> Path:
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    if path == BUNDLED and PHONE_COPY.parent.is_dir():
        PHONE_COPY.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- reading it (untrusted: from the internet)
def _text(value: Any, n: int) -> str:
    return " ".join(str(value or "").split())[:n].rstrip() if isinstance(value, (str, int, float)) else ""


def clean_item(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    title, url = _text(raw.get("title"), 160), _https(raw.get("url"))
    download = _https(raw.get("download"))
    if not title or not (url or download) or raw.get("field") not in FIELDS or raw.get("level") not in LEVELS:
        return None
    size = raw.get("size_mb")
    open_, nc = licence_ok(_text(raw.get("license"), 40))
    if not open_:
        return None
    return {"id": _text(raw.get("id"), 80) or title.lower(), "title": title, "field": raw["field"],
            "why": _text(raw.get("why"), 200), "about": _text(raw.get("about"), 300), "level": raw["level"],
            "skills": [_text(s, 60) for s in (raw.get("skills") or [])[:6] if _text(s, 60)]
            if isinstance(raw.get("skills"), list) else [],
            "source": _text(raw.get("source"), 60), "url": url or download, "download": download,
            "size_mb": float(size) if isinstance(size, (int, float)) and not isinstance(size, bool) and 0 <= size < 1e6 else 0.0,
            "formats": [_text(f, 16) for f in (raw.get("formats") or [])[:6]] if isinstance(raw.get("formats"), list) else [],
            "license": _text(raw.get("license"), 40), "nc": nc, "doi": _text(raw.get("doi"), 80),
            "tutorial": _https(raw.get("tutorial")),
            "uses": int(raw["uses"]) if isinstance(raw.get("uses"), int) and not isinstance(raw.get("uses"), bool) and raw["uses"] >= 0 else 0,
            "core": raw.get("core") is True, "checked": _text(raw.get("checked"), 10)}


def clean(data: Any) -> dict[str, Any]:
    data = data if isinstance(data, dict) else {}
    rows = [c for c in (clean_item(r) for r in (data.get("datasets") or [])[:3000]
                        if isinstance(data.get("datasets"), list)) if c]
    version = _text(data.get("version"), 10)
    return {"version": version if len(version) == 10 and version[4] == "-" else "", "datasets": rows}


_loaded: dict[str, Any] | None = None


def load(force: bool = False) -> dict[str, Any]:
    global _loaded
    if _loaded is not None and not force:
        return _loaded
    shipped = clean(read_json(BUNDLED, {}))
    fetched = clean((read_json(CACHE_FILE, {}) or {}).get("data"))
    _loaded = fetched if fetched["datasets"] and fetched["version"] >= shipped["version"] else shipped
    return _loaded


def refresh_if_due(force: bool = False, now: datetime | None = None, timeout: float = 20.0) -> bool:
    """Fetch the newest list from GitHub, at most once a day. True if a newer one arrived."""
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
    if getattr(r, "status_code", 200) != 200 or len(r.content) > 5_000_000:
        write_json(CACHE_FILE, {**(cached if isinstance(cached, dict) else {}), "checked_at": now.isoformat(timespec="seconds")})
        return False
    data = clean(r.json())
    old = clean(cached.get("data")) if isinstance(cached, dict) else clean({})
    write_json(CACHE_FILE, {"checked_at": now.isoformat(timespec="seconds"), "data": data})
    _loaded = None
    return data["version"] > old["version"]


# --------------------------------------------------------------------------- for you
LEVEL_BONUS = {"beginner": 0.4, "intermediate": 0.2, "advanced": 0.0}


def text_of(d: dict[str, Any]) -> str:
    return f"{d['title']} ; {d['why']} ; {d['about']} ; {' '.join(d['skills'])} ; {d['field']}"


def rank(items: list[dict[str, Any]], weights: dict[str, float], wanted: Iterable[str] = (), field: str = "",
         votes: dict[str, int] | None = None, top: int = 40) -> dict[str, Any]:
    """{"items": [...best first, each with score and `for` (the skills you want it teaches)], "hidden": n}.
    `field`: "" for all, "for you" for what matches you, or one of FIELDS. `votes`: {id: +1/-1}."""
    from .interests import match
    want = {w.lower() for w in wanted}
    votes = votes or {}
    out, hidden = [], 0
    for d in items:
        v = votes.get(d["id"], 0)
        if v < 0:
            hidden += 1
            continue
        fit = match(text_of(d), weights)[0] if weights else 0.0
        hit = [s for s in d["skills"] if s.lower() in want]
        if field == "for you" and not (fit or hit):
            continue
        if field and field != "for you" and d["field"] != field:
            continue
        score = 1 + 2 * fit + (1.5 if hit else 0) + LEVEL_BONUS[d["level"]] + (0.3 if d["core"] else 0) \
            + 0.1 * math.log10(1 + d["uses"])
        score *= 1.3 if v > 0 else 1.0
        out.append({**d, "score": math.floor(score * 10000 + 0.5) / 10000, "for": hit, "vote": v})   # as JavaScript rounds
    out.sort(key=lambda d: (-d["score"], d["title"]))
    return {"items": out[:top], "hidden": hidden}


def size_text(mb: float) -> str:
    """"7 MB", "1.2 GB", "under 1 MB" -- the same words on the phone."""
    if mb <= 0:
        return ""
    if mb < 1:
        return "under 1 MB"
    if mb >= 1000:
        return f"{math.floor(mb / 100 + 0.5) / 10:g} GB"
    return f"{math.floor(mb + 0.5)} MB"


if __name__ == "__main__":
    cmd = sys.argv[1:] or ["help"]
    if cmd == ["build"]:
        data = build()
        save(data)
        print(f"datasets: {len(data['datasets'])} written")
    elif cmd == ["check"]:
        for r in (read_json(CORE, {}) or {}).get("datasets") or []:
            print(r["id"], accept({**r, "core": True}) or "ok")
    else:
        print("usage: python -m mygeeky.datasets build | check")
