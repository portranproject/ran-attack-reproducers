#!/usr/bin/env python3
import os
import json
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CTL = ROOT / "ctl.sh"


class ControllerTest(unittest.TestCase):
    def run_ctl(self, *args, env=None):
        return subprocess.run(
            ["bash", str(CTL), *args], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        )

    def profile(self, root, backend="p5", environment=None):
        value = {
            "schema": "ran-reproducer.profile.v1", "id": "lab", "backend": backend,
            "configured": True, "lab_only": True, "run_root": str(root / "runs"),
            "environment": environment or {},
            "detector": {"binary": "/tmp/detector", "config": "/tmp/detector.json",
                         "repository": "local", "commit": "1" * 40},
            "telemetry": {"binary": "/tmp/portran", "period_ms": 100,
                          "repository": "local", "commit": "2" * 40},
            "limits": {"max_duration_s": 300, "max_ues": 20, "max_tx_gain_db": 0},
            "target_allowlist": ["lab-only"], "rf": None,
        }
        if backend == "p5":
            value["environment"].update({
                "P5_CU_HOST": "cu.lab", "P5_DU_HOST": "du.lab",
                "P5_CU_PRIVATE_IP": "10.0.0.10", "P5_DU_PRIVATE_IP": "10.0.0.11",
            })
        else:
            value["rf"] = {"shielding_confirmed": True, "clock_source": "external",
                           "devices": [{"role": "attacker-ue", "serial": "A"},
                                       {"role": "o-du", "serial": "B"}]}
        (root / "lab.json").write_text(json.dumps(value))

    def test_list_exposes_every_module_and_reproduction_type(self):
        result = self.run_ctl("list")
        self.assertEqual(result.returncode, 0, result.stderr)
        for attack in ("rrc-storm", "blind-dos", "uplink-dos", "uplink-credential-flood", "auth-timeout", "downlink-imsi", "ue-capability"):
            self.assertIn(attack, result.stdout)
        self.assertIn("프로토콜 결과 에뮬레이션", result.stdout)

    def test_capability_dry_run_maps_to_module_runner(self):
        result = self.run_ctl(
            "run", "ue-capability", "emulation", "test-capability", "--enable", "--dry-run"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ue-capability-run", result.stdout)
        self.assertIn("UE_CAPABILITY_CONF", result.stdout)

    def test_l3_06_dry_run_maps_to_live_runner(self):
        result = self.run_ctl(
            "run", "l3-06", "emulation", "test-l3-06", "--enable", "--dry-run"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("nas-counter-desync-run", result.stdout)
        self.assertIn("NAS_DESYNC_CONF", result.stdout)

    def test_active_run_requires_explicit_enable(self):
        result = self.run_ctl("run", "blind-dos", "attack", "test-run", "--dry-run")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--enable", result.stderr)

    def test_dry_run_maps_to_existing_module_runner(self):
        result = self.run_ctl(
            "run", "uplink-dos", "emulation", "test-run", "--enable", "--dry-run"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("uplink-run", result.stdout)
        self.assertIn("emulation", result.stdout)
        self.assertIn("-e 1", result.stdout)

    def test_credential_flood_dry_run_maps_to_detection_runner(self):
        result = self.run_ctl(
            "run", "uplink-credential-flood", "attack", "test-flood", "--enable", "--dry-run"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("uplink-credential-flood-run", result.stdout)
        self.assertIn("attack", result.stdout)

    def test_credential_flood_build_requires_ue_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = pathlib.Path(directory)
            binary = tree / "cmake_targets/ran_build/build/nr-uesoftmodem"
            binary.parent.mkdir(parents=True)
            binary.write_text("UPLINK_DOS_DETECTION event=registration_failure\nOAI_SAME_CELL_GATE_FILE")
            binary.chmod(0o700)
            env = dict(os.environ, UPLINK_OAI=str(tree))
            result = self.run_ctl("build", "uplink-credential-flood", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("빌드 준비됨", result.stdout)

    def test_manifest_scenario_alias_and_generated_campaign_id(self):
        result = self.run_ctl(
            "campaign", "rrc-context-exhaustion", "--enable", "--dry-run"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("rss-run", result.stdout)
        self.assertIn("set 1..3", result.stdout)

    def test_explicit_profile_selects_external_module_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            config = root / "capability.conf"
            self.profile(root, environment={"UE_CAPABILITY_CONF": str(config)})
            env = dict(os.environ, RAN_REPRO_PROFILE_DIR=str(root))
            result = self.run_ctl(
                "run", "ue-capability", "control", "profile-control", "--profile", "lab", "--dry-run",
                env=env,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(config), result.stdout)

    def test_ota_protocol_run_fails_until_adapter_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            self.profile(root, backend="ota")
            env = dict(os.environ, RAN_REPRO_PROFILE_DIR=str(root))
            result = self.run_ctl(
                "run", "ue-capability", "control", "ota-control", "--profile", "lab", "--dry-run",
                env=env,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OTA 실행 adapter", result.stderr)

    def test_validate_routes_to_manifest_catalog(self):
        result = self.run_ctl("validate")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("13 modules", result.stdout)

    def test_control_rejects_enable(self):
        result = self.run_ctl(
            "run", "auth-timeout", "control", "test-run", "--enable", "--dry-run"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("control", result.stderr)

    def test_auth_timeout_dry_run_uses_qualified_two_by_five_runner(self):
        result = self.run_ctl(
            "campaign", "auth-timeout", "auth-qualified", "--enable", "--dry-run"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("auth-stall-cell-run"), 6)
        self.assertNotIn("auth-timeout-run", result.stdout)

    def test_same_cell_suite_dry_run_uses_seven_live_ran_paths(self):
        result = self.run_ctl(
            "same-cell", "campaign", "l3-live", "--campaign-id", "suite",
            "--sets", "3", "--count", "5", "--enable", "--dry-run",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("실행 예정:"), 42)
        self.assertEqual(result.stdout.count("timeout --signal=TERM --kill-after=60s 900s"), 42)
        self.assertEqual(result.stdout.count("LIVE_E2E_WAIT_FOR_BASELINE=1"), 30)
        for runner in (
            "rss-broker-witness", "auth-stall-cell-run", "blind-run",
            "uplink-credential-flood-run", "downlink-imsi-run",
            "ue-capability-run", "nas-counter-desync-run",
        ):
            self.assertIn(runner, result.stdout)
        self.assertNotIn("generate_rule_signal.py", result.stdout)
        rrc_lines = [line for line in result.stdout.splitlines() if "rss-broker-witness" in line]
        self.assertEqual(len(rrc_lines), 6)
        self.assertTrue(all(
            "BROKER_NORMAL_CONF=" in line
            and "BROKER_WITNESS_MULTI_RU=1" in line
            and "BROKER_WITNESS_PHASE_MS=3000" in line
            and "NORMAL_UE_BROKER_ENDPOINTS=11" in line
            and "-d 240" in line
            for line in rrc_lines
        ))

    def test_same_cell_p1_dry_run_uses_p1_normal_ue_config(self):
        result = self.run_ctl(
            "same-cell", "run", "blind-dos", "--profile", "p1",
            "--mode", "control", "--dry-run",
            env=dict(os.environ, RAN_REPRO_PROFILE_ID="p1"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("workloads/normal-ue/conf/p1.conf", result.stdout)

    def test_same_cell_active_run_requires_enable(self):
        result = self.run_ctl(
            "same-cell", "run", "blind-dos", "--mode", "attack", "--dry-run",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--enable", result.stderr)

    def test_same_cell_phase_timeout_is_bounded(self):
        for value in ("0", "1801"):
            result = self.run_ctl(
                "same-cell", "run", "blind-dos", "--mode", "control", "--dry-run",
                env=dict(os.environ, SAME_CELL_PHASE_TIMEOUT_S=value),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("1..1800", result.stderr)

    def test_build_reuses_binary_with_module_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = pathlib.Path(directory)
            binary = tree / "cmake_targets/ran_build/build/nr-uesoftmodem"
            binary.parent.mkdir(parents=True)
            binary.write_text("UPLINK_DOS_EMULATION event=service_request_mac_corrupted\nOAI_SAME_CELL_GATE_FILE")
            binary.chmod(0o700)
            env = dict(os.environ, UPLINK_OAI=str(tree))
            result = self.run_ctl("build", "uplink-dos", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("빌드 준비됨", result.stdout)


if __name__ == "__main__":
    unittest.main()
