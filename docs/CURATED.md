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

## When someone reports a listing

Each card has a 🚩. It opens either:
- a prefilled issue in [mygeeky/myGeeKy-ideas](https://github.com/mygeeky/myGeeKy-ideas/issues?q=label%3Areport) (label `report`);
- or an email to support@mygeeky.org.

Check the listing. If it's fake or gone, delete it from the file. 👍 and 👎 never leave anyone's device: they only
teach that person's own model.

## Later: jobs posted by others

This is not built yet. The plan (ORCID and institutional-email sign-in, proof of hire, a trust score, a blacklist that
can be appealed) is in the maker's private notes.
