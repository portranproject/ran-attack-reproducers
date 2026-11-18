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
    def test_preserves_subscribers_for_shared_ru_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.conf"
            target = root / "runtime.conf"
            source.write_text("\n".join(f"uicc{i} = {{ imsi = \"{i}\"; }};" for i in range(5)))
            multi_ru_config.generate(source, target, 5)
            text = target.read_text()
            self.assertEqual(text, source.read_text())
            self.assertNotIn("RUs =", text)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_rejects_existing_radio_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.conf"
            source.write_text("uicc0 = {};\nRUs = ();\n")
            with self.assertRaises(ValueError):
                multi_ru_config.generate(source, root / "runtime.conf", 1)


if __name__ == "__main__":
    unittest.main()
