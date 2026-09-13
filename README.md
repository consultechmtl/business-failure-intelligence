# Business Failure Intelligence

An evidence-linked, open research database for learning from business and startup failures.

## Goals

- Separate business outcomes (shutdown, bankruptcy, acquisition, distress) from causes.
- Preserve primary evidence, quotations, source dates, and confidence.
- Combine qualitative post-mortems with official business-dynamics and bankruptcy data.
- Support Quebec/Canada coverage alongside international cases.
- Create a foundation for analysis and, later, a public insight application.

## Current status

Phase 0: schema and source registry. The project intentionally starts with a small, auditable data model before bulk ingestion.

## Data principles

1. A cause is multi-label, not a single definitive field.
2. Every cause must link to evidence or be marked as inference.
3. A post-mortem is not a representative population sample.
4. Shutdown, bankruptcy, acquisition, and distress are distinct outcomes.
5. Raw source data is preserved separately from normalized analytical tables.
6. Personal, confidential, and paywalled material is not copied into this repository.

## Repository layout

- `docs/` research plan, taxonomy, and source methodology
- `data/raw/` downloaded source snapshots (gitignored by default)
- `data/curated/` reviewed, shareable records
- `schema/` database schema and controlled vocabularies
- `scripts/` ingestion and validation tools
- `tests/` data-quality tests
- `app/` reserved for a later explorer/API

## First milestone

Build a reviewed seed set of 25-50 cases, including Quebec/Canadian cases, with at least one source quotation per coded cause. Do not claim completeness.

## Validate, load, query, and test

Run these commands from the repository root:

```sh
# Validate curated CSV records and their references.
python3 scripts/validate_data.py

# Build the SQLite database from the validated corpus.
python3 scripts/load_sqlite.py --db data/business_failure.sqlite

# Query loaded data with the Python standard library.
python3 -c "import sqlite3; connection = sqlite3.connect('data/business_failure.sqlite'); print(connection.execute('SELECT confidence, COUNT(*) FROM cause_assertions GROUP BY confidence ORDER BY confidence').fetchall())"

# Inspect evidence-linked warning signs in chronological order.
python3 -c "import sqlite3; connection = sqlite3.connect('data/business_failure.sqlite'); print(connection.execute('SELECT company_id, signal_code, observed_date, observed_text FROM warning_signs ORDER BY observed_date IS NULL, observed_date, company_id').fetchall())"

# Load a temporary SQLite database and print descriptive corpus summaries.
python3 scripts/analyze_corpus.py

# Run the standard-library test suite.
python3 -m unittest discover -s tests -v
```

The analysis is descriptive of the reviewed seed corpus, not a population failure-rate estimate. See [docs/analysis.md](docs/analysis.md) for limits on interpretation and the distinction between source evidence and analyst inference.

## License

Code and schema: MIT. Source content remains subject to its original license and terms. See `docs/data-governance.md`.
