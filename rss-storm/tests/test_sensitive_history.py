"""Reachable Git-history credential scanner regression tests."""

import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


SCANNER = Path(__file__).resolve().parents[1] / "analysis" / "check_sensitive_history.py"


def secret_line():
    return (
        "UICC simulation: IMSI=" + "0" * 15 +
        ", Ki=" + "a" * 32 + ", OPc=" + "b" * 32 + "\n"
    )


class SensitiveHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "History test")
        self.git("config", "user.email", "history@example.invalid")

    def git(self, *arguments):
        return subprocess.run(
            ["git", "-C", str(self.repo), *arguments],
            env=dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull),
            text=True, capture_output=True, check=True,
        )

    def commit(self, message):
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", message)

    def scan(self):
        return subprocess.run(
            [sys.executable, str(SCANNER), str(self.repo)],
            text=True, capture_output=True, check=False,
        )

    def test_redacted_tip_still_fails_on_reachable_old_blob_without_values(self):
        log = self.repo / "ue.log"
        log.write_text(secret_line())
        self.commit("secret fixture")
        log.write_text("[REDACTED subscriber/auth material]\n")
        self.commit("redacted fixture")

        result = self.scan()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sensitive Git blob", result.stderr)
        self.assertIn("ue.log", result.stderr)
        self.assertIn("imsi,ki,opc", result.stderr)
        self.assertIn("findings=1 errors=0", result.stderr)
        self.assertNotIn("0" * 15, result.stderr)
        self.assertNotIn("a" * 32, result.stderr)

    def test_deleted_archive_still_fails_from_history(self):
        archive = self.repo / "evidence.tar.gz"
        payload = secret_line().encode()
        info = tarfile.TarInfo("ue.log")
        info.size = len(payload)
        with tarfile.open(archive, "w:gz") as output:
            output.addfile(info, io.BytesIO(payload))
        self.commit("archive fixture")
        archive.unlink()
        self.commit("delete archive")

        result = self.scan()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("evidence.tar.gz::ue.log", result.stderr)
        self.assertNotIn("b" * 32, result.stderr)

    def test_clean_reachable_history_passes(self):
        (self.repo / "ue.log").write_text("[REDACTED subscriber/auth material]\n")
        self.commit("clean fixture")
        result = self.scan()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("reachable blobs", result.stdout)


if __name__ == "__main__":
    unittest.main()
