# Aggregate Intelligence API

**Goal:** Expose read-only, provenance-rich Statistics Canada aggregate queries without linking aggregate observations to narrative company records.

## Acceptance criteria

- `/aggregate/summary`, `/aggregate/trends`, `/aggregate/by-size`, and `/aggregate/by-industry` return deterministic JSON.
- Every aggregate response includes Statistics Canada dataset/table provenance, reference-period coverage, UOM, status flags, and a closure interpretation disclaimer.
- Geography and dynamics filters are allow-listed; invalid known filter values return 404 and malformed/duplicate/oversized query parameters return 400.
- Result collections use explicit stable SQL ordering and bounded `limit` parameters.
- Aggregate responses do not infer permanent business death, insolvency, bankruptcy, or causes.

## Non-goals

- Do not modify narrative records, curated aggregate observations, or schema data.
- Do not calculate rates, causal effects, or failure probabilities.

## Risk and safety

Risk: public read-only API/data interpretation. No authentication, writes, database migrations, external network calls, or secrets are involved. All SQL uses bound values after allow-list validation.

## Test plan

1. Add a failing aggregate module test for summary counts/provenance.
2. Add failing API tests for Canada/Quebec trend comparison, size/industry filters, deterministic output, and invalid parameters.
3. Implement minimum reusable query and route logic.
4. Run validator, full unittest suite, loader, and real ephemeral-server curl smoke tests.

## Rollback

Revert the single feature commit; no data or schema mutation is performed.
