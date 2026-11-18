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
            (root / "same-cell-session.json").write_text(json.dumps({
                "schema": "same-cell.session.v2", "run_id": "cap-e2e-1",
                "normal_ues": 5, "clocked_attack_slots": True,
            }))
            (root / "same-cell-run.json").write_text(json.dumps({
                "schema": "same-cell.run.v3", "run_id": "cap-e2e-1",
                "direct_detector_input": False, "ue_to_ran_path_required": True,
                "normal_healthy_before_attack_teardown": True, "attack_exit_status": 0,
            }))
            health = [
                {"schema": "same-cell.normal-health.v1", "run_id": "cap-e2e-1",
                 "phase": phase, "ue": ue, "tun_ok": True, "ping_ok": True}
                for phase in ("before", "after") for ue in range(1, 6)
            ]
            (root / "same-cell-normal-health.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in health)
            )
            verdict = verify(root, "ue-capability-hijacking", "emulation", "cap-e2e-1", child,
                             require_same_cell=True)
            self.assertTrue(verdict["passed"])
            self.assertEqual(verdict["observed_alerts"], 1)
            self.assertEqual(json.loads((root / "oracle.jsonl").read_text())["checks"]["same_cell"]["normal_after"], 5)
            self.assertEqual(hashlib.sha256((root / "mechanism.json").read_bytes()).hexdigest(),
                             json.loads((root / "run.json").read_text())["source"]["mechanism_sha256"])
            session = json.loads((root / "same-cell-session.json").read_text())
            wrapper = json.loads((root / "same-cell-run.json").read_text())
            session["attack"] = "auth-timeout"
            wrapper["normal_healthy_before_attack_teardown"] = False
            wrapper["attack_teardown_before_recovery"] = True
            (root / "same-cell-session.json").write_text(json.dumps(session))
            (root / "same-cell-run.json").write_text(json.dumps(wrapper))
            auth_recovery = verify(root, "ue-capability-hijacking", "emulation", "cap-e2e-1", child,
                                   require_same_cell=True)
            self.assertTrue(auth_recovery["passed"])
            wrapper["attack_exit_status"] = 1
            (root / "same-cell-run.json").write_text(json.dumps(wrapper))
            failed = verify(root, "ue-capability-hijacking", "emulation", "cap-e2e-1", child,
                            require_same_cell=True)
            self.assertFalse(failed["passed"])
            (root / "same-cell-run.json").unlink()
            missing = verify(root, "ue-capability-hijacking", "emulation", "cap-e2e-1", child,
                             require_same_cell=True)
            self.assertFalse(missing["passed"])


if __name__ == "__main__":
    unittest.main()
