"""Offline checks for the saturation-profile switch (no gNB, no host files)."""
import os
import pathlib
import subprocess
import tempfile
import unittest


TOOL = pathlib.Path(__file__).resolve().parents[1] / "bin" / "rss-gnb-profile"

CU_YAML = """cu_cp:
  max_nof_ues: 90
  amf: { addrs: 10.53.1.2, port: 38412, bind_addrs: 10.53.1.1 }
  f1ap: { bind_addrs: 172.31.5.10 }
"""

DU_YAML = """cell_cfg:
  pci: 1
"""


class ProfileSwitchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = pathlib.Path(self.tmp.name)
        (self.cfg / "cu.yaml").write_text(CU_YAML)
        (self.cfg / "du.yaml").write_text(DU_YAML)
        self.env = dict(os.environ, RSS_CONF=str(self.cfg / "absent.conf"),
                        CFGDIR=str(self.cfg))

    def run_tool(self, *args):
        return subprocess.run(
            ["bash", str(TOOL), "--role", "cu", *args],
            env=self.env, text=True, capture_output=True, timeout=10,
        )

    def max_nof_ues(self):
        for line in (self.cfg / "cu.yaml").read_text().splitlines():
            if "max_nof_ues:" in line:
                return int(line.split(":")[1])
        raise AssertionError("max_nof_ues disappeared")

    def test_cap_sets_the_cu_admission_limit(self):
        result = self.run_tool("cap", "30")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.max_nof_ues(), 30)

    def test_default_restores_the_shipped_limit(self):
        self.run_tool("cap", "30")
        result = self.run_tool("cap", "default")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.max_nof_ues(), 8192)

    def test_out_of_scope_limits_are_refused(self):
        result = self.run_tool("cap", "91")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("1..90", result.stderr)

    def test_show_reports_the_current_limit(self):
        result = self.run_tool("cap", "show")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("max_nof_ues: 90", result.stdout)


if __name__ == "__main__":
    unittest.main()
