import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RunUITest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="run-ui-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.profiles = self.directory / "profiles"
        self.profiles.mkdir()
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith("RAN_REPRO_")}
        self.env.update(RAN_REPRO_PROFILE_DIR=str(self.profiles), NO_COLOR="1")

    def write_profile(self, name, *, configured=True, lab_only=True):
        value = {
            "schema": "ran-reproducer.profile.v1", "id": "test-du", "backend": "p5",
            "configured": configured, "lab_only": lab_only,
            "run_root": str(self.directory / "runs"),
            "environment": {
                "P5_CU_HOST": "cu.test.invalid", "P5_DU_HOST": "du.test.invalid",
                "P5_CU_PRIVATE_IP": "192.0.2.10", "P5_DU_PRIVATE_IP": "192.0.2.11",
                "NORMAL_UE_CONF": str(self.directory / "normal ue.conf"),
            },
            "detector": {"commit": "1" * 40},
            "telemetry": {"commit": "2" * 40, "period_ms": 100},
            "limits": {"max_duration_s": 300, "max_ues": 5},
            "target_allowlist": ["du.test.invalid"],
        }
        path = self.profiles / f"{name}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def resolve(self, backend="p5"):
        return subprocess.run(
            [sys.executable, str(ROOT / "tools/reproctl.py"), "local-profile",
             "--backend", backend], cwd=self.directory, env=self.env,
            text=True, capture_output=True, timeout=10,
        )

    def ui(self, keys="", *args):
        # Start outside the repository to check root-relative entrypoint resolution.
        return subprocess.run(
            [str(ROOT / "run.sh"), *args], input=keys, cwd=self.directory,
            env=self.env, text=True, capture_output=True, timeout=30,
        )

    def test_single_ready_profile_ignores_examples_and_unconfigured_profiles(self):
        self.write_profile("sample.example")
        self.write_profile("unfinished", configured=False)
        self.write_profile("local")
        result = self.resolve()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "local")

    def test_du_file_and_explicit_selection_precedence(self):
        explicit = self.write_profile("custom")
        self.write_profile("du")
        result = self.resolve()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "du")
        for selected in ("custom", str(explicit)):
            with self.subTest(selected=selected):
                self.env["RAN_REPRO_PROFILE_ID"] = selected
                result = self.resolve()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), selected)

    def test_missing_and_ambiguous_profiles_fail_without_guessing(self):
        result = self.resolve()
        self.assertEqual(result.returncode, 2)
        self.assertIn("DU 설정이 없습니다", result.stderr)
        self.write_profile("first")
        self.write_profile("second")
        result = self.resolve()
        self.assertEqual(result.returncode, 2)
        self.assertIn("DU 설정이 여러 개", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_relative_profile_paths_survive_controller_directory_change(self):
        path = self.write_profile("local")
        for selection in ("./profiles/local.json", "local"):
            with self.subTest(selection=selection):
                self.env["RAN_REPRO_PROFILE_ID"] = selection
                self.env["RAN_REPRO_PROFILE_DIR"] = "profiles"
                result = self.resolve()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), str(path))
                result = self.ui("1\n3\n2\nrelative-control\n\nq\n", "--dry-run")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("끝남 (종료 코드 0)", result.stdout)
                self.assertIn("normal\\ ue.conf", result.stdout)

    def test_invalid_explicit_selection_does_not_fall_back(self):
        self.write_profile("du")
        self.env["RAN_REPRO_PROFILE_ID"] = "missing"
        result = self.resolve()
        self.assertEqual(result.returncode, 2)
        self.assertIn("profile이 없습니다", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_auto_selected_profile_keeps_existing_validation(self):
        self.write_profile("du", configured=False)
        result = self.resolve()
        self.assertEqual(result.returncode, 2)
        self.assertIn("예제 상태", result.stderr)
        self.write_profile("du", lab_only=False)
        result = self.resolve()
        self.assertEqual(result.returncode, 2)
        self.assertIn("lab_only", result.stderr)
        self.write_profile("du")
        result = self.resolve("ota")
        self.assertEqual(result.returncode, 2)
        self.assertIn("backend가 선택한 환경과 다릅니다", result.stderr)

    def test_control_uses_local_paths_without_profile_selection_or_enable(self):
        self.write_profile("du")
        result = self.ui("1\n3\n2\nui-control\n\nq\n", "--dry-run", "--no-anim")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("same-cell run blind-dos --profile du --mode control", result.stdout)
        self.assertIn("정상 대조", result.stdout)
        self.assertNotIn("profile 선택", result.stdout)
        self.assertIn("normal\\ ue.conf", result.stdout)
        self.assertIn("끝남 (종료 코드 0)", result.stdout)
        command = next(line for line in result.stdout.splitlines() if "실행:" in line)
        self.assertNotIn("--enable", command)
        self.assertIn("--dry-run", command)

    def test_active_menu_delegates_all_seven_modes(self):
        self.write_profile("local")
        attacks = [
            ("rrc-storm", "attack"), ("auth-timeout", "attack"),
            ("blind-dos", "attack"), ("uplink-credential-flood", "attack"),
            ("downlink-imsi", "emulation"), ("ue-capability", "emulation"),
            ("l3-06", "emulation"),
        ]
        for index, (attack, mode) in enumerate(attacks, 1):
            with self.subTest(attack=attack):
                result = self.ui(
                    f"1\n{index}\n3\nui-active\nENABLE\n\nq\n", "--dry-run")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"same-cell run {attack} --profile local --mode {mode}", result.stdout)
                self.assertIn("--run-id ui-active --enable --dry-run", result.stdout)
                self.assertIn("끝남 (종료 코드 0)", result.stdout)

    def test_active_cancel_and_dry_doctor_do_not_invoke_runner(self):
        self.write_profile("du")
        result = self.ui("1\n1\n3\nui-cancel\nno\n\nq\n", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("취소됨", result.stdout)
        self.assertNotIn("실행:", result.stdout)
        result = self.ui("1\n1\n1\n\nq\n", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("same-cell doctor --profile du", result.stdout)
        self.assertIn("doctor 는 실행하지 않음", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_campaign_delegates_to_official_full_campaign(self):
        self.write_profile("du")
        result = self.ui("1\n1\n4\nui-campaign\nENABLE\n\nq\n", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("same-cell campaign l3-live --profile du --campaign-id ui-campaign", result.stdout)
        self.assertIn("--sets 3 --count 5 --enable --dry-run", result.stdout)
        self.assertIn("끝남 (종료 코드 0)", result.stdout)

    def test_missing_profile_returns_to_environment_menu(self):
        result = self.ui("1\n\nq\n", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DU 설정이 없습니다", result.stderr)
        self.assertNotIn("작업 선택", result.stdout)
        self.assertNotIn("실행:", result.stdout)

    def test_usrp_preview_works_without_profile_or_runner(self):
        for index in range(1, 8):
            with self.subTest(attack=index):
                result = self.ui(f"2\n{index}\n\nq\n", "--no-anim")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertIn("USRP ↔ gNB", result.stdout)
                self.assertIn("))▸", result.stdout)
                self.assertIn("◂((", result.stdout)
                self.assertIn("OTA 실행 adapter는 준비 중", result.stdout)
                self.assertNotIn("실행:", result.stdout)

    def test_back_quit_eof_and_help(self):
        self.write_profile("du")
        result = self.ui("1\n1\nb\nb\n2\nb\nq\n", "--no-anim")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ui().returncode, 1)
        result = self.ui("", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("./run.sh", result.stdout)

    def test_frames_export_both_transports_and_bidirectional_motion(self):
        directory = self.directory / "frames"
        result = self.ui("", "--frames", str(directory))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list(directory.glob("frames-*.txt"))), 14)
        for path in directory.glob("frames-usrp-*.txt"):
            with self.subTest(file=path.name):
                content = path.read_text(encoding="utf-8")
                self.assertIn("OTA 실행 adapter 준비 중", content)
                self.assertNotIn("same-cell run", content)
                self.assertNotIn("\x1b", content)
                tx = [line.index("))▸") for line in content.splitlines() if "))▸" in line]
                rx = [line.index("◂((") for line in content.splitlines() if "◂((" in line]
                self.assertEqual(len(tx), 5)
                self.assertEqual(len(rx), 5)
                self.assertLess(tx[0], tx[1])
                self.assertGreater(rx[0], rx[1])


if __name__ == "__main__":
    unittest.main()
