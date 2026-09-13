import json
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from app.server import create_server  # noqa: E402
from load_sqlite import load  # noqa: E402


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(cls.temp_dir.name) / "corpus.sqlite"
        load(db_path, REPO_ROOT / "data" / "curated", REPO_ROOT / "schema" / "cause_taxonomy.csv", REPO_ROOT / "schema" / "schema.sql")
        cls.server = create_server("127.0.0.1", 0, db_path)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()
        cls.temp_dir.cleanup()

    def request(self, path):
        connection = HTTPConnection("127.0.0.1", self.port)
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        connection.close()
        return response.status, body

    def test_summary_json_is_deterministic(self):
        first = self.request("/summary")
        second = self.request("/summary")
        self.assertEqual(first[0], 200)
        self.assertEqual(first[1], second[1])
        self.assertEqual(json.loads(first[1])["companies"], 21)

    def test_case_endpoint_returns_evidence_and_missing_case_is_404(self):
        status, body = self.request("/companies/wesabe")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["assertions"][0]["evidence_quote"])
        status, body = self.request("/companies/missing")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body), {"error": "company not found"})

    def test_aggregate_summary_is_deterministic_and_includes_provenance(self):
        first = self.request("/aggregate/summary")
        second = self.request("/aggregate/summary")
        self.assertEqual(first, second)
        self.assertEqual(first[0], 200)
        payload = json.loads(first[1])
        self.assertEqual(payload["observation_count"], 50862)
        self.assertEqual(payload["reference_periods"]["first"], "2015-01")
        self.assertIn("not necessarily permanent deaths", payload["interpretation_disclaimer"])
        self.assertEqual(payload["datasets"][0]["table_number"], "33-10-0270-01")

    def test_aggregate_trends_compares_canada_and_quebec_and_filters(self):
        status, body = self.request("/aggregate/trends?dynamics=Closures&limit=500")
        self.assertEqual(status, 200)
        rows = json.loads(body)["rows"]
        self.assertEqual(rows[0]["reference_period"], "2015-01")
        self.assertEqual({row["geo"] for row in rows}, {"Canada", "Quebec"})
        status, body = self.request("/aggregate/trends?geo=Quebec&dynamics=Closures")
        self.assertEqual(status, 200)
        rows = json.loads(body)["rows"]
        self.assertTrue(rows)
        self.assertEqual({row["geo"] for row in rows}, {"Quebec"})
        self.assertEqual({row["business_dynamics"] for row in rows}, {"Closures"})

    def test_aggregate_size_and_industry_filters(self):
        status, body = self.request("/aggregate/by-size?geo=Quebec")
        self.assertEqual(status, 200)
        size_rows = json.loads(body)["rows"]
        self.assertTrue(size_rows)
        self.assertEqual({row["geo"] for row in size_rows}, {"Quebec"})
        status, body = self.request("/aggregate/by-industry?geo=Quebec&employment_size=1%20to%204%20employees")
        self.assertEqual(status, 200)
        industry_rows = json.loads(body)["rows"]
        self.assertTrue(industry_rows)
        self.assertEqual({row["geo"] for row in industry_rows}, {"Quebec"})
        self.assertEqual({row["employment_size"] for row in industry_rows}, {"1 to 4 employees"})

    def test_aggregate_rejects_invalid_or_unbounded_parameters(self):
        for path, expected in (
            ("/aggregate/trends?geo=Ontario", 404),
            ("/aggregate/trends?dynamics=Deaths", 404),
            ("/aggregate/trends?geo=Quebec&geo=Canada", 400),
            ("/aggregate/trends?limit=0", 400),
            ("/aggregate/trends?limit=501", 400),
            ("/aggregate/by-industry?employment_size=unknown", 404),
            ("/aggregate/by-size?unexpected=value", 400),
        ):
            status, _ = self.request(path)
            self.assertEqual(status, expected, path)

    def test_read_endpoints_and_unknown_route(self):
        for path in ("/health", "/companies", "/causes", "/geographies"):
            status, body = self.request(path)
            self.assertEqual(status, 200, path)
            self.assertIsNotNone(json.loads(body))
        status, _ = self.request("/not-a-route")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
