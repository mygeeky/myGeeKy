"""Assemble the mygeeky.org site into _site/ (what GitHub Pages publishes).

    python website/build.py        ->  _site/index.html + _site/img/*

Images are copied from where they already live (docs/screenshots, the app's
icons, the Product Hunt hero slide), so the repo holds one copy of each.
"""

from __future__ import annotations

import re
import shutil
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
    "phone.png": ROOT / "docs/screenshots/phone/hero-phone-grow.png",
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


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "img").mkdir(parents=True)
    html = (ROOT / "website/index.html").read_text(encoding="utf-8").replace("{{VERSION}}", version())
    (OUT / "index.html").write_text(html, encoding="utf-8")
    for page in ("privacy.html", "orcid/index.html"):   # other pages: the privacy policy, the ORCID sign-in relay
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
