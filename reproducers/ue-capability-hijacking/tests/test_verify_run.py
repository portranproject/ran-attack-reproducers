import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from analysis.verify_run import verify, write_manifest


def make_run(root: Path, mode: str, enquiry_before: bool = False) -> None:
    enabled = mode == "emulation"
    pcap = b"pcap" * 10
    (root / "f1.pcap").write_bytes(pcap)
    run = {
        "schema": "ue-capability.run.v1", "run_id": "r1", "mode": mode,
        "pre_security_information_injection_emulated": enabled,
        "mitm_relay_observed": False, "capability_content_modified": False,
        "capability_downgrade_accepted": False, "f1_pcap_sha256": hashlib.sha256(pcap).hexdigest(),
        "source_commit": "1" * 40, "ue_patch_sha256": "2" * 64, "ue_binary_sha256": "3" * 64,
        "gnb_config_sha256": "4" * 64, "core_config_sha256": "5" * 64, "ue_config_sha256": "6" * 64,
    }
    (root / "run.json").write_text(json.dumps(run))
    (root / "process.json").write_text(json.dumps({"schema": "ue-capability.process.v1", "crash_count": 0, "forced_kill_count": 0}))
    service_ok = mode == "control"
    (root / "service.json").write_text(json.dumps({"schema": "ue-capability.service.v1", "registration_ok": service_ok, "pdu_session_ok": service_ok, "ping_ok": service_ok}))
    (root / "oracle.json").write_text(json.dumps({"schema": "ue-capability.oracle.v1", "injected_marker_count": int(enabled), "normal_marker_count": 0}))
    messages = [("uplink", "RRCSetupComplete", "OFF")]
    if enabled:
        if enquiry_before:
            messages.append(("downlink", "UECapabilityEnquiry", "OFF"))
        messages.extend([("uplink", "UECapabilityInformation", "OFF"), ("downlink", "SecurityModeCommand", "OFF")])
    else:
        messages.extend([("downlink", "SecurityModeCommand", "OFF"), ("uplink", "SecurityModeComplete", "OFF")])
    rows = []
    for order, (direction, message, security) in enumerate(messages):
        rows.append({
            "schema": "ue-capability.observation.v1", "order": order, "source": "f1ap",
            "direction": direction, "message": message, "gnb_cu_ue_f1ap_id": 7,
            "gnb_du_ue_f1ap_id": 9, "realtime_ns": 100 + order, "rrc_security_before": security,
        })
    (root / "observations.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    marker = "UE_CAPABILITY_INJECTION event=pre_security_information_injected information_submitted=true\n" if enabled else "normal control\n"
    (root / "ue.log").write_text(marker)
    (root / "cu.log").write_text("current CU slice\n")


class VerifyRunTest(unittest.TestCase):
    def fixture(self, mode="emulation", enquiry_before=False):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        make_run(root, mode, enquiry_before)
        return temporary, root

    def test_pre_security_unsolicited_information_passes(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        result = verify(root)
        self.assertTrue(result["passed"])
        self.assertTrue(result["pre_security_injection_observed"])
        self.assertFalse(result["capability_downgrade_accepted"])

    def test_control_passes_without_capability_exchange(self):
        temporary, root = self.fixture("control")
        self.addCleanup(temporary.cleanup)
        result = verify(root)
        self.assertTrue(result["passed"])
        self.assertTrue(result["control_healthy"])

    def test_prior_enquiry_fails_unsolicited_condition(self):
        temporary, root = self.fixture(enquiry_before=True)
        self.addCleanup(temporary.cleanup)
        self.assertFalse(verify(root)["passed"])

    def test_claim_boundary_fails_closed(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        run = json.loads((root / "run.json").read_text())
        run["capability_content_modified"] = True
        (root / "run.json").write_text(json.dumps(run))
        with self.assertRaisesRegex(ValueError, "주장 경계"):
            verify(root)

    def test_manifest_is_created(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        (root / "verdict.json").write_text(json.dumps(verify(root)))
        write_manifest(root)
        self.assertEqual(json.loads((root / "evidence_manifest.json").read_text())["schema"], "ue-capability.evidence.v1")


if __name__ == "__main__":
    unittest.main()
