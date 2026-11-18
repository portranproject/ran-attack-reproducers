import hashlib
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from tools.verify_live_e2e import DETECTOR_COMMIT, verify


class LiveE2ETest(unittest.TestCase):
    def test_live_wrapper_waits_for_normal_baseline_before_observation(self):
        wrapper = (Path(__file__).resolve().parents[1] / "tools" / "p5-live-e2e").read_text()
        self.assertLess(wrapper.index("start_live\n"),
                        wrapper.index('until [[ -f $LIVE_E2E_BASELINE_READY_FILE'))
        self.assertLess(wrapper.index('until [[ -f $LIVE_E2E_BASELINE_READY_FILE'),
                        wrapper.index("reset_detector_after_baseline\n"))
        self.assertLess(wrapper.index("reset_detector_after_baseline\n"),
                        wrapper.index('date +%s%N >"$LIVE_E2E_OBSERVATION_READY_FILE"'))

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
            (live / "detector-input.jsonl.20261117-010300").write_text(json.dumps(rows[0]) + "\n")
            (live / "detector-input.jsonl").write_text(json.dumps(rows[1]) + "\n")
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
            with mock.patch.dict("os.environ", {"RAN_REPRO_PROFILE_ID": "p1"}):
                verdict = verify(root, "ue-capability-hijacking", "emulation", "cap-e2e-1", child,
                                 require_same_cell=True)
            self.assertTrue(verdict["passed"])
            self.assertEqual(verdict["observed_alerts"], 1)
            with (live / "detector.stdout").open("a") as output:
                output.write("ALERT RAISE rule=L3-14 cell=0 t=200 branch=1\n")
            with mock.patch.dict("os.environ", {"RAN_REPRO_PROFILE_ID": "p1"}):
                repeated = verify(root, "ue-capability-hijacking", "emulation", "cap-e2e-1", child,
                                  require_same_cell=True)
            self.assertTrue(repeated["passed"])
            self.assertEqual(repeated["observed_alerts"], 2)
            self.assertEqual(json.loads((root / "run.json").read_text())["profile"], "p1")
            self.assertEqual(json.loads((root / "oracle.jsonl").read_text())["checks"]["same_cell"]["normal_after"], 5)
            self.assertEqual(hashlib.sha256((root / "mechanism.json").read_bytes()).hexdigest(),
                             json.loads((root / "run.json").read_text())["source"]["mechanism_sha256"])
            wrapper = json.loads((root / "same-cell-run.json").read_text())
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
