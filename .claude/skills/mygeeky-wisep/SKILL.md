---
name: mygeeky-wisep
description: Use for ANY code that calls an open database or repository over the network (OpenAlex, Crossref, arXiv, bioRxiv/medRxiv, Zenodo, NCBI GEO/E-utilities, Figshare, Hugging Face, or a new one), on the computer or the phone, and when changing WISEP itself (src/mygeeky/wisep.py, mobile/src/lib/wisep.ts), its budgets, its evaluation (docs/WISEP.md, tools/wisep_bench.py, .github/workflows/wisep.yml) or the admin view of it. WISEP decides when and how much myGeeKy may ask; nothing calls these sources around it.
---

# WISEP: every call to an open source goes through it

WISEP (Wisely, a Systematic Statistically adapted system for API calling) keeps one cache of answers, estimates how
often each answer really changes, learns which pages the person opens and when, and asks a source only when a fresh
answer is worth it -- within a daily budget per source, spaced, backing off when a source is busy, and spending what's
left of the budget in the evening on what will be wanted tomorrow. It runs on the device; nothing about the person
leaves it.

## The rules for code

1. **Never call a managed source directly.** On the computer use `wisep.session(page, force=...)` (a drop-in
   `requests.Session`) or `wisep.get(url, params, page=...)`; on the phone `wiseFetch(url, { page, force })`.
   A plain `requests.get` / `fetchT` to `api.openalex.org` (or any host in `SOURCES`) is a bug.
2. **Name the page** the answer is for, with the names in `PAGES` (`you:cited`, `world:papers`, `grow:wins`,
   `grow:paths`, `grow:data:new`, `repos:rising`, `you:model`, `you:admin`, `setup`, `you:whois`). That's how what
   the person opens decides what stays fresh. A new page: add it to `PAGES` on both apps.
3. **`force` only when the person asked** (a Refresh button, a search they typed). It is honoured but counted, up to
   120% of the day's budget.
4. **Ask small:** `select=` only the fields used, batch ids (`filter=id:a|b|c`, up to 50; `author.id:a|b|c` for
   people), `per-page` no bigger than needed.
5. **A new source:** add it to `SOURCES` on both apps with a daily budget well under its published limit and the
   gap between calls it asks for (arXiv: 3 s; NCBI: 3 a second without a key; Zenodo: 30 a minute for guests).
6. **A new kind of answer:** if `kind_of` can't tell it from the URL, give it a kind (`search`, `citations`,
   `entity`, `static`) by its real rhythm: the prior hours between changes, never sooner than, always by.
7. **Same rules on both apps.** `decide`, `care`, `threshold`, `change_rate`, `p_changed`, `kind_of`, `source_of`,
   `PAGES` are pure and identical; `tests/test_wisep.py` runs the phone's on the same inputs. Python's `sum()`
   rounds differently from JavaScript's adding: add floats one by one where both must agree.

## The decision, in one line

`worth = (1 - exp(-rate * age)) * care(page, hour)`; fetch when `worth >= threshold(used, budget, time of day)`.
`rate = (changes + 1) / (hours watched + prior hours)`. `care` = how often the page is opened against the most-opened
page, and whether its opens fall in the next three hours (opens fade with a two-week half-life; an unknown page is
0.5, a never-opened one 0.1). The bar is 0.15 while spending is on pace and rises as the day's budget runs ahead.
Hard limits: never sooner than a kind's minimum age, always once it's older than its maximum (budget allowing), never
when the source asked us to wait (429/503, Retry-After), a kept answer served when the source is down.

## It tunes itself, and takes over from old timers

- `tune()` (daily, from the hourly look) turns each kind's prior into what this device watched (`tuned_prior`: at
  least 5 answers and 14 days, kept within the kind's limits). Don't hand-tune priors per user; change `KINDS` only
  for a better starting point.
- A module's own "is it time?" check goes through `wisep.timer_due(own_due, age_hours)` (phone: `timerDue`). Until
  `proven_by` says so (14 days, 100 answers, 40% from the cache, failures under 15%) the module's timer leads; after,
  a refresh may run every half hour and WISEP decides. ⚙ / You → Settings → How myGeeKy asks the internet: Auto / Always / Never (`set_mode`), per user. A new
  module that refreshes on a timer from a WISEP source should use `timer_due` too.
- GitHub isn't gated by WISEP (its own cache and per-person limit) but is counted beside it in Admin.

## Checking it

`docs/WISEP.md` is the evaluation plan. In short:
- `pytest tests/test_wisep.py`: the rules, the store, backing off, the top-up, the phone's agreement, and the
  simulation (a month, 20 answers changing at their own rates, pages opened on a daily rhythm): WISEP must make
  under half the calls of fixed 6-hourly timers with stale views no more than 5 points higher.
- `python tools/wisep_bench.py [--live]`: decision speed, the store's size and write cost, the simulation over
  several seeds, and (live) two identical OpenAlex asks reaching the network once.
- `.github/workflows/wisep.yml` runs both on Windows, macOS and Linux.
- Every user sees their own WISEP in ⚙ / You → Settings → How myGeeKy asks the internet (gui/wisep_ui.py,
  components/wisep-settings.tsx): today's calls, what its cache answered, GitHub beside it, the pages learned, the
  takeover progress, the switch and Forget what it learned. Admin only points to it.
