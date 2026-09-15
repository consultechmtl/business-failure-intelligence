"""Read-only, evidence-linked queries for the curated failure corpus."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


CONFIDENCES = ("high", "medium", "low")


@contextmanager
def _connect(database_path):
    connection = sqlite3.connect(Path(database_path))
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _rows(connection, query, parameters=()):
    return [dict(row) for row in connection.execute(query, parameters)]


def corpus_summary(database_path):
    tables = ("companies", "outcomes", "sources", "cause_assertions", "warning_signs", "lessons", "entity_aliases")
    with _connect(database_path) as connection:
        counts = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
    return {"companies": counts["companies"], "outcomes": counts["outcomes"], "sources": counts["sources"], "cause_assertions": counts["cause_assertions"], "warning_signs": counts["warning_signs"], "lessons": counts["lessons"], "aliases": counts["entity_aliases"]}


def coverage_dashboard(database_path):
    """Describe coverage without conflating narrative cases and aggregate rows."""
    narrative_tables = (
        "companies", "outcomes", "sources", "cause_assertions", "warning_signs",
        "lessons", "entity_aliases",
    )
    with _connect(database_path) as connection:
        narrative_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in narrative_tables
        }
        aggregate_rows = connection.execute("SELECT COUNT(*) FROM aggregate_observations").fetchone()[0]
        osb_rows = connection.execute("SELECT COUNT(*) FROM osb_insolvency_observations").fetchone()[0]
        datasets = _rows(connection, """
            SELECT d.dataset_id, d.table_number, d.title, d.publisher, d.source_url,
                   d.retrieval_date, d.definition_notes, d.extraction_criteria,
                   (SELECT COUNT(*) FROM aggregate_observations a WHERE a.dataset_id = d.dataset_id) AS statistics_canada_rows,
                   (SELECT COUNT(*) FROM osb_insolvency_observations o WHERE o.dataset_id = d.dataset_id) AS osb_proceeding_rows
            FROM datasets AS d
            ORDER BY d.table_number
        """)
    return {
        "narrative_cases": {
            "label": "Reviewed individual company cases",
            "row_counts": narrative_counts,
            "companies": narrative_counts["companies"],
            "scope_note": "Curated narrative cases are non-representative individual records; causes require linked evidence.",
        },
        "aggregate_observations": {
            "label": "Official aggregate observations",
            "statistics_canada_rows": aggregate_rows,
            "osb_insolvency_proceeding_rows": osb_rows,
            "scope_note": "Aggregate rows are not individual companies or narrative cases and must not be added to case counts.",
        },
        "datasets": datasets,
        "interpretation_caveat": "Statistics Canada closures, OSB proceedings, and curated company outcomes are separate layers with different definitions and observation units.",
    }


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
            FROM datasets
            WHERE dataset_id IN (SELECT DISTINCT dataset_id FROM aggregate_observations)
            ORDER BY table_number
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



OSB_INSOLVENCY_DISCLAIMER = (
    "OSB BIA insolvency proceedings are not equivalent to all business failures or permanent closure; "
    "they are not Statistics Canada business-closure observations or narrative company outcomes."
)


def insolvency_filter_values(database_path):
    with _connect(database_path) as connection:
        return {
            "geo": [row[0] for row in connection.execute("SELECT DISTINCT geo FROM osb_insolvency_observations ORDER BY geo")],
            "period": [row[0] for row in connection.execute("SELECT DISTINCT reference_period FROM osb_insolvency_observations ORDER BY reference_period")],
            "type": [row[0] for row in connection.execute("SELECT DISTINCT insolvency_type FROM osb_insolvency_observations ORDER BY insolvency_type")],
        }


def aggregate_insolvencies(database_path, geo=None, period=None, insolvency_type=None, limit=500):
    filters = {"geo": geo, "reference_period": period, "insolvency_type": insolvency_type}
    clauses, parameters = [], []
    for field, value in filters.items():
        if value is not None:
            clauses.append(field + " = ?")
            parameters.append(value)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _connect(database_path) as connection:
        rows = _rows(connection, """
            SELECT reference_period, geo, geo_level, debtor_type, business_form,
                   insolvency_type, naics, measure, uom, value,
                   COALESCE(NULLIF(status, ''), 'none') AS status_flag, source_url, retrieval_date
            FROM osb_insolvency_observations%s
            ORDER BY reference_period, geo, debtor_type, business_form, naics, insolvency_type, osb_insolvency_observation_id
            LIMIT ?
        """ % where, tuple(parameters + [limit]))
        metadata = _rows(connection, """
            SELECT table_number, title, publisher, source_url, retrieval_date, definition_notes, extraction_criteria
            FROM datasets WHERE dataset_id = 'osb-bia-insolvency-statistics-2026-03'
        """)
        return {"filters": {key: value for key, value in {"geo": geo, "period": period, "type": insolvency_type}.items() if value is not None},
                "rows": rows, "metadata": {"datasets": metadata,
                "status_flags": [row[0] for row in connection.execute("SELECT DISTINCT COALESCE(NULLIF(status, ''), 'none') FROM osb_insolvency_observations%s ORDER BY 1" % where, tuple(parameters))],
                "interpretation_disclaimer": OSB_INSOLVENCY_DISCLAIMER}}


COMPARISON_SAFE_LANGUAGE_WARNINGS = (
    "Statistics Canada openings and closures and OSB BIA insolvency proceedings are separately reported observation layers with incompatible definitions, populations, and measurement processes.",
    "OSB insolvency proceedings are not equivalent to Statistics Canada closures, permanent business closure, business failure, bankruptcy totals, or narrative company outcomes.",
    "This comparison is descriptive only: it makes no causal interpretation and does not estimate a failure rate, insolvency rate, or closure rate.",
    "Do not divide insolvencies by closures or treat either layer as the denominator for the other unless an explicit, separately documented analytical request defines and justifies that calculation.",
)


def _period_coverage(connection, table, where, parameters):
    first, last, count = connection.execute(
        f"SELECT MIN(reference_period), MAX(reference_period), COUNT(DISTINCT reference_period) FROM {table} WHERE {where}",
        parameters,
    ).fetchone()
    return {"first": first, "last": last, "count": count}


def _comparison_dataset_provenance(connection, dataset_id, source_tables):
    datasets = _rows(connection, """
        SELECT table_number, title, publisher, source_url, retrieval_date, definition_notes, extraction_criteria
        FROM datasets WHERE dataset_id = ? ORDER BY table_number
    """, (dataset_id,)) if dataset_id else _rows(connection, """
        SELECT table_number, title, publisher, source_url, retrieval_date, definition_notes, extraction_criteria
        FROM datasets WHERE dataset_id IN ('statcan-33100270', 'statcan-33100722') ORDER BY table_number
    """)
    return {"source_tables": source_tables, "datasets": datasets}


def cross_layer_comparison(database_path, geo, period_start=None, period_end=None, limit=500):
    """Return co-presented source observations without merging layers or calculating rates."""
    statcan_clauses = ["geo = ?", "reference_period >= ?", "reference_period <= ?"]
    osb_clauses = ["geo = ?", "reference_period >= ?", "reference_period <= ?"]
    start = period_start or "0000-00"
    end = period_end or "9999-99"
    parameters = (geo, start, end)
    statcan_where = " AND ".join(statcan_clauses)
    osb_where = " AND ".join(osb_clauses)
    with _connect(database_path) as connection:
        def statcan_rows_for(dynamics):
            return _rows(connection, f"""
                SELECT reference_period, geo, naics, employment_size, business_dynamics, uom, value,
                       COALESCE(NULLIF(status, ''), 'none') AS status_flag, table_number, source_url, retrieval_date
                FROM aggregate_observations WHERE {statcan_where} AND business_dynamics = ?
                ORDER BY reference_period, geo, naics, employment_size, table_number, aggregate_observation_id
                LIMIT ?
            """, parameters + (dynamics, limit))

        openings = statcan_rows_for("Openings")
        closures = statcan_rows_for("Closures")
        osb_rows = _rows(connection, f"""
            SELECT reference_period, geo, geo_level, debtor_type, business_form, insolvency_type,
                   naics, measure, uom, value, COALESCE(NULLIF(status, ''), 'none') AS status_flag,
                   source_url, retrieval_date
            FROM osb_insolvency_observations WHERE {osb_where}
            ORDER BY reference_period, geo, debtor_type, business_form, naics, insolvency_type, osb_insolvency_observation_id
            LIMIT ?
        """, parameters + (limit,))
        return {
            "filters": {key: value for key, value in {"geo": geo, "period_start": period_start, "period_end": period_end}.items() if value is not None},
            "statistics_canada": {
                "label": "Statistics Canada business-dynamics observations",
                "openings": openings,
                "closures": closures,
                "period_coverage": _period_coverage(connection, "aggregate_observations", statcan_where, parameters),
                "units": [row[0] for row in connection.execute(f"SELECT DISTINCT uom FROM aggregate_observations WHERE {statcan_where} ORDER BY uom", parameters)],
                "provenance": _comparison_dataset_provenance(connection, None, ["33-10-0270-01", "33-10-0722-01"]),
            },
            "osb_insolvencies": {
                "label": "OSB BIA insolvency proceeding observations",
                "rows": osb_rows,
                "period_coverage": _period_coverage(connection, "osb_insolvency_observations", osb_where, parameters),
                "units": [row[0] for row in connection.execute(f"SELECT DISTINCT uom FROM osb_insolvency_observations WHERE {osb_where} ORDER BY uom", parameters)],
                "provenance": _comparison_dataset_provenance(connection, "osb-bia-insolvency-statistics-2026-03", ["OSB BIA insolvency statistics workbook"]),
            },
            "metadata": {
                "comparison_method": "Co-presentation only; no rows are joined, summed, normalized, or used as each other's denominator.",
                "incompatible_definitions": True,
                "causal_interpretation": "none",
                "safe_language_warnings": list(COMPARISON_SAFE_LANGUAGE_WARNINGS),
            },
        }


FOUNDER_INSIGHT_CAVEATS = (
    "Statistics Canada closures are business-dynamics observations, not necessarily permanent deaths, insolvencies, bankruptcies, or causes of business failure.",
    "OSB BIA insolvency proceedings are not equivalent to all business failures or permanent closure and are not Statistics Canada closure observations.",
    "Narrative cases are a small, non-representative, evidence-constrained corpus; their warning signs and cause assertions do not estimate prevalence or establish causation.",
    "This response co-presents separate layers only: it does not join, sum, normalize, score, predict, rank, or calculate rates across them.",
    "Statistics Canada NAICS categories are not equated with the normalized narrative industry taxonomy; industry and business-model filters apply only to narrative matching.",
)


def founder_filter_values(database_path):
    """Return normalized profile dimensions and compatible aggregate dimensions."""
    with _connect(database_path) as connection:
        return {
            "geo": ("Quebec", "Canada"),
            "industries": _rows(connection, "SELECT industry_code, label_en, label_fr FROM industries ORDER BY industry_code"),
            "business_models": _rows(connection, "SELECT business_model_code, label_en, label_fr FROM business_models ORDER BY business_model_code"),
            "employment_size": [row[0] for row in connection.execute(
                "SELECT DISTINCT employment_size FROM aggregate_observations ORDER BY employment_size"
            )],
        }


def resolve_industry(database_path, industry_code=None, industry=None):
    """Resolve a normalized industry code or case-insensitive label without fuzzy inference."""
    with _connect(database_path) as connection:
        if industry_code is not None:
            row = connection.execute(
                "SELECT industry_code, label_en, label_fr FROM industries WHERE industry_code = ?", (industry_code,)
            ).fetchone()
            if row is None:
                return None
            if industry is not None and industry.casefold() not in {row["industry_code"].casefold(), row["label_en"].casefold(), row["label_fr"].casefold()}:
                return False
            return dict(row)
        if industry is None:
            return None
        row = connection.execute("""
            SELECT industry_code, label_en, label_fr FROM industries
            WHERE lower(industry_code) = lower(?) OR lower(label_en) = lower(?) OR lower(label_fr) = lower(?)
        """, (industry, industry, industry)).fetchone()
        return dict(row) if row is not None else None


def _profile_geography_clause(geo):
    return ("c.country_code = 'CA'", ()) if geo == "Canada" else ("c.country_code = 'CA' AND c.region_code = 'QC'", ())


def founder_profile_insight(database_path, profile, limit=20):
    """Co-present compatible aggregate context and exact normalized narrative matches; never score or merge layers."""
    geo = profile["geo"]
    industry = resolve_industry(database_path, profile.get("industry_code"), profile.get("industry"))
    if not industry:
        raise ValueError("industry must resolve before querying")
    model_code = profile.get("business_model_code")
    employment_size = profile.get("employment_size")
    geo_clause, geo_parameters = _profile_geography_clause(geo)
    with _connect(database_path) as connection:
        requested = {"geo": geo, "industry_code": industry["industry_code"], "industry": industry["label_en"]}
        if model_code is not None:
            requested["business_model_code"] = model_code
        if employment_size is not None:
            requested["employment_size"] = employment_size
        model_clause, model_parameters = (" AND c.business_model_code = ?", (model_code,)) if model_code else ("", ())
        cases = _rows(connection, f"""
            SELECT c.company_id, c.canonical_name, c.industry_code, c.business_model_code, c.geography_code,
                   c.country_code, c.region_code, c.city, c.description
            FROM companies AS c
            WHERE c.industry_code = ? AND {geo_clause}{model_clause}
            ORDER BY c.canonical_name COLLATE NOCASE, c.company_id
            LIMIT ?
        """, (industry["industry_code"],) + geo_parameters + model_parameters + (limit,))
        case_ids = [case["company_id"] for case in cases]
        if case_ids:
            placeholders = ",".join("?" for _ in case_ids)
            warnings = _rows(connection, f"""
                SELECT w.company_id, c.canonical_name, w.warning_id, w.signal_code, w.observed_text,
                       w.observed_date, w.confidence, s.source_id, s.source_url, s.title AS source_title,
                       s.source_type, s.evidence_quality
                FROM warning_signs AS w JOIN companies AS c ON c.company_id = w.company_id
                LEFT JOIN sources AS s ON s.source_id = w.source_id
                WHERE w.company_id IN ({placeholders})
                ORDER BY c.canonical_name COLLATE NOCASE, w.observed_date IS NULL, w.observed_date, w.warning_id
            """, case_ids)
            causes = _rows(connection, f"""
                SELECT ca.company_id, c.canonical_name, ca.assertion_id, ca.cause_code, fc.label AS cause_label,
                       ca.assertion_type, ca.confidence, ca.evidence_quote, ca.analyst_note,
                       s.source_id, s.source_url, s.title AS source_title, s.source_type, s.evidence_quality
                FROM cause_assertions AS ca JOIN companies AS c ON c.company_id = ca.company_id
                JOIN failure_causes AS fc ON fc.cause_code = ca.cause_code
                JOIN sources AS s ON s.source_id = ca.source_id
                WHERE ca.company_id IN ({placeholders})
                ORDER BY c.canonical_name COLLATE NOCASE,
                         CASE ca.confidence WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                         ca.assertion_id
            """, case_ids)
        else:
            warnings, causes = [], []
        statcan_filters = {"geo": geo, "employment_size": employment_size, "business_dynamics": None}
        statcan = _aggregate_rows(
            database_path, "o.reference_period, o.naics, o.business_dynamics, o.table_number", statcan_filters, limit
        )
        osb = aggregate_insolvencies(database_path, geo=geo, limit=limit)
        return {
            "requested_profile": requested,
            "statistics_canada": {
                "label": "Statistics Canada business-dynamics observations (compatible geography and employment-size dimensions only)",
                "filters": statcan["filters"], "rows": statcan["rows"], "metadata": statcan["metadata"],
            },
            "osb_insolvencies": {
                "label": "OSB BIA insolvency proceeding observations (separate context; geography only)",
                "filters": osb["filters"], "rows": osb["rows"], "metadata": osb["metadata"],
            },
            "narrative_cases": cases,
            "warning_signs": warnings,
            "causes": causes,
            "provenance": {
                "narrative_matching": "Exact normalized industry/business-model codes and Canadian geography fields from reviewed company records.",
                "statistics_canada": statcan["metadata"]["datasets"],
                "osb_insolvencies": osb["metadata"]["datasets"],
            },
            "caveats": list(FOUNDER_INSIGHT_CAVEATS),
        }


def to_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
