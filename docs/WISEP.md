# WISEP: how it decides, and how we check it

**WISEP** (Wisely, a Systematic Statistically adapted system for API calling) is the one gateway every call to an
open database goes through, on the computer (`src/mygeeky/wisep.py`) and the phone (`mobile/src/lib/wisep.ts`). It
runs for every user, on their own device (each has their own cache, budget and what it learned; they see it all in
⚙ / You → Settings → How myGeeKy asks the internet, can switch it and can make it forget). It
keeps one cache of answers, estimates how often each answer really changes, learns which pages you open and when, and
asks a source only when a fresh answer is worth it: within a daily budget per source, spaced, backing off when a
source is busy, and spending what's left of the day's budget in the evening on what you'll want tomorrow. It runs on
your device; nothing about you leaves it. The rules for code that calls a source are in the `mygeeky-wisep` skill.

## Why

Before WISEP (2026-10-20), OpenAlex was called from 8 desktop modules (29 places) and 7 phone files (24 places), each
with its own refresh rule (16 separate timers on the desktop). Nothing counted the total, nothing learned what was
opened, and the requests didn't join OpenAlex's polite pool. A refresh asked again for answers that hadn't changed in
weeks, and answers nobody looked at were kept fresh all the same.

## How it decides

    rate  = (changes + 1) / (hours watched + prior hours)              # a Gamma-Poisson estimate per answer
    worth = (1 - exp(-rate * age)) * care(page, hour)                  # chance it changed x how much you care
    fetch when worth >= threshold(used today, budget, time of day)     # 0.15 on pace, rising when spending runs ahead

`care` is how often the page is opened against your most-opened page, and whether its opens fall in the next three
hours (opens fade with a two-week half-life; an unknown page counts 0.5, a never-opened one 0.1). Each kind of answer
has a prior and hard limits: a search (new or rising work) is never asked again within an hour and always after three
days; citations 6 hours / 7 days; an author or a work's counts 6 hours / 14 days; a topic or a paper's metadata 7 days
/ 90 days. A source that answers 429 or 503 rests (Retry-After, doubling); its kept answer is served meanwhile. A
refresh you press is honoured (up to 120% of the day's budget) and counted.

**The evening top-up.** From 20:00 local time, once an hour, budget left over is spent on the answers most worth
having fresh tomorrow morning (the same measure, with care taken for the morning hours), at most half of what's left
and 40 answers on the computer, 15 on the phone.

**It tunes itself.** Each kind's prior (the hours between changes it assumes) starts from the table above. Once a
device has watched at least 5 answers of a kind for 14 days in all, the prior becomes what was actually seen there
(pooled changes over hours watched, `tuned_prior`), kept between the kind's "never sooner" and four times its "always
by", and recomputed once a day. Admin shows what was learned ("search every ~42 h").

**It takes over from the old timers once proven.** Cited by, Papers' rising work and the dataset radar each kept
their own "once a day" timer. After 14 days of use, 100 answers given, at least 40% of them from the cache and failures
under 15% of the asks (`proven_by`), those timers stop gating: a refresh may run every half hour and WISEP alone
decides which answers are worth asking for (`timer_due`). ⚙ Settings → How myGeeKy asks the internet switches this
between Auto (once proven), Always and Never, for each user on their own device, and shows how far it is ("6 of 14 days, 48 of 100 answers, 55% from the cache").

## Daily budgets (well under each source's published limits)

| Source | Budget a day | Gap between calls |
|---|---|---|
| OpenAlex | 1,500 | 0.12 s |
| Crossref | 500 | 0.2 s |
| arXiv | 300 | 3.1 s (arXiv asks for 3 s) |
| bioRxiv / medRxiv | 300 | 0.5 s |
| Zenodo | 300 | 2.1 s (30 a minute for guests) |
| NCBI E-utilities | 500 | 0.35 s (3 a second without a key) |
| Figshare | 300 | 0.3 s |
| Hugging Face | 300 | 0.2 s |

GitHub keeps its own cache (`ghcache.py`: ETags, 304s, a slow list; the phone's `lib/github.ts`) and its own limit
per person; its asks and what its cache saved are counted and shown beside WISEP's sources in Settings.

## The evaluation plan

What we measure, and the bar each must clear:

| Question | Measure | Bar | Where |
|---|---|---|---|
| Does it ask less? | calls a month, against fixed 6-hourly timers | under 50% | simulation (`tests/test_wisep.py`, `tools/wisep_bench.py`) |
| Is what you see still fresh? | share of looks showing an answer older than its last real change | no more than 5 points above timers | simulation |
| Does it learn? | pages you open often refreshed more than pages you never open; the top-up spends on the former | the test passes | `test_the_evening_top_up_...`, `test_what_you_open_...` |
| Is it polite? | backs off on 429/503, never asks a resting source, the polite-pool contact on every OpenAlex ask | the tests pass | `test_a_busy_source_...`, `test_asking_through_wisep_...` |
| Is it fast? | microseconds per decision; a cached answer's time against the network's | under 200 µs; cache in under 1 ms (network ~450 ms) | benchmark |
| Does it cost the machine much? | ms per write and per read, MB on disk for 2,000 answers, the size cap holding | under 50 ms a write; capped at 3,000 answers / 40 MB | benchmark, `Store._trim` |
| Do both apps decide alike? | the phone's rules on 60 random cases, `care` on 15, `kind_of`/`source_of` on 7 URLs | identical | `test_the_phone_decides_the_same` |
| Every operating system? | all of the above on Windows, macOS and Linux | green on all three | `.github/workflows/wisep.yml` (weekly too) |
| Android? | the phone's rules (parity test), its store capped at 300 answers, written once things settle | the parity test; a look on a phone | `lib/wisep.ts` |
| Does tuning stay sane? | a learned prior within its kind's limits, only with enough history | the tests pass | `test_priors_are_tuned_...` |
| Does it take over only when it should? | the old timers lead until 14 days / 100 answers / 40% saved / <15% failures; the switch works | the tests pass | `test_wisep_takes_over_...` |
| In real use? | today's calls per source, saved by the cache, top-up, the pages learned, the takeover progress | every user sees their own | ⚙ / You → Settings → How myGeeKy asks the internet (both apps); Admin points to it |

First numbers (Linux, Python 3.12, 2026-10-20): a decision takes ~1 µs; a write 2 ms, a read 0.008 ms; 11 MB for
2,000 answers of 5 KB; the simulation saves 85% of calls (357 against 2,400 a month) with stale views 8.2% against
6.8%; live, OpenAlex answered in 453 ms and the same ask again came from the store in 0.12 ms.

## Next

- Move the remaining sources' calls onto WISEP as they're touched (the weekly harvests in GitHub Actions stay direct:
  they run once, for everyone).
- Watch the first weeks of real tallies in Admin: the learned priors and the takeover progress; adjust PROVEN_* if
  the bar turns out too strict or too loose.
