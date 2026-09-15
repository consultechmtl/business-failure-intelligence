import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class AnalyzeCorpusTests(unittest.TestCase):
    def test_reports_deterministic_corpus_summary(self):
        result = subprocess.run(
            [sys.executable, "scripts/analyze_corpus.py"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            "\n".join(
                [
                    "Cause assertions by confidence:",
                    "high: 28",
                    "medium: 15",
                    "low: 0",
                    "",
                    "Cases by country/region:",
                    "CA / AB: 1",
                    "CA / NS: 1",
                    "CA / ON: 4",
                    "CA / QC: 13",
                    "GB / Unknown: 2",
                    "US / CA: 2",
                    "US / PA: 1",
                    "US / Unknown: 3",
                    "Unknown / Unknown: 2",
                    "",
                    "Canada, Quebec, and international cases:",
                    "Canada: 19",
                    "Quebec: 13",
                    "International: 10",
                    "",
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
