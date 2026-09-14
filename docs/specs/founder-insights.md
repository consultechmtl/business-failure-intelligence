# Founder profile insights

## Goal
Provide a read-only `GET /insights/profile` response that co-presents compatible official aggregate context, separately labeled OSB proceeding context, and evidence-linked narrative cases for a founder-selected profile.

## Inputs
- Required: `geo=Quebec|Canada` and one of `industry_code` or `industry`.
- Optional: `business_model_code`, `employment_size`, `limit` (1–100; default 20).
- Codes must exist in normalized vocabularies. Industry text is matched case-insensitively against normalized English/French labels (or the code); unknown recognized filters return 404. Conflicting `industry_code` and `industry`, malformed, duplicate, blank, and unsupported inputs return 400.

## Output and boundaries
The response contains `requested_profile`, `statistics_canada`, `osb_insolvencies`, `narrative_cases`, `warning_signs`, `causes`, `provenance`, and `caveats`.

Statistics Canada rows are filtered only by compatible dimensions: requested geography and employment size; its NAICS values are not equated with narrative taxonomy codes. OSB has no compatible industry/business-model dimension in this endpoint and remains separately labeled and geo-filtered. Narrative cases require every supplied normalized dimension that can be evidenced (industry, optional business model, and geography); Canada includes Canadian cases and Quebec includes Quebec cases.

No score, probability, forecast, rate, ranking, causal claim, joins, sums, or common denominator are returned. Narratives are non-representative; case evidence does not establish population prevalence or causation.

## Risk and rollback
This is a read-only query over existing schema/data; no migration or curated-data change. Roll back by reverting the endpoint/function commit.

## Verification
Unit tests cover deterministic matching, geography/business-model filtering, layer separation, and invalid input status. Full validation, database load, API smoke requests, compilation, and diff checks are required before release.
