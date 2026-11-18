"""Offline lifecycle tests for the p5 Blind DoS raw-evidence hook."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "bin" / "blind-p5-phase"
RAW_NAMES = {
    "attacker_events.jsonl",
    "victim_service.jsonl",
    "target_snapshot_before.json",
    "target_snapshot_after.json",
    "amf.log",
    "cu.log",
    "du.log",
    "ngap.pcap",
    "f1ap.pcap",
    "ground_truth.jsonl",
}


class BlindP5PhaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.trace = self.root / "trace.jsonl"
        self.counter = self.root / "attacker.counter"
        self.absent_conf = self.root / "absent.conf"
        self.victim_cfg = self.root / "victim.conf"
        self.attacker_cfg = self.root / "attacker.conf"
        self.control_cfg = self.root / "control.conf"
        self.uecap = self.root / "uecap.xml"
        for path in (self.victim_cfg, self.attacker_cfg, self.control_cfg, self.uecap):
            path.write_text("fixture\n")

        self.ue = self.root / "fake-ue.py"
        self.ue.write_text(textwrap.dedent(r'''
            #!/usr/bin/env python3
            import fcntl
            import json
            import os
            from pathlib import Path
            import signal
            import sys
            import time

            args = sys.argv[1:]
            def option(name, default=None):
                try:
                    return args[args.index(name) + 1]
                except ValueError:
                    return default

            cfg = Path(option("-O")).name
            base_role = "victim" if cfg.startswith("victim") else "attacker"
            if base_role == "attacker":
                counter = Path(os.environ["FAKE_ATTACKER_COUNTER"])
                with counter.open("a+") as handle:
                    fcntl.flock(handle, fcntl.LOCK_EX)
                    handle.seek(0)
                    value = int(handle.read() or "0") + 1
                    handle.seek(0)
                    handle.truncate()
                    handle.write(str(value))
                role = f"attacker-{value}"
            else:
                role = "victim"

            trace = Path(os.environ["BLIND_TEST_TRACE"])
            def emit(event, **extra):
                with trace.open("a") as output:
                    output.write(json.dumps({"event": event, "role": role,
                                             "pid": os.getpid(), **extra}) + "\n")

            interrupts = 0
            def stop(_signum, _frame):
                global interrupts
                interrupts += 1
                emit("ue_int", count=interrupts)
                if os.environ.get("FAKE_STUBBORN_ROLE") != role and interrupts >= 2:
                    os._exit(int(os.environ.get("FAKE_UE_CLEAN_EXIT", "0")))

            signal.signal(signal.SIGINT, stop)
            def recover(_signum, _frame):
                emit("victim_recovery")
                print("Received Registration Accept", flush=True)
                print("Received PDU Session Establishment Accept", flush=True)
            if base_role == "victim":
                signal.signal(signal.SIGUSR1, recover)
            enable = option("--blind.enable", "0")
            target = option("--blind.target_5g_s_tmsi")
            target_file = option("--blind.target_file")
            run_id = option("--blind.run_id")
            log_file = option("--blind.log_file")
            emit("ue_start", enable=enable, target=target, run_id=run_id,
                 target_file=target_file, log_file=log_file,
                 recovery_mode=option("--blind.recovery_mode", "0"),
                 tun_suffix=option("--blind.tun_suffix"),
                 tx=option("--zmq.[0].tx_channels"),
                 rx=option("--zmq.[0].rx_channels"))
            print(os.environ["FAKE_CREDENTIAL_SENTINEL"], flush=True)
            if base_role == "victim":
                print("Received Registration Accept", flush=True)
                print("Received PDU Session Establishment Accept", flush=True)

            if enable == "1":
                with open(log_file, "x"):
                    pass
                while not Path(target_file).is_file():
                    time.sleep(0.05)
                target = Path(target_file).read_text().strip()
                emit("target_gate_opened", target=target)
                full = int(target[2:], 16)
                common = {"schema": "blind.attacker-event.v1", "run_id": run_id,
                          "ue": 0, "target_5g_s_tmsi": target}
                rows = [
                    {**common, "event": "target_gate_opened"},
                    {**common, "event": "target_msg3_committed",
                     "part1": full & ((1 << 39) - 1), "part2": full >> 39,
                     "claim": "payload_committed_not_air_confirmed"},
                    {**common, "event": "nas_guti_selected", "amf_region_id": 2,
                     "amf_set_id": (full >> 38) & 0x3ff,
                     "amf_pointer": (full >> 32) & 0x3f, "tmsi": full & 0xffffffff},
                    {**common, "event": "rrc_setup_complete_submitted"},
                    {**common, "event": "authentication_request_withheld",
                     "response_submitted": False},
                ]
                with open(log_file, "a") as output:
                    for seq, row in enumerate(rows, 1):
                        row.update(seq=seq, realtime_ns=time.time_ns(),
                                   monotonic_ns=time.monotonic_ns())
                        output.write(json.dumps(row, separators=(",", ":")) + "\n")

            if os.environ.get("FAKE_EARLY_EXIT_ROLE") == role:
                raise SystemExit(7)
            while True:
                time.sleep(0.05)
        ''').lstrip())
        self.ue.chmod(0o755)

        self.hook = self.root / "hook.py"
        self.hook.write_text(textwrap.dedent(r'''
            import json
            import os
            from pathlib import Path
            import signal
            import sys
            import time

            kind = sys.argv[1]
            trace = Path(os.environ["BLIND_TEST_TRACE"])
            def emit(event, **extra):
                with trace.open("a") as output:
                    output.write(json.dumps({"event": event, **extra}) + "\n")

            if os.environ.get("FAKE_BLOCK_HOOK") == kind:
                emit("hook-block", kind=kind)
                time.sleep(60)
            if (os.environ.get("FAKE_LATE_RECOVERY") == "1" and kind == "ping"
                    and os.environ.get("BLIND_SERVICE_PHASE") == "recovery"):
                emit("late-recovery-ping")
                time.sleep(1.2)
            if os.environ.get("FAKE_FAIL_HOOK") == kind:
                emit(kind)
                raise SystemExit(1)
            if kind == "process-clear":
                emit(kind)
                raise SystemExit(1 if os.environ.get("FAKE_PROCESS_CONFLICT") == "1" else 0)
            if kind in {"du-stop", "du-restart", "du-ready", "log-start", "capture-start"}:
                emit(kind)
            elif kind == "endpoint":
                pid = int(os.environ["BLIND_CHILD_PID"])
                os.kill(pid, 0)
                rows = [json.loads(line) for line in trace.read_text().splitlines()]
                if not any(row.get("event") == "ue_start" and row.get("pid") == pid
                           for row in rows):
                    raise SystemExit(1)
                emit("endpoint-ready", role=os.environ["BLIND_ENDPOINT_ROLE"], pid=pid)
            elif kind in {"registration", "tun", "ping"}:
                emit(kind, phase=os.environ["BLIND_SERVICE_PHASE"],
                     victim_pid=int(os.environ["BLIND_VICTIM_PID"]))
                if os.environ.get("FAKE_FAIL_SERVICE") == kind:
                    raise SystemExit(1)
            elif kind == "snapshot":
                phase = os.environ["BLIND_SNAPSHOT_PHASE"]
                victim_log = Path(os.environ["BLIND_VICTIM_LOG_PATH"])
                if not victim_log.is_file():
                    raise SystemExit(1)
                emit("snapshot", phase=phase, victim_log=victim_log.name)
                value = {
                    "schema": "blind.target-snapshot.v1",
                    "run_id": os.environ["BLIND_RUN_ID"],
                    "owner_role": "target_owner_existing",
                    "owner_id": os.environ["VICTIM_ID"],
                    "amf_region_id": int(os.environ["AMF_REGION_ID"]),
                    "target_5g_s_tmsi": "0x0123456789ab",
                    "part1": int("0123456789ab", 16) & ((1 << 39) - 1),
                    "part2": int("0123456789ab", 16) >> 39,
                    "ran_ue_ngap_id": 11, "amf_ue_ngap_id": 22,
                    "captured_realtime_ns": time.time_ns(),
                    "fiveg_guti": "redacted-fixture",
                    "source_sha256": "a" * 64,
                }
                with open(os.environ["BLIND_SNAPSHOT_PATH"], "x") as output:
                    output.write(json.dumps(value) + "\n")
            elif kind == "capture-stop":
                emit(kind)
                Path(os.environ["BLIND_NGAP_PCAP_PATH"]).write_bytes(b"ngap fixture\n")
                Path(os.environ["BLIND_F1AP_PCAP_PATH"]).write_bytes(b"f1 fixture\n")
            elif kind == "log-stop":
                emit(kind)
                for key in ("BLIND_AMF_LOG_PATH", "BLIND_CU_LOG_PATH", "BLIND_DU_LOG_PATH"):
                    Path(os.environ[key]).write_text(f"{key} fixture\n")
            elif kind == "network":
                emit(kind)
                row = {
                    "schema": "blind.network-event.v1",
                    "run_id": os.environ["BLIND_RUN_ID"],
                    "role": "target_owner_existing",
                    "owner_id": os.environ["VICTIM_ID"],
                    "target_5g_s_tmsi": "0x0123456789ab",
                    "event": "observation", "exact_join": False,
                    "realtime_ns": time.time_ns(),
                }
                with open(os.environ["BLIND_NETWORK_EVENTS_PATH"], "x") as output:
                    output.write(json.dumps(row) + "\n")
        ''').lstrip())

        def command(kind):
            return "exec " + shlex.quote(sys.executable) + " " + shlex.quote(str(self.hook)) \
                + " " + shlex.quote(kind)

        self.env = dict(
            os.environ,
            BLIND_CONF=str(self.absent_conf),
            BLIND_MODE="control",
            BLIND_ATTACK_ENABLED="0",
            BLIND_RUN_ID="fixture-control",
            OAI_BLIND_BIN=str(self.ue),
            VICTIM_UE_CFG=str(self.victim_cfg),
            ATTACKER_UE_CFG=str(self.attacker_cfg),
            CONTROL_UE_CFG=str(self.control_cfg),
            UECAP=str(self.uecap),
            VICTIM_ID="victim-fixture",
            AMF_REGION_ID="2",
            BAND="78", DL_FREQ="3489420000", NUMEROLOGY="1", PRB="51",
            DEVICE="fixture-zmq",
            VICTIM_TX_ENDPOINT="tcp://fixture:2101",
            VICTIM_RX_ENDPOINT="tcp://fixture:2100",
            ATTACKER_TX_ENDPOINT="tcp://fixture:2201",
            ATTACKER_RX_ENDPOINT="tcp://fixture:2200",
            PROCESS_CLEAR_CMD=command("process-clear"),
            DU_STOP_CMD=command("du-stop"),
            DU_RESTART_CMD=command("du-restart"),
            DU_READY_CMD=command("du-ready"),
            VICTIM_ENDPOINT_READY_CMD=command("endpoint"),
            ATTACKER_ENDPOINT_READY_CMD=command("endpoint"),
            VICTIM_REGISTRATION_CMD=command("registration"),
            VICTIM_TUN_CMD=command("tun"),
            VICTIM_PING_CMD=command("ping"),
            CU_TARGET_SNAPSHOT_CMD=command("snapshot"),
            CU_LOG_SLICE_START_CMD=command("log-start"),
            CU_LOG_SLICE_STOP_CMD=command("log-stop"),
            CU_CAPTURE_START_CMD=command("capture-start"),
            CU_CAPTURE_STOP_CMD=command("capture-stop"),
            CU_NETWORK_EVENTS_CMD=command("network"),
            USE_SETSID="0",
            DU_SETTLE_S="0",
            DU_READY_TIMEOUT_S="2", ENDPOINT_READY_TIMEOUT_S="2",
            SERVICE_READY_TIMEOUT_S="2",
            OBSERVATION_S="1", OBSERVATION_POLL_S="0.05",
            RECOVERY_TIMEOUT_S="2", LOSS_CONSECUTIVE_PINGS="1", BASELINE_PING_COUNT="1",
            RECOVERY_PING_COUNT="1", TEARDOWN_GRACE_S="1", HOOK_TIMEOUT_S="3",
            BLIND_TEST_TRACE=str(self.trace),
            FAKE_ATTACKER_COUNTER=str(self.counter),
            FAKE_CREDENTIAL_SENTINEL="SUPI-AND-KEY-MUST-NOT-ESCAPE",
        )

    def execute(self, name="run", **overrides):
        run_dir = self.root / name
        run_dir.mkdir()
        for path in (self.trace, self.counter):
            path.unlink(missing_ok=True)
        env = dict(self.env, BLIND_RUN_DIR=str(run_dir))
        env.update({key: str(value) for key, value in overrides.items()})
        result = subprocess.run(
            ["bash", str(PHASE)], env=env, text=True,
            capture_output=True, timeout=20,
        )
        return result, run_dir

    def events(self):
        if not self.trace.exists():
            return []
        return [json.loads(line) for line in self.trace.read_text().splitlines()]

    @staticmethod
    def first(events, event, role=None, **fields):
        for index, row in enumerate(events):
            if row.get("event") == event and (role is None or row.get("role") == role) \
                    and all(row.get(key) == value for key, value in fields.items()):
                return index
        raise AssertionError(f"missing event={event!r} role={role!r} fields={fields!r}")

    def test_default_control_lifecycle_raw_files_and_clean_teardown(self):
        result, run_dir = self.execute()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual({path.name for path in run_dir.iterdir()}, RAW_NAMES)
        self.assertEqual((run_dir / "attacker_events.jsonl").read_text(), "")
        self.assertNotIn(self.env["FAKE_CREDENTIAL_SENTINEL"], result.stdout + result.stderr)

        events = self.events()
        victim_starts = [index for index, row in enumerate(events)
                         if row.get("event") == "ue_start" and row.get("role") == "victim"]
        self.assertEqual(len(victim_starts), 1)
        victim_start = victim_starts[0]
        attacker_start = self.first(events, "ue_start", "attacker-1", enable="1")
        baseline_ping = self.first(events, "ping", phase="baseline")
        snapshot_before = self.first(events, "snapshot", phase="before")
        self.assertEqual(events[snapshot_before]["victim_log"], "victim.log")
        recovery_ping = self.first(events, "ping", phase="recovery")
        attacker_stop = self.first(events, "ue_int", "attacker-1")
        self.assertLess(baseline_ping, snapshot_before)
        self.assertLess(attacker_start, snapshot_before)
        self.assertLess(snapshot_before, recovery_ping)
        self.assertLess(recovery_ping, attacker_stop)
        self.assertFalse(any(row["event"] == "broker_start" for row in events))

        victim_pid = events[victim_start]["pid"]
        ue_starts = [row for row in events if row["event"] == "ue_start"]
        self.assertEqual([row["tun_suffix"] for row in ue_starts], ["1", "1"])
        self.assertEqual([row["recovery_mode"] for row in ue_starts], ["1", "0"])
        baseline_pids = {row["victim_pid"] for row in events if row["event"] in
                         {"registration", "tun", "ping"}
                         and row["phase"] == "baseline"}
        recovery_pids = {row["victim_pid"] for row in events if row["event"] in
                         {"registration", "tun", "ping"}
                         and row["phase"] == "recovery"}
        self.assertEqual(baseline_pids, {victim_pid})
        self.assertEqual(recovery_pids, {victim_pid})
        self.assertEqual(len([row for row in events if row["event"] == "ue_int"
                              and row["role"] == "victim"]), 2)
        self.assertEqual(len([row for row in events if row["event"] == "ue_int"
                              and row["role"].startswith("attacker-")]), 2)
        self.assertFalse(any(row["event"] == "target_gate_opened" for row in events))
        truth = [json.loads(line) for line in
                 (run_dir / "ground_truth.jsonl").read_text().splitlines()]
        self.assertFalse(any(row["event"] in {"process_crash", "forced_kill"}
                             for row in truth))

    def test_external_ran_keeps_du_running_and_honors_readiness_gate(self):
        ready = self.root / "normal.ready"
        ran_ready = self.root / "ran.ready"
        attack_ready = self.root / "attack.ready"
        attack_done = self.root / "attack.done"
        release = self.root / "attack.release"
        ready.write_text("")
        ran_ready.write_text("")
        release.write_text("")
        result, _ = self.execute(
            "external-ran", BLIND_MANAGE_DU="0", SAME_CELL_READY_FILE=str(ready),
            SAME_CELL_PRESTART="1", SAME_CELL_RAN_READY_FILE=str(ran_ready),
            SAME_CELL_ATTACK_READY_FILE=str(attack_ready),
            SAME_CELL_ATTACK_DONE_FILE=str(attack_done),
            SAME_CELL_RELEASE_FILE=str(release),
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        events = self.events()
        names = [row["event"] for row in events]
        self.assertIn("du-ready", names)
        self.assertNotIn("du-stop", names)
        self.assertNotIn("du-restart", names)
        self.assertTrue(attack_ready.is_file())
        self.assertTrue(attack_done.is_file())
        self.assertEqual([row["tun_suffix"] for row in events
                          if row["event"] == "ue_start"], ["0", "1"])

    def test_attack_passes_exact_target_run_and_exclusive_log_arguments(self):
        result, run_dir = self.execute(
            "attack", BLIND_MODE="attack", BLIND_ATTACK_ENABLED="1",
            BLIND_RUN_ID="fixture-attack",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        starts = [row for row in self.events() if row["event"] == "ue_start"]
        attacker = next(row for row in starts if row["role"] == "attacker-1")
        self.assertEqual(attacker["enable"], "1")
        self.assertIsNone(attacker["target"])
        self.assertTrue(Path(attacker["target_file"]).is_absolute())
        self.assertEqual(attacker["run_id"], "fixture-attack")
        self.assertEqual(Path(attacker["log_file"]),
                         (run_dir / "attacker_events.jsonl").resolve())
        gate = next(row for row in self.events() if row["event"] == "target_gate_opened")
        self.assertEqual(gate["role"], "attacker-1")
        self.assertEqual(gate["target"], "0x0123456789ab")
        rows = [json.loads(line) for line in
                (run_dir / "attacker_events.jsonl").read_text().splitlines()]
        self.assertEqual([row["event"] for row in rows], [
            "target_gate_opened", "target_msg3_committed", "nas_guti_selected",
            "rrc_setup_complete_submitted", "authentication_request_withheld",
        ])
        recovery = [row for row in self.events() if row["event"] == "victim_recovery"]
        self.assertEqual(len(recovery), 1)

    def test_recovery_signal_targets_only_the_victim_main_process(self):
        source = PHASE.read_text()
        self.assertIn('kill -USR1 -- "${PIDS[$VICTIM_INDEX]}"', source)
        self.assertNotIn('signal_child "$VICTIM_INDEX" USR1', source)

    def test_attack_is_fail_closed_without_explicit_enable(self):
        result, run_dir = self.execute("disabled-attack", BLIND_MODE="attack")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("explicit enable=1", result.stderr)
        self.assertEqual(list(run_dir.iterdir()), [])
        self.assertEqual(self.events(), [])

    def test_missing_required_hook_fails_before_actions_or_artifacts(self):
        result, run_dir = self.execute("missing-hook", CU_CAPTURE_STOP_CMD="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CU_CAPTURE_STOP_CMD is required", result.stderr)
        self.assertEqual(list(run_dir.iterdir()), [])
        self.assertEqual(self.events(), [])

    def test_existing_symlink_artifact_is_not_followed_or_overwritten(self):
        run_dir = self.root / "symlink"
        run_dir.mkdir()
        outside = self.root / "outside"
        outside.write_text("keep\n")
        (run_dir / "victim_service.jsonl").symlink_to(outside)
        env = dict(self.env, BLIND_RUN_DIR=str(run_dir))
        result = subprocess.run(
            ["bash", str(PHASE)], env=env, text=True,
            capture_output=True, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("raw artifact already exists", result.stderr)
        self.assertEqual(outside.read_text(), "keep\n")
        self.assertEqual(self.events(), [])

    def test_existing_process_check_fails_before_raw_creation(self):
        result, run_dir = self.execute("process-conflict", FAKE_PROCESS_CONFLICT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("conflicting process", result.stderr)
        self.assertEqual(list(run_dir.iterdir()), [])
        self.assertEqual([row["event"] for row in self.events()], ["process-clear"])

    def test_forced_kill_is_preserved_in_ground_truth(self):
        result, run_dir = self.execute(
            "forced", BLIND_MODE="attack", BLIND_ATTACK_ENABLED="1",
            BLIND_RUN_ID="fixture-forced", FAKE_STUBBORN_ROLE="attacker-1",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        truth = [json.loads(line) for line in
                 (run_dir / "ground_truth.jsonl").read_text().splitlines()]
        forced = [row for row in truth if row["event"] == "forced_kill"]
        self.assertEqual(len(forced), 1)
        self.assertEqual(forced[0]["role"], "infrastructure")
        self.assertEqual(forced[0]["process_role"], "attacker")
        self.assertFalse(forced[0]["exact_join"])

    def test_oai_sigint_exit_two_is_clean_teardown(self):
        result, run_dir = self.execute("exit-two", FAKE_UE_CLEAN_EXIT="2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        truth = [json.loads(line) for line in
                 (run_dir / "ground_truth.jsonl").read_text().splitlines()]
        self.assertFalse(any(row["event"] == "process_crash" for row in truth))

    def test_recovery_success_after_deadline_is_not_accepted(self):
        result, run_dir = self.execute(
            "late-recovery", FAKE_LATE_RECOVERY="1", RECOVERY_TIMEOUT_S="1",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        rows = [json.loads(line) for line in
                (run_dir / "victim_service.jsonl").read_text().splitlines()]
        after = [row for row in rows if row["phase"] == "after"]
        self.assertEqual(len(after), 1)
        self.assertFalse(after[0]["ping_ok"])

    def test_early_child_exit_is_recorded_as_crash(self):
        result, run_dir = self.execute(
            "crash", BLIND_MODE="attack", BLIND_ATTACK_ENABLED="1",
            BLIND_RUN_ID="fixture-crash", FAKE_EARLY_EXIT_ROLE="attacker-1",
        )
        self.assertNotEqual(result.returncode, 0)
        truth_path = run_dir / "ground_truth.jsonl"
        self.assertTrue(truth_path.is_file())
        truth = [json.loads(line) for line in truth_path.read_text().splitlines()]
        crashes = [row for row in truth if row["event"] == "process_crash"]
        self.assertEqual(len(crashes), 1)
        self.assertEqual(crashes[0]["process_role"], "attacker")

    def test_partial_collection_start_is_stopped_on_failure(self):
        result, _ = self.execute("capture-start-failed", FAKE_FAIL_HOOK="capture-start")
        self.assertNotEqual(result.returncode, 0)
        names = [row["event"] for row in self.events()]
        self.assertIn("log-start", names)
        self.assertIn("log-stop", names)
        self.assertIn("capture-stop", names)

    def test_blocked_hook_times_out_without_leaving_radio_children(self):
        result, _ = self.execute(
            "blocked-hook", FAKE_BLOCK_HOOK="ping", HOOK_TIMEOUT_S="1",
            SERVICE_READY_TIMEOUT_S="1",
        )
        self.assertNotEqual(result.returncode, 0)
        starts = [row for row in self.events() if row["event"] == "ue_start"]
        self.assertTrue(starts)
        for row in starts:
            with self.assertRaises(ProcessLookupError):
                os.kill(row["pid"], 0)

    def test_external_term_cleans_active_hook_radio_and_collectors(self):
        run_dir = self.root / "external-term"
        run_dir.mkdir()
        env = dict(
            self.env,
            BLIND_RUN_DIR=str(run_dir),
            FAKE_BLOCK_HOOK="ping",
            HOOK_TIMEOUT_S="60",
            SERVICE_READY_TIMEOUT_S="60",
        )
        process = subprocess.Popen(
            ["bash", str(PHASE)], env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        for _ in range(100):
            if self.trace.exists() and any(
                    json.loads(line).get("event") == "hook-block"
                    for line in self.trace.read_text().splitlines()):
                break
            time.sleep(0.05)
        else:
            process.kill()
            self.fail("phase did not reach the blocked hook")
        process.terminate()
        stdout, stderr = process.communicate(timeout=12)
        self.assertNotEqual(process.returncode, 0, stdout + stderr)
        events = self.events()
        starts = [row for row in events if row["event"] == "ue_start"]
        for row in starts:
            with self.assertRaises(ProcessLookupError):
                os.kill(row["pid"], 0)
        names = [row["event"] for row in events]
        self.assertIn("capture-stop", names)
        self.assertIn("log-stop", names)


if __name__ == "__main__":
    unittest.main()
