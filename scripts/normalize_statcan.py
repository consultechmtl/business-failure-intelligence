#!/usr/bin/env python3
"""Normalize Statistics Canada bulk-table CSV rows into the aggregate layer.

No aggregate row is related to a narrative company. The normalizer retains only
Canada and Quebec by default; it preserves dimensions required to reproduce a
Statistics Canada observation.
"""

import argparse
import csv
import hashlib
import io
import sys
import zipfile
from pathlib import Path


TABLES = {
    "33100722": {
        "dataset_id": "statcan-33100722",
        "table_number": "33-10-0722-01",
        "source_url": "https://www150.statcan.gc.ca/n1/tbl/csv/33100722-eng.zip",
    },
    "33100270": {
        "dataset_id": "statcan-33100270",
        "table_number": "33-10-0270-01",
        "source_url": "https://www150.statcan.gc.ca/n1/tbl/csv/33100270-eng.zip",
    },
}


def pick(row, *names):
    for name in names:
        if name in row:
            return (row[name] or "").strip()
    return ""


def normalize_rows(rows, table_id, geos):
    """Return reproducible, compact records from a StatsCan CSV reader."""
    table = TABLES[table_id]
    result = []
    for row in rows:
        geo = pick(row, "GEO")
        if geo not in geos:
            continue
        value = pick(row, "VALUE")
        if not value:
            continue
        dynamics = pick(row, "Business dynamics")
        if dynamics not in {"Openings", "Closures"}:
            continue
        reference_period = pick(row, "REF_DATE")
        naics = pick(row, "North American Industry Classification System (NAICS)", "NAICS")
        employment_size = pick(row, "Employment size")
        uom = pick(row, "UOM")
        if not all((reference_period, naics, employment_size, uom)):
            continue
        key = "|".join((table["dataset_id"], reference_period, geo, naics, employment_size, dynamics, uom, pick(row, "STATUS")))
        result.append({
            "aggregate_observation_id": "agg-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20],
            "dataset_id": table["dataset_id"],
            "sample_frame_id": table["dataset_id"] + "-frame",
            "observation_unit_id": table["dataset_id"] + "-unit",
            "outcome_definition_id": table["dataset_id"] + "-" + dynamics.lower(),
            "reference_period": reference_period,
            "geo": geo,
            "naics": naics,
            "employment_size": employment_size,
            "business_dynamics": dynamics,
            "uom": uom,
            "value": value,
            "status": pick(row, "STATUS"),
            "table_number": table["table_number"],
            "source_url": table["source_url"],
        })
    return result


def read_zip_rows(zip_path):
    with zipfile.ZipFile(zip_path) as archive:
        csv_members = [item for item in archive.namelist() if item.lower().endswith(".csv") and "MetaData" not in item]
        if not csv_members:
            raise ValueError("ZIP contains no data CSV")
        with archive.open(csv_members[0]) as raw:
            yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--table", choices=TABLES, required=True)
    parser.add_argument("--output", type=Path, default=root / "data" / "curated" / "aggregate_observations.csv")
    parser.add_argument("--retrieval-date", required=True)
    args = parser.parse_args()
    try:
        records = normalize_rows(read_zip_rows(args.zip_path), args.table, {"Canada", "Quebec"})
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"Normalization failed: {error}", file=sys.stderr)
        return 1
    fields = list(records[0]) + ["retrieval_date"] if records else ["aggregate_observation_id", "dataset_id", "sample_frame_id", "observation_unit_id", "outcome_definition_id", "reference_period", "geo", "naics", "employment_size", "business_dynamics", "uom", "value", "status", "table_number", "source_url", "retrieval_date"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            record["retrieval_date"] = args.retrieval_date
            writer.writerow(record)
    print(f"Normalized {len(records)} {TABLES[args.table]['table_number']} observations to {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
