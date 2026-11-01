"""Conservative label-v1 export from immutable UE event logs."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


EXPORTER = Path(__file__).resolve().parents[1] / "analysis" / "export_labels.py"


def event(run_id, ue, seq, t_ns, name, **fields):
    record = {"type": "event", "run_id": run_id, "ue": ue, "seq": seq,
              "t_ns": t_ns, "event": name}
    record.update(fields)
    return record


class LabelExportTests(unittest.TestCase):
    def run_export(self, events, run_id="run-1", run_text=None, events_text=None,
                   du_text=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_path = root / "run.json"
            events_path = root / "attempts.jsonl"
            default_run = {"type": "run", "run_id": run_id, "scenario": "A"}
            if du_text is not None:
                default_run["orchestration"] = {"du_sector_id": 0}
            run_path.write_text(
                run_text if run_text is not None else json.dumps(default_run)
            )
            events_path.write_text(events_text if events_text is not None else "".join(
                json.dumps(record) + "\n" for record in events
            ))
            command = [sys.executable, str(EXPORTER), str(run_path), str(events_path)]
            if du_text is not None:
                du_path = root / "odu-run-slice.log"
                du_path.write_text(du_text)
                command.append(str(du_path))
            result = subprocess.run(
                command,
                text=True, capture_output=True, check=False,
            )
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        return result, rows

    def test_same_sequence_on_two_ues_stays_two_attempts(self):
        records = [
            event("run-1", 0, 1, 10, "attempt_start", ue_identity="0x00"),
            event("run-1", 1, 1, 11, "attempt_start", ue_identity="0x02"),
            event("run-1", 0, 1, 20, "attempt_end", actual_reach="no_msg4"),
            event("run-1", 1, 1, 21, "attempt_end", actual_reach="no_msg4"),
        ]
        result, rows = self.run_export(records)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([row["attempt_id"] for row in rows], ["run-1:0:1", "run-1:1:1"])
        self.assertTrue(all(row["actual_reach"] == "no_msg4" for row in rows))
        self.assertTrue(all(row["canonical_a"] is False for row in rows))

    def test_a_early_requires_mac_confirmed_msg3_and_no_msg4(self):
        msg3 = event(
            "run-1", 0, 1, 20, "msg3_tx", tc_rnti="0x4601",
            frame=100, slot=2, source="ue_mac",
        )
        cases = {
            "confirmed": (
                [event("run-1", 0, 1, 10, "attempt_start"), msg3],
                "msg3_sent", True, None, False,
            ),
            "payload_only": (
                [event("run-1", 0, 1, 10, "attempt_start"),
                 event("run-1", 0, 1, 30, "attempt_end", actual_reach="no_msg4")],
                "no_msg4", False, False, False,
            ),
            "reached_msg4": (
                [event("run-1", 0, 1, 10, "attempt_start"), msg3,
                 event("run-1", 0, 1, 30, "msg4_rx", msg5_action="skipped")],
                "msg4_ack_unknown", False, False, None,
            ),
        }
        run = json.dumps({"type": "run", "run_id": "run-1", "scenario": "A_early"})
        for name, (records, reach, canonical_ue, canonical, canonical_a) in cases.items():
            with self.subTest(name=name):
                result, rows = self.run_export(records, run_text=run)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(rows[0]["actual_reach"], reach)
                self.assertIs(rows[0]["canonical_msg3_ue"], canonical_ue)
                self.assertIs(rows[0]["canonical_msg3_only"], canonical)
                self.assertIs(rows[0]["canonical_a"], canonical_a)

        result, rows = self.run_export(
            [event("run-1", 0, 1, 10, "attempt_start"),
             event("run-1", 0, 1, 20, "msg3_tx", tc_rnti="bad", frame=100, slot=2)],
            run_text=run,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(rows, [])
        self.assertIn("invalid TC-RNTI", result.stderr)

    def test_exact_cu_rrc_setup_promotes_msg3_candidate(self):
        records = [
            event("run-1", 0, 1, 10, "attempt_start"),
            event("run-1", 0, 1, 20, "msg3_tx", tc_rnti="0x4601",
                  frame=100, slot=2, source="ue_mac"),
        ]
        run = json.dumps({"run_id": "run-1", "scenario": "A_early"})
        cu = (
            "2026-10-30T01:35:21.935825 [RRC] [D] ue=1 c-rnti=0x4601: "
            "Rx SRB0 CCCH UL rrcSetupRequest (6 B)\n"
        )
        result, rows = self.run_export(records, run_text=run, du_text=cu)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(rows[0]["canonical_msg3_only"], True)
        self.assertEqual(rows[0]["canonical_msg3_evidence"],
                         "ue_mac+ocudu_cu_rrc")
        evidence = rows[0]["cu_msg3_evidence"]
        self.assertEqual((evidence["line"], evidence["ue"], evidence["rnti"]),
                         (1, 1, "0x4601"))
        self.assertRegex(evidence["log_sha256"], r"^[0-9a-f]{64}$")

    def test_cu_msg3_join_requires_unique_rnti_on_both_sides(self):
        run = json.dumps({"run_id": "run-1", "scenario": "A_early"})
        one = [
            event("run-1", 0, 1, 10, "attempt_start"),
            event("run-1", 0, 1, 20, "msg3_tx", tc_rnti="0x4601",
                  frame=100, slot=2),
        ]
        line = ("ue=1 c-rnti=0x4601: Rx SRB0 CCCH UL "
                "rrcSetupRequest (6 B)\n")
        cases = {
            "no match": (one, line.replace("0x4601", "0x4602")),
            "duplicate CU": (one, line + line),
            "duplicate UE": (
                one + [
                    event("run-1", 0, 2, 30, "attempt_start"),
                    event("run-1", 0, 2, 40, "msg3_tx", tc_rnti="0x4601",
                          frame=101, slot=2),
                ],
                line,
            ),
        }
        for name, (records, cu) in cases.items():
            with self.subTest(name=name):
                result, rows = self.run_export(records, run_text=run, du_text=cu)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(all(row["canonical_msg3_only"] is None for row in rows))
                self.assertTrue(all(row["cu_msg3_evidence"] is None for row in rows))

    def test_malformed_cu_rrc_candidate_fails_without_output(self):
        records = [event("run-1", 0, 1, 10, "attempt_start")]
        malformed = "ue=bad c-rnti=0xzz: Rx SRB0 CCCH UL rrcSetupRequest (6 B)\n"
        result, rows = self.run_export(records, du_text=malformed)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(rows, [])
        self.assertIn("malformed RRC Setup evidence", result.stderr)

    def test_withheld_ack_overrides_legacy_msg5_skip(self):
        records = [
            event("run-1", 0, 1, 10, "attempt_start", ue_identity="0xaa"),
            event("run-1", 0, 1, 20, "msg4_rx", actual_reach="msg5_skip",
                  intended_reach="msg5_skip", tc_rnti="0x4601"),
            event("run-1", 0, 1, 21, "msg4_ack_withheld"),
        ]
        result, rows = self.run_export(records)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rows[0]["actual_reach"], "msg4_no_ack")
        self.assertIs(rows[0]["canonical_a_ue"], False)
        self.assertIs(rows[0]["canonical_a"], False)
        self.assertEqual(rows[0]["msg4_ack_state"], "withheld")
        self.assertEqual(rows[0]["du_ack_state"], "unknown")

    def test_legacy_msg4_without_ack_event_is_inconclusive(self):
        records = [
            event("run-1", 0, 1, 10, "attempt_start"),
            event("run-1", 0, 1, 20, "msg4_rx", actual_reach="msg5_skip"),
        ]
        result, rows = self.run_export(records)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rows[0]["actual_reach"], "msg4_ack_unknown")
        self.assertIsNone(rows[0]["canonical_a_ue"])
        self.assertIsNone(rows[0]["canonical_a"])
        self.assertEqual(rows[0]["canonical_a_evidence"], "missing_ue_ack_event")

    def test_scheduled_ack_and_skipped_msg5_is_ue_side_canonical_a(self):
        records = [
            event("run-1", 0, 1, 10, "attempt_start"),
            event("run-1", 0, 1, 20, "msg4_rx", msg5_action="skipped"),
            event("run-1", 0, 1, 21, "msg4_ack_scheduled"),
        ]
        result, rows = self.run_export(records)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rows[0]["actual_reach"], "msg5_skip")
        self.assertIs(rows[0]["canonical_a_ue"], True)
        self.assertIsNone(rows[0]["canonical_a"])
        self.assertEqual(rows[0]["canonical_a_evidence"], "du_ack_missing")
        self.assertEqual(rows[0]["du_ack_state"], "unknown")
        self.assertNotIn("du_ack_evidence", rows[0])

    def test_conflicting_ack_events_are_inconclusive(self):
        records = [
            event("run-1", 0, 1, 10, "attempt_start"),
            event("run-1", 0, 1, 20, "msg4_rx", msg5_action="skipped"),
            event("run-1", 0, 1, 21, "msg4_ack_scheduled"),
            event("run-1", 0, 1, 22, "msg4_ack_withheld"),
        ]
        result, rows = self.run_export(records)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rows[0]["actual_reach"], "inconclusive")
        self.assertIsNone(rows[0]["canonical_a_ue"])
        self.assertIsNone(rows[0]["canonical_a"])

    def test_rrc_reject_and_msg5_precedence(self):
        records = [
            event("run-1", 0, 1, 10, "attempt_start"),
            event("run-1", 0, 1, 20, "msg5_submitted"),
            event("run-1", 0, 1, 21, "rrc_reject"),
            event("run-1", 0, 2, 30, "attempt_start"),
            event("run-1", 0, 2, 40, "msg5_submitted"),
        ]
        result, rows = self.run_export(records)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rows[0]["actual_reach"], "rrc_reject")
        self.assertEqual(rows[1]["actual_reach"], "msg5_submitted")
        self.assertTrue(all(row["canonical_a"] is False for row in rows))

    def test_malformed_json_and_run_id_mismatch_fail_without_output(self):
        cases = [
            {"events_text": "{not json\n"},
            {"events": [event("other-run", 0, 1, 10, "attempt_start")]},
            {"run_text": "{not json\n"},
        ]
        for case in cases:
            with self.subTest(case=case):
                result, rows = self.run_export(case.get("events", []),
                                               run_text=case.get("run_text"),
                                               events_text=case.get("events_text"))
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(rows, [])
                self.assertIn("export_labels:", result.stderr)

    def test_last_open_attempt_is_unknown(self):
        result, rows = self.run_export([
            event("run-1", 0, 9, 10, "attempt_start", ue_identity="0xaa")
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rows[0]["actual_reach"], "unknown")
        self.assertIsNone(rows[0]["canonical_a"])

    def test_exact_fapi_ack_promotes_only_ue_side_candidate(self):
        records = [
            event("run-1", 0, 1, 10, "attempt_start"),
            event("run-1", 0, 1, 20, "msg4_rx", msg5_action="skipped",
                  tc_rnti="0x4601"),
            event("run-1", 0, 1, 21, "msg4_ack_scheduled", tc_rnti="0x4601",
                  frame=321, slot=7, source="ra_pucch"),
        ]
        du = (
            "[FAPI] Sector#0: UCI.indication slot=321.7 PUCCH format 0/1 format=0 "
            "rnti=17921 sinr=20.0dB HARQ: harq_ack=ack\n"
        )
        result, rows = self.run_export(records, du_text=du)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(rows[0]["canonical_a"], True)
        self.assertEqual(rows[0]["du_ack_state"], "ack")
        self.assertEqual(rows[0]["canonical_a_evidence"], "ue_scheduler+ocudu_fapi")
        evidence = rows[0]["du_ack_evidence"]
        self.assertEqual((evidence["rnti"], evidence["frame"], evidence["slot"]),
                         ("0x4601", 321, 7))
        self.assertEqual(evidence["line"], 1)
        self.assertEqual(evidence["sector_id"], 0)
        self.assertRegex(evidence["log_sha256"], r"^[0-9a-f]{64}$")

    def test_fapi_join_is_exact_and_non_ack_is_not_negative_truth(self):
        records = [
            event("run-1", 0, 1, 10, "attempt_start"),
            event("run-1", 0, 1, 20, "msg4_rx", msg5_action="skipped",
                  tc_rnti="0x4601"),
            event("run-1", 0, 1, 21, "msg4_ack_scheduled", tc_rnti="0x4601",
                  frame=100, slot=3, source="ra_pucch"),
        ]
        cases = {
            "different slot": "Sector#0: UCI.indication slot=100.4 PUCCH format 0/1 format=0 rnti=17921 HARQ: harq_ack=ack\n",
            "different rnti": "Sector#0: UCI.indication slot=100.3 PUCCH format 0/1 format=0 rnti=17922 HARQ: harq_ack=ack\n",
            "dtx": "Sector#0: UCI.indication slot=100.3 PUCCH format 0/1 format=0 rnti=17921 HARQ: harq_ack=dtx\n",
            "nack": "Sector#0: UCI.indication slot=100.3 PUCCH format 0/1 format=0 rnti=17921 HARQ: harq_ack=nack\n",
            "duplicate": (
                "Sector#0: UCI.indication slot=100.3 PUCCH format 0/1 format=0 rnti=17921 HARQ: harq_ack=ack\n"
                "Sector#0: UCI.indication slot=100.3 PUCCH format 0/1 format=0 rnti=17921 HARQ: harq_ack=ack\n"
            ),
            "ignored evidence": (
                "ConRes CE ACKed rnti=0x4601\n"
                "Sector#0: UCI.indication slot=100.3 PUCCH format 2/3/4 format=2 rnti=17921 HARQ: harq_ack=ack\n"
            ),
        }
        for name, du in cases.items():
            with self.subTest(name=name):
                result, rows = self.run_export(records, du_text=du)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIsNone(rows[0]["canonical_a"])
                self.assertEqual(rows[0]["du_ack_state"], "unknown")
                self.assertIsNone(rows[0]["du_ack_evidence"])

    def test_retransmission_ack_can_confirm_after_initial_dtx(self):
        records = [
            event("run-1", 0, 1, 10, "attempt_start"),
            event("run-1", 0, 1, 20, "msg4_rx", msg5_action="skipped",
                  tc_rnti="0x4601"),
            event("run-1", 0, 1, 21, "msg4_ack_scheduled", tc_rnti="0x4601",
                  frame=100, slot=3, source="ra_pucch"),
            event("run-1", 0, 1, 22, "msg4_ack_scheduled", rnti="0x4601",
                  frame=100, slot=8, source="generic_retx"),
        ]
        du = (
            "Sector#0: UCI.indication slot=100.3 PUCCH format 0/1 format=0 rnti=17921 HARQ: harq_ack=dtx\n"
            "Sector#0: UCI.indication slot=100.8 PUCCH format 0/1 format=0 rnti=0x4601 HARQ: harq_ack=ack\n"
        )
        result, rows = self.run_export(records, du_text=du)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(rows[0]["canonical_a"], True)
        self.assertEqual(rows[0]["du_ack_evidence"]["slot"], 8)

    def test_one_du_ack_cannot_confirm_two_attempts_with_the_same_tuple(self):
        records = []
        for seq, start in ((1, 10), (2, 30)):
            records.extend([
                event("run-1", 0, seq, start, "attempt_start"),
                event("run-1", 0, seq, start + 1, "msg4_rx",
                      msg5_action="skipped", tc_rnti="0x4601"),
                event("run-1", 0, seq, start + 2, "msg4_ack_scheduled",
                      tc_rnti="0x4601", frame=100, slot=3,
                      source="ra_pucch"),
            ])
        du = ("Sector#0: UCI.indication slot=100.3 PUCCH format 0/1 format=0 "
              "rnti=17921 HARQ: harq_ack=ack\n")
        result, rows = self.run_export(records, du_text=du)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["canonical_a_ue"] is True for row in rows))
        self.assertTrue(all(row["canonical_a"] is None for row in rows))
        self.assertTrue(all(row["du_ack_evidence"] is None for row in rows))

    def test_malformed_fapi_candidate_fails_without_partial_output(self):
        records = [event("run-1", 0, 1, 10, "attempt_start")]
        malformed = (
            "Sector#0: UCI.indication slot=bad PUCCH format 0/1 rnti=17921 HARQ: harq_ack=ack\n",
            "Sector#0: UCI.indication slot=100.3 PUCCH format 0/1 rnti=17921 HARQ: outcome=ack\n",
        )
        for line in malformed:
            with self.subTest(line=line):
                result, rows = self.run_export(records, du_text=line)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(rows, [])
                self.assertIn("malformed FAPI HARQ evidence", result.stderr)

    def test_missing_sector_fails_without_output(self):
        records = [event("run-1", 0, 1, 10, "attempt_start")]
        line = "UCI.indication slot=100.3 PUCCH format 0/1 rnti=17921 HARQ: harq_ack=ack\n"
        result, rows = self.run_export(records, du_text=line)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(rows, [])

    def test_other_sector_is_ignored_in_shared_du_log(self):
        records = [
            event("run-1", 0, 1, 10, "attempt_start"),
            event("run-1", 0, 1, 20, "msg4_rx", msg5_action="skipped",
                  tc_rnti="0x4601"),
            event("run-1", 0, 1, 21, "msg4_ack_scheduled", tc_rnti="0x4601",
                  frame=100, slot=3, source="ra_pucch"),
        ]
        du = (
            "Sector#1: UCI.indication slot=bad PUCCH format 0/1 rnti=17922 HARQ: harq_ack=ack\n"
            "Sector#0: UCI.indication slot=100.3 PUCCH format 0/1 rnti=17921 HARQ: harq_ack=ack\n"
        )
        result, rows = self.run_export(records, du_text=du)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(rows[0]["canonical_a"], True)
        self.assertEqual(rows[0]["du_ack_evidence"]["sector_id"], 0)

    def test_du_join_requires_sector_in_run_json(self):
        run_text = json.dumps({"run_id": "run-1", "scenario": "A"})
        result, rows = self.run_export(
            [event("run-1", 0, 1, 10, "attempt_start")],
            run_text=run_text,
            du_text="Sector#0: UCI.indication slot=100.3 PUCCH format 0/1 "
                    "rnti=17921 HARQ: harq_ack=ack\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(rows, [])
        self.assertIn("du_sector_id", result.stderr)


if __name__ == "__main__":
    unittest.main()
