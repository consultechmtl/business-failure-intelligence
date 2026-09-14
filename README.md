# Business Failure Intelligence

An evidence-linked, open research database for learning from business and startup failures.

## Goals

- Separate business outcomes (shutdown, bankruptcy, acquisition, distress) from causes.
- Preserve primary evidence, quotations, source dates, and confidence.
- Combine qualitative post-mortems with official business-dynamics and bankruptcy data.
- Support Quebec/Canada coverage alongside international cases.

## Data principles

1. A cause is multi-label, not a single definitive field.
2. Every narrative cause links to evidence or is marked as inference.
3. A post-mortem is not a representative population sample.
4. Shutdown, bankruptcy, acquisition, and distress are distinct outcomes.
5. Raw source data is preserved separately from normalized analytical tables.
6. Official aggregate observations are never related to narrative companies.

## Repository layout

- `data/raw/`: downloaded source snapshots (gitignored)
- `data/curated/`: reviewed narrative records and compact official-statistics metadata/extracts
- `schema/`: SQLite schema and controlled vocabularies
- `scripts/`: validation, loading, normalization, and analysis tools
- `tests/`: standard-library `unittest` quality checks

## Aggregate Statistics Canada layer

The additive aggregate layer contains `datasets`, `sample_frames`,
`observation_units`, `outcome_definitions`, and `aggregate_observations`.
It intentionally has no `company_id`: Statistics Canada aggregate data and
narrative company cases are different evidence types.

Table 33-10-0722-01 source:
`https://www150.statcan.gc.ca/n1/tbl/csv/33100722-eng.zip`

Optional table 33-10-0270-01 source:
`https://www150.statcan.gc.ca/n1/tbl/csv/33100270-eng.zip`

The normalizer filters to GEO `Canada` and `Quebec`, preserving reference
period, GEO, Industry/NAICS, employment size (or an explicit unavailable marker
when a source table has no such dimension), business dynamics, UOM, VALUE,
STATUS, table number, source URL, and retrieval date. It retains all available
Industry/NAICS and employment-size categories and only `Openings`/`Closures`
with a VALUE. The 2026-09-13 extracts originate from the official archives
provided at `/mnt/c/Users/Executor/Downloads/33100722-eng.zip` and
`/mnt/c/Users/Executor/Downloads/33100270-eng.zip`; raw ZIPs remain outside git.

“Closures” is Statistics Canada's published business-dynamics label. It is
**not** an assertion of permanent enterprise death, insolvency, bankruptcy, or
a cause of failure.

## OSB aggregate insolvency layer

Official OSB workbook source: `https://ised-isde.canada.ca/site/office-superintendent-bankruptcy/sites/default/files/documents/insolvency_statistiques_insolvabilite_march_2026.xlsx`.

The March 2026 workbook was downloaded and ZIP-verified on 2026-09-14; SHA-256 is recorded in `docs/data-sources.md`. Its raw `.xlsx` is gitignored in `data/raw/`. The additive `osb_insolvency_observations` table is not company-linked and preserves period, province/Canada, consumer/business debtor type, business form, bankruptcy/proposal proceeding type, NAICS sector when supplied, unit, published status, and provenance.

OSB BIA insolvency proceedings are **not equivalent to all business failures or permanent closure**. Do not combine or sum them with Statistics Canada closure observations or narrative cases; they are distinct outcome layers and do not establish causes.

## Validate, load, normalize, analyze, and test

Run from the repository root:

```sh
python3 scripts/validate_data.py
python3 scripts/load_sqlite.py --db data/business_failure.sqlite
python3 scripts/analyze_corpus.py
python3 scripts/analyze_aggregate.py

# A complete ZIP is required; raw archives remain gitignored.
python3 scripts/normalize_statcan.py data/raw/33100722-eng.zip \
  --table 33100722 --retrieval-date YYYY-MM-DD
python3 scripts/normalize_osb_insolvencies.py \
  data/raw/insolvency_statistiques_insolvabilite_march_2026.xlsx \
  --retrieval-date YYYY-MM-DD

python3 -m unittest discover -s tests -v
```

The aggregate analysis reports available Canada-vs-Quebec opening/closure
observations by employment size. An empty normalized extract produces a clear
empty-state message rather than fabricated values.

## Aggregate API

Start the read-only server with an explicitly loaded database:

```sh
python3 app/server.py --db data/business_failure.sqlite --port 8000
```

```sh
curl http://127.0.0.1:8000/aggregate/summary
curl 'http://127.0.0.1:8000/aggregate/trends?geo=Quebec&dynamics=Closures'
curl 'http://127.0.0.1:8000/aggregate/by-size?geo=Quebec'
curl 'http://127.0.0.1:8000/aggregate/by-industry?geo=Quebec&employment_size=1%20to%204%20employees'
curl 'http://127.0.0.1:8000/aggregate/insolvencies?geo=Quebec&period=2026-03&type=Bankruptcy'
```

All aggregate responses include source dataset/table provenance, source URL and
retrieval date, available reference-period coverage, UOM, status flags, and the
Statistics Canada interpretation disclaimer. Query parameters are allow-listed;
unknown `geo`, `dynamics`, or `employment_size` values return `404`, while
malformed, duplicate, or out-of-range query parameters return `400`. `limit` is
optional and bounded to 1–500 (default 500).

Use safe language: call values **Statistics Canada business-dynamics
observations** or **published closures/openings**, not business deaths, failures,
insolvencies, bankruptcies, or causal findings. In particular, a Statistics
Canada closure is not necessarily a permanent enterprise death, an insolvency,
or evidence of why a business failed. Aggregate observations remain separate
from narrative company cases.

## License

Code and schema: MIT. Source content remains subject to its original licence
and terms. Statistics Canada source reuse is governed by the Statistics Canada
Open Government Licence - Canada; see the source data and `datasets.csv`.
