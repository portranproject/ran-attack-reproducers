import hashlib
import tempfile
import unittest
from pathlib import Path

from analysis.normalize_pcap import normalize


HEADER = "frame\ttime_epoch\tsrc\tdst\tran_id\tamf_id\tmessage_type\tscheme_id\tmcc\tmnc\tmsin\n"


class NormalizePcapTest(unittest.TestCase):
    def fixture(self, identity=True):
        temporary = tempfile.TemporaryDirectory()
        path = Path(temporary.name) / "nas.tsv"
        lines = [
            "1\t1.000000001\ta\tb\t7\t\t0x41\t0\t001\t01\t0123456780\n",
            "2\t1.100000001\tb\ta\t7\t9\t0x56\t\t\t\t\n",
            ("3\t1.200000001\ta\tb\t7\t9\t0x5c\t0\t001\t01\t0123456780\n" if identity else "3\t1.200000001\ta\tb\t7\t9\t0x57\t\t\t\t\n"),
        ]
        path.write_text(HEADER + "".join(lines))
        return temporary, path

    def test_identity_response_is_hashed_and_removed(self):
        temporary, path = self.fixture()
        self.addCleanup(temporary.cleanup)
        expected = hashlib.sha256(b"001010123456780").hexdigest()
        rows, oracle = normalize(path, expected)
        self.assertEqual([row["message"] for row in rows], ["RegistrationRequest", "AuthenticationRequest", "IdentityResponse"])
        self.assertEqual(oracle["observed_subscriber_fingerprint"], expected)
        self.assertNotIn("0123456780", str(rows))

    def test_control_has_no_observed_exposure(self):
        temporary, path = self.fixture(False)
        self.addCleanup(temporary.cleanup)
        rows, oracle = normalize(path, "a" * 64)
        self.assertEqual(rows[-1]["message"], "AuthenticationResponse")
        self.assertIsNone(oracle["observed_subscriber_fingerprint"])

    def test_multiple_contexts_fail_closed(self):
        temporary, path = self.fixture()
        self.addCleanup(temporary.cleanup)
        with path.open("a") as output:
            output.write("4\t1.3\ta\tb\t8\t10\t0x56\t\t\t\t\n")
        with self.assertRaisesRegex(ValueError, "단일"):
            normalize(path, "a" * 64)


if __name__ == "__main__":
    unittest.main()
