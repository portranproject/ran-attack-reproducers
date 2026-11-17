import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "workloads" / "normal-ue" / "bin" / "same-cell-run"


class SameCellContractTests(unittest.TestCase):
    def test_help_lists_the_same_cell_live_protocol_modules(self):
        result = subprocess.run([str(SCRIPT), "--help"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("same-cell-run start", result.stdout)
        self.assertIn("same-cell-run run", result.stdout)
        self.assertIn("same-cell-run status", result.stdout)
        self.assertIn("same-cell-run stop", result.stdout)
        self.assertIn("blind|uplink|uplink-credential-flood|auth-timeout|downlink-imsi|ue-capability", result.stdout)
        self.assertIn("hot-run", result.stdout)

    def test_module_runners_have_external_lifecycle_and_readiness_gates(self):
        contracts = {
            ROOT / "reproducers/blind-dos/bin/blind-p5-phase": "BLIND_MANAGE_DU",
            ROOT / "reproducers/uplink-dos/bin/uplink-run": "UPLINK_MANAGE_RAN",
            ROOT / "reproducers/uplink-dos/bin/uplink-credential-flood-run":
                "CREDENTIAL_FLOOD_MANAGE_RAN",
            ROOT / "reproducers/authentication-timeout-exhaustion/bin/auth-timeout-p5-phase":
                "AUTH_TIMEOUT_MANAGE_DU",
            ROOT / "reproducers/downlink-imsi-extractor/bin/downlink-imsi-run":
                "DOWNLINK_IMSI_MANAGE_RAN",
            ROOT / "reproducers/ue-capability-hijacking/bin/ue-capability-run":
                "UE_CAPABILITY_MANAGE_RAN",
            ROOT / "reproducers/nas-counter-desynchronization/bin/nas-counter-desync-run":
                "NAS_DESYNC_MANAGE_RAN",
        }
        for path, lifecycle in contracts.items():
            source = path.read_text()
            self.assertIn(lifecycle, source)
            self.assertIn("SAME_CELL_READY_FILE", source)
            self.assertIn("SAME_CELL_RAN_READY_FILE", source)
            self.assertIn("SAME_CELL_PRESTART", source)
            self.assertIn("SAME_CELL_ATTACK_READY_FILE", source)

    def test_normal_tun_suffix_is_opt_in(self):
        patch = (ROOT / "workloads/normal-ue/patch/normal-tun-suffix.patch").read_text()
        self.assertIn("OAI_NORMAL_TUN_SUFFIX", patch)
        self.assertIn('strcmp(normal_tun_suffix, "1") == 0', patch)
        self.assertIn("normal UE PDU session id를 읽지 못했습니다", SCRIPT.read_text())

    def test_persistent_session_owns_du_and_never_restarts_it_per_attack(self):
        source = SCRIPT.read_text()
        self.assertIn('record_pid du "${GNB_PIDS[0]}"', source)
        self.assertIn('DU_PID=$(owned_pid du 2>/dev/null || true)', source)
        self.assertIn('"du_restarted":false', source)
        self.assertIn("start_placeholder_group", source)
        self.assertIn("select_broker", source)
        self.assertIn("SAME_CELL_EXPERIMENTAL_SWITCH", source)
        self.assertGreaterEqual(source.count("9>&- &"), 4)
        self.assertIn('NORMAL_UE_GNB_RESTART_CMD" >"$RUN_OUT/gnb-start.log" 2>&1 9>&-', source)
        run_section = source.rsplit("case $ATTACK in", 1)[1]
        self.assertNotIn("NORMAL_UE_GNB_RESTART_CMD", run_section)

    def test_broker_switches_paths_without_replacing_zmq_peers(self):
        broker = (ROOT / "workloads/normal-ue/tools/same_cell_broker.py").read_text()
        self.assertIn("def select_attack_slots", broker)
        self.assertIn("blocks.selector", broker)
        self.assertIn("blocks.multiply_const_cc(0.0)", broker)
        self.assertIn("ul_gate.set_k", broker)
        self.assertIn("dl_gate.set_k", broker)
        self.assertIn("NORMAL_UE_BROKER_PERSISTENT_ATTACK", broker)
        self.assertIn('mode == "warmup"', broker)
        self.assertIn("attack slots must be warmed first", broker)
        method = broker.split("def select_attack_slots", 1)[1].split("\n\n", 1)[0]
        self.assertNotIn("self.lock()", method)
        self.assertNotIn("self.connect(", method)
        self.assertIn("signal.SIGUSR1", broker)
        self.assertIn("SAME_CELL_SLOT_SELECTION", broker)

    def test_default_run_cold_starts_clocked_attack_slots(self):
        source = SCRIPT.read_text()
        run_section = source.rsplit("if [[ $ACTION == run ]]; then", 1)[1].split(
            "if [[ $ACTION == start ]]; then", 1
        )[0]
        self.assertIn("SAME_CELL_PRESTART=1", run_section)
        self.assertIn("NORMAL_UE_BROKER_PERSISTENT_ATTACK=1", run_section)
        self.assertIn("SAME_CELL_HEALTH_TIMEOUT_S + 30", run_section)
        self.assertIn("select_broker attack", run_section)
        self.assertLess(run_section.index("select_broker warmup"), run_section.index("select_broker attack"))
        self.assertIn("SAME_CELL_ATTACK_DONE_FILE", run_section)
        self.assertIn("SAME_CELL_VICTIM_TUN=oaitun_ue1", run_section)
        self.assertIn('공격 UE clock 유지 중 normal UE가 $COUNT/$COUNT가 아닙니다', run_section)
        self.assertIn("normal_healthy_before_attack_teardown", run_section)
        self.assertIn("attack.ready", run_section)
        self.assertIn("clocked_attack_slots", run_section)
        restart = run_section.index('bash -c "$NORMAL_UE_GNB_RESTART_CMD"')
        self.assertLess(run_section.index("start_normal_group"), restart)
        self.assertLess(run_section.index('setsid "${COMMAND[@]}"'), restart)

    def test_credential_flood_starts_managed_du_before_ue(self):
        source = (ROOT / "reproducers/uplink-dos/bin/uplink-credential-flood-run").read_text()
        managed = source.index('if (( MANAGE_RAN )); then')
        ue = source.index('OAI_UPLINK_DOS_REGISTRATION_FAILURE_FLOOD=1')
        self.assertLess(managed, ue)
        self.assertIn('TARGET_PER_UE=$((ENABLE == 1 ? 10 : 1))', source)
        self.assertIn('OAI_UPLINK_DOS_REGISTRATION_FAILURE_TARGET=$TARGET_PER_UE', source)
        self.assertIn("Received Registration Reject cause", source)
        self.assertIn("SAME_CELL_RELEASE_FILE", source)
        self.assertIn('uplink-credential-flood) ATTACK_SLOTS=1', SCRIPT.read_text())

    def test_modified_shell_entrypoints_are_syntax_valid(self):
        paths = [
            SCRIPT,
            ROOT / "reproducers/blind-dos/bin/blind-p5-phase",
            ROOT / "reproducers/uplink-dos/bin/uplink-run",
            ROOT / "reproducers/uplink-dos/bin/uplink-credential-flood-run",
            ROOT / "reproducers/authentication-timeout-exhaustion/bin/auth-timeout-p5-phase",
            ROOT / "reproducers/downlink-imsi-extractor/bin/downlink-imsi-run",
            ROOT / "reproducers/ue-capability-hijacking/bin/ue-capability-run",
            ROOT / "reproducers/nas-counter-desynchronization/bin/nas-counter-desync-run",
        ]
        for path in paths:
            result = subprocess.run(["bash", "-n", str(path)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, f"{path}: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
