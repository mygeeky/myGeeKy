"""What works without a GitHub account, and what honestly cannot.

Two different requirements used to be gated behind one flag, `cfg.github_username`:

  * parts that read YOUR ACCOUNT -- who follows you, who you follow, your own repos. No account, nothing
    to compute. Follow-back suggestions, Activity, Signals, Collab.
  * parts that only need A FIELD -- Market and Repos-to-improve search PUBLIC repos against your own
    keywords, CV and publications, and never look your account up at all. The domain half of People is
    the same: people found by searching your field.

The second group was locked for users with no GitHub -- a feature denied for a reason it never had. These
tests hold the line both ways: the field parts must run without an account, and the account parts must
still refuse rather than return a number that means nothing.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from mygeeky.config import MyGeekyConfig, profile_ready
from mygeeky.gui import app as logic


# --------------------------------------------------------------------------- what counts as a profile
def test_keywords_alone_are_a_profile():
    assert profile_ready(MyGeekyConfig(keywords=["metagenomics", "snakemake"]))
    assert profile_ready(MyGeekyConfig(orcid_id="0000-0002-1825-0097"))
    assert profile_ready(MyGeekyConfig(topics=["bioinformatics"]))
    assert not profile_ready(MyGeekyConfig())


# --------------------------------------------------------------------------- the field-only parts run
@pytest.mark.parametrize("call, said", [
    (logic.refresh_market, "rows"),
    (logic.refresh_contributions, None),
    (logic.refresh_suggestions, None),
])
def test_field_parts_do_not_ask_for_a_github_username(monkeypatch, call, said):
    """They may fail for other reasons (no network), but never with "run init first"."""
    cfg = MyGeekyConfig(keywords=["metagenomics"])
    monkeypatch.setattr(logic, "_run_market", lambda *a, **k: [], raising=False)
    monkeypatch.setattr("mygeeky.cli._run_market", lambda *a, **k: [], raising=False)
    monkeypatch.setattr("mygeeky.cli._run_contribute", lambda *a, **k: [], raising=False)
    monkeypatch.setattr(logic, "_run_contribute", lambda *a, **k: [], raising=False)
    monkeypatch.setattr(logic, "_run_suggestions", lambda *a, **k: {"followback": [],
                                                                   "domain_highlights": []}, raising=False)
    out = call(cfg)
    error = out.get("error", "") if isinstance(out, dict) else ""
    assert "init" not in error, f"{call.__name__} still asks for a GitHub account: {error!r}"


def test_field_parts_still_refuse_with_no_profile_at_all():
    blank = MyGeekyConfig()
    assert "init" in logic.refresh_market(blank)["error"]
    assert "init" in logic.refresh_contributions(blank)["error"]
    assert "init" in logic.refresh_suggestions(blank)["error"]


# --------------------------------------------------------------------------- the self profile
def test_self_profile_without_a_username_never_calls_github():
    """An empty username must not be sent to /users/ -- it is a wasted request that always 404s."""
    from mygeeky.profile_builder import build_profile_from_github

    class Loud:
        def get_user(self, username):
            raise AssertionError(f"asked GitHub about {username!r}")

    assert build_profile_from_github(Loud(), "") is None


def test_self_profile_falls_back_to_cv_keywords_and_papers(monkeypatch):
    from mygeeky import cli
    cfg = MyGeekyConfig(keywords=["metagenomics", "dada2"])
    monkeypatch.setattr(cli, "_load_cv_text", lambda: "amplicon sequencing of soil")
    monkeypatch.setattr("mygeeky.scholar.scholar_corpus", lambda p: "16S rRNA community profiling")
    monkeypatch.setattr("mygeeky.scholar.load_scholar_profile", lambda: None)

    class Loud:
        def get_user(self, username):
            raise AssertionError("should not be reached")

    profile = cli._self_profile(Loud(), cfg)
    assert profile.username == ""
    for word in ("metagenomics", "amplicon", "rRNA"):
        assert word in profile.corpus


# --------------------------------------------------------------------------- the two halves of People
def _run_suggestions(monkeypatch, cfg, scored_people):
    """Drive the real pipeline with a fake GitHub, and return its two lists."""
    from mygeeky import cli

    class Fake:
        def __init__(self):
            self.asked_following = []

        def get_user(self, username):
            return {"login": username, "bio": f"{username} works on metagenomics", "public_repos": 9,
                    "followers": 40, "following": 20, "type": "User"}

        def list_repos(self, username, max_pages=1):
            return [{"full_name": f"{username}/tool", "stargazers_count": 5, "topics": ["metagenomics"],
                     "description": "metagenomics pipeline", "language": "Python",
                     "pushed_at": "2026-10-01T00:00:00Z", "created_at": "2025-01-01T00:00:00Z",
                     "fork": False, "archived": False}]

        def list_following(self, username, max_pages=None):
            self.asked_following.append(username)
            return []

        def list_followers(self, *a, **k):
            return []

        def list_stargazers(self, *a, **k):
            return []

        def search_users(self, *a, **k):
            return []

        def search_repositories(self, *a, **k):
            return [{"full_name": "lab/metagenomics-tool", "stargazers_count": 300,
                     "owner": {"login": p, "type": "User"}} for p in scored_people]

        def list_contributors(self, *a, **k):
            return [{"login": p, "type": "User"} for p in scored_people]

        def _get(self, *a, **k):
            return SimpleNamespace(status_code=404, json=lambda: {})

    fake = Fake()
    monkeypatch.setattr(cli, "_client_for", lambda c: fake)
    monkeypatch.setattr(cli, "_apply_activity_qc", lambda client, c, rows, n, cache: rows[:n])
    monkeypatch.setattr(cli, "_annotate_papers", lambda *a, **k: None)
    monkeypatch.setattr("mygeeky.scholar.load_scholar_profile", lambda: None)
    monkeypatch.setattr("mygeeky.scholar.scholar_corpus", lambda p: "")
    monkeypatch.setattr("mygeeky.scholar.scholar_keyword_counts", lambda p: {})
    return cli._run_suggestions(cfg), fake


def test_without_an_account_the_domain_list_fills_and_followback_is_empty(monkeypatch):
    cfg = MyGeekyConfig(keywords=["metagenomics"], include_own_stargazers=True)
    out, fake = _run_suggestions(monkeypatch, cfg, ["ada", "linus"])
    assert out["followback"] == [], "there is no account to score a follow-back against"
    assert out["domain_highlights"], "people found by searching the field need no account"
    assert fake.asked_following == [], "asked GitHub who an account-less user follows"


def test_with_an_account_both_lists_are_computed(monkeypatch):
    cfg = MyGeekyConfig(github_username="me", keywords=["metagenomics"])
    out, fake = _run_suggestions(monkeypatch, cfg, ["ada", "linus"])
    assert fake.asked_following == ["me"]
    assert out["domain_highlights"]


# --------------------------------------------------------------------------- the account-only parts
def test_the_parts_that_read_your_account_still_say_no():
    cfg = MyGeekyConfig(keywords=["metagenomics"])          # a field, but no account
    assert logic.get_activity(cfg)["events"] == []
    assert not logic.phone_pairing(cfg)["ok"]
    assert logic.get_token_warnings(cfg) == []


def test_syncing_to_the_phone_is_the_one_thing_a_keyword_profile_cannot_buy():
    """The model itself is a local file and needs nothing. Carrying it to a second device goes through
    your own private GitHub repo, which is why an account is needed for that and nothing else."""
    import inspect

    from mygeeky import sync
    assert "sync_repo" in inspect.getsource(sync.push) or "repo" in inspect.getsource(sync.push)


# --------------------------------------------------------------------------- the copy must not under-sell
def test_no_doc_still_claims_the_pre_chances_list():
    """Prose that enumerates "what works without GitHub" is a dependency on every later feature. These
    four files each carried a list written before Chances and Grow existed."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    stale = "News, Research, AI models and Launches"
    for rel in ("README.md", "docs/GUIDE.md", "src/mygeeky/cli.py", "src/mygeeky/gui/setup_wizard.py"):
        said = (root / rel).read_text(encoding="utf-8")
        assert stale not in said, f"{rel} still lists the pre-Chances capabilities"
