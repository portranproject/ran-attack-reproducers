import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class BlindBuildContractTests(unittest.TestCase):
    def test_common_same_cell_gate_is_applied_after_the_blind_patch(self):
        source = (ROOT / "bin" / "blind-build").read_text()
        self.assertIn("workloads/normal-ue/patch/same-cell-ra-gate-w38.patch", source)
        blind_apply = 'apply "$PATCH"'
        gate_apply = 'apply "$SAME_CELL_GATE_PATCH"'
        self.assertLess(source.index(blind_apply), source.index(gate_apply))
        self.assertIn("OAI_SAME_CELL_GATE_FILE", source)


if __name__ == "__main__":
    unittest.main()
