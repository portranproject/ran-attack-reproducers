import json
import tempfile
import unittest
from pathlib import Path

from analysis.normalize_f1 import normalize


HEADER = "frame\ttime_epoch\tsrc\tdst\tdu_id\tcu_id\trrc_setup_complete\tsecurity_mode_command\tsecurity_mode_complete\tue_capability_enquiry\tue_capability_information\n"


class NormalizeF1Test(unittest.TestCase):
    def test_selects_capability_context_and_tracks_security(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "f1.tsv"
            raw.write_text(HEADER +
                "1\t1.0\t10.0.0.2\t10.0.0.1\t9\t7\t1\t\t\t\t\n" +
                "2\t1.1\t10.0.0.2\t10.0.0.1\t9\t7\t\t\t\t\t1\n" +
                "3\t1.2\t10.0.0.1\t10.0.0.2\t9\t7\t\t1\t\t\t\n" +
                "4\t1.3\t10.0.0.2\t10.0.0.1\t9\t7\t\t\t1\t\t\n")
            normalize(raw, "10.0.0.1", "10.0.0.2", root / "out")
            rows = [json.loads(line) for line in (root / "out/observations.jsonl").read_text().splitlines()]
        self.assertEqual([row["message"] for row in rows], ["RRCSetupComplete", "UECapabilityInformation", "SecurityModeCommand", "SecurityModeComplete"])
        self.assertEqual(rows[1]["rrc_security_before"], "OFF")
        self.assertEqual({(row["gnb_cu_ue_f1ap_id"], row["gnb_du_ue_f1ap_id"]) for row in rows}, {(7, 9)})

    def test_ambiguous_capability_context_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "f1.tsv"
            raw.write_text(HEADER +
                "1\t1.0\t10.0.0.2\t10.0.0.1\t9\t7\t\t\t\t\t1\n" +
                "2\t1.1\t10.0.0.2\t10.0.0.1\t10\t8\t\t\t\t\t1\n")
            with self.assertRaisesRegex(ValueError, "하나"):
                normalize(raw, "10.0.0.1", "10.0.0.2", root / "out")


if __name__ == "__main__":
    unittest.main()
