import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from analysis.generate_l3_21_replay import generate
from analysis.verify_registration_failure_live import failed_contexts, join_rotated_jsonl, session_started_at
from analysis.verify_registration_failure_run import verify

MODULE_ROOT = Path(__file__).resolve().parents[1]


class RegistrationFailureFloodTest(unittest.TestCase):
    def test_same_cell_ra_gate_is_built_and_passed_fail_closed(self):
        build = (MODULE_ROOT / "bin/uplink-build").read_text()
        runner = (MODULE_ROOT / "bin/uplink-credential-flood-run").read_text()

        self.assertIn("workloads/normal-ue/patch/same-cell-ra-gate-w38.patch", build)
        self.assertLess(
            build.index('git -C "$OAI" apply "$FLOOD_PATCH"'),
            build.index('git -C "$OAI" apply --check "$SAME_CELL_GATE_PATCH"'),
        )
        self.assertIn("grep -Faq 'OAI_SAME_CELL_GATE_FILE' \"$BIN\"", build)

        self.assertIn('SAME_CELL_UE_GATE_FILE=${SAME_CELL_UE_GATE_FILE:-}', runner)
        self.assertIn('[[ $SAME_CELL_UE_GATE_FILE == /* ]]', runner)
        self.assertIn('[[ -f $SAME_CELL_UE_GATE_FILE && ! -L $SAME_CELL_UE_GATE_FILE ]]', runner)
        self.assertIn("grep -Faq 'OAI_SAME_CELL_GATE_FILE' \"$OAI_BIN\"", runner)
        self.assertIn('OAI_SAME_CELL_GATE_FILE="$SAME_CELL_UE_GATE_FILE"', runner)

    def test_live_session_start_is_normalized(self):
        self.assertEqual(session_started_at("20261116T030405Z"), "2026-11-16T03:04:05Z")
        with self.assertRaises(ValueError):
            session_started_at("2026-11-16T03:04:05Z")

    def test_live_input_rotation_is_joined_in_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "detector-input.jsonl"
            (root / "detector-input.jsonl.20261118-180000").write_text('{"seq":1}\n')
            current.write_text('{"seq":2}\n')
            rows = join_rotated_jsonl(current, root / "observations.jsonl")
        self.assertEqual([row["seq"] for row in rows], [1, 2])

    def test_live_result_uses_the_selected_profile(self):
        source = (MODULE_ROOT / "analysis/verify_registration_failure_live.py").read_text()
        self.assertIn('os.environ.get("RAN_REPRO_PROFILE_ID", "p5")', source)
        self.assertNotIn('"profile": "p5"', source)

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

    def test_emulation_generates_ten_contexts_and_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_run(root, "emulation")
            observations = [json.loads(line) for line in (root / "observations.jsonl").read_text().splitlines()]
            replay = [json.loads(line) for line in (root / "detector-input.jsonl").read_text().splitlines()]
            verdict = verify(root)
        self.assertEqual(sum(row["message"] == "RegistrationReject" for row in observations), 10)
        self.assertEqual([row["seq"] for row in replay], list(range(1, len(replay) + 1)))
        self.assertTrue(verdict["passed"])
        self.assertTrue(verdict["l3_21_signal_emulated"])

    def test_control_generates_nine_failures_without_alert(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_run(root, "control")
            verdict = verify(root)
        self.assertTrue(verdict["passed"])
        self.assertFalse(verdict["l3_21_signal_emulated"])
        self.assertEqual(verdict["checks"]["registration_reject_count"], 9)
        self.assertEqual(verdict["checks"]["l3_21_raise_count"], 0)

    def test_live_verifier_ignores_normal_background_contexts(self):
        normal = [{"cell_id": 1, "du_ue_id": 1, "crnti": 10, "msg": "RegistrationRequest"},
                  {"cell_id": 1, "du_ue_id": 1, "crnti": 10, "msg": "RegistrationAccept"}]
        failed = [{"cell_id": 1, "du_ue_id": 2, "crnti": 11, "msg": "RegistrationRequest"},
                  {"cell_id": 1, "du_ue_id": 2, "crnti": 11, "msg": "RegistrationReject"}]
        self.assertEqual(failed_contexts(normal + failed), [failed])


if __name__ == "__main__":
    unittest.main()
