"""Offline policy checks for the broker witness retry wrapper."""
import json
import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "rss-broker-witness-retry"


class BrokerWitnessRetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.runs = self.root / "runs"
        self.runs.mkdir()
        self.trace = self.root / "trace"
        self.runner = self.root / "fake-runner"
        self.runner.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            "mode = sys.argv[1]\n"
            "run_id = sys.argv[sys.argv.index('-n') + 1]\n"
            "trace = pathlib.Path(os.environ['FAKE_TRACE'])\n"
            "seen = trace.read_text().splitlines() if trace.exists() else []\n"
            "plan = json.loads(os.environ['FAKE_PLAN'])[len(seen)]\n"
            "with trace.open('a') as stream: stream.write(run_id + '\\n')\n"
            "out = pathlib.Path(os.environ['BROKER_LOGDIR']) / run_id\n"
            "out.mkdir()\n"
            "if plan.get('no_result'):\n"
            "    raise SystemExit(plan.get('rc', 1))\n"
            "if plan.get('corrupt'):\n"
            "    (out / 'result.json').write_text('{broken')\n"
            "    raise SystemExit(plan.get('rc', 1))\n"
            "data = {\n"
            "  'type': 'broker_witness_result', 'run_id': run_id, 'mode': mode,\n"
            "  'valid': plan['valid'], 'reason': plan['reason'],\n"
            "  'sync_ues': plan.get('sync_ues', 5),\n"
            "  'crash_markers': plan.get('crash_markers', 0),\n"
            "  'topology': plan.get('topology', {'ue_processes': 5}),\n"
            "  'startup': plan.get('startup', {'sync_ready': True, 'sync_timeout': False}),\n"
            "  'teardown': plan.get('teardown', {'ue_exit_statuses': [0, 0, 0, 0, 0], 'broker_exit_status': 0, 'ue_sigsegv_count': 0, 'broker_sigsegv': False, 'forced_kill_count': 0}),\n"
            "  'witness': {'service_ok': plan.get('service_ok', False)},\n"
            "}\n"
            "if plan.get('wrong_id'): data['run_id'] = 'wrong-id'\n"
            "(out / 'result.json').write_text(json.dumps(data))\n"
            "raise SystemExit(plan.get('rc', 0 if plan['valid'] else 1))\n"
        )
        self.runner.chmod(0o755)

    @staticmethod
    def timeout_result():
        return {
            "valid": False,
            "reason": "infrastructure_failure",
            "sync_ues": 0,
            "crash_markers": 0,
            "startup": {"sync_ready": False, "sync_timeout": True},
            "rc": 1,
        }

    @staticmethod
    def valid_result(service_ok=False):
        return {
            "valid": True,
            "reason": "ok",
            "sync_ues": 5,
            "crash_markers": 0,
            "startup": {"sync_ready": True, "sync_timeout": False},
            "service_ok": service_ok,
            "rc": 0,
        }

    def run_wrapper(self, plan, mode="attack", base="bw-campaign", attempts=3):
        env = dict(
            os.environ,
            RSS_CONF=str(self.root / "missing.conf"),
            BROKER_LOGDIR=str(self.runs),
            BROKER_WITNESS_BIN=str(self.runner),
            FAKE_PLAN=json.dumps(plan),
            FAKE_TRACE=str(self.trace),
        )
        return subprocess.run(
            [
                "bash",
                str(SCRIPT),
                mode,
                "-n",
                base,
                "-a",
                str(attempts),
                "-d",
                "1",
            ],
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )

    def trace_ids(self):
        return self.trace.read_text().splitlines() if self.trace.exists() else []

    def test_retries_sync_timeouts_under_unique_ids_then_accepts_valid_result(self):
        result = self.run_wrapper(
            [self.timeout_result(), self.timeout_result(), self.valid_result(False)]
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(
            self.trace_ids(),
            ["bw-campaign-try01", "bw-campaign-try02", "bw-campaign-try03"],
        )

    def test_seven_process_timeout_retries_then_accepts_matching_teardown(self):
        timeout = self.timeout_result()
        timeout["topology"] = {"ue_processes": 7}
        timeout["teardown"] = {
            "ue_exit_statuses": [0] * 7,
            "broker_exit_status": 0,
            "ue_sigsegv_count": 0,
            "broker_sigsegv": False,
            "forced_kill_count": 0,
        }
        valid = self.valid_result()
        valid.update(sync_ues=7, topology={"ue_processes": 7})
        valid["teardown"] = dict(timeout["teardown"])
        result = self.run_wrapper([timeout, valid], base="bw-seven")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.trace_ids(), ["bw-seven-try01", "bw-seven-try02"])

    def test_teardown_length_must_match_topology(self):
        invalid = self.timeout_result()
        invalid["topology"] = {"ue_processes": 7}
        result = self.run_wrapper([invalid], base="bw-seven-bad")
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertEqual(self.trace_ids(), ["bw-seven-bad-try01"])

    def test_sequential_recovery_counts_six_starts_on_five_endpoints(self):
        valid = self.valid_result()
        valid["topology"] = {"ue_processes": 5, "ue_process_starts": 6}
        valid["teardown"] = {
            "ue_exit_statuses": [0] * 6,
            "broker_exit_status": 0,
            "ue_sigsegv_count": 0,
            "broker_sigsegv": False,
            "forced_kill_count": 0,
        }
        result = self.run_wrapper([valid], base="bw-recovery")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

        self.trace.unlink()
        invalid = dict(valid)
        invalid["teardown"] = dict(valid["teardown"], ue_exit_statuses=[0] * 5)
        result = self.run_wrapper([invalid], base="bw-recovery-bad")
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)

    def test_valid_attack_service_failure_is_not_retried(self):
        result = self.run_wrapper([self.valid_result(False)])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.trace_ids(), ["bw-campaign-try01"])

    def test_semantic_invalid_result_is_not_retried(self):
        invalid = self.timeout_result()
        invalid.update(reason="zero_attack_attempts", startup={"sync_timeout": False})
        result = self.run_wrapper([invalid])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.trace_ids(), ["bw-campaign-try01"])

    def test_teardown_anomaly_is_not_retried(self):
        anomalies = (
            {
                "ue_exit_statuses": [139, 0, 0, 0, 0],
                "broker_exit_status": 0,
                "ue_sigsegv_count": 1,
                "broker_sigsegv": False,
                "forced_kill_count": 0,
            },
            {
                "ue_exit_statuses": [0, 0, 0, 0, 0],
                "broker_exit_status": 1,
                "ue_sigsegv_count": 0,
                "broker_sigsegv": False,
                "forced_kill_count": 0,
            },
        )
        for index, teardown in enumerate(anomalies, 1):
            with self.subTest(teardown=teardown):
                self.trace.unlink(missing_ok=True)
                invalid = self.timeout_result()
                invalid["teardown"] = teardown
                result = self.run_wrapper([invalid], base=f"bw-teardown-{index}")
                self.assertEqual(result.returncode, 1)
                self.assertEqual(self.trace_ids(), [f"bw-teardown-{index}-try01"])

    def test_valid_observation_with_teardown_anomaly_is_not_accepted_or_retried(self):
        result_plan = self.valid_result(service_ok=False)
        result_plan["teardown"] = {
            "ue_exit_statuses": [0, 0, 0, 0, 0],
            "broker_exit_status": 139,
            "ue_sigsegv_count": 0,
            "broker_sigsegv": True,
            "forced_kill_count": 0,
        }
        result = self.run_wrapper([result_plan])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.trace_ids(), ["bw-campaign-try01"])

    def test_missing_corrupt_or_mismatched_result_is_not_retried(self):
        cases = (
            {"no_result": True, "rc": 1},
            {"corrupt": True, "rc": 1},
            dict(self.valid_result(), wrong_id=True),
        )
        for index, plan in enumerate(cases, 1):
            with self.subTest(plan=plan):
                self.trace.unlink(missing_ok=True)
                result = self.run_wrapper([plan], base=f"bw-bad-{index}")
                self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
                self.assertEqual(self.trace_ids(), [f"bw-bad-{index}-try01"])

    def test_existing_planned_path_aborts_before_running_any_attempt(self):
        occupied = self.runs / "bw-existing-try02"
        occupied.mkdir()
        marker = occupied / "keep"
        marker.write_text("original\n")
        result = self.run_wrapper(
            [self.valid_result()], base="bw-existing", attempts=3
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.trace_ids(), [])
        self.assertEqual(marker.read_text(), "original\n")
        self.assertFalse((self.runs / "bw-existing-try01").exists())

    def test_exhausted_sync_timeout_budget_preserves_every_attempt(self):
        result = self.run_wrapper([self.timeout_result()] * 3)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.trace_ids()), 3)
        for attempt in range(1, 4):
            self.assertTrue(
                (self.runs / f"bw-campaign-try{attempt:02d}" / "result.json").is_file()
            )

    def test_runner_exit_and_result_must_agree(self):
        inconsistent = self.valid_result()
        inconsistent["rc"] = 1
        result = self.run_wrapper([inconsistent])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.trace_ids(), ["bw-campaign-try01"])


if __name__ == "__main__":
    unittest.main()
