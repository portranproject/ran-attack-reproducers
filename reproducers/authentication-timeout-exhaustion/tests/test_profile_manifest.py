import tempfile
import unittest
from pathlib import Path

from analysis.profile_manifest import build


def test_imsi(index):
    return "00101" + f"{index:010d}"


class ProfileManifestTest(unittest.TestCase):
    def test_unique_attackers_and_witness_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for index, imsi in enumerate((test_imsi(1), test_imsi(2), test_imsi(3))):
                path = root / f"ue{index}.conf"
                path.write_text(f'uicc0 = {{ imsi = "{imsi}"; }};\n')
                paths.append(path)
            result = build(paths[:2], paths[2])
            self.assertEqual(result["attacker_count"], 2)
            self.assertEqual(result["attacker_process_count"], 2)
            self.assertEqual(len({row["subscriber_fingerprint"] for row in result["profiles"]}), 3)

    def test_multiple_uicc_profiles_share_one_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attacker = root / "attacker.conf"
            witness = root / "witness.conf"
            attacker.write_text(
                f'uicc0 = {{ imsi = {test_imsi(1)}; }};\n'
                f'uicc1 = {{ imsi = "{test_imsi(2)}"; }};\n'
            )
            witness.write_text(f'uicc0 = {{ imsi = {test_imsi(3)}; }};\n')
            result = build([attacker], witness)
            rows = [row for row in result["profiles"] if row["role"] == "attacker"]
            self.assertEqual(result["attacker_count"], 2)
            self.assertEqual(result["attacker_process_count"], 1)
            self.assertEqual([(row["process_index"], row["ue_id"]) for row in rows], [(0, 0), (0, 1)])

    def test_duplicate_subscriber_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for index in range(3):
                path = root / f"ue{index}.conf"
                path.write_text(f'uicc0 = {{ imsi = "{test_imsi(1)}"; }};\n')
                paths.append(path)
            with self.assertRaises(ValueError):
                build(paths[:2], paths[2])

    def test_one_attacker_is_not_accumulation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attacker, witness = root / "a.conf", root / "w.conf"
            attacker.write_text(f'uicc0 = {{ imsi = "{test_imsi(1)}"; }};\n')
            witness.write_text(f'uicc0 = {{ imsi = "{test_imsi(2)}"; }};\n')
            with self.assertRaises(ValueError):
                build([attacker], witness)


if __name__ == "__main__":
    unittest.main()
