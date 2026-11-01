import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "rss-cu200"


class Cu200Tests(unittest.TestCase):
    def run_suite(self, mode, duration="2", **extra):
        temp = tempfile.TemporaryDirectory()
        root = pathlib.Path(temp.name)
        trace = root / "trace"
        runner = root / "runner"
        runner.write_text(
            "#!/bin/sh\n"
            "printf '%s|%s|%s|%s\\n' \"$ODU_SECTOR_ID\" \"$ZMQ_TX\" \"$ZMQ_RX\" \"$*\" >> \"$TRACE\"\n"
        )
        runner.chmod(0o755)
        odu = root / "odu.log"
        odu.write_text("ready\n")
        env = dict(
            os.environ,
            RSS_CU200_RUNNER=str(runner), TRACE=str(trace),
            LOGDIR=str(root / "runs"), ODU_LOG=str(odu),
            CU200_GNB_READY_CMD="true", FLOCK_BIN="true",
            LOCK_FILE=str(root / "lock"), WITNESS_DELAY_MS="1000", HOLD_MS="3000",
        )
        env.update(extra)
        result = subprocess.run(
            ["bash", str(SCRIPT), mode, "-n", "T1", "-d", duration],
            env=env, text=True, capture_output=True, timeout=10,
        )
        return temp, root, trace, result

    def test_attack_maps_three_attackers_and_independent_witness(self):
        temp, root, trace, result = self.run_suite("attack")
        with temp:
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = trace.read_text().splitlines()
            self.assertEqual(len(rows), 4)
            for sector in range(4):
                self.assertTrue(any(
                    row.startswith(f"{sector}|tcp://127.0.0.1:{4557 + 2 * sector}|tcp://127.0.0.1:{4556 + 2 * sector}|")
                    for row in rows
                ))
            witness = next(row for row in rows if row.startswith("3|"))
            self.assertIn("-p 1 -t 1000", witness)
            for sector in range(3):
                attacker = next(row for row in rows if row.startswith(f"{sector}|"))
                self.assertIn("-o 0 -H 3000 -r 0 -M 1 -A 1", attacker)
            self.assertTrue((root / "runs" / "T1" / "orchestration.json").is_file())

    def test_rejects_a_witness_window_beyond_context_lifetime(self):
        temp, _, trace, result = self.run_suite(
            "attack", duration="4", WITNESS_DELAY_MS="1000", HOLD_MS="3000"
        )
        with temp:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not exceed HOLD_MS", result.stderr)
            self.assertFalse(trace.exists())

    def test_control_does_not_require_an_attack_witness_window(self):
        temp, _, trace, result = self.run_suite("control", duration="1")
        with temp:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(trace.read_text().splitlines()), 4)

    def test_long_lived_children_do_not_inherit_the_run_lock(self):
        content = SCRIPT.read_text()
        for command in (
            'bash -c "$CU200_GNB_STOP_CMD" 9>&-',
            'bash -c "$CU200_GNB_RESTART_CMD" 9>&-',
            'bash -c "$CU200_GNB_READY_CMD" 9>&-',
            '9>&- > "$OUT/$name.runner.log"',
        ):
            self.assertIn(command, content)


if __name__ == "__main__":
    unittest.main()
