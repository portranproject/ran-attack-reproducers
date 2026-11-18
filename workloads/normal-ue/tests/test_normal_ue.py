import json
import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "workloads" / "normal-ue" / "bin" / "normal-ue"
BUILD_SCRIPT = ROOT / "workloads" / "normal-ue" / "bin" / "normal-ue-build"


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

    def test_doctor_accepts_another_zmq_profile(self):
        result = subprocess.run(
            [str(SCRIPT), "doctor", "--profile", "p1", "--config", str(self.conf), "--count", "5"],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK p1 same-cell backend", result.stdout)

    def test_doctor_rejects_duplicate_subscribers(self):
        self.write_subscribers(["001010000000001"] * 5)
        result = self.run_doctor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("서로 다른 가입자 설정이 5개 필요합니다", result.stderr)

    def test_doctor_rejects_radio_sections_in_subscriber_config(self):
        for section in ("RUs", "cells", "zmq"):
            with self.subTest(section=section):
                self.write_subscribers([f"00101000000000{i}" for i in range(5)])
                with self.normal_cfg.open("a") as stream:
                    stream.write(f"{section} = ();\n")
                result = self.run_doctor()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("RUs/cells/zmq를 넣지 마세요", result.stderr)

    def test_doctor_rejects_counts_above_broker_limit(self):
        with self.conf.open("a") as stream:
            stream.write("NORMAL_UE_MAX_COUNT=11\n")
        result = self.run_doctor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("NORMAL_UE_MAX_COUNT는 1..10", result.stderr)

    def test_help_does_not_require_runtime_config(self):
        result = subprocess.run([str(SCRIPT), "--help"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("normal-ue setup|build|doctor|prepare|start|status|stop", result.stdout)

    def test_setup_materializes_private_lab_du_config(self):
        profile_dir = self.root / "profiles"
        profile_dir.mkdir()
        profile = {
            "schema": "ran-reproducer.profile.v1", "id": "clean", "backend": "p5",
            "configured": True, "lab_only": True, "run_root": str(self.root / "runs"),
            "environment": {
                "P5_CU_HOST": "cu", "P5_DU_HOST": "du",
                "P5_CU_PRIVATE_IP": "172.31.1.10", "P5_DU_PRIVATE_IP": "172.31.1.11",
            },
            "detector": {"commit": "1" * 40},
            "telemetry": {"commit": "2" * 40, "period_ms": 100},
            "limits": {"max_duration_s": 300, "max_ues": 20},
            "target_allowlist": ["clean-lab"],
        }
        (profile_dir / "clean.json").write_text(json.dumps(profile))
        target = self.root / "ocudu" / "du-broker-default.yaml"
        setup_conf = self.root / "clean.conf"
        setup_conf.write_text(f"NORMAL_UE_GNB_CONFIG={target}\n")
        setup_conf.chmod(0o600)
        result = subprocess.run(
            [str(SCRIPT), "setup", "--profile", "clean", "--config", str(setup_conf)],
            env={**os.environ, "RAN_REPRO_PROFILE_DIR": str(profile_dir)},
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        payload = target.read_text()
        self.assertIn("addrs: 172.31.1.10, bind_addrs: 172.31.1.11", payload)
        self.assertIn("tx_port=tcp://127.0.0.1:2000,rx_port=tcp://127.0.0.1:2001", payload)
        self.assertNotIn("__", payload)

    def test_clean_build_uses_the_complete_ordered_patch_stack(self):
        source = BUILD_SCRIPT.read_text()
        expected = [
            "rss-ue-curated.patch",
            "oai-stale-rnti-dci.patch",
            "oai-msg4-ack-rnti.patch",
            "oai-broker-control-gate.patch",
            "normal-multi-ru.patch",
            "normal-probe-phase.patch",
            "normal-tun-suffix.patch",
            "normal-reconnect-w38.patch",
            "normal-safe-initial-ra.patch",
        ]
        positions = [source.index(name) for name in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('git -C "$OAI" apply --cached "$patch"', source)
        self.assertIn("./build_oai --nrUE -w ZMQ --ninja", source)
        for marker in ("RSS_SHARE_NUE", "OAI_NORMAL_TUN_SUFFIX", "NORMAL_UE_RECOVERY"):
            self.assertIn(marker, source)
        safe = (ROOT / "workloads/normal-ue/patch/normal-safe-initial-ra.patch").read_text()
        self.assertIn("mac && mac->current_UL_BWP", safe)
        self.assertIn("normal_reconnect_pending[rrc->ue_id]", safe)
        self.assertNotIn("if (NR_RRC_MAC_RA_IND(msg_p).RA_succeeded)", safe)

    def test_prepare_writes_private_independent_ru_runtime_config(self):
        state = self.root / "same-cell-state"
        result = subprocess.run(
            [str(SCRIPT), "prepare", "--config", str(self.conf), "--count", "5"],
            env={
                **os.environ,
                "SAME_CELL_NORMAL_STATE_DIR": str(state),
                "NORMAL_UE_ZMQ_ENDPOINT_OFFSET": "2",
            },
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        runtime = pathlib.Path(result.stdout.strip())
        self.assertEqual(runtime, state / "normal-ue-runtime.conf")
        self.assertEqual(runtime.stat().st_mode & 0o777, 0o600)
        payload = runtime.read_text()
        self.assertIn(self.normal_cfg.read_text().strip(), payload)
        self.assertEqual(payload.count('sdr_addrs = "type=zmq"'), 5)
        self.assertEqual(payload.count("ru_id = "), 5)
        self.assertEqual(payload.count("tx_channels = "), 5)
        self.assertIn("tcp://127.0.0.1:2301", payload)
        self.assertIn("tcp://127.0.0.1:2701", payload)


if __name__ == "__main__":
    unittest.main()
