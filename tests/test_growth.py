"""Rising Skills, Learning paths, learning resources, wins, verified jobs/funding/conferences,
collaborator match -- and the 👍/👎 that teach all of them."""

import json
from pathlib import Path
from datetime import date, datetime, timedelta, timezone

import pytest

import phone
from mygeeky import collab, curated, skills, taste, wins
from mygeeky.config import MyGeekyConfig

TODAY = date(2026, 10, 13)


def _lists(**kw):
    base = {"version": "2026-10-13T00:00:00Z", "jobs": [], "funding": [], "conferences": [], "resources": []}
    base.update(kw)
    return base


def _job(i, title="Postdoc in statistical genetics", deadline="2026-11-30", **kw):
    return {"id": i, "title": title, "org": "Some University", "place": "Oslo", "url": f"https://example.org/{i}",
            "deadline": deadline, "type": "postdoc", "keywords": ["gwas", "fine-mapping"], **kw}


# --------------------------------------------------------------------------- 👍 / 👎
def test_a_vote_teaches_its_terms_and_the_same_thumb_takes_it_back():
    assert taste.vote("job", "j1", True, "Postdoc in GWAS fine-mapping", ["gwas", "fine-mapping"]) == 1
    assert taste.vote_of("job", "j1") == 1
    w = taste.weights()
    assert w["gwas"] > 0 and w["fine-mapping"] > 0
    assert taste.vote("job", "j1", True) == 0           # pressed again: taken back
    assert taste.vote_of("job", "j1") == 0
    assert taste.vote("job", "j1", False, "wet lab", ["wet lab"]) == -1
    assert taste.weights()["wet lab"] < 0
    assert taste.lean("A wet lab position", [], taste.weights()) < 0
    assert taste.lean("", ["unrelated"], taste.weights()) == 0


def test_votes_fade_and_only_known_kinds_count():
    assert taste.vote("nonsense", "x", True) == 0
    taste.vote("skill", "Nextflow", True, "Nextflow", ["nextflow"])
    later = datetime.now(timezone.utc) + timedelta(days=taste.HALF_LIFE_DAYS)
    assert taste.weights(now=later)["nextflow"] == pytest.approx(taste.weights()["nextflow"] / 2, rel=0.01)
    assert taste.weights(["job"]) == {}                 # only votes on jobs


def test_show_them_again_clears_only_the_thumbs_down_of_that_kind():
    taste.vote("job", "a", False)
    taste.vote("job", "b", True)
    taste.vote("resource", "c", False)
    assert taste.clear("job", -1) == 1
    assert taste.vote_of("job", "a") == 0 and taste.vote_of("job", "b") == 1 and taste.vote_of("resource", "c") == -1


# --------------------------------------------------------------------------- the curated lists
def test_only_checked_items_survive_from_the_file():
    raw = _lists(jobs=[_job("ok-job"),
                       _job("http-job", url="http://example.org/x"),        # not https
                       _job("no-date", deadline="soon"),                    # a dated list needs a date
                       _job("Bad Id!"),
                       _job("ok-job")],                                     # the same id twice
                 resources=[{"id": "res", "title": "<b>Bold</b> course", "url": "https://x.org", "type": "nope",
                             "skills": ["Nextflow", 3], "level": "expert"}])
    c = curated.clean(raw)
    assert [j["id"] for j in c["jobs"]] == ["ok-job"]
    r = c["resources"][0]
    assert r["type"] == "website" and r["level"] == "" and r["skills"] == ["nextflow", "3"]
    assert r["title"] == "<b>Bold</b> course"            # kept as text; the cards show it as plain text
    msgs = curated.problems(raw)
    assert any("http-job" in m and "https" in m for m in msgs)
    assert any("no-date" in m and "deadline" in m for m in msgs)
    assert any("twice" in m for m in msgs)


def test_past_deadlines_disappear_but_the_deadline_day_still_counts():
    items = [{"id": "a", "deadline": "2026-10-12"}, {"id": "b", "deadline": "2026-10-13"}, {"id": "c"}]
    assert [i["id"] for i in curated.live(items, TODAY)] == ["b", "c"]
    pruned, removed = curated.prune(_lists(jobs=[_job("old", deadline="2026-10-01"), _job("new")]), TODAY)
    assert removed == 1 and [j["id"] for j in pruned["jobs"]] == ["new"]


def test_the_tidy_command_prunes_the_file_and_stamps_a_version(tmp_path):
    f = tmp_path / "curated.json"
    f.write_text(json.dumps(_lists(jobs=[_job("old", deadline="2020-01-01"), _job("new")])), encoding="utf-8")
    removed, errs = curated.tidy_file(f, TODAY)
    data = json.loads(f.read_text(encoding="utf-8"))
    assert removed == 1 and errs == [] and [j["id"] for j in data["jobs"]] == ["new"]
    assert data["version"] > "2026-10-13T00:00:00Z"
    assert curated.main(["check", str(f)]) == 0


def test_jobs_are_matched_to_you_and_thumbs_down_hides_one():
    cfg = MyGeekyConfig(keywords=["gwas"])
    data = curated.clean(_lists(jobs=[_job("fits"), _job("far", title="Wet-lab technician in plant pathology",
                                                         keywords=["plant pathology"])]))
    out = curated.ranked(cfg, "jobs", weights={"gwas": 1.0}, data=data, today=TODAY)
    assert [i["id"] for i in out["items"]] == ["fits", "far"]
    assert out["items"][0]["match"] == ["gwas"] and out["items"][0]["days_left"] == 48
    taste.vote("job", "fits", False, "Postdoc in statistical genetics", ["gwas"])
    out = curated.ranked(cfg, "jobs", weights={"gwas": 1.0}, data=data, today=TODAY)
    assert [i["id"] for i in out["items"]] == ["far"] and out["hidden"] == 1


def test_the_newest_lists_win_and_are_fetched_only_when_due(monkeypatch):
    class Resp:
        content = b"{}"

        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    calls = []
    newer = _lists(version="2099-01-01T00:00:00Z", jobs=[_job("fresh")])
    monkeypatch.setattr(curated.requests, "get", lambda *a, **k: calls.append(1) or Resp(newer))
    assert curated.refresh_if_due() is True
    assert [j["id"] for j in curated.load(force=True)["jobs"]] == ["fresh"]
    assert curated.refresh_if_due() is False and len(calls) == 1      # not due again for a few hours
    later = datetime.now(timezone.utc) + timedelta(hours=curated.CHECK_EVERY_HOURS + 1)
    curated.refresh_if_due(now=later)
    assert len(calls) == 2


def test_the_bundled_lists_are_valid_and_resources_teach_known_skills():
    raw = json.loads(curated.BUNDLED.read_text(encoding="utf-8"))
    assert curated.problems(raw) == []
    known = {s["name"].lower() for s in skills.vocabulary()}
    for r in curated.clean(raw)["resources"]:
        assert set(r["skills"]) <= known, r["id"]


def test_a_report_goes_to_the_maker_by_github_or_private_email():
    links = curated.report_links("jobs", {"id": "x-job", "title": "Too good to be true", "url": "https://e.org/x"})
    assert links["issue"].startswith("https://github.com/mygeeky/myGeeKy-ideas/issues/new?")
    assert "labels=report" in links["issue"] and "x-job" in links["issue"]
    assert links["email"].startswith("mailto:support@mygeeky.org?subject=")


def test_curated_links_open_and_others_still_dont(monkeypatch):
    pytest.importorskip("PySide6")
    from mygeeky.gui import app as logic
    opened = []
    import PySide6.QtGui as gui
    monkeypatch.setattr(gui.QDesktopServices, "openUrl", lambda u: opened.append(u.toString()))
    url = curated.load()["resources"][0]["url"]
    assert logic.open_link(url) is True
    assert logic.open_link("https://evil.example/x") is False
    assert logic.open_link("mailto:support@mygeeky.org?subject=x") is True
    assert logic.open_link("mailto:someone@else.org") is False
    assert len(opened) == 2


# --------------------------------------------------------------------------- Rising Skills
def _doc(text, source="repo", days_ago=3, url="https://github.com/a/b", title="a/b"):
    when = datetime(2026, 10, 13, tzinfo=timezone.utc) - timedelta(days=days_ago)
    return {"text": text, "when": when, "source": source, "url": url, "title": title}


def test_the_dictionary_finds_skills_by_their_names_and_leaves_tiny_words_out():
    assert {"Nextflow", "Single-cell RNA-seq", "Docker"} <= skills.skills_in("An nf-core pipeline for scRNA-seq in containers")
    assert "R" not in skills.skills_in("our r and go")                   # "r"/"go" alone are too short to trust
    assert "Fine-mapping" in skills.skills_in("fine mapping with SuSiE")
    assert all(len(a) >= 3 for s in skills.vocabulary() for a in s["aliases"])


def test_rising_skills_are_what_your_field_uses_and_you_dont_show():
    cfg = MyGeekyConfig(keywords=["gwas"])
    docs = [_doc("Nextflow pipeline for GWAS"), _doc("nf-core gwas workflow", "contribute"),
            _doc("Nextflow tutorial", "paper", days_ago=100), _doc("Docker image"),          # Docker: once only
            _doc("GWAS summary statistics", "paper"), _doc("gwas fine mapping", "tool")]
    out = skills.rising(cfg, docs=docs, mine="I do GWAS", weights={"gwas": 1.0}, today=TODAY, save=False)
    names = [s["name"] for s in out["skills"]]
    assert "Nextflow" in names and "Docker" not in names
    assert "GWAS" not in names and "GWAS" in [s["name"] for s in out["strengths"]]
    nf = next(s for s in out["skills"] if s["name"] == "Nextflow")
    assert nf["reasons"][0].startswith("in ") and nf["mentions"] == 3
    taste.vote("skill", "Nextflow", False)
    out = skills.rising(cfg, docs=docs, mine="I do GWAS", weights={"gwas": 1.0}, today=TODAY, save=False)
    assert "Nextflow" not in [s["name"] for s in out["skills"]] and out["hidden"] == 1


def test_rising_is_only_claimed_where_no_one_picked_for_you():
    cfg = MyGeekyConfig()
    docs = [_doc("snakemake rule"), _doc("snakemake workflow", "contribute")] * 3 + [_doc("snakemake old", days_ago=200)]
    out = skills.rising(cfg, docs=docs, mine="", weights={}, today=TODAY, save=False)
    assert out["skills"][0]["name"] == "Snakemake" and out["skills"][0]["rising"] is False   # only your own feed
    world = {"docs": [1000, 1000], "skills": {"Snakemake": [10, 40]}}
    sk = skills.rising(cfg, docs=docs, mine="", weights={}, today=TODAY, save=False, trends=world)["skills"][0]
    assert sk["rising"] is True and sk["growth"] > 3 and sk["lo"] > 1.1
    few = {"docs": [1000, 1000], "skills": {"Snakemake": [1, 3]}}       # 3x, but on four mentions: not sure yet
    assert skills.rising(cfg, docs=docs, mine="", weights={}, today=TODAY, save=False, trends=few)["skills"][0]["rising"] is False


def test_a_rise_you_made_yourself_is_marked_and_one_beyond_your_usual_too():
    cfg = MyGeekyConfig()
    mine = [_doc("snakemake rule")] * 6 + [_doc("snakemake old", days_ago=200)] + [_doc("python script")] * 3
    wide = [dict(_doc("nextflow pipeline"), pick="wide"), dict(_doc("nextflow tutorial", days_ago=80), pick="wide")]
    world = {"docs": [2000, 2000], "skills": {"Snakemake": [20, 20], "Nextflow": [5, 40]}}
    out = skills.rising(cfg, docs=mine + wide, mine="", weights={}, today=TODAY, save=False, trends=world)
    by = {s["name"]: s for s in out["skills"]}
    assert by["Snakemake"]["self_made"] is True and by["Snakemake"]["rising"] is False
    assert by["Nextflow"]["beyond"] is True and by["Nextflow"]["rising"] is True
    assert by["Nextflow"]["mine"] == 0 and by["Nextflow"]["world"] > 0


def test_the_views_join_your_skills_to_the_rising_ones():
    cfg = MyGeekyConfig()
    docs = [_doc("GWAS with Nextflow"), _doc("GWAS and nextflow again"), _doc("python and docker"),
            _doc("docker images in python"), _doc("GWAS on Docker")]
    world = {"docs": [1000, 1000], "skills": {"Nextflow": [5, 40], "Docker": [30, 30], "GWAS": [20, 60]}}
    out = skills.rising(cfg, docs=docs, mine="I do GWAS in Python", weights={}, today=TODAY, save=False, trends=world)
    assert ["GWAS", "Nextflow", 2] in out["links"] and ["Python", "Docker", 2] in out["links"]
    v = skills.shapes(out)
    nf = next(n for n in v["next"] if n["name"] == "Nextflow")
    assert nf["via"] == "GWAS" and nf["more"] == 0 and nf["sure"] is True
    assert set(v["flow"]["left"]) == {"GWAS", "Python"} and set(v["flow"]["right"]) == {"Nextflow", "Docker"}
    assert set(v["ladder"]["left"]) == {"GWAS", "Python"} and ["GWAS", "Nextflow", 2] in v["ladder"]["links"]
    assert all(r["mine"] > r["world"] for r in v["lens"]["mine"]) and all(r["world"] > r["mine"] for r in v["lens"]["world"])


def test_the_world_file_is_cleaned_and_the_phone_has_the_same_one():
    from mygeeky import skilltrends
    c = skilltrends.clean({"version": "2026-10-19", "docs": [10, 12], "skills": {"Nextflow": [1, 2], "Made up": [1, 1],
                                                                                "Docker": ["x", -3]}})
    assert c == {"version": "2026-10-19", "docs": [10, 12], "skills": {"Nextflow": [1, 2], "Docker": [0, 0]}}
    assert skilltrends.clean("junk")["skills"] == {}
    root = Path(__file__).resolve().parents[1]
    assert (root / "src/mygeeky/data/skill_trends.json").read_bytes() == (root / "mobile/src/data/skill_trends.json").read_bytes()
    (old_lo, old_hi), (new_lo, new_hi) = skilltrends.windows(TODAY)
    assert (new_hi - new_lo).days == (old_hi - old_lo).days == skilltrends.WINDOW_DAYS - 1 and (new_lo - old_hi).days == 1


def test_counts_are_kept_per_day_for_later(monkeypatch):
    cfg = MyGeekyConfig()
    skills.rising(cfg, docs=[_doc("polars dataframe"), _doc("polars")], mine="", weights={}, today=TODAY)
    hist = skills._history()
    assert hist["2026-10-13"]["Polars"] > 0


# --------------------------------------------------------------------------- wins
def _repo(name, stars, forks=0):
    return {"name": name, "url": f"https://github.com/{name}", "stars": stars, "forks": forks}


def test_the_first_read_only_sets_the_starting_point():
    assert wins.diff({}, [_repo("me/a", 5)], {"W1": {"title": "T", "cited": 3, "url": "u"}}, "now") == []


def test_new_stars_forks_milestones_and_citations_are_wins():
    old = {"repos": {"me/a": {"stars": 8, "forks": 1}, "me/b": {"stars": 2, "forks": 0}},
           "papers": {"W1": {"cited": 3}}}
    new = wins.diff(old, [_repo("me/a", 12, 3), _repo("me/b", 3), _repo("me/new", 50)],
                    {"W1": {"title": "My paper", "cited": 5, "url": "https://doi.org/x"}}, "2026-10-13T00:00:00+00:00")
    texts = [w["text"] for w in new]
    assert "a reached 10 ⭐" in texts and "b got 1 new ⭐" in texts and "2 new forks of a" in texts
    assert any("My paper" in t and "2 more times" in t for t in texts)
    assert not any("new" == w["text"].split()[0] for w in new)           # a brand-new repo isn't a win yet


def test_refresh_saves_counts_keeps_wins_and_asks_who_cited(monkeypatch):
    cfg = MyGeekyConfig(github_username="me")

    class Client:
        stars = 3

        def list_repos(self, user, max_pages=3):
            return [{"full_name": "me/tool", "stargazers_count": self.stars, "forks_count": 0, "topics": ["gwas"]},
                    {"full_name": "me/forked", "fork": True}]

    monkeypatch.setattr(wins, "read_papers", lambda author, session: {})
    c = Client()
    first = wins.refresh(cfg, client=c, force=True)
    assert first["wins"] == [] and first["repos"] == {"me/tool": {"stars": 3, "forks": 0}}
    assert [r["name"] for r in wins.load_my_repos()] == ["me/tool"]
    c.stars = 4
    second = wins.refresh(cfg, client=c, force=True)
    assert [w["text"] for w in second["wins"]] == ["tool got 1 new ⭐"]
    assert wins.refresh(cfg, client=c) is not None and not wins.due(wins.load())
    assert [w["text"] for w in wins.recent()] == ["tool got 1 new ⭐"]


# --------------------------------------------------------------------------- collaborators
def test_collaborators_who_bring_what_you_lack_come_first():
    people = [
        {"login": "same", "interests": ["gwas", "python"], "shared": ["gwas"], "fit": 0.6},
        {"login": "complement", "interests": ["gwas", "nextflow", "docker"], "shared": ["gwas"], "fit": 0.6},
        {"login": "stranger", "interests": ["knitting"], "shared": [], "fit": 0.0},
    ]
    out = collab.matches(people, have={"GWAS", "Python"}, wanted={"Nextflow"}, collab_sent={"complement"})
    logins = [p["login"] for p in out["people"]]
    assert logins[0] == "complement" and "stranger" not in logins
    top = out["people"][0]
    assert top["they_bring"][0] == "Nextflow" and top["asked"] is True and "Python" in top["you_bring"]
    taste.vote("collaborator", "complement", False)
    out = collab.matches(people, have={"GWAS", "Python"}, wanted={"Nextflow"})
    assert [p["login"] for p in out["people"]] == ["same"] and out["hidden"] == 1


# --------------------------------------------------------------------------- the panel
def test_grow_and_chances_planets_draw_their_cards_safely(monkeypatch):
    pytest.importorskip("PySide6")
    from tests.test_freshness import _close, _quiet_panel
    from mygeeky.files import write_json
    from mygeeky.config import CURATED_FILE
    write_json(CURATED_FILE, {"checked_at": datetime.now(timezone.utc).isoformat(), "lists": _lists(
        version="2099-01-01T00:00:00Z",
        jobs=[_job("evil-job", title="<img src=x> Postdoc <b>now</b>", deadline=(date.today() + timedelta(days=3)).isoformat())],
        resources=[{"id": "nf-train", "title": "Nextflow training", "url": "https://training.nextflow.io/",
                    "skills": ["nextflow"], "level": "beginner"}])})
    monkeypatch.setattr("mygeeky.gui.app.growth_due", lambda cfg: False)
    app, panel = _quiet_panel(monkeypatch, MyGeekyConfig(github_username="me", keywords=["gwas"]))
    try:
        panel._switch_tab("chances")
        for w in list(panel._workers):
            w.wait(5000)
        for _ in range(5):
            app.processEvents()
        from PySide6.QtWidgets import QLabel
        from mygeeky.gui.growth_ui import OpportunityCard
        cards = panel.chances_area.parentWidget().findChildren(OpportunityCard)
        assert len(cards) == 1
        texts = " ".join(lbl.text() for lbl in cards[0].findChildren(QLabel))
        assert "&lt;img src=x&gt;" in texts and "<img" not in texts                # escaped, never drawn
        assert "closes in 3 days" in texts
        panel._switch_tab("grow")
        for mode in ("skills", "paths", "learn", "wins", "collab"):
            panel._set_grow_mode(mode)
            for w in list(panel._workers):
                w.wait(5000)
            app.processEvents()
        panel._set_grow_mode("learn")
        assert not panel._growth.get("error"), panel._growth
        from mygeeky.gui.growth_ui import ResourceRow, ThumbBar
        rows = panel.grow_area.parentWidget().findChildren(ResourceRow)
        assert rows, "the bundled learning resources show"
        bar = rows[0].findChild(ThumbBar)
        bar.up.click()
        assert bar.vote == 1 and taste.vote_of("resource", "nf-train") == 1
        bar.up.click()                                             # again: taken back
        assert bar.vote == 0 and taste.vote_of("resource", "nf-train") == 0
    finally:
        _close(panel)


# --------------------------------------------------------------------------- the phone carries the same lists
def test_the_phone_bundles_the_same_skills_and_curated_lists():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for name in ("skills.json", "curated.json"):
        desktop = json.loads((root / "src" / "mygeeky" / "data" / name).read_text(encoding="utf-8"))
        phone = json.loads((root / "mobile" / "src" / "data" / name).read_text(encoding="utf-8"))
        assert phone == desktop, f"mobile/src/data/{name} is out of date: copy it from src/mygeeky/data/"


def test_a_fetched_copy_with_the_same_version_still_wins():
    from mygeeky.config import CURATED_FILE
    from mygeeky.files import write_json
    shipped = json.loads(curated.BUNDLED.read_text(encoding="utf-8"))
    edited = dict(shipped, jobs=[_job("added-by-hand")])          # the maker forgot to stamp a new version
    write_json(CURATED_FILE, {"checked_at": datetime.now(timezone.utc).isoformat(), "lists": edited})
    assert [j["id"] for j in curated.load(force=True)["jobs"]] == ["added-by-hand"]


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_corrects_rising_skills_the_same_way():
    import random
    rng = random.Random(5)
    names = ["Nextflow", "Docker", "GWAS", "Python", "Snakemake", "Single-cell RNA-seq", "Polars"]
    cases = []
    for k in range(6):
        docs = [{"skills": rng.sample(names, rng.randint(0, 3)), "pick": rng.choice(["mine", "mine", "wide"]),
                 "recent": rng.random() < 0.6} for _ in range(rng.randint(0, 40))]
        trends = {"version": "2026-10-19", "docs": [rng.randint(0, 900), rng.randint(0, 900)],
                  "skills": {n: [rng.randint(0, 30), rng.randint(0, 30)] for n in rng.sample(names, 4)}} if k else {}
        feed = {n: round(rng.uniform(0.5, 3), 2) for n in names}
        cases.append({"docs": docs, "trends": trends, "feed": feed})
    cfg = MyGeekyConfig()
    docs = [_doc("GWAS with Nextflow"), _doc("GWAS and nextflow again"), _doc("python and docker"),
            _doc("docker images in python"), _doc("GWAS on Docker"), dict(_doc("polars in python"), pick="wide"),
            _doc("polars dataframes")]
    world = {"docs": [1000, 1000], "skills": {"Nextflow": [5, 40], "Docker": [30, 30], "GWAS": [20, 60]}}
    result = skills.rising(cfg, docs=docs, mine="I do GWAS in Python", weights={}, today=TODAY, save=False, trends=world)
    said = phone.run("""
import { cleanTrends, corrected, note, shapes } from './lib/skills.ts';
out({ corrected: INPUT.cases.map((c: any) => corrected(c.docs, cleanTrends(c.trends), c.feed)), shapes: shapes(INPUT.result),
      notes: [...INPUT.result.skills, ...INPUT.result.strengths].map(note),
      clean: INPUT.cases.map((c: any) => cleanTrends(c.trends)) });
""", {"cases": cases, "result": result})
    from mygeeky import skilltrends
    for c, got, cl in zip(cases, said["corrected"], said["clean"]):
        assert skilltrends.clean(c["trends"]) == cl
        assert json.loads(json.dumps(skills.corrected(c["docs"], skilltrends.clean(c["trends"]), c["feed"]))) == got
    assert json.loads(json.dumps(skills.shapes(result))) == said["shapes"]
    assert [skills.note(s) for s in result["skills"] + result["strengths"]] == said["notes"]
    assert any(said["notes"])
