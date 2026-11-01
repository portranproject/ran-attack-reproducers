"""UE log sanitization tests; fixture values never leave the temporary directory."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REDACTOR = Path(__file__).resolve().parents[1] / "analysis" / "sanitize_ue_log.py"


def secret_line():
    return (
        "UICC simulation: IMSI=" + "0" * 15 +
        ", IMEISV=" + "1" * 16 + ", Ki=" + "a" * 32 +
        ", OPc=" + "b" * 32 + "\n"
    )


def dump_line(label, size):
    return label + ":" + "".join(f"{index:02x} " for index in range(size)) + "\r\n"


class SensitiveLogRedactionTests(unittest.TestCase):
    def run_redactor(self, log, report):
        return subprocess.run(
            [sys.executable, str(REDACTOR), str(log), str(report), "run-1"],
            text=True, capture_output=True, check=False,
        )

    def test_sensitive_line_is_replaced_without_echoing_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "ue.log"
            report = root / "ue_redaction.json"
            log.write_text("before\n" + secret_line() + "after\n")
            result = self.run_redactor(log, report)
            content = log.read_text()
            metadata = json.loads(report.read_text())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(content.splitlines(), [
            "before", "[REDACTED subscriber/auth material]", "after",
        ])
        self.assertEqual(metadata["status"], "redacted")
        self.assertEqual(metadata["redacted_lines"], 1)
        self.assertEqual(metadata["output_sha256"],
                         hashlib.sha256(content.encode()).hexdigest())
        for value in ("0" * 15, "1" * 16, "a" * 32, "b" * 32):
            self.assertNotIn(value, result.stdout + result.stderr + content)

    def test_clean_log_is_unchanged_and_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "ue.log"
            report = root / "ue_redaction.json"
            original = b"[RSS] configured\nnormal diagnostic\n"
            log.write_bytes(original)
            result = self.run_redactor(log, report)
            metadata = json.loads(report.read_text())
            self.assertEqual(log.read_bytes(), original)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(metadata["status"], "clean")
        self.assertEqual(metadata["redacted_lines"], 0)

    def test_spaced_auth_dump_is_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "ue.log"
            report = root / "ue_redaction.json"
            log.write_text("before\n" + dump_line("milenage output ik", 16) + "after\n")
            result = self.run_redactor(log, report)
            content = log.read_text()
            metadata = json.loads(report.read_text())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(content.splitlines(), [
            "before", "[REDACTED subscriber/auth material]", "after",
        ])
        self.assertEqual(metadata["status"], "redacted")
        self.assertEqual(metadata["redacted_lines"], 1)
        self.assertNotIn("00 01 02 03", result.stdout + result.stderr + content)

    def test_symlink_is_rejected_without_touching_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.log"
            target.write_text(secret_line())
            link = root / "ue.log"
            link.symlink_to(target)
            result = self.run_redactor(link, root / "report.json")
            self.assertEqual(target.read_text(), secret_line())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a regular file", result.stderr)


if __name__ == "__main__":
    unittest.main()
