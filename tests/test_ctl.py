#!/usr/bin/env python3
import os
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

    def test_list_exposes_every_module_and_reproduction_type(self):
        result = self.run_ctl("list")
        self.assertEqual(result.returncode, 0, result.stderr)
        for attack in ("rrc-storm", "blind-dos", "uplink-dos", "auth-timeout", "downlink-imsi", "ue-capability"):
            self.assertIn(attack, result.stdout)
        self.assertIn("프로토콜 결과 에뮬레이션", result.stdout)

    def test_capability_dry_run_maps_to_module_runner(self):
        result = self.run_ctl(
            "run", "ue-capability", "emulation", "test-capability", "--enable", "--dry-run"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ue-capability-run", result.stdout)
        self.assertIn("UE_CAPABILITY_CONF", result.stdout)

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

    def test_control_rejects_enable(self):
        result = self.run_ctl(
            "run", "auth-timeout", "control", "test-run", "--enable", "--dry-run"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("control", result.stderr)

    def test_build_reuses_binary_with_module_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = pathlib.Path(directory)
            binary = tree / "cmake_targets/ran_build/build/nr-uesoftmodem"
            binary.parent.mkdir(parents=True)
            binary.write_text("UPLINK_DOS_EMULATION event=service_request_mac_corrupted")
            binary.chmod(0o700)
            env = dict(os.environ, UPLINK_OAI=str(tree))
            result = self.run_ctl("build", "uplink-dos", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("빌드 준비됨", result.stdout)


if __name__ == "__main__":
    unittest.main()
