import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

class RunnerTest(unittest.TestCase):
    def test_control_run_seals_phase_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_root = root / "runs"
            profiles = root / "profiles.json"
            profiles.write_text(json.dumps({
                "schema": "auth-timeout.profiles.v1", "attacker_count": 2,
                "profiles": [
                    {"role": "attacker", "subscriber_fingerprint": "a" * 64, "config_sha256": "1" * 64},
                    {"role": "attacker", "subscriber_fingerprint": "b" * 64, "config_sha256": "2" * 64},
                    {"role": "witness", "subscriber_fingerprint": "c" * 64, "config_sha256": "3" * 64},
                ],
            }, sort_keys=True, separators=(",", ":")) + "\n")
            for name in ("gnb.yml", "core.yml", "ue.patch"):
                (root / name).write_text(name + "\n")
            binary = root / "nr-uesoftmodem"
            binary.write_text("#!/bin/sh\nexit 0\n")
            binary.chmod(0o700)
            (root / "liboai_zmqdevif.so").write_bytes(b"fixture zmq library\n")
            driver = root / "phase.py"
            driver.write_text("""#!/usr/bin/env python3
import os, pathlib, shutil, tempfile
from test_export_labels import make_run
out = pathlib.Path(os.environ['AUTH_TIMEOUT_RUN_DIR'])
with tempfile.TemporaryDirectory() as directory:
    source = pathlib.Path(directory)
    make_run(source, os.environ['AUTH_TIMEOUT_MODE'], os.environ['AUTH_TIMEOUT_RUN_ID'])
    for path in source.iterdir():
        if path.name not in {'run.json', 'profiles.manifest.json'}:
            shutil.copy2(path, out / path.name)
""")
            driver.chmod(0o700)
            fakebin = root / "fakebin"
            fakebin.mkdir()
            flock = fakebin / "flock"
            flock.write_text("#!/bin/sh\nexit 0\n")
            flock.chmod(0o700)
            config = root / "auth-timeout.conf"
            values = {
                "AUTH_TIMEOUT_RUN_ROOT": run_root,
                "PHASE_DRIVER": driver,
                "PROFILES_MANIFEST": profiles,
                "GNB_CONFIG": root / "gnb.yml",
                "CORE_CONFIG": root / "core.yml",
                "OAI_BIN": binary,
                "ZMQ_LIB": root / "liboai_zmqdevif.so",
                "UE_PATCH": root / "ue.patch",
                "START_INTERVAL_MS": "100",
                "REGISTRATION_LIMIT_MS": "10000",
            }
            config.write_text("".join(f"{key}={shlex.quote(str(value))}\n" for key, value in values.items()))
            module = Path(__file__).resolve().parents[1]
            environment = os.environ.copy()
            environment.update({
                "AUTH_TIMEOUT_CONF": str(config),
                "PATH": str(fakebin) + os.pathsep + environment["PATH"],
                "PYTHONPATH": str(module / "tests") + os.pathsep + str(module) + os.pathsep + environment.get("PYTHONPATH", ""),
            })
            result = subprocess.run(
                [str(module / "bin" / "auth-timeout-run"), "control", "-n", "runner-control", "-e", "0"],
                text=True, capture_output=True, env=environment, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            output = run_root / "runner-control"
            self.assertTrue(json.loads((output / "verdict.json").read_text())["passed"])
            self.assertTrue((output / "evidence_manifest.json").is_file())

            override = subprocess.run(
                [str(module / "bin" / "auth-timeout-run"), "control", "-n", "runner-control-override", "-e", "0", "-t", "12000"],
                text=True, capture_output=True, env=environment, timeout=20,
            )
            self.assertEqual(override.returncode, 0, override.stdout + override.stderr)
            run = json.loads((run_root / "runner-control-override" / "run.json").read_text())
            self.assertEqual(run["registration_limit_ms"], 12_000)


if __name__ == "__main__":
    unittest.main()
