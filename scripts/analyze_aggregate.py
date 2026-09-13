#!/usr/bin/env python3
"""Report Statistics Canada aggregate openings/closures without conflating them with failures."""

import sqlite3
import tempfile
from pathlib import Path

from load_sqlite import load

ROOT = Path(__file__).resolve().parents[1]


def analyze():
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "aggregate.sqlite"
        load(database, ROOT / "data" / "curated", ROOT / "schema" / "cause_taxonomy.csv", ROOT / "schema" / "schema.sql")
        with sqlite3.connect(database) as connection:
            return connection.execute(
                """
                SELECT reference_period, geo, employment_size, business_dynamics, value, uom
                FROM aggregate_observations
                WHERE geo IN ('Canada', 'Quebec')
                  AND business_dynamics IN ('Openings', 'Closures')
                ORDER BY reference_period, employment_size, business_dynamics, geo
                """
            ).fetchall()


def main():
    print("Statistics Canada aggregate business dynamics: Openings and Closures (not narrative company outcomes):")
    print("Closures retain Statistics Canada's label; they are not asserted to be permanent enterprise deaths, insolvencies, bankruptcies, or causes of failure.")
    print("Geographies requested: Canada, Quebec.")
    print("reference_period | geo | employment_size | business_dynamics | value | uom")
    rows = analyze()
    if not rows:
        print("No normalized observations are committed yet; run normalize_statcan.py after a complete official ZIP download.")
    for row in rows:
        print(" | ".join(str(value) for value in row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

