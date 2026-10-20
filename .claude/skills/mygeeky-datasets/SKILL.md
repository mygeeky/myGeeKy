---
name: mygeeky-datasets
description: Use when adding, reviewing, harvesting or changing myGeeKy's training datasets (Grow → Data, src/mygeeky/data/datasets.json, datasets_core.json, src/mygeeky/datasets.py, the datasets workflow), or when deciding whether a dataset may be shown. Holds the acceptance rules every dataset must pass, the sources myGeeKy harvests (Zenodo, GEO curated DataSets, OpenML) and how the list is updated.
---

# myGeeKy datasets: what we accept, and how the list grows

Grow → 🗂️ Data lists public datasets people can **practise and train on**: small enough for a laptop, open,
documented, and downloadable with one click. It is a hand-checked core plus records harvested from trusted
sources, all passing the same rules. `datasets.accept()` enforces the hard rules in code; the judgement rules
below are for a person (or Claude) adding to the core.

## The acceptance rules

A dataset is shown only if **all** of these hold. `accept(record)` returns the rules a record breaks (empty =
accepted); `python -m mygeeky.datasets check` prints them for the whole list.

1. **Open licence.** CC0, CC-BY (any version), CC-BY-SA, ODbL, ODC-By, PDDL, public domain (incl. US-government
   data: NCBI, NOAA, NASA, USGS, CDC), or an OSI licence (MIT, BSD, Apache). CC-BY-NC is accepted but marked
   "non-commercial". No licence stated = rejected.
2. **One click, no gate.** A direct download or an open landing page with download links. Rejected: anything
   behind a login, registration, application or data-access committee (dbGaP, UK Biobank, MIMIC, Kaggle,
   Materials Project API keys, EGA).
3. **Laptop-sized.** Total ≤ 5 GB, and a starter file ≤ 1 GB that is enough to begin. Bigger collections are
   accepted only with a named starter subset (e.g. "chromosome 22").
4. **Common formats.** CSV/TSV/TXT, JSON, Excel, Parquet, HDF5/h5ad/loom, MTX, FASTA/FASTQ, VCF, BED/GFF, PDB/mmCIF,
   SOFT, ARFF, FITS, NetCDF, images (PNG/JPG/TIFF), or archives of these. Proprietary-only formats are rejected.
5. **Documented.** At least 120 characters saying what it is, how it was made and what the columns or files
   hold, or a paper/README that does.
6. **Stable and citable.** A DOI or a stable accession (Zenodo DOI, GEO GDS/GSE, OpenML id, UCI id, PDB id) or
   a long-lived institutional URL (an agency, a consortium, a university group). No personal file shares.
7. **Validated or used.** Curated by its source (GEO DataSets are curated by NCBI; OpenML-CC18 is a vetted
   benchmark suite; the Galaxy Training Network's data is built for tutorials), or clearly used: Zenodo
   downloads ≥ 300, or a well-known teaching dataset in the core.
8. **No personal data.** Nothing that identifies a person. Human data only if it is de-identified and open by
   its own terms.
9. **Teaches something.** It says what to practise (`why`: one plain line, e.g. "clustering and marker genes on
   3,000 blood cells") and its level: beginner, intermediate or advanced.
10. **One field** from `datasets.FIELDS`, and the skills it teaches named with `data/skills.json` names where they
    exist (the app ranks by them).

## Sources

- **The core** (`src/mygeeky/data/datasets_core.json`): hand-picked classics across the sciences, each checked
  against the rules above. Add here when a dataset is famous for teaching (PBMC 3k, the Palmer penguins, MNIST,
  Mauna Loa CO2). The builder checks every core URL still answers.
- **Zenodo** (`zenodo.org/api/records`, no key, 30 requests a minute): the Galaxy Training Network community
  (`communities=galaxy-training`), plus per-field searches for "training data", "tutorial dataset", "benchmark
  dataset", `type=dataset`, `sort=mostviewed`. Loose search: a record must also pass rule 7 (downloads ≥ 300)
  and mention its field's words.
- **GEO DataSets** (NCBI E-utilities, `db=gds`, `GDS[ETYP]`): curated expression sets, each with a SOFT file
  download. Searched per organism/topic (human disease, mouse, Arabidopsis, rice, yeast, E. coli...).
- **OpenML** (`openml.org/api/v1/json`): the OpenML-CC18 suite (vetted classification tasks), ARFF/CSV
  downloads.

## Updating

- `python -m mygeeky.datasets build` re-harvests, keeps the core, drops anything that now fails a rule, and
  writes `src/mygeeky/data/datasets.json` and the phone's identical copy (`mobile/src/data/datasets.json`).
- `.github/workflows/datasets.yml` runs it every week and commits a change; every myGeeKy then reads the newest
  file from GitHub (at most once a day) and falls back to the one it shipped with.
- Changing a rule: change `datasets.accept()` and this file together, and `tests/test_datasets.py`.
- The phone shows the same list (`mobile/src/lib/datasets.ts`, the same cleaning and ranking:
  `tests/test_datasets.py` checks both agree).

## What a record looks like

```json
{"id": "pbmc3k", "title": "PBMC 3k: 2,700 blood cells (10x Genomics)", "field": "Biology & genomics",
 "why": "clustering, marker genes and cell types on a small single-cell set", "level": "beginner",
 "skills": ["Single-cell RNA-seq", "Scanpy", "Seurat"], "source": "10x Genomics", "url": "https://...",
 "download": "https://.../pbmc3k_filtered_gene_bc_matrices.tar.gz", "size_mb": 7, "formats": ["MTX"],
 "license": "CC-BY-4.0", "doi": "", "tutorial": "https://scanpy-tutorials.readthedocs.io/...", "uses": 0,
 "checked": "2026-10-20"}
```
