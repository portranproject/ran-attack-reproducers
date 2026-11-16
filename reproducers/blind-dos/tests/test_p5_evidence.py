"""p5 log normalization and exact target-owner join tests."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "p5_evidence.py"
RUN_ID = "blind-p5-fixture"
VICTIM = "victim-v"
TARGET = "0x0040c00001b9"
TEST_IMSI = "001010000000001"


class P5EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.victim = self.root / "victim.log"
        self.victim_config = self.root / "victim.conf"
        self.amf = self.root / "amf.raw"
        self.cu = self.root / "cu.raw"
        self.du = self.root / "du.raw"
        self.victim.write_text(
            "[NAS] 5G-GUTI: AMF pointer 0, AMF Set ID 1, "
            "5G-TMSI 3221225913\n"
        )
        self.victim_config.write_text(f'uicc0 = {{ imsi = "{TEST_IMSI}"; }};\n')
        self.amf.write_text(
            "2026-11-02T00:00:01.000000000Z InitialUEMessage\n"
            "2026-11-02T00:00:01.100000000Z "
            "RAN_UE_NGAP_ID[2] AMF_UE_NGAP_ID[1] TAC[1]\n"
            "2026-11-02T00:00:01.110000000Z "
            "[suci-0-001-01-0000-0-0-0000000001] known UE by SUCI\n"
        )
        self.cu.write_text(
            "2026-11-02T00:00:01.050000000Z "
            "ue=2 ran_ue=2: NGAP UE context created\n"
            "2026-11-02T00:00:01.120000000Z "
            "ue=2 ran_ue=2: Setting AMF-UE-NGAP-ID=1\n"
        )
        self.fake_key = "00" * 16
        self.du.write_text(f"untrusted Ki: {self.fake_key}\n")

    def run_tool(self, *args, ok=True):
        result = subprocess.run(
            [sys.executable, str(TOOL), *map(str, args)],
            text=True, capture_output=True, timeout=10,
        )
        if ok and result.returncode != 0:
            self.fail(result.stderr)
        if not ok:
            self.assertNotEqual(result.returncode, 0)
        return result

    def snapshot_before(self):
        output = self.root / "target_snapshot_before.json"
        self.run_tool(
            "snapshot", "--victim-log", self.victim, "--amf-raw", self.amf,
            "--victim-config", self.victim_config,
            "--output", output, "--phase", "before", "--run-id", RUN_ID,
            "--victim-id", VICTIM, "--amf-region-id", "2",
        )
        return output, json.loads(output.read_text())

    def normalize(self):
        outputs = [self.root / name for name in ("amf.log", "cu.log", "du.log")]
        self.run_tool(
            "normalize", "--amf-raw", self.amf, "--cu-raw", self.cu,
            "--du-raw", self.du, "--amf-output", outputs[0],
            "--cu-output", outputs[1], "--du-output", outputs[2],
        )
        return outputs

    def test_before_snapshot_uses_unique_victim_mapping_and_exact_48_bits(self):
        _, snapshot = self.snapshot_before()
        self.assertEqual(snapshot["target_5g_s_tmsi"], TARGET)
        self.assertEqual((snapshot["ran_ue_ngap_id"], snapshot["amf_ue_ngap_id"]), (2, 1))
        self.assertEqual(
            (snapshot["part2"] << 39) | snapshot["part1"], int(TARGET, 16)
        )
        self.assertRegex(snapshot["source_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(snapshot["amf_region_id"], 2)

    def test_before_snapshot_rejects_ambiguous_initial_mappings(self):
        with self.amf.open("a") as output:
            output.write(
                "2026-11-02T00:00:02Z InitialUEMessage\n"
                "2026-11-02T00:00:02Z RAN_UE_NGAP_ID[3] AMF_UE_NGAP_ID[2]\n"
                "2026-11-02T00:00:02Z "
                "[suci-0-001-01-0000-0-0-0000000001] known UE by SUCI\n"
            )
        result = self.run_tool(
            "snapshot", "--victim-log", self.victim, "--amf-raw", self.amf,
            "--victim-config", self.victim_config,
            "--output", self.root / "snapshot.json", "--phase", "before",
            "--run-id", RUN_ID, "--victim-id", VICTIM,
            "--amf-region-id", "2", ok=False,
        )
        self.assertIn("exactly one", result.stderr)

    def test_before_snapshot_ignores_normal_ue_mapping(self):
        with self.amf.open("a") as output:
            output.write(
                "2026-11-02T00:00:02Z InitialUEMessage\n"
                "2026-11-02T00:00:02Z RAN_UE_NGAP_ID[3] AMF_UE_NGAP_ID[2]\n"
                "2026-11-02T00:00:02Z "
                "[suci-0-001-01-0000-0-0-0000000002] known UE by SUCI\n"
            )
        _, snapshot = self.snapshot_before()
        self.assertEqual((snapshot["ran_ue_ngap_id"], snapshot["amf_ue_ngap_id"]), (2, 1))
        self.assertEqual(snapshot["mapping_counts"]["initial"], 2)
        self.assertEqual(snapshot["mapping_counts"]["victim"], 1)

    def test_before_snapshot_selects_only_live_victim_retry(self):
        with self.amf.open("a") as output:
            output.write(
                "2026-11-02T00:00:02Z Clear NG Context\n"
                "2026-11-02T00:00:02Z RAN_UE_NGAP_ID[2] AMF_UE_NGAP_ID[1]\n"
                "2026-11-02T00:00:03Z InitialUEMessage\n"
                "2026-11-02T00:00:03Z RAN_UE_NGAP_ID[4] AMF_UE_NGAP_ID[3]\n"
                "2026-11-02T00:00:03Z "
                "[suci-0-001-01-0000-0-0-0000000001] known UE by SUCI\n"
            )
        _, snapshot = self.snapshot_before()
        self.assertEqual((snapshot["ran_ue_ngap_id"], snapshot["amf_ue_ngap_id"]), (4, 3))
        self.assertEqual(snapshot["mapping_counts"]["released"], 1)
        self.assertEqual(snapshot["mapping_counts"]["surviving"], 1)

    def test_before_snapshot_rejects_explicit_target_mismatch(self):
        self.amf.write_text(
            "2026-11-02T00:00:01Z InitialUEMessage\n"
            "2026-11-02T00:00:01Z "
            "5G-S_TMSI[AMF_ID:0x000040,M_TMSI:0xc00001ba]\n"
            "2026-11-02T00:00:01Z RAN_UE_NGAP_ID[2] AMF_UE_NGAP_ID[1]\n"
            "2026-11-02T00:00:01Z "
            "[suci-0-001-01-0000-0-0-0000000001] known UE by SUCI\n"
        )
        result = self.run_tool(
            "snapshot", "--victim-log", self.victim, "--amf-raw", self.amf,
            "--victim-config", self.victim_config,
            "--output", self.root / "snapshot.json", "--phase", "before",
            "--run-id", RUN_ID, "--victim-id", VICTIM,
            "--amf-region-id", "2", ok=False,
        )
        self.assertIn('"surviving":0', result.stderr)

    def test_after_snapshot_fails_if_victim_guti_changed(self):
        before, _ = self.snapshot_before()
        self.victim.write_text(
            self.victim.read_text()
            + "5G-GUTI: AMF pointer 0, AMF Set ID 1, 5G-TMSI 9\n"
        )
        result = self.run_tool(
            "snapshot", "--victim-log", self.victim, "--amf-raw", self.amf,
            "--victim-config", self.victim_config,
            "--output", self.root / "after.json", "--phase", "after",
            "--before", before, "--run-id", RUN_ID, "--victim-id", VICTIM,
            "--amf-region-id", "2", ok=False,
        )
        self.assertIn("changed", result.stderr)

    def test_normalizer_never_copies_unallowlisted_secret_lines(self):
        outputs = self.normalize()
        combined = "".join(path.read_text() for path in outputs)
        self.assertNotIn(self.fake_key, combined)
        self.assertNotIn("suci-", combined)
        self.assertIn('"event":"slice_digest"', combined)
        self.assertIn('"event":"ngap_binding"', combined)

    def test_same_old_ids_join_identity_reach_and_holding_effect(self):
        before, snapshot = self.snapshot_before()
        self.amf.write_text(
            self.amf.read_text()
            + "2026-11-02T00:00:03.000000000Z InitialUEMessage\n"
            + "2026-11-02T00:00:03.010000000Z [suci-secret] "
              "5G-S_TMSI[AMF_ID:0x000040,M_TMSI:0xc00001b9]\n"
            + "2026-11-02T00:00:03.020000000Z [suci-secret] Holding NG Context\n"
            + "2026-11-02T00:00:03.030000000Z [suci-secret] "
              "RAN_UE_NGAP_ID[2] AMF_UE_NGAP_ID[1]\n"
            + "2026-11-02T00:00:03.040000000Z "
              "RAN_UE_NGAP_ID[2] AMF_UE_NGAP_ID[1]\n"
        )
        amf_log, _, _ = self.normalize()
        attacker = self.root / "attacker.jsonl"
        attacker.write_text(json.dumps({
            "schema": "blind.attacker-event.v1",
            "run_id": RUN_ID,
            "event": "target_msg3_committed",
            "target_5g_s_tmsi": TARGET,
            "realtime_ns": 1793577602500000000,
        }) + "\n")
        output = self.root / "network.jsonl"
        self.run_tool(
            "network-events", "--amf-log", amf_log, "--before", before,
            "--attacker-events", attacker, "--output", output,
            "--run-id", RUN_ID, "--mode", "attack",
        )
        rows = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual({row["event"] for row in rows}, {"identity_reached", "binding_changed"})
        effect = next(row for row in rows if row["event"] == "binding_changed")
        self.assertTrue(effect["exact_join"])
        self.assertEqual((effect["ran_ue_ngap_id"], effect["amf_ue_ngap_id"]), (2, 1))
        self.assertEqual(effect["target_5g_s_tmsi"], snapshot["target_5g_s_tmsi"])

    def test_wrong_id_or_missing_timestamp_never_fabricates_effect(self):
        before, _ = self.snapshot_before()
        self.amf.write_text(
            self.amf.read_text()
            + "Holding NG Context\nRAN_UE_NGAP_ID[99] AMF_UE_NGAP_ID[100]\n"
        )
        amf_log, _, _ = self.normalize()
        attacker = self.root / "attacker.jsonl"
        attacker.write_text(json.dumps({
            "schema": "blind.attacker-event.v1", "run_id": RUN_ID,
            "event": "target_msg3_committed", "target_5g_s_tmsi": TARGET,
            "realtime_ns": 1,
        }) + "\n")
        output = self.root / "network.jsonl"
        self.run_tool(
            "network-events", "--amf-log", amf_log, "--before", before,
            "--attacker-events", attacker, "--output", output,
            "--run-id", RUN_ID, "--mode", "attack",
        )
        rows = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual([row["event"] for row in rows], ["observation"])
        self.assertFalse(rows[0]["exact_join"])

    def test_commit_from_another_run_is_rejected(self):
        before, _ = self.snapshot_before()
        amf_log, _, _ = self.normalize()
        attacker = self.root / "attacker.jsonl"
        attacker.write_text(json.dumps({
            "schema": "blind.attacker-event.v1", "run_id": "other-run",
            "event": "target_msg3_committed", "target_5g_s_tmsi": TARGET,
            "realtime_ns": 1,
        }) + "\n")
        result = self.run_tool(
            "network-events", "--amf-log", amf_log, "--before", before,
            "--attacker-events", attacker, "--output", self.root / "network.jsonl",
            "--run-id", RUN_ID, "--mode", "attack", ok=False,
        )
        self.assertIn("does not match", result.stderr)


if __name__ == "__main__":
    unittest.main()
