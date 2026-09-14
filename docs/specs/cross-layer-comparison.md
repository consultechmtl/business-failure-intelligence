# Cross-layer comparison

## Goal

Expose a read-only co-presentation of Statistics Canada business-dynamics
openings/closures and Office of the Superintendent of Bankruptcy (OSB) BIA
insolvency proceeding observations without converting them into a common failure
measure.

## Endpoint

`GET /aggregate/comparison?geo=Quebec|Canada&period_start=YYYY-MM&period_end=YYYY-MM&limit=1..500`

- `geo` is required and limited to `Quebec` or `Canada`.
- `period_start` and `period_end` are optional, inclusive, validated calendar
  months; reversed ranges return `400`.
- `limit` defaults to 500 and bounds each separately returned collection.
- Unknown supported geography returns `404`; malformed, blank, duplicate, or
  unsupported parameters return `400`.

## Response contract

The response has independent `statistics_canada` and `osb_insolvencies` objects.
Statistics Canada contains separately labeled `openings` and `closures`; OSB
contains `rows`. Every layer provides its own source-table/dataset provenance,
reference-period coverage, and units. Stable SQL ordering makes repeated
responses deterministic.

`metadata` states that definitions are incompatible, causal interpretation is
`none`, and that the endpoint neither joins nor sums layers, assigns either as
the other’s denominator, nor calculates rates. In particular, OSB insolvencies
must not be divided by Statistics Canada closures unless a future explicit
request documents both the analytical purpose and the denominator choice.

## Non-goals

- No curated data, schema, or narrative-company record changes.
- No failure, insolvency, closure, survival, or causal rate.
- No linkage between OSB observations, Statistics Canada observations, or
  narrative company cases.

## Risk and rollback

This is a public read-only query surface with bound SQL values after allow-list
validation. Roll back by reverting the feature commit; it does not mutate data.

## Test plan

Unit and endpoint tests cover Quebec and Canada queries, deterministic output,
separate-layer labels/collections, source provenance, invalid geography, invalid
or reversed dates, and invalid limits.
