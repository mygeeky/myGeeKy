"""Assemble the mygeeky.org site into _site/ (what GitHub Pages publishes).

    python website/build.py        ->  _site/index.html + _site/img/*

Images are copied from where they already live (docs/screenshots, the app's
icons, the Product Hunt hero slide), so the repo holds one copy of each.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"

IMAGES = {
    "hero.png": ROOT / "docs/screenshots/hero.png",
    "suggestions.png": ROOT / "docs/screenshots/suggestions.png",
    "market.png": ROOT / "docs/screenshots/market.png",
    "signals.png": ROOT / "docs/screenshots/signals.png",
    "live.png": ROOT / "docs/screenshots/live.png",
    "activity.png": ROOT / "docs/screenshots/activity.png",
    "repos.png": ROOT / "docs/screenshots/repos.png",
    "model.png": ROOT / "docs/screenshots/model.png",
    "research.png": ROOT / "docs/screenshots/research.png",
    "news.png": ROOT / "docs/screenshots/news.png",
    "games.png": ROOT / "docs/screenshots/games.png",
    "games-run.png": ROOT / "docs/screenshots/games-run.png",
    "phone.png": ROOT / "docs/screenshots/phone/hero-phone-grow.png",
    "phone-home.png": ROOT / "google-play/screenshots/1-home.png",
    "phone-protocols.png": ROOT / "google-play/screenshots/2-protocols.png",
    "phone-quiz.png": ROOT / "google-play/screenshots/3-quiz.png",
    "phone-jobs.png": ROOT / "google-play/screenshots/4-jobs.png",
    "phone-skills.png": ROOT / "google-play/screenshots/5-skills.png",
    "phone-papers.png": ROOT / "google-play/screenshots/6-papers.png",
    "phone-month.png": ROOT / "google-play/screenshots/7-month.png",
    "grow-skills.png": ROOT / "docs/screenshots/grow-skills.png",
    "grow-protocols.png": ROOT / "docs/screenshots/grow-protocols.png",
    "grow-quiz.png": ROOT / "docs/screenshots/grow-quiz.png",
    "chances-jobs.png": ROOT / "docs/screenshots/chances-jobs.png",
    "chances-seasons.png": ROOT / "docs/screenshots/chances-seasons.png",
    "quiz-question.png": ROOT / "docs/screenshots/quiz-question.png",
    "quiz-score.png": ROOT / "docs/screenshots/quiz-score.png",
    "video-thumbnail.png": ROOT / "docs/video-thumbnail.png",
    "icon_64.png": ROOT / "src/mygeeky/gui/assets/icon_64.png",
    "icon_256.png": ROOT / "src/mygeeky/gui/assets/icon_256.png",
    "character.jpg": ROOT / "docs/character.jpg",
    "og.png": ROOT / "launch/producthunt/gallery-1-hero.png",   # link-preview image
}


def version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'^version = "([^"]+)"', text, re.M).group(1)


def scientists() -> list[dict]:
    """website/scientists.json, checked: only the fields the page shows, plain text, an https link, at most six fields.
    A wrong entry stops the build (the maker fixes it) rather than reaching the page."""
    import json
    items = json.loads((ROOT / "website/scientists.json").read_text(encoding="utf-8")).get("scientists", [])
    out = []
    for i, p in enumerate(items):
        def text(key: str, most: int, need: bool = False) -> str:
            v = p.get(key, "")
            if not isinstance(v, str) or len(v) > most or (need and not v.strip()):
                raise SystemExit(f"website/scientists.json, entry {i + 1}: '{key}' must be text, at most {most} characters")
            return v.strip()
        link = text("link", 200)
        if link and not link.startswith("https://"):
            raise SystemExit(f"website/scientists.json, entry {i + 1}: the link must start with https://")
        fields = p.get("fields", [])
        if not isinstance(fields, list) or not 1 <= len(fields) <= 6 or not all(isinstance(f, str) and 0 < len(f) <= 30 for f in fields):
            raise SystemExit(f"website/scientists.json, entry {i + 1}: 1 to 6 fields, each at most 30 characters")
        out.append({"name": text("name", 80, True), "role": text("role", 80), "place": text("place", 80), "link": link,
                    "fields": [f.strip() for f in fields], "since": text("since", 7)})
    return out


def fields_covered() -> list[str]:
    """What the word map shows until scientists join: the broad fields myGeeKy covers and its most used field words
    (the app's own dictionary, data/keywords.json)."""
    import json
    sys.path.insert(0, str(ROOT / "src"))
    from mygeeky import datasets
    broad = [label for key, label, _icon, _about in datasets.FIELD_PARTS if key not in ("for-you", "new")]
    terms = json.loads((ROOT / "src/mygeeky/data/keywords.json").read_text(encoding="utf-8"))["terms"]
    labels = sorted({t["label"] for t in terms.values() if 2 < len(t["label"]) <= 18 and not any(c.isdigit() for c in t["label"])},
                    key=lambda w: (-len(terms.get(w.replace(" ", "-"), {}).get("related", [])), w))
    words: list[str] = []
    for _field, pattern in datasets.FIELD_WORDS:          # about three of the dictionary's words for each field
        words += [w for w in labels if re.search(pattern, w, re.I) and w not in words][:3]
    return broad + [w for w in words if w.lower() not in {b.lower() for b in broad}]


def map_data() -> str:
    import json
    text = json.dumps({"scientists": scientists(), "fields": fields_covered()}, ensure_ascii=False)
    return text.replace("</", "<\\/")        # never closes the <script> it sits in


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "img").mkdir(parents=True)
    html = (ROOT / "website/index.html").read_text(encoding="utf-8").replace("{{VERSION}}", version())
    html = html.replace("{{MAP_DATA}}", map_data())
    (OUT / "index.html").write_text(html, encoding="utf-8")
    for page in ("privacy.html", "terms.html", "delete.html", "orcid/index.html"):   # other pages (delete: Play's deletion URL)
        (OUT / page).parent.mkdir(parents=True, exist_ok=True)
        (OUT / page).write_text((ROOT / "website" / page).read_text(encoding="utf-8").replace("{{VERSION}}", version()),
                                encoding="utf-8")
    for name, src in IMAGES.items():
        shutil.copyfile(src, OUT / "img" / name)
    shutil.copytree(ROOT / "website/fonts", OUT / "fonts")      # self-hosted fonts (no request to Google)
    (OUT / "geekoc").mkdir()                                    # GeekOc, alive in the hero: the rig and its canvas drawer
    for js in ("geekoc.js", "geekoc-canvas.js"):
        shutil.copyfile(ROOT / "website/geekoc" / js, OUT / "geekoc" / js)
    shutil.copyfile(ROOT / "website/install.sh", OUT / "install.sh")   # curl -fsSL https://mygeeky.org/install.sh | sh
    cname = ROOT / "website/CNAME"
    if cname.exists():
        shutil.copyfile(cname, OUT / "CNAME")
    print(f"Built {OUT} (v{version()}, {len(IMAGES)} images)")


if __name__ == "__main__":
    main()
