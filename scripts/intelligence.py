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


AGGREGATE_DISCLAIMER = (
    "Statistics Canada closures are business-dynamics observations, not necessarily "
    "permanent deaths, insolvencies, bankruptcies, or causes of business failure."
)


def _aggregate_metadata(connection, where="", parameters=()):
    clause = f" WHERE {where}" if where else ""
    period = connection.execute(
        f"SELECT MIN(reference_period), MAX(reference_period), COUNT(DISTINCT reference_period) "
        f"FROM aggregate_observations{clause}", parameters,
    ).fetchone()
    return {
        "datasets": _rows(connection, """
            SELECT table_number, title, publisher, source_url, retrieval_date,
                   definition_notes, extraction_criteria
            FROM datasets ORDER BY table_number
        """),
        "reference_periods": {"first": period[0], "last": period[1], "count": period[2]},
        "uom": [row[0] for row in connection.execute(
            f"SELECT DISTINCT uom FROM aggregate_observations{clause} ORDER BY uom", parameters
        )],
        "status_flags": [row[0] for row in connection.execute(
            f"SELECT DISTINCT COALESCE(NULLIF(status, ''), 'none') FROM aggregate_observations{clause} "
            "ORDER BY COALESCE(NULLIF(status, ''), 'none')", parameters
        )],
        "interpretation_disclaimer": AGGREGATE_DISCLAIMER,
    }


def aggregate_filter_values(database_path):
    with _connect(database_path) as connection:
        return {
            "geo": [row[0] for row in connection.execute("SELECT DISTINCT geo FROM aggregate_observations ORDER BY geo")],
            "dynamics": [row[0] for row in connection.execute("SELECT DISTINCT business_dynamics FROM aggregate_observations ORDER BY business_dynamics")],
            "employment_size": [row[0] for row in connection.execute("SELECT DISTINCT employment_size FROM aggregate_observations ORDER BY employment_size")],
        }


def aggregate_summary(database_path):
    with _connect(database_path) as connection:
        metadata = _aggregate_metadata(connection)
        metadata.update({
            "observation_count": connection.execute("SELECT COUNT(*) FROM aggregate_observations").fetchone()[0],
            "geographies": _rows(connection, """
                SELECT geo, COUNT(*) AS observation_count
                FROM aggregate_observations GROUP BY geo ORDER BY geo
            """),
            "dynamics": _rows(connection, """
                SELECT business_dynamics AS dynamics, COUNT(*) AS observation_count
                FROM aggregate_observations GROUP BY business_dynamics ORDER BY business_dynamics
            """),
        })
        return metadata


def _aggregate_rows(database_path, order_by, filters, limit):
    """Return source observations without summing overlapping categories or tables."""
    clauses, parameters = [], []
    for field, value in filters.items():
        if value is not None:
            clauses.append(f"o.{field} = ?")
            parameters.append(value)
    where = " AND ".join(clauses)
    where_sql = f" WHERE {where}" if where else ""
    metadata_where = where.replace("o.", "")
    with _connect(database_path) as connection:
        rows = _rows(connection, f"""
            SELECT o.reference_period, o.geo, o.naics, o.employment_size,
                   o.business_dynamics, o.uom, o.value,
                   COALESCE(NULLIF(o.status, ''), 'none') AS status_flag,
                   o.table_number, o.source_url, o.retrieval_date
            FROM aggregate_observations AS o{where_sql}
            ORDER BY {order_by}, o.table_number, o.aggregate_observation_id
            LIMIT ?
        """, tuple(parameters + [limit]))
        return {"filters": {key: value for key, value in filters.items() if value is not None},
                "rows": rows,
                "metadata": _aggregate_metadata(connection, metadata_where, tuple(parameters))}


def aggregate_trends(database_path, geo=None, dynamics=None, limit=500):
    return _aggregate_rows(database_path, "o.reference_period, o.geo, o.business_dynamics",
                           {"geo": geo, "business_dynamics": dynamics}, limit)


def aggregate_by_size(database_path, geo=None, dynamics=None, limit=500):
    return _aggregate_rows(database_path, "o.employment_size, o.geo, o.business_dynamics, o.reference_period",
                           {"geo": geo, "business_dynamics": dynamics}, limit)


def aggregate_by_industry(database_path, geo=None, employment_size=None, dynamics=None, limit=500):
    return _aggregate_rows(database_path, "o.naics, o.geo, o.employment_size, o.business_dynamics, o.reference_period",
                           {"geo": geo, "employment_size": employment_size, "business_dynamics": dynamics}, limit)


def to_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
