import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "workloads" / "normal-ue" / "bin" / "same-cell-run"


class SameCellContractTests(unittest.TestCase):
    def test_help_lists_the_three_live_protocol_modules(self):
        result = subprocess.run([str(SCRIPT), "--help"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("same-cell-run start", result.stdout)
        self.assertIn("same-cell-run run", result.stdout)
        self.assertIn("same-cell-run status", result.stdout)
        self.assertIn("same-cell-run stop", result.stdout)
        self.assertIn("blind|uplink|auth-timeout", result.stdout)

    def test_module_runners_have_external_lifecycle_and_readiness_gates(self):
        contracts = {
            ROOT / "reproducers/blind-dos/bin/blind-p5-phase": "BLIND_MANAGE_DU",
            ROOT / "reproducers/uplink-dos/bin/uplink-run": "UPLINK_MANAGE_RAN",
            ROOT / "reproducers/authentication-timeout-exhaustion/bin/auth-timeout-p5-phase":
                "AUTH_TIMEOUT_MANAGE_DU",
        }
        for path, lifecycle in contracts.items():
            source = path.read_text()
            self.assertIn(lifecycle, source)
            self.assertIn("SAME_CELL_READY_FILE", source)

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
        run_section = source.split("case $ATTACK in", 1)[1]
        self.assertNotIn("NORMAL_UE_GNB_RESTART_CMD", run_section)

    def test_broker_switches_paths_without_replacing_zmq_peers(self):
        broker = (ROOT / "workloads/normal-ue/tools/same_cell_broker.py").read_text()
        self.assertIn("def select_attack_slots", broker)
        self.assertIn("blocks.selector", broker)
        self.assertIn('mode == "warmup"', broker)
        self.assertIn("attack slots must be warmed first", broker)
        method = broker.split("def select_attack_slots", 1)[1].split("\n\n", 1)[0]
        self.assertNotIn("self.lock()", method)
        self.assertNotIn("self.connect(", method)
        self.assertIn("signal.SIGUSR1", broker)
        self.assertIn("SAME_CELL_SLOT_SELECTION", broker)


if __name__ == "__main__":
    unittest.main()
