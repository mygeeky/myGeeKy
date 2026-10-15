"""Check the hand-written reviewed protocols, then put them in the shipped curated lists (maker side).

    python tools/protocols/merge.py --check     # only check: every link opens, every protocol is valid
    python tools/protocols/merge.py             # check, then write src/mygeeky/data/curated.json

"Reviewed" means the maker read it, so nothing here is automatic: the script's
job is to catch a link that has died or a protocol that wouldn't survive
`protocols.clean_protocol`, and to keep the file tidy.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from mygeeky import curated, protocols, safety, skills  # noqa: E402

SRC = Path(__file__).with_name("reviewed.json")
CURATED = ROOT / "src" / "mygeeky" / "data" / "curated.json"
MOBILE = ROOT / "mobile" / "src" / "data" / "curated.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"}


# A supplier or publisher that blocks robots (403, 429, 503) or times us out isn't a dead link: the page
# opens fine in a browser. Only "gone" (404, 410) or a name that doesn't resolve means the link is dead.
SHY = (401, 403, 405, 406, 429, 503)


def alive(url: str) -> tuple[str, int, str]:
    """(url, status, note). A status of -1 means the site wouldn't talk to us -- the link is kept."""
    with requests.Session() as s:
        for method in ("head", "get"):
            try:
                r = getattr(s, method)(url, timeout=30, headers=UA, allow_redirects=True)
            except requests.Timeout:
                if method == "get":
                    return url, -1, "timed out (kept: it's slow, not gone)"
                continue
            except requests.RequestException as exc:
                if method == "get":
                    return url, 0, type(exc).__name__
                continue
            if r.status_code < 400:
                return url, r.status_code, ""
            if method == "get":
                return (url, -1, f"{r.status_code}: won't talk to robots (kept)") if r.status_code in SHY                     else (url, r.status_code, "")
    return url, 0, "no answer"


def main() -> int:
    check_only = "--check" in sys.argv
    data = json.loads(SRC.read_text(encoding="utf-8"))
    protos = data["protocols"]
    links = sorted({it["url"] for p in protos for st in p["stages"] for it in st["items"]})
    print(f"{len(protos)} protocols, {len(links)} links to check")
    bad: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for url, status, note in pool.map(alive, links):
            if status == -1:
                print(f"  ~ {note}  {url}")
            elif status == 0 or status >= 400:
                bad[url] = note or str(status)
                print(f"  ! {status or note}  {url}")
    problems = []
    cleaned = []
    for raw in protos:
        s = skills.find(raw["skill"])
        ok, why = safety.allowed(raw["skill"], raw.get("goal", ""), lab=bool(s and s.get("kind") == "lab"))
        if not ok:
            problems.append(f"{raw['id']}: {why}")
            continue
        if not s:
            problems.append(f"{raw['id']}: '{raw['skill']}' isn't in the skills dictionary (skills.json)")
        p = protocols.clean_protocol(raw, reviewed=True)
        if not p:
            problems.append(f"{raw['id']}: wouldn't survive clean_protocol")
            continue
        if p["id"] != raw["id"]:
            problems.append(f"{raw['id']}: id changed to {p['id']} (must be 3-80 lowercase letters/digits/dashes)")
        for st in p["stages"]:
            kept = [it for it in st["items"] if it["url"] not in bad]
            if len(kept) != len(st["items"]):
                print(f"  dropped {len(st['items']) - len(kept)} dead link(s) from {p['id']}/{st['id']}")
            st["items"] = kept
        empty = [st["id"] for st in p["stages"] if not st["items"] and st["role"] != "use"]
        if empty:
            problems.append(f"{p['id']}: no links left in {', '.join(empty)}")
        cleaned.append(p)
    for line in problems:
        print(f"  ! {line}")
    print(f"{len(cleaned)} protocols ready, {len(bad)} dead links, {len(problems)} problems")
    if check_only:
        return 1 if problems or bad else 0
    if problems:
        print("Not writing: fix the problems above first.")
        return 1
    file = json.loads(CURATED.read_text(encoding="utf-8"))
    fresh = {c["id"] for c in cleaned}
    keep = []
    for raw in file.get("protocols") or []:
        if raw["id"] in fresh:
            continue
        stale = [it for st in raw.get("stages") or [] for it in st.get("items") or []
                 if safety.blocked_source(it.get("url", "")) or safety.is_bench(f"{it.get('title', '')} "
                                                                                f"{it.get('note', '')}")]
        if protocols.clean_protocol(raw, reviewed=True) is None or stale:
            print(f"  removing '{raw['id']}': myGeeKy no longer teaches it (safety.py)")
            continue                         # a bench protocol, or one leaning on bench sources: it goes
        keep.append(raw)
    file["protocols"] = keep + [{k: v for k, v in p.items() if k not in ("reviewed", "source")} for p in cleaned]
    file["version"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    issues = curated.problems(file)
    if issues:
        for i in issues[:5]:
            print(f"  ! {i}")
        return 1
    text = json.dumps(file, indent=1, ensure_ascii=False) + "\n"
    CURATED.write_text(text, encoding="utf-8")
    if MOBILE.exists():
        MOBILE.write_text(text, encoding="utf-8")
    print(f"wrote {len(file['protocols'])} protocols -> {CURATED.relative_to(ROOT)}"
          + (f" and {MOBILE.relative_to(ROOT)}" if MOBILE.exists() else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
