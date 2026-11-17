import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_live_e2e import DETECTOR_COMMIT, verify


class LiveE2ETest(unittest.TestCase):
    def test_active_run_requires_mechanism_live_input_alert_and_dashboard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            live = root / "live"
            child = Path(directory) / "child"
            live.mkdir(parents=True)
            child.mkdir()
            (child / "verdict.json").write_text(json.dumps({"schema": "ue-capability.verdict.v1", "passed": True}))
            rows = [
                {"type": "hello", "seq": 1, "session": "20261117T010203Z", "period_ms": 100, "ue_evt": True},
                {"type": "kpm2", "seq": 2, "t_start_ms": 0, "t_end_ms": 100},
            ]
            (live / "telemetry.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            digest = "a" * 64
            (live / "components.json").write_text(json.dumps({
                "detector": {"commit": DETECTOR_COMMIT, "binary_sha256": digest},
                "telemetry": {"commit": "b" * 40, "binary_sha256": digest},
                "dashboard": {"sender_sha256": digest},
            }))
            (live / "detector.stdout").write_text("ALERT RAISE rule=L3-14 cell=0 t=100 branch=1\n")
            (live / "sender.exit").write_text("0\n")
            (live / "sender.log").write_text(
                "send file=/tmp/evidence.jsonl status=200 accepted=1 rejected=0\n"
                "send file=/tmp/detector-input.jsonl status=200 accepted=2 rejected=0\n")
            verdict = verify(root, "ue-capability-hijacking", "emulation", "cap-e2e-1", child)
            self.assertTrue(verdict["passed"])
            self.assertEqual(verdict["observed_alerts"], 1)
            self.assertEqual(hashlib.sha256((root / "mechanism.json").read_bytes()).hexdigest(),
                             json.loads((root / "run.json").read_text())["source"]["mechanism_sha256"])


if __name__ == "__main__":
    unittest.main()
