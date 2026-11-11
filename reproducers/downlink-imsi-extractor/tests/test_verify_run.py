import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from analysis.verify_run import verify, write_manifest


HASH = "a" * 64


def make_run(root: Path, mode: str, run_id: str = "r1", scheme: int = 0) -> None:
    enabled = mode == "emulation"
    pcap = b"pcap" * 10
    (root / "ngap.pcap").write_bytes(pcap)
    common = {
        "schema": "downlink-imsi.run.v1", "run_id": run_id, "mode": mode,
        "identity_response_substitution_emulated": enabled, "dl_overshadowing_observed": False,
        "ngap_pcap_sha256": hashlib.sha256(pcap).hexdigest(),
        "source_commit": "1" * 40, "ue_patch_sha256": "2" * 64, "ue_binary_sha256": "3" * 64,
        "gnb_config_sha256": "4" * 64, "core_config_sha256": "5" * 64, "ue_config_sha256": "6" * 64,
    }
    (root / "run.json").write_text(json.dumps(common))
    (root / "process.json").write_text(json.dumps({"schema": "downlink-imsi.process.v1", "crash_count": 0, "forced_kill_count": 0}))
    service_ok = not enabled
    (root / "service.json").write_text(json.dumps({"schema": "downlink-imsi.service.v1", "registration_ok": service_ok, "pdu_session_ok": service_ok, "ping_ok": service_ok}))
    (root / "oracle.json").write_text(json.dumps({"schema": "downlink-imsi.oracle.v1", "protection_scheme": scheme, "expected_subscriber_fingerprint": HASH, "observed_subscriber_fingerprint": HASH if scheme == 0 else None}))
    messages = [
        ("uplink", "RegistrationRequest"),
        ("downlink", "AuthenticationRequest"),
        ("uplink", "IdentityResponse" if enabled else "AuthenticationResponse"),
    ]
    rows = []
    for order, (direction, message) in enumerate(messages):
        rows.append({"schema": "downlink-imsi.observation.v1", "order": order, "source": "ngap", "direction": direction, "message": message, "ran_ue_ngap_id": 7, "amf_ue_ngap_id": 9, "realtime_ns": 100 + order, "nas_security": "plain"})
    (root / "observations.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    marker = "DOWNLINK_IMSI_EXTRACTOR event=identity_response_substituted identity_response_submitted=true\n" if enabled else "DOWNLINK_IMSI_EXTRACTOR event=authentication_response_submitted response_submitted=true\n"
    (root / "ue.log").write_text(marker)
    (root / "cu.log").write_text("current run CU slice\n")
    (root / "amf.log").write_text("current run AMF slice\n")


class VerifyRunTest(unittest.TestCase):
    def fixture(self, mode="emulation", scheme=0):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        make_run(root, mode, scheme=scheme)
        return temporary, root

    def test_null_scheme_emulation_passes(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        result = verify(root)
        self.assertTrue(result["passed"])
        self.assertTrue(result["null_scheme_identity_exposure_observed"])

    def test_profile_a_passes_without_supi_exposure_claim(self):
        temporary, root = self.fixture(scheme=1)
        self.addCleanup(temporary.cleanup)
        result = verify(root)
        self.assertTrue(result["passed"])
        self.assertFalse(result["null_scheme_identity_exposure_observed"])

    def test_control_passes(self):
        temporary, root = self.fixture("control")
        self.addCleanup(temporary.cleanup)
        result = verify(root)
        self.assertTrue(result["passed"])
        self.assertTrue(result["control_healthy"])

    def test_identity_request_makes_emulation_fail(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        rows = [json.loads(line) for line in (root / "observations.jsonl").read_text().splitlines()]
        rows.insert(2, {**rows[1], "order": 2, "message": "IdentityRequest"})
        rows[3]["order"] = 3
        (root / "observations.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.assertFalse(verify(root)["passed"])

    def test_second_identity_response_fails(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        rows = [json.loads(line) for line in (root / "observations.jsonl").read_text().splitlines()]
        rows.append({**rows[-1], "order": 3, "realtime_ns": 103})
        (root / "observations.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.assertFalse(verify(root)["passed"])

    def test_subscriber_data_in_detector_input_fails_closed(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        with (root / "observations.jsonl").open("a") as output:
            output.write("suci-0-001-01-0-0-0-123\n")
        with self.assertRaisesRegex(ValueError, "가입자"):
            verify(root)

    def test_manifest_detects_mutation(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        (root / "verdict.json").write_text(json.dumps(verify(root)))
        write_manifest(root)
        manifest = json.loads((root / "evidence_manifest.json").read_text())
        self.assertEqual(manifest["schema"], "downlink-imsi.evidence.v1")


if __name__ == "__main__":
    unittest.main()
