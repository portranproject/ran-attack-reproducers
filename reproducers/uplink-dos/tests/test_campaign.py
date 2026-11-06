import json
import tempfile
import unittest
from pathlib import Path

from analysis.verify_campaign import verify


class CampaignTest(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        campaign = "c1"
        for index in range(1, 4):
            for mode in ("control", "emulation"):
                run_id = f"{campaign}-{mode}-{index}"
                run = root / run_id
                run.mkdir()
                (run / "run.json").write_text(json.dumps({
                    "schema": "uplink-dos.run.v1", "run_id": run_id,
                    "mode": mode, "victim_pid": index,
                }))
                emulation = mode == "emulation"
                (run / "verdict.json").write_text(json.dumps({
                    "schema": "uplink-dos.verdict.v1", "run_id": run_id,
                    "mode": mode, "passed": True,
                    "rf_overshadowing_observed": False,
                    "same_victim_recovered": True,
                    "protocol_impact_reproduced": emulation,
                    "network_effect_observed": emulation,
                    "victim_service_loss_observed": emulation,
                    "checks": {"service_request_substitution_count": int(emulation)},
                }))
        return temporary, root, campaign

    def test_three_matched_sets_pass(self):
        temporary, root, campaign = self.fixture()
        self.addCleanup(temporary.cleanup)
        result = verify(root, campaign)
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["children"]), 6)
        self.assertFalse(result["rf_overshadowing_observed"])

    def test_failed_child_is_rejected(self):
        temporary, root, campaign = self.fixture()
        self.addCleanup(temporary.cleanup)
        path = root / "c1-emulation-2" / "verdict.json"
        value = json.loads(path.read_text())
        value["passed"] = False
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            verify(root, campaign)

    def test_unknown_child_schema_is_rejected(self):
        temporary, root, campaign = self.fixture()
        self.addCleanup(temporary.cleanup)
        path = root / "c1-emulation-2" / "verdict.json"
        value = json.loads(path.read_text())
        value["schema"] = "other"
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            verify(root, campaign)


if __name__ == "__main__":
    unittest.main()
