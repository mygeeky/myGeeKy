"""🏠 Home's feed: fit, freshness, what you've seen, the kinds you enjoy, variety and new territory -- and the phone
arranging the very same feed."""

import json

import pytest

from mygeeky import feed
from tests import phone

TODAY = "2026-10-21"
W = {"gwas": 1.0, "plant breeding": 0.8, "snakemake": 0.7, "genomics": 0.6}


def card(cid, kind, title, at=TODAY, source="", terms=()):
    return {"id": cid, "kind": kind, "title": title, "at": at, "source": source or kind, "terms": list(terms)}


CARDS = [
    card("p1", "paper", "A GWAS of drought tolerance in wheat", source="openalex"),
    card("p2", "paper", "Plant breeding with genomic selection", "2026-10-15", "openalex"),
    card("p3", "paper", "GWAS meta-analysis pipelines", "2026-10-20", "openalex"),
    card("p4", "paper", "Another GWAS paper", "2026-10-19", "openalex"),
    card("j1", "job", "Postdoc in statistical genetics (GWAS)", "2026-10-18", "curated"),
    card("h1", "headline", "Big model released", source="techpress"),
    card("h2", "headline", "Snakemake 9 is out", source="techpress"),
    card("d1", "dataset", "Rice genomics panel", "2026-10-01", "zenodo"),
    card("x1", "headline", "Mars rover finds water", source="space"),
    card("x2", "news", "Quantum computing for chemistry", "2026-10-20", "hn"),
    card("dup", "news", "Snakemake 9 is OUT!", "2026-10-20", "hn"),                # the same story as h2
]


def test_fit_matches_whole_words_best_first():
    f, terms = feed.fit(card("a", "paper", "GWAS for plant breeding"), W)
    assert terms == ["gwas", "plant breeding"] and f == feed.r4(1.0)           # capped at 1
    assert feed.fit(card("b", "paper", "gwasx and genomicsish"), W) == (0.0, [])  # whole words only
    assert feed.fit(card("c", "paper", "Rice", terms=["genomics"]), W)[0] == 0.6


def test_fresh_things_first_and_each_kind_fades_at_its_own_pace():
    assert feed.freshness(card("a", "headline", "x"), TODAY) == 1.0
    assert feed.freshness(card("a", "headline", "x", "2026-10-19"), TODAY) == 0.5     # two days: half
    assert feed.freshness(card("a", "paper", "x", "2026-10-07"), TODAY) == 0.5        # two weeks: half
    assert feed.freshness(card("a", "paper", "x", at=""), TODAY) == feed.r4(0.5 ** (30 / 14))


def test_the_feed_has_variety_and_new_territory_and_puts_what_you_saw_last():
    seen = {"p3": {"n": 2}}
    items = feed.arrange(CARDS, {"today": TODAY, "weights": W, "seen": seen})
    kinds = [x["card"]["kind"] for x in items]
    fresh = [x["card"]["kind"] for x in items if not x["seen"]]
    assert all(max(fresh[i:i + 4].count(k) for k in fresh[i:i + 4]) <= 2 for i in range(len(fresh) - 3) if len(set(fresh)) > 2), fresh
    assert items[4]["explore"] and "new territory" in items[4]["why"]                          # the fifth: 🔭
    assert items[-1]["card"]["id"] == "p3" and items[-1]["seen"]                               # seen: after "caught up"
    assert items[0]["card"]["id"] == "p1" and items[0]["why"].startswith("matches gwas")
    assert len(items) == len(CARDS) - 1 and "dup" not in [x["card"]["id"] for x in items]   # shown once


def test_it_learns_which_kinds_you_enjoy_and_forgets_slowly():
    stats = {}
    for _ in range(4):
        stats = feed.learn(stats, "dataset", "open")
    stats = feed.learn(stats, "headline", "view", dwell=0.3)                   # skipped
    assert feed.kind_pref(stats, "dataset") > feed.kind_pref(stats, "headline")
    assert feed.kind_pref({}, "quiz") > 0.5                                    # an untried kind gets a chance
    faded = feed.learn(stats, "job", "view", dwell=2, days_since=30)
    assert faded["dataset"]["s"] == 2.0                                        # half after 30 days
    learned = {x["card"]["id"]: x["score"] for x in feed.score_all(CARDS, {"today": TODAY, "weights": W, "stats": stats})}
    plain = {x["card"]["id"]: x["score"] for x in feed.score_all(CARDS, {"today": TODAY, "weights": W})}
    assert learned["d1"] > plain["d1"]                                         # datasets climb
    assert feed.kind_pref(stats, "headline") < feed.kind_pref(stats, "quiz")    # skipped sinks below untried


def test_seen_and_opened_and_the_store_with_its_switch(monkeypatch, tmp_path):
    s = feed.mark_seen({}, "a", False, TODAY)
    s = feed.mark_seen(s, "a", True, TODAY)
    assert s["a"] == {"n": 1, "opened": True, "at": TODAY} and feed.seen_factor(s, "a") == 0.15
    feed.record("paper", "p1", "open", today=TODAY)
    st = feed.load()
    assert st["stats"]["paper"]["s"] == 1 and st["seen"]["p1"]["opened"]
    feed.set_dwell(False)
    feed.record("paper", "p2", "view", dwell=9, today=TODAY)                   # time on screen: switched off
    assert "p2" not in feed.load()["seen"]


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_arranges_the_same_feed_and_learns_the_same():
    stats = feed.learn(feed.learn({}, "dataset", "open"), "headline", "view", dwell=0.2)
    ctx = {"today": TODAY, "weights": W, "seen": {"p3": {"n": 2}}, "stats": stats}
    said = phone.run("""
import { arrange, interestKind, interestText, learn, markSeen } from './lib/feed.ts';
const s1 = learn(learn({}, 'dataset', 'open'), 'headline', 'view', 0.2);
out({ items: arrange(INPUT.cards, INPUT.ctx), stats: s1, faded: learn(s1, 'job', 'view', 5, 45),
      seen: markSeen(markSeen({}, 'a', false, '2026-10-21'), 'a', true, '2026-10-21'),
      teach: INPUT.teach.map((c) => [interestKind(c), interestText(c)]) });
""", {"cards": CARDS, "ctx": ctx, "teach": TEACH})
    py = feed.arrange(CARDS, ctx)
    assert [(x["card"]["id"], x["score"], x["why"], x["explore"], x["seen"]) for x in said["items"]] == \
           [(x["card"]["id"], x["score"], x["why"], x["explore"], x["seen"]) for x in py]
    assert said["stats"] == stats and said["faded"] == feed.learn(stats, "job", "view", 5, 45)
    assert said["seen"] == feed.mark_seen(feed.mark_seen({}, "a", False, TODAY), "a", True, TODAY)
    assert json.dumps(said["items"][0]["card"]) == json.dumps(py[0]["card"])
    assert said["teach"] == [[feed.interest_kind(c), feed.interest_text(c)] for c in TEACH]


TEACH = [{"kind": "person", "title": "JakeWharton", "sub": "works on kotlin compilers"},
         {"kind": "work", "title": "Fine-mapping GWAS loci", "sub": "Nature · A. Smith, B. Jones"},
         {"kind": "job", "title": "Postdoc in statistical genetics", "sub": "Broad · closes in 9 days"},
         {"kind": "model", "title": "org/gwas-bert", "sub": "fill-mask"}]


def test_what_an_opened_card_teaches_the_model_has_no_names():
    assert [feed.interest_text(c) for c in TEACH] == ["works on kotlin compilers", "Fine-mapping GWAS loci",
                                                      "Postdoc in statistical genetics", "org/gwas-bert"]
    assert [feed.interest_kind(c) for c in TEACH] == ["person", "news", "news", "repo"]


def test_home_is_the_first_page_and_learns_from_what_you_do(qapp_offscreen, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from mygeeky.config import MyGeekyConfig
    from mygeeky.gui.qt_panel import MyGeekyPanel
    opened = []
    monkeypatch.setattr("mygeeky.gui.app.open_link", lambda url: opened.append(url))
    p = MyGeekyPanel(MyGeekyConfig(github_username="me", keywords=["gwas"]))
    try:
        p.resize(380, 800)
        p.show()
        assert p.active_tab == "home" and p.content_stack.currentWidget() is p.home_page
        cards = [dict(c, url="https://example.org/" + c["id"], page="chances:jobs" if c["kind"] == "job" else "news:headlines")
                 for c in CARDS]
        p.home_page._got(feed.arrange(cards, {"today": TODAY, "weights": W}))
        for _ in range(5):
            QApplication.processEvents()
        first = next(w for w in p.home_page.findChildren(__import__("mygeeky.gui.feed_ui", fromlist=["x"]).FeedCard))
        first.open()
        assert opened and feed.load()["seen"][first.card["id"]]["opened"]
        assert feed.load()["stats"][first.card["kind"]]["s"] == 1
        job = next(x for x in p.home_page.items if x["card"]["kind"] == "job")
        p.home_page.go(job["card"]["page"])                                   # "More in Jobs ›"
        assert p.active_tab == "chances" and p._chance_mode == "jobs"
        # time on screen: a card that showed for 5 s and left teaches "read"; switched off, nothing is learned
        p.home_page.dwell["x"] = 5.0
        p.home_page._tell({"id": "x", "kind": "headline"})
        assert feed.load()["stats"]["headline"]["s"] == 0.5
        feed.set_dwell(False)
        p.home_page.dwell["y"] = 5.0
        p.home_page._tell({"id": "y", "kind": "headline"})
        assert feed.load()["stats"]["headline"]["s"] == 0.5 and "y" not in feed.load()["seen"]
        feed.set_dwell(True)
        # a card seen for one moment and scrolled past is a skip; leaving Home teaches only what was read
        page = p.home_page
        p._switch_tab("home")
        card = next(w for w in page.findChildren(type(first)) if w.card["id"] not in page.told)
        cid = card.card["id"]
        page.dwell.clear()
        page.verticalScrollBar().setValue(0)
        page._tick()
        assert page.dwell.get(cid) == 0.0 or cid not in page.dwell          # first seen counts 0 s
        page.dwell = {cid: 0.0, "never-read": 2.0}
        card.hide()                                                          # off screen now
        card.move(0, 10000)
        before = feed.load()["stats"].get(card.card["kind"], {"f": 0})["f"]
        page._tick()
        assert feed.load()["stats"][card.card["kind"]]["f"] == before + 0.25 and cid in page.told
        other = next(w for w in page.findChildren(type(first)) if w.card["id"] not in page.told)
        stats = feed.load()["stats"]
        page.dwell = {other.card["id"]: 2.0}
        page._flush()
        assert page.dwell == {} and feed.load()["stats"] == stats            # dropped, not taught as a skip
    finally:
        p.close()
