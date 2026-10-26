"""The phone's seasons and country filter must answer exactly what the desktop does.

mobile/src/lib/seasons.ts is a port of seasons.py, and mobile/src/lib/countries.ts of the country half of
curated.py. A port is a second implementation of the same rules, which is a second thing to drift: a
season shown on the laptop and missing on the phone, or a window named one way here and another there,
would be nobody's bug and everybody's problem.

So this runs the phone's REAL TypeScript in Node, against the real lists, on a fixed day, and holds its
answers against this Python. Skipped where Node isn't installed (it is on a developer's machine, and in
the phone workflow).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from mygeeky import curated, seasons

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
WORK = MOBILE / ".crosscheck"
LISTS = ROOT / "src" / "mygeeky" / "data" / "curated.json"
DAY = date(2026, 10, 15)          # fixed, or the two sides would disagree whenever one ran past midnight


def _ready() -> bool:
    if not shutil.which("node") or not (MOBILE / "src" / "lib" / "seasons.ts").exists():
        return False
    v = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=120).stdout.strip().lstrip("v").split(".")
    return len(v) > 1 and v[0].isdigit() and v[1].isdigit() and (int(v[0]), int(v[1])) >= (22, 6)   # runs TypeScript


pytestmark = pytest.mark.skipif(not _ready(), reason="needs Node 23+")

SCRIPT = """
import { countriesIn, countryOf } from '../src/lib/countries.ts';
import * as seasons from '../src/lib/seasons.ts';
import { readFileSync } from 'node:fs';

const TODAY = process.argv[2];
const data = JSON.parse(readFileSync(process.argv[3], 'utf-8'));
const ss = seasons.clean(data.seasons);
const wins = seasons.windows(ss, TODAY);
const jobs = (data.jobs ?? []).map((j) => ({ country: countryOf(j.place) }));
const conferences = (data.conferences ?? []).map((c) => ({ country: countryOf(c.place) }));
console.log(JSON.stringify({
  cleaned: ss.map((s) => s.id),
  evidenced: ss.filter(seasons.evidenced).map((s) => s.id),
  windows: wins.map((w) => ({ label: w.label, from: w.from, to: w.to, now: w.now, past: w.past,
                              seasons: w.seasons.map((s) => s.id) })),
  offered: seasons.around(wins, TODAY).map((w) => w.label),
  current: seasons.current(seasons.around(wins, TODAY), TODAY),
  notice: seasons.ranked(ss, TODAY).map((s) => [s.id, seasons.noticeText(s.when)]),
  states: ss.map((s) => [s.id, seasons.when(s, TODAY).state, seasons.when(s, TODAY).confirmed]),
  countries: countriesIn([...jobs, ...conferences]),
  places: ['Lyon, France', 'Cambridge, Cambridgeshire, UK', 'Dortmund, Nordrhein-Westfalen (DE)',
           'Norman, Oklahoma', 'Remote', 'Lyon', ''].map((p) => [p, countryOf(p)]),
}));
"""


@pytest.fixture(scope="module")
def phone() -> dict:
    WORK.mkdir(exist_ok=True)
    runner = WORK / "seasons-side.ts"
    runner.write_text(SCRIPT, encoding="utf-8")
    out = subprocess.run(["node", "--experimental-strip-types", str(runner), DAY.isoformat(), str(LISTS)],
                         capture_output=True, text=True, cwd=str(MOBILE), timeout=120)
    if out.returncode != 0:
        pytest.fail(f"the phone's seasons.ts would not run:\n{out.stderr[-2000:]}")
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def here() -> dict:
    data = json.loads(LISTS.read_text(encoding="utf-8"))
    cleaned = seasons.clean(data.get("seasons"))
    wins = seasons.windows(cleaned, DAY)
    items = []
    for kind in ("jobs", "conferences"):
        for raw in data.get(kind) or []:
            it = curated.clean_item(kind, raw)
            if it:
                items.append(it)
    return {"cleaned": cleaned, "windows": wins, "items": items}


# --------------------------------------------------------------------------- the same seasons
def test_the_same_seasons_survive_cleaning(phone, here):
    assert phone["cleaned"] == [s["id"] for s in here["cleaned"]]


def test_the_same_ones_count_as_evidenced(phone, here):
    """What is shown to people at all: a season nobody has read on a page waits in the admin tab."""
    assert phone["evidenced"] == [s["id"] for s in here["cleaned"] if seasons.evidenced(s)]


def test_the_same_windows_with_the_same_names(phone, here):
    mine = [{"label": w["label"], "from": w["from"], "to": w["to"], "now": w["now"], "past": w["past"],
             "seasons": [s["id"] for s in w["seasons"]]} for w in here["windows"]]
    assert phone["windows"] == mine


def test_the_picker_offers_the_same_periods_and_starts_on_the_same_one(phone, here):
    offered = seasons.around(here["windows"], DAY)
    assert phone["offered"] == [w["label"] for w in offered]
    assert phone["current"] == seasons.current(offered, DAY)


def test_every_season_is_in_the_same_state(phone, here):
    mine = [[s["id"], seasons.when(s, DAY)["state"], seasons.when(s, DAY)["confirmed"]]
            for s in here["cleaned"]]
    assert phone["states"] == mine


def test_the_same_words_about_when_it_opens(phone, here):
    """The sentence a person reads. "expected in about 12 weeks" on one and "3 months" on the other
    would be the same truth told two ways, which is still a bug."""
    mine = [[s["id"], seasons.notice_text(s["when"])] for s in seasons.ranked(here["cleaned"], DAY)]
    assert phone["notice"] == mine


# --------------------------------------------------------------------------- the same countries
def test_the_country_filter_offers_the_same_countries(phone, here):
    assert phone["countries"] == curated.countries_in(here["items"])


def test_a_place_is_read_the_same_way(phone):
    """Every shape a board writes a place in, including the ones that name no country at all."""
    assert phone["places"] == [
        ["Lyon, France", "France"],
        ["Cambridge, Cambridgeshire, UK", "United Kingdom"],
        ["Dortmund, Nordrhein-Westfalen (DE)", "Germany"],
        ["Norman, Oklahoma", "United States"],
        ["Remote", ""],
        ["Lyon", ""],                      # a city alone invents nothing
        ["", ""],
    ]


def test_the_phone_ships_the_same_lists_as_the_desktop():
    """The workflow copies one file to the other; a port of the readers is no use against stale data."""
    phone_lists = json.loads((MOBILE / "src" / "data" / "curated.json").read_text(encoding="utf-8"))
    here_lists = json.loads(LISTS.read_text(encoding="utf-8"))
    assert phone_lists == here_lists
