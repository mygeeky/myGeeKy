<p align="center"><a href="https://github.com/mygeeky/myGeeKy"><img src="https://raw.githubusercontent.com/mygeeky/myGeeKy/main/src/mygeeky/gui/assets/icon_256.png" width="72" alt="myGeeKy"></a></p>

<h1 align="center">The myGeeKy guide</h1>

<p align="center"><sub>Everything in detail: every command, every setting, how the models work, and what myGeeKy will never do.<br>
New here? Start with the <a href="https://github.com/mygeeky/myGeeKy#readme">README</a> (install in 3 steps).</sub></p>

**Contents:** [How it works](#how-it-works) · [Finding people](#finding-people-mygeeky-run) ·
[Repos you could improve](#repos-you-could-improve-mygeeky-contribute) ·
[Market](#your-fields-repos-as-a-market-board-mygeeky-market) ·
[Your profile](#your-profile-cv--github--orcidopenalex--google-scholar) ·
[Sync](#use-it-from-any-computer-mygeeky-sync) ·
[Research trends](#research-trends-and-the-papers-behind-repos-mygeeky-trends) ·
[News](#news-for-your-field-mygeeky-news) ·
[Keywords](#keywords-that-mean-something-mygeeky-keywords) ·
[Learning & exploring](#it-learns-what-youre-into-and-keeps-room-to-explore) ·
[Signals](#signal-other-mygeeky-users-without-words-mygeeky-beacon) ·
[Install](#install) · [Updating](#updating) · [Token expiry](#token-expiry) ·
[Troubleshooting](#if-something-goes-wrong-on-windows) · [Everyday use](#everyday-use) ·
[Running weekly](#running-it-weekly) · [The panel](#live-glass-panel-optional-gui) ·
[All settings](#all-parameters-adjustable-or-leave-at-the-defaults) · [Safety](#safety) ·
[From scripts & AI agents](#using-mygeeky-from-an-ai-agent--script) ·
[How the learning works](#how-the-learning-works)

## How it works

GitHub's Markdown renderer strips `<script>` tags (security), so it can't
run a live JS diagram inline — the image below is a preview of a real,
animated, click-to-expand HTML/JS page that ships in this repo at
[`docs/flowchart.html`](https://github.com/mygeeky/myGeeKy/blob/main/docs/flowchart.html):

<p align="center">
  <a href="https://raw.githack.com/mygeeky/myGeeKy/main/docs/flowchart.html">
    <img src="https://raw.githubusercontent.com/mygeeky/myGeeKy/main/docs/flowchart_preview.png" width="480" alt="How myGeeKy works — click for the live interactive version">
  </a>
</p>

**[▶ Open the live interactive version](https://raw.githack.com/mygeeky/myGeeKy/main/docs/flowchart.html)**
— real vanilla JS (click any step to expand it), served straight off this
repo via [githack](https://raw.githack.com), no build step, no server.
(If that link is ever slow/unavailable: clone the repo and open
`docs/flowchart.html` directly in a browser — it's fully self-contained,
zero dependencies.)

*The pink "You follow — by hand" step is the only place a follow ever
happens — myGeeKy has no follow/unfollow code anywhere in the project; see
[Safety](#safety).*


**The four signs** on the right of the strip with the page's name: GitHub, ORCID, Saving (your private data repo)
and Beacon (Signals). Lit means on, faint means not set up, red means its access expired or stopped working: renew
it (a small reminder comes at most once a day). Click or tap one to see what it means.

## 🌱 Grow and 🎯 Chances

Two planets on the panel (and two on the phone's rings) for what comes next.

myGeeKy is for researchers who build things **at a computer**. Setup asks which fits you best
(*I mostly build software* / *I mostly analyse data* / *both*), and it only sets the starting balance of what's
suggested: your model still learns from what you open. Change it any time (`work_style` in `config.json`).

### ✨ Highlights

The last part of Grow is **Highlights**: research articles picked by myGeeKy's maker, each retold as a short science news
article -- a headline, a one-line standfirst and a few paragraphs, each with one idea: what they found, who
did it and where (and whether it was a collaboration), the problem and what came before, what they did and
with which tools, the findings and the limits. Tap a language button to read it in Arabic, French, German,
Spanish or Chinese. "Learn these tools" turns a skill from the article into a protocol, and "Read the
article" opens it. Each says whether it was written from the full article or from its abstract only. Facts
such as the team leader, institutions and journal are looked up on OpenAlex, never guessed. Highlights
arrive with the curated lists, like jobs and funding.

### What myGeeKy does not teach

**Laboratory work.** myGeeKy covers code, data, statistics, figures and pipelines. It does not give protocols,
steps, recipes, volumes, conditions or troubleshooting for anything done at a bench, and it **refuses to build
one**: type a bench technique and it says so, and says what to ask for instead.

Why: a wrong line of R wastes an afternoon; a wrong line at a bench can hurt somebody. myGeeKy has one
maintainer, can't review bench safety, can't know your lab's rules, training or containment, and can't check
what anyone actually does. That work belongs to your lab and your institution.

This is enforced in code (`src/mygeeky/safety.py`), not only in words:
- a protocol is refused if its skill or goal names a laboratory technique, reagent or instrument;
- protocol repositories, protocol journals and suppliers' method libraries are refused as sources, so none of
  their pages can become a step, a link or a quiz question — including in a protocol somebody else published;
- the same rules go into the prompts the maker's tools send.

**Analysing data an experiment produced is welcome**, and is what *From Excel to R*, *statistics for
experiments* and *images into numbers with Fiji* are for.

**🌱 Grow** has five parts:
- **🧠 How myGeeKy asks the internet** (⚙ on the computer, More → Settings on the phone): papers, citations and
  datasets come from open databases. myGeeKy keeps their answers and asks again only when a fresh one is worth it --
  when it has probably changed and you're likely to look -- within a daily budget and kindly to the databases (WISEP).
  It learns which pages you open and when, on your device only; it spends what's left of the day's budget in the
  evening on what you'll want tomorrow. Here you see today's numbers, what it learned, how far it is from deciding
  alone (Auto, Always or Never) and a button to make it forget what it learned. OpenAlex gives each network a free daily
  budget shared by everyone on it (1,000 searches without a key): it shows what's left today, and **🔑 Get a free
  OpenAlex key** gets you a budget of your own (OpenAlex emails you a link; the key works once you click it).
- **🗂️ Data**: public datasets to practise and train on, across the sciences (biology, plants, medicine,
  neuroscience, ecology, climate, chemistry, physics and astronomy, social science, machine learning). Every one
  passes the same rules: an open licence, a download with no login or application, laptop-sized (or with a named
  starter file), common formats, documented, stable, validated by its source or widely used, and no personal
  data. The list is a hand-checked core (PBMC 3k, the Palmer penguins, Mauna Loa CO2, MNIST...) plus the Galaxy
  Training Network's tutorial data and well-used datasets on Zenodo, NCBI's curated GEO DataSets and OpenML's vetted
  CC18 suite, re-checked every week. ✨ For you puts first what matches your field and teaches the skills rising
  for you; pick a field to browse the rest. Each card says what to practise, its size, format and licence, with
  ⬇ Download, the page and a tutorial when there is one. **🆕 New** is the radar: once a day myGeeKy searches, on
  your device, for public datasets that have just come out on your own keywords (or, without any, your strongest
  topics) on Zenodo, NCBI GEO's new series and Figshare. It keeps what is open, needs no login, is on topic and in
  English, marks what you haven't seen with 🆕, and can tell you in a notification (🗂 New data on your topics).
  Only the search words leave your device.
- **📈 Skills**: Rising Skills, the skills growing in your field that you don't show yet. What myGeeKy reads
  for you is picked by your interests, so on its own it would call anything you started reading about "rising".
  Growth is therefore measured where no one picked for you: the explore share of your feeds, plus one shared file
  (the same for everyone, rebuilt daily) counting each skill in an even sample of new bioRxiv, medRxiv and arXiv
  preprints, the last 45 days against the 45 before and against the same 45 days a year ago. A skill is **📈 rising** only when that growth is clear for
  how few mentions it has; **🌍 beyond your usual** when it's rising across the field but rare in your feed; **🪞 in
  your feed only** when it's busy mostly in what you chose to read. **🚀 Directions** come first: where your field
  is heading, even if your feed never mentioned it. Anything rising for sure across the new preprints counts, over
  the last 45 days or since the same 45 days a year ago (a big shift can be flat lately but many times bigger than
  a year ago), as long as preprints tie it to a skill you have, directly or through one skill between. The
  dictionary has direction-sized entries for this, such as genomic language models, AI agents, virtual cell, AI
  protein design and self-driving labs: "×7.7 in new preprints since a year ago; appears with your Genomics in 9 of
  them". A jump over the last weeks that is still below last year's level doesn't count. Directions are drawn
  three ways: a launch pad (each direction a rocket rising from the skill of yours it's most tied to: higher grows
  faster, bigger has more preprints), bridges (bands from your skills to directions) and a horizon (how far each is
  from you). Then 🧭 next steps
  (what to learn, and the skill of yours that leads there), 🌉 bridges (bands from your skills to rising ones),
  🪜 rising with you (your rising strengths and the new skills they appear with) and 🔍 your lens (how often a skill
  shows in your feed against the world). After all the plots, **🧭 Start a protocol** lists every direction and
  next step with a button that turns it into stages.
  - Each one says why it's suggested.
  - 👍 means "yes, I want to learn this"; 👎 hides it ("Show them again" brings hidden ones back).
  - **🧭 Make it a protocol** turns a skill into stages.
- **🧭 Protocols**: a skill as ordered stages, e.g. R basics → statistics with R → R for data analysis → a real
  project to rerun → your own work.
  - **Start one:** pick a ✓ reviewed protocol, or type any skill (and, if you like, what it's for, like *data
    analysis*) and press **🧭 Build**. Without a reviewed one, myGeeKy searches GitHub and papers, and its small
    protocol model sorts what it finds into stages. That one is marked *Auto-built, not reviewed*.
  - **Reviewed protocols**: 💻 *Git and GitHub for working with others*, *algorithms and data structures*, *your
    first web app*, *machine learning outside a notebook*, *your first pull request*; 🧬 *R and Python for data
    analysis*, *GWAS*, *Nextflow*, *single-cell RNA-seq*; 📊 and for anyone starting to analyse their own data:
    *From Excel to R*, *statistics for experiments*, *figures for papers*, *images into numbers with Fiji*.
  - **The level check:** stages your own repos already show are marked *You know this*; press **Not really** if
    they aren't. **🎓 Check** asks that step's own questions (pass at 75%), or shows a list of "I can do these".
    **▶ Start here** marks the first stage you don't know yet.
  - Tick a stage with **☑ Done**. The last stage, *Use it in your own work*, ticks itself when one of your repos
    shows the skill.
  - **✏️ Edit** lets you move stages and links up and down (a link past the top or bottom moves to the stage before
    or after), rename, add and remove them. Your copy is then *Yours*.
  - **📤 Publish** sends your protocol to myGeeKy's maker, as a public issue in the ideas repository that you send
    with your own GitHub account. It holds the stages, the links, and the links you removed. It never holds your
    progress, checks or answers. Published protocols become reviewed ones for everyone and teach the next model.
- **🏆 Quiz** (its own tab, next to Protocols): every protocol that has questions, in one place, with your best
  score on each, what you can still try today, and the ones you could start. **🏁 Take the quiz** asks ten
  questions drawn at random from that protocol's bank — half
  basics, then applied, then a few real pitfalls. Every question comes from one of that protocol's own sources, and
  shows you that source, with the sentence that proves the answer, once you've answered.
  - Only your best score counts, and there's one attempt a day.
  - **🚩** on a question you think is wrong: it's left out of your next attempts, and you can tell the maker.
  - **The quiz is drawn in that tab, never in a pop-up.** The same 🏁 button is on each protocol in
    🧭 Protocols, and **🎓 I know this: check me** on a step asks only that step's questions — both move you
    to 🏆 Quiz and open it there. One quiz, three ways in, one place it happens.
  - A dot per question shows where you are; ✕ leaves (an unfinished attempt simply doesn't count).
  - **🌍 Show my result** is how a score could appear on mygeeky.org — and it is off until you ask. Your name and
    your scores are two separate choices, you see exactly what would appear, and you agree by writing `accept` on a
    GitHub issue from your own account (`withdraw` undoes it). A score can follow you into a job application, so low
    scores are never shown at all: [LEADERBOARD.md](LEADERBOARD.md).
- **📚 Learn**: hand-picked learning resources, matched to you and your rising skills.
- **🎉 Wins**: new stars, forks and citations. The first check only sets the starting point.
- **🤝 Collaborators** (hidden for now, until more people use Signals): fellow myGeeKy users on Signals whose
  skills complement yours. **🤝 I'd like to collaborate** sends the sealed, mutual-only collaborate signal.

**🎯 Chances** has verified **jobs**, **funding** and **conferences**:
- each one is checked by hand and disappears after its deadline;
- 👍 / 👎 teach your model;
- 🚩 reports one that looks fake (as a GitHub issue, or by email to support@mygeeky.org).

All matching happens on your device. Your votes are kept in `taste.json`, your protocols in `learning_paths.json`
and your quiz scores in `quiz.json` (all synced to your private data repository if sync is on). How listings are
added: [CURATED.md](CURATED.md). How questions are written and checked: [QUIZZES.md](QUIZZES.md).

## How myGeeKy spends your GitHub limit

GitHub's limit belongs to **you**, not to myGeeKy: your own token gets 5,000 requests an hour (60 without
one, which is why the phone asks you to sign in). So refreshing cheaply is about your app staying quick,
not about GitHub's servers.

Every answer GitHub gives is kept on your computer with its **ETag**, and the next request carries it. When
nothing has changed GitHub replies **304 Not Modified**, which costs nothing against your limit and sends no
data. Nothing goes stale, because myGeeKy still asks every time — GitHub just answers "unchanged" for free.
In a measured check, re-reading three profiles cost 3 requests the first time and **0** the second.

On top of that:
- the same question asked twice in one refresh goes out **once**;
- **slow numbers wait a day**: a repo's stars, forks and commit activity, and a person's profile, known from
  less than a day ago aren't asked again, so switching tabs shows them at once;
- an account that no longer exists isn't asked about again for hours;
- **if GitHub or your network is away, the tabs still fill** from what was kept, with an honest "updated N
  hours ago" instead of an empty page.

The maker's Admin (You → Admin → 📊 Overview) shows what was asked and what was free today; **Forget GitHub's answers** is in Admin → ⚙ Settings. Forgetting loses
nothing: the next refresh asks again. It is a small SQLite database, `github_cache.sqlite` in your data
folder: each answer is its own row, so a refresh never rewrites the whole cache. It is capped in size, and never
synced — it only holds public data GitHub served.

## Finding people (`mygeeky run`)

How the people suggestions are made:

1. **Understands you** — reads your CV (txt/md/pdf), your own GitHub
   repos (languages, topics, descriptions) and, if you give them, your
   ORCID/OpenAlex and Google Scholar publications to build a profile of what
   you're into, and auto-derives a weighted "domain vocabulary" from that
   corpus (not a hardcoded field-specific wordlist).
2. **Collects candidates from multiple sources**, not just a plain search:
   the owners and contributors of active repos matching your research terms
   (ranked first — a plain language search mostly returns famous accounts),
   GitHub user search (language/location/follower filters), followers of
   well-known accounts in your field (`seed_accounts`), stargazers of
   relevant repos (`seed_repos`), stargazers of your own repos, and
   optionally second-degree contacts (people followed by people you
   already follow). Candidates corroborated by more than one source get a
   small ranking boost.
3. **Filters out noise before scoring**: accounts following more than
   `max_following` people (a growth-hacking/mass-follow pattern, not
   genuine engagement), dormant/throwaway-looking accounts, organizations,
   and — for the top-ranked candidates — a **real per-repo activity check**
   (a maintained repo pushed to recently, or a freshly-created one; a
   profile's `updated_at` alone can just reflect a bio edit).
4. **Scores each surviving candidate** on:
   - content similarity to your CV/repos (TF-IDF + cosine similarity)
   - how likely they are to follow back (their own following/follower ratio);
     for the follow-back list, accounts that follow almost nobody relative to
     their audience, or have more than `followback_max_followers`, are skipped
   - how active their account is
   - once you've used it a while: a learned model (see below)
5. **Suggests two ranked lists**, not one — printed, or returned as JSON.
   Nothing is followed automatically:
   - **Likely to follow back** — the blended score above.
   - **Domain-fit highlights** — ranked purely by match to your CV/repos,
     *independent* of follow-back likelihood. A senior domain expert who
     follows almost no one on GitHub is exactly who the follow-back score
     would otherwise bury, and is often the best actual match.
6. **Learns from real outcomes**, not just from waiting:
   - `mygeeky bootstrap` seeds the model immediately from accounts you
     *already* follow (checks, read-only, who already follows you back) —
     so you get real training data on day one instead of waiting weeks.
   - `mygeeky learn` (meant to run weekly) looks at who *you* actually
     followed since the last check, checks whether they followed back, and
     retrains a logistic-regression model on the growing set of outcomes —
     reporting cross-validated AUC so you can see how trustworthy it is,
     and excluding mass-follow outliers from training.

## Repos you could improve (`mygeeky contribute`)

Beyond people, myGeeKy suggests **repositories you could fork, improve,
and realistically get merged**, matched to your CV, repos, and
publications:

```bash
mygeeky contribute          # search + rank (a few minutes; GitHub's search API is rate-limited)
mygeeky contribute --last   # re-print the last results
mygeeky contribute --json   # for scripts / AI agents
```

1. Your profile is turned into a handful of search terms: your
   publications' OpenAlex keywords, topics used across your repos, and the
   CV vocabulary. Explicit `topics` / `contribute_extra_terms` always come first.
2. GitHub is searched for **active, non-archived, non-fork** repos matching
   those terms that have open `good first issue` / `help wanted` issues.
3. Each repo is ranked on fit (content similarity, a language you use,
   recency), then the top few get the check that actually predicts a merge:
   **of its recently closed PRs from outside contributors, how many did the
   maintainers merge?** Bot PRs and insiders' own PRs don't count.
4. Each suggestion lists its unassigned, recent starter issues and a
   plain-language "why".

As with people, this only ever *suggests*: there is no fork, PR, or comment
code anywhere. You open the repo, fork it, and send the PR yourself.

## 📄 Researchers: people who publish, not only people on GitHub

Circle → **📄 Researchers** (the computer and the phone) is for people who publish, whether or not they use GitHub.

- **🆕 New work:** new preprints and papers from the people you follow, as they appear. Preprints (arXiv,
  bioRxiv, medRxiv…) show months before the journal version; when the published version arrives (same title, by the
  same people), the two show as one: "now published · first as a preprint on bioRxiv, 2 Mar 2026".
- **👥 Following:** follow anyone by name. You pick the right person from OpenAlex's author search, with their
  institution, topics and recent titles (the same "is this the right one?" check as finding your own papers). The list
  stays on your device: nobody is told, and myGeeKy never contacts anyone.
- **✨ Suggested:** who cites your work (from You → Cited by) and who leads the papers rising in your field (from
  World → Papers). Both were already read, so suggesting costs nothing.

- **🌟 Leading lights:** living people who lead your field: Nobel and other prize winners, the most cited on a topic,
  and the people behind famous tools. Your Model picks four who fit you, and a new set comes every three days, going
  round everyone who fits before anyone comes back. Each shows why they're here, their latest papers, Follow, and a link
  to their Google Scholar (or ORCID / OpenAlex) profile. Tap a name (or Report) and their report unfolds right under them: papers, citations, h-index and
  i10-index, the last ten years as a chart, their topics (yours marked ★), their most cited papers and where they work.
  It costs about one OpenAlex credit a set and one a report. The list is checked by hand; *Report a mistake* says if
  someone is wrong, has moved or has passed away.
- **🕸 Network:** you in the middle, your co-authors around you, the people one introduction away outside, and
  the people you follow in orange, with lines where people have written together. Tap anyone to see who connects you
  ("you → Ada → Grace") and follow them. It's built from your papers (ORCID or "Find my papers") and rebuilt weekly
  with two searches. The topics your circle publishes on also join your Model gently (never above what you typed);
  the Network page shows what it adds and can switch it off.

Careful with OpenAlex's shared budget: everyone you follow is looked up in **one** search (up to 50 people at a
time), each person about as often as they publish (daily for the prolific, every three days, or weekly for the
quiet), through WISEP. An optional notification (🔔 → "New work from people you follow") tells you when something new
appears.

## 📦 Packs: share your setup like a seed

Setting myGeeKy up well takes a while. A pack lets someone start from your setup instead of from zero: the lab's
GitHub-savvy person sets it up once, or a teacher hands one pack to a whole class.

- **Make one:** ⚙ Settings → 📦 Packs (computer) or More → Settings → 📦 Packs (phone). Tick what goes in:
  keywords and topics, your research field, the researchers you follow, and add a note ("Plant genomics lab, 2026").
  Nothing else ever goes in: no account, no tokens, no Model.
- **Show it:** it appears as one to three QR codes, one at a time: "Code 1 of 3", then **Next code**. A full pack
  (40 keywords, 40 topics, a field and 30 researchers) usually needs two.
- **Receive it (on a phone):** More → Settings → 📦 Packs → **Receive a pack**, then point the camera at any code.
  The first scan tells how many codes the pack has; the screen shows which ones you have (✓ 1 ○ 2 ○ 3) and says
  which to show next, in any order. A code from a different pack starts over; a damaged set is never imported.
- **Choose:** you see what the pack holds before anything changes, then **Merge into mine** (only adds) or **Start
  from it** (its keywords, topics and field replace yours). **Undo** in Packs puts everything back.

Packs travel only as QR codes on a screen: no internet, no server, nothing stored anywhere. A pack is checked like
anything from outside: only plain words and researcher ids get through, and nothing in it can run.

## Your field's repos as a market board (`mygeeky market`)

<img src="https://raw.githubusercontent.com/mygeeky/myGeeKy/main/docs/screenshots/market.png" width="300" align="right" alt="Market tab">

Not repos to contribute to — the projects your field actually runs on,
ranked like a stock board by **momentum**:

```bash
mygeeky market              # snapshot (once a day) + print the board
mygeeky market --refresh    # snapshot again now
mygeeky market --last       # print the saved board, no network
mygeeky market --json       # for scripts / AI agents
```

```
#1    +2  bioconda/bioconda-recipes   *1.9k (+31)  752 commits/4wk
#2   NEW  biotite-dev/biotite         * 976 (+9)   pypi 391.1k/wk +117%  6 commits/4wk
#3    -1  rgcgithub/regenie           * 270 (+3)   1 commits/4wk
```

1. **The watchlist** (`market_size`, default 25) is picked weekly by
   searching GitHub for your profile terms, as text and as topics, among
   repos with `market_min_stars`+ stars pushed in the last
   `market_pushed_within_days`. Your terms take turns filling it, so broad
   ones like "genome" can't crowd out "gwas". Repos only get in when they
   clearly belong to the field: your terms in their own name/description,
   or a real share of their topics — not "bioinformatics" as one tag among
   twenty, not AMD's "SEV-SNP", not awesome-lists, courses or AI-agent
   tooling borrowing the words. `market_pinned` repos always stay on.
2. **Signals:** stars (GitHub has no star history for normal tokens, so
   star momentum builds from myGeeKy's own daily snapshots — "collecting"
   for the first days), commits over the last 4 weeks (52 weeks of history
   come at once), and — when the repo publishes a PyPI package whose page
   links back to it — real PyPI downloads per week and their change, from
   pypistats.org with mirrors excluded.
3. **Ranking:** a weighted average of each repo's percentile on the signals
   it actually has, so tools that aren't on PyPI (PLINK, GATK, …) aren't
   pushed down for lacking downloads. ▲▼ shows places moved since the last
   day ranked.

About 3 GitHub API calls per repo, once a day. In the panel it's the
**Market** tab, refreshed in the background when it's older than
`market_refresh_hours` (default 12).

**Product Hunt launches in your field.** Under the board, the Market also
lists recent [Product Hunt](https://www.producthunt.com) launches. Launches
that mention your profile terms come first (tagged *your field*), then the
rest by upvotes. Product Hunt has no search, so launches are pulled from a few
topics (`market_ph_topics`), from the last `market_ph_days` (30). It's
read-only and needs a free Product Hunt developer token:

```bash
mygeeky auth producthunt          # walks you through creating the token; stored in the OS keyring
mygeeky market --refresh          # board + launches
```

<br clear="right">

### 🤗 Models trending on Hugging Face (Market → Models)

Two lists, refreshed every 6 hours from Hugging Face's public API (no key needed):

- **In your field:** models carrying the Hugging Face tags your interests point to
  (e.g. GWAS and single cell lead to `biology` and `genomics`; your own keywords
  count as tags too), sorted by Hugging Face's trending score and your interests.
  First-attempt uploads with no trend and few likes are skipped.
- **🌍 Trending everywhere:** the global top, so you see the big new models too.

Settings: `market_hf_enabled`, `market_hf_size` (15), `market_hf_refresh_hours` (6).

### Product Hunt, with or without a token

Launches show up under the Repos board for everyone: without setup they come from
Product Hunt's public feed (today's featured launches). `mygeeky auth producthunt`
(a free developer token) switches to the API, which adds upvotes and topics and
reaches further back.

## Your profile: CV + GitHub + ORCID/OpenAlex + Google Scholar

**📑 Who cited you** (You → Cited by, on the computer and the phone): with your ORCID iD or the papers you found
with "Is this you?", myGeeKy shows your citations and h-index, the new papers citing you (who wrote them, where,
and which of your papers they cite), the people who cite you most (your real readers: often good collaborators) and
the countries you're read in. It reads OpenAlex once a day, and only asks about papers whose citations went up, so
it's a few requests a day. The first read only sets the starting point; after that, new citing papers are marked
NEW, and there's an optional notification for them (⚙ → Notifications, off unless you switch it on).

```bash
mygeeky profile refresh --cv ~/cv.pdf --orcid 0000-0002-1825-0097 \
    --scholar "https://scholar.google.com/citations?user=XXXXXXXXXXXX"   # all remembered
mygeeky profile refresh     # after updating your CV: re-extract the PDF, re-fetch publications
mygeeky profile show        # what myGeeKy knows about you (no network)
```

- **CV**: PDF, Word (.docx), txt or md, converted to text.
- **Drop a CV, thesis or abstract** (setup, or ⚙ on the computer and More → Settings on the phone): myGeeKy picks
  out your field's keywords (from the keyword dictionary), your methods and tools, and the people you've written
  with, and you untick anything that isn't you. A first-year student with only a thesis proposal still gets a full
  profile. The file is read on the device and not kept: only the words you keep are saved, in your keywords and
  co-authors. Scanned PDFs have no text to read; paste the text instead.
- **No ORCID? "Find my papers"** (setup, ⚙ → Your papers, More → Settings): type your name and institution (or
  institutional email, or a co-author's name) and pick yourself among the researchers OpenAlex knows; your papers
  then shape your profile as an ORCID would. If OpenAlex is busy, setup carries on with keywords and the search is
  tried again later by itself, asking "Is this you?" when it works.
- **ORCID** (public API) and **OpenAlex** (looked up by your ORCID): your
  publication titles, abstracts, keywords and research topics. They're free and
  need no key. They feed both people matching and repo suggestions.
- **Google Scholar** (optional): your research interests and up to 100 paper
  titles, read from your own public profile page. Scholar has no API and limits
  automated access, so this is one request per `profile refresh`, never part of
  a normal run; if Google refuses it, the last fetched copy is kept and
  ORCID/OpenAlex still cover your publications.

## Linux: the panel, the menu and the background

`mygeeky gui` starts the panel **in the background** (you can close the terminal)
and adds **myGeeKy to your applications menu**, with its icon. Quit it from ⚙ in
the panel. `mygeeky gui --foreground` keeps it in the terminal, for troubleshooting.

```bash
mygeeky desktop install --autostart   # also open it when you sign in
mygeeky desktop install --no-autostart
mygeeky desktop remove                # out of the menu (and sign-in) again
```

If you ran an older version you may have seen
`qt.qpa.theme.gnome: dbus reply error ... org.freedesktop.portal.Settings`.
It was harmless (Qt asking the desktop for its dark/light preference, which some
desktops don't offer) and is no longer printed.

## macOS

**Install.** The one-line installer works the same as on Linux:

```bash
curl -fsSL https://mygeeky.org/install.sh | sh
```

It needs Python 3.9 or newer, from any of these:
- **Homebrew:** `brew install python` (see [brew.sh](https://brew.sh));
- **python.org:** the installer from python.org;
- **macOS's own** `/usr/bin/python3`, once Apple's Command Line Tools are installed (`xcode-select --install`). Without them, that `python3` is only a stub that offers to install them, so the installer skips it.

myGeeKy gets its own environment in `~/.local/share/mygeeky-app`, so Homebrew's "externally managed" rule never gets in the way.

The installer adds **`~/Applications/myGeeKy.app`**, which shows up in Launchpad and Spotlight and can be kept in the Dock. The `mygeeky` command goes in `~/.local/bin`; if that isn't on your PATH, the installer prints the one line to add to `~/.zprofile`.

**Or with uv:**

```bash
uv tool install mygeeky --with PySide6-Essentials
mygeeky setup            # the setup window
mygeeky gui              # the panel (and myGeeKy.app in ~/Applications)
```

`--with PySide6-Essentials` brings Qt along. Without it, the first `mygeeky gui` installs Qt with uv, because a uv environment has no pip. The panel's **Update** button runs `uv tool upgrade mygeeky`, which keeps Qt.

**The app, login and the weekly run:**

```bash
mygeeky desktop install               # (re)create ~/Applications/myGeeKy.app
mygeeky desktop install --autostart   # also open it when you log in
mygeeky desktop remove                # remove the app and the login item
mygeeky schedule install --yes        # refresh suggestions every Monday at 09:00
```

**What gets created:**
- **Login item:** `~/Library/LaunchAgents/org.mygeeky.panel.login.plist`, which opens myGeeKy.app.
- **Weekly run:** `org.mygeeky.weekly.plist` in the same folder.

Both are launchd agents, not cron jobs: cron is deprecated on macOS, and launchd runs a Monday that was missed while the Mac slept as soon as it wakes. Newer macOS shows a "Background Items Added" notice the first time; you can see and switch them off in **System Settings → General → Login Items**.

**Your tokens** are kept in the macOS **Keychain** (in Keychain Access they're named `mygeeky-github-token`, and `mygeeky-beacon-token` if you use Signals), never in a file. To paste one in a terminal, use **⌘V**.

**The panel** docks to the edge of the screen inside the space the menu bar and the Dock leave free, and stays visible when you switch to another app. The menu bar shows **myGeeKy**, not Python.

**Uninstall:** ⚙ → **Uninstall…** in the panel, or `mygeeky uninstall`. It removes:
- myGeeKy.app;
- the login item;
- the weekly run;
- the install folder and the package.

Your data and Keychain entries stay, so a reinstall picks up where you left off, unless you choose to erase them too.

## Use it from any computer (`mygeeky sync`)

Your myGeeKy data can live in a **private** GitHub repo, so the model keeps
learning no matter which machine you run it on. It's optional, and it needs
**Git**. On Windows the installer installs Git for you when you tick sync;
otherwise get [Git for Windows](https://git-scm.com/download/win).

```bash
mygeeky sync init                      # creates <you>/mygeeky-data (private) and pushes
mygeeky sync init --repo you/other     # or use/choose another private repo
mygeeky sync pull | push | status
```

On a new computer: `pip install mygeeky`, then `gh auth login` and
`mygeeky sync init --repo <you>/mygeeky-data` (the **same** repo). It pulls your
config, keywords, CV text, publications, history, sent signals and training data.

After that it keeps itself in step: **the panel syncs every hour while it's
open** (and once more when you quit it), so what you do on one computer shows up
on the others. `mygeeky pipeline` (the weekly job) also does
**pull → learn → run → contribute → push**. Your Signals token and key stay per
computer: run `mygeeky beacon init` on each computer you want to send signals from.

- It refuses to sync to a public repo.
- Never synced: any token, caches, logs, and the pickled model. Loading a
  pickle that came over the network could run code, so the model is
  retrained locally from the synced training data instead.
- `.jsonl` logs use git's `union` merge, so two machines in the same week merge cleanly.
- Git uses your own `gh`/git credentials. myGeeKy's API client stays read-only.

## Research trends, and the papers behind repos (`mygeeky trends`)

<img src="https://raw.githubusercontent.com/mygeeky/myGeeKy/main/docs/screenshots/research.png" width="280" align="right" alt="Research trends">

Tools in research live in two places: papers and GitHub. myGeeKy connects
them, using [OpenAlex](https://openalex.org), a free, open index of the
world's papers that's updated daily.

In the panel, it's the **Market** tab's **Research** switch:

- **🔥 Rising in your field:** recent papers ranked by **citations per month**,
  so a hot three-month-old paper beats an old classic. *Your field* comes from
  your OpenAlex research topics (from your ORCID papers), your Google Scholar
  interests and your topics, and it follows what you've been engaging with lately.
- **🛠️ Tools with papers:** new tools in your field whose paper links their
  code on GitHub.
- **👩‍🔬 People behind the trends:** who leads them (first and senior authors),
  linked to their ORCID or OpenAlex profiles.

**Click a paper** to open it, open its **GitHub repo**, and see **the people
working on it** (the repo's owner and top contributors).

**The green P.** Any repo with a published paper gets a green **P**, in
Repos, the Market and Research. myGeeKy finds the paper through the repo's
`CITATION.cff` or a DOI in its README. Hover it for the paper and its citation
count; click it to open the paper. For example, fastp → *fastp 1.0* (253
citations) and scanpy → *SCANPY* (10,000+ citations).

```bash
mygeeky trends              # rising papers, tools with papers, people
mygeeky trends --refresh    # ask OpenAlex again now (otherwise daily)
```

<br clear="right">

## News for your field (`mygeeky news`)

**🏁 AI race** (the first view in the News tab, on the computer and the phone): who leads the AI race and how far
open-weights models trail (in points and in months), the newest releases with where each lands, the race replayed
month by month, what each recent model is best at (reasoning, coding, math, science, agents, knowledge, writing,
vision, security), each top model's "fingerprint", and a picker that ranks models for the skills your work needs.
The numbers are [Epoch AI](https://epoch.ai/benchmarks)'s open benchmark data (CC BY 4.0), turned into one small
file once a day by a GitHub Action and read from GitHub; the skill groups and scores are myGeeKy's own: each
benchmark scored from a random guess (0) to its ceiling (1), averaged per skill, among models from the last 18
months.

**Headlines** (the second view in the News tab, or `mygeeky headlines`): just
titles, so you know what's happening across your work at a glance. Every three
hours myGeeKy reads the public feeds of AI labs (OpenAI, Google AI and DeepMind,
Hugging Face, MIT Technology Review, The Verge, TechCrunch), journals (Nature,
Nature Genetics, Nature Biotechnology, Science, Quanta, ScienceDaily, Ars
Technica) and the tech press (Ars Technica, GitHub, The Register). It ranks
them with **your model**: your topics and keywords (with their meanings), your
CV and papers, and what you've clicked lately.

- **For your work:** headlines with real evidence, meaning two of your terms, a
  multi-word one, or a topic or keyword you chose. One stray word doesn't count.
- **🌍 The big picture:** the newest of the rest, taking turns across AI, science
  and tech, and always at least `headlines_ai_min` (3) from AI.
- Settings: `headlines_categories` (`ai`, `science`, `tech`), `headlines_size` (30),
  `headlines_days` (4), `headlines_refresh_hours` (3), `headlines_enabled`.
- Only feeds are downloaded; nothing about you is sent. Titles are plain text,
  and a link only opens if it points at that feed's own site.

**One letter, one meaning, everywhere:**

| | On a news item | On a repo (Repos, Market) |
|---|---|---|
| 🟩 **P** | it's a paper (research article, preprint) | it has a published paper |
| 🟨 **N** | a news story | it's **in the news this week** (a story links to it or names it) |
| 🟦 **D** | a Hacker News discussion | it's being discussed on Hacker News |
| 🟪 **A** | an announcement from an AI lab or company blog | |

Click a repo's **N** or **D** to read the story. A repo's name only counts from a
title when it's distinctive (not "tools" or a field like "genomics").

**Papers & discussions** (the other view):

<img src="https://raw.githubusercontent.com/mygeeky/myGeeKy/main/docs/screenshots/news.png" width="280" align="right" alt="News tab">

New preprints and discussions that match your interests, from free and
constantly updated sources, with no accounts or keys:

- **arXiv:** new preprints (AI, CS, statistics, quantitative biology, ...).
- **bioRxiv:** the last days' biology preprints.
- **Hacker News:** what developers are discussing.

Each item says why it's there (*matches gwas, fine mapping*). Items are ranked
by how well they match your interests and how new they are. A single generic
word like "stress" isn't enough on its own (physics uses it too); it takes two
of your terms, or one specific phrase. One source being down never empties
the feed.

```bash
mygeeky news              # the saved news (refreshed every 6 hours)
mygeeky news --refresh    # fetch now
```

<br clear="right">

## Keywords that mean something (`mygeeky keywords`)

A keyword in myGeeKy is a **concept, not just a word**. Add "AI" and myGeeKy
also looks for LLMs, deep learning, AI agents and so on, each weighted by how
closely it goes with "AI". Add "GWAS" and it brings in genomics, genetics and
statistical genetics.

```bash
mygeeky keywords                  # yours: ● green = known, ● red = a plain word for now
mygeeky keywords add AI "single cell"
mygeeky keywords explain gwas     # what it brings in, and how strongly
mygeeky keywords suggest "my niche term"   # ask for a red one to be learned
```

In the panel: **Model → 🔤 Your keywords**. Type to get suggestions from the
dictionary, hover a keyword to see what it brings in, ✕ to remove it.

**Where the meaning comes from.** A small, explainable model reads GitHub's
open data: for each keyword (a GitHub topic) it looks at the 100 most-starred
repos carrying it and counts which other topics they carry. Topics that go with
everything ("python", "hacktoberfest") are discounted, so they can't relate to
everything. The result is a dictionary of a few hundred keywords that ships with
myGeeKy; a newer one is picked up by itself, at most once a week
(`mygeeky keywords update` checks now).

**Red keywords aren't lost.** They still work, matched as plain words, and they
reach myGeeKy's maker so the next dictionary can learn them:
- automatically, if you're on Signals: your beacon's public interest tags already
  carry your keywords (red ones first);
- or when you click a red keyword (or run `mygeeky keywords suggest`): a
  prefilled GitHub issue that you submit yourself.

## 🏅 Badges

Under your name in the panel: the badges you've earned, and your GitHub
achievements (Pull Shark, Quickdraw…). Click them, or the 🏅 tab, to see them all,
with how far you are from the next level. A dot on 🏅 means a new one.

| | Badge | Earned by | Bronze · Silver · Gold |
|---|---|---|---|
| 🔥 | Regular | days you open myGeeKy | 3 · 14 · 60 |
| 🖱️ | Clicker | things you open from it | 10 · 50 · 200 |
| 📰 | News Reader | headlines and news | 10 · 50 · 200 |
| 📊 | Analyst | papers | 5 · 25 · 100 |
| 🤖 | AI Fan | AI headlines and models | 5 · 25 · 100 |
| 🤗 | Model Hunter | Hugging Face models | 3 · 15 · 50 |
| 🔭 | Explorer | things outside your usual interests | 3 · 15 · 50 |
| 🤝 | Networker | people you follow | 1 · 10 · 30 |
| ⭐ | Stargazer | repos you star | 1 · 10 · 50 |
| 🛠️ | Builder | repos you fork to contribute | 1 · 5 · 20 |
| 🙏 | Grateful | signals you send | 1 · 5 · 20 |
| 🔤 | Wordsmith | keywords you set | 3 · 8 · 15 |
| 💡 | Idea Giver | ideas and problems you send | 1 · 3 · 10 |
| ☁️ | Everywhere | sync set up | earned once |
| 🌱 | Early Adopter | joined before 2027 | earned once |

Badges come from your own files only. myGeeKy keeps a small usage log
(`usage.jsonl`) with the **kind** of thing you opened (a headline, a model, a
paper) and its area, never titles or links; it syncs with the rest of your data.
GitHub achievements have no API, so they're read from your public profile at most
once a week; if GitHub changes that page, they just don't show.

## 🔔 Notifications (off unless you switch them on)

myGeeKy never notifies you unless you ask it to. In setup (the last step) or in Settings (⚙ on the computer,
More → Settings on the phone), switch on only the kinds you want: 🗓 a Season opening, 💼 a job, 💶 funding or
🎤 a conference that fits you very well, 📄 an important new paper in your field, ✨ a new Highlight. Choose
"at most once a day" or "at most once a week", and quiet hours (22:00-08:00 to start with).

What's told is only what's really worth it: a Season confirmed open or expected within three weeks; a job,
funding call or conference with a very high fit; one of the three papers rising fastest in your field, just
out; a Highlight from the last two weeks. Each thing is told once, all in one line ("🗓 2 Seasons open soon ·
💼 1 job fits you"); tapping it opens the right place. Settings shows exactly what you agreed to, and **Turn all
off** switches everything off at once.

It's worked out on your device from what myGeeKy already has; nothing is sent anywhere and no server pushes
anything. The computer looks every 20 minutes while myGeeKy is open; the phone looks when it opens and when
Android lets it run in the background (a few times a day), so a phone notification can come a little late.

## 🎖 My month and your rank

**You → 🎖 My month** (the first part of You, on the computer and the phone) shows what you did this month and your
rank, with a card you can share.

**Your rank** climbs from Soldier to General as you earn points for what you do yourself:

| Points | For |
|---|---|
| +1 | a news story or a repo you opened |
| +2 | a paper you opened, a chance you 👍 (saved) |
| +3 | a topic outside your usual interests, a person you followed |
| +4 | a quiz |
| +5 | a protocol step done |
| +6 | an idea you sent |
| +8 | a protocol you published |
| +10 | a protocol you built, a step you can already do (a skill) |

| Rank | Soldier | Corporal | Sergeant | Lieutenant | Captain | Major | Colonel | General |
|---|---|---|---|---|---|---|---|---|
| From | 0 | 50 | 150 | 350 | 700 | 1200 | 2000 | 3500 |

Points count over all your time in myGeeKy, so a rank never goes down. Stars and citations from others show on
your card but earn no points: the rank is for your own effort, and works the same with or without a GitHub
account. When you move up, GeekOc tells you once.

**Your month in pictures**: eight drawings, each with GeekOc and a line from him. Your GitHub work as a glowing
calendar of contributions; the languages you used as GeekOc's arms; your wins (stars, forks, citations) along a
ribbon; your protocols as constellations, a lit star for each step you know; the topics you explored on a compass
(new territory in pink); when in the day you come by, on a sky clock, with your badges as medals beneath it; what
you gave and got (thank-yous, invites, follows); and how your interests moved since last month. The GitHub ones
read your own GitHub events (at most once an hour, kept on your device for 400 days); everything else is what
myGeeKy already keeps. Each says so when there's nothing yet.

**Your card** is a 4:5 picture (the shape LinkedIn and X show largest): the month as a calendar with a dot for
each kind of thing you did that day, your three highlights (a first gets a **FIRST!** ribbon), every count, your
rank's shield and GeekOc. Untick anything you'd rather leave off, then **Save image** or **Copy image** on the
computer, or **Share my month** on the phone (its own share sheet: LinkedIn, Instagram, Facebook...). ‹ › go back
through earlier months. Nothing is posted for you.

It's worked out on your device from the same usage log as badges (now also noting, by kind only, a protocol
step, a protocol built or published, a quiz, a skill and a chance saved) plus your follows and wins. Nothing is
sent anywhere. With your data repo connected, your computers and phone count the same records.

## It learns what you're into, and keeps room to explore

Everything you do teaches myGeeKy a little about your interests:

| You | Counts as |
|---|---|
| fork a repo | strongest signal |
| follow someone new | strong |
| star a repo | strong |
| click a repo (Repos, Market) | medium |
| click a news item | medium |
| click a suggested person | light |

From each one it keeps **a few terms** (topics, words from the description
or bio, never the full text). Recent actions count more: each one fades to
half after `interest_half_life_days` (30). A single stray click isn't enough to
change anything; repeated interest is. What it learns tunes **who it searches
for, which repos it suggests, which repos the Market watches, and the News**.
Follows, stars and forks are picked up from your public GitHub activity.

**🔭 New territory.** A profile that only follows your clicks shuts you in a
bubble. So **20% of every list** (`explore_share`) is kept for things *outside*
your usual interests, from fields that rotate daily, marked **🔭 new territory**.
If one catches your eye, clicking it teaches myGeeKy that the new area
interests you too.

```bash
mygeeky interests          # what it has learned, and today's new territory
mygeeky interests --reset  # forget it (your CV, papers and topics stay)
```

The **Model** tab shows all of it as *What myGeeKy knows about you*: an
animated **interest map** (you in the middle, your research field on the inner
ring, what you've been into lately pulsing on the middle ring, today's 🔭 new
territory on the outer ring; hover any point), **what teaches it** (your
clicks, follows, stars and forks over the last 30 days), **room to explore**,
and **who follows you back** (the follow-back model). Turn learning
off with `mygeeky config set interest_learning false`, or exploration with
`mygeeky config set explore_share 0`.

## Signal other myGeeKy users, without words (`mygeeky beacon`)

myGeeKy users can send each other small **private signals**, and myGeeKy
never needs a server for it: everything goes through GitHub. They're built to
be **gifts, not requests**, so nobody is ever left feeling ignored:

| | Signal | The recipient sees |
|---|---|---|
| 🙏 | `thanks` | "thanked you for your work" |
| 📚 | `learn` | "learned from your work" |
| ⭐ | `used --repo owner/name` | "used owner/name in their work" (an informal citation) |
| 👀 | `watching` | "is following your work" |
| 🤝 | `collab` | **nothing, unless they choose it for you too.** Then you both see "you both want to collaborate". |

Every signal they receive says **"no reply needed"**, and your own side never
shows "no answer yet": only "sent ✓".

### Join Signals, step by step

Signals is the one part of myGeeKy where you do two things on github.com
yourself. Run `mygeeky beacon init` (or tick *Join Signals* in the Windows
installer): it opens each page for you, waits while you do it, and checks that
each step worked before going on.

**Step 1: create your public beacon repo.**
1. Open [github.com/new?name=mygeeky-beacon](https://github.com/new?name=mygeeky-beacon&visibility=public&description=My+myGeeKy+beacon+(private+signals)).
   The name `mygeeky-beacon` and **Public** are filled in.
2. Check that the owner is you, then click **Create repository**. Leave it
   empty; myGeeKy writes the files. (If the GitHub CLI `gh` is installed and
   logged in, myGeeKy creates the repo for you instead.)

**Step 2: create a second token, one that can write to that repo only.**
This is separate from the read-only token you made when you set myGeeKy up,
and it can only be made **after** Step 1: GitHub only lets a token be limited
to a repo that already exists.
1. Open [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new).
   Name it `mygeeky-beacon`, with **Resource owner** set to you, and a long
   **Expiration**.
2. **Repository access** → **Only select repositories** → pick `mygeeky-beacon`.
   The permission list only appears after you pick the repo, so do Step 1 first.
3. Under *Repositories*, click **Add permissions** → **Contents**, and set it to
   **Read and write**. (On the older page: **Repository permissions** →
   **Contents** → **Read and write**.) *Metadata: Read-only* is added by itself;
   that's fine.
4. Add nothing else. Click **Generate token**, copy it (it starts with
   `github_pat_`), and paste it when `mygeeky beacon init` asks.

**Step 3: done.** myGeeKy tests the token by publishing your `beacon.json`,
stores the token in your OS keyring, and reads it back from GitHub to make
sure others can see you. Your repo should now contain `beacon.json`.

**Not showing up?** Run `mygeeky beacon check`. It changes nothing and lists
what's missing:

| What you see | What it means | Fix |
|---|---|---|
| repo "doesn't exist yet" | Step 1 wasn't done, or under another account | Create `mygeeky-beacon` under your own account |
| repo "is private" | Nobody can read your beacon | Repo **Settings → Change visibility → Public** |
| "GitHub refused the write" | The token can't write | Make a new token with **Contents: Read and write** |
| "token can't see" the repo | The token is for other repos | Choose **Only select repositories → mygeeky-beacon** |
| "beacon.json isn't published" | Setup stopped before Step 3 | Run `mygeeky beacon init` again |

Adding the topic `mygeeky-beacon` to the repo (⚙ next to *About*) is
optional: myGeeKy finds beacons by their name as well.

### Using it

```bash
mygeeky beacon init                  # one-time setup, as above
mygeeky beacon check                 # what's missing, if others can't see you
mygeeky beacon people                # fellow myGeeKy users, those sharing your interests first
mygeeky beacon send alice thanks     # or: learn | watching | collab | used --repo alice/tool
mygeeky beacon inbox                 # signals sent to you (no reply is ever expected)
mygeeky beacon status open-to-collab # or learning, heads-down, seeking-reviewers, mentoring, none
mygeeky beacon quiet on              # not taking signals right now (off to undo)
mygeeky beacon sent | unsend alice | mute alice | block troll
```

<img src="https://raw.githubusercontent.com/mygeeky/myGeeKy/main/docs/screenshots/signals.png" width="260" align="right" alt="Signals tab (example data)">

In the panel, the **Signals** tab shows what people sent you and who else
is around, with one-click 🙏 📚 👀 🤝 buttons (hover one to see exactly what
it does), a **🔕 Not taking signals right now** switch, and 🔇 to mute someone.
Incoming signals also lead the Live tab's rotation.

How it works: each user's beacon is a public repo named `mygeeky-beacon`
(ideally also tagged with that topic), holding one `beacon.json` file: your
status, a few interest tags from your `topics`, `keywords` and `languages`
(turn those off with `beacon_share_interests false`), one public key per
computer you use, and your **sealed** signals. myGeeKy finds other beacons with
a normal repo search and tries to open every sealed signal with your key.
Someone who signalled you also gets a boost in your suggestions.

- **Signals are private.** Each one is encrypted to the recipient's key
  (X25519 + ChaCha20-Poly1305, padded so every signal looks the same size).
  Nobody else can tell who it's for or what it says, so nobody can see who
  didn't answer. Your private key never leaves your computer's keyring. The
  sender's name is sealed inside too, so nobody can pass off someone else's signal.
- **🤝 is mutual opt-in.** The other person's panel only shows it once they've
  chosen it for you too. (The app hides it; a determined person running modified
  code could find out early, but nobody else ever can.)
- **Courtesy, built in.** The same signal to the same person once a month
  (`beacon_repeat_days`, 30), at most `beacon_weekly_new_people` (5) new people
  a week and `beacon_daily_limit` (10) signals a day. Someone who's *quiet*
  can't be signalled at all; nobody is told why.
- **There's no text, so there's nothing to moderate.** Signals and statuses come
  from fixed lists. Everything read from other people's beacons is validated and
  shown as plain text. `mute` hides someone quietly; `block` also stops yours to them.
- **Signals expire** after `beacon_gesture_ttl_days` (90), and `unsend` takes one
  back from your beacon at once.
- **Older versions:** people still on myGeeKy 0.7.5 or older can't receive
  private signals until they update (the panel says so). Their old public
  signals still show up for you, in the new wording.
- **A separate, single-repo token.** `init` asks for a fine-grained token
  with access to *only* `<you>/mygeeky-beacon` and only **Contents: Read and
  write**. It's stored in your OS keyring under its own entry. Your main token
  stays read-only.

## Install

```bash
pip install mygeeky
```

That's all: PDF CVs work out of the box, and the panel's GUI library (Qt) is
set up automatically the first time you run `mygeeky gui`. With uv instead:
`uv tool install mygeeky --with PySide6-Essentials` (see [macOS](#macos); it works
the same on Linux). (`pip install
"mygeeky[gui,pdf]"` still works too; the extras just aren't needed any more.)

On Windows you can use `MyGeeKySetup.exe` instead (see the top of this page).
To build it yourself: `pip install pyinstaller build`, then
`python installer/build.py`, which writes `dist/MyGeeKySetup-<version>.exe`.

### Updating

myGeeKy tells you when a new version is out: a banner in the panel with an
**Update** button (it updates and restarts the panel by itself), and a one-line
note in the terminal. Or run:

```bash
mygeeky update            # update now
mygeeky update --check    # only say whether there's a newer version
```

It asks PyPI at most once a day, sending nothing about you. Turn it off with
`mygeeky config set check_for_updates false`. (A developer install made with
`pip install -e .` is never touched; update it with `git pull`.)

### Token expiry

GitHub tokens expire on the date you chose when you made them. myGeeKy reads
that date from GitHub (once a day) and, **from a week before**, reminds you: a
banner in the panel with **Renew on GitHub** and **Paste new token**, and a
note in the terminal. To renew, open the token on
[github.com/settings/personal-access-tokens](https://github.com/settings/personal-access-tokens),
click **Regenerate token**, and paste the new one (in the panel, or with
`mygeeky auth login` for token 1 and `mygeeky beacon init` for token 2).

```bash
mygeeky auth status       # both tokens and when they expire
```

### If something goes wrong on Windows

Every error says what went wrong, naming the file or program involved, and
the full details are saved for you to send:
- **Installer:** `~/.mygeeky/setup.log`. The error message has an *Open the setup log* link.
- **`mygeeky` command and panel:** the error says where it saved its report
  (an `error-<date>.txt` in myGeeKy's `logs` folder).

Please attach that file when you [open an issue](https://github.com/mygeeky/myGeeKy/issues)
(or email it to [support@mygeeky.org](mailto:support@mygeeky.org)).

If you don't have Python, or only have the Microsoft Store Python, the
installer sets up a regular Python 3.12 just for you: with winget when your PC
has it, otherwise straight from python.org. No admin rights needed.


- **`'mygeeky' is not recognized`**: pip put the command in a folder that isn't
  on your PATH (common with the Microsoft Store Python). Use `python -m mygeeky`
  instead, e.g. `python -m mygeeky init`. It offers once to add that folder to
  your PATH, so plain `mygeeky` works in new terminals.
- **`OSError: [Errno 2] No such file or directory: ...PySide6\qml\...`** with a
  *Long Path* hint, from installing PySide6 yourself: the Microsoft Store
  Python's package folder is too deep for Qt's files. You don't need to install
  Qt by hand. `mygeeky gui` sets it up in a short folder (`~/.mygeeky/qt`) that
  avoids the limit, no admin rights needed. If you'd rather, `MyGeeKySetup.exe`
  sets up a regular Python instead.

## Quick start

```bash
mygeeky init      # asks for your GitHub username, CV, and the kind of people you're looking for
mygeeky run       # get your first batch of suggestions
```

`mygeeky init` asks a short set of questions — all optional, all editable
later:

- Your GitHub username (optional: leave it blank if you have no GitHub account)
- Your CV (a file path, pasted text, or skip)
- Your ORCID iD (type `signin` to sign in with ORCID in your browser) and your Google Scholar profile URL (each optional)

Any one of the username, the ORCID iD or a few topics is enough. Without GitHub: Chances, Grow, News, Research,
Market, Repos to improve and the field half of People all work. An account is needed for who'd follow you back,
Activity, Signals, Collab, and for syncing to your phone.
- Languages / topics / keywords / locations you're looking for
- Optional extra candidate sources: well-known accounts in your field, relevant repos
- Follower-count range, `max_following`, minimum repo count, how many suggestions per run

Then it offers to store a GitHub token (see [Safety](#safety) — this is
handled very deliberately), and — if a token is set up — offers to run
`mygeeky bootstrap` immediately so you're not starting the learning model
from zero.

## Everyday use

```bash
mygeeky run                 # search + rank + suggest (two lists: followback + domain-fit)
mygeeky run --json          # same, as JSON (for scripts / AI agents)
mygeeky suggestions         # re-print the last run's results without re-querying GitHub
mygeeky bootstrap           # seed the model from accounts you already follow (run once, early)
mygeeky learn               # check who you followed since last time, learn from who followed back
mygeeky contribute          # repos you could fork, improve, and get merged
mygeeky market              # momentum board of the popular, active repos in your field
mygeeky profile refresh     # re-read your CV + publications (ORCID/OpenAlex)
mygeeky sync push|pull      # keep your data in your private GitHub repo
mygeeky pipeline            # sync pull, learn, run, contribute, sync push — the weekly job
mygeeky gui                 # launch the live glass panel
```

## Running it weekly

myGeeKy doesn't run in the background by itself — you decide when it's
allowed to touch your OS's task scheduler:

```bash
mygeeky schedule show          # print the exact command/cron line for your OS (does nothing)
mygeeky schedule install --yes # actually register it (Windows Task Scheduler / launchd on a Mac / cron)
mygeeky schedule remove        # undo it
```

The scheduled job runs `mygeeky pipeline` — i.e. it *checks and learns*
from what you did last week, then produces new suggestions. It still never
follows anyone.

## Live glass panel (optional GUI)

```bash
mygeeky gui          # (or the standalone `mygeeky-gui` command)
```

The first run sets up Qt (PySide6, about 80 MB) by itself. It uses this
Python's normal package folder when Windows' path limit allows, and otherwise
a short private folder, `~/.mygeeky/qt` (or `$MYGEEKY_QT_DIR`).

**🏠 Home** (the first page, on the computer and the phone): one scrolling feed of what the other pages found for
you: new work from people you follow, rising papers, jobs and funding still open, datasets just out, repos and people,
headlines, a quiz question or two. New things come first; after **"You're all caught up"** come the ones you've seen,
best first. Each card glows in its kind's colour (a plain outline in the light theme) and shows what makes it worth
a look: a ring counting down the days left on a job, grant or conference, a repo's stars and how many it gained this
week, a dataset's size and licence, a model's downloads, and quiz questions you answer right on the card. A banner on
top celebrates what's new ("3 new papers from your circle this week", "2 deadlines this week"). Every card says why
it's there ("matches GWAS · new today") and has:

- **♡ More like this**: Home shows more of that kind, and your Model learns the card's topics (never names).
- **🔖 Save**: keeps it in **🔖 Saved** at the top of Home for later, and teaches like ♡.
- **✕ Fewer like this**: Home shows fewer of that kind (with **Undo**); your Model only learns what you like.
- **↗ Open**, and **More in … ›** for its page.

Home learns what you enjoy: which kinds of card you open, vote up or read for a while, and which you scroll straight
past. It keeps room for every kind, one card in five for new territory 🔭, and never more than two of a kind in any
four. It's built only from what the other pages already keep, so scrolling never downloads anything and works offline;
what you open there also tells WISEP to keep those pages fresh first. **⏱ learning** at the top switches off the
time-on-screen part (taps, ♡, 🔖 and ✕ still count). Everything it learns stays on your devices (feed.json on the
computer, synced with your other computers like your Model).

**Moving around** (the panel and the phone): everything sits under six groups, **You, Grow, World, Circle, Repos
and Chances**.

On the computer, a **side rail** runs down the side of the panel nearest the screen's edge (on the right for a panel
on the right; **⚙ → Menu side** puts it always left or always right). Folded (46px), it shows the six groups' icons, each
with its "new" count on the corner, and the page you're on written down the side. **»** or an icon opens it (128px):
tap a group and its pages drop down under it; tap a page with parts (Data's fields, News' parts, Researchers' parts)
and they drop down under it; tap an open line again, or **‹** (or Esc), to go up a level. Every count sits on its
icon, open or folded. Unpinned, the rail opens over the page and folds itself after you pick one (**«**, Ctrl+\ or a
tap on the dimmed page folds it too); **📌** pins it beside the page, and myGeeKy remembers that. The line above the
page names where you are ("Chances › Jobs") in its group's colour. The open panel is 460px wide; drag its inner edge
(or **⚙ → Panel width**, 360-900px) to make it wider, and its bottom edge to make it taller.

On the phone the orbit zooms: the group you open flies to the centre with its pages around it, and "‹ Back to …",
the trail beside it, or the ↑ on the centre planet take you back. The heading always names the page and where it lives.

A small, translucent, always-on-top panel docked to the edge of your
screen (Windows and Linux), built with [PySide6/Qt](https://doc.qt.io/qtforpython-6/)
— native widgets, not a webview. (An earlier version used pywebview; its
WebView2-on-Windows transparency turned out to be a confirmed, currently
inconsistent upstream bug that even its maintainer can't reproduce reliably
across machines — see [pywebview#1611](https://github.com/r0x0r/pywebview/issues/1611).
Qt's `WA_TranslucentBackground` is the mature, well-supported way apps
actually get real per-pixel window transparency on Windows.) Click the
folded tab to expand it; click the arrow to fold it back to a slim strip.

- **Suggestions tab** — both lists from `mygeeky run` (avatar, bio, score),
  each with an **Open →** button that opens their GitHub profile in your
  browser. That's the *only* thing a click ever does — myGeeKy still never
  follows anyone; a "Refresh" button re-runs a real search on demand.
  People you open or already follow drop off, and older unseen suggestions
  move up to fill their place. Once the list is empty, the panel searches
  again by itself, but no more often than `gui_suggestions_auto_refresh_hours`
  (default 6; `0` turns it off), to stay well inside GitHub's rate limits.
- **Market tab** — the `mygeeky market` board: rank, ▲▼ places moved,
  stars (+ this week), PyPI downloads/week (± change), commits, and a
  green/red sparkline of weekly downloads (or commits for non-PyPI tools).
  Click a row to open the repo. It refreshes itself in the background.
- **Repos tab** — the results of `mygeeky contribute`: repos you could
  improve, each with why it fits you, its top starter issues, and
  **Fork →** / **Open →** buttons. Those buttons only open the GitHub page;
  forking and the PR stay yours. It shows the last run's results, and
  "Refresh" runs a new repo search only when you click it.
- **Activity tab** — a live feed of what people you follow are actually
  doing (pushes, merged PRs, new repos, releases, stars...), from GitHub's
  own events API, plus the recent activity of your best profile matches
  (your top `gui_activity_match_people` suggestions, scored against your
  CV, ORCID and repos), tagged "profile match". Grouped into one card per
  person with their latest action and a count; click a card to expand
  everything they did, or ↗ to open their profile. Strangers acting on
  repos of orgs you follow are filtered out. Refreshes automatically, but no
  more often than `gui_activity_refresh_minutes` (default 5) — about one API
  call per matched person, not a full search.
- **Model tab** — an animated ring with your model's cross-validated AUC and
  a plain-language grade, tiles for examples / follow-backs / follow-back
  rate / retrains, bars showing what the trained model rewards and
  penalizes, and a trend chart (hover a point for details) so you can watch
  it actually improve as you run `mygeeky bootstrap`/`learn`.

**⚙ Settings** — click the small gear icon in the header to open a compact
panel with:
- **Theme**, switchable live (no restart needed): **Midnight Glass** (dark,
  cool-toned, the default), **Frosted White** (light, warm,
  iOS-control-center-like), and **Vibrant Aurora** (saturated, colorful,
  leans into the geeky/hearts branding).
- **Transparency**, a slider from 0% (fully opaque) to 100% (fully
  transparent), applied live as you drag.

Both choices are saved (`gui_theme`, `gui_opacity`) and remembered next time
you open the panel.

Clicking a person in the Suggestions list (or a suggestion in the Live tab)
opens their profile and removes them from the list — they're added to your
excluded list, so later runs skip them too. People you follow from the browser
drop out on the next activity refresh (within `gui_activity_refresh_minutes`).

Folded, the panel shrinks to just the app icon on the screen edge,
half-transparent until you hover it. It always stays inside the screen it's
on, including on multi-monitor setups.

Config: `gui_dock_side` (`"right"`/`"left"`), `gui_expanded_width`,
`gui_folded_width`, `gui_folded_height`, `gui_folded_opacity`, `gui_panel_height_fraction`, `gui_activity_refresh_minutes`, `gui_suggestions_auto_refresh_hours`,
`gui_activity_limit`, `gui_theme` (`"midnight"`/`"frosted"`/`"aurora"`),
`gui_opacity` (`0.0`-`1.0`, note the settings panel's slider shows this
inverted, as "Transparency") — same `mygeeky config set` mechanism as
everything else.

No LLM/AI is used anywhere in the GUI (or the rest of myGeeKy) — the
suggestions, activity feed, and model chart are all built from the same
TF-IDF/logistic-regression pipeline the CLI uses, so there's no API cost
and nothing to configure to make it work. (There's deliberately no way to
plug in a Claude subscription either — that kind of auth is scoped to
Claude Code itself and isn't something a third-party tool can piggyback
on; if you ever want AI-written explanations, that'd be a separate opt-in
using your own API key or a local model, not something myGeeKy needs.)

*Rendering note: the panel is genuinely transparent (real per-pixel alpha,
confirmed on Windows 11), but it's a flat translucency, not a blurred
"frosted glass" effect — Windows' native DWM Acrylic/Mica backdrop was
tried and turned out to conflict with Qt's own transparency on tested
hardware, reliably making the window opaque instead, so it isn't wired up.
On Linux, real transparency depends on your compositor/window manager the
same way it does for any Qt app.*

## Always something new

myGeeKy remembers what you've already seen, so each tab keeps feeling fresh:

- **Seen** means a card was mostly on screen for about a second and a half while the panel was open, or you clicked it. Scrolling quickly past doesn't count.
- **New cards** carry a small dot, and each tab's planet shows how many new things wait there.
- **Seen things make room for new ones** when you next open the panel or switch tabs. Never while you're reading: nothing jumps under your mouse.
- **People and repos** you've seen rest for a week, then may come back. A person you clicked never comes back.
- **Market rows** you've seen move down for three days.
- **News, headlines, papers and models** are read once. A few already-read ones stay at the end, dimmed, so a tab you've finished isn't empty.
- **The Activity feed** is a timeline: nothing moves, and what you've seen is dimmed.
- **Something seen three times and never clicked** rests for a month.
- **When a tab runs low on new things,** myGeeKy looks for more on GitHub in the background: people at most every 6 hours, repos every 12. What it finds waits for your next visit to that tab.

What you've seen is kept in `seen.json` and syncs to your other computers with the rest of your data. Every rest period is a setting (see the table below).

## All parameters (adjustable, or leave at the defaults)

```bash
mygeeky config show
mygeeky config set max_followers 3000
mygeeky config set languages "Python, Rust, Go"
mygeeky config reset
```

<details>
<summary><strong>Full parameter table</strong> — every key, what it does, and its default</summary>

| Key | Meaning | Default |
|---|---|---|
| `languages` | languages you're looking for | `[]` (any) |
| `topics` | topics/interests you're looking for | `[]` (any) |
| `keywords` | extra free-text interests fed into matching | `[]` |
| `locations` | optional location filter | `[]` (any) |
| `min_followers` / `max_followers` | candidate follower-count range | `0` / `20000` |
| `max_following` | reject candidates following more than this (growth-hacking signal) | `500` |
| `min_public_repos` | minimum public repos a candidate must have | `2` |
| `require_followers_or_following` / `min_followers_gate` / `min_following_gate` | drop dormant/throwaway accounts with neither | `true` / `5` / `5` |
| `exclude_organizations` | skip org accounts | `true` |
| `exclude_already_following` | skip people you already follow | `true` |
| `exclude_users` | usernames to never suggest | `[]` |
| `seed_accounts` | candidates = followers of these well-known accounts | `[]` |
| `seed_repos` | candidates = stargazers of these `owner/repo` repos | `[]` |
| `include_own_stargazers` | candidates = people who starred your own repos | `true` |
| `include_second_degree` / `second_degree_sample` | candidates = who a sample of your followees follow (expensive) | `false` / `15` |
| `source_max_pages` | pages fetched per candidate source | `3` |
| `activity_check_top_n` | how many top-ranked candidates get the real per-repo activity check | `150` |
| `max_repo_push_age_days` / `recent_upload_days` / `min_maintain_span_days` | real activity QC thresholds | `365` / `120` / `60` |
| `domain_vocab_size` / `domain_highlight_count` | size of the auto-derived domain vocabulary / highlight list | `25` / `15` |
| `search_pages` | GitHub search pages scanned per query | `3` |
| `max_candidates_per_run` | cap on candidates evaluated per run | `60` |
| `max_suggestions_returned` | cap on follow-back suggestions shown per run | `15` |
| `similarity_threshold` | minimum blended score to be suggested | `0.08` |
| `content_similarity_weight` / `follow_back_ratio_weight` / `activity_weight` | heuristic scoring weights | `0.5` / `0.3` / `0.2` |
| `rate_limit_sleep_seconds` / `search_pause_seconds` | pacing for normal vs. GitHub's tighter search-API rate limit | `1.5` / `2.1` |
| `cv_path` / `orcid_id` / `scholar_id` | CV file, ORCID iD and Google Scholar user id used by `mygeeky profile refresh` | `""` / `""` / `""` |
| `include_domain_repo_people` / `domain_repo_terms` / `domain_repo_count` | candidates = owners/contributors of active repos matching your profile terms | `true` / `6` / `20` |
| `followback_min_ratio` / `followback_max_followers` | follow-back list only: skip accounts with following/followers below this, or more followers than this | `0.05` / `3000` |
| `contribute_extra_terms` | terms always searched by `contribute`, e.g. `gwas, snakemake` | `[]` |
| `contribute_min_stars` / `contribute_max_stars` | star range for repo suggestions | `10` / `20000` |
| `contribute_pushed_within_days` | a suggested repo must have been pushed to this recently | `90` |
| `contribute_queries` / `contribute_check_top_n` / `contribute_max_returned` | search terms used / repos given the maintainer check / results shown | `10` / `25` / `10` |
| `market_size` / `market_terms` | repos on the market board / profile terms searched to pick them | `25` / `8` |
| `market_min_stars` / `market_pushed_within_days` | a board repo needs this many stars and a push this recent | `50` / `180` |
| `market_pinned` | `owner/repo` always on the board, e.g. `snakemake/snakemake, chrchang/plink-ng` | `[]` |
| `market_ph_topics` / `market_ph_days` / `market_ph_size` | Product Hunt topics to read, how far back, and how many launches to show (needs `mygeeky auth producthunt`) | `developer-tools, open-source, github, artificial-intelligence, science, health` / `30` / `10` |
| `market_refresh_hours` | the panel re-snapshots the board once it's this old | `12` |
| `beacon_enabled` | set by `mygeeky beacon init`; signals are off until then | `false` |
| `beacon_status` | your status (`open-to-collab`, `learning`, `heads-down`, `seeking-reviewers`, `mentoring`) | `""` |
| `beacon_share_interests` | publish your topics/keywords/languages as interest tags in your beacon | `true` |
| `beacon_blocked` | people whose signals are never shown | `[]` |
| `beacon_daily_limit` / `beacon_gesture_ttl_days` | signals you can send per day / days before a signal expires | `20` / `90` |
| `beacon_refresh_minutes` / `beacon_max_users` | minimum minutes between re-reading beacons / beacons read per refresh | `30` / `60` |
| `interest_learning` / `interest_half_life_days` | learn from your clicks, follows, stars and forks / days until an action counts half | `true` / `30` |
| `explore_share` | share of every list kept for 🔭 new territory outside your interests | `0.2` |
| `trends_months` / `trends_size` / `trends_refresh_hours` | how recent a trending paper must be, papers per section, how often to refresh | `18` / `15` / `24` |
| `news_sources` / `news_size` / `news_refresh_hours` / `news_days` | where news comes from, how many items, how often to refresh, how far back | `arxiv, biorxiv, hackernews` / `25` / `6` / `7` |
| `check_for_updates` | check PyPI once a day and offer an **Update** button when a new version is out | `true` |
| `sync_repo` / `sync_auto` | private data repo (set by `sync init`) / whether `pipeline` pulls+pushes | `""` / `true` |
| `min_training_samples` | labeled examples needed before the ML model kicks in | `8` |
| `ml_blend_weight` | how much the learned model influences the final score once trained | `0.5` |
| `training_mass_follow_outlier` | exclude training examples from accounts following more than this | `3000` |
| `gui_dock_side` | which screen edge the live panel docks to (`"right"`/`"left"`) | `"right"` |
| `gui_expanded_width` / `gui_folded_width` / `gui_folded_height` | panel size in pixels, expanded vs. folded (the folded icon) | `380` / `76` / `76` |
| `gui_hearts_enabled` / `gui_hearts_interval_minutes` | a few small hearts drift up from the folded icon, fade and vanish (toggle in the panel's ⚙ settings) | `true` / `3` |
| `gui_folded_opacity` | folded icon's opacity (fully opaque while hovered) | `0.5` |
| `gui_panel_height_fraction` | panel height as a fraction of the screen height | `0.25` |
| `gui_activity_refresh_minutes` | minimum minutes between automatic activity-feed refreshes | `5` |
| `gui_activity_limit` | how many recent activity events to show | `30` |
| `gui_suggestions_auto_refresh_hours` | when the follow-back list is empty or running low on people you haven't seen, search again by itself if the last search is at least this old (`0` = only on Refresh) | `6` |
| `fresh_people_days` | a person you've seen (scrolled past, not clicked) may come back after this many days | `7` |
| `fresh_repos_days` | the same for repos to contribute to | `7` |
| `fresh_market_days` | a Market row you've seen moves down for this many days | `3` |
| `fresh_ignored_after` | seen this many times and never clicked... | `3` |
| `fresh_ignored_days` | ...then it rests this many days instead | `30` |
| `fresh_people_topup_hours` | look for more people in the background at most this often | `6` |
| `fresh_repos_topup_hours` | look for more repos in the background at most this often | `12` |
| `gui_theme` | glass style (`"midnight"`/`"frosted"`/`"aurora"`) | `"midnight"` |
| `gui_opacity` | whole-window transparency, adjustable via the ⚙ settings panel | `1.0` |

</details>

## Safety

- **No follow/unfollow code exists in this project.** `github_client.py`
  only implements read endpoints (`GET`). There is no method that calls
  `PUT /user/following/*`, so myGeeKy cannot follow anyone even by
  accident, regardless of what token scope you provide.
- **Your GitHub token is never written to a file.** It's requested with
  hidden input (`getpass`) and stored only in your OS's encrypted secret
  store via the [`keyring`](https://pypi.org/project/keyring/) package
  (Windows Credential Locker / macOS Keychain / Linux Secret Service).
  `mygeeky auth status` shows *where* it's coming from — never the value.
  An environment variable (`MYGEEKY_GITHUB_TOKEN`) is supported as an
  explicit, opt-in fallback for CI/agent contexts.
- **Token fallback to the GitHub CLI.** If no keyring token or env var is
  set, myGeeKy uses `gh auth token` when `gh` is logged in. This is still only
  used for GET requests.
- **Research trends** send only your topic ids, search terms and DOIs to
  OpenAlex (public and read-only); finding a repo's paper reads its public
  `CITATION.cff`/README.
- **News** sends only your search terms to arXiv, bioRxiv and Hacker News
  (public, read-only APIs). What you click is learned **locally**, as a few
  terms per action, and only syncs to your own private data repo.
- **Update checks** are one read-only request to PyPI's public API, at most
  once a day, carrying nothing about you. Updating only happens when you click
  **Update** or run `mygeeky update`.
- **Sync writes only to your own private data repo**, through `git`
  with your own credentials, never through myGeeKy's API client.
- **Beacons are the one opt-in write.** After `mygeeky beacon init`,
  myGeeKy writes `beacon.json`/`README.md` in your own public
  `mygeeky-beacon` repo, and nothing else. The writer has no parameter that
  could point it at another repo or file. It uses a second, fine-grained token
  scoped to that single repo, and never falls back to `gh`.
- **Minimal token scope.** myGeeKy only reads public profile/repo/follower
  data — create your token with **no scopes at all**, or a fine-grained
  token limited to read-only public repositories/followers. Never grant it
  write or admin scopes.
- All local state (config, CV text, suggestion history, the learned model)
  lives under your OS's standard config/data directories, not inside this
  project folder, so nothing personal ever ends up in a repo or a published
  package by accident.
- **The GUI follows the same rule.** `open_profile()` (the only thing a
  click in the panel can trigger) refuses to open anything that isn't a
  `https://github.com/...` URL, and there's no other code path from the
  panel to the network beyond the read-only suggestion/activity fetches
  described above, except the Signals tab's emoji buttons. Once you've run
  `mygeeky beacon init`, those publish to your own beacon repo.

## Using myGeeKy from an AI agent / script

Every result-producing command supports `--json`:

```bash
mygeeky run --json
```

<details>
<summary><strong>Example output shape</strong></summary>

```json
{
  "followback": [
    {
      "username": "example-geek",
      "profile_url": "https://github.com/example-geek",
      "score": 0.4123,
      "score_breakdown": {"heuristic": 0.41, "ml_proba": null, "blended": 0.41},
      "features": {
        "content_similarity": 0.31,
        "follow_back_ratio": 0.9,
        "activity_recency": 1.0,
        "shared_languages": 0.5,
        "shared_topics": 0.33
      },
      "domain_fit": 0.62,
      "followers": 120,
      "following": 140,
      "public_repos": 34,
      "bio": "...",
      "sources": ["search:language:Python followers:0..20000 ...", "starred_your_repo:you/tool"],
      "n_sources": 2,
      "timestamp": "2026-09-17T12:00:00+00:00",
      "list": "followback"
    }
  ],
  "domain_highlights": [
    { "...": "same shape, ranked by domain_fit instead of score", "list": "domain" }
  ]
}
```

</details>

An agent can read this list and *present* it to you — it should never be
wired up to auto-follow anyone; that defeats the entire point of this tool.

## How the "learning" works

<details>
<summary><strong>Bootstrapping, retraining, and how to read the AUC</strong></summary>

**Bootstrapping (day one):** `mygeeky bootstrap` looks at accounts you
*already* follow, checks (read-only) whether each one follows you back,
and logs `(features, followed_back)` as a training example immediately —
so the model has real data from the start instead of an empty cold start
that only grows by however many people you manually follow each week.

**Ongoing (weekly):** `mygeeky learn` compares your current GitHub
following list against a snapshot taken at the last check. Anyone new is a
person *you* chose to follow. It checks whether they followed back and
logs the same kind of training example.

In both cases: once there are at least `min_training_samples` examples
with both outcomes represented (excluding accounts following more than
`training_mass_follow_outlier`, a growth-hacking outlier that would
distort the model), a `scikit-learn` `LogisticRegression` model is trained
and its prediction is blended into future scores (`ml_blend_weight`
controls how much). myGeeKy reports the model's cross-validated AUC each
time it retrains, so you can judge how trustworthy it is rather than take
it on faith — with a small training set, treat it as directional, not
precise. This is intentionally simple and transparent rather than a black
box — you can inspect `score_breakdown` on every suggestion to see the
heuristic and learned components separately.

</details>

## Two lists, on purpose

`mygeeky run` produces a **followback** list (ranked by the blended
score above) and a **domain_highlights** list (ranked purely by
`domain_fit`, an auto-derived match to your CV/repo vocabulary,
independent of follow-back likelihood). These optimize for different
things: some of the best domain-specific matches — senior researchers,
niche maintainers — follow almost no one on GitHub, so the reciprocation
model correctly scores them low even though they may be the best actual
fit. Both lists go through the same activity-QC and bot/dormant filters.

## License

MIT — see [LICENSE](https://github.com/mygeeky/myGeeKy/blob/main/LICENSE).


## 💡 Ideas, problems and questions

Click **💡** at the top of the panel (or run `mygeeky idea "your idea"`). Pick *Idea*, *Problem* or *Question*,
write a line or two, and press **Open on GitHub**: your browser opens a ready-to-send issue in
[myGeeKy-ideas](https://github.com/mygeeky/myGeeKy-ideas), and you click **Submit**. Nothing is sent
until you do, and no token passes through myGeeKy. Issues there are public, so leave out tokens and private data.
