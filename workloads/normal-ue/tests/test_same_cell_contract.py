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
        self.assertIn("blind|uplink|uplink-credential-flood|auth-timeout", result.stdout)
        self.assertIn("downlink-imsi|ue-capability|nas-counter-desync", result.stdout)
        self.assertNotIn("hot-run", result.stdout)

    def test_live_l3_paths_reach_configuration_validation(self):
        for attack in ("blind", "auth-timeout", "nas-counter-desync"):
            result = subprocess.run(
                [str(SCRIPT), "run", attack, "-n", "blocked", "--", "true"],
                text=True, capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("normal UE 설정", result.stderr)

    def test_module_runners_have_external_lifecycle_and_readiness_gates(self):
        contracts = {
            ROOT / "reproducers/blind-dos/bin/blind-p5-phase": "BLIND_MANAGE_DU",
            ROOT / "reproducers/uplink-dos/bin/uplink-run": "UPLINK_MANAGE_RAN",
            ROOT / "reproducers/uplink-dos/bin/uplink-credential-flood-run":
                "CREDENTIAL_FLOOD_MANAGE_RAN",
            ROOT / "reproducers/authentication-timeout-exhaustion/bin/auth-timeout-p5-phase":
                "AUTH_TIMEOUT_MANAGE_DU",
            ROOT / "reproducers/authentication-timeout-exhaustion/bin/auth-stall-cell-run":
                "SAME_CELL_AUTH_TIMEOUT_MANAGE_DU",
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
            if path.name not in {"auth-timeout-p5-phase", "uplink-run"}:
                self.assertIn("SAME_CELL_ATTACK_DONE_FILE", source)
                self.assertIn("SAME_CELL_RELEASE_FILE", source)

    def test_wrapped_runners_publish_their_evidence_directory(self):
        for path in (
            ROOT / "reproducers/blind-dos/bin/blind-run",
            ROOT / "reproducers/authentication-timeout-exhaustion/bin/auth-stall-cell-run",
            ROOT / "reproducers/downlink-imsi-extractor/bin/downlink-imsi-run",
            ROOT / "reproducers/ue-capability-hijacking/bin/ue-capability-run",
        ):
            self.assertIn("output=$OUT", path.read_text(), str(path))

    def test_blind_same_cell_uses_the_current_checkout(self):
        runner = (ROOT / "reproducers/blind-dos/bin/blind-run").read_text()
        phase = (ROOT / "reproducers/blind-dos/bin/blind-p5-phase").read_text()
        example = (ROOT / "reproducers/blind-dos/conf/p5-zmq.conf.example").read_text()
        self.assertIn('PHASE_CMD \'exec %q\' "$HERE/bin/blind-p5-phase"', runner)
        self.assertIn("P5_HOOK=$HERE/bin/blind-p5-hook", phase)
        self.assertNotIn("/root/blind-dos-tool", example)

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
        self.assertIn("dl_gate = blocks.multiply_const_cc(1.0)", broker)
        self.assertIn("NORMAL_UE_BROKER_PERSISTENT_ATTACK", broker)
        self.assertIn('mode not in {"standby", "warmup", "attack"}', broker)
        self.assertIn("endpoint_count > 15", broker)
        self.assertIn('mode == "warmup"', broker)
        self.assertIn("attack slots must be warmed first", broker)
        method = broker.split("def select_attack_slots", 1)[1].split("\n\n", 1)[0]
        self.assertNotIn("self.lock()", method)
        self.assertNotIn("self.connect(", method)
        self.assertIn("signal.SIGUSR1", broker)
        self.assertIn("SAME_CELL_SLOT_SELECTION", broker)

    def test_rrc_attack_ue_waits_for_the_broker_gate(self):
        patch = (ROOT / "reproducers/rrc-signaling-storm/patch/oai-broker-control-gate.patch").read_text()
        runner = (ROOT / "reproducers/rrc-signaling-storm/bin/rss-broker-witness").read_text()
        self.assertIn('getenv("RSS_BROKER_CONTROL_FILE")', patch)
        self.assertIn('memcmp(mode, "attack"', patch)
        self.assertIn("if (!rss_broker_attack_enabled())", patch)
        self.assertIn('grep -Faq RSS_BROKER_CONTROL_FILE "$BROKER_ATTACK_UE_BIN"', runner)
        gate = runner.split("select_persistent_attack()", 1)[1].split("\n}\n", 1)[0]
        open_gate = 'printf \'attack\\n\' >"$ATTACK_UE_GATE_FILE"'
        self.assertLess(gate.index('count > before'), gate.index(open_gate))

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
        self.assertIn('if [[ $ATTACK != uplink ]]; then', run_section)
        self.assertIn("TOTAL_ENDPOINTS <= 15", run_section)
        self.assertIn("TOTAL_ENDPOINTS=$((ATTACK_SLOTS + COUNT))", source)
        self.assertIn("auth-timeout) ATTACK_SLOTS=10", source)
        normal_group = source.split("start_normal_group()", 1)[1].split("start_placeholder_group()", 1)[0]
        self.assertIn("RSS_SHARE_NUE=\"$COUNT\"", normal_group)
        self.assertNotIn("--zmq.", normal_group)
        self.assertIn('NORMAL_UE_ZMQ_ENDPOINT_OFFSET="$ATTACK_SLOTS"', run_section)
        self.assertIn("attack.ready", run_section)
        done = run_section.index('SAME_CELL_ATTACK_DONE_FILE')
        recover = run_section.index('wait_healthy "$COUNT"')
        self.assertLess(done, run_section.index("select_broker standby", done, recover))
        self.assertIn("clocked_attack_slots", run_section)
        self.assertIn("embed_self_live_evidence", run_section)
        self.assertIn("SAME_CELL_ATTACK_TIMEOUT_S", run_section)
        self.assertIn("공격 runner 완료가", run_section)
        self.assertIn("공격 runner 종료가", run_section)
        self.assertIn('"normal_ue_coexistence"', source)
        restart = run_section.index('bash -c "$NORMAL_UE_GNB_RESTART_CMD"')
        self.assertLess(run_section.index("start_normal_group"), restart)
        self.assertLess(run_section.index('setsid "${COMMAND[@]}"'), restart)

    def test_stop_recovers_a_partial_cold_run_without_placeholder_state(self):
        source = SCRIPT.read_text()
        stop = source.index("if [[ $ACTION == stop ]]; then")
        placeholder = source.index('read -r PLACEHOLDER_CFG <"$STATE/placeholder_config"')
        self.assertLess(stop, placeholder)
        stop_section = source[stop:placeholder]
        self.assertIn("for role in attack placeholder-group broker normal", stop_section)
        self.assertIn('bash -c "$NORMAL_UE_GNB_STOP_CMD"', stop_section)
        self.assertIn("상태를 보존합니다", stop_section)

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

    def test_auth_timeout_uses_ten_independent_ru_attack_slots(self):
        source = (ROOT / "reproducers/authentication-timeout-exhaustion/bin/auth-stall-cell-run").read_text()
        self.assertIn("${#endpoint_rows[@]} == UE_COUNT", source)
        self.assertIn("endpoint_offset=$((i * UES_PER_PROCESS))", source)
        self.assertIn('endpoint_rows[$((i * UES_PER_PROCESS + ru))]', source)
        self.assertNotIn('"--zmq.[0].tx_channels"', source)
        self.assertNotIn('"--zmq.[$ru].tx_channels"', source)
        self.assertIn('OAI_AUTH_TIMEOUT_GATE_FILE="$SAME_CELL_UE_GATE_FILE"', source)
        self.assertIn('OAI_AUTH_TIMEOUT_GATE_BASE_MS="$gate_base_ms"', source)
        self.assertIn('OAI_AUTH_TIMEOUT_GATE_STEP_MS="$gate_step_ms"', source)
        self.assertIn('gate_base_ms=$((i * 25))', source)
        self.assertIn('"same_cell_ra_base_ms":[0,25]', source)
        self.assertIn('"same_cell_ra_step_ms":50', source)

    def test_auth_build_disables_ru_sharing_when_each_ue_has_a_ru(self):
        build = (ROOT / "reproducers/authentication-timeout-exhaustion/bin/auth-timeout-build").read_text()
        patch = (ROOT / "workloads/normal-ue/patch/normal-multi-ru.patch").read_text()
        gate = (ROOT / "reproducers/authentication-timeout-exhaustion/patch/same-cell-ra-gate-w38.patch").read_text()
        self.assertIn("NORMAL_MULTI_RU_PATCH", build)
        self.assertLess(build.index('apply "$RU_SHARE_PATCH"'), build.index('apply "$NORMAL_MULTI_RU_PATCH"'))
        self.assertLess(build.index('apply "$NORMAL_MULTI_RU_PATCH"'), build.index('apply "$PATCH"'))
        self.assertLess(build.index('apply "$PATCH"'), build.index('apply "$SAME_CELL_GATE_PATCH"'))
        self.assertIn("return NB_UE_INST > nrue_get_ru_count();", patch)
        self.assertIn('auth_timeout_same_cell_ms("OAI_AUTH_TIMEOUT_GATE_BASE_MS", 1000)', gate)
        self.assertIn('auth_timeout_same_cell_ms("OAI_AUTH_TIMEOUT_GATE_STEP_MS", 1000)', gate)
        self.assertIn("auth_timeout_same_cell_ra_allowed(mac->ue_id)", gate)
        self.assertIn("mac->state == UE_RECEIVING_SIB && mac->current_UL_BWP", gate)
        self.assertIn("pthread_mutex_lock(&auth_timeout_gate_mutex)", gate)
        self.assertIn("AUTH_TIMEOUT_RA_GATE event=released", gate)
        self.assertIn("if (!same_cell_gate || same_cell_gate[0] == '\\0')", gate)
        self.assertNotIn("usleep", gate)

    def test_common_broker_opens_the_ue_gate_only_after_attack_ack(self):
        source = SCRIPT.read_text()
        select = source.split("select_broker()", 1)[1].split("\n}\n", 1)[0]
        open_gate = 'printf \'attack\\n\' >"$STATE/attack-ue-gate"'
        self.assertLess(select.index('count > before'), select.index(open_gate))
        self.assertIn('SAME_CELL_UE_GATE_FILE="$STATE/attack-ue-gate"', source)

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
