import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from analysis.export_labels import verify, write_manifest
from analysis.verify_evidence import verify as verify_evidence


def jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def make_run(root: Path, mode: str = "attack", run_id: str = "r1") -> None:
    attackers = ["a" * 64, "b" * 64]
    witness = "c" * 64
    profiles = {
        "schema": "auth-timeout.profiles.v1",
        "attacker_count": 2,
        "profiles": [
            {"role": "attacker", "subscriber_fingerprint": attackers[0], "config_sha256": "1" * 64},
            {"role": "attacker", "subscriber_fingerprint": attackers[1], "config_sha256": "2" * 64},
            {"role": "witness", "subscriber_fingerprint": witness, "config_sha256": "3" * 64},
        ],
    }
    profile_text = json.dumps(profiles, sort_keys=True, separators=(",", ":")) + "\n"
    (root / "profiles.manifest.json").write_text(profile_text)
    (root / "phase_inputs.json").write_text(json.dumps({
        "schema": "auth-timeout.phase-inputs.v1",
        "files": {name: character * 64 for name, character in (
            ("uecap", "4"), ("ue_endpoints", "5"), ("p5_hook", "6"), ("service_probe", "7")
        )},
    }, sort_keys=True, separators=(",", ":")) + "\n")
    attacker_logs = {"attacker-1.log": b"attacker one\n", "attacker-2.log": b"attacker two\n"}
    for name, data in attacker_logs.items():
        (root / name).write_bytes(data)
    (root / "attacker_map.json").write_text(json.dumps({
        "schema": "auth-timeout.attacker-map.v1",
        "attackers": [
            {"subscriber_fingerprint": attackers[0], "log_file": "attacker-1.log", "log_sha256": hashlib.sha256(attacker_logs["attacker-1.log"]).hexdigest()},
            {"subscriber_fingerprint": attackers[1], "log_file": "attacker-2.log", "log_sha256": hashlib.sha256(attacker_logs["attacker-2.log"]).hexdigest()},
        ],
    }))
    (root / "run.json").write_text(json.dumps({
        "schema": "auth-timeout.run.v1", "run_id": run_id, "mode": mode,
        "withholding_enabled": mode == "attack", "attacker_count": 2,
        "start_interval_ms": 100, "registration_limit_ms": 10_000,
        "profile_manifest_sha256": hashlib.sha256(profile_text.encode()).hexdigest(),
        "gnb_config_sha256": "d" * 64, "core_config_sha256": "e" * 64,
        "phase_driver_sha256": "f" * 64, "ue_patch_sha256": "0" * 64,
        "ru_sharing_patch_sha256": "4" * 64,
        "ue_binary_sha256": "1" * 64, "zmq_library_sha256": "3" * 64,
        "runtime_config_sha256": "2" * 64,
    }))
    attack = mode == "attack"
    jsonl(root / "attacker_truth.jsonl", [{
        "schema": "auth-timeout.truth.v1", "subscriber_fingerprint": fingerprint,
        "withheld_request_count": 2 if attack else 0,
        "submitted_response_count": 0 if attack else 1,
        "response_submitted": not attack,
    } for fingerprint in attackers])
    jsonl(root / "contexts.jsonl", [{
        "schema": "auth-timeout.context.v1", "subscriber_fingerprint": fingerprint,
        "ran_ue_ngap_id": index, "amf_ue_ngap_id": index + 10,
        "rrc_setup_complete": True, "initial_ue_message": True, "authentication_request": True,
        "authentication_response_count": 0 if attack else 1, "authentication_failure_count": 0,
        "created_realtime_ns": 100 + index, "released_realtime_ns": 1_000 + index,
    } for index, fingerprint in enumerate(attackers, 1)])
    service = [{
        "schema": "auth-timeout.service.v1", "phase": "baseline", "attempt": 1,
        "witness_fingerprint": witness, "registration_ok": True, "pdu_session_ok": True,
        "ping_ok": True, "elapsed_ms": 100, "realtime_ns": 50,
    }]
    for phase in ("impact", "recovery"):
        for attempt in range(1, 6):
            failed = attack and phase == "impact"
            service.append({
                "schema": "auth-timeout.service.v1", "phase": phase, "attempt": attempt,
                "witness_fingerprint": witness, "registration_ok": not failed,
                "pdu_session_ok": not failed, "ping_ok": not failed,
                "elapsed_ms": 10_000 if failed else 100,
                "realtime_ns": 200 + attempt,
            })
    jsonl(root / "service.jsonl", service)
    (root / "process.json").write_text(json.dumps({
        "schema": "auth-timeout.process.v1", "crash_count": 0, "forced_kill_count": 0,
    }))
    for name in ("ue.log", "cu.log", "amf.log"):
        (root / name).write_text(f"fixture {name}\n")


class ExportLabelsTest(unittest.TestCase):
    def fixture(self, mode="attack"):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        make_run(root, mode)
        return temporary, root

    def test_attack_requires_mechanism_accumulation_denial_and_recovery(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        verdict = verify(root)
        self.assertTrue(verdict["passed"])
        self.assertEqual(verdict["checks"]["peak_concurrent_pre_auth_contexts"], 2)

    def test_control_passes_without_withholding_or_denial(self):
        temporary, root = self.fixture("control")
        self.addCleanup(temporary.cleanup)
        verdict = verify(root)
        self.assertTrue(verdict["passed"])
        self.assertFalse(verdict["mechanism_reproduced"])

    def test_authentication_response_in_attack_fails(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        rows = [json.loads(line) for line in (root / "attacker_truth.jsonl").read_text().splitlines()]
        rows[0]["submitted_response_count"] = 1
        rows[0]["response_submitted"] = True
        jsonl(root / "attacker_truth.jsonl", rows)
        self.assertFalse(verify(root)["passed"])

    def test_non_overlapping_contexts_fail_accumulation(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        rows = [json.loads(line) for line in (root / "contexts.jsonl").read_text().splitlines()]
        rows[0]["released_realtime_ns"] = 150
        rows[1]["created_realtime_ns"] = 151
        jsonl(root / "contexts.jsonl", rows)
        verdict = verify(root)
        self.assertFalse(verdict["passed"])
        self.assertEqual(verdict["checks"]["peak_concurrent_pre_auth_contexts"], 1)

    def test_one_successful_impact_registration_fails(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        rows = [json.loads(line) for line in (root / "service.jsonl").read_text().splitlines()]
        impact = next(row for row in rows if row["phase"] == "impact")
        impact.update(registration_ok=True, pdu_session_ok=True, ping_ok=True, elapsed_ms=100)
        jsonl(root / "service.jsonl", rows)
        self.assertFalse(verify(root)["passed"])

    def test_impact_outside_full_accumulation_window_fails(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        rows = [json.loads(line) for line in (root / "service.jsonl").read_text().splitlines()]
        next(row for row in rows if row["phase"] == "impact")["realtime_ns"] = 1_002
        jsonl(root / "service.jsonl", rows)
        self.assertFalse(verify(root)["passed"])

    def test_reconnected_attack_contexts_can_sustain_accumulation(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        contexts = [json.loads(line) for line in (root / "contexts.jsonl").read_text().splitlines()]
        extra = []
        for index, row in enumerate(contexts, 1):
            copy = dict(row)
            copy.update(ran_ue_ngap_id=100 + index, amf_ue_ngap_id=200 + index,
                        created_realtime_ns=900, released_realtime_ns=2_000)
            extra.append(copy)
        jsonl(root / "contexts.jsonl", contexts + extra)
        truth = [json.loads(line) for line in (root / "attacker_truth.jsonl").read_text().splitlines()]
        for row in truth:
            row["withheld_request_count"] = 4
        jsonl(root / "attacker_truth.jsonl", truth)
        service = [json.loads(line) for line in (root / "service.jsonl").read_text().splitlines()]
        for row in service:
            if row["phase"] == "impact":
                row["realtime_ns"] = 1_200
        jsonl(root / "service.jsonl", service)
        self.assertTrue(verify(root)["passed"])

    def test_manifest_detects_modified_raw_file(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        (root / "verdict.json").write_text(json.dumps(verify(root)))
        write_manifest(root)
        self.assertGreater(verify_evidence(root), 0)
        (root / "ue.log").write_text("changed\n")
        with self.assertRaises(ValueError):
            verify_evidence(root)


if __name__ == "__main__":
    unittest.main()
