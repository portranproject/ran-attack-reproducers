import json
import tempfile
import unittest
from pathlib import Path

from analysis.export_labels import verify


class ExportLabelsTest(unittest.TestCase):
    def fixture(self, mode="emulation"):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        enabled = mode == "emulation"
        (root / "run.json").write_text(json.dumps({
            "schema": "uplink-dos.run.v1", "run_id": "r1", "mode": mode,
            "emulation_enabled": enabled, "victim_pid": 42,
        }))
        rows = []
        for phase, ok in (("baseline", True), ("impact", not enabled), ("recovery", True)):
            rows.extend({"schema": "uplink-dos.service.v1", "phase": phase, "ping_ok": ok, "victim_pid": 42} for _ in range(5))
        (root / "service.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (root / "process.json").write_text(json.dumps({
            "schema": "uplink-dos.process.v1", "victim_pid": 42,
            "crash_count": 0, "forced_kill_count": 0,
        }))
        marker = "UPLINK_DOS_EMULATION event=service_request_mac_corrupted\nReceived NAS Service Reject message\n" if enabled else ""
        (root / "ue.log").write_text(marker)
        (root / "cu.log").write_text("Tx PDU: InitialUEMessage\nTx PDU: InitialUEMessage\n")
        (root / "amf.log").write_text("Service request\nNAS MAC verification failed\n")
        return temporary, root

    def test_emulation_passes_with_independent_evidence(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        verdict = verify(root)
        self.assertTrue(verdict["passed"])
        self.assertFalse(verdict["rf_overshadowing_observed"])

    def test_control_passes_without_substitution_or_loss(self):
        temporary, root = self.fixture("control")
        self.addCleanup(temporary.cleanup)
        self.assertTrue(verify(root)["passed"])

    def test_control_allows_only_one_paging_loss(self):
        temporary, root = self.fixture("control")
        self.addCleanup(temporary.cleanup)
        rows = [json.loads(line) for line in (root / "service.jsonl").read_text().splitlines()]
        next(row for row in rows if row["phase"] == "impact")["ping_ok"] = False
        (root / "service.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.assertTrue(verify(root)["passed"])

    def test_control_allows_two_paging_losses_but_not_three(self):
        temporary, root = self.fixture("control")
        self.addCleanup(temporary.cleanup)
        rows = [json.loads(line) for line in (root / "service.jsonl").read_text().splitlines()]
        impact = [row for row in rows if row["phase"] == "impact"]
        impact[0]["ping_ok"] = impact[1]["ping_ok"] = False
        (root / "service.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.assertTrue(verify(root)["passed"])
        impact[2]["ping_ok"] = False
        (root / "service.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.assertFalse(verify(root)["passed"])

    def test_missing_core_effect_fails_closed(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        (root / "amf.log").write_text("Service request accepted\n")
        self.assertFalse(verify(root)["passed"])

    def test_missing_service_reject_fails_closed(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        (root / "ue.log").write_text("UPLINK_DOS_EMULATION event=service_request_mac_corrupted\n")
        self.assertFalse(verify(root)["passed"])

    def test_second_substitution_fails(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        with (root / "ue.log").open("a") as output:
            output.write("UPLINK_DOS_EMULATION event=service_request_mac_corrupted\n")
        self.assertFalse(verify(root)["passed"])

    def test_recovery_allows_one_paging_loss_then_five_successes(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        rows = [json.loads(line) for line in (root / "service.jsonl").read_text().splitlines()]
        recovery = [row for row in rows if row["phase"] == "recovery"]
        recovery[0]["ping_ok"] = False
        recovery.append({"schema": "uplink-dos.service.v1", "phase": "recovery", "ping_ok": True, "victim_pid": 42})
        (root / "service.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows if row["phase"] != "recovery") + "".join(json.dumps(row) + "\n" for row in recovery))
        self.assertTrue(verify(root)["passed"])


if __name__ == "__main__":
    unittest.main()
