import json
import tempfile
import unittest
from pathlib import Path

from analysis.export_labels import verify as verify_run, write_manifest
from analysis.verify_campaign import verify
from test_export_labels import make_run


class CampaignTest(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        for index in range(1, 4):
            for mode in ("control", "attack"):
                run_id = f"c1-{mode}-{index}"
                child = root / run_id
                child.mkdir()
                make_run(child, mode, run_id)
                (child / "verdict.json").write_text(json.dumps(verify_run(child)))
                write_manifest(child)
        return temporary, root

    def test_three_matched_sets_pass(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        result = verify(root, "c1")
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["children"]), 6)

    def test_parameter_mismatch_fails(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        path = root / "c1-attack-2" / "run.json"
        value = json.loads(path.read_text())
        value["start_interval_ms"] = 101
        path.write_text(json.dumps(value))
        # The seal catches the mutation before matched-pair comparison.
        with self.assertRaises(ValueError):
            verify(root, "c1")

    def test_attack_limit_must_come_from_control(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        child = root / "c1-control-2"
        service = child / "service.jsonl"
        rows = [json.loads(line) for line in service.read_text().splitlines()]
        rows[0]["elapsed_ms"] = 4_000
        service.write_text("".join(json.dumps(row) + "\n" for row in rows))
        verdict_path = child / "verdict.json"
        verdict_path.write_text(json.dumps(verify_run(child)))
        evidence = child / "evidence_manifest.json"
        evidence.unlink()
        write_manifest(child)
        with self.assertRaisesRegex(ValueError, "사전 고정"):
            verify(root, "c1")

    def test_phase_input_mismatch_fails(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        child = root / "c1-attack-1"
        value = json.loads((child / "phase_inputs.json").read_text())
        value["files"]["ue_endpoints"] = "8" * 64
        (child / "phase_inputs.json").write_text(json.dumps(value))
        (child / "evidence_manifest.json").unlink()
        write_manifest(child)
        with self.assertRaisesRegex(ValueError, "phase input"):
            verify(root, "c1")


if __name__ == "__main__":
    unittest.main()
