import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from analysis.generate_l3_21_replay import generate
from analysis.verify_registration_failure_run import verify


class RegistrationFailureFloodTest(unittest.TestCase):
    def make_run(self, root: Path, mode: str) -> None:
        generate(mode, f"test-{mode}", root)
        replay = root / "detector-input.jsonl"
        (root / "run.json").write_text(json.dumps({
            "schema": "uplink-dos.registration-failure-emulation.v1", "run_id": f"test-{mode}", "mode": mode,
            "registration_failure_flood_emulated": mode == "emulation", "rf_overshadowing_observed": False,
            "live_protocol_path_observed": False, "detector_input_sha256": hashlib.sha256(replay.read_bytes()).hexdigest(),
        }))
        raises = 1 if mode == "emulation" else 0
        (root / "l3-21-verdict.json").write_text(json.dumps({
            "schema": "uplink-dos.l3-21-verdict.v1", "run_id": f"test-{mode}", "mode": mode,
            "passed": True, "l3_21_raise_count": raises, "l3_21_branch1_raise_count": raises,
            "detector_sha256": "a" * 64, "detector_config_sha256": "b" * 64,
        }))

    def test_emulation_generates_five_contexts_and_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_run(root, "emulation")
            observations = [json.loads(line) for line in (root / "observations.jsonl").read_text().splitlines()]
            replay = [json.loads(line) for line in (root / "detector-input.jsonl").read_text().splitlines()]
            verdict = verify(root)
        self.assertEqual(sum(row["message"] == "RegistrationReject" for row in observations), 5)
        self.assertEqual([row["seq"] for row in replay], list(range(1, len(replay) + 1)))
        self.assertTrue(verdict["passed"])
        self.assertTrue(verdict["l3_21_signal_emulated"])

    def test_control_generates_one_failure_without_alert(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_run(root, "control")
            verdict = verify(root)
        self.assertTrue(verdict["passed"])
        self.assertFalse(verdict["l3_21_signal_emulated"])
        self.assertEqual(verdict["checks"]["l3_21_raise_count"], 0)


if __name__ == "__main__":
    unittest.main()
