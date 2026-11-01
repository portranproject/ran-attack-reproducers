"""Subscriber/auth artifact scanner regression tests."""

import io
import gzip
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


SCANNER = Path(__file__).resolve().parents[1] / "analysis" / "check_sensitive_artifacts.py"


def secret_line():
    return (
        "UICC simulation: IMSI=" + "0" * 15 +
        ", Ki=" + "a" * 32 + ", OPc=" + "b" * 32 + "\n"
    )


def dump_line(label, size, ending="\n"):
    return label + ":" + "".join(f"{index:02x} " for index in range(size)) + ending


class SensitiveArtifactTests(unittest.TestCase):
    def run_scan(self, *paths):
        return subprocess.run(
            [sys.executable, str(SCANNER), *map(str, paths)],
            text=True, capture_output=True, check=False,
        )

    def test_plain_secret_is_named_without_echoing_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ue.log"
            path.write_text(secret_line())
            result = self.run_scan(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sensitive artifact", result.stderr)
        self.assertIn("imsi,ki,opc", result.stderr)
        self.assertNotIn("0" * 15, result.stderr)
        self.assertNotIn("a" * 32, result.stderr)

    def test_redacted_marker_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ue.log"
            path.write_text("[REDACTED subscriber/auth material]\n")
            result = self.run_scan(path)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_oai_spaced_auth_dumps_are_named_without_echoing_values(self):
        sizes = {
            "opc": 16, "amf": 2, "key": 16, "sqn": 6, "rand": 16,
            "milenage output ik": 16, "milenage output ck": 16,
            "milenage output res": 8, "milenage output autn": 8,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ue.log"
            payload = "".join(
                dump_line(label, size, "\x1b[0m\r\n" if label == "key" else "\n")
                for label, size in sizes.items()
            )
            path.write_text(payload)
            result = self.run_scan(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("amf,autn,ck,ik,key,opc,rand,res,sqn", result.stderr)
        self.assertNotIn("00 01 02 03", result.stderr)

    def test_spaced_auth_dump_near_misses_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ue.log"
            path.write_text(
                dump_line("kamf", 2) + dump_line("key", 15) + dump_line("key", 17)
            )
            result = self.run_scan(path)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_oai_config_auth_fields_are_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ue.conf"
            path.write_text(
                "key=" + "a" * 32 + "\nsqn=" + "b" * 12 + "\namf=" + "c" * 4 + "\n"
            )
            result = self.run_scan(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("amf,key,sqn", result.stderr)
        self.assertNotIn("a" * 32, result.stderr)

    def test_tar_member_is_scanned(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "evidence.tar.gz"
            payload = secret_line().encode()
            info = tarfile.TarInfo("ue.log")
            info.size = len(payload)
            with tarfile.open(archive, "w:gz") as output:
                output.addfile(info, io.BytesIO(payload))
            result = self.run_scan(archive)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("evidence.tar.gz::ue.log", result.stderr)
        self.assertNotIn("b" * 32, result.stderr)

    def test_large_plain_log_is_scanned_without_loading_it_all(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "odu.log"
            with path.open("wb") as handle:
                handle.write(b"not an archive\n")
                handle.truncate(100 * 1024 * 1024 + 4096)
                handle.seek(100 * 1024 * 1024 + 1)
                handle.write(secret_line().encode())
            result = self.run_scan(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("imsi,ki,opc", result.stderr)
        self.assertNotIn("a" * 32, result.stderr)

    def test_oversized_gzip_is_streamed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "odu.log.gz"
            with gzip.open(path, "wb", compresslevel=1) as handle:
                chunk = b"ordinary log line\n" * 65536
                for _ in range(96):
                    handle.write(chunk)
                handle.write(secret_line().encode())
            result = self.run_scan(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("imsi,ki,opc", result.stderr)
        self.assertNotIn("a" * 32, result.stderr)

    def test_oversized_tar_member_is_streamed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "odu.log"
            with source.open("wb") as handle:
                handle.write(secret_line().encode())
                handle.truncate(100 * 1024 * 1024 + 4096)
            archive = Path(directory) / "evidence.tar.gz"
            with tarfile.open(archive, "w:gz", compresslevel=1) as output:
                output.add(source, arcname="odu.log")
            result = self.run_scan(archive)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("evidence.tar.gz::odu.log", result.stderr)
        self.assertIn("imsi,ki,opc", result.stderr)
        self.assertNotIn("a" * 32, result.stderr)

    def test_current_repository_passes(self):
        result = self.run_scan()
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
