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

    def test_aggregate_summary_reports_counts_provenance_and_safe_interpretation(self):
        summary = intelligence.aggregate_summary(self.db_path)
        self.assertEqual(summary["observation_count"], 50862)
        self.assertEqual(summary["geographies"], [{"geo": "Canada", "observation_count": 29318}, {"geo": "Quebec", "observation_count": 21544}])
        self.assertEqual(summary["reference_periods"], {"first": "2015-01", "last": "2026-05", "count": 137})
        self.assertEqual([dataset["table_number"] for dataset in summary["datasets"]], ["33-10-0270-01", "33-10-0722-01"])
        self.assertEqual(summary["uom"], ["Number"])
        self.assertIn("not necessarily permanent deaths", summary["interpretation_disclaimer"])

    def test_cross_layer_comparison_keeps_quebec_statcan_and_osb_layers_separate(self):
        payload = intelligence.cross_layer_comparison(
            self.db_path, geo="Quebec", period_start="2026-01", period_end="2026-03", limit=3
        )
        self.assertEqual(payload["filters"], {"geo": "Quebec", "period_start": "2026-01", "period_end": "2026-03"})
        self.assertEqual(payload["statistics_canada"]["label"], "Statistics Canada business-dynamics observations")
        self.assertEqual(payload["osb_insolvencies"]["label"], "OSB BIA insolvency proceeding observations")
        self.assertEqual({row["business_dynamics"] for row in payload["statistics_canada"]["openings"]}, {"Openings"})
        self.assertEqual({row["business_dynamics"] for row in payload["statistics_canada"]["closures"]}, {"Closures"})
        self.assertEqual({row["geo"] for row in payload["statistics_canada"]["openings"]}, {"Quebec"})
        self.assertEqual({row["geo"] for row in payload["osb_insolvencies"]["rows"]}, {"Quebec"})
        self.assertNotIn("rate", payload)
        self.assertNotIn("ratio", payload)
        self.assertIn("not equivalent", payload["metadata"]["safe_language_warnings"][1])
        self.assertEqual(payload["statistics_canada"]["provenance"]["source_tables"], ["33-10-0270-01", "33-10-0722-01"])
        self.assertEqual(payload["osb_insolvencies"]["provenance"]["source_tables"], ["OSB BIA insolvency statistics workbook"])

    def test_cross_layer_comparison_supports_canada_and_is_deterministic(self):
        first = intelligence.cross_layer_comparison(self.db_path, geo="Canada", period_start="2026-01", period_end="2026-03", limit=2)
        second = intelligence.cross_layer_comparison(self.db_path, geo="Canada", period_start="2026-01", period_end="2026-03", limit=2)
        self.assertEqual(first, second)
        self.assertEqual({row["geo"] for row in first["statistics_canada"]["closures"]}, {"Canada"})
        self.assertEqual({row["geo"] for row in first["osb_insolvencies"]["rows"]}, {"Canada"})
        self.assertEqual(first["statistics_canada"]["period_coverage"], {"first": "2026-01", "last": "2026-03", "count": 3})
        self.assertEqual(first["osb_insolvencies"]["period_coverage"], {"first": "2026-01", "last": "2026-03", "count": 3})

    def test_json_serialization_is_deterministic(self):
        payload = intelligence.to_json(intelligence.corpus_summary(self.db_path))
        self.assertEqual(payload, intelligence.to_json(intelligence.corpus_summary(self.db_path)))
        self.assertEqual(json.loads(payload)["companies"], 21)


if __name__ == "__main__":
    unittest.main()
