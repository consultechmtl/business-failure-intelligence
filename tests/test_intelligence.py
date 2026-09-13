import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import intelligence  # noqa: E402
from load_sqlite import load  # noqa: E402


class IntelligenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.temp_dir.name) / "corpus.sqlite"
        load(cls.db_path, REPO_ROOT / "data" / "curated", REPO_ROOT / "schema" / "cause_taxonomy.csv", REPO_ROOT / "schema" / "schema.sql")

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_summary_reports_reviewed_corpus_counts(self):
        summary = intelligence.corpus_summary(self.db_path)
        self.assertEqual(summary["companies"], 21)
        self.assertEqual(summary["outcomes"], 21)
        self.assertEqual(summary["sources"], 22)
        self.assertEqual(summary["cause_assertions"], 37)
        self.assertEqual(summary["warning_signs"], 10)
        self.assertEqual(summary["lessons"], 21)
        self.assertEqual(summary["aliases"], 32)

    def test_cause_counts_by_confidence_are_complete_and_ordered(self):
        self.assertEqual(
            intelligence.cause_counts_by_confidence(self.db_path),
            [{"confidence": "high", "count": 27}, {"confidence": "medium", "count": 10}, {"confidence": "low", "count": 0}],
        )

    def test_company_detail_preserves_evidence_linkages(self):
        detail = intelligence.company_case_detail(self.db_path, "wesabe")
        self.assertEqual(detail["company"]["company_id"], "wesabe")
        self.assertEqual(detail["outcomes"][0]["outcome_type"], "shutdown")
        self.assertTrue(detail["sources"][0]["source_url"].startswith("https://"))
        self.assertEqual(detail["assertions"][0]["source_id"], "wesabe-hedlund-2010")
        self.assertTrue(detail["assertions"][0]["evidence_quote"])
        self.assertEqual(detail["warnings"][0]["source_id"], "wesabe-hedlund-2010")
        self.assertTrue(detail["lessons"][0]["lesson"])
        self.assertEqual(detail["aliases"][0]["alias_name"], "Wesabe")

    def test_missing_company_returns_none(self):
        self.assertIsNone(intelligence.company_case_detail(self.db_path, "missing"))

    def test_geography_and_quebec_comparison_are_descriptive(self):
        geography = intelligence.causes_by_geography(self.db_path)
        geography_by_code = {row["geography_code"]: row for row in geography}
        self.assertIn("CA-QC", geography_by_code)
        self.assertGreater(geography_by_code["CA-QC"]["cause_assertions"], 0)
        comparison = intelligence.quebec_vs_international(self.db_path)
        self.assertEqual(comparison["quebec"]["companies"], 7)
        self.assertEqual(comparison["international"]["companies"], 10)

    def test_json_serialization_is_deterministic(self):
        payload = intelligence.to_json(intelligence.corpus_summary(self.db_path))
        self.assertEqual(payload, intelligence.to_json(intelligence.corpus_summary(self.db_path)))
        self.assertEqual(json.loads(payload)["companies"], 21)


if __name__ == "__main__":
    unittest.main()
