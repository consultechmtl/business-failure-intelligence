import csv
import sqlite3
from contextlib import closing
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))


class AggregateLayerTests(unittest.TestCase):
    def test_normalizer_filters_statcan_rows_and_preserves_required_dimensions(self):
        from normalize_statcan import normalize_rows

        rows = [
            {
                "REF_DATE": "2024-01",
                "GEO": "Canada",
                "North American Industry Classification System (NAICS)": "Total, all industries",
                "Employment size": "1 to 4 employees",
                "Business dynamics": "Openings",
                "UOM": "Number",
                "UOM_ID": "223",
                "SCALAR_FACTOR": "units",
                "SCALAR_ID": "0",
                "VECTOR": "v1",
                "COORDINATE": "1.1.1.1.1",
                "VALUE": "100",
                "STATUS": "",
                "SYMBOL": "",
                "TERMINATED": "",
                "DECIMALS": "0",
            },
            {
                "REF_DATE": "2024-01",
                "GEO": "Ontario",
                "North American Industry Classification System (NAICS)": "Total, all industries",
                "Employment size": "1 to 4 employees",
                "Business dynamics": "Openings",
                "UOM": "Number",
                "VALUE": "999",
                "STATUS": "",
            },
        ]
        normalized = normalize_rows(rows, "33100722", {"Canada", "Quebec"})
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["reference_period"], "2024-01")
        self.assertEqual(normalized[0]["geo"], "Canada")
        self.assertEqual(normalized[0]["business_dynamics"], "Openings")
        self.assertEqual(normalized[0]["table_number"], "33-10-0722-01")

    def test_normalizer_supports_current_statcan_business_dynamics_headers(self):
        from normalize_statcan import normalize_rows

        rows = [
            {
                "REF_DATE": "2026-07",
                "GEO": "Quebec",
                "Industry": "Business sector industries [T004]",
                "Employment size": "Total, all employment sizes",
                "Business dynamics measure": "Business closures",
                "UOM": "Number",
                "VALUE": "123",
                "STATUS": "",
            }
        ]
        normalized = normalize_rows(rows, "33100722", {"Canada", "Quebec"})
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["naics"], "Business sector industries [T004]")
        self.assertEqual(normalized[0]["business_dynamics"], "Closures")

    def test_loader_creates_aggregate_tables_without_company_relationships(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "curated"
            data_dir.mkdir()
            for source in (REPO_ROOT / "data" / "curated").glob("*.csv"):
                (data_dir / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            database = root / "aggregate.sqlite"
            result = subprocess.run(
                [sys.executable, "scripts/load_sqlite.py", "--db", str(database), "--data-dir", str(data_dir)],
                cwd=REPO_ROOT, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with closing(sqlite3.connect(database)) as connection:
                self.assertGreater(connection.execute("SELECT COUNT(*) FROM datasets").fetchone()[0], 0)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM aggregate_observations").fetchone()[0], 50862)
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
                columns = {row[1] for row in connection.execute("PRAGMA table_info(aggregate_observations)")}
                self.assertNotIn("company_id", columns)

    def test_analysis_reports_aggregate_openings_and_closures_for_canada_and_quebec(self):
        result = subprocess.run([sys.executable, "scripts/analyze_aggregate.py"], cwd=REPO_ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Statistics Canada aggregate business dynamics", result.stdout)
        self.assertIn("Canada", result.stdout)
        self.assertIn("Quebec", result.stdout)
        self.assertIn("Openings", result.stdout)
        self.assertIn("Closures", result.stdout)


class OsbInsolvencyTests(unittest.TestCase):
    def test_osb_normalizer_preserves_business_type_and_naics_dimensions(self):
        from normalize_osb_insolvencies import normalize_sheet

        rows = [
            ["BIA Insolvencies Filed by Businesses/Dossiers", "", ""],
            ["", "jan/janv", "mar"],
            ["Quebec/Québec", "10", "12"],
            ["Bankruptcies/Faillites", "3", "4"],
            ["Proposals/Propositions", "7", "8"],
            ["BIA Insolvencies by NAICS Sectors/Dossiers", "", ""],
            ["", "jan/janv", "mar"],
            ["Construction", "5", "6"],
            ["Bankruptcies/Faillites", "1", "2"],
            ["Proposals/Propositions", "4", "4"],
        ]
        normalized = normalize_sheet(rows, 2026, "https://example.test/workbook.xlsx", "2026-09-14")
        self.assertEqual(len(normalized), 8)
        business = [row for row in normalized if row["geo"] == "Quebec" and row["insolvency_type"] == "Bankruptcy"]
        self.assertEqual(business[0]["debtor_type"], "business")
        self.assertEqual(business[0]["business_form"], "all_businesses")
        self.assertEqual(business[0]["reference_period"], "2026-01")
        naics = [row for row in normalized if row["naics"] == "Construction" and row["insolvency_type"] == "Proposal"]
        self.assertEqual(naics[0]["geo"], "Canada")
        self.assertEqual(naics[0]["value"], "4")

    def test_loader_keeps_osb_observations_separate_from_statcan_and_companies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "curated"
            data_dir.mkdir()
            for source in (REPO_ROOT / "data" / "curated").glob("*.csv"):
                (data_dir / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            database = root / "insolvencies.sqlite"
            result = subprocess.run([sys.executable, "scripts/load_sqlite.py", "--db", str(database), "--data-dir", str(data_dir)], cwd=REPO_ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with closing(sqlite3.connect(database)) as connection:
                self.assertGreater(connection.execute("SELECT COUNT(*) FROM osb_insolvency_observations").fetchone()[0], 0)
                columns = {row[1] for row in connection.execute("PRAGMA table_info(osb_insolvency_observations)")}
                self.assertNotIn("company_id", columns)
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
