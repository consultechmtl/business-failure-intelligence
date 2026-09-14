#!/usr/bin/env python3
"""Validate curated CSV data before it is loaded into SQLite."""

import argparse
import csv
import sys
from pathlib import Path


TABLES = {
    "companies": ("companies.csv", ["company_id", "canonical_name", "legal_name", "country_code", "region_code", "city", "founded_year", "industry", "business_model", "description", "industry_code", "business_model_code", "geography_code"]),
    "industries": ("industries.csv", ["industry_code", "label_en", "label_fr", "description"]),
    "business_models": ("business_models.csv", ["business_model_code", "label_en", "label_fr", "description"]),
    "geographies": ("geographies.csv", ["geography_code", "parent_geography_code", "geography_type", "country_code", "region_code", "municipality", "name_en", "name_fr"]),
    "entity_aliases": ("entity_aliases.csv", ["alias_id", "company_id", "alias_name", "alias_type", "language_code"]),
    "outcomes": ("outcomes.csv", ["outcome_id", "company_id", "outcome_type", "outcome_date", "jurisdiction", "status", "notes"]),
    "sources": ("sources.csv", ["source_id", "source_url", "title", "publisher", "source_type", "published_date", "accessed_date", "evidence_quality", "notes"]),
    "cause_assertions": ("cause_assertions.csv", ["assertion_id", "company_id", "cause_code", "source_id", "assertion_type", "confidence", "evidence_quote", "analyst_note"]),
    "lessons": ("lessons.csv", ["lesson_id", "company_id", "lesson", "applicability", "action_for_founder", "confidence"]),
}
WARNING_SIGNS = ("warning_signs.csv", ["warning_id", "company_id", "signal_code", "observed_text", "observed_date", "source_id", "confidence"])
AGGREGATE_TABLES = {
    "datasets": ("datasets.csv", ["dataset_id", "table_number", "title", "publisher", "source_url", "retrieval_date", "license_notes", "definition_notes", "extraction_criteria"]),
    "sample_frames": ("sample_frames.csv", ["sample_frame_id", "dataset_id", "label", "definition_notes"]),
    "observation_units": ("observation_units.csv", ["observation_unit_id", "dataset_id", "label", "unit_of_measure", "definition_notes"]),
    "outcome_definitions": ("outcome_definitions.csv", ["outcome_definition_id", "dataset_id", "label", "definition_text"]),
}
AGGREGATE_OBSERVATIONS = ("aggregate_observations.csv", ["aggregate_observation_id", "dataset_id", "sample_frame_id", "observation_unit_id", "outcome_definition_id", "reference_period", "geo", "naics", "employment_size", "business_dynamics", "uom", "value", "status", "table_number", "source_url", "retrieval_date"])
OSB_INSOLVENCIES = ("osb_insolvency_observations.csv", ["osb_insolvency_observation_id", "dataset_id", "reference_period", "geo", "geo_level", "debtor_type", "business_form", "insolvency_type", "naics", "measure", "uom", "value", "status", "source_url", "retrieval_date"])
OUTCOME_TYPES = {"shutdown", "bankruptcy", "insolvency", "distress", "acquisition", "asset_sale", "pivot", "dormant", "unknown"}
CONFIDENCES = {"high", "medium", "low"}
ASSERTION_TYPES = {"explicit_founder_statement", "court_or_regulatory_finding", "contemporaneous_reporting", "editorial_classification", "analyst_inference"}
GEOGRAPHY_TYPES = {"country", "region", "municipality"}
ALIAS_TYPES = {"canonical", "legal", "brand", "former_legal", "other"}
LANGUAGE_CODES = {"en", "fr", "und"}


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
    rows = {table: read_table(data_dir, filename, columns, errors) for table, (filename, columns) in TABLES.items()}
    warning_filename, warning_columns = WARNING_SIGNS
    warning_path = data_dir / warning_filename
    rows["warning_signs"] = read_table(data_dir, warning_filename, warning_columns, errors) if warning_path.exists() else []
    aggregate_enabled = (data_dir / "datasets.csv").exists()
    for table, (filename, columns) in AGGREGATE_TABLES.items():
        rows[table] = read_table(data_dir, filename, columns, errors) if aggregate_enabled else []
    aggregate_filename, aggregate_columns = AGGREGATE_OBSERVATIONS
    rows["aggregate_observations"] = read_table(data_dir, aggregate_filename, aggregate_columns, errors) if aggregate_enabled else []
    if aggregate_enabled and not (data_dir / aggregate_filename).exists():
        errors.append(f"{aggregate_filename}: file is required when datasets.csv is present")
    osb_filename, osb_columns = OSB_INSOLVENCIES
    rows["osb_insolvency_observations"] = read_table(data_dir, osb_filename, osb_columns, errors) if (data_dir / osb_filename).exists() else []
    ids = {
        table: unique_ids(rows[table], filename, columns[0], errors)
        for table, (filename, columns) in AGGREGATE_TABLES.items()
    }
    ids["aggregate_observations"] = unique_ids(rows["aggregate_observations"], aggregate_filename, "aggregate_observation_id", errors)
    ids["osb_insolvency_observations"] = unique_ids(rows["osb_insolvency_observations"], osb_filename, "osb_insolvency_observation_id", errors)
    ids.update({
        "companies": unique_ids(rows["companies"], "companies.csv", "company_id", errors),
        "industries": unique_ids(rows["industries"], "industries.csv", "industry_code", errors),
        "business_models": unique_ids(rows["business_models"], "business_models.csv", "business_model_code", errors),
        "geographies": unique_ids(rows["geographies"], "geographies.csv", "geography_code", errors),
        "entity_aliases": unique_ids(rows["entity_aliases"], "entity_aliases.csv", "alias_id", errors),
        "outcomes": unique_ids(rows["outcomes"], "outcomes.csv", "outcome_id", errors),
        "sources": unique_ids(rows["sources"], "sources.csv", "source_id", errors),
        "cause_assertions": unique_ids(rows["cause_assertions"], "cause_assertions.csv", "assertion_id", errors),
        "lessons": unique_ids(rows["lessons"], "lessons.csv", "lesson_id", errors),
        "warning_signs": unique_ids(rows["warning_signs"], "warning_signs.csv", "warning_id", errors),
    })
    for line_number, row in enumerate(rows["sample_frames"], start=2):
        if row["dataset_id"].strip() not in ids["datasets"]:
            errors.append(f"sample_frames.csv: row {line_number}: unknown dataset_id: {row['dataset_id']}")
    for table in ("observation_units", "outcome_definitions"):
        for line_number, row in enumerate(rows[table], start=2):
            if row["dataset_id"].strip() not in ids["datasets"]:
                errors.append(f"{table}.csv: row {line_number}: unknown dataset_id: {row['dataset_id']}")
    for line_number, row in enumerate(rows["osb_insolvency_observations"], start=2):
        if row["dataset_id"].strip() not in ids["datasets"]:
            errors.append(f"{osb_filename}: row {line_number}: unknown dataset_id: {row['dataset_id']}")
        if row["debtor_type"].strip() not in {"all", "business", "consumer"}:
            errors.append(f"{osb_filename}: row {line_number}: invalid debtor_type")
        if row["insolvency_type"].strip() not in {"Total", "Bankruptcy", "Proposal"}:
            errors.append(f"{osb_filename}: row {line_number}: invalid insolvency_type")
        try:
            float(row["value"])
        except ValueError:
            errors.append(f"{osb_filename}: row {line_number}: value must be numeric")
    for line_number, row in enumerate(rows["aggregate_observations"], start=2):
        for column, table in (("dataset_id", "datasets"), ("sample_frame_id", "sample_frames"), ("observation_unit_id", "observation_units"), ("outcome_definition_id", "outcome_definitions")):
            if row[column].strip() not in ids[table]:
                errors.append(f"aggregate_observations.csv: row {line_number}: unknown {column}: {row[column]}")
        if row["business_dynamics"].strip() not in {"Openings", "Closures"}:
            errors.append(f"aggregate_observations.csv: row {line_number}: invalid business_dynamics: {row['business_dynamics']}")
        try:
            float(row["value"])
        except ValueError:
            errors.append(f"aggregate_observations.csv: row {line_number}: value must be numeric")
    for line_number, row in enumerate(rows["geographies"], start=2):
        parent = row["parent_geography_code"].strip()
        if parent and parent not in ids["geographies"]:
            errors.append(f"geographies.csv: row {line_number}: unknown parent_geography_code: {parent}")
        if row["geography_type"].strip() not in GEOGRAPHY_TYPES:
            errors.append(f"geographies.csv: row {line_number}: invalid geography_type: {row['geography_type']}")
    for line_number, row in enumerate(rows["entity_aliases"], start=2):
        if row["company_id"].strip() not in ids["companies"]:
            errors.append(f"entity_aliases.csv: row {line_number}: unknown company_id: {row['company_id']}")
        if not row["alias_name"].strip():
            errors.append(f"entity_aliases.csv: row {line_number}: alias_name is required")
        if row["alias_type"].strip() not in ALIAS_TYPES:
            errors.append(f"entity_aliases.csv: row {line_number}: invalid alias_type: {row['alias_type']}")
        if row["language_code"].strip() not in LANGUAGE_CODES:
            errors.append(f"entity_aliases.csv: row {line_number}: invalid language_code: {row['language_code']}")
    for line_number, row in enumerate(rows["companies"], start=2):
        for code_column, table in (("industry_code", "industries"), ("business_model_code", "business_models"), ("geography_code", "geographies")):
            code = row[code_column].strip()
            if code and code not in ids[table]:
                errors.append(f"companies.csv: row {line_number}: unknown {code_column}: {code}")

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
        company_id, source_id = row["company_id"].strip(), row["source_id"].strip()
        if company_id not in ids["companies"]: errors.append(f"cause_assertions.csv: row {line_number}: unknown company_id: {company_id}")
        if row["cause_code"].strip() not in cause_codes: errors.append(f"cause_assertions.csv: row {line_number}: unknown cause_code: {row['cause_code']}")
        if source_id not in ids["sources"]: errors.append(f"cause_assertions.csv: row {line_number}: unknown source_id: {source_id}")
        elif not source_urls[source_id]: errors.append(f"cause_assertions.csv: row {line_number}: source_url is required for cause assertion")
        if row["assertion_type"].strip() not in ASSERTION_TYPES: errors.append(f"cause_assertions.csv: row {line_number}: invalid assertion_type: {row['assertion_type']}")
        if row["confidence"].strip() not in CONFIDENCES: errors.append(f"cause_assertions.csv: row {line_number}: invalid confidence: {row['confidence']}")
    for line_number, row in enumerate(rows["lessons"], start=2):
        if row["company_id"].strip() not in ids["companies"]: errors.append(f"lessons.csv: row {line_number}: unknown company_id: {row['company_id']}")
        if row["confidence"].strip() not in CONFIDENCES: errors.append(f"lessons.csv: row {line_number}: invalid confidence: {row['confidence']}")
    for line_number, row in enumerate(rows["warning_signs"], start=2):
        company_id, source_id = row["company_id"].strip(), row["source_id"].strip()
        if not row["signal_code"].strip(): errors.append(f"warning_signs.csv: row {line_number}: signal_code is required")
        if not row["observed_text"].strip(): errors.append(f"warning_signs.csv: row {line_number}: observed_text is required")
        if company_id not in ids["companies"]: errors.append(f"warning_signs.csv: row {line_number}: unknown company_id: {company_id}")
        if source_id not in ids["sources"]: errors.append(f"warning_signs.csv: row {line_number}: unknown source_id: {source_id}")
        elif not source_urls[source_id]: errors.append(f"warning_signs.csv: row {line_number}: source_url is required for warning sign")
        if row["confidence"].strip() not in CONFIDENCES: errors.append(f"warning_signs.csv: row {line_number}: invalid confidence: {row['confidence']}")
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
    if (args.data_dir / "datasets.csv").exists():
        curated_file_count += len(AGGREGATE_TABLES) + 1
    print(f"Validation passed: {row_count} rows across {curated_file_count} curated files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
