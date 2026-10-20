"""Grow → 🗂️ Data: the acceptance rules, harvesting (with a stand-in network), cleaning, ranking for you -- and the
phone giving the same answers."""

import json
from datetime import date
from pathlib import Path

import pytest

import phone
from mygeeky import datasets

ROOT = Path(__file__).resolve().parents[1]
GOOD = {"id": "x", "title": "A clean table", "field": "Earth & climate", "why": "trends", "level": "beginner",
        "license": "CC-BY-4.0", "url": "https://example.org/x", "download": "https://example.org/x.csv",
        "size_mb": 3, "formats": ["csv"], "about": "a" * 130, "uses": 500, "doi": "10.5281/zenodo.1"}


def test_the_rules_say_which_one_a_record_breaks():
    assert datasets.accept(GOOD) == []
    cases = {"1 open licence": {"license": "All rights reserved"},
             "2 one click, no gate": {"about": "a" * 130 + " available on request"},
             "3 laptop-sized": {"size_mb": 9000},
             "4 common formats": {"formats": ["xyz"]},
             "5 documented": {"about": "short"},
             "7 validated or used": {"uses": 10},
             "9 says what to practise": {"level": "expert"},
             "10 one field": {"field": "Astrology"}}
    for rule, change in cases.items():
        assert rule in datasets.accept({**GOOD, **change}), rule
    assert datasets.accept({**GOOD, "size_mb": 9000, "starter": "one file", "starter_mb": 200}) == []
    assert datasets.accept({**GOOD, "uses": 0, "curated": True}) == []          # validated by its source
    assert "3 laptop-sized" in datasets.accept({**GOOD, "starter_mb": 3000})


def test_licences():
    assert datasets.licence_ok("cc-by-4.0") == (True, False)
    assert datasets.licence_ok("CC0-1.0") == (True, False)
    assert datasets.licence_ok("Public domain") == (True, False)
    assert datasets.licence_ok("cc-by-nc-4.0") == (True, True)
    assert datasets.licence_ok("cc-by-nd-4.0")[0] is False
    assert datasets.licence_ok("")[0] is False and datasets.licence_ok("proprietary")[0] is False


def test_every_core_dataset_passes_and_the_shipped_list_is_clean_and_on_the_phone():
    core = json.loads((ROOT / "src/mygeeky/data/datasets_core.json").read_text())["datasets"]
    assert len(core) >= 25 and len({d["field"] for d in core}) >= 8
    for d in core:
        assert datasets.accept({**d, "core": True}) == [], d["id"]
    shipped = json.loads((ROOT / "src/mygeeky/data/datasets.json").read_text())
    assert datasets.clean(shipped)["datasets"] == shipped["datasets"]
    assert len(shipped["datasets"]) >= len(core)
    assert (ROOT / "src/mygeeky/data/datasets.json").read_bytes() == (ROOT / "mobile/src/data/datasets.json").read_bytes()


class _Resp:
    def __init__(self, data=None, headers=None, status=200):
        self._data, self.headers, self.status_code = data, headers or {}, status

    def json(self):
        return self._data


class _Session:
    """Answers like Zenodo, NCBI and OpenML do, from canned pages."""

    def get(self, url, params=None, **kw):
        params = params or {}
        if "zenodo.org" in url:
            assert params.get("size", 0) <= 25                                  # Zenodo's guest limit
            if params.get("communities") == "galaxy-training" and params.get("page", 1) == 1:
                return _Resp({"hits": {"hits": [ZENODO_GALAXY]}})
            if params.get("q") == "RNA-seq tutorial dataset":
                return _Resp({"hits": {"hits": [ZENODO_OFF_TOPIC, ZENODO_SEARCH]}})
            return _Resp({"hits": {"hits": []}})
        if "esearch" in url:
            return _Resp({"esearchresult": {"idlist": ["4378"] if "Arabidopsis" in params["term"] else []}})
        if "esummary" in url:
            return _Resp({"result": {"4378": {"accession": "GDS4378", "title": "Ozone effect on <b>leaves</b>",
                                              "summary": "Analysis of leaves from G-protein mutants " * 5, "taxon": "Arabidopsis thaliana",
                                              "n_samples": "27", "ftplink": "ftp://ftp.ncbi.nlm.nih.gov/geo/datasets/GDS4nnn/GDS4378/"}}})
        if url.endswith("/data/list/tag/OpenML-CC18/limit/100"):
            return _Resp({"data": {"dataset": [{"did": 61, "name": "iris", "quality": [
                {"name": "NumberOfInstances", "value": "150.0"}, {"name": "NumberOfFeatures", "value": "5.0"}]}]}})
        if url.endswith("/data/61"):
            return _Resp({"data_set_description": {"description": "Fisher's iris data, " * 10, "licence": "Public",
                                                   "url": "https://openml.org/data/v1/download/61/iris.arff"}})
        return _Resp({}, status=404)

    def head(self, url, **kw):
        return _Resp(headers={"Content-Length": "2500000"})


ZENODO_GALAXY = {"id": 6457007, "doi": "10.5281/zenodo.6457007", "links": {"self_html": "https://zenodo.org/records/6457007"},
                 "stats": {"downloads": 278547},
                 "metadata": {"title": "Reference-based RNA-seq data analysis (training data)", "license": {"id": "cc-by-4.0"},
                              "description": "<p>Training data for the Galaxy tutorial on RNA-seq &amp; counting.</p>" * 3,
                              "related_identifiers": [{"identifier": "https://training.galaxyproject.org/topics/transcriptomics/"}]},
                 "files": [{"key": "GSM461177_1.fastqsanger", "size": 14e8, "links": {"self": "https://zenodo.org/f/1"}},
                           {"key": "counts.tabular", "size": 3e6, "links": {"self": "https://zenodo.org/f/2"}}]}
ZENODO_SEARCH = {"id": 2, "doi": "10.5281/zenodo.2", "links": {"self_html": "https://zenodo.org/records/2"}, "stats": {"downloads": 900},
                 "metadata": {"title": "Yeast RNA-seq counts for teaching", "license": {"id": "cc0-1.0"},
                              "description": "Gene counts from yeast RNA-seq for a differential expression lesson. " * 3},
                 "files": [{"key": "counts.csv.gz", "size": 2e6, "links": {"self": "https://zenodo.org/f/3"}}]}
ZENODO_OFF_TOPIC = {"id": 3, "links": {"self_html": "https://zenodo.org/records/3"}, "stats": {"downloads": 900},
                    "metadata": {"title": "Election survey of 2020", "license": {"id": "cc0-1.0"},
                                 "description": "Census and election survey answers. " * 6},
                    "files": [{"key": "survey.csv", "size": 1e6, "links": {"self": "https://zenodo.org/f/4"}}]}


def test_harvesting_maps_each_source_and_keeps_only_what_passes(monkeypatch):
    monkeypatch.setattr(datasets.time, "sleep", lambda *_: None)
    s = _Session()
    z = datasets.harvest_zenodo(s, galaxy_max=25)
    g = {r["id"]: r for r in z}
    gal = g["zenodo-6457007"]
    assert gal["source"].endswith("Galaxy Training Network") and gal["curated"] and gal["level"] == "beginner"
    assert "<p>" not in gal["about"] and "&amp;" not in gal["about"]                     # plain text only
    assert gal["formats"] == ["fastqsanger", "tabular"] and gal["size_mb"] == 1403.0 and gal["starter_mb"] == 3.0
    assert gal["tutorial"].startswith("https://training.galaxyproject.org") and gal["download"] == ""
    assert "zenodo-2" in g and "zenodo-3" not in g                                       # the off-topic hit is dropped
    assert g["zenodo-2"]["download"] == "https://zenodo.org/f/3" and g["zenodo-2"]["formats"] == ["csv"]
    geo = datasets.harvest_geo(s)
    assert len(geo) == 1 and geo[0]["download"] == ("https://ftp.ncbi.nlm.nih.gov/geo/datasets/GDS4nnn/GDS4378/soft/"
                                                    "GDS4378.soft.gz")
    assert geo[0]["field"] == "Plants & agriculture" and geo[0]["size_mb"] == 2.5 and "<b>" not in geo[0]["title"]
    om = datasets.harvest_openml(s)
    assert om[0]["id"] == "openml-61" and om[0]["license"] == "Public domain" and om[0]["level"] == "beginner"
    for r in [gal, g["zenodo-2"], geo[0], om[0]]:
        assert datasets.accept(r) == [], (r["id"], datasets.accept(r))


def test_build_merges_the_core_with_the_harvest_and_drops_dead_core_links(monkeypatch, tmp_path):
    core = tmp_path / "core.json"
    core.write_text(json.dumps({"datasets": [{**GOOD, "id": "alive"}, {**GOOD, "id": "dead", "title": "Gone",
                                                                     "download": "https://example.org/dead"}]}))
    monkeypatch.setattr(datasets, "CORE", core)
    monkeypatch.setattr(datasets, "_url_alive", lambda s, url: "dead" not in url)
    monkeypatch.setattr(datasets, "harvest_zenodo", lambda s: [{**GOOD, "id": "zenodo-9", "title": "Harvested one"},
                                                               {**GOOD, "id": "zenodo-10", "title": "Bad", "license": ""}])
    monkeypatch.setattr(datasets, "harvest_geo", lambda s: [])
    monkeypatch.setattr(datasets, "harvest_openml", lambda s: (_ for _ in ()).throw(RuntimeError("down")))
    out = datasets.build(date(2026, 10, 20), session=object())
    assert [d["id"] for d in out["datasets"]] == ["alive", "zenodo-9"] and out["version"] == "2026-10-20"
    assert out["datasets"][0]["core"] is True and out["datasets"][0]["checked"] == "2026-10-20"


ITEMS = [datasets.clean_item({**GOOD, "id": "a", "title": "Single-cell blood cells", "field": "Biology & genomics",
                              "skills": ["Single-cell RNA-seq", "Scanpy"], "level": "beginner"}),
         datasets.clean_item({**GOOD, "id": "b", "title": "Galaxy images", "field": "Physics & astronomy",
                              "skills": ["Deep learning"], "level": "advanced", "license": "cc-by-nc-4.0"}),
         datasets.clean_item({**GOOD, "id": "c", "title": "Ocean temperatures", "field": "Earth & climate",
                              "skills": [], "level": "intermediate", "core": True, "uses": 0})]


def test_ranking_puts_your_field_and_rising_skills_first():
    r = datasets.rank(ITEMS, {"single-cell": 1.0}, ["scanpy"])
    assert [d["id"] for d in r["items"]][0] == "a" and r["items"][0]["for"] == ["Scanpy"]
    assert [d["id"] for d in datasets.rank(ITEMS, {"single-cell": 1.0}, [], "for you")["items"]] == ["a"]
    assert [d["id"] for d in datasets.rank(ITEMS, {}, [], "Earth & climate")["items"]] == ["c"]
    hid = datasets.rank(ITEMS, {}, [], "", {"a": -1, "c": 1})
    assert hid["hidden"] == 1 and hid["items"][0]["id"] == "c" and hid["items"][0]["vote"] == 1
    assert ITEMS[1]["nc"] is True
    assert datasets.clean_item({**GOOD, "license": "proprietary"}) is None
    assert datasets.clean_item({**GOOD, "url": "http://x.org", "download": ""}) is None
    assert [datasets.size_text(x) for x in (0, 0.4, 7.4, 999.6, 1500, 2000)] == ["", "under 1 MB", "7 MB", "1000 MB",
                                                                                  "1.5 GB", "2 GB"]


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_reads_and_ranks_the_same():
    shipped = json.loads((ROOT / "src/mygeeky/data/datasets.json").read_text())
    raw = [GOOD, {**GOOD, "license": "cc-by-nc-sa-4.0", "id": "n"}, {**GOOD, "license": "nope"}, {"title": 3},
           {**GOOD, "url": "javascript:x", "download": ""}, {**GOOD, "size_mb": -1, "uses": 2.5, "skills": "x"}]
    weights = {"genom": 0.8, "single-cell": 1.0, "climate": 0.5}
    said = phone.run("""
import { clean, cleanItem, licenceOk, rank, sizeText } from './lib/datasets.ts';
const items = clean(INPUT.shipped).datasets;
out({ items, raw: INPUT.raw.map(cleanItem), lic: INPUT.lic.map(licenceOk), sizes: INPUT.sizes.map(sizeText),
      ranks: INPUT.fields.map((f: string) => rank(items, INPUT.weights, INPUT.wanted, f, INPUT.votes)) });
""", {"shipped": shipped, "raw": raw, "weights": weights, "wanted": ["Scanpy", "Machine learning"],
      "votes": {shipped["datasets"][0]["id"]: -1}, "fields": ["", "for you", "Earth & climate"],
      "lic": ["cc-by-4.0", "CC0-1.0", "cc-by-nd-4.0", "Public domain", "", "mit"], "sizes": [0, 0.4, 7.4, 1500, 2000]})
    items = datasets.clean(shipped)["datasets"]
    assert said["items"] == json.loads(json.dumps(items))
    assert said["raw"] == json.loads(json.dumps([datasets.clean_item(r) for r in raw]))
    assert said["lic"] == [list(datasets.licence_ok(x)) for x in ["cc-by-4.0", "CC0-1.0", "cc-by-nd-4.0", "Public domain", "", "mit"]]
    assert said["sizes"] == [datasets.size_text(x) for x in [0, 0.4, 7.4, 1500, 2000]]
    for f, got in zip(["", "for you", "Earth & climate"], said["ranks"]):
        want = datasets.rank(items, weights, ["Scanpy", "Machine learning"], f, {shipped["datasets"][0]["id"]: -1})
        assert json.loads(json.dumps(want)) == got, f


# --------------------------------------------------------------------------- 🆕 the radar
ZEN_NEW = {"hits": {"hits": [
    {"id": 11, "created": "2026-10-19T10:00:00", "links": {"self_html": "https://zenodo.org/records/11"},
     "metadata": {"title": "Single-cell RNA-seq of mouse liver", "publication_date": "2026-10-19",
                  "license": {"id": "cc-by-4.0"}, "description": "<p>Counts from single-cell RNA-seq of 9 livers by G&uuml;rhan &amp; Ng &#8211; v2.</p>"},
     "files": [{"key": "counts.h5ad", "size": 3e8}]},
    {"id": 12, "links": {"self_html": "https://zenodo.org/records/12"},
     "metadata": {"title": "Regulation of artificial intelligence", "publication_date": "2026-10-19",
                  "license": {"id": "cc-by-4.0"}, "description": "A law paper."}, "files": []}]}}
GEO_NEW = {"1": {"accession": "GSE300001", "title": "Single-cell RNA-seq of human PBMC after vaccination",
                 "summary": "We profiled 50,000 cells.", "taxon": "Homo sapiens", "n_samples": "12",
                 "gdstype": "Expression profiling by high throughput sequencing", "pdat": "2026/10/18"},
           "2": {"accession": "GSE300002", "title": "Single-cell RNA-seq of human PBMC after vaccination",
                 "summary": "SubSeries.", "taxon": "Homo sapiens", "n_samples": "6", "pdat": "2026/10/18"},
           "3": {"accession": "GDS1", "title": "not a series"}}
FIG_NEW = {"id": 77, "title": "VasQ matrix for single-cell RNA-seq", "url_public_html": "https://figshare.com/articles/dataset/x/77",
           "published_date": "2026-10-20T16:23:19Z", "license": {"name": "CC BY 4.0"},
           "description": "<p>single-cell rna seq matrix and metadata</p>", "files": [{"name": "m.npz", "size": 9.46e8}]}


def test_the_radar_searches_your_words_and_keeps_only_new_open_on_topic_data():
    assert datasets.radar_terms(["Single-cell  RNA-seq", "gw"], {"gwas": 1.0, "jake": 3.0, "nextflow": 0.5, "a": 2}) == \
        ["single-cell rna-seq", "gwas", "nextflow"]                            # "jake" is a name, not a topic
    found = (datasets.parse_zenodo_new(ZEN_NEW, "single-cell rna-seq")
             + datasets.parse_geo_new(GEO_NEW, ["1", "2", "3"], "single-cell rna-seq")
             + [datasets.parse_figshare_new(FIG_NEW, "single-cell rna-seq")])
    assert "<p>" not in found[0]["about"] and found[0]["formats"] == ["h5ad"] and found[0]["size_mb"] == 300.0
    st = datasets.radar_merge({}, found, "2026-10-20")
    ids = [i["id"] for i in st["items"]]
    assert "zenodo-12" not in ids                                          # off topic: the words aren't in it
    assert "geo-gse300001" in ids and "geo-gse300002" not in ids           # a SuperSeries and its part: once
    assert "figshare-77" in ids and all(i["found"] == "2026-10-20" for i in st["items"])
    r = datasets.radar_rank(st, {"pbmc": 1.0}, {}, "2026-10-20")
    assert r["items"][0]["id"] == "geo-gse300001" and r["new"] == 3 and all(i["new"] for i in r["items"])
    seen = {**st, "seen": ["geo-gse300001"]}
    assert datasets.radar_rank(seen, {}, {"zenodo-11": -1}, "2026-10-20")["hidden"] == 1
    assert [i["new"] for i in datasets.radar_rank(seen, {}, {}, "2026-10-20")["items"] if i["id"] == "geo-gse300001"] == [False]
    later = datasets.radar_merge(st, [], "2027-01-30")                     # past RADAR_KEEP_DAYS: gone
    assert later["items"] == []


def test_a_new_dataset_can_be_a_notification():
    from mygeeky import notify
    assert "datasets" in notify.ORDER and notify.TAB["datasets"] == "grow"
    c = notify.candidates("2026-10-20", datasets=[{"id": "geo-1", "title": "New PBMC data", "found": "2026-10-18"},
                                                  {"id": "old", "title": "Old", "found": "2026-09-01"}])
    assert [x["id"] for x in c] == ["dataset:geo-1"]
    assert "🗂 1 new dataset on your topics" in notify.summary(c)["body"]


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_radar_reads_merges_and_ranks_the_same():
    said = phone.run("""
import { parseZenodoNew, parseGeoNew, parseFigshareNew, radarMerge, radarRank, radarTerms } from './lib/datasets.ts';
const found = [...parseZenodoNew(INPUT.zen, 'single-cell rna-seq'), ...parseGeoNew(INPUT.geo, ['1', '2', '3'], 'single-cell rna-seq'),
               parseFigshareNew(INPUT.fig, 'single-cell rna-seq')!];
const st = radarMerge({}, found, '2026-10-20');
out({ found, st, rank: radarRank({ ...st, seen: ['geo-gse300001'] }, { pbmc: 1.0 }, { 'zenodo-11': -1 }, '2026-10-20'),
      terms: radarTerms(['Single-cell  RNA-seq', 'gw'], { gwas: 1.0, jake: 3.0, nextflow: 0.5, a: 2 }) });
""", {"zen": ZEN_NEW, "geo": GEO_NEW, "fig": FIG_NEW})
    found = (datasets.parse_zenodo_new(ZEN_NEW, "single-cell rna-seq")
             + datasets.parse_geo_new(GEO_NEW, ["1", "2", "3"], "single-cell rna-seq")
             + [datasets.parse_figshare_new(FIG_NEW, "single-cell rna-seq")])
    st = datasets.radar_merge({}, found, "2026-10-20")
    assert said["found"] == json.loads(json.dumps(found))
    assert said["st"] == json.loads(json.dumps(st))
    assert said["rank"] == json.loads(json.dumps(datasets.radar_rank({**st, "seen": ["geo-gse300001"]}, {"pbmc": 1.0},
                                                                     {"zenodo-11": -1}, "2026-10-20")))
    assert said["terms"] == datasets.radar_terms(["Single-cell  RNA-seq", "gw"], {"gwas": 1.0, "jake": 3.0, "nextflow": 0.5, "a": 2})
