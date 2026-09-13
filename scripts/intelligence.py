"""Read-only, evidence-linked queries for the curated failure corpus."""

import json
import sqlite3
from pathlib import Path


CONFIDENCES = ("high", "medium", "low")


def _connect(database_path):
    connection = sqlite3.connect(Path(database_path))
    connection.row_factory = sqlite3.Row
    return connection


def _rows(connection, query, parameters=()):
    return [dict(row) for row in connection.execute(query, parameters)]


def corpus_summary(database_path):
    tables = ("companies", "outcomes", "sources", "cause_assertions", "warning_signs", "lessons", "entity_aliases")
    with _connect(database_path) as connection:
        counts = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
    return {"companies": counts["companies"], "outcomes": counts["outcomes"], "sources": counts["sources"], "cause_assertions": counts["cause_assertions"], "warning_signs": counts["warning_signs"], "lessons": counts["lessons"], "aliases": counts["entity_aliases"]}


def companies(database_path):
    with _connect(database_path) as connection:
        return _rows(connection, """
            SELECT company_id, canonical_name, country_code, region_code, city,
                   industry, business_model, geography_code
            FROM companies ORDER BY canonical_name COLLATE NOCASE, company_id
        """)


def cause_counts_by_confidence(database_path):
    with _connect(database_path) as connection:
        counts = dict(connection.execute("SELECT confidence, COUNT(*) FROM cause_assertions GROUP BY confidence"))
    return [{"confidence": confidence, "count": counts.get(confidence, 0)} for confidence in CONFIDENCES]


def causes_by_geography(database_path):
    with _connect(database_path) as connection:
        return _rows(connection, """
            SELECT CASE
                       WHEN c.country_code IS NULL OR c.country_code = '' THEN 'unknown'
                       WHEN c.region_code IS NULL OR c.region_code = '' THEN c.country_code
                       ELSE c.country_code || '-' || c.region_code
                   END AS geography_code,
                   CASE
                       WHEN c.country_code IS NULL OR c.country_code = '' THEN 'Unknown'
                       WHEN c.region_code IS NULL OR c.region_code = '' THEN c.country_code
                       ELSE c.country_code || ' / ' || c.region_code
                   END AS geography_name,
                   COUNT(ca.assertion_id) AS cause_assertions,
                   COUNT(DISTINCT ca.company_id) AS companies
            FROM cause_assertions AS ca
            JOIN companies AS c ON c.company_id = ca.company_id
            GROUP BY c.country_code, c.region_code
            ORDER BY cause_assertions DESC, geography_code
        """)


def company_case_detail(database_path, company_id):
    with _connect(database_path) as connection:
        company = connection.execute("SELECT * FROM companies WHERE company_id = ?", (company_id,)).fetchone()
        if company is None:
            return None
        sources = _rows(connection, """
            SELECT DISTINCT s.* FROM sources AS s
            JOIN (
                SELECT source_id FROM cause_assertions WHERE company_id = ?
                UNION SELECT source_id FROM warning_signs WHERE company_id = ? AND source_id IS NOT NULL
            ) AS linked ON linked.source_id = s.source_id
            ORDER BY s.published_date IS NULL, s.published_date, s.source_id
        """, (company_id, company_id))
        return {
            "company": dict(company),
            "outcomes": _rows(connection, "SELECT * FROM outcomes WHERE company_id = ? ORDER BY outcome_date IS NULL, outcome_date, outcome_id", (company_id,)),
            "sources": sources,
            "assertions": _rows(connection, """
                SELECT ca.*, fc.label AS cause_label, fc.definition AS cause_definition
                FROM cause_assertions AS ca JOIN failure_causes AS fc ON fc.cause_code = ca.cause_code
                WHERE ca.company_id = ?
                ORDER BY CASE ca.confidence WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, ca.assertion_id
            """, (company_id,)),
            "warnings": _rows(connection, "SELECT * FROM warning_signs WHERE company_id = ? ORDER BY observed_date IS NULL, observed_date, warning_id", (company_id,)),
            "lessons": _rows(connection, "SELECT * FROM lessons WHERE company_id = ? ORDER BY lesson_id", (company_id,)),
            "aliases": _rows(connection, "SELECT * FROM entity_aliases WHERE company_id = ? ORDER BY alias_name COLLATE NOCASE, alias_id", (company_id,)),
        }


def quebec_vs_international(database_path):
    with _connect(database_path) as connection:
        counts = dict(connection.execute("""
            SELECT CASE WHEN country_code = 'CA' AND region_code = 'QC' THEN 'quebec'
                        WHEN country_code != 'CA' OR country_code IS NULL THEN 'international'
                   END AS group_name, COUNT(*)
            FROM companies
            WHERE (country_code = 'CA' AND region_code = 'QC') OR country_code != 'CA' OR country_code IS NULL
            GROUP BY group_name
        """))
    return {"quebec": {"companies": counts.get("quebec", 0)}, "international": {"companies": counts.get("international", 0)}}


def to_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
