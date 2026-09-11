# Phase 1 Seed Corpus Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add an auditable seed corpus and validation tooling for international, Canadian, and Quebec business-failure cases.

**Architecture:** Keep curated records in CSV/JSON with normalized IDs, source metadata, cause assertions, and evidence quotes. Validate referential integrity and required provenance before loading into SQLite. Start with a small hand-reviewed corpus; do not scrape indiscriminately.

**Tech Stack:** Python 3.12 standard library, CSV/JSON, SQLite, pytest.

---

### Task 1: Add seed corpus format and validator

**Files:**
- Create: `data/curated/companies.csv`
- Create: `data/curated/outcomes.csv`
- Create: `data/curated/sources.csv`
- Create: `data/curated/cause_assertions.csv`
- Create: `data/curated/lessons.csv`
- Create: `scripts/validate_data.py`
- Create: `tests/test_validate_data.py`

Implement validation for required columns, unique IDs, foreign keys, allowed outcome/cause confidence values, and non-empty source URL for every cause assertion. Use only standard library.

Follow strict TDD: write tests, run them failing, implement, run all tests.

### Task 2: Add internationally sourced seed cases

Add at least 10 cases using founder/company primary postmortems where available, including Wesabe, RethinkDB, Tract, and Advisable. Every coded cause requires an evidence quote and source URL. Record uncertainty and use multi-label causes.

### Task 3: Add Canadian and Quebec seed cases

Add at least 5 Canadian/Quebec cases only where public evidence is adequate. Preserve French and English source titles where applicable. If a case lacks a directly attributable cause, record outcome and `unknown` rather than inventing a cause. Document coverage gaps.

### Task 4: Add SQLite loader and smoke tests

Create `scripts/load_sqlite.py` that loads curated CSVs into the schema and rejects invalid data. Add tests proving the database loads and cause assertions join to sources and companies.

### Task 5: Documentation and verification

Update README with exact commands for validation and loading. Run the full test suite, validate the corpus, inspect git diff, commit, and push.
