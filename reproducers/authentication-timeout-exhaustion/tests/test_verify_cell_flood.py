import json
import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).parents[1] / "analysis/verify_cell_flood.py"
SPEC = importlib.util.spec_from_file_location("verify_cell_flood", MODULE)
verify_cell_flood = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(verify_cell_flood)
verify = verify_cell_flood.verify


class CellFloodVerifierTest(unittest.TestCase):
    def test_ten_attack_ues_pass_without_service_denial_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "run.json").write_text(json.dumps({
                "schema": "auth-timeout.cell-flood-run.v1", "run_id": "attack-1", "mode": "attack",
                "process_count": 2, "ues_per_process": 5}))
            (root / "process.json").write_text(json.dumps({
                "schema": "auth-timeout.cell-flood-process.v1", "early_exit_count": 0, "forced_kill_count": 0}))
            marker = "AUTH_TIMEOUT_EXHAUSTION event=authentication_request_withheld"
            for process in range(1, 3):
                (root / f"ue-{process}.log").write_text("".join(
                    marker + f" ue={ue} response_submitted=false\n" for ue in range(5)))
            verdict = verify(root, "attack", "attack-1", 10)
            self.assertTrue(verdict["passed"])
            self.assertTrue(verdict["mechanism_reproduced"])
            self.assertEqual(verdict["checks"]["marker_count"], 10)
            self.assertEqual(verdict["checks"]["recovery_signal_count"], 0)

    def test_one_process_ten_ues_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "run.json").write_text(json.dumps({
                "schema": "auth-timeout.cell-flood-run.v1", "run_id": "control-1", "mode": "control",
                "process_count": 1, "ues_per_process": 10}))
            (root / "process.json").write_text(json.dumps({
                "schema": "auth-timeout.cell-flood-process.v1", "early_exit_count": 0, "forced_kill_count": 0}))
            marker = "AUTH_TIMEOUT_EXHAUSTION event=authentication_response_submitted"
            (root / "ue-1.log").write_text("".join(marker + f" ue={ue}\n" for ue in range(10)))
            self.assertTrue(verify(root, "control", "control-1", 10)["passed"])


if __name__ == "__main__":
    unittest.main()
