"""Protocols: building, the level check, editing, publishing, harvesting, and the small model."""

import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from mygeeky import config, curated, protocols, protomodel
from mygeeky.config import MyGeekyConfig
from mygeeky.files import write_json

TODAY = date(2026, 10, 13)
ROOT = Path(__file__).resolve().parents[1]


def _model(**weights):
    """A tiny hand-made model: each word pushes towards one role."""
    w = {}
    for role, words in weights.items():
        for t in words.split():
            vec = [0.0] * len(protomodel.ROLES)
            vec[protomodel.ROLES.index(role)] = 4.0
            w[t] = vec
    return {"version": "t", "roles": protomodel.ROLES, "bias": [0.5, 0, 0, 0, 0], "weights": w}


def _repo(name, desc, stars=50, **kw):
    return {"kind": "repo", "id": f"gh:{name}", "title": name, "url": f"https://github.com/{name}", "text": desc,
            "topics": [], "language": "", "stars": stars, "updated": "2026-01-01", "pages": False, **kw}


def _article(i, title, cited=10):
    return {"kind": "article", "id": f"oa:W{i}", "title": title, "url": f"https://doi.org/10.1/{i}", "text": "",
            "topics": [], "type": "article", "year": 2022, "cited": cited, "oa": True}


def _write_repos(repos):
    """Your repo snapshot, in this test's temp dir. Path constants are read here, at run time: a
    module-level `from mygeeky.config import MY_REPOS_FILE` would still point at the real file."""
    path = config.MY_REPOS_FILE
    assert "pytest" in str(path).lower() or "tmp" in str(path).lower(), path
    write_json(path, {"repos": repos})


def _started(cfg, skill="R", goal="data analysis"):
    return protocols.start(cfg, protocols.fill(protocols.template(skill, goal), [], {"resources": []}))


# --------------------------------------------------------------------------- shape
def test_a_template_follows_the_skill_and_goal():
    p = protocols.template("rstats", "data analysis")          # an alias finds the skill
    assert p["skill"] == "R" and p["title"] == "R for data analysis" and p["id"] == "r-data-analysis"
    assert [s["title"] for s in p["stages"]] == ["R basics", "Statistics with R", "R for data analysis",
                                                 "A real project to rerun", "Use it in your own work"]
    assert [s["role"] for s in p["stages"]] == list(protocols.ROLES)
    assert all(s["can"] for s in p["stages"] if s["role"] != "use")
    q = protocols.template("Nextflow")
    assert q["title"] == "Learning Nextflow" and q["stages"][1]["title"] == "Nextflow in depth"


def test_cleaning_keeps_only_safe_parts():
    raw = {"id": "Bad Id!", "skill": "R", "title": "R", "reviewed": True, "stages": [
        {"id": "a", "title": "One", "role": "weird", "items": [
            {"title": "ok", "url": "https://x.org/a"}, {"title": "dup", "url": "https://x.org/a"},
            {"title": "http", "url": "http://x.org/b"}, {"title": "", "url": "https://x.org/c"}],
         "quiz": [{"q": "?", "options": ["a", "b"], "answer": 5}, {"q": "Q", "options": ["a", "b"], "answer": 1}]},
        {"id": "a", "title": "Two"}, {"title": ""}]}
    p = protocols.clean_protocol(raw)
    assert p["id"] == "r-protocol" and p["reviewed"] is False and p["source"] == "mine"   # the file can't claim "reviewed"
    assert [s["id"] for s in p["stages"]] == ["a", "a-2"] and p["stages"][0]["role"] == "applied"
    assert [i["url"] for i in p["stages"][0]["items"]] == ["https://x.org/a"]
    assert p["stages"][0]["quiz"] == [{"q": "Q", "options": ["a", "b"], "answer": 1}]
    assert protocols.clean_protocol({"skill": "R", "title": "x", "stages": []}) is None


def test_the_shipped_reviewed_protocols_are_clean_and_found_by_alias():
    data = json.loads((ROOT / "src/mygeeky/data/curated.json").read_text(encoding="utf-8"))
    assert curated.problems(data) == []
    clean = curated.clean(data)["protocols"]
    assert len(clean) == len(data["protocols"]) >= 5 and all(p["reviewed"] for p in clean)
    assert protocols.find_reviewed("rstats", "data analysis")["id"] == "r-data-analysis"
    assert protocols.find_reviewed("nextflow")["id"] == "nextflow"
    assert protocols.find_reviewed("Polars") is None
    r = protocols.find_reviewed("R")
    assert [s["title"] for s in r["stages"]][:3] == ["R basics", "Statistics with R", "R for data analysis"]
    assert all(q["answer"] < len(q["options"]) for s in r["stages"] for q in s["quiz"])


def test_curated_check_reports_a_broken_protocol():
    errs = curated.problems({"protocols": [{"id": "x-1", "skill": "R", "title": "R", "stages": [
        {"title": "S", "items": [{"title": "no https", "url": "http://a.org"}],
         "quiz": [{"q": "?", "options": ["a"], "answer": 3}]}]}]})
    assert any("https://" in e for e in errs) and any("quiz" in e for e in errs)


# --------------------------------------------------------------------------- building
def test_fill_sorts_candidates_into_stages_with_the_model():
    model = _model(basics="beginner introduction", deeper="statistics theory", applied="analysis workflow",
                   project="pipeline reproducible", none="library package")
    cands = [_repo("a/intro", "A beginner introduction", stars=5000), _repo("b/stats", "statistics theory"),
             _repo("c/lib", "a fast library package", stars=90000), _repo("d/flow", "analysis workflow"),
             _repo("e/pipe", "reproducible pipeline"), _article(1, "statistics theory review"),
             _article(2, "statistics theory again"), _repo("f/old", "beginner introduction", archived=True)]
    p = protocols.fill(protocols.template("R", "data analysis"), cands, {"resources": []}, model=model,
                       lean_weights={}, today=TODAY)
    by = {s["role"]: [i["url"] for i in s["items"]] for s in p["stages"]}
    assert by["basics"] == ["https://github.com/a/intro"]
    assert "https://github.com/b/stats" in by["deeper"]
    assert sum(1 for u in by["deeper"] if "doi.org" in u) == 1        # one article per stage
    assert by["applied"] == ["https://github.com/d/flow"] and by["project"] == ["https://github.com/e/pipe"]
    assert all("c/lib" not in u for us in by.values() for u in us)     # "none" is left out
    assert by["use"] == []
    empty = protocols.fill(protocols.template("Polars"), [], {"resources": []}, model=model, lean_weights={})
    assert all("github.com/search" in s["items"][0]["url"] for s in empty["stages"] if s["role"] != "use")


def test_curated_resources_come_first_by_level():
    data = curated.clean({"resources": [
        {"id": "nf-a", "title": "Nextflow training", "url": "https://training.nextflow.io/", "skills": ["nextflow"],
         "level": "beginner"},
        {"id": "nf-b", "title": "nf-core docs", "url": "https://nf-co.re/docs/", "skills": ["nextflow"],
         "level": "advanced"}]})
    p = protocols.fill(protocols.template("Nextflow"), [], data, model=_model(), lean_weights={})
    assert p["stages"][0]["items"][0]["url"] == "https://training.nextflow.io/"
    assert p["stages"][1]["items"][0]["url"] == "https://nf-co.re/docs/"


def test_build_uses_the_reviewed_protocol_when_there_is_one(monkeypatch):
    cfg = MyGeekyConfig()
    asked = []
    monkeypatch.setattr(protocols, "candidates_for", lambda *a, **k: asked.append(1) or [])
    p = protocols.build(cfg, "R", "data analysis", docs=[])
    assert p["reviewed"] and p["id"] == "r-data-analysis" and not asked
    q = protocols.build(cfg, "Polars", docs=[{"source": "repo", "url": "https://github.com/me/polars-demo",
                                              "title": "me/polars-demo", "text": "a polars analysis"}])
    assert not q["reviewed"] and q["source"] == "auto" and asked
    project = next(s for s in q["stages"] if s["role"] == "project")
    assert project["items"][0]["url"] == "https://github.com/me/polars-demo"   # a real project from your field


# --------------------------------------------------------------------------- the level check
def test_evidence_from_your_repos_skips_what_you_know(monkeypatch):
    cfg = MyGeekyConfig()
    repos = [{"name": f"me/r{i}", "description": "statistics in R" if i < 2 else "a tool", "topics": [],
              "language": "R"} for i in range(3)]
    p = protocols.template("R", "data analysis")
    ev = protocols.evidence(cfg, p, repos=repos, mine="")
    assert ev["basics"]["known"] and "3 of your repos use R" in ev["basics"]["why"]
    assert ev["deeper"]["known"] and "statistics" in ev["deeper"]["why"]
    assert not ev["applied"]["known"] and ev["use"]["known"]
    assert not protocols.evidence(cfg, p, repos=[], mine="")["basics"]["known"]


def test_status_quiz_self_and_overrule():
    cfg = MyGeekyConfig()
    pid = protocols.start(cfg, protocols.find_reviewed("R", "data analysis"))
    _write_repos([{"name": f"me/r{i}", "description": "x", "topics": [], "language": "R"} for i in range(2)])
    v = protocols.views(cfg)[0]
    st = {s["id"]: s for s in v["stages"]}
    assert st["basics"]["status"] == "known" and st["basics"]["how"] == "evidence"
    assert st["deeper"]["status"] == "current" and v["current"] == "deeper"
    assert st["use"]["status"] == "done"
    protocols.mark_known(cfg, pid, "basics", "no")                        # "not really"
    st = {s["id"]: s for s in protocols.views(cfg)[0]["stages"]}
    assert st["basics"]["status"] == "current" and st["basics"]["overruled"]
    quiz = protocols.find_reviewed("R")["stages"][1]["quiz"]
    assert protocols.answer_quiz(cfg, pid, "deeper", [q["answer"] for q in quiz]) == 1.0
    wrong = [(q["answer"] + 1) % len(q["options"]) for q in quiz]
    assert protocols.answer_quiz(cfg, pid, "applied", wrong) == 0.0
    protocols.mark_known(cfg, pid, "project", "self")
    protocols.tick(cfg, pid, "applied")
    st = {s["id"]: s for s in protocols.views(cfg)[0]["stages"]}
    assert st["deeper"]["how"] == "quiz" and st["applied"]["status"] == "done"
    assert st["project"]["how"] == "self" and st["basics"]["status"] == "current"


# --------------------------------------------------------------------------- editing
def test_editing_reorders_adds_and_removes_and_makes_it_yours():
    cfg = MyGeekyConfig()
    pid = protocols.start(cfg, protocols.find_reviewed("R", "data analysis"))
    get = lambda: protocols.mine(cfg)[pid]  # noqa: E731
    first = get()["protocol"]["stages"][0]["items"][0]["url"]
    assert protocols.move_stage(cfg, pid, "deeper", -1)
    e = get()
    assert [s["id"] for s in e["protocol"]["stages"]][:2] == ["deeper", "basics"]
    assert e["edited"] and e["protocol"]["source"] == "mine" and e["protocol"]["based_on"] == "r-data-analysis"
    assert not e["protocol"]["reviewed"]
    assert protocols.rename_stage(cfg, pid, "basics", "Base R first")
    assert protocols.add_stage(cfg, pid, "Shiny apps")
    stages = get()["protocol"]["stages"]
    assert stages[-1]["role"] == "use" and stages[-2]["title"] == "Shiny apps"     # before "your own work"
    assert protocols.remove_item(cfg, pid, "basics", first)
    assert first in get()["removed"]
    assert protocols.add_item(cfg, pid, "shiny-apps", "https://mastering-shiny.org/", "Mastering Shiny")
    assert not protocols.add_item(cfg, pid, "shiny-apps", "http://insecure.org/", "x")
    assert protocols.add_item(cfg, pid, "basics", first, "back again")
    assert first not in get()["removed"]                                  # put back: no longer "removed"
    basics = next(s for s in get()["protocol"]["stages"] if s["id"] == "basics")
    last = basics["items"][-1]["url"]
    assert protocols.move_item(cfg, pid, "basics", last, 1)               # past the bottom: to the next stage
    nxt = get()["protocol"]["stages"][2]
    assert nxt["items"][0]["url"] == last
    assert protocols.remove_stage(cfg, pid, "shiny-apps")
    assert "https://mastering-shiny.org/" in get()["removed"]
    assert not protocols.move_stage(cfg, pid, "deeper", -1)               # already first: nothing changes
    protocols.stop(cfg, pid)
    assert protocols.mine(cfg) == {}


def test_starting_the_same_id_twice_keeps_both_when_they_differ():
    cfg = MyGeekyConfig()
    a = _started(cfg)
    assert _started(cfg) == a and len(protocols.mine(cfg)) == 1          # the same one again: nothing new
    assert protocols.rename_stage(cfg, a, "basics", "Mine")
    b = _started(cfg)                                                     # yours changed: the new one sits beside it
    assert b == f"{a}-2" and set(protocols.mine(cfg)) == {a, b}


def test_old_learning_paths_become_protocols():
    cfg = MyGeekyConfig()
    write_json(config.PATHS_FILE, {"paths": {"Nextflow": {"started_at": "2026-10-01", "done": ["basics", "practice"]}}})
    e = protocols.mine(cfg)["nextflow"]
    assert e["protocol"]["reviewed"] and e["started_at"] == "2026-10-01"
    assert set(e["done"]) == {"basics", "project"}


# --------------------------------------------------------------------------- publishing and harvesting
def test_publishing_sends_the_protocol_and_nothing_private():
    cfg = MyGeekyConfig()
    pid = protocols.start(cfg, protocols.find_reviewed("R", "data analysis"))
    gone = protocols.mine(cfg)[pid]["protocol"]["stages"][0]["items"][0]["url"]
    protocols.remove_item(cfg, pid, "basics", gone)
    protocols.answer_quiz(cfg, pid, "deeper", [0, 0, 0, 0])
    protocols.tick(cfg, pid, "applied")
    entry = protocols.mine(cfg)[pid]
    out = protocols.publish(entry)
    url = out["url"]
    assert url.startswith("https://github.com/mygeeky/myGeeKy-ideas/issues/new?") and len(url) <= 7000
    assert out["clipboard"] == ""
    q = parse_qs(urlsplit(url).query)
    assert q["title"][0].startswith("🧭 Protocol: ") and q["labels"] == ["protocol"]
    body = q["body"][0]
    payload = json.loads(body.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert payload["removed"] == [gone] and payload["based_on"] == "r-data-analysis"
    for private in ("done", "known", "quiz", "started_at", "edited"):
        assert private not in payload
    assert '"score"' not in body and all("quiz" not in s and "can" not in s for s in payload["stages"])
    issue = {"title": q["title"][0], "body": body, "number": 7, "user": {"login": "someone"},
             "html_url": "https://github.com/mygeeky/myGeeKy-ideas/issues/7", "state": "open"}
    got = protocols.parse_issue(issue)
    assert got["protocol"]["by"] == "someone" and got["removed"] == [gone] and not got["protocol"]["reviewed"]
    assert [s["id"] for s in got["protocol"]["stages"]] == [s["id"] for s in entry["protocol"]["stages"]]
    assert protocols.parse_issue({"title": "💡 an idea", "body": body}) is None


def test_a_huge_protocol_still_fits_in_a_link():
    cfg = MyGeekyConfig()
    pid = _started(cfg)
    for i in range(6):
        protocols.add_stage(cfg, pid, f"Extra stage {i}")
    for st in protocols.mine(cfg)[pid]["protocol"]["stages"]:
        for k in range(8):
            protocols.add_item(cfg, pid, st["id"], f"https://example.org/{st['id']}/{k}/" + "x" * 60, "T" * 120)
    out = protocols.publish(protocols.mine(cfg)[pid])
    assert len(out["url"]) <= 7000 and out["clipboard"]                   # too long for a link: pasted instead
    issue = {"title": "🧭 Protocol: x", "body": out["clipboard"], "user": {"login": "u"}}
    assert len(protocols.parse_issue(issue)["protocol"]["stages"]) == 10


def test_published_links_open_from_the_panel():
    from mygeeky.gui import app
    cfg = MyGeekyConfig()
    pid = _started(cfg)
    protocols.add_item(cfg, pid, "basics", "https://mastering-shiny.org/", "Mastering Shiny")
    assert app._curated_link("https://mastering-shiny.org/")
    assert app._curated_link("https://r4ds.hadley.nz/")                  # in a reviewed protocol
    assert not app._curated_link("https://evil.example/")


# --------------------------------------------------------------------------- the model
def test_tokens_mask_the_skill_and_bin_the_facts():
    t = protomodel.tokens(_repo("x/r-course", "Learn R programming: an R course", stars=1500), ["r", "rstats"], TODAY)
    assert "__skill" in t and "r" not in t and "course" in t and "an___skill" in t and "__skill_course" in t
    assert "__kind_repo" in t and "__stars_3" in t and "__updated_0" in t
    a = protomodel.tokens(_article(3, "A GWAS tutorial", cited=150), ["gwas"], TODAY)
    assert "__skill_tutorial" in a and "__cited_2" in a and "__oa" in a


def test_predict_is_a_probability():
    p = protomodel.predict(_repo("a/b", "beginner introduction"), [], _model(basics="beginner"), TODAY)
    assert abs(sum(p.values()) - 1) < 1e-9 and max(p, key=p.get) == "basics"


def test_the_shipped_model_is_small_and_sensible():
    path = ROOT / "src/mygeeky/data/protocol_model.json"
    assert path.stat().st_size < 1_000_000
    m = protomodel.load(path)
    assert m["roles"] == protomodel.ROLES and len(m["weights"]) > 100
    course = _repo("someone/r-for-beginners", "A free course: learn R programming for beginners, with exercises",
                   stars=3000)
    lib = _repo("someone/fastjson", "Fast JSON parser library written in C++", stars=8000)
    p_course = protomodel.predict(course, ["r"], m, TODAY)
    p_lib = protomodel.predict(lib, ["r"], m, TODAY)
    assert p_course["none"] < 0.5 and p_lib["none"] > p_course["none"]
    assert (ROOT / "mobile/src/data/protocol_model.json").read_text(encoding="utf-8") == \
        path.read_text(encoding="utf-8")


def test_queries_follow_the_skill():
    qs = protomodel.github_queries("R", "language", "data analysis")
    assert "R tutorial" in qs and "R data analysis" in qs and "data analysis language:R" in qs
    assert protomodel.github_queries("Nextflow")[0] == "Nextflow tutorial"
    assert protomodel.github_queries("Mixed models")[0] == '"Mixed models" tutorial'


# --------------------------------------------------------------------------- how it's shown: Step and Resource
def test_each_kind_of_link_is_shown_its_own_way():
    R = protocols.Resource.from_link
    repo = R(protocols.clean_item({"title": "hadley/r4ds", "url": "https://github.com/hadley/r4ds", "kind": "repo",
                                   "note": "R for data science", "stars": 4900, "lang": "R", "updated": "2025-03-01"}))
    assert (repo.label, repo.title, repo.action) == ("GitHub repo", "r4ds", "Open on GitHub")
    assert repo.subtitle == "by hadley · ⭐ 4.9k · R · updated 2025" and repo.blurb == "R for data science"
    paper = R({"title": "Tidy Data", "url": "https://doi.org/10.18637/jss.v059.i10", "kind": "article", "year": 2014,
               "cited": 6100})
    assert (paper.label, paper.action, paper.subtitle) == ("Paper", "Read the paper", "2014 · cited 6.1k× · DOI")
    book = R({"title": "R for Data Science (2e)", "url": "https://www.r4ds.hadley.nz/", "kind": "book"})
    assert (book.icon, book.subtitle, book.action) == ("📖", "r4ds.hadley.nz", "Read the book")
    search = R(protocols._search_link("Polars", "tutorial"))
    assert search.kind == "search" and search.title == "Polars tutorial" and search.action == "Search GitHub"


def test_a_protocol_view_has_steps_ready_to_show():
    cfg = MyGeekyConfig()
    pid = protocols.start(cfg, protocols.find_reviewed("R", "data analysis"))
    _write_repos([{"name": f"me/r{i}", "description": "x", "topics": [], "language": "R"} for i in range(2)])
    protocols.tick(cfg, pid, "deeper")
    steps = protocols.views(cfg)[0]["steps"]
    assert [s.number for s in steps] == [1, 2, 3, 4, 5]
    assert [s.status for s in steps] == ["known", "done", "current", "todo", "done"]
    first, third, last = steps[0], steps[2], steps[4]
    assert first.why == "From your work: 2 of your repos use R" and not first.can_check
    assert third.role_label == "Apply it" and third.status_label == "Start here" and third.can_check
    assert [r.kind for r in third.resources] == ["course", "book", "article"]
    assert last.auto and last.why.startswith("Done: ")


def test_facts_are_kept_on_links_but_not_published():
    cfg = MyGeekyConfig()
    p = protocols.fill(protocols.template("Snakemake"), [_repo("a/snake-intro", "beginner introduction", stars=321,
                                                                language="Python")],
                       {"resources": []}, model=_model(basics="beginner"), lean_weights={}, today=TODAY)
    item = p["stages"][0]["items"][0]
    assert item["stars"] == 321 and item["lang"] == "Python" and item["updated"] == "2026-01-01"
    pid = protocols.start(cfg, p)
    payload = protocols.publish_payload(protocols.mine(cfg)[pid])
    assert set(payload["stages"][0]["items"][0]) == {"title", "url", "kind", "note"}


def test_the_road_map_makes_room_for_the_chosen_step():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from mygeeky.gui.growth_ui import StepBar, qcolor
    from mygeeky.gui.qt_panel import THEMES
    cfg = MyGeekyConfig()
    protocols.start(cfg, protocols.find_reviewed("GWAS"))
    steps = protocols.views(cfg)[0]["steps"]
    for chosen in ("basics", "project"):
        bar = StepBar(steps, chosen, THEMES["midnight"], lambda sid: None)
        bar.resize(340, 70)
        cols = bar.columns()
        widths = {s.id: w for s, (_, w) in zip(steps, cols)}
        assert abs(sum(widths.values()) - 340) < 0.5                       # fills the width, never wider
        assert widths[chosen] > max(w for sid, w in widths.items() if sid != chosen)
        assert min(widths.values()) >= StepBar.MIN_COL - 0.01
        assert all(abs(cols[i][0] + cols[i][1] - cols[i + 1][0]) < 0.01 for i in range(len(cols) - 1))
    c = qcolor("rgba(255,255,255,51)")
    assert (c.red(), c.alpha()) == (255, 51) and qcolor("#34d399").name() == "#34d399"
