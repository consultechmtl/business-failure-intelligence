#!/usr/bin/env python3
"""Load validated curated CSV data into the SQLite analytical schema."""

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

from validate_data import TABLES, validate


LOAD_ORDER = ("industries", "business_models", "geographies", "companies", "entity_aliases", "outcomes", "sources", "cause_assertions", "lessons")


def read_rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def insert_rows(connection, table, columns, rows):
    if not rows:
        return 0
    placeholders = ", ".join("?" for _ in columns)
    column_names = ", ".join(columns)
    values = [tuple(row[column].strip() or None for column in columns) for row in rows]
    connection.executemany(f"INSERT INTO {table} ({column_names}) VALUES ({placeholders})", values)
    return len(values)


def load(database_path, data_dir, taxonomy_path, schema_path):
    errors, _ = validate(data_dir, taxonomy_path)
    if errors:
        raise ValueError("\n".join(errors))
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if database_path.exists():
        database_path.unlink()
    rows = {table: read_rows(data_dir / filename) for table, (filename, _) in TABLES.items()}
    warning_path = data_dir / "warning_signs.csv"
    warnings = read_rows(warning_path) if warning_path.exists() else []
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        counts = {}
        counts["failure_causes"] = insert_rows(connection, "failure_causes", ["cause_code", "parent_code", "label", "definition"], read_rows(taxonomy_path))
        for table in LOAD_ORDER:
            _, columns = TABLES[table]
            counts[table] = insert_rows(connection, table, columns, rows[table])
        counts["warning_signs"] = insert_rows(connection, "warning_signs", ["warning_id", "company_id", "signal_code", "observed_text", "observed_date", "source_id", "confidence"], warnings)
    return counts


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=root / "data" / "business_failure.sqlite")
    parser.add_argument("--data-dir", type=Path, default=root / "data" / "curated")
    parser.add_argument("--taxonomy", type=Path, default=root / "schema" / "cause_taxonomy.csv")
    parser.add_argument("--schema", type=Path, default=root / "schema" / "schema.sql")
    args = parser.parse_args()
    try:
        counts = load(args.db, args.data_dir, args.taxonomy, args.schema)
    except ValueError as error:
        print("Validation failed:", error, sep="\n", file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error) as error:
        print(f"Load failed: {error}", file=sys.stderr)
        return 1
    total = sum(counts.values())
    report = ", ".join(f"{table}={count}" for table, count in counts.items())
    print(f"Loaded {total} rows into {args.db}: {report}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
