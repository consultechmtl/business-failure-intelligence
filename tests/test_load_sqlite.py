import csv
import sqlite3
from contextlib import closing
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class LoadSqliteTests(unittest.TestCase):
    def run_loader(self, database_path, data_dir=None):
        command = [sys.executable, "scripts/load_sqlite.py", "--db", str(database_path)]
        if data_dir is not None:
            command.extend(["--data-dir", str(data_dir)])
        return subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True)

    def test_loads_normalized_tables_and_preserves_company_compatibility_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "corpus.sqlite"
            result = self.run_loader(database_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("aggregate_observations=50862", result.stdout)
            self.assertIn("Loaded 51689 rows", result.stdout)

            with closing(sqlite3.connect(database_path)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM industries").fetchone()[0], 17)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM business_models").fetchone()[0], 16)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM geographies").fetchone()[0], 19)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM entity_aliases").fetchone()[0], 32)
                company = connection.execute(
                    "SELECT industry, business_model, industry_code, business_model_code, geography_code FROM companies WHERE company_id = 'lion-electric'"
                ).fetchone()
                self.assertEqual(company, ("electric vehicles", "vehicle manufacturing", "electric-vehicles", "vehicle-manufacturing", "CA-QC-Saint-Jerome"))
                alias_count = connection.execute("SELECT COUNT(*) FROM entity_aliases WHERE company_id = 'just-for-laughs'").fetchone()[0]
                self.assertEqual(alias_count, 2)
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_loads_curated_corpus_and_joins_assertions_to_companies_and_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "corpus.sqlite"
            result = self.run_loader(database_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            with closing(sqlite3.connect(database_path)) as connection:
                warning_count = connection.execute("SELECT COUNT(*) FROM warning_signs").fetchone()[0]
                warning_joined_count = connection.execute("SELECT COUNT(*) FROM warning_signs AS warning JOIN companies AS company ON company.company_id = warning.company_id JOIN sources AS source ON source.source_id = warning.source_id").fetchone()[0]
                self.assertEqual(warning_count, 10)
                self.assertEqual(warning_joined_count, warning_count)
                assertion_count = connection.execute("SELECT COUNT(*) FROM cause_assertions").fetchone()[0]
                joined_count = connection.execute("SELECT COUNT(*) FROM cause_assertions AS assertion JOIN companies AS company ON company.company_id = assertion.company_id JOIN sources AS source ON source.source_id = assertion.source_id").fetchone()[0]
                self.assertEqual(assertion_count, 43)
                self.assertEqual(joined_count, assertion_count)
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_rejects_invalid_data_before_creating_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "data" / "curated"
            data_dir.mkdir(parents=True)
            for source in (REPO_ROOT / "data" / "curated").glob("*.csv"):
                destination = data_dir / source.name
                destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            outcomes_path = data_dir / "outcomes.csv"
            with outcomes_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
            rows[1][1] = "missing-company"
            with outcomes_path.open("w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerows(rows)
            database_path = root / "rejected.sqlite"
            result = self.run_loader(database_path, data_dir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Validation failed", result.stderr)
            self.assertFalse(database_path.exists())


if __name__ == "__main__":
    unittest.main()
