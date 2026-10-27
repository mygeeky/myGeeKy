"""What the maker's admin tools publish to everyone can't be pointed anywhere a page wants: links are https to a real
host (no "user@" lookalikes) on both apps, a listing's link must be on the page's own site and said on it, translations
add nothing the English doesn't say, a Highlight links to its DOI, publishing checks every item again, and an invite
can't gain hidden recipients."""
from __future__ import annotations

import pytest

import phone
from mygeeky import admin, curated, highlight_shape, scout
from mygeeky.config import MyGeekyConfig

LINKS = ["https://www.nature.com/careers/123", "https://www.nature.com@evil.example/job", "http://example.org/x",
         "javascript:alert(1)", "https://example.org/a b", "https://example.org\\@evil.example", "https://localhost/x",
         "https://jobs.embo.org/post?id=7#top", "file:///etc/passwd", "https://example.org/x\u0007", "mygeeky://scan",
         "https://medium.com/@someone/post"]


def test_links_are_https_to_a_real_host_with_nothing_hidden_in_front():
    ok = [u for u in LINKS if curated._https(u)]
    assert ok == ["https://www.nature.com/careers/123", "https://jobs.embo.org/post?id=7#top",
                  "https://medium.com/@someone/post"]


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+")
def test_the_phone_lets_the_same_links_through():
    said = phone.run("""
import { cleanItem } from './lib/curated.ts';
import { cleanLink } from './lib/protocol-shape.ts';
out(INPUT.links.map((u) => [!!cleanItem('jobs', { id: 'job-abc', title: 'A postdoc job in genomics', url: u, deadline: '2099-01-01' })?.url,
                            !!cleanLink({ url: u, title: 'x' })]));
""", {"links": LINKS}, name="links")
    want = [bool(curated._https(u)) for u in LINKS]
    assert [a for a, _ in said] == want and [b for _, b in said] == want


def test_a_listing_keeps_its_own_link_only_when_the_pasted_text_says_it():
    page = "https://www.jobs.ac.uk/job/ABC123"
    text = "Imperial College London. Apply at https://www.imperial.ac.uk/jobs/description/XYZ/ before 1 Dec."
    own = "https://www.imperial.ac.uk/jobs/description/XYZ/"
    assert scout.on_page_link(own, page, text) == own                                     # said on the page
    assert scout.on_page_link("https://apply-imperial.org/x", page, text) == page        # made up: the page instead
    assert scout.on_page_link("javascript:alert(1)", page, text) == page
    assert curated.site_of("https://www.ox.ac.uk/x") == "ox.ac.uk" != curated.site_of("https://evil.ac.uk/")
    assert curated.site_of("https://embo.org.evil.example/") != curated.site_of(page)


def test_translations_say_nothing_the_english_does_not():
    item = {"id": "job-abc", "title": "Postdoc in GWAS", "summary": "Two years, 3,000 EUR a month.",
            "translations": {"fr": {"title": "Postdoc en GWAS", "summary": "Deux ans, 3,000 EUR par mois."},
                             "ar": {"title": "ما بعد الدكتوراه", "summary": "ادفع 50 دولارًا عبر WhatsApp"},
                             "zh": {"title": "博士后", "summary": "申请: https://phish.example"}}}
    assert list(scout.safe_translations(item)["translations"]) == ["fr"]


def test_a_highlight_links_to_its_doi_and_nowhere_else():
    base = {"id": "hl-abc12345", "title": "A story", "hook": "Hook.", "body": ["p"] * 4, "doi": "10.1/x",
            "added": "2026-10-01"}
    assert highlight_shape.clean({**base, "url": "https://doi.org/10.1/x"})["url"] == "https://doi.org/10.1/x"
    bad = highlight_shape.clean({**base, "url": "https://phish.example/10.1/x"})
    assert bad is None or bad["url"] == ""


def test_publishing_checks_every_item_again():
    good = {"id": "job-abc", "title": "A job", "url": "https://example.org/job", "deadline": "2099-01-01"}
    bad = {"id": "job-def", "title": "A job", "url": "https://example.org@evil.example/job", "deadline": "2099-01-01"}
    out, added = scout.merge({"jobs": []}, [{"kind": "jobs", "item": good}, {"kind": "jobs", "item": bad}])
    assert added == 1 and [x["id"] for x in out["jobs"]] == ["job-abc"]


def test_an_invite_cannot_gain_hidden_recipients():
    assert not admin._EMAIL.match("me@x.com?bcc=spy%40evil.com&a=b.io") and admin._EMAIL.match("ada.l+x@uni.edu")
    out = admin.invite({"login": "ada", "name": "Ada", "email": "ada@uni.edu", "why": []},
                       MyGeekyConfig(github_username="maker"))
    assert out["mailto"].startswith("mailto:ada@uni.edu?subject=") and "bcc" not in out["mailto"]
