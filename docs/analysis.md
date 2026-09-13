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
