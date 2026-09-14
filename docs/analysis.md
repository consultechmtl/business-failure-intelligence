# Analysis notes

`python3 scripts/analyze_corpus.py` produces descriptive counts from the reviewed
seed corpus after loading it into a temporary SQLite database. It reports coded
cause assertions by confidence, company cases by country/region, and a
Canada/Quebec/international comparison.

These are curated-corpus frequencies, not population failure rates. The corpus
is deliberately small, evidence-constrained, and not sampled to represent all
business failures. Differences in public reporting, surviving sources, language,
and inclusion criteria can affect every count.

The database preserves evidence separately from interpretation. An evidence
quote and its source support a cause assertion; the assertion type, confidence,
and analyst note record the degree and nature of interpretation. A count of
assertions is therefore not proof that a cause is more prevalent or causally
more important outside this corpus. Use the analysis to inspect the reviewed
cases and their coverage, then follow the linked sources before drawing a
conclusion.

## Warning-sign timelines

`warning_signs` stores short, source-linked observations that may be useful for
case timelines. A warning sign is not a proven cause or a predictive model.
`observed_date` is populated only when the linked source supports a specific
date; missing dates sort after dated observations.

```sql
-- Inspect one case's evidence-linked warning signs in timeline order.
SELECT warning.signal_code, warning.observed_date, warning.observed_text,
       source.source_url, warning.confidence
FROM warning_signs AS warning
JOIN sources AS source ON source.source_id = warning.source_id
WHERE warning.company_id = 'target-canada'
ORDER BY warning.observed_date IS NULL, warning.observed_date, warning.warning_id;

-- Count reviewed warning signs by signal and confidence.
SELECT signal_code, confidence, COUNT(*) AS warning_count
FROM warning_signs
GROUP BY signal_code, confidence
ORDER BY warning_count DESC, signal_code, confidence;
```

Use these records to navigate back to the cited evidence, not to infer when a
signal first appeared or that it caused the final outcome.

## Intelligence API interpretation

The read-only API exposes stored records and deterministic descriptive counts;
it does not calculate failure probabilities, rank causes by causal importance,
or supply counterfactual explanations. `/causes` groups **assertions**, so one
company can contribute multiple entries and an assertion may be an analyst
inference rather than a primary statement. `/geographies` groups only the
geography fields present in reviewed records; `unknown` means coverage is
incomplete, not that a company had no geography. The Quebec comparison contrasts
reviewed Quebec cases with non-Canadian or unlocated cases and is not a matched
international benchmark. Inspect each case's `sources`, `assertions`, confidence,
and assertion type before reusing a count or lesson.

The API intentionally has no authentication or write endpoints. It rebuilds its
default SQLite file from validated curated CSVs for reproducibility, but callers
using `--db` are responsible for the provenance and freshness of that database.

## Aggregate intelligence API

The `/aggregate/*` routes are read-only views of `aggregate_observations`, not
views of the narrative corpus. They attach dataset/table provenance (including
publisher, source URL, retrieval date, definitions, and extraction criteria),
reference-period coverage, UOM, status flags, and the same interpretation
disclaimer on every response.

```sh
curl http://127.0.0.1:8000/aggregate/summary
curl 'http://127.0.0.1:8000/aggregate/trends?geo=Quebec&dynamics=Closures'
curl 'http://127.0.0.1:8000/aggregate/by-size?geo=Quebec'
curl 'http://127.0.0.1:8000/aggregate/by-industry?geo=Quebec&employment_size=1%20to%204%20employees'
curl 'http://127.0.0.1:8000/aggregate/comparison?geo=Canada&period_start=2026-01&period_end=2026-03'
```

### Cross-layer comparison

`/aggregate/comparison` is a co-presentation endpoint, not a harmonized
failure-rate dataset. It requires `geo=Quebec` or `geo=Canada` and accepts
optional inclusive `period_start`/`period_end` values in `YYYY-MM`. The response
keeps three result collections separate: Statistics Canada `openings`,
Statistics Canada `closures`, and OSB `osb_insolvencies.rows`. Each layer has
independent dataset provenance, source tables, period coverage, and units.

The endpoint does not join, sum, normalize, compare as a common denominator, or
divide OSB insolvencies by Statistics Canada closures. OSB BIA proceedings and
Statistics Canada business-dynamics closures have incompatible definitions,
populations, and measurement processes. The response explicitly makes no causal
interpretation; it cannot show that an opening, closure, or insolvency caused
another observation or a narrative-company outcome.

`geo`, `dynamics`, and `employment_size` are validated against values stored in
the loaded aggregate data. An invalid value returns `404`; unsupported,
duplicate, blank, or out-of-range query parameters return `400`. Results are
ordered deterministically and optional `limit` is bounded to 1–500.

## Founder-profile insight API

`/insights/profile` provides founder-selected context without converting the
corpus into a score or causal model:

```sh
curl 'http://127.0.0.1:8000/insights/profile?geo=Quebec&industry=Electric%20vehicles&business_model_code=vehicle-manufacturing&employment_size=1%20to%204%20employees&limit=20'
curl 'http://127.0.0.1:8000/insights/profile?geo=Canada&industry_code=financial-technology&limit=10'
```

It requires `geo` and an exact normalized `industry_code` or normalized industry
label. Optional normalized `business_model_code` narrows narrative cases only;
optional `employment_size` narrows Statistics Canada context only. `geo` applies
to all three layers, while OSB has no industry or business-model filter in this
endpoint. This is intentional: taxonomy codes from reviewed narrative cases are
not a crosswalk to StatCan NAICS and OSB proceeding tables do not supply the
profile dimensions needed for a valid match.

The response has separately labeled `statistics_canada`, `osb_insolvencies`,
and `narrative_cases` collections plus evidence-linked `warning_signs` and
`causes` for the returned cases. Empty warning/cause collections mean no matching
reviewed evidence exists; they are not filled by inference. Ordering is
deterministic. Consult `docs/specs/founder-insights.md` for request validation
and response boundaries.

This endpoint does not predict failure, assign a risk score, join or total the
layers, calculate a rate, or claim a warning sign/cause applies beyond its cited
case. StatCan closures are not necessarily permanent deaths, and OSB proceedings
are not all failures or permanent closures. The narrative corpus is
non-representative and publication-biased.

### Safe language

Describe these as **Statistics Canada business-dynamics observations** or
**published openings/closures**. Do not relabel a closure as a business death,
permanent closure, failure, insolvency, bankruptcy, or cause. A Statistics Canada
closure is not necessarily any of those things, and an aggregate count cannot
identify why a company failed. Do not merge these counts with the reviewed
narrative cases or use them to estimate causal prevalence.
