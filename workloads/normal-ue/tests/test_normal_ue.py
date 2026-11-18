import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "workloads" / "normal-ue" / "bin" / "normal-ue"


class NormalUeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.runner = self.executable("runner")
        self.attack = self.executable("attack-ue")
        self.normal = self.executable("normal-ue")
        self.broker = self.file("broker.py")
        self.uecap = self.file("uecap.xml")
        self.attack_cfg = self.file("attack.conf", "uicc0 = { imsi=999; }\n", 0o600)
        self.gnb = self.file("du.yaml")
        self.normal_cfg = self.root / "normal.conf"
        self.write_subscribers([f"00101000000000{i}" for i in range(5)])
        self.conf = self.root / "p5.conf"
        self.conf.write_text(
            "\n".join(
                [
                    f"NORMAL_UE_OAI={self.root}",
                    f"NORMAL_UE_RUNNER={self.runner}",
                    f"NORMAL_UE_ATTACK_BIN={self.attack}",
                    f"NORMAL_UE_BIN={self.normal}",
                    f"NORMAL_UE_UECAP={self.uecap}",
                    f"NORMAL_UE_ATTACK_CFG={self.attack_cfg}",
                    f"NORMAL_UE_CFG={self.normal_cfg}",
                    f"NORMAL_UE_BROKER_PY={self.broker}",
                    f"NORMAL_UE_GNB_CONFIG={self.gnb}",
                    "NORMAL_UE_GNB_STOP_CMD=true",
                    "NORMAL_UE_GNB_RESTART_CMD=true",
                    "NORMAL_UE_GNB_READY_CMD=true",
                    "SETSID_BIN=true",
                    "IP_CMD=true",
                    "PING_CMD=true",
                ]
            )
            + "\n"
        )
        self.conf.chmod(0o600)

    def file(self, name, text="fixture\n", mode=0o644):
        path = self.root / name
        path.write_text(text)
        path.chmod(mode)
        return path

    def executable(self, name):
        return self.file(name, "#!/bin/sh\nexit 0\n", 0o755)

    def write_subscribers(self, values):
        self.normal_cfg.write_text(
            "".join(
                f'uicc{i} = {{ imsi="{value}"; key="00"; opc="00"; '
                'pdu_sessions=( { id=3; dnn="internet"; nssai_sst=1; } ); }\n'
                for i, value in enumerate(values)
            )
        )
        self.normal_cfg.chmod(0o600)

    def run_doctor(self):
        return subprocess.run(
            [str(SCRIPT), "doctor", "--config", str(self.conf), "--count", "5"],
            text=True,
            capture_output=True,
        )

    def test_doctor_accepts_five_unique_subscribers(self):
        result = self.run_doctor()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("normal_ues=5 attack_slot=1", result.stdout)

    def test_doctor_rejects_duplicate_subscribers(self):
        self.write_subscribers(["001010000000001"] * 5)
        result = self.run_doctor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("서로 다른 가입자 설정이 5개 필요합니다", result.stderr)

    def test_doctor_rejects_radio_sections_in_subscriber_config(self):
        with self.normal_cfg.open("a") as stream:
            stream.write("RUs = ( { nb_tx=1; } );\n")
        result = self.run_doctor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RUs/cells를 넣지 마세요", result.stderr)

    def test_doctor_rejects_counts_above_broker_limit(self):
        with self.conf.open("a") as stream:
            stream.write("NORMAL_UE_MAX_COUNT=11\n")
        result = self.run_doctor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("NORMAL_UE_MAX_COUNT는 1..10", result.stderr)

    def test_help_does_not_require_runtime_config(self):
        result = subprocess.run([str(SCRIPT), "--help"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("normal-ue setup|doctor|prepare|start|status|stop", result.stdout)

    def test_prepare_writes_private_shared_ru_runtime_config(self):
        state = self.root / "same-cell-state"
        result = subprocess.run(
            [str(SCRIPT), "prepare", "--config", str(self.conf), "--count", "5"],
            env={**os.environ, "SAME_CELL_NORMAL_STATE_DIR": str(state)},
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        runtime = pathlib.Path(result.stdout.strip())
        self.assertEqual(runtime, state / "normal-ue-runtime.conf")
        self.assertEqual(runtime.stat().st_mode & 0o777, 0o600)
        payload = runtime.read_text()
        self.assertEqual(payload, self.normal_cfg.read_text())
        self.assertNotIn("RUs =", payload)


if __name__ == "__main__":
    unittest.main()
