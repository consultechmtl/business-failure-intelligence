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
