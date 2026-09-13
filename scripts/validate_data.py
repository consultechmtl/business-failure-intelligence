#!/usr/bin/env python3
"""Validate curated CSV data before it is loaded into SQLite."""

import argparse
import csv
import sys
from pathlib import Path


TABLES = {
    "companies": ("companies.csv", ["company_id", "canonical_name", "legal_name", "country_code", "region_code", "city", "founded_year", "industry", "business_model", "description"]),
    "outcomes": ("outcomes.csv", ["outcome_id", "company_id", "outcome_type", "outcome_date", "jurisdiction", "status", "notes"]),
    "sources": ("sources.csv", ["source_id", "source_url", "title", "publisher", "source_type", "published_date", "accessed_date", "evidence_quality", "notes"]),
    "cause_assertions": ("cause_assertions.csv", ["assertion_id", "company_id", "cause_code", "source_id", "assertion_type", "confidence", "evidence_quote", "analyst_note"]),
    "lessons": ("lessons.csv", ["lesson_id", "company_id", "lesson", "applicability", "action_for_founder", "confidence"]),
}
WARNING_SIGNS = (
    "warning_signs.csv",
    ["warning_id", "company_id", "signal_code", "observed_text", "observed_date", "source_id", "confidence"],
)
OUTCOME_TYPES = {"shutdown", "bankruptcy", "insolvency", "distress", "acquisition", "asset_sale", "pivot", "dormant", "unknown"}
CONFIDENCES = {"high", "medium", "low"}
ASSERTION_TYPES = {"explicit_founder_statement", "court_or_regulatory_finding", "contemporaneous_reporting", "editorial_classification", "analyst_inference"}


def read_table(data_dir, filename, columns, errors):
    path = data_dir / filename
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            missing = [column for column in columns if column not in headers]
            if missing:
                errors.append(f"{filename}: missing required columns: {', '.join(missing)}")
                return []
            return list(reader)
    except FileNotFoundError:
        errors.append(f"{filename}: file is required")
        return []


def unique_ids(rows, table, id_column, errors):
    ids = set()
    for line_number, row in enumerate(rows, start=2):
        identifier = row[id_column].strip()
        if not identifier:
            errors.append(f"{table}: row {line_number}: {id_column} is required")
        elif identifier in ids:
            errors.append(f"{table}: row {line_number}: duplicate {id_column}: {identifier}")
        else:
            ids.add(identifier)
    return ids


def validate(data_dir, taxonomy_path):
    errors = []
    rows = {
        table: read_table(data_dir, filename, columns, errors)
        for table, (filename, columns) in TABLES.items()
    }
    warning_filename, warning_columns = WARNING_SIGNS
    warning_path = data_dir / warning_filename
    if warning_path.exists():
        rows["warning_signs"] = read_table(data_dir, warning_filename, warning_columns, errors)
    else:
        rows["warning_signs"] = []
    ids = {
        "companies": unique_ids(rows["companies"], "companies.csv", "company_id", errors),
        "outcomes": unique_ids(rows["outcomes"], "outcomes.csv", "outcome_id", errors),
        "sources": unique_ids(rows["sources"], "sources.csv", "source_id", errors),
        "cause_assertions": unique_ids(rows["cause_assertions"], "cause_assertions.csv", "assertion_id", errors),
        "lessons": unique_ids(rows["lessons"], "lessons.csv", "lesson_id", errors),
        "warning_signs": unique_ids(rows["warning_signs"], "warning_signs.csv", "warning_id", errors),
    }

    cause_codes = set()
    try:
        with taxonomy_path.open(newline="", encoding="utf-8") as handle:
            cause_codes = {row["cause_code"].strip() for row in csv.DictReader(handle)}
    except FileNotFoundError:
        errors.append(f"{taxonomy_path}: cause taxonomy file is required")

    source_urls = {row["source_id"].strip(): row["source_url"].strip() for row in rows["sources"]}
    for line_number, row in enumerate(rows["outcomes"], start=2):
        if row["company_id"].strip() not in ids["companies"]:
            errors.append(f"outcomes.csv: row {line_number}: unknown company_id: {row['company_id']}")
        if row["outcome_type"].strip() not in OUTCOME_TYPES:
            errors.append(f"outcomes.csv: row {line_number}: invalid outcome_type: {row['outcome_type']}")

    for line_number, row in enumerate(rows["cause_assertions"], start=2):
        company_id = row["company_id"].strip()
        source_id = row["source_id"].strip()
        if company_id not in ids["companies"]:
            errors.append(f"cause_assertions.csv: row {line_number}: unknown company_id: {company_id}")
        if row["cause_code"].strip() not in cause_codes:
            errors.append(f"cause_assertions.csv: row {line_number}: unknown cause_code: {row['cause_code']}")
        if source_id not in ids["sources"]:
            errors.append(f"cause_assertions.csv: row {line_number}: unknown source_id: {source_id}")
        elif not source_urls[source_id]:
            errors.append(f"cause_assertions.csv: row {line_number}: source_url is required for cause assertion")
        if row["assertion_type"].strip() not in ASSERTION_TYPES:
            errors.append(f"cause_assertions.csv: row {line_number}: invalid assertion_type: {row['assertion_type']}")
        if row["confidence"].strip() not in CONFIDENCES:
            errors.append(f"cause_assertions.csv: row {line_number}: invalid confidence: {row['confidence']}")

    for line_number, row in enumerate(rows["lessons"], start=2):
        if row["company_id"].strip() not in ids["companies"]:
            errors.append(f"lessons.csv: row {line_number}: unknown company_id: {row['company_id']}")
        if row["confidence"].strip() not in CONFIDENCES:
            errors.append(f"lessons.csv: row {line_number}: invalid confidence: {row['confidence']}")

    for line_number, row in enumerate(rows["warning_signs"], start=2):
        company_id = row["company_id"].strip()
        source_id = row["source_id"].strip()
        if not row["signal_code"].strip():
            errors.append(f"warning_signs.csv: row {line_number}: signal_code is required")
        if not row["observed_text"].strip():
            errors.append(f"warning_signs.csv: row {line_number}: observed_text is required")
        if company_id not in ids["companies"]:
            errors.append(f"warning_signs.csv: row {line_number}: unknown company_id: {company_id}")
        if source_id not in ids["sources"]:
            errors.append(f"warning_signs.csv: row {line_number}: unknown source_id: {source_id}")
        elif not source_urls[source_id]:
            errors.append(f"warning_signs.csv: row {line_number}: source_url is required for warning sign")
        if row["confidence"].strip() not in CONFIDENCES:
            errors.append(f"warning_signs.csv: row {line_number}: invalid confidence: {row['confidence']}")

    return errors, sum(len(table_rows) for table_rows in rows.values())


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=root / "data" / "curated")
    parser.add_argument("--taxonomy", type=Path, default=root / "schema" / "cause_taxonomy.csv")
    args = parser.parse_args()

    errors, row_count = validate(args.data_dir, args.taxonomy)
    if errors:
        print("Validation failed:", *errors, sep="\n", file=sys.stderr)
        return 1
    curated_file_count = len(TABLES) + int((args.data_dir / WARNING_SIGNS[0]).exists())
    print(f"Validation passed: {row_count} rows across {curated_file_count} curated files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
