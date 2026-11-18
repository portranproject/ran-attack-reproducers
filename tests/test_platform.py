#!/usr/bin/env python3
import importlib.util
import json
import os
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
REPROCTL = ROOT / "tools/reproctl.py"
GENERATOR = ROOT / "tools/generate_rule_signal.py"
RULES = ("L3-06", "AN-01", "AN-06a", "AN-02", "AN-04", "AN-07", "AN-08")
SIGNAL_RULES = ("AN-01", "AN-06a", "AN-02", "AN-04", "AN-07", "AN-08")

SPEC = importlib.util.spec_from_file_location("reproctl", REPROCTL)
REPROCTL_MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(REPROCTL_MODULE)


class PlatformTest(unittest.TestCase):
    def test_p5_doctor_checks_the_remote_production_components(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            key = root / "key.pem"
            known = root / "known_hosts"
            credentials = root / "p5.env"
            key.write_text("fixture")
            known.write_text("fixture")
            credentials.write_text(f"SSH_KEY={key}\nKNOWN_HOSTS={known}\n")
            live = root / "live-e2e.conf"
            live.write_text(
                f"CU_HOST=ubuntu@cu.lab\nSSH_KEY={key}\nKNOWN_HOSTS={known}\n"
                "CU_LIVE_RUN_ROOT=/srv/live-runs\nCU_F1_INTERFACE=ens5\nCU_N2_INTERFACE=core0\n"
                "CU_DASHBOARD_URL=https://dashboard.invalid/ingest\n"
                "CU_DASHBOARD_CA_FILE=/srv/platform/dashboard/ingest.crt\n"
            )
            key.chmod(0o600)
            credentials.chmod(0o600)
            live.chmod(0o600)
            profile = {
                "environment": {"P5_CU_HOST": "ubuntu@cu.lab", "LIVE_E2E_CONF": str(live),
                                "CU_PLATFORM_ROOT": "/srv/platform", "CU_DASHBOARD_ENV": "p1",
                                "CU_TELEMETRY_NODE": "p1-e2e"},
                "credentials_file": str(credentials),
                "detector": {"binary": "/srv/platform/detection/build/detector", "config": "/srv/platform/detection/config/detector.json", "commit": "1" * 40},
                "telemetry": {"binary": "/srv/platform/telemetry/build/portran", "commit": "2" * 40},
            }
            hashes = {"detector_sha256": "a" * 64, "detector_config_sha256": "b" * 64,
                      "telemetry_sha256": "c" * 64, "dashboard_sender_sha256": "d" * 64,
                      "dashboard_ca_sha256": "e" * 64}
            completed = subprocess.CompletedProcess([], 0, json.dumps(hashes), "")
            with mock.patch.object(REPROCTL_MODULE.subprocess, "run", return_value=completed) as run:
                self.assertEqual(REPROCTL_MODULE.p5_remote_components(profile), hashes)
            command = run.call_args.args[0]
            self.assertIn("ubuntu@cu.lab", command)
            self.assertIn(f"UserKnownHostsFile={known}", command)

    def test_live_e2e_settings_reject_mismatched_execution_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            conf = root / "live.conf"
            conf.write_text(
                "CU_HOST=ubuntu@cu.lab\nSSH_KEY=/tmp/key\nKNOWN_HOSTS=/tmp/known\n"
                "CU_LIVE_RUN_ROOT=/srv/runs\nCU_F1_INTERFACE=f1\nCU_N2_INTERFACE=n2\n"
                "CU_DASHBOARD_URL=https://dashboard.invalid/ingest\nCU_DASHBOARD_CA_FILE=/srv/ca.pem\n"
            )
            conf.chmod(0o600)
            profile = {
                "environment": {"P5_CU_HOST": "ubuntu@cu.lab", "LIVE_E2E_CONF": str(conf),
                                "CU_PLATFORM_ROOT": "/srv/platform", "CU_DASHBOARD_ENV": "p1",
                                "CU_TELEMETRY_NODE": "p1-e2e"},
                "detector": {"binary": "/wrong/detector", "config": "/srv/platform/detection/config/detector.json"},
                "telemetry": {"binary": "/srv/platform/telemetry/build/portran"},
            }
            with self.assertRaisesRegex(REPROCTL_MODULE.ReproError, "실행 경로가 다릅니다"):
                REPROCTL_MODULE.live_e2e_settings(profile)

    def test_qualified_checkout_rejects_modified_deployment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "test"], check=True)
            runner = root / "bin/runner"
            runner.parent.mkdir()
            runner.write_text("qualified\n")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "baseline"], check=True)
            baseline = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            lock = {
                "schema": "ran-reproducer.integration-lock.v1",
                "reproducer": {
                    "minimum_commit": baseline,
                    "required_files": {"bin/runner": REPROCTL_MODULE.sha256(runner)},
                },
            }
            (root / "integration.lock.json").write_text(json.dumps(lock))
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "lock"], check=True)
            self.assertEqual(REPROCTL_MODULE.check_qualified_checkout(root), subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip())
            runner.write_text("tampered\n")
            with self.assertRaises(REPROCTL_MODULE.ReproError):
                REPROCTL_MODULE.check_qualified_checkout(root)

    def test_catalog_has_exactly_thirteen_rule_families(self):
        result = subprocess.run(
            ["python3", str(REPROCTL), "coverage", "--json"], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        coverage = json.loads(result.stdout)
        self.assertEqual(len(coverage), 13)
        self.assertEqual(set(RULES) - set(coverage), set())
        self.assertTrue(all(len(items) == 1 for items in coverage.values()))

    def test_six_an_signal_generators_are_gap_free_and_distinguish_control(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for rule in SIGNAL_RULES:
                signals = {}
                for mode in ("control", "emulation"):
                    output = root / f"{rule}-{mode}.jsonl"
                    result = subprocess.run(
                        ["python3", str(GENERATOR), rule, mode, f"test-{mode}", str(output)],
                        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    rows = [json.loads(line) for line in output.read_text().splitlines()]
                    self.assertEqual(rows[0]["type"], "hello")
                    self.assertEqual(rows[0]["period_ms"], 100)
                    self.assertNotIn("gap", {row["type"] for row in rows})
                    self.assertEqual([row["seq"] for row in rows], list(range(1, len(rows) + 1)))
                    signals[mode] = [row for row in rows if row["type"] == "ue_evt"]
                self.assertNotEqual(signals["emulation"], signals["control"], rule)

    def test_common_run_seals_and_verifies_detector_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            profiles = root / "profiles"
            runs = root / "runs"
            profiles.mkdir()
            detector = root / "detector"
            detector.write_text(
                "#!/usr/bin/env python3\n"
                "import json,sys\n"
                "p=sys.argv[sys.argv.index('--replay')+1]\n"
                "h=json.loads(open(p,encoding='utf-8').readline())\n"
                "if 'emulation' in h['session']: print('ALERT RAISE rule=AN-01 branch=1')\n"
            )
            detector.chmod(0o700)
            telemetry = root / "telemetry"
            telemetry.write_text("#!/bin/sh\nexit 0\n")
            telemetry.chmod(0o700)
            config = root / "detector.json"
            config.write_text("{}\n")
            profile = {
                "schema": "ran-reproducer.profile.v1",
                "id": "test",
                "backend": "replay",
                "configured": True,
                "lab_only": True,
                "run_root": str(runs),
                "environment": {},
                "detector": {"binary": str(detector), "config": str(config), "repository": "local", "commit": "1" * 40},
                "telemetry": {"binary": str(telemetry), "period_ms": 100, "repository": "local", "commit": "2" * 40},
                "limits": {"max_duration_s": 300, "max_ues": 20, "max_tx_gain_db": None},
                "target_allowlist": ["test-only"],
            }
            (profiles / "test.json").write_text(json.dumps(profile))
            env = dict(os.environ, RAN_REPRO_PROFILE_DIR=str(profiles))
            run = subprocess.run(
                ["python3", str(REPROCTL), "signal-run", "an-01", "emulation", "test-emulation", "--profile", "test", "--enable"],
                cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            output = runs / "test-emulation"
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {"run.json", "observations.jsonl", "oracle.jsonl", "detector.jsonl", "verdict.json", "report.md", "evidence_manifest.json"},
            )
            verify = subprocess.run(
                ["python3", str(REPROCTL), "verify", "test-emulation", "--profile", "test"],
                cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
            )
            self.assertEqual(verify.returncode, 0, verify.stderr)
            self.assertTrue(json.loads((output / "verdict.json").read_text())["passed"])
            (output / "unsealed.txt").write_text("must fail\n")
            rejected = subprocess.run(
                ["python3", str(REPROCTL), "verify", "test-emulation", "--profile", "test"],
                cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("파일 집합", rejected.stderr)

    def test_an02_uses_guti_registration_without_raw_subscriber_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "an02.jsonl"
            result = subprocess.run(
                ["python3", str(GENERATOR), "AN-02", "emulation", "an02-emulation", str(output)],
                cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            registrations = [
                row for row in map(json.loads, output.read_text().splitlines())
                if row.get("msg") == "RegistrationRequest"
            ]
            self.assertEqual(len(registrations), 5)
            self.assertTrue(all(row["f"]["id_type"] == "5G-GUTI" for row in registrations))
            self.assertNotIn("supi", output.read_text().lower())


if __name__ == "__main__":
    unittest.main()
