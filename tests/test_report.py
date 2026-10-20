"""Offline checks for report errors and the scope of its conclusions."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPORT = Path(__file__).resolve().parents[1] / "bin" / "rss-report"


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log = self.root / "cu.log"
        self.log.write_text("")
        self.env = dict(os.environ, RSS_CONF=str(self.root / "absent.conf"), CAPACITY="96")

    def report(self, *args):
        return subprocess.run(
            ["bash", str(REPORT), "--log", str(self.log), *args],
            env=self.env, text=True, capture_output=True, timeout=10,
        )

    def test_missing_option_value_is_explicit(self):
        result = self.report("--since")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing value for --since", result.stderr)

    def test_empty_log_cannot_produce_a_verdict(self):
        result = self.report("--since", "00:00:01", "--until", "00:00:04")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("== how to read this", result.stdout)
        self.assertNotIn("never hit", result.stdout)

    def test_explicit_missing_jsonl_is_not_silently_ignored(self):
        result = self.report(
            "--since", "00:00:01", "--until", "00:00:04",
            "--jsonl", str(self.root / "missing.jsonl"),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot read", result.stderr)
        self.assertNotIn("== occupancy", result.stdout)

    def test_mixed_outcomes_remain_observations(self):
        self.log.write_text(
            '2026-10-20T00:00:00 [CU] log boundary\n'
            '2026-10-20T00:00:01 [CU] ue=1 "RRC Setup Procedure" started\n'
            '2026-10-20T00:00:02 [CU] rrcReject\n'
            '2026-10-20T00:00:02.250 [CU] rrcSetupComplete\n'
            '2026-10-20T00:00:02.500 [CU] rrcReject\n'
            '2026-10-20T00:00:03 [CU] ue=1 "RRC Setup Procedure" finished successfully\n'
            '2026-10-20T00:00:04 [CU] log boundary\n'
        )
        result = self.report("--since", "00:00:01", "--until", "00:00:04")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("rrcSetupComplete", result.stdout)
        self.assertIn("matching log occurrences", result.stdout)
        self.assertNotIn("denial was CONTINUOUS", result.stdout)
        self.assertNotIn("scenario stayed", result.stdout)


if __name__ == "__main__":
    unittest.main()
