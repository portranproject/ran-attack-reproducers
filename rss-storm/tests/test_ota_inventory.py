"""Fail-closed checks for the shielded-OTA G0 inventory."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "analysis" / "validate_ota_inventory.py"
EXAMPLE = ROOT / "conf" / "ota-inventory.example.json"


def endpoint(alias, role, serial_hash):
    return {
        "alias": alias,
        "role": role,
        "host_alias": f"{role}-host",
        "model": "team-sdr-model",
        "serial_hash": serial_hash,
        "rf_port": "TX/RX",
        "channel": 0,
        "antenna_alias": f"{alias}-antenna",
        "backend": "team-backend",
        "driver_version": "1.2.3",
        "firmware_version": "4.5.6",
        "clock_source": "external",
        "time_source": "external",
        "master_clock_rate_hz": 30_720_000,
        "sample_rate_hz": 23_040_000,
        "tx_gain_max_db": 10,
        "rx_gain_max_db": 20,
    }


def inventory():
    return {
        "schema_version": 1,
        "lab_id": "shielded-lab",
        "equipment_owned_by_team": True,
        "subscriber_profiles_owned_by_team": True,
        "physical_crosscheck_complete": True,
        "endpoints": [
            endpoint("du-sdr", "du", "a" * 64),
            endpoint("attack-sdr", "attack_ue", "b" * 64),
            endpoint("witness-sdr", "witness_ue", "c" * 64),
        ],
        "rf_paths": [
            {
                "alias": "du-to-attack",
                "from_endpoint": "du-sdr",
                "to_endpoint": "attack-sdr",
                "diagram_ref": "restricted:diagram-v1",
                "components": [
                    {"alias": "attack-cable", "type": "cable", "attenuation_db": 2},
                    {"alias": "attack-pad", "type": "attenuator", "attenuation_db": 38},
                ],
                "total_attenuation_db": 40,
            },
            {
                "alias": "du-to-witness",
                "from_endpoint": "du-sdr",
                "to_endpoint": "witness-sdr",
                "diagram_ref": "restricted:diagram-v1",
                "components": [
                    {"alias": "witness-cable", "type": "cable", "attenuation_db": 2},
                    {"alias": "witness-pad", "type": "attenuator", "attenuation_db": 38},
                ],
                "total_attenuation_db": 40,
            },
        ],
        "leakage": {
            "threshold": -80,
            "unit": "dBm",
            "instrument_alias": "spectrum-analyzer",
            "measurement_location": "shield-reference-point",
            "procedure_ref": "restricted:leakage-procedure-v1",
        },
        "subscribers": {
            "attack_alias": "subscriber-attack",
            "witness_alias": "subscriber-witness",
            "distinct_profiles": True,
        },
        "witness": {
            "endpoint_alias": "witness-sdr",
            "process_host_alias": "witness-host",
            "independent_sdr": True,
            "independent_process": True,
            "independent_rf_path": True,
        },
        "approvals": [
            {"reviewer_alias": "reviewer-a", "approved_at": "2026-10-30T10:00:00+09:00"},
            {"reviewer_alias": "reviewer-b", "approved_at": "2026-10-30T10:05:00+09:00"},
        ],
    }


class OtaInventoryTests(unittest.TestCase):
    def run_validator(self, data=None, source=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            if source is not None:
                path.write_text(Path(source).read_text())
            else:
                path.write_text(json.dumps(data))
            return subprocess.run(
                [sys.executable, str(VALIDATOR), str(path)],
                text=True,
                capture_output=True,
                check=False,
            )

    def assert_invalid(self, data, message):
        result = self.run_validator(data)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr)
        self.assertNotIn("structure complete", result.stdout)

    def test_complete_manifest_passes_but_does_not_claim_hardware_gate(self):
        result = self.run_validator(inventory())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("structure complete", result.stdout)
        self.assertIn("does not prove the physical two-person cross-check", result.stdout)
        self.assertIn("G1 TX-off", result.stdout)

    def test_example_is_intentionally_fail_closed(self):
        result = self.run_validator(source=EXAMPLE)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("physical_crosscheck_complete", result.stderr)
        self.assertNotIn("structure complete", result.stdout)

    def test_missing_placeholder_duplicate_and_false_safety_inputs_fail(self):
        cases = []
        missing = inventory()
        del missing["leakage"]
        cases.append((missing, "$.leakage: missing"))
        placeholder = inventory()
        placeholder["endpoints"][0]["model"] = "TBD"
        cases.append((placeholder, "model: needs a concrete"))
        duplicate = inventory()
        duplicate["endpoints"][2]["serial_hash"] = "a" * 64
        cases.append((duplicate, "duplicate physical device"))
        shared_subscriber = inventory()
        shared_subscriber["subscribers"]["witness_alias"] = "subscriber-attack"
        cases.append((shared_subscriber, "aliases must differ"))
        shared_witness = inventory()
        shared_witness["witness"]["independent_rf_path"] = False
        cases.append((shared_witness, "independent_rf_path: must be true"))
        bad_sum = inventory()
        bad_sum["rf_paths"][0]["total_attenuation_db"] = 39
        cases.append((bad_sum, "does not match component sum"))
        for data, message in cases:
            with self.subTest(message=message):
                self.assert_invalid(data, message)

    def test_secret_field_is_rejected_without_echoing_the_value(self):
        data = inventory()
        data["endpoints"][1]["opc"] = "do-not-print-this-secret"
        result = self.run_validator(data)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("secret or raw identifier keys are forbidden", result.stderr)
        self.assertNotIn("do-not-print-this-secret", result.stdout + result.stderr)
        self.assertNotIn("structure complete", result.stdout)

    def test_two_distinct_timezone_aware_approvals_are_required(self):
        one = inventory()
        one["approvals"] = one["approvals"][:1]
        self.assert_invalid(one, "needs at least 2 item")
        duplicate = inventory()
        duplicate["approvals"][1]["reviewer_alias"] = "reviewer-a"
        self.assert_invalid(duplicate, "reviewer must be distinct")
        no_timezone = inventory()
        no_timezone["approvals"][0]["approved_at"] = "2026-10-30T10:00:00"
        self.assert_invalid(no_timezone, "timestamp with timezone")


if __name__ == "__main__":
    unittest.main()
