#!/usr/bin/env python3
import json
import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
REPROCTL = ROOT / "tools/reproctl.py"
GENERATOR = ROOT / "tools/generate_rule_signal.py"
RULES = ("L3-06", "AN-01", "AN-06a", "AN-02", "AN-04", "AN-07", "AN-08")
SIGNAL_RULES = ("AN-01", "AN-06a", "AN-02", "AN-04", "AN-07", "AN-08")


class PlatformTest(unittest.TestCase):
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
