"""Offline report regressions; these fixtures contain no radio execution."""
import pathlib
import subprocess
import sys
import tempfile
import unittest


ANALYSIS = pathlib.Path(__file__).resolve().parents[1] / "analysis"


def event(stamp, ue, kind):
    return f'{stamp} [RRC] ue={ue} "RRC Setup Procedure" {kind}\n'


class AnalysisTests(unittest.TestCase):
    def report(self, script, content, start, end, *extra):
        with tempfile.TemporaryDirectory() as directory:
            log = pathlib.Path(directory) / "cu.log"
            log.write_text(content)
            return subprocess.run(
                [sys.executable, str(ANALYSIS / script), str(log), start, end, *extra],
                capture_output=True, text=True, check=False,
            )

    def test_carry_in_and_full_requested_duration(self):
        log = (
            event("2026-10-20T09:59:59", 1, "started")
            + event("2026-10-20T10:00:01", 2, "started")
            + event("2026-10-20T10:00:02", 1, "cancelled")
            + event("2026-10-20T10:00:02.5", 2, "cancelled")
            + "2026-10-20T10:00:03 [INFO] end of capture\n"
        )
        result = self.report("cu_occupancy.py", log, "10:00:00", "10:00:03", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("peak occupancy 2", result.stdout)
        self.assertIn(">=   2      1.0 s of   3.0 s", result.stdout)
        self.assertIn("initial occupancy is unknown", result.stdout)

    def test_carry_out_integrates_to_end_without_in_window_events(self):
        log = (
            event("2026-10-20T09:59:59", 1, "started")
            + event("2026-10-20T10:00:10", 1, "cancelled")
        )
        result = self.report("cu_occupancy.py", log, "10:00:00", "10:00:05", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(">=   1      5.0 s of   5.0 s ( 100%)", result.stdout)

    def test_unmatched_end_is_explicitly_uncertain(self):
        log = (
            "2026-10-20T10:00:00 [INFO] capture\n"
            + event("2026-10-20T10:00:01", 5, "cancelled")
            + "2026-10-20T10:00:02 [INFO] capture\n"
        )
        result = self.report("cu_occupancy.py", log, "10:00:00", "10:00:02")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("evidence uncertain", result.stdout)
        self.assertIn("unmatched endings 1", result.stdout)

    def test_events_at_window_edges_follow_half_open_semantics(self):
        log = (
            event("2026-10-20T09:59:59", 1, "started")
            + event("2026-10-20T10:00:00", 1, "cancelled")
            + event("2026-10-20T10:00:02", 2, "started")
        )
        result = self.report("cu_occupancy.py", log, "10:00:00", "10:00:02", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("peak occupancy 0", result.stdout)
        self.assertIn(">=   1      0.0 s of   2.0 s", result.stdout)

    def test_midnight_is_supported_and_end_is_exclusive(self):
        log = (
            "2026-10-20T23:59:59 [RRC] rrcReject\n"
            "2026-10-21T00:00:00 [RRC] rrcReject\n"
            "2026-10-21T00:00:01 [RRC] rrcReject\n"
        )
        result = self.report("cu_count.py", log, "23:59:59", "00:00:01")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"rrcReject\s+2\s+1\.0/s")

    def test_adjacent_overnight_window_is_not_ambiguous(self):
        log = (
            "2026-10-20T00:00:01 [INFO] capture\n"
            "2026-10-20T23:59:59 [RRC] rrcReject\n"
            "2026-10-21T00:00:01 [INFO] capture\n"
        )
        result = self.report("cu_count.py", log, "23:59:59", "00:00:01")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"rrcReject\s+1\s+0\.5/s")

    def test_offset_timestamps_and_mixed_timezone_style(self):
        log = (
            "2026-10-20T10:00:00Z [RRC] rrcReject\n"
            "2026-10-20T10:00:02Z [INFO] capture\n"
        )
        naive = self.report("cu_count.py", log,
                            "2026-10-20T10:00:00", "2026-10-20T10:00:02")
        self.assertNotEqual(naive.returncode, 0)
        self.assertIn("same timezone style", naive.stderr)
        aware = self.report("cu_count.py", log,
                            "2026-10-20T10:00:00Z", "2026-10-20T10:00:02+00:00")
        self.assertEqual(aware.returncode, 0, aware.stderr)
        self.assertRegex(aware.stdout, r"rrcReject\s+1\s+0\.5/s")

    def test_multiple_dates_require_explicit_bounds(self):
        log = (
            "2026-10-20T09:59:59 [INFO] capture\n"
            "2026-10-20T10:00:01 [RRC] rrcReject\n"
            "2026-10-21T10:00:01 [RRC] rrcReject\n"
            "2026-10-21T10:00:03 [INFO] capture\n"
        )
        ambiguous = self.report("cu_count.py", log, "10:00:00", "10:00:02")
        self.assertNotEqual(ambiguous.returncode, 0)
        self.assertIn("ambiguous", ambiguous.stderr)
        explicit = self.report(
            "cu_count.py", log, "2026-10-21T10:00:00", "2026-10-21T10:00:02"
        )
        self.assertEqual(explicit.returncode, 0, explicit.stderr)
        self.assertRegex(explicit.stdout, r"rrcReject\s+1\s+0\.5/s")

    def test_empty_and_truncated_logs_do_not_produce_verdicts(self):
        for script in ("cu_count.py", "cu_occupancy.py"):
            for log in ("", "2026-10-20T10:00:01 [RRC] rrcReject\n"):
                with self.subTest(script=script, log=log):
                    result = self.report(script, log, "10:00:00", "10:00:02")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("analysis unavailable", result.stderr)
                    self.assertNotIn("peak occupancy", result.stdout)

    def test_rejection_cadence_does_not_claim_service_denial(self):
        log = (
            "2026-10-20T10:00:00 [RRC] rrcReject\n"
            "2026-10-20T10:00:00.25 [RRC] rrcSetupComplete\n"
            "2026-10-20T10:00:00.5 [RRC] rrcReject\n"
            "2026-10-20T10:00:00.75 [RRC] rrcSetupComplete\n"
            "2026-10-20T10:00:02 [INFO] capture\n"
        )
        result = self.report("cu_count.py", log, "10:00:00", "10:00:02")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"rrcSetupComplete\s+2\s+1\.0/s")
        self.assertIn("observed rejection cadence", result.stdout)
        self.assertNotIn("CONTINUOUS", result.stdout)
        self.assertIn("cannot be inferred", result.stdout)
        no_reject = self.report("cu_count.py", log.replace("rrcReject", "heartbeat"),
                                "10:00:00", "10:00:02")
        self.assertIn("no rrcReject observed", no_reject.stdout)
        self.assertNotIn("never hit", no_reject.stdout)


if __name__ == "__main__":
    unittest.main()
