"""Offline profile provisioning contracts; no remote host is touched."""

import csv
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "provision_profiles.py"
VICTIM_IMSI = "001010123456780"
VICTIM_KEY = "00112233445566778899aabbccddeeff"
VICTIM_OPC = "63bfa50ee6523365ff14c1f45f88737d"
VICTIM_IP = "10.45.1.2"


class ProvisionProfilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.victim = self.root / "victim.conf"
        self.env = self.root / "open5gs.env"
        self.victim.write_text(
            f'uicc0 = {{ imsi="{VICTIM_IMSI}"; key="{VICTIM_KEY}";\n'
            f'          opc="{VICTIM_OPC}";\n'
            '          pdu_sessions=( { dnn="internet"; nssai_sst=1; } ); }\n'
        )
        self.env.write_text(
            "MONGODB_IP=127.0.0.1\n"
            "OPEN5GS_IP=10.53.1.2\n"
            "UE_IP_BASE=10.45.0\n"
            f"SUBSCRIBER_DB={VICTIM_IMSI},{VICTIM_KEY},opc,{VICTIM_OPC},8000,9,{VICTIM_IP}\n"
            "MCC=001\nMNC=01\nTZ=UTC\n"
        )

    def execute(self, output, *extra):
        return subprocess.run(
            [
                sys.executable, str(TOOL),
                "--victim-config", str(self.victim),
                "--open5gs-env", str(self.env),
                "--output-dir", str(output),
                *extra,
            ],
            text=True,
            capture_output=True,
            timeout=20,
        )

    def test_creates_private_three_profile_bundle_without_secret_output(self):
        output = self.root / "bundle"
        victim_before = self.victim.read_bytes()
        env_before = self.env.read_bytes()
        result = self.execute(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.victim.read_bytes(), victim_before)
        self.assertEqual(self.env.read_bytes(), env_before)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)

        expected = {
            "victim.conf", "attacker.conf", "control.conf", "subscriber_db.csv",
            "open5gs.env", "compose.override.yml", "profiles.manifest.json",
        }
        self.assertEqual({path.name for path in output.iterdir()}, expected)
        for path in output.iterdir():
            self.assertFalse(path.is_symlink())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600, path.name)

        rows = list(csv.reader((output / "subscriber_db.csv").read_text().splitlines()))
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(len(row) == 8 for row in rows))
        self.assertEqual([row[0] for row in rows],
                         ["blind-victim", "blind-attacker", "blind-control"])
        self.assertEqual(rows[0][1:], [
            VICTIM_IMSI, VICTIM_KEY, "opc", VICTIM_OPC, "8000", "9", VICTIM_IP,
        ])
        for index in (1, 2):
            self.assertRegex(rows[index][1], r"^00101[0-9]{10}$")
            self.assertRegex(rows[index][2], r"^[0-9a-f]{32}$")
            self.assertEqual(rows[index][3], "opc")
            self.assertRegex(rows[index][4], r"^[0-9a-f]{32}$")
        for column in (1, 2, 4, 7):
            self.assertEqual(len({row[column].lower() for row in rows}), 3)
        self.assertEqual([row[7] for row in rows],
                         [VICTIM_IP, "10.45.1.3", "10.45.1.4"])

        generated_configs = {
            role: (output / f"{role}.conf").read_text() for role in ("attacker", "control")
        }
        generated_configs["victim"] = (output / "victim.conf").read_text()
        for index, role in enumerate(("victim", "attacker", "control")):
            config = generated_configs[role]
            self.assertIn(f'imsi="{rows[index][1]}"', config)
            self.assertIn(f'key="{rows[index][2]}"', config)
            self.assertIn(f'opc="{rows[index][4]}"', config)
            self.assertRegex(config, rf"\bid\s*=\s*{index + 1}\s*;")

        original_lines = self.env.read_text().splitlines()
        generated_lines = (output / "open5gs.env").read_text().splitlines()
        self.assertEqual(len(original_lines), len(generated_lines))
        for before, after in zip(original_lines, generated_lines):
            if before.startswith("SUBSCRIBER_DB="):
                self.assertEqual(after, "SUBSCRIBER_DB=/open5gs/subscriber_db.csv")
            else:
                self.assertEqual(after, before)

        override = (output / "compose.override.yml").read_text()
        self.assertIn(str((output / "subscriber_db.csv").absolute()), override)
        manifest_text = (output / "profiles.manifest.json").read_text()
        manifest = json.loads(manifest_text)
        self.assertEqual(manifest["profile_count"], 3)
        self.assertEqual([row["role"] for row in manifest["profiles"]],
                         ["victim", "attacker", "control"])
        self.assertEqual([row["pdu_session_id"] for row in manifest["profiles"]],
                         [1, 2, 3])

        stdout = result.stdout
        secrets = [value for row in rows for value in (row[1], row[2], row[4], row[7])]
        for value in secrets:
            self.assertNotIn(value, stdout)
            self.assertNotIn(value, manifest_text)
        self.assertNotIn(VICTIM_KEY, (output / "open5gs.env").read_text())

    def test_existing_and_symlink_outputs_fail_closed(self):
        existing = self.root / "existing"
        existing.mkdir()
        marker = existing / "keep"
        marker.write_text("original\n")
        result = self.execute(existing)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(marker.read_text(), "original\n")

        target = self.root / "outside"
        target.mkdir()
        target_marker = target / "keep"
        target_marker.write_text("original\n")
        linked = self.root / "linked"
        linked.symlink_to(target, target_is_directory=True)
        result = self.execute(linked)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(linked.is_symlink())
        self.assertEqual(target_marker.read_text(), "original\n")

    def test_symlink_input_is_rejected(self):
        real = self.victim
        linked = self.root / "victim-link.conf"
        linked.symlink_to(real)
        self.victim = linked
        output = self.root / "bundle"
        result = self.execute(output)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())
        self.assertIn("non-symlink", result.stderr)

    def test_invalid_schema_validation_is_deterministic_and_creates_nothing(self):
        self.env.write_text(self.env.read_text().replace("MNC=01", "MNC=99"))
        output = self.root / "bundle"
        first = self.execute(output)
        second = self.execute(output)
        self.assertEqual(first.returncode, 2)
        self.assertEqual(second.returncode, 2)
        self.assertEqual(first.stderr, second.stderr)
        self.assertFalse(output.exists())
        self.assertNotIn(VICTIM_IMSI, first.stderr)
        self.assertNotIn(VICTIM_KEY, first.stderr)
        self.assertNotIn(VICTIM_OPC, first.stderr)

    def test_custom_mount_source_must_be_absolute_and_is_quoted(self):
        relative = self.execute(self.root / "relative", "--compose-mount-source", "x.csv")
        self.assertEqual(relative.returncode, 2)
        self.assertFalse((self.root / "relative").exists())

        output = self.root / "custom"
        mount = self.root / 'deployed "profiles"' / "subscriber_db.csv"
        result = self.execute(output, "--compose-mount-source", str(mount))
        self.assertEqual(result.returncode, 0, result.stderr)
        override = (output / "compose.override.yml").read_text()
        quoted = re.search(r"source: (.+)", override).group(1)
        self.assertEqual(json.loads(quoted), str(mount.absolute()))

    def test_explicit_cidr_contains_victim_and_prefers_victim_24(self):
        self.env.write_text(
            self.env.read_text().replace("UE_IP_BASE=10.45.0", "UE_IP_BASE=10.45.0.0/16")
        )
        output = self.root / "cidr"
        result = self.execute(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = list(csv.reader((output / "subscriber_db.csv").read_text().splitlines()))
        self.assertEqual([row[7] for row in rows],
                         [VICTIM_IP, "10.45.1.3", "10.45.1.4"])

        self.env.write_text(
            self.env.read_text().replace("UE_IP_BASE=10.45.0.0/16", "UE_IP_BASE=10.45.2.0/24")
        )
        rejected = self.execute(self.root / "outside")
        self.assertEqual(rejected.returncode, 2)
        self.assertFalse((self.root / "outside").exists())
        self.assertIn("inside the UE_IP_BASE network", rejected.stderr)

    def test_nondefault_or_multiple_victim_pdu_sessions_are_rejected(self):
        original = self.victim.read_text()
        self.victim.write_text(original.replace("pdu_sessions=( {", "pdu_sessions=( { id=9;"))
        rejected = self.execute(self.root / "nondefault")
        self.assertEqual(rejected.returncode, 2)
        self.assertFalse((self.root / "nondefault").exists())

        self.victim.write_text(original.replace(
            'pdu_sessions=( { dnn="internet"; nssai_sst=1; } );',
            'pdu_sessions=( { dnn="internet"; nssai_sst=1; }, '
            '{ dnn="internet"; nssai_sst=1; } );',
        ))
        rejected = self.execute(self.root / "multiple")
        self.assertEqual(rejected.returncode, 2)
        self.assertFalse((self.root / "multiple").exists())


if __name__ == "__main__":
    unittest.main()
