#!/usr/bin/env python3
"""Print descriptive summaries for the curated corpus."""

import sqlite3
import tempfile
from pathlib import Path

from load_sqlite import load


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "curated"
TAXONOMY_PATH = ROOT / "schema" / "cause_taxonomy.csv"
SCHEMA_PATH = ROOT / "schema" / "schema.sql"
CONFIDENCE_LEVELS = ("high", "medium", "low")


def query_rows(connection, query):
    return connection.execute(query).fetchall()


def analyze():
    """Load the corpus into a temporary database and return summary rows."""
    with tempfile.TemporaryDirectory() as directory:
        database_path = Path(directory) / "corpus.sqlite"
        load(database_path, DATA_DIR, TAXONOMY_PATH, SCHEMA_PATH)
        with sqlite3.connect(database_path) as connection:
            confidence_counts = dict(
                query_rows(
                    connection,
                    "SELECT confidence, COUNT(*) FROM cause_assertions GROUP BY confidence",
                )
            )
            locations = query_rows(
                connection,
                """
                SELECT COALESCE(country_code, 'Unknown'),
                       COALESCE(region_code, 'Unknown'),
                       COUNT(*)
                FROM companies
                GROUP BY country_code, region_code
                ORDER BY 1, 2
                """,
            )
            comparisons = query_rows(
                connection,
                """
                SELECT 'Canada', COUNT(*) FROM companies WHERE country_code = 'CA'
                UNION ALL
                SELECT 'Quebec', COUNT(*) FROM companies
                WHERE country_code = 'CA' AND region_code = 'QC'
                UNION ALL
                SELECT 'International', COUNT(*) FROM companies
                WHERE country_code IS NULL OR country_code != 'CA'
                """,
            )
        connection.close()
    return confidence_counts, locations, comparisons


def main():
    confidence_counts, locations, comparisons = analyze()
    print("Cause assertions by confidence:")
    for confidence in CONFIDENCE_LEVELS:
        print(f"{confidence}: {confidence_counts.get(confidence, 0)}")
    print("\nCases by country/region:")
    for country, region, count in locations:
        print(f"{country} / {region}: {count}")
    print("\nCanada, Quebec, and international cases:")
    for label, count in comparisons:
        print(f"{label}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
