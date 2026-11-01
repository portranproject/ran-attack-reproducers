"""Run-scoped DU log capture rejects rotation and mutable prefixes."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CAPTURE = Path(__file__).resolve().parents[1] / "analysis" / "capture_du_log.py"


class DuLogCaptureTests(unittest.TestCase):
    def run_capture(self, *args):
        return subprocess.run(
            [sys.executable, str(CAPTURE), *map(str, args)],
            text=True,
            capture_output=True,
            check=False,
        )

    def start(self, root, initial=b"boot\n"):
        source = root / "odu.log"
        state = root / "start.json"
        source.write_bytes(initial)
        result = self.run_capture("start", source, state)
        self.assertEqual(result.returncode, 0, result.stderr)
        return source, state

    def finish(self, root, source, state):
        slice_path = root / "odu-run.log"
        manifest_path = root / "slice.json"
        result = self.run_capture(
            "finish", source, state, slice_path, manifest_path
        )
        return result, slice_path, manifest_path

    def test_finish_captures_only_complete_appended_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, state = self.start(root)
            appended = b"UCI.indication slot=321.7 HARQ: harq_ack=ack\n"
            with source.open("ab") as handle:
                handle.write(appended)

            result, slice_path, manifest_path = self.finish(root, source, state)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(slice_path.read_bytes(), appended)
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["start_offset"], len(b"boot\n"))
            self.assertEqual(manifest["end_offset"], len(b"boot\n") + len(appended))
            self.assertEqual(manifest["discarded_trailing_bytes"], 0)
            self.assertEqual(manifest["sha256"], hashlib.sha256(appended).hexdigest())

    def test_finish_rejects_rotated_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, state = self.start(root)
            replacement = root / "replacement.log"
            replacement.write_bytes(b"boot\nnew\n")
            os.replace(replacement, source)

            result, slice_path, manifest_path = self.finish(root, source, state)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source rotated or was replaced", result.stderr)
            self.assertFalse(slice_path.exists())
            self.assertFalse(manifest_path.exists())

    def test_finish_rejects_truncation_and_prefix_rewrite(self):
        cases = {
            "truncated": b"x\n",
            "rewritten": b"changed\nnew\n",
        }
        for name, replacement in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source, state = self.start(root, b"original\n")
                source.write_bytes(replacement)

                result, slice_path, manifest_path = self.finish(root, source, state)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "source was truncated" if name == "truncated"
                    else "source prefix changed after capture start",
                    result.stderr,
                )
                self.assertFalse(slice_path.exists())
                self.assertFalse(manifest_path.exists())

    def test_finish_discards_partial_trailing_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, state = self.start(root)
            with source.open("ab") as handle:
                handle.write(b"complete\npartial")

            result, slice_path, manifest_path = self.finish(root, source, state)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(slice_path.read_bytes(), b"complete\n")
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["discarded_trailing_bytes"], len(b"partial"))
            self.assertEqual(manifest["source_size_at_finish"], source.stat().st_size)

    def test_start_discards_preexisting_partial_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "odu.log"
            state = root / "start.json"
            initial = b"boot\npartial"
            source.write_bytes(initial)

            result = self.run_capture("start", source, state)

            self.assertEqual(result.returncode, 0, result.stderr)
            start_state = json.loads(state.read_text())
            self.assertIs(start_state["discard_leading_partial"], True)
            continuation = b" remainder\n"
            with source.open("ab") as handle:
                handle.write(continuation + b"fresh\ntrailing")

            result, slice_path, manifest_path = self.finish(root, source, state)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(slice_path.read_bytes(), b"fresh\n")
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["capture_offset"], len(initial))
            self.assertEqual(
                manifest["start_offset"], len(initial) + len(continuation)
            )
            self.assertEqual(
                manifest["discarded_leading_bytes"], len(continuation)
            )
            self.assertEqual(manifest["discarded_trailing_bytes"], len(b"trailing"))


if __name__ == "__main__":
    unittest.main()
