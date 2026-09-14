#!/usr/bin/env python3
"""Minimal standard-library JSON API for the curated failure corpus."""

import argparse
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit


AGGREGATE_PARAMS = {
    "/aggregate/summary": set(),
    "/aggregate/trends": {"geo", "dynamics", "limit"},
    "/aggregate/by-size": {"geo", "dynamics", "limit"},
    "/aggregate/by-industry": {"geo", "dynamics", "employment_size", "limit"},
    "/aggregate/insolvencies": {"geo", "period", "type", "limit"},
}
MAX_AGGREGATE_LIMIT = 500


def aggregate_query(database_path, path, query):
    """Validate bounded aggregate filters before executing a read-only query."""
    params = parse_qs(query, keep_blank_values=True)
    unexpected = set(params).difference(AGGREGATE_PARAMS[path])
    if unexpected or any(len(values) != 1 or not values[0] for values in params.values()):
        return 400, {"error": "invalid query parameters"}
    limit = 500
    if "limit" in params:
        try:
            limit = int(params["limit"][0])
        except ValueError:
            return 400, {"error": "limit must be an integer"}
        if not 1 <= limit <= MAX_AGGREGATE_LIMIT:
            return 400, {"error": f"limit must be between 1 and {MAX_AGGREGATE_LIMIT}"}
    if path == "/aggregate/insolvencies":
        filters = {name: params.get(name, [None])[0] for name in ("geo", "period", "type")}
        valid = intelligence.insolvency_filter_values(database_path)
        for name, value in filters.items():
            if value is not None and value not in valid[name]:
                return 404, {"error": f"{name} not found"}
        return 200, intelligence.aggregate_insolvencies(database_path, filters["geo"], filters["period"], filters["type"], limit)
    filters = {name: params.get(name, [None])[0] for name in ("geo", "dynamics", "employment_size")}
    valid = intelligence.aggregate_filter_values(database_path)
    for name, value in filters.items():
        if value is not None and value not in valid[name]:
            return 404, {"error": f"{name} not found"}
    if path == "/aggregate/summary":
        return 200, intelligence.aggregate_summary(database_path)
    if path == "/aggregate/trends":
        return 200, intelligence.aggregate_trends(database_path, filters["geo"], filters["dynamics"], limit)
    if path == "/aggregate/by-size":
        return 200, intelligence.aggregate_by_size(database_path, filters["geo"], filters["dynamics"], limit)
    return 200, intelligence.aggregate_by_industry(
        database_path, filters["geo"], filters["employment_size"], filters["dynamics"], limit
    )


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import intelligence
from load_sqlite import load


def ensure_database(database_path):
    if database_path is None:
        database_path = ROOT / "data" / "business_failure.sqlite"
        load(database_path, ROOT / "data" / "curated", ROOT / "schema" / "cause_taxonomy.csv", ROOT / "schema" / "schema.sql")
    return Path(database_path)


def create_server(host, port, database_path):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, status, payload):
            body = intelligence.to_json(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            request = urlsplit(self.path)
            path = request.path
            if path in AGGREGATE_PARAMS:
                status, payload = aggregate_query(database_path, path, request.query)
                return self._json(status, payload)
            if path == "/health":
                return self._json(200, {"status": "ok"})
            if path == "/summary":
                return self._json(200, intelligence.corpus_summary(database_path))
            if path == "/companies":
                return self._json(200, intelligence.companies(database_path))
            if path == "/causes":
                return self._json(200, {"by_confidence": intelligence.cause_counts_by_confidence(database_path)})
            if path == "/geographies":
                return self._json(200, {"causes_by_geography": intelligence.causes_by_geography(database_path), "quebec_vs_international": intelligence.quebec_vs_international(database_path)})
            if path.startswith("/companies/") and path.count("/") == 2:
                detail = intelligence.company_case_detail(database_path, unquote(path.rsplit("/", 1)[1]))
                return self._json(200, detail) if detail else self._json(404, {"error": "company not found"})
            return self._json(404, {"error": "not found"})

        def do_POST(self):
            self._json(405, {"error": "method not allowed"})

        def log_message(self, format, *args):
            return

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", type=Path)
    args = parser.parse_args()
    database_path = ensure_database(args.db)
    server = create_server(args.host, args.port, database_path)
    print(f"Serving {database_path} on http://{args.host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
