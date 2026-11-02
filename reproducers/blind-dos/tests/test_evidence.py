"""Blind DoS label and immutable evidence contracts; no radio is started."""

import json
from pathlib import Path
import sys
import tempfile
import unittest


ANALYSIS = Path(__file__).resolve().parents[1] / "analysis"
sys.path.insert(0, str(ANALYSIS))

import evidence_manifest  # noqa: E402
import export_labels  # noqa: E402
from identity import split_5g_s_tmsi  # noqa: E402


TARGET = "0x0123456789ab"
PART1, PART2 = split_5g_s_tmsi(TARGET)
RUN_ID = "blind-fixture-1"
OWNER = "victim-v"


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name) / RUN_ID
        self.run.mkdir()
        self.make_attack_run()

    def write_json(self, name, value):
        (self.run / name).write_text(json.dumps(value, sort_keys=True) + "\n")

    def write_jsonl(self, name, rows):
        (self.run / name).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))

    def snapshot(self, when):
        return {
            "schema": "blind.target-snapshot.v1",
            "run_id": RUN_ID,
            "owner_role": "target_owner_existing",
            "owner_id": OWNER,
            "fiveg_guti": "fixture-guti",
            "amf_region_id": 2,
            "target_5g_s_tmsi": TARGET,
            "part1": PART1,
            "part2": PART2,
            "ran_ue_ngap_id": 17,
            "amf_ue_ngap_id": 23,
            "captured_realtime_ns": when,
            "source_sha256": "a" * 64,
        }

    def service(self, phase, when, healthy, registration_count=None, pdu_count=None):
        registration_count = (2 if phase == "after" else 1) \
            if registration_count is None else registration_count
        pdu_count = (2 if phase == "after" else 1) \
            if pdu_count is None else pdu_count
        return {
            "schema": "blind.victim-service.v1",
            "run_id": RUN_ID,
            "victim_id": OWNER,
            "phase": phase,
            "registration": healthy,
            "pdu_session": healthy,
            "ping_ok": healthy,
            "victim_pid": 4242,
            "registration_count": registration_count,
            "pdu_session_count": pdu_count,
            "realtime_ns": when,
        }

    def network(self, role="target_owner_existing", owner=OWNER,
                event="ue_context_released", ran=17, amf=23, when=300):
        return {
            "schema": "blind.network-event.v1",
            "run_id": RUN_ID,
            "role": role,
            "owner_id": owner,
            "target_5g_s_tmsi": TARGET,
            "event": event,
            "exact_join": True,
            "ran_ue_ngap_id": ran,
            "amf_ue_ngap_id": amf,
            "realtime_ns": when,
        }

    def identity_reached(self, when=250):
        return {
            "schema": "blind.network-event.v1",
            "run_id": RUN_ID,
            "role": "attacker_new",
            "owner_id": "attacker-new",
            "target_5g_s_tmsi": TARGET,
            "event": "identity_reached",
            "exact_join": True,
            "realtime_ns": when,
        }

    def make_attack_run(self):
        self.write_json("run.json", {
            "schema_version": "blind.run.v1",
            "run_id": RUN_ID,
            "mode": "attack",
            "attack_enabled": True,
            "recovery_method": "same_victim_process_after_one_shot_end",
            "thresholds": {"loss_consecutive_pings": 1},
        })
        self.write_json("target_snapshot_before.json", self.snapshot(100))
        self.write_json("target_snapshot_after.json", self.snapshot(600))
        target_value = int(TARGET, 16)
        self.write_jsonl("attacker_events.jsonl", [{
            "schema": "blind.attacker-event.v1",
            "run_id": RUN_ID,
            "seq": 1,
            "ue": 0,
            "realtime_ns": 200,
            "monotonic_ns": 20,
            "event": "target_msg3_committed",
            "target_5g_s_tmsi": TARGET,
            "part1": PART1,
            "part2": PART2,
            "claim": "payload_committed_not_air_confirmed",
        }, {
            "schema": "blind.attacker-event.v1", "run_id": RUN_ID,
            "seq": 2, "ue": 0, "realtime_ns": 210, "monotonic_ns": 21,
            "event": "nas_guti_selected", "amf_region_id": 2,
            "amf_set_id": (target_value >> 38) & 0x3ff,
            "amf_pointer": (target_value >> 32) & 0x3f,
            "tmsi": target_value & 0xffffffff,
        }, {
            "schema": "blind.attacker-event.v1", "run_id": RUN_ID,
            "seq": 3, "ue": 0, "realtime_ns": 220, "monotonic_ns": 22,
            "event": "authentication_request_withheld",
            "response_submitted": False,
        }])
        self.write_jsonl("victim_service.jsonl", [
            self.service("before", 150, True),
            self.service("during", 400, False),
            self.service("recovery", 500, False),
            self.service("after", 550, True),
        ])
        self.write_jsonl("ground_truth.jsonl", [self.identity_reached(), self.network()])
        for name in ("amf.log", "cu.log", "du.log", "ngap.pcap", "f1ap.pcap"):
            (self.run / name).write_bytes((name + " fixture\n").encode())

    def finish(self, classification=None):
        verdict = export_labels.write_verdict(self.run)
        classification = classification or (
            "passed" if export_labels._phase_passed(verdict) else "valid-failure")
        self.write_json("run_stop.json", {
            "schema_version": "blind.run-stop.v1",
            "run_id": RUN_ID,
            "mode": verdict["mode"],
            "classification": classification,
            "passed": classification == "passed",
            "valid": classification != "infrastructure-invalid",
            "reason": "matched_phase_contract_met" if classification == "passed"
            else "attack_effect_contract_not_met",
            "checks": {},
            "verdict": verdict,
            "t_stop_utc": "2026-11-02T00:00:00Z",
            "t_stop_ns": 700,
        })
        return verdict

    def test_target_owner_effect_loss_and_same_victim_recovery_pass(self):
        verdict = export_labels.evaluate_run(self.run)
        self.assertTrue(verdict["target_owner_state_effect"])
        self.assertTrue(verdict["exact_join"])
        self.assertTrue(verdict["victim_service_loss"])
        self.assertTrue(verdict["same_victim_recovery"])
        self.assertTrue(export_labels._phase_passed(verdict))

    def test_recovery_without_sealed_same_process_method_does_not_pass(self):
        run = json.loads((self.run / "run.json").read_text())
        del run["recovery_method"]
        self.write_json("run.json", run)
        verdict = export_labels.evaluate_run(self.run)
        self.assertFalse(verdict["same_victim_recovery"])
        self.assertFalse(export_labels._phase_passed(verdict))

    def test_recovery_requires_same_pid_and_new_registration_and_session(self):
        rows = [json.loads(line) for line in
                (self.run / "victim_service.jsonl").read_text().splitlines()]
        rows[-1]["victim_pid"] = 9999
        self.write_jsonl("victim_service.jsonl", rows)
        self.assertFalse(export_labels.evaluate_run(self.run)["same_victim_recovery"])

        rows[-1]["victim_pid"] = 4242
        rows[-1]["registration_count"] = 1
        rows[-1]["pdu_session_count"] = 1
        self.write_jsonl("victim_service.jsonl", rows)
        self.assertFalse(export_labels.evaluate_run(self.run)["same_victim_recovery"])

    def test_attacker_own_context_release_is_never_a_target_effect(self):
        self.write_jsonl("ground_truth.jsonl", [
            self.identity_reached(),
            self.network(role="attacker_new", owner="attacker-a", ran=99, amf=101),
        ])
        verdict = export_labels.evaluate_run(self.run)
        self.assertFalse(verdict["target_owner_state_effect"])
        self.assertFalse(verdict["exact_join"])
        self.assertTrue(verdict["victim_service_loss"])
        self.assertTrue(verdict["same_victim_recovery"])
        self.assertFalse(export_labels._phase_passed(verdict))

    def test_loss_requires_the_sealed_consecutive_probe_threshold(self):
        run = json.loads((self.run / "run.json").read_text())
        run["thresholds"]["loss_consecutive_pings"] = 3
        self.write_json("run.json", run)
        self.write_jsonl("victim_service.jsonl", [
            self.service("before", 150, True),
            self.service("during", 350, False),
            self.service("during", 400, False),
            self.service("during", 450, True),
            self.service("recovery", 500, False),
            self.service("after", 550, True),
        ])
        self.assertFalse(export_labels.evaluate_run(self.run)["victim_service_loss"])

        self.write_jsonl("victim_service.jsonl", [
            self.service("before", 150, True),
            self.service("during", 350, False),
            self.service("during", 400, False),
            self.service("during", 450, False),
            self.service("recovery", 500, False),
            self.service("after", 550, True),
        ])
        self.assertTrue(export_labels.evaluate_run(self.run)["victim_service_loss"])

    def test_target_role_with_new_context_ids_is_not_an_existing_state_effect(self):
        self.write_jsonl("ground_truth.jsonl", [
            self.identity_reached(), self.network(ran=99, amf=101)
        ])
        verdict = export_labels.evaluate_run(self.run)
        self.assertFalse(verdict["target_owner_state_effect"])

    def test_target_effect_without_identity_reach_is_not_an_exact_join(self):
        self.write_jsonl("ground_truth.jsonl", [self.network()])
        verdict = export_labels.evaluate_run(self.run)
        self.assertFalse(verdict["target_owner_state_effect"])
        self.assertFalse(verdict["exact_join"])

    def test_infrastructure_events_are_counted_and_invalidate_the_verdict(self):
        rows = [self.identity_reached(), self.network()]
        for event, when in (("process_crash", 500), ("forced_kill", 501)):
            rows.append({
                "schema": "blind.network-event.v1",
                "run_id": RUN_ID,
                "role": "infrastructure",
                "event": event,
                "exact_join": False,
                "realtime_ns": when,
            })
        self.write_jsonl("ground_truth.jsonl", rows)
        verdict = export_labels.evaluate_run(self.run)
        self.assertEqual(verdict["crash_count"], 1)
        self.assertEqual(verdict["forced_kill_count"], 1)
        self.assertFalse(verdict["infrastructure_valid"])
        self.assertFalse(export_labels._phase_passed(verdict))

    def test_cross_file_run_id_mismatch_is_rejected(self):
        rows = [self.service("before", 150, True)]
        rows[0]["run_id"] = "other-run"
        rows.extend((self.service("during", 400, False),
                     self.service("recovery", 500, False),
                     self.service("after", 550, True)))
        self.write_jsonl("victim_service.jsonl", rows)
        with self.assertRaisesRegex(ValueError, "wrong run_id"):
            export_labels.evaluate_run(self.run)

    def test_control_requires_healthy_service_and_no_attack_events(self):
        run = json.loads((self.run / "run.json").read_text())
        run.update(mode="control", attack_enabled=False)
        self.write_json("run.json", run)
        (self.run / "attacker_events.jsonl").write_text("")
        self.write_jsonl("victim_service.jsonl", [
            self.service("before", 150, True),
            self.service("during", 400, True),
            self.service("recovery", 500, True),
            self.service("after", 550, True),
        ])
        neutral = self.network(event="observation")
        neutral["exact_join"] = False
        self.write_jsonl("ground_truth.jsonl", [neutral])
        verdict = export_labels.evaluate_run(self.run)
        self.assertFalse(verdict["victim_service_loss"])
        self.assertFalse(verdict["target_owner_state_effect"])
        self.assertTrue(export_labels._phase_passed(verdict))

    def test_manifest_detects_tamper_missing_and_unsealed_addition(self):
        self.finish()
        run_id, count = evidence_manifest.seal(self.run)
        self.assertEqual(run_id, RUN_ID)
        self.assertGreaterEqual(count, len(evidence_manifest.REQUIRED))
        self.assertEqual(evidence_manifest.verify(self.run), (RUN_ID, count))

        with self.subTest("tamper"):
            with (self.run / "amf.log").open("a") as handle:
                handle.write("tampered\n")
            with self.assertRaisesRegex(ValueError, "hash or size mismatch"):
                evidence_manifest.verify(self.run)

    def test_manifest_detects_missing_artifact(self):
        self.finish()
        evidence_manifest.seal(self.run)
        (self.run / "du.log").unlink()
        with self.assertRaisesRegex(ValueError, "missing or not a regular file"):
            evidence_manifest.verify(self.run)

    def test_manifest_rejects_symlink_artifact(self):
        self.finish()
        outside = Path(self.tmp.name) / "outside.log"
        outside.write_text("outside\n")
        (self.run / "amf.log").unlink()
        (self.run / "amf.log").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "contains a symlink"):
            evidence_manifest.seal(self.run)

    def test_manifest_detects_file_added_after_seal(self):
        self.finish()
        evidence_manifest.seal(self.run)
        (self.run / "late.log").write_text("late\n")
        with self.assertRaisesRegex(ValueError, "contents changed after seal"):
            evidence_manifest.verify(self.run)

    def test_changed_target_cannot_be_sealed_as_a_valid_failure(self):
        after = self.snapshot(600)
        after["owner_id"] = "victim-other"
        self.write_json("target_snapshot_after.json", after)
        self.finish(classification="valid-failure")
        with self.assertRaisesRegex(ValueError, "infrastructure-invalid verdict"):
            evidence_manifest.seal(self.run)

    def test_verdict_and_run_stop_run_id_are_checked_before_seal(self):
        self.finish()
        stopped = json.loads((self.run / "run_stop.json").read_text())
        stopped["run_id"] = "other-run"
        self.write_json("run_stop.json", stopped)
        with self.assertRaisesRegex(ValueError, "inconsistent schema, run_id, or mode"):
            evidence_manifest.seal(self.run)


if __name__ == "__main__":
    unittest.main()
