# TRACE: how the maker's admin tools notice what's new

**TRACE** (Triggered Retrieval, Assessment and Corroboration Engine, `src/mygeeky/trace.py`) is how myGeeKy's maker
keeps up with AI and technology news, jobs, conferences and funding without missing the important things or wasting
DeepSeek. It runs only in the maker's Admin console, on the maker's computer. Users only ever see what the maker
accepted and published (News → What's new, Chances), checked again by their own app (`whatsnew_shape.py`,
`mobile/src/lib/whatsnew-shape.ts`).

TRACE learns only from the maker's own decisions and from public data. It never sees anything about users.

## The five steps

1. **Trigger.** Something new appears:
   - a new entry on a **feed**: a YouTube channel (`youtube.com/feeds/videos.xml?channel_id=UC…`), an arXiv category
     (through WISEP, `export.arxiv.org`) or any https RSS/Atom feed;
   - a new email in the **trigger inbox** (e.g. bioresearch3000@gmail.com) from an **allowed sender** (Google Scholar
     alerts, Google Alerts, job boards, conference lists). Mail from anyone else is counted and ignored, so nobody can
     feed TRACE by emailing the address. The inbox is read-only (`mailbox.Mailbox`), only the labels named, with an
     app password kept in the keyring (`mygeeky-trace-inbox`).
2. **Retrieve.** For news: the linked page (`scout.page`), the same story on Hacker News (Algolia search) and arXiv,
   and any other trigger telling it. For jobs, conferences and funding: the email's own text plus its first page.
3. **Assess.** DeepSeek writes a short item from what was fetched (`WRITE_SYSTEM`), or reads the listings
   (`scout.read_paste`). Everything fetched is untrusted: the prompt says so, links offered to the model are only those
   myGeeKy fetched, and any link in the answer that isn't one of them is dropped. Listings go through the scout's own
   checks (`scout.queue_listings`: title and deadline sentence on the page, a link only if the text says it).
4. **Corroborate.** A story told again (same link, or a title sharing ≥ 50% of its words) is merged into the item
   already waiting, as one more source, at no DeepSeek cost. The number of independent sites is part of the evidence.
5. **Elect.** Items wait in Review ranked by their chance of being accepted. Nothing reaches users without the maker's
   Accept and Publish.

## The statistics

| What | How | Where |
|---|---|---|
| How often to check a feed | Gamma-Poisson posting rate `(posts + 1) / (hours + 168)`; check when half a post is expected, between 1 h and 24 h | `post_rate`, `check_every` |
| A source's record | Beta(1 + accepted, 1 + rejected): mean and 95% range | `record` |
| An item's chance of acceptance | logistic model over evidence: grounded (headline words in what was fetched), corroboration (independent sites), source record, freshness (2-day half-life), own https link, duplicate | `features`, `p_accept` |
| Learning | one step of online logistic regression (rate 0.15, L2 0.01) after every news decision | `learn`, `decide` |
| Which triggers get DeepSeek | `worth = P(accept) × novelty × urgency ÷ cost`, best first; 10% of slots for sources with fewer than 5 decisions (chosen at random) | `worth`, `allocate` |
| Budget | 40 calls a day by default; automatic runs use 80%, 20% is kept for what the maker asks (Check now); what doesn't fit waits up to 3 days | `BUDGET`, `run` |
| What's rising | a topic's mentions today against its 7-day mean: ratio and Poisson z-score; rising when ratio ≥ 2 and z ≥ 2 | `rising` |
| Can the score be trusted | predicted against actual acceptance in 10 bins, and the weighted mean gap | `calibration` |
| Urgency | news: 1; a listing: 1 + 1/max(1, days left ÷ 14), 0 under 3 days | `urgency` |

Starting weights: bias −0.4, grounded 1.2, corroboration 0.6, source 1.6, fresh 0.4, linked 0.5, duplicate −2.5.

## What the maker sees

The Admin console (desktop, `gui/qt_panel.py` + `gui/trace_ui.py`):

- **Dashboard → TRACE · this week**: from trigger to published; sources with their 95% ranges; what's rising; calibration;
  what was accepted each week by kind; DeepSeek calls per accepted item; deadlines coming up; how fast items reach users.
- **Review**: news items with their sources, checks and chance of acceptance; Accept / Reject teach the model and the
  source's record.
- **Triggers**: the trigger inbox (address, labels, app password, Check now), allowed senders, feeds (with their posting
  rate and next check), the daily budget, and what each latest trigger led to.
- **Publish**: accepted news goes into curated.json's `whatsnew` list with the other accepted items, in one commit, with
  each item's link site shown first.

The phone shows an overview only (`admin_summary.json`, counts with no names or emails, `mobile/src/lib/admin.ts`).

## How it is checked

`tests/test_trace.py` runs TRACE against fake feeds, a fake inbox and a fake DeepSeek: a new video becomes one checked
item, a made-up link never gets in, the same story corroborates for free, only allowed senders count, the budget holds
and what's left waits, decisions teach the model and the source, accepted news is published into What's new, and the
statistics on their own (rates, records, learning, allocation, rising, calibration). `tests/test_whatsnew.py` checks the
published list is read the same way on both apps; `tests/test_admin_console.py` checks the console.

Measures to watch as it runs (all on the Dashboard): precision (share of items the maker accepts), calibration error
(below 10 points: its ranking is worth following), DeepSeek calls per accepted item, and items reported as fake after
publishing (Chances' Report button).
