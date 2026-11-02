"""Exact 48-bit identity encoding tests; no radio is started."""

from pathlib import Path
import sys
import unittest


ANALYSIS = Path(__file__).resolve().parents[1] / "analysis"
sys.path.insert(0, str(ANALYSIS))

import identity  # noqa: E402


class IdentityTests(unittest.TestCase):
    def test_exact_split_and_roundtrip_across_48_bit_boundaries(self):
        values = (
            0,
            1,
            identity.PART1_MAX,
            1 << identity.PART1_BITS,
            0x0123456789AB,
            identity.FULL_MAX,
        )
        for value in values:
            with self.subTest(value=value):
                part1, part2 = identity.split_5g_s_tmsi(value)
                self.assertEqual(identity.join_5g_s_tmsi(part1, part2), value)
                self.assertEqual(identity.format_5g_s_tmsi(value), f"0x{value:012x}")

    def test_invalid_values_are_rejected_instead_of_truncated(self):
        for value in (-1, True, 1 << 48, "0x123", "123456789abc", "0xgggggggggggg"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    identity.parse_5g_s_tmsi(value)
        for part1, part2 in ((-1, 0), (1 << 39, 0), (0, -1), (0, 1 << 9), (True, 0)):
            with self.subTest(part1=part1, part2=part2):
                with self.assertRaises(ValueError):
                    identity.join_5g_s_tmsi(part1, part2)


if __name__ == "__main__":
    unittest.main()
