import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILD = ROOT / "bin" / "downlink-imsi-build"
RUNNER = ROOT / "bin" / "downlink-imsi-run"


class SameCellRaGateContractTests(unittest.TestCase):
    def test_build_applies_attack_patch_before_common_gate(self):
        script = BUILD.read_text()
        self.assertIn("same-cell-ra-gate-w38.patch", script)
        self.assertLess(script.index('apply "$PATCH"'), script.index('apply "$SAME_CELL_GATE_PATCH"'))
        self.assertIn("grep -Faq 'DOWNLINK_IMSI_EXTRACTOR event=%s' \"$BIN\"", script)
        self.assertIn("grep -Faq 'identity_response_substituted' \"$BIN\"", script)
        self.assertIn("grep -Faq 'OAI_SAME_CELL_GATE_FILE' \"$BIN\"", script)

    def test_prestart_fails_closed_and_passes_gate_to_ue(self):
        script = RUNNER.read_text()
        check = script.index("$SAME_CELL_UE_GATE_FILE == /*")
        guard = script.rindex("if (( SAME_CELL_PRESTART )); then", 0, check)
        launch = script.index('OAI_SAME_CELL_GATE_FILE="$SAME_CELL_UE_GATE_FILE"')
        self.assertLess(guard, check)
        self.assertLess(check, launch)
        self.assertIn("-f $SAME_CELL_UE_GATE_FILE", script[guard:launch])
        self.assertIn("! -L $SAME_CELL_UE_GATE_FILE", script[guard:launch])
        self.assertIn("grep -Faq 'OAI_SAME_CELL_GATE_FILE' \"$OAI_BIN\"", script[guard:launch])

    def test_shell_entrypoints_parse(self):
        for script in (BUILD, RUNNER):
            subprocess.run(["bash", "-n", str(script)], check=True)


if __name__ == "__main__":
    unittest.main()
