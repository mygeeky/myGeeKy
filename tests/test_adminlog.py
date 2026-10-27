"""The maker's admin actions made on the phone: applied once, in order, never over a later undo."""
from mygeeky import admin, adminlog, scout
from mygeeky.config import MyGeekyConfig
from mygeeky.files import append_jsonl, read_jsonl

MAKER = MyGeekyConfig(github_username="AlsammanAlsamman")


def _people(**status):
    admin.save({"people": {login: {"login": login, "status": st} for login, st in status.items()}})


def test_phone_actions_are_applied_once_and_in_order():
    _people(ccsosa="new", vegerot="new")
    append_jsonl(adminlog.ACTIONS_FILE, {"id": "phone-0001", "at": "2026-10-16T10:00:00+00:00", "kind": "prospect",
                                         "login": "ccsosa", "status": "invited"})
    append_jsonl(adminlog.ACTIONS_FILE, {"id": "phone-0002", "at": "2026-10-16T10:01:00+00:00", "kind": "prospect",
                                         "login": "vegerot", "status": "declined"})
    assert adminlog.apply(MAKER) == 2
    people = admin.load()["people"]
    assert people["ccsosa"]["status"] == "invited" and people["ccsosa"]["invited_at"].startswith("2026-10-16T10:00")
    assert people["vegerot"]["status"] == "declined"
    # an undo made later on a computer is not overwritten by replaying the phone's older action
    admin.mark("ccsosa", "new")
    assert adminlog.apply(MAKER) == 0
    assert admin.load()["people"]["ccsosa"]["status"] == "new"
    assert {r["id"] for r in read_jsonl(adminlog.APPLIED_FILE)} == {"phone-0001", "phone-0002"}


def test_only_the_maker_applies_and_odd_lines_are_skipped():
    _people(ccsosa="new")
    append_jsonl(adminlog.ACTIONS_FILE, {"id": "phone-0003", "kind": "prospect", "login": "ccsosa", "status": "invited"})
    assert adminlog.apply(MyGeekyConfig(github_username="someone-else")) == 0
    assert admin.load()["people"]["ccsosa"]["status"] == "new"
    for bad in ({"id": "x", "kind": "prospect", "login": "ccsosa", "status": "invited"},          # id too short
                {"id": "phone-0004", "kind": "prospect", "login": "bad login!", "status": "invited"},
                {"id": "phone-0005", "kind": "prospect", "login": "ccsosa", "status": "joined"},   # not the phone's to set
                {"id": "phone-0006", "kind": "wire-money", "status": "new"}):
        append_jsonl(adminlog.ACTIONS_FILE, bad)
    adminlog.apply(MAKER)
    assert admin.load()["people"]["ccsosa"]["status"] == "invited"       # phone-0003, and nothing else


def test_a_listing_reviewed_on_the_phone_is_accepted_or_rejected_here():
    item = {"id": "job-abc", "title": "Postdoc in GWAS", "url": "https://example.org/job", "org": "Lab",
            "deadline": "2099-01-01", "type": "postdoc", "summary": "A postdoc.", "keywords": ["gwas"]}
    scout.save({"candidates": {"job-abc": {"kind": "jobs", "item": item, "score": 0.9, "checks": [], "status": "new"},
                               "job-def": {"kind": "jobs", "item": {**item, "id": "job-def"}, "score": 0.5,
                                           "checks": [], "status": "new"}},
                "rejected": []})
    append_jsonl(adminlog.ACTIONS_FILE, {"id": "phone-0010", "at": "2026-10-16T11:00:00+00:00", "kind": "listing",
                                         "id_listing": "job-abc", "status": "accepted"})
    append_jsonl(adminlog.ACTIONS_FILE, {"id": "phone-0011", "at": "2026-10-16T11:01:00+00:00", "kind": "listing",
                                         "id_listing": "job-def", "status": "rejected"})
    assert adminlog.apply(MAKER) == 2
    state = scout.load()
    assert state["candidates"]["job-abc"]["status"] == "accepted"
    assert state["candidates"]["job-def"]["status"] == "rejected" and "job-def" in state["rejected"]


def test_a_phone_action_changes_a_listings_status_never_its_link():
    item = {"id": "job-abc", "title": "Postdoc in GWAS", "url": "https://example.org/job", "org": "Lab",
            "deadline": "2099-01-01", "type": "postdoc", "summary": "A postdoc.", "keywords": ["gwas"]}
    scout.save({"candidates": {"job-abc": {"kind": "jobs", "item": item, "score": 0.9, "checks": [], "status": "new"}},
                "rejected": []})
    append_jsonl(adminlog.ACTIONS_FILE, {"id": "phone-0020", "at": "2026-10-16T11:00:00+00:00", "kind": "listing",
                                         "id_listing": "job-abc", "status": "accepted",
                                         "item": {"url": "https://phish.example/apply"}})
    adminlog.apply(MAKER)
    c = scout.load()["candidates"]["job-abc"]
    assert c["status"] == "accepted" and c["item"]["url"] == "https://example.org/job" and not c.get("edited")
