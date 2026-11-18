import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).parents[1] / "analysis/multi_ru_config.py"
SPEC = importlib.util.spec_from_file_location("multi_ru_config", MODULE)
multi_ru_config = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(multi_ru_config)


class MultiRuConfigTest(unittest.TestCase):
    def test_adds_independent_ru_and_zmq_arrays_at_the_requested_offset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.conf"
            target = root / "runtime.conf"
            source.write_text("\n".join(f"uicc{i} = {{ imsi = \"{i}\"; }};" for i in range(5)))
            multi_ru_config.generate(source, target, 5, 5)
            text = target.read_text()
            self.assertIn(source.read_text().strip(), text)
            self.assertEqual(text.count('sdr_addrs = "type=zmq"'), 5)
            self.assertEqual(text.count("ru_id = "), 5)
            self.assertEqual(text.count("tx_channels = "), 5)
            self.assertIn("tcp://127.0.0.1:2601", text)
            self.assertIn("tcp://127.0.0.1:3001", text)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_rejects_existing_radio_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.conf"
            for section in ("RUs", "cells", "zmq"):
                with self.subTest(section=section):
                    source.write_text(f"uicc0 = {{}};\n{section} = ();\n")
                    with self.assertRaises(ValueError):
                        multi_ru_config.generate(source, root / f"runtime-{section}.conf", 1)

    def test_rejects_a_sixteenth_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.conf"
            source.write_text("\n".join(f"uicc{i} = {{}};" for i in range(5)))
            with self.assertRaises(ValueError):
                multi_ru_config.generate(source, root / "runtime.conf", 5, 11)


if __name__ == "__main__":
    unittest.main()
