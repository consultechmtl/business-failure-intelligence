import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_ROWS = {
    "companies.csv": [
        ["company_id", "canonical_name", "legal_name", "country_code", "region_code", "city", "founded_year", "industry", "business_model", "description"],
        ["fixture-co", "Fixture Co", "", "CA", "QC", "", "", "", "", ""],
    ],
    "outcomes.csv": [
        ["outcome_id", "company_id", "outcome_type", "outcome_date", "jurisdiction", "status", "notes"],
        ["fixture-outcome", "fixture-co", "shutdown", "", "", "reported", ""],
    ],
    "sources.csv": [
        ["source_id", "source_url", "title", "publisher", "source_type", "published_date", "accessed_date", "evidence_quality", "notes"],
        ["fixture-source", "https://example.com/fixture", "Fixture source", "", "other", "", "2026-09-11", "unknown", ""],
    ],
    "cause_assertions.csv": [
        ["assertion_id", "company_id", "cause_code", "source_id", "assertion_type", "confidence", "evidence_quote", "analyst_note"],
        ["fixture-assertion", "fixture-co", "unknown", "fixture-source", "analyst_inference", "low", "", ""],
    ],
    "lessons.csv": [
        ["lesson_id", "company_id", "lesson", "applicability", "action_for_founder", "confidence"],
        ["fixture-lesson", "fixture-co", "Fixture only; not a research case.", "", "", "low"],
    ],
}


def write_corpus(root, changes=None):
    changes = changes or {}
    curated = root / "data" / "curated"
    curated.mkdir(parents=True)
    for filename, rows in VALID_ROWS.items():
        rows = changes.get(filename, rows)
        with (curated / filename).open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerows(rows)


def validate(root):
    return subprocess.run(
        [sys.executable, "scripts/validate_data.py", "--data-dir", str(root / "data" / "curated")],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )


class ValidateDataTests(unittest.TestCase):
    def test_accepts_a_valid_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            write_corpus(Path(directory))
            result = validate(Path(directory))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validation passed", result.stdout)

    def test_rejects_missing_required_column(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [row[:] for row in VALID_ROWS["companies.csv"]]
            rows[0].remove("canonical_name")
            write_corpus(root, {"companies.csv": rows})
            result = validate(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required columns", result.stderr)

    def test_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [row[:] for row in VALID_ROWS["companies.csv"]]
            rows.append(rows[1][:])
            write_corpus(root, {"companies.csv": rows})
            result = validate(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate company_id", result.stderr)

    def test_rejects_invalid_foreign_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [row[:] for row in VALID_ROWS["outcomes.csv"]]
            rows[1][1] = "missing-company"
            write_corpus(root, {"outcomes.csv": rows})
            result = validate(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown company_id", result.stderr)

    def test_rejects_disallowed_outcome_confidence_and_assertion_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outcome_rows = [row[:] for row in VALID_ROWS["outcomes.csv"]]
            outcome_rows[1][2] = "failed"
            assertion_rows = [row[:] for row in VALID_ROWS["cause_assertions.csv"]]
            assertion_rows[1][4] = "unsupported"
            assertion_rows[1][5] = "certain"
            write_corpus(root, {"outcomes.csv": outcome_rows, "cause_assertions.csv": assertion_rows})
            result = validate(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid outcome_type", result.stderr)
        self.assertIn("invalid assertion_type", result.stderr)
        self.assertIn("invalid confidence", result.stderr)

    def test_rejects_cause_assertion_without_a_source_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_rows = [row[:] for row in VALID_ROWS["sources.csv"]]
            source_rows[1][1] = ""
            write_corpus(root, {"sources.csv": source_rows})
            result = validate(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source_url is required for cause assertion", result.stderr)

    def test_validates_optional_warning_signs_foreign_keys_confidence_and_unique_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_corpus(root)
            warning_path = root / "data" / "curated" / "warning_signs.csv"
            with warning_path.open("w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerows(
                    [
                        ["warning_id", "company_id", "signal_code", "observed_text", "observed_date", "source_id", "confidence"],
                        ["fixture-warning", "fixture-co", "demand", "Demand was weak.", "2026-01-01", "fixture-source", "high"],
                        ["fixture-warning", "missing-company", "demand", "Demand was weak.", "", "missing-source", "certain"],
                    ]
                )
            result = validate(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate warning_id", result.stderr)
        self.assertIn("unknown company_id", result.stderr)
        self.assertIn("unknown source_id", result.stderr)
        self.assertIn("invalid confidence", result.stderr)


if __name__ == "__main__":
    unittest.main()
