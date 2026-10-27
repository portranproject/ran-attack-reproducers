"""Offline checks for the normal-UE probe: the summary and the runner knobs."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "analysis" / "probe_summary.py"
RUNNER = ROOT / "bin" / "rss-run"


def probe_event(ue, seq, t_ns, event, **extra):
    record = {"type": "event", "run_id": "t", "ue": ue, "seq": seq,
              "t_ns": t_ns, "air_ms": 0, "event": event}
    record.update(extra)
    return json.dumps(record) + "\n"


class ProbeSummaryTests(unittest.TestCase):
    def summarise(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "attempts.jsonl"
            path.write_text(content)
            return subprocess.run(
                [sys.executable, str(SUMMARY), str(path)],
                capture_output=True, text=True, check=False,
            )

    def test_attempts_without_a_connection_are_reported_as_denial(self):
        result = self.summarise(
            probe_event(0, 0, 1_000_000_000, "probe_attempt", **{"try": 1})
            + probe_event(0, 1, 3_000_000_000, "probe_attempt", **{"try": 2})
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("probe attempts      2", result.stdout)
        self.assertIn("probe connected     no", result.stdout)
        self.assertIn("the normal UE never connected", result.stdout)

    def test_connected_reports_the_try_count_and_latency(self):
        result = self.summarise(
            probe_event(0, 0, 1_000_000_000, "probe_attempt", **{"try": 1})
            + probe_event(0, 1, 6_100_000_000, "probe_connected", tries=1, ms=5102)
        )
        self.assertIn("probe connected     yes   tries=1  5102 ms", result.stdout)
        self.assertIn("stayed connected", result.stdout)

    def test_a_run_without_probe_events_says_so(self):
        result = self.summarise(
            probe_event(1, 0, 1_000_000_000, "attempt_start")
        )
        self.assertIn("no probe events", result.stdout)


class RunnerProbeKnobTests(unittest.TestCase):
    def run_with(self, *options):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        runs = pathlib.Path(self.tmp.name) / "runs"
        runs.mkdir()
        env = dict(
            os.environ,
            RSS_CONF=str(pathlib.Path(self.tmp.name) / "absent.conf"),
            LOGDIR=str(runs), OAI="/nonexistent", UE_BIN=shutil.which("true"),
            UE_CFG="/dev/null", UECAP="/dev/null",
            GNB_RESTART_CMD="", GNB_STOP_CMD="",
        )
        result = subprocess.run(
            ["bash", str(RUNNER), "-e", "1", "-d", "1", *options],
            env=env, text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        run = json.loads(next(runs.glob("*/run.json")).read_text())
        return run

    def test_probe_instances_are_removed_from_the_lockstep_batch(self):
        run = self.run_with("-u", "3", "-p", "1")
        self.assertEqual(run["knobs"]["probe_ues"], 1)
        self.assertEqual(run["radio"]["share_nue"], 2)

    def test_no_probe_keeps_every_instance_in_the_batch(self):
        run = self.run_with("-u", "3")
        self.assertEqual(run["knobs"]["probe_ues"], 0)
        self.assertEqual(run["radio"]["share_nue"], 3)


if __name__ == "__main__":
    unittest.main()
