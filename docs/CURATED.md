# Curated lists: verified jobs, funding, conferences and learning resources

myGeeKy's 🎯 **Chances** planet (verified jobs, funding, conferences) and the 📚 **Learn** part of 🌱 **Grow** show lists
that myGeeKy's maker adds **by hand**, after checking each item is real. They all live in one file:

```
src/mygeeky/data/curated.json
```

Every myGeeKy (computer and phone) downloads that file at most every few hours and matches it to its user **on the
user's own device**. Nobody, not the maker and not the poster, learns who matched what, or who looked.

## Adding something

1. Open `src/mygeeky/data/curated.json` (on GitHub: the pencil icon, or locally in an editor).
2. Add an item to the right list. Copy an example below, and give it a **new id** (3-80 lowercase letters, digits or
   dashes, e.g. `oslo-postdoc-finemapping-2026`).
3. Check it: `python -m mygeeky.curated check src/mygeeky/data/curated.json` (prints `ok`, or what to fix).
4. Optional: `python -m mygeeky.curated stamp src/mygeeky/data/curated.json` gives the file a new version.
   Apps take the newest version, and a fetched copy also wins a tie, so forgetting this is fine.
5. Commit to `main`. Within a few hours every myGeeKy shows it.

Then the daily **Curated lists** workflow (`.github/workflows/curated-lists.yml`):
- checks the file;
- **removes anything past its deadline** (the apps already hide it the day after);
- keeps the phone app's copy (`mobile/src/data/curated.json`) the same.

## English only (jobs, funding, conferences)

A listing is shown to people in **English**, whatever language the board it came from is in. The French
bioinformatics society's board, for instance, is read for its English posts and its French ones are left
where they are.

The test counts function words rather than guessing from accented letters, so a post written in English at
the *Université de Paris* still counts as English, while one full of *de*, *pour*, *la* does not. A short
title that marks neither language ("Computational Biologist") is kept rather than thrown away.

It is enforced in `curated.clean_item`, which every route goes through — the scout, this file edited by
hand, and anything else — so a non-English listing cannot reach the lists by any path. The scout says
"not in English" when it drops one, rather than dropping it silently. **Learning resources are not
filtered this way**: a good course in another language is still a good course.

## The four lists

**Rules for every item:**
- `id`, `title` and `url` are required.
- Only `https://` links are kept.
- Keep `summary` to one or two sentences.
- `keywords` are what the matching uses, besides the title and summary. Use the words people in that field use:
  `gwas`, `single-cell`, `fine-mapping`.

### `jobs`: verified jobs

```json
{"id": "oslo-postdoc-finemapping-2026", "type": "postdoc",
 "title": "Postdoc in statistical genetics and fine-mapping",
 "org": "University of Oslo", "place": "Oslo, Norway", "remote": false,
 "url": "https://example.org/the-real-job-page",
 "deadline": "2026-12-01",
 "keywords": ["gwas", "fine-mapping", "statistical genetics"],
 "summary": "Two years, funded. Fine-mapping of GWAS loci across ancestries."}
```

- **`type`** is one of: `phd`, `postdoc`, `master`, `job`, `internship`, `fellowship`, `faculty`, `engineer`.
- **`deadline` is required**, as `YYYY-MM-DD`. The job disappears the day after it.
- **Before adding**, check the job is real. Good evidence:
  - the institution's own page;
  - a named contact person with an institutional email address;
  - an official job portal.

### `funding`: grants, fellowships, scholarships, travel grants

```json
{"id": "esgh-travel-2027", "title": "Early-career travel grant",
 "org": "Example Society", "url": "https://example.org/travel-grants",
 "deadline": "2027-01-15", "who": "PhD students and postdocs up to 5 years after the PhD",
 "amount": "up to 1,500 EUR", "keywords": ["genetics"],
 "summary": "For presenting your work at a conference."}
```

### `conferences`

```json
{"id": "example-genomics-2027", "title": "Example Genomics Meeting 2027",
 "place": "Lisbon, Portugal", "url": "https://example.org/meeting",
 "deadline": "2027-02-01", "starts": "2027-05-10", "ends": "2027-05-13",
 "student": "half-price registration, 20 travel awards",
 "keywords": ["genomics", "gwas"]}
```

`deadline` is the date it should leave the list: usually the abstract deadline, or the last day to register.

### `resources`: learning resources (no deadline)

```json
{"id": "nextflow-training", "type": "tutorial", "level": "beginner", "free": true,
 "title": "Nextflow training", "url": "https://training.nextflow.io/",
 "skills": ["nextflow", "workflow management", "docker"],
 "keywords": ["pipelines", "bioinformatics"],
 "summary": "Official Nextflow training: write, run and scale reproducible pipelines."}
```

- **`type`** is one of: `repo`, `website`, `course`, `book`, `tutorial`, `video`.
- **`level`** is one of: `beginner`, `intermediate`, `advanced`.
- **`skills`** connects a resource to **Rising Skills** and **Learning paths**: a path's "Learn the basics" and
  "Go deeper" steps come from here.
  - Use names from the skills dictionary (`src/mygeeky/data/skills.json`), in lowercase.
  - The test suite checks every tag is a known skill.

### `protocols`: reviewed protocols

A protocol turns a skill into ordered stages, each with links and a level check. For skills that have no reviewed
protocol, the app builds one itself from GitHub and papers.

```json
{"id": "r-data-analysis", "skill": "R", "goal": "data analysis", "title": "R for data analysis",
 "summary": "From your first R script to a full analysis.",
 "stages": [
  {"id": "basics", "title": "R basics", "role": "basics",
   "can": ["I can read a CSV file into a data frame"],
   "quiz": [{"q": "What does c(1, 2, 3) * 2 return?", "options": ["1 2 3 1 2 3", "2 4 6", "an error"], "answer": 1}],
   "items": [{"title": "R for Data Science (2e)", "url": "https://r4ds.hadley.nz/", "kind": "book",
              "note": "The free classic."}]},
  {"id": "use", "title": "Use it in your own work", "role": "use", "items": []}]}
```

- **`skill`** is a name from the skills dictionary. Any alias finds it (`rstats` finds `R`).
- **No laboratory work** (`src/mygeeky/safety.py`). A protocol whose skill, goal, title or summary names a bench
  technique is refused when the file is read, and so is any link from a protocol repository, protocol journal or
  supplier method library — in the curated file, in a protocol a user published, and in one built on a device.
  `tools/protocols/merge.py` removes such a protocol from the file and says so. Analysis of data an experiment
  produced is welcome; the bench steps that produced it are not myGeeKy's to give.
- **`role`** is one of `basics`, `deeper`, `applied`, `project` or `use`.
  - The `use` stage ticks itself when one of the user's repos shows the skill.
  - The other roles decide how the user's own repos count as evidence.
- **`query`** (optional) adds words to that stage's evidence check, and to its searches when the app fills an
  empty stage. Example: `"statistics"`.
- **The level check:**
  - **`quiz`:** multiple choice, where `answer` is the position of the right option (0 = the first). Passing at 75%
    marks the stage as known.
  - **`can`:** "I can do these" statements, used when there's no quiz.
- **`kind`** for a link is one of `repo`, `article`, `website`, `course`, `book`, `tutorial`, `video` or
  `guide` (📘 a project's or tool's own documentation). An `article` may also carry `venue` (the journal),
  which its card shows.
- **A `project` stage with no links** is filled with real repos from the user's own field.

### Protocols users publish

Users can change any protocol (reorder, rename, add and remove stages and links) and 📤 publish it. Publishing opens
a prefilled issue in [mygeeky/myGeeKy-ideas](https://github.com/mygeeky/myGeeKy-ideas/issues), with a title starting
**🧭 Protocol:**. The issue holds:
- the stages and their links;
- the links the user removed from an auto-built one, which teach the model what *not* to pick.

It never holds anyone's progress, checks or answers. To collect them:

```
python -m mygeeky.protocols harvest      # -> tools/protocol_model/published.jsonl
```

To make a published protocol reviewed:
1. Check it.
2. Copy its JSON into `protocols` here.
3. Give it a question bank with the admin tab's **📝 Write questions** ([QUIZZES.md](QUIZZES.md)).

**Writing reviewed protocols by hand** (how the current 19 were made):

```
python tools/protocols/draft.py          # optional: drafts from the app's own builder, to start from
# then write them properly in tools/protocols/reviewed.json
python tools/protocols/merge.py --check  # every link must open; dead ones are named
python tools/protocols/merge.py          # writes curated.json and the phone's copy
```

`merge.py` keeps a link that only *robots* are refused (403, or a timeout) and drops one that is really gone (404).
The auto-built drafts were not good enough for the lab and computer-science protocols, which is why those were
written by hand: "reviewed" means the maker read it.

Every harvested protocol also becomes training data for the next model (see `tools/protocol_model/README.md`).

## Finding listings with DeepSeek (the admin tab)

Instead of writing each item by hand, the maker's **🎯 Listings to review** section (in the admin tab) finds them:

1. **🔑 Add DeepSeek key**, once. It's kept in the system's credential store, never in a file.
2. **🌐 Sites and field.** The sites to look through, one per line (`jobs | jobs.ac.uk | https://…`), and what
   counts as your field.
3. **🔎 Find new listings.**
   - myGeeKy reads each site's listing page. DeepSeek picks the links that are single, relevant, open listings, by
     their number, so it can't invent a link.
   - myGeeKy reads each listing's own page. DeepSeek extracts the fields and quotes the sentence that gives the
     deadline.
   - myGeeKy then checks DeepSeek's answer itself: the title is on the page, the quote is on the page and holds
     the deadline's date, the deadline is at least 3 days away, it's on the site it was listed on, and it fits your
     field.
   - Hard failures are dropped. The rest are ranked by "% sure": DeepSeek's confidence × the checks passed.
4. **Review.** ✓ Accept, ✏️ Edit (then accept), or ✕ Reject. Rejected ones are never offered again.
5. **🚀 Publish.**
   - It adds every accepted listing to `curated.json` on GitHub's **main** branch, in one commit, with your own
     git login, from a fresh temporary copy. Your own checkouts aren't touched.
   - Every myGeeKy shows them within a few hours. Each disappears after its deadline.

Nothing goes online until you press Publish.

## When someone reports a listing

Each card has a 🚩. It opens either:
- a prefilled issue in [mygeeky/myGeeKy-ideas](https://github.com/mygeeky/myGeeKy-ideas/issues?q=label%3Areport) (label `report`);
- or an email to support@mygeeky.org.

Check the listing. If it's fake or gone, delete it from the file. 👍 and 👎 never leave anyone's device: they only
teach that person's own model.

## Later: jobs posted by others

This is not built yet. The plan (ORCID and institutional-email sign-in, proof of hire, a trust score, a blacklist that
can be appealed) is in the maker's private notes.
