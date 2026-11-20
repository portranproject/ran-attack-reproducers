import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "reproducers/authentication-timeout-exhaustion/analysis/multi_ru_config.py"


def _source(path: Path, count: int) -> None:
    blocks = "".join(
        f'uicc{i} = {{ imsi="{i}"; key="00"; opc="00"; }}\n'
        for i in range(count)
    )
    path.write_text(blocks, encoding="utf-8")


class AuthScaleDiagnosticTest(unittest.TestCase):
    def test_diagnostic_cap_is_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.conf"
            _source(src, 20)
            env = {**os.environ}
            env.pop("AUTH_STALL_CELL_DIAGNOSTIC_MAX_ENDPOINTS", None)
            default = subprocess.run([sys.executable, str(SCRIPT), str(src), str(Path(tmp) / "a.conf"), "20"], capture_output=True, text=True)
            assert default.returncode != 0
            env["AUTH_STALL_CELL_DIAGNOSTIC_MAX_ENDPOINTS"] = "120"
            diagnostic = subprocess.run([sys.executable, str(SCRIPT), str(src), str(Path(tmp) / "b.conf"), "20"], capture_output=True, text=True, env=env)
            assert diagnostic.returncode == 0, diagnostic.stderr
            text = (Path(tmp) / "b.conf").read_text()
            assert "tcp://127.0.0.1:2101" in text


if __name__ == "__main__":
    unittest.main()
