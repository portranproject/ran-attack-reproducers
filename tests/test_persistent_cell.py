#!/usr/bin/env python3
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CTL = ROOT / "ctl.sh"


class PersistentCellCommandTest(unittest.TestCase):
    def run_ctl(self, *args):
        return subprocess.run(
            ["bash", str(CTL), *args], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def test_cell_up_dry_run_maps_to_same_cell_start(self):
        result = self.run_ctl("cell", "up", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("same-cell-run start", result.stdout)
        self.assertIn("-n cell-", result.stdout)

    def test_attack_run_dry_run_declares_reserved_slot(self):
        result = self.run_ctl(
            "attack", "run", "l3-06", "--profile", "p5", "--enable", "--dry-run"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("nas-counter-desynchronization", result.stdout)
        self.assertIn("SLOT_GATE", result.stdout)

    def test_attack_run_requires_a_running_cell(self):
        result = self.run_ctl("attack", "run", "l3-06", "--profile", "p5", "--enable")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("same-cell 세션", result.stderr)

    def test_cell_rejects_multi_ue_reserved_modules(self):
        result = self.run_ctl("cell", "up", "--modules", "L3-01-O", "--dry-run")
        self.assertEqual(result.returncode, 2)
        self.assertIn("단일 UE 모듈만", result.stderr)

    def test_attack_run_requires_enable(self):
        result = self.run_ctl("attack", "run", "l3-06", "--profile", "p5")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--enable", result.stderr)

    def test_boundary_document_separates_ops(self):
        text = (ROOT / "docs" / "BOUNDARY.md").read_text(encoding="utf-8")
        self.assertIn("범위 밖", text)
        self.assertIn("verify_live.py", text)
        self.assertIn("옛 방식 기록", text)


if __name__ == "__main__":
    unittest.main()
