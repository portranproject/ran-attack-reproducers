"""Offline contracts for blind-run and blind-campaign; no radio is started."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "bin" / "blind-run"
CAMPAIGN = ROOT / "bin" / "blind-campaign"


class BlindRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stubs = self.root / "stubs"
        self.stubs.mkdir()
        self.runs = self.root / "runs"
        self.trace = self.root / "trace"
        self.absent_conf = self.root / "absent.conf"

        self.flock = self.stub("flock", "#!/bin/sh\nexit 0\n")
        self.timeout = self.stub(
            "timeout", "#!/bin/sh\nshift 3\nexec \"$@\"\n"
        )
        self.scanner = self.root / "scanner.py"
        self.scanner.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('sensitive-artifact-check: ok (fixture)')\n"
        )
        self.scanner.chmod(0o755)

        self.phase = self.root / "phase.py"
        self.phase.write_text(textwrap.dedent(r'''
            import json
            import os
            from pathlib import Path

            out = Path(os.environ["BLIND_RUN_DIR"])
            mode = os.environ["BLIND_MODE"]
            run_id = os.environ["BLIND_RUN_ID"]
            trace = Path(os.environ["BLIND_TEST_TRACE"])
            with trace.open("a") as handle:
                handle.write(f"{mode}|{run_id}\n")
            if os.environ.get("FAKE_PHASE_EXIT") == mode:
                raise SystemExit(7)

            target = "0x0123456789ab"
            changed = "0x0123456789ac"
            full = int(target, 16)
            t0 = 1_000_000_000
            snapshot = {
                "schema": "blind.target-snapshot.v1", "run_id": run_id,
                "owner_role": "target_owner_existing", "owner_id": "victim",
                "target_5g_s_tmsi": target, "part1": full & ((1 << 39) - 1),
                "part2": full >> 39, "ran_ue_ngap_id": 11,
                "amf_ue_ngap_id": 22, "fiveg_guti": "fixture-guti",
                "source_sha256": "a" * 64,
            }
            before = dict(snapshot, captured_realtime_ns=t0)
            after_target = changed if os.environ.get("FAKE_TARGET_CHANGED") == "1" else target
            after_full = int(after_target, 16)
            after = dict(snapshot, target_5g_s_tmsi=after_target,
                         part1=after_full & ((1 << 39) - 1), part2=after_full >> 39,
                         captured_realtime_ns=t0 + 200)

            attack_ok = mode == "attack" and os.environ.get("FAKE_VALID_FAILURE_MODE") != mode
            service = []
            for timestamp in (t0 - 100, t0 - 90):
                service.append({"schema": "blind.victim-service.v1", "run_id": run_id,
                                "victim_id": "victim", "phase": "before",
                                "registration": True, "pdu_session": True,
                                "ping_ok": True, "realtime_ns": timestamp})
            for index in range(5):
                service.append({"schema": "blind.victim-service.v1", "run_id": run_id,
                                "victim_id": "victim", "phase": "during",
                                "registration": not attack_ok, "pdu_session": not attack_ok,
                                "ping_ok": not attack_ok, "realtime_ns": t0 + 30 + index})
            for timestamp in (t0 + 100, t0 + 110):
                service.append({"schema": "blind.victim-service.v1", "run_id": run_id,
                                "victim_id": "victim", "phase": "after",
                                "registration": True, "pdu_session": True,
                                "ping_ok": True, "realtime_ns": timestamp})

            attacker = []
            if mode == "attack":
                attacker.append({
                    "schema": "blind.attacker-event.v1", "run_id": run_id,
                    "seq": 1, "ue": 0, "realtime_ns": t0 + 10,
                    "monotonic_ns": 10, "event": "target_msg3_committed",
                    "target_5g_s_tmsi": target,
                    "part1": full & ((1 << 39) - 1), "part2": full >> 39,
                    "claim": "payload_committed_not_air_confirmed",
                })

            set_index = int(os.environ.get("BLIND_INTERNAL_SET_INDEX", "0"))
            try_index = int(os.environ.get("BLIND_INTERNAL_TRY_INDEX", "0"))
            infra = (os.environ.get("FAKE_INFRA_MODE") == mode
                     and int(os.environ.get("FAKE_INFRA_SET", str(set_index))) == set_index
                     and try_index <= int(os.environ.get("FAKE_INFRA_TRIES", "0")))
            network = []
            if attack_ok:
                network.append({
                    "schema": "blind.network-event.v1", "run_id": run_id,
                    "role": "attacker_new", "owner_id": "attacker-new",
                    "target_5g_s_tmsi": target, "event": "identity_reached",
                    "exact_join": True, "realtime_ns": t0 + 19,
                })
                network.append({
                    "schema": "blind.network-event.v1", "run_id": run_id,
                    "role": "target_owner_existing", "owner_id": "victim",
                    "target_5g_s_tmsi": target, "event": "binding_changed",
                    "exact_join": True, "ran_ue_ngap_id": 11,
                    "amf_ue_ngap_id": 22, "realtime_ns": t0 + 20,
                })
            else:
                network.append({
                    "schema": "blind.network-event.v1", "run_id": run_id,
                    "role": "target_owner_existing", "owner_id": "victim",
                    "target_5g_s_tmsi": target, "event": "observation",
                    "exact_join": False, "realtime_ns": t0 + 20,
                })
            if infra:
                network.append({
                    "schema": "blind.network-event.v1", "run_id": run_id,
                    "role": "infrastructure", "event": "process_crash",
                    "exact_join": False, "process_role": "fixture",
                    "realtime_ns": t0 + 25,
                })

            def jsonl(rows):
                return "".join(json.dumps(row) + "\n" for row in rows)

            files = {
                "attacker_events.jsonl": jsonl(attacker),
                "victim_service.jsonl": jsonl(service),
                "target_snapshot_before.json": json.dumps(before) + "\n",
                "target_snapshot_after.json": json.dumps(after) + "\n",
                "amf.log": "amf fixture\n", "cu.log": "cu fixture\n",
                "du.log": "du fixture\n", "ngap.pcap": "ngap fixture\n",
                "f1ap.pcap": "f1ap fixture\n", "ground_truth.jsonl": jsonl(network),
            }
            skip = os.environ.get("FAKE_SKIP_EVIDENCE")
            for name, value in files.items():
                if name != skip:
                    (out / name).write_text(value)
            if os.environ.get("FAKE_MUTATE_CONF") == "1":
                with open(os.environ["BLIND_CONF"], "a") as handle:
                    handle.write("# changed\n")
        ''').lstrip())

        self.verifier = self.root / "verify.py"
        self.verifier.write_text(textwrap.dedent(f'''
            import os
            from pathlib import Path
            import subprocess
            import sys

            result = subprocess.run([
                sys.executable, {str(ROOT / "analysis" / "export_labels.py")!r},
                os.environ["BLIND_RUN_DIR"], os.environ["BLIND_HOOK_RESULT"],
            ])
            if result.returncode:
                raise SystemExit(result.returncode)
            if os.environ.get("FAKE_MODIFY_RAW") == "1":
                with (Path(os.environ["BLIND_RUN_DIR"]) / "ground_truth.jsonl").open("a") as handle:
                    handle.write("{{}}\\n")
        ''').lstrip())

        self.env = dict(
            os.environ,
            BLIND_CONF=str(self.absent_conf),
            BLIND_RUN_ROOT=str(self.runs),
            BLIND_LOCK_FILE=str(self.root / "lock"),
            FLOCK_BIN=str(self.flock),
            TIMEOUT_BIN=str(self.timeout),
            PHASE_CMD="exec " + shlex.quote(sys.executable) + " " + shlex.quote(str(self.phase)),
            VERIFY_CMD="exec " + shlex.quote(sys.executable) + " " + shlex.quote(str(self.verifier)),
            ARTIFACT_SCANNER=str(self.scanner),
            CLOCK_SYNC_METHOD="fixture",
            CLOCK_OFFSET_NS="0",
            CLOCK_UNCERTAINTY_NS="1",
            MAX_CLOCK_UNCERTAINTY_NS="10",
            CLOCK_EVIDENCE_SHA256="0" * 64,
            LAB_INVENTORY_SHA256="3" * 64,
            VICTIM_PROFILE_FINGERPRINT="1" * 64,
            ATTACKER_PROFILE_FINGERPRINT="2" * 64,
            BLIND_TEST_TRACE=str(self.trace),
        )

    def stub(self, name, content):
        path = self.stubs / name
        path.write_text(content)
        path.chmod(0o755)
        return path

    def execute(self, script, *args, timeout=90, **overrides):
        env = dict(self.env, **{key: str(value) for key, value in overrides.items()})
        return subprocess.run(
            ["bash", str(script), *args], env=env, text=True,
            capture_output=True, timeout=timeout,
        )

    def load(self, *parts):
        return json.loads(self.runs.joinpath(*parts).read_text())

    def test_single_run_defaults_to_control_and_attack_requires_explicit_enable(self):
        control = self.execute(RUN, "-n", "single-control")
        self.assertEqual(control.returncode, 0, control.stderr + control.stdout)
        stopped = self.load("single-control", "run_stop.json")
        self.assertEqual(stopped["classification"], "passed")
        manifest = self.load("single-control", "evidence_manifest.json")
        self.assertEqual(manifest["classification"], "passed")
        self.assertEqual(stopped["mode"], "control")

        attack = self.execute(RUN, "attack", "-n", "single-attack")
        self.assertEqual(attack.returncode, 2)
        self.assertIn("explicit -e 1", attack.stderr)
        self.assertFalse((self.runs / "single-attack").exists())

    def test_run_id_may_contain_uppercase_o_as_the_second_character(self):
        result = self.execute(RUN, "-n", "aO-valid")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.load("aO-valid", "run_stop.json")["run_id"], "aO-valid")

    def test_campaign_requires_explicit_attack_enable_before_artifacts(self):
        result = self.execute(CAMPAIGN, "-n", "safe-default")
        self.assertEqual(result.returncode, 2)
        self.assertIn("pass -e 1 explicitly", result.stderr)
        self.assertFalse(self.runs.exists())

    def test_existing_and_symlink_run_are_never_overwritten(self):
        first = self.execute(RUN, "-n", "saved")
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        original = (self.runs / "saved" / "run_stop.json").read_text()

        second = self.execute(RUN, "-n", "saved")
        self.assertEqual(second.returncode, 2)
        self.assertIn("never overwritten", second.stderr)
        self.assertEqual((self.runs / "saved" / "run_stop.json").read_text(), original)

        (self.runs / "linked").symlink_to(self.runs / "saved", target_is_directory=True)
        linked = self.execute(RUN, "-n", "linked")
        self.assertEqual(linked.returncode, 2)
        self.assertIn("never overwritten", linked.stderr)
        self.assertTrue((self.runs / "linked").is_symlink())

    def test_missing_evidence_cannot_be_turned_into_success_by_verifier(self):
        result = self.execute(
            RUN, "attack", "-e", "1", "-n", "missing-evidence",
            FAKE_SKIP_EVIDENCE="ngap.pcap",
        )
        self.assertEqual(result.returncode, 20, result.stderr + result.stdout)
        stopped = self.load("missing-evidence", "run_stop.json")
        self.assertEqual(stopped["classification"], "infrastructure-invalid")
        self.assertEqual(stopped["reason"], "required_evidence_missing")

    def test_verifier_may_not_modify_raw_evidence(self):
        result = self.execute(
            RUN, "attack", "-e", "1", "-n", "mutating-verifier",
            FAKE_MODIFY_RAW="1",
        )
        self.assertEqual(result.returncode, 20, result.stderr + result.stdout)
        stopped = self.load("mutating-verifier", "run_stop.json")
        self.assertEqual(stopped["reason"], "verifier_modified_raw_evidence")

    def test_sensitive_artifact_scan_failure_cannot_pass(self):
        scanner = self.root / "failing-scanner.py"
        scanner.write_text("raise SystemExit(1)\n")
        result = self.execute(
            RUN, "attack", "-e", "1", "-n", "scanner-failed",
            ARTIFACT_SCANNER=str(scanner),
        )
        self.assertEqual(result.returncode, 20, result.stderr + result.stdout)
        stopped = self.load("scanner-failed", "run_stop.json")
        self.assertEqual(stopped["reason"], "sensitive_artifact_scan_failed")

    def test_target_identity_change_is_infrastructure_invalid(self):
        result = self.execute(
            RUN, "attack", "-e", "1", "-n", "target-changed",
            FAKE_TARGET_CHANGED="1",
        )
        self.assertEqual(result.returncode, 20, result.stderr + result.stdout)
        stopped = self.load("target-changed", "run_stop.json")
        self.assertEqual(stopped["reason"], "target_identity_changed")

    def test_equal_subscriber_fingerprints_fail_before_artifacts(self):
        result = self.execute(
            RUN, "-n", "same-subscriber",
            ATTACKER_PROFILE_FINGERPRINT="1" * 64,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("must be distinct", result.stderr)
        self.assertFalse(self.runs.exists())

    def test_configuration_change_invalidates_the_run(self):
        conf = self.root / "blind.conf"
        conf.write_text("# fixed before run\n")
        result = self.execute(
            RUN, "-n", "changed-config", BLIND_CONF=str(conf), FAKE_MUTATE_CONF="1",
        )
        self.assertEqual(result.returncode, 20, result.stderr + result.stdout)
        stopped = self.load("changed-config", "run_stop.json")
        self.assertEqual(stopped["reason"], "configuration_changed")

    def test_campaign_defaults_to_three_and_accepts_exact_ten(self):
        default = self.execute(CAMPAIGN, "-e", "1", "-n", "campaign-three")
        self.assertEqual(default.returncode, 0, default.stderr + default.stdout)
        result = self.load("campaign-three", "campaign_result.json")
        self.assertEqual((result["required_sets"], result["passed_sets"]), (3, 3))
        events = (self.runs / "campaign-three" / "campaign_events.jsonl").read_text().splitlines()
        self.assertEqual(len(events), 6)

        ten = self.execute(
            CAMPAIGN, "-e", "1", "-n", "campaign-ten", "-R", "10", timeout=180,
        )
        self.assertEqual(ten.returncode, 0, ten.stderr + ten.stdout)
        result = self.load("campaign-ten", "campaign_result.json")
        self.assertEqual((result["required_sets"], result["passed_sets"]), (10, 10))
        events = (self.runs / "campaign-ten" / "campaign_events.jsonl").read_text().splitlines()
        self.assertEqual(len(events), 20)

    def test_valid_failure_is_not_retried_or_replaced(self):
        result = self.execute(
            CAMPAIGN, "-e", "1", "-n", "valid-failure",
            FAKE_VALID_FAILURE_MODE="attack",
        )
        self.assertEqual(result.returncode, 10, result.stderr + result.stdout)
        verdict = self.load("valid-failure", "campaign_result.json")
        self.assertEqual(verdict["status"], "valid-failure")
        self.assertEqual(verdict["failed_set"], 1)
        events = [json.loads(line) for line in
                  (self.runs / "valid-failure" / "campaign_events.jsonl").read_text().splitlines()]
        self.assertEqual([(row["mode"], row["try_index"]) for row in events],
                         [("control", 1), ("attack", 1)])

    def test_only_infrastructure_invalid_is_retried(self):
        result = self.execute(
            CAMPAIGN, "-e", "1", "-n", "infra-retry",
            FAKE_INFRA_MODE="attack", FAKE_INFRA_SET="1", FAKE_INFRA_TRIES="1",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        events = [json.loads(line) for line in
                  (self.runs / "infra-retry" / "campaign_events.jsonl").read_text().splitlines()]
        self.assertEqual(len(events), 7)
        self.assertEqual(
            [(row["mode"], row["try_index"], row["classification"]) for row in events[:3]],
            [("control", 1, "passed"),
             ("attack", 1, "infrastructure-invalid"),
             ("attack", 2, "passed")],
        )

    def test_infrastructure_retry_exhaustion_stops_campaign(self):
        result = self.execute(
            CAMPAIGN, "-e", "1", "-n", "infra-exhausted",
            FAKE_INFRA_MODE="attack", FAKE_INFRA_SET="1", FAKE_INFRA_TRIES="9",
        )
        self.assertEqual(result.returncode, 20, result.stderr + result.stdout)
        verdict = self.load("infra-exhausted", "campaign_result.json")
        self.assertEqual(verdict["status"], "infrastructure-invalid")
        events = (self.runs / "infra-exhausted" / "campaign_events.jsonl").read_text().splitlines()
        self.assertEqual(len(events), 3)

    def test_repetition_validation_happens_before_artifact_creation(self):
        for value in ("2", "101", "not-a-number"):
            with self.subTest(value=value):
                result = self.execute(
                    CAMPAIGN, "-e", "1", "-n", "invalid-repetitions", "-R", value,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("must be 3..100", result.stderr)
                self.assertFalse(self.runs.exists())

    def test_existing_campaign_symlink_is_never_followed(self):
        target = self.root / "outside"
        target.mkdir()
        marker = target / "keep"
        marker.write_text("original\n")
        self.runs.mkdir()
        (self.runs / "linked-campaign").symlink_to(target, target_is_directory=True)

        result = self.execute(
            CAMPAIGN, "-e", "1", "-n", "linked-campaign",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("never overwritten", result.stderr)
        self.assertEqual(marker.read_text(), "original\n")
        self.assertFalse((target / "campaign.json").exists())

    def test_symlink_run_root_is_rejected(self):
        target = self.root / "outside-root"
        target.mkdir()
        self.runs.symlink_to(target, target_is_directory=True)
        result = self.execute(RUN, "-n", "must-not-exist")
        self.assertEqual(result.returncode, 2)
        self.assertIn("run root must not be a symlink", result.stderr)
        self.assertFalse((target / "must-not-exist").exists())


if __name__ == "__main__":
    unittest.main()
