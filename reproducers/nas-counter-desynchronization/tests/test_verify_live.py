import importlib.util
import unittest
from pathlib import Path


MODULE = Path(__file__).parents[1] / "analysis" / "verify_live.py"
SPEC = importlib.util.spec_from_file_location("verify_live", MODULE)
verify_live = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(verify_live)


class UnsolicitedRejectTest(unittest.TestCase):
    def test_live_result_uses_selected_profile_and_reseals_public_output(self):
        source = MODULE.read_text()
        runner = (MODULE.parents[1] / "bin" / "nas-counter-desync-run").read_text()
        self.assertIn('os.environ.get("RAN_REPRO_PROFILE_ID", "p5")', source)
        self.assertNotIn('"profile": "p5"', source)
        self.assertIn('tools/reproctl.py" seal "$FINAL" "$RUN_ID"', runner)
        self.assertNotIn('report.md evidence_manifest.json', runner)

    def test_reject_without_prior_command_is_counted(self):
        events = [
            {"t_ms": 10, "cell_id": 1, "du_ue_id": 2, "cu_ue_id": 3, "crnti": 4,
             "msg": "AuthenticationRequest"},
            {"t_ms": 20, "cell_id": 1, "du_ue_id": 2, "cu_ue_id": 3, "crnti": 4,
             "msg": "SecurityModeReject"},
        ]
        self.assertEqual(verify_live.unsolicited_rejects(events), [events[1]])

    def test_reject_after_command_is_not_counted(self):
        events = [
            {"t_ms": 10, "cell_id": 1, "du_ue_id": 2, "cu_ue_id": 3, "crnti": 4,
             "msg": "SecurityModeCommand"},
            {"t_ms": 20, "cell_id": 1, "du_ue_id": 2, "cu_ue_id": 3, "crnti": 4,
             "msg": "SecurityModeReject"},
        ]
        self.assertEqual(verify_live.unsolicited_rejects(events), [])


if __name__ == "__main__":
    unittest.main()
