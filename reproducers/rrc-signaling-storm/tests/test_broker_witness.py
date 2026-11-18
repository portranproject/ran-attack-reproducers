"""Offline lifecycle and role checks for the independent broker witness."""
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "rss-broker-witness"
BROKER2 = ROOT / "tools" / "multi_ue_2ue.py"
BROKER5 = ROOT / "tools" / "multi_ue_5ue.py"
BROKER7 = ROOT / "tools" / "multi_ue_7ue.py"
BROKER8 = ROOT / "tools" / "multi_ue_8ue.py"
DYNAMIC_BROKER = ROOT.parents[1] / "workloads" / "normal-ue" / "tools" / "same_cell_broker.py"


class BrokerWitnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.stubs = self.root / "stubs"
        self.stubs.mkdir()
        self.runs = self.root / "runs"
        self.trace = self.root / "ue.trace"
        self.tun_state = self.root / "tun.state"

        self.ue_cfg = self.root / "ue.conf"
        self.witness_ue_cfg = self.root / "witness-ue.conf"
        self.uecap = self.root / "uecap.xml"
        self.broker_py = self.root / "broker.py"
        self.gnb_cfg = self.root / "du.yaml"
        for path in (self.ue_cfg, self.uecap, self.broker_py):
            path.write_text("fixture\n")
        self.witness_ue_cfg.write_text(
            "".join(f'uicc{i} = {{ imsi = "{i}"; }};\n' for i in range(5))
        )
        self.broker_py.write_text(
            "tcp://127.0.0.1:2501 tcp://127.0.0.1:2500 "
            "tcp://127.0.0.1:2601 tcp://127.0.0.1:2600 "
            "tcp://127.0.0.1:2801 tcp://127.0.0.1:2800\n"
        )
        self.gnb_cfg.write_text(
            "device_args: tx_port=tcp://127.0.0.1:2000,"
            "rx_port=tcp://127.0.0.1:2001,base_srate=23.04e6\n"
        )
        self.ue = self.root / "nr-uesoftmodem"
        self.ue.write_text(
            "#!/bin/bash\n"
            "# OAI_NORMAL_TUN_SUFFIX fixture marker\n"
            "tx= probe= delay= log= run= max_duration= honor_reject= msg4_wait= num_ues= probe_ra_only= probe_interval= phase= cfg=\n"
            "txs=()\n"
            "while (( $# )); do\n"
            "  case $1 in\n"
            "    --zmq.\\[*\\].tx_channels) tx=$2; txs+=(\"$2\"); shift 2;;\n"
            "    --rss.probe_ues) probe=$2; shift 2;;\n"
            "    --rss.probe_delay_ms) delay=$2; shift 2;;\n"
            "    --rss.log_file) log=$2; shift 2;;\n"
            "    --rss.run_id) run=$2; shift 2;;\n"
            "    --rss.max_duration_s) max_duration=$2; shift 2;;\n"
            "    --rss.honor_reject) honor_reject=$2; shift 2;;\n"
            "    --rss.msg4_wait) msg4_wait=$2; shift 2;;\n"
            "    --num-ues) num_ues=$2; shift 2;;\n"
            "    --rss.probe_ra_only) probe_ra_only=$2; shift 2;;\n"
            "    --rss.probe_interval_ms) probe_interval=$2; shift 2;;\n"
            "    --rss.phase_ms) phase=$2; shift 2;;\n"
            "    -O) cfg=$2; shift 2;;\n"
            "    *) shift;;\n"
            "  esac\n"
            "done\n"
            "if (( ${#txs[@]} == 0 )) && [[ -f $cfg ]]; then\n"
            "  while IFS= read -r endpoint; do txs+=(\"$endpoint\"); done < <(grep -oE 'tcp://127\\.0\\.0\\.1:[0-9]+' \"$cfg\" | awk 'NR % 2 == 1')\n"
            "  (( ${#txs[@]} == 0 )) || tx=${txs[$((${#txs[@]} - 1))]}\n"
            "fi\n"
            "trap 'exit 0' INT TERM\n"
            "printf '%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s\\n' \"$tx\" \"$probe\" \"$delay\" \"$run\" \"$max_duration\" \"$honor_reject\" \"$msg4_wait\" \"$num_ues\" \"$RSS_SHARE_NUE\" \"$probe_ra_only\" \"$probe_interval\" \"$phase\" \"$cfg\" >> \"$FAKE_TRACE\"\n"
            "printf '%s\\n' '[RSS] fixture'\n"
            "for endpoint in \"${txs[@]}\"; do\n"
            "  if [[ -z ${FAKE_NO_TX_BOUND_RUN:-} || $run != ${FAKE_NO_TX_BOUND_RUN} ]]; then printf '%s\\n' \"[HW] [ZMQ] TX socket for antenna 0 bound to $endpoint\"; fi\n"
            "  if [[ ( -z ${FAKE_NO_SYNC_PORT:-} || $endpoint != *:${FAKE_NO_SYNC_PORT} ) && ( -z ${FAKE_NO_SYNC_RUN:-} || $run != ${FAKE_NO_SYNC_RUN} ) ]]; then printf '%s\\n' 'Initial sync successful'; fi\n"
            "done\n"
            ": > \"$log\"\n"
            "witness_tx=${FAKE_WITNESS_TX_PORT:-2501}\n"
            "same_witness=0\n"
            "if [[ ${BROKER_SAME_WITNESS_CYCLE:-0} == 1 && $tx == *:$witness_tx ]]; then\n"
            "  same_witness=1; attempts=${FAKE_SAME_WITNESS_ATTEMPTS:-10}; span_ms=${FAKE_SAME_WITNESS_SPAN_MS:-30000}\n"
            "  for ((i=0; i<attempts; i++)); do\n"
            "    step_ns=0; (( attempts <= 1 )) || step_ns=$((span_ms * 1000000 / (attempts - 1)))\n"
            "    t_ns=$((1000000000 + i * step_ns)); (( i + 1 < attempts )) || t_ns=$((1000000000 + span_ms * 1000000))\n"
            "    printf '{\"event\":\"attempt_start\",\"t_ns\":%d,\"ue_identity\":\"0x%010x\"}\\n' \"$t_ns\" $((i + 1)) >> \"$log\"\n"
            "  done\n"
            "  msg3=${FAKE_SAME_WITNESS_MSG3:-10}; msg3_span_ms=${FAKE_SAME_WITNESS_MSG3_SPAN_MS:-30000}; distinct_tc_rnti=${FAKE_SAME_WITNESS_DISTINCT_TC_RNTI:-$msg3}\n"
            "  for ((i=0; i<msg3; i++)); do\n"
            "    step_ns=0; (( msg3 <= 1 )) || step_ns=$((msg3_span_ms * 1000000 / (msg3 - 1)))\n"
            "    t_ns=$((2000000000 + i * step_ns)); (( i + 1 < msg3 )) || t_ns=$((2000000000 + msg3_span_ms * 1000000))\n"
            "    tc_rnti=0; (( distinct_tc_rnti <= 0 )) || tc_rnti=$((i % distinct_tc_rnti + 1))\n"
            "    printf '{\"event\":\"msg3_tx\",\"t_ns\":%d,\"tc_rnti\":\"0x%04x\"}\\n' \"$t_ns\" \"$tc_rnti\" >> \"$log\"\n"
            "  done\n"
            "fi\n"
            "if (( same_witness )); then\n"
            "  :\n"
            "elif [[ $run == *-recovery && ${FAKE_RECOVERY_EARLY_ATTEMPT:-0} == 1 ]]; then printf '%s\\n' '{\"event\":\"attempt_start\"}' >> \"$log\"; fi\n"
            "if (( !same_witness )) && [[ $run == *-recovery && $delay -gt 0 ]]; then\n"
            "  settle_delay=${FAKE_RECOVERY_SETTLE_ATTEMPT_DELAY_S:-}\n"
            "  if [[ -n $settle_delay ]]; then\n"
            "    sleep \"$settle_delay\"; printf '%s\\n' '{\"event\":\"attempt_start\"}' >> \"$log\"\n"
            "    remaining=$((delay / 1000 - settle_delay)); (( remaining <= 0 )) || sleep \"$remaining\"\n"
            "  else\n"
            "    sleep $((delay / 1000))\n"
            "  fi\n"
            "fi\n"
            "if (( same_witness )); then\n"
            "  :\n"
            "elif [[ $run == *-control-extra-quiet ]]; then\n"
            "  if [[ ${FAKE_CONTROL_EXTRA_QUIET_ATTEMPT:-0} == 1 ]]; then printf '%s\\n' '{\"event\":\"attempt_start\"}' >> \"$log\"; fi\n"
            "elif [[ $probe_ra_only == 1 || $probe == 0 ]]; then\n"
            "  printf '%s\\n' '{\"event\":\"attempt_start\"}' '{\"event\":\"msg3_tx\",\"t_ns\":1,\"tc_rnti\":\"0x1111\"}' '{\"event\":\"msg5_skip\"}' >> \"$log\"\n"
            "  if [[ ${FAKE_DELAYED_MSG3:-0} == 1 ]]; then ( until grep -q '^attack' \"$RSS_BROKER_CONTROL_FILE\"; do sleep .05; done; printf '%s\\n' '{\"event\":\"msg3_tx\",\"t_ns\":2,\"tc_rnti\":\"0x2222\"}' >> \"$log\" ) & fi\n"
            "  if (( max_duration > 0 )) && [[ -z ${FAKE_NO_KILL_SWITCH_PORT:-} || $tx != *:${FAKE_NO_KILL_SWITCH_PORT} ]]; then\n"
            "    sleep ${FAKE_ATTACK_KILL_DELAY_S:-0}; printf '%s\\n' '{\"event\":\"kill_switch\"}' >> \"$log\"\n"
            "    if [[ -n ${FAKE_ATTACK_POST_BOUNDARY_PORT:-} && $tx == *:${FAKE_ATTACK_POST_BOUNDARY_PORT} ]]; then sleep 2; printf '%s\\n' '{\"event\":\"attempt_start\"}' >> \"$log\"; fi\n"
            "    if [[ -n ${FAKE_ATTACK_POST_BOUNDARY_MSG3_PORT:-} && $tx == *:${FAKE_ATTACK_POST_BOUNDARY_MSG3_PORT} ]]; then sleep 2; printf '%s\\n' '{\"event\":\"msg3_tx\",\"t_ns\":9,\"tc_rnti\":\"0x9999\"}' >> \"$log\"; fi\n"
            "  fi\n"
            "elif (( delay > 1000 )); then\n"
            "  printf '%s\\n' '{\"event\":\"attempt_start\"}' >> \"$log\"\n"
            "  printf '%s\\n' 'Generating RRCSetupComplete'\n"
            "else\n"
            "  printf '%s\\n' '{\"event\":\"probe_attempt\"}' >> \"$log\"\n"
            "fi\n"
            "witness_ok=${FAKE_WITNESS_OK:-1}\n"
            "if [[ $run == *-recovery ]]; then witness_tx=${FAKE_RECOVERY_WITNESS_TX_PORT:-2601}; witness_ok=${FAKE_RECOVERY_WITNESS_OK:-$witness_ok}; else witness_ok=${FAKE_PRIMARY_WITNESS_OK:-$witness_ok}; fi\n"
            "if [[ $tx == *:$witness_tx && $run != *-recovery && -n ${FAKE_PRIMARY_POST_ATTACK_DELAY_S:-} ]]; then sleep \"$FAKE_PRIMARY_POST_ATTACK_DELAY_S\"; witness_ok=1; fi\n"
            "if (( same_witness )) && [[ ${FAKE_SAME_WITNESS_RECOVERY_OK:-1} == 1 ]]; then\n"
            "  sleep ${FAKE_SAME_WITNESS_RECOVERY_DELAY_S:-3}\n"
            "  printf '%s\\n' 'Generating RRCSetupComplete' 'Registration Accept' 'PDU Session Establishment Accept'\n"
            "  : > \"$FAKE_TUN_STATE\"\n"
            "elif [[ $tx == *:$witness_tx && $witness_ok == 1 ]]; then\n"
            "  printf '%s\\n' 'Generating RRCSetupComplete' 'Registration Accept' "
            "'PDU Session Establishment Accept'\n"
            "  : > \"$FAKE_TUN_STATE\"\n"
            "fi\n"
            "[[ -z ${FAKE_UE_EXIT_PORT:-} || $tx != *:${FAKE_UE_EXIT_PORT} ]] || exit 9\n"
            "if [[ -n ${FAKE_UE_TEARDOWN_CRASH_PORT:-} && $tx == *:${FAKE_UE_TEARDOWN_CRASH_PORT} ]]; then\n"
            "  exec python3 -c 'import os,signal,time; signal.signal(signal.SIGINT, lambda *_: (print(\"Segmentation fault\", flush=True), os._exit(139))); time.sleep(20)'\n"
            "fi\n"
            "if [[ -n ${FAKE_UE_TEARDOWN_CRASH_RUN:-} && $run == ${FAKE_UE_TEARDOWN_CRASH_RUN} ]]; then\n"
            "  exec python3 -c 'import os,signal,time; signal.signal(signal.SIGINT, lambda *_: (print(\"Segmentation fault\", flush=True), os._exit(139))); time.sleep(20)'\n"
            "fi\n"
            "exec python3 -c 'import os,signal,time; n=[0]; signal.signal(signal.SIGINT, lambda *_: (n.__setitem__(0,n[0]+1), os._exit(0) if n[0] > 1 else None)); time.sleep(20)'\n"
        )
        self.ue.chmod(0o755)
        self.normal_conf = self.root / "normal.conf"
        self.normal_conf.write_text(
            f"NORMAL_UE_BIN={shlex.quote(str(self.ue))}\n"
            f"NORMAL_UE_CFG={shlex.quote(str(self.witness_ue_cfg))}\n"
            f"NORMAL_UE_UECAP={shlex.quote(str(self.uecap))}\n"
        )

        self.broker = self.root / "fake-broker"
        self.broker.write_text(
            "#!/usr/bin/env python3\n"
            "import os, signal, time\n"
            "if os.environ.get('FAKE_BROKER_EXIT', '0') != '0':\n"
            "    raise SystemExit(7)\n"
            "def stop(_signum, _frame):\n"
            "    raise SystemExit(int(os.environ.get('FAKE_BROKER_STOP_STATUS', '0')))\n"
            "def reset_witness(_signum, _frame):\n"
            "    control = os.environ.get('NORMAL_UE_BROKER_CONTROL', '')\n"
            "    if control:\n"
            "        raw = open(control, encoding='utf-8').read().strip()\n"
            "        print('SAME_CELL_SLOT_SELECTION mode=' + raw.replace(' ', ' slots='), flush=True)\n"
            "    elif os.environ.get('FAKE_BROKER_NO_RESET_ACK', '0') != '1':\n"
            "        print('RSS_BROKER_WITNESS_UPLINK_RESET port=' + os.environ.get('FAKE_WITNESS_TX_PORT', '2501'), flush=True)\n"
            "signal.signal(signal.SIGINT, stop)\n"
            "signal.signal(signal.SIGUSR1, reset_witness)\n"
            "while True:\n"
            "    time.sleep(0.05)\n"
        )
        self.broker.chmod(0o755)

        self.stub("flock", "exit 0\n")
        self.stub(
            "ip",
            "if [ \"$1\" = addr ]; then rm -f \"$FAKE_TUN_STATE\"; exit 0; fi\n"
            "if [ -f \"$FAKE_TUN_STATE\" ]; then\n"
            "  echo '1: oaitun_ue1 inet 10.45.1.2/24 scope global oaitun_ue1'\n"
            "  exit 0\n"
            "fi\n"
            "exit 1\n",
        )
        self.stub(
            "ping",
            "tx=${FAKE_PING_TX:-5}; rx=${FAKE_PING_RX:-$tx}; loss=${FAKE_PING_LOSS:-0}\n"
            "echo \"$tx packets transmitted, $rx received, $loss% packet loss\"\n"
            "echo 'rtt min/avg/max/mdev = 1/2/3/1 ms'\n",
        )

        self.env = dict(
            os.environ,
            RSS_CONF=str(self.root / "missing.conf"),
            OAI=str(self.root),
            UE_BIN=str(self.ue),
            UE_CFG=str(self.ue_cfg),
            UECAP=str(self.uecap),
            BROKER_PY=str(self.broker_py),
            BROKER_CMD="exec " + shlex.quote(str(self.broker)),
            BROKER_LOGDIR=str(self.runs),
            GNB_CONFIG=str(self.gnb_cfg),
            GNB_STOP_CMD="true",
            GNB_RESTART_CMD="true",
            GNB_READY_CMD="true",
            GNB_SETTLE_S="0",
            GNB_READY_TIMEOUT_S="2",
            GNB_READY_INTERVAL_S="1",
            GNB_READY_PROBE_TIMEOUT_S="1",
            WITNESS_DELAY_MS="0",
            UE_BEFORE_BROKER_S="0",
            BROKER_SYNC_TIMEOUT_S="2",
            FLOCK_BIN=str(self.stubs / "flock"),
            IP_CMD=str(self.stubs / "ip"),
            PING_CMD=str(self.stubs / "ping"),
            LOCK_FILE=str(self.root / "lock"),
            USE_SETSID="0",
            FAKE_TRACE=str(self.trace),
            FAKE_TUN_STATE=str(self.tun_state),
        )

    def stub(self, name, body):
        path = self.stubs / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)
        return path

    def run_script(self, mode="control", run_id="bw-test", duration=1, **overrides):
        env = dict(self.env, **{key: str(value) for key, value in overrides.items()})
        return subprocess.run(
            ["bash", str(SCRIPT), mode, "-n", run_id, "-d", str(duration)],
            env=env,
            text=True,
            capture_output=True,
            timeout=20,
        )

    def result(self, run_id):
        return json.loads((self.runs / run_id / "result.json").read_text())

    def test_control_uses_four_quiet_ports_and_one_ordinary_witness(self):
        result = self.run_script(
            run_id="bw-control", BROKER_ATTACK_UES_PER_PROCESS="2"
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        rows = [line.split("|") for line in self.trace.read_text().splitlines()]
        self.assertEqual({row[0].rsplit(":", 1)[1] for row in rows},
                         {"2101", "2201", "2301", "2401", "2501"})
        roles = {row[0].rsplit(":", 1)[1]: row for row in rows}
        for port in ("2101", "2201", "2301", "2401"):
            self.assertEqual(roles[port][1], "2")
            self.assertGreater(int(roles[port][2]), 1_000)
            self.assertEqual(roles[port][4:7], ["0", "0", "1"])
            self.assertEqual(roles[port][7:9], ["2", "2"])
        self.assertEqual(roles["2501"][1:3], ["1", "0"])
        self.assertEqual(roles["2501"][4:7], ["0", "0", "1"])
        self.assertEqual(roles["2501"][7:9], ["1", "1"])
        self.assertTrue(all(row[11] == "0" for row in rows))
        verdict = self.result("bw-control")
        self.assertTrue(verdict["valid"])
        self.assertEqual(verdict["load_ue_attempts"], 4)
        self.assertEqual(verdict["load_ue_msg5"], 4)
        self.assertEqual(verdict["attacker_attempts"], 0)
        self.assertTrue(verdict["witness"]["service_ok"])
        self.assertEqual(verdict["witness"]["ping"]["transmitted"], 5)
        self.assertEqual(verdict["witness"]["ping"]["received"], 5)
        self.assertEqual(verdict["witness"]["ping"]["loss_pct"], 0)
        self.assertEqual(verdict["witness"]["ping"]["rtt_avg_ms"], 2)
        self.assertEqual(verdict["teardown"]["broker_exit_status"], 0)
        self.assertFalse(verdict["teardown"]["broker_sigsegv"])
        self.assertEqual(len(verdict["teardown"]["ue_exit_statuses"]), 5)
        self.assertTrue(
            all(isinstance(code, int) for code in verdict["teardown"]["ue_exit_statuses"])
        )
        self.assertEqual(verdict["teardown"]["ue_exit_statuses"], [0] * 5)
        self.assertEqual(verdict["teardown"]["forced_kill_count"], 0)
        self.assertEqual(verdict["teardown"]["ue_stop_signal"], "INTx2")
        self.assertEqual(verdict["teardown"]["broker_stop_signal"], "INT")

    def test_primary_witness_supports_five_ues_and_a_separate_config(self):
        result = self.run_script(
            run_id="bw-five-witnesses",
            BROKER_ATTACK_PROCESSES="1",
            BROKER_PY=str(BROKER2),
            BROKER_WITNESS_UES="5",
            BROKER_WITNESS_PHASE_MS="250",
            BROKER_WITNESS_RETRY_MS="5000",
            BROKER_WITNESS_UE_CFG=str(self.witness_ue_cfg),
            FAKE_WITNESS_TX_PORT="2201",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        rows = [line.split("|") for line in self.trace.read_text().splitlines()]
        roles = {row[0].rsplit(":", 1)[1]: row for row in rows}
        self.assertEqual(roles["2101"][7], "1")
        self.assertEqual(roles["2101"][12], str(self.ue_cfg))
        self.assertEqual(roles["2201"][1], "5")
        self.assertEqual(roles["2201"][7], "5")
        self.assertEqual(roles["2201"][8], "5")
        self.assertEqual(roles["2201"][10], "5000")
        self.assertEqual(roles["2201"][11], "250")
        self.assertEqual(roles["2201"][12], str(self.witness_ue_cfg))
        self.assertEqual(self.result("bw-five-witnesses")["topology"]["witness_ues"], 5)

    def test_primary_witness_can_use_five_independent_ru_endpoints(self):
        result = self.run_script(
            run_id="bw-five-ru-witnesses",
            BROKER_ATTACK_PROCESSES="1",
            BROKER_WITNESS_UES="5",
            BROKER_WITNESS_MULTI_RU="1",
            BROKER_WITNESS_UE_CFG=str(self.witness_ue_cfg),
            FAKE_WITNESS_TX_PORT="2601",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        witness_log = (self.runs / "bw-five-ru-witnesses" / "ue2.log").read_text()
        self.assertEqual(witness_log.count("TX socket for antenna 0 bound to"), 5)
        verdict = self.result("bw-five-ru-witnesses")
        self.assertTrue(verdict["valid"])
        self.assertEqual(verdict["sync_ues"], 6)
        self.assertEqual(verdict["topology"]["ue_processes"], 2)
        self.assertEqual(verdict["topology"]["zmq_endpoints"], 6)

    def test_six_attack_processes_can_share_a_cell_with_five_independent_witness_rus(self):
        result = self.run_script(
            mode="attack",
            run_id="bw-six-attack-five-witness",
            BROKER_ATTACK_PROCESSES="6",
            BROKER_ATTACK_UES_PER_PROCESS="2",
            BROKER_WITNESS_UES="5",
            BROKER_WITNESS_MULTI_RU="1",
            BROKER_WITNESS_UE_CFG=str(self.witness_ue_cfg),
            BROKER_PY=str(DYNAMIC_BROKER),
            FAKE_WITNESS_TX_PORT="3101",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        verdict = self.result("bw-six-attack-five-witness")
        self.assertTrue(verdict["valid"])
        self.assertEqual(verdict["sync_ues"], 11)
        self.assertEqual(verdict["topology"]["attack_or_quiet_ues"], 12)
        self.assertEqual(verdict["topology"]["witness_ues"], 5)
        self.assertEqual(verdict["topology"]["zmq_endpoints"], 11)

    def test_normal_pool_qualification_records_before_during_and_recovery(self):
        result = self.run_script(
            mode="attack",
            run_id="bw-normal-pool-qualified",
            duration=211,
            BROKER_ATTACK_PROCESSES="6",
            BROKER_ATTACK_UES_PER_PROCESS="2",
            BROKER_NORMAL_ATTACK_DURATION_S="1",
            BROKER_WITNESS_UES="5",
            BROKER_WITNESS_MULTI_RU="1",
            BROKER_NORMAL_POOL_QUALIFICATION="1",
            BROKER_NORMAL_PDU_SESSION_ID="1",
            BROKER_NORMAL_CONF=str(self.normal_conf),
            BROKER_PY=str(DYNAMIC_BROKER),
            FAKE_WITNESS_TX_PORT="3101",
            FAKE_DELAYED_MSG3="1",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        verdict = self.result("bw-normal-pool-qualified")
        self.assertTrue(verdict["valid"])
        self.assertEqual(verdict["attacker_attempts"], 6)
        pool = verdict["normal_pool"]
        self.assertEqual(pool["expected_ues"], 5)
        self.assertEqual(pool["before"], {"healthy_ues": 5, "all_healthy": True})
        self.assertGreater(pool["during"]["samples"], 0)
        self.assertEqual(pool["during"]["min_healthy_ues"], 5)
        self.assertEqual(pool["recovery"]["deadline_s"], 90)
        self.assertEqual(pool["recovery"]["healthy_ues"], 5)
        self.assertTrue(pool["recovery"]["all_healthy"])
        self.assertFalse(pool["direct_detector_input"])
        self.assertTrue(pool["ue_to_ran_path_required"])
        self.assertTrue(pool["broker_gate"]["activated"])
        self.assertGreater(pool["broker_gate"]["standby_ns"], pool["broker_gate"]["attack_ns"])
        self.assertGreater(pool["attacker_ue_msg3_during_gate"]["delta"], 0)
        phases = {
            json.loads(line)["phase"]
            for line in (self.runs / "bw-normal-pool-qualified" / "normal-health.jsonl")
            .read_text()
            .splitlines()
        }
        self.assertEqual(phases, {"before", "during", "after"})
        self.assertTrue(
            all(
                json.loads(line)["schema"] == "same-cell.normal-health.v1"
                for line in (
                    self.runs / "bw-normal-pool-qualified" / "normal-health.jsonl"
                )
                .read_text()
                .splitlines()
            )
        )
        session = json.loads(
            (self.runs / "bw-normal-pool-qualified" / "same-cell-session.json").read_text()
        )
        self.assertEqual(session["run_id"], "bw-normal-pool-qualified")
        self.assertEqual(session["normal_ues"], 5)
        self.assertTrue(session["clocked_attack_slots"])
        standard_run = json.loads(
            (self.runs / "bw-normal-pool-qualified" / "same-cell-run.json").read_text()
        )
        self.assertEqual(standard_run["attack_exit_status"], 0)
        self.assertTrue(standard_run["normal_healthy_before_attack_teardown"])
        self.assertFalse(standard_run["direct_detector_input"])
        self.assertTrue(standard_run["ue_to_ran_path_required"])

    def test_normal_pool_control_requires_five_healthy_ues_without_attack(self):
        result = self.run_script(
            mode="control",
            run_id="bw-normal-pool-control",
            duration=211,
            BROKER_ATTACK_PROCESSES="6",
            BROKER_ATTACK_UES_PER_PROCESS="2",
            BROKER_NORMAL_ATTACK_DURATION_S="1",
            BROKER_WITNESS_UES="5",
            BROKER_WITNESS_MULTI_RU="1",
            BROKER_NORMAL_POOL_QUALIFICATION="1",
            BROKER_NORMAL_PDU_SESSION_ID="1",
            BROKER_WITNESS_UE_CFG=str(self.witness_ue_cfg),
            BROKER_PY=str(DYNAMIC_BROKER),
            FAKE_WITNESS_TX_PORT="3101",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        verdict = self.result("bw-normal-pool-control")
        self.assertTrue(verdict["valid"])
        self.assertEqual(verdict["attacker_attempts"], 0)
        self.assertTrue(verdict["normal_pool"]["before"]["all_healthy"])
        self.assertGreater(verdict["normal_pool"]["during"]["samples"], 0)
        self.assertTrue(verdict["normal_pool"]["recovery"]["all_healthy"])

    def test_normal_pool_attack_rejects_missing_ue_oracle_during_gate(self):
        result = self.run_script(
            mode="attack",
            run_id="bw-normal-pool-no-ran",
            duration=211,
            BROKER_ATTACK_PROCESSES="6",
            BROKER_ATTACK_UES_PER_PROCESS="2",
            BROKER_NORMAL_ATTACK_DURATION_S="1",
            BROKER_WITNESS_UES="5",
            BROKER_WITNESS_MULTI_RU="1",
            BROKER_NORMAL_POOL_QUALIFICATION="1",
            BROKER_NORMAL_PDU_SESSION_ID="1",
            BROKER_WITNESS_UE_CFG=str(self.witness_ue_cfg),
            BROKER_PY=str(DYNAMIC_BROKER),
            FAKE_WITNESS_TX_PORT="3101",
        )
        self.assertNotEqual(result.returncode, 0)
        verdict = self.result("bw-normal-pool-no-ran")
        self.assertEqual(verdict["reason"], "normal_pool_ue_attack_oracle_missing")
        self.assertEqual(verdict["normal_pool"]["attacker_ue_msg3_during_gate"]["delta"], 0)

    def test_normal_pool_qualification_requires_duration_and_recovery_budget(self):
        for run_id, attack_duration, duration, expected in (
            (
                "bw-normal-pool-invalid-duration",
                "0",
                240,
                "BROKER_NORMAL_ATTACK_DURATION_S must be 1..300",
            ),
            (
                "bw-normal-pool-short",
                "30",
                239,
                "requires -d >= 240 seconds",
            ),
        ):
            with self.subTest(run_id=run_id):
                result = self.run_script(
                    mode="attack",
                    run_id=run_id,
                    duration=duration,
                    BROKER_ATTACK_PROCESSES="6",
                    BROKER_ATTACK_UES_PER_PROCESS="2",
                    BROKER_NORMAL_ATTACK_DURATION_S=attack_duration,
                    BROKER_WITNESS_UES="5",
                    BROKER_WITNESS_MULTI_RU="1",
                    BROKER_NORMAL_POOL_QUALIFICATION="1",
                    BROKER_NORMAL_PDU_SESSION_ID="1",
                    BROKER_PY=str(DYNAMIC_BROKER),
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)
                self.assertFalse((self.runs / run_id).exists())

    def test_normal_pool_config_rejects_a_symlink(self):
        link = self.root / "normal-link.conf"
        link.symlink_to(self.normal_conf)
        result = self.run_script(
            run_id="bw-normal-config-link",
            BROKER_NORMAL_CONF=str(link),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("absolute readable regular non-symlink", result.stderr)
        self.assertFalse((self.runs / "bw-normal-config-link").exists())

    def test_primary_witness_can_use_an_unpatched_normal_ue_binary(self):
        result = self.run_script(
            run_id="bw-clean-witness",
            BROKER_ATTACK_PROCESSES="1",
            BROKER_PY=str(BROKER2),
            BROKER_WITNESS_UES="5",
            BROKER_WITNESS_RSS="0",
            BROKER_WITNESS_UE_CFG=str(self.witness_ue_cfg),
            FAKE_WITNESS_TX_PORT="2201",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        rows = [line.split("|") for line in self.trace.read_text().splitlines()]
        witness = next(row for row in rows if row[0].endswith(":2201"))
        self.assertEqual(witness[1:4], ["", "", ""])
        self.assertEqual(witness[7:9], ["5", "5"])
        self.assertEqual(witness[12], str(self.witness_ue_cfg))

    def test_broker_waits_for_every_ue_zmq_endpoint(self):
        result = self.run_script(
            run_id="bw-endpoint-timeout",
            BROKER_ATTACK_PROCESSES="1",
            BROKER_PY=str(BROKER2),
            BROKER_ENDPOINT_READY_TIMEOUT_S="1",
            FAKE_NO_TX_BOUND_RUN="u2-bw-endpoint-timeout",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("1/2 UE ZMQ endpoints ready", result.stderr)
        self.assertFalse((self.runs / "bw-endpoint-timeout" / "broker.log").exists())

    def test_control_can_match_attack_with_an_eighth_quiet_endpoint(self):
        result = self.run_script(
            run_id="bw-control-eight-endpoint",
            BROKER_ATTACK_PROCESSES="6",
            BROKER_ATTACK_UES_PER_PROCESS="2",
            BROKER_CONTROL_EXTRA_QUIET_WITNESS="1",
            FAKE_WITNESS_TX_PORT="2701",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        rows = [line.split("|") for line in self.trace.read_text().splitlines()]
        self.assertEqual(
            {row[0].rsplit(":", 1)[1] for row in rows},
            {"2101", "2201", "2301", "2401", "2501", "2601", "2701", "2801"},
        )
        extra = next(row for row in rows if row[0].endswith(":2801"))
        self.assertEqual(extra[1], "1")
        self.assertGreater(int(extra[2]), 1_000)
        self.assertTrue(extra[3].endswith("-control-extra-quiet"))
        run = json.loads(
            (self.runs / "bw-control-eight-endpoint" / "run.json").read_text()
        )
        self.assertEqual(run["topology"]["ue_processes"], 8)
        self.assertEqual(
            run["roles"]["control_extra_quiet_witness"],
            {
                "processes": 1,
                "ues_per_process": 1,
                "prelaunched": True,
                "quiet_for_whole_run": True,
                "endpoint_index": 8,
            },
        )
        verdict = self.result("bw-control-eight-endpoint")
        self.assertTrue(verdict["valid"])
        self.assertTrue(verdict["witness"]["service_ok"])
        self.assertEqual(verdict["sync_ues"], 8)
        self.assertEqual(verdict["topology"]["ue_processes"], 8)
        self.assertEqual(verdict["topology"]["ue_process_starts"], 8)
        self.assertEqual(
            verdict["control_extra_quiet_witness"],
            {"prelaunched": True, "endpoint_index": 8, "attempts": 0, "quiet": True},
        )

    def test_control_extra_quiet_endpoint_activity_is_invalid(self):
        result = self.run_script(
            run_id="bw-control-eight-endpoint-active",
            BROKER_ATTACK_PROCESSES="6",
            BROKER_CONTROL_EXTRA_QUIET_WITNESS="1",
            FAKE_WITNESS_TX_PORT="2701",
            FAKE_CONTROL_EXTRA_QUIET_ATTEMPT="1",
        )
        self.assertNotEqual(result.returncode, 0)
        verdict = self.result("bw-control-eight-endpoint-active")
        self.assertFalse(verdict["valid"])
        self.assertEqual(
            verdict["reason"], "control_extra_quiet_witness_activity_unexpected"
        )
        self.assertEqual(verdict["control_extra_quiet_witness"]["attempts"], 1)

    def test_control_extra_quiet_endpoint_is_scoped_to_six_load_processes(self):
        for mode, processes, value in (
            ("attack", "6", "1"),
            ("control", "4", "1"),
            ("control", "6", "2"),
        ):
            with self.subTest(mode=mode, processes=processes, value=value):
                run_id = f"bw-extra-scope-{mode}-{processes}-{value}"
                result = self.run_script(
                    mode,
                    run_id,
                    BROKER_ATTACK_PROCESSES=processes,
                    BROKER_CONTROL_EXTRA_QUIET_WITNESS=value,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.runs / run_id).exists())

    def test_seven_load_process_control_is_the_exact_eight_endpoint_comparator(self):
        result = self.run_script(
            run_id="bw-control-seven-load",
            BROKER_ATTACK_PROCESSES="7",
            BROKER_ATTACK_UES_PER_PROCESS="2",
            FAKE_WITNESS_TX_PORT="2801",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        verdict = self.result("bw-control-seven-load")
        self.assertTrue(verdict["valid"])
        self.assertEqual(verdict["sync_ues"], 8)
        self.assertEqual(verdict["topology"]["attack_or_quiet_processes"], 7)
        self.assertEqual(verdict["topology"]["ue_processes"], 8)
        self.assertTrue(verdict["witness"]["service_ok"])

    def test_same_witness_cycle_requires_denial_then_same_endpoint_recovery(self):
        result = self.run_script(
            "attack",
            "bw-same-witness-cycle",
            duration=35,
            BROKER_ATTACK_PROCESSES="7",
            BROKER_ATTACK_UES_PER_PROCESS="2",
            BROKER_ATTACK_MAX_DURATION_S="1",
            BROKER_ATTACK_MSG4_WAIT="0",
            BROKER_WITNESS_HONOR_REJECT="1",
            BROKER_SAME_WITNESS_CYCLE="1",
            FAKE_WITNESS_TX_PORT="2801",
            FAKE_ATTACK_KILL_DELAY_S="1",
            FAKE_SAME_WITNESS_RECOVERY_DELAY_S="4",
            FAKE_PING_TX="20",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        run = json.loads((self.runs / "bw-same-witness-cycle" / "run.json").read_text())
        self.assertEqual(
            run["roles"]["same_witness_cycle"],
            {
                "enabled": True,
                "endpoint_index": 8,
                "min_msg3_tx": 10,
                "min_distinct_nonzero_tc_rnti": 10,
                "min_msg3_span_ms": 30000,
                "recovery_deadline_s": 30,
                "min_ping_transmitted": 20,
                "required_ping_loss_pct": 0,
                "expected_last_attacker_stop_ms": 1000,
                "ping_budget_ms": 4000,
                "required_duration_ms": 35000,
            },
        )
        verdict = self.result("bw-same-witness-cycle")
        self.assertTrue(verdict["valid"])
        window = verdict["witness"]["attack_window"]
        self.assertEqual(window["attempts"], 10)
        self.assertEqual(window["distinct_fresh_identities"], 10)
        self.assertEqual(window["attempt_span_ms"], 30000)
        self.assertEqual(window["msg3_tx"], 10)
        self.assertEqual(window["distinct_nonzero_tc_rnti"], 10)
        self.assertEqual(window["msg3_span_ms"], 30000)
        self.assertEqual(window["boundary"], "all_attacker_kill_switches_observed")
        self.assertEqual(window["rrc_setup_complete"], 0)
        self.assertEqual(window["registration_accept"], 0)
        self.assertEqual(window["pdu_accept"], 0)
        cycle = verdict["same_witness_cycle"]
        self.assertTrue(cycle["attack_denial_ok"])
        self.assertEqual(cycle["attackers"]["post_boundary_attempts"], 0)
        self.assertEqual(cycle["attackers"]["msg3_tx_at_boundary"], 7)
        self.assertEqual(cycle["attackers"]["post_boundary_msg3_tx"], 0)
        self.assertTrue(cycle["recovery"]["within_deadline"])
        self.assertEqual(cycle["recovery"]["rrc_setup_complete"], 1)
        self.assertEqual(cycle["recovery"]["registration_accept"], 1)
        self.assertEqual(cycle["recovery"]["pdu_accept"], 1)
        self.assertTrue(cycle["recovery"]["ping_isolated"])
        self.assertEqual(cycle["recovery"]["ping"]["transmitted"], 20)
        self.assertEqual(cycle["recovery"]["ping"]["received"], 20)
        self.assertEqual(cycle["recovery"]["ping"]["loss_pct"], 0)
        self.assertTrue(cycle["recovery"]["service_ok"])
        self.assertTrue(cycle["passed"])

    def test_same_witness_cycle_fails_closed_on_weak_radio_probe_evidence(self):
        for run_id, msg3, span_ms, distinct_tc_rnti in (
            ("bw-same-msg3-too-few", "9", "30000", "9"),
            ("bw-same-msg3-too-short", "10", "29999", "10"),
            ("bw-same-msg3-too-few-rntis", "10", "30000", "9"),
        ):
            with self.subTest(run_id=run_id):
                result = self.run_script(
                    "attack",
                    run_id,
                    duration=35,
                    BROKER_ATTACK_PROCESSES="7",
                    BROKER_ATTACK_MAX_DURATION_S="1",
                    BROKER_WITNESS_HONOR_REJECT="1",
                    BROKER_SAME_WITNESS_CYCLE="1",
                    FAKE_WITNESS_TX_PORT="2801",
                    FAKE_ATTACK_KILL_DELAY_S="1",
                    FAKE_SAME_WITNESS_MSG3=msg3,
                    FAKE_SAME_WITNESS_MSG3_SPAN_MS=span_ms,
                    FAKE_SAME_WITNESS_DISTINCT_TC_RNTI=distinct_tc_rnti,
                    FAKE_SAME_WITNESS_RECOVERY_DELAY_S="3",
                    FAKE_PING_TX="20",
                )
                self.assertNotEqual(result.returncode, 0)
                verdict = self.result(run_id)
                self.assertEqual(verdict["reason"], "same_witness_attack_denial_missing")
                self.assertEqual(verdict["witness"]["attack_window"]["attempts"], 10)
                self.assertEqual(
                    verdict["witness"]["attack_window"]["attempt_span_ms"], 30000
                )
                self.assertFalse(verdict["same_witness_cycle"]["passed"])

    def test_same_witness_cycle_fails_closed_on_recovery_ping_requirement(self):
        for run_id, tx, rx, loss in (
            ("bw-same-ping-short", "19", "19", "0"),
            ("bw-same-ping-loss", "20", "19", "5"),
        ):
            with self.subTest(run_id=run_id):
                result = self.run_script(
                    "attack",
                    run_id,
                    duration=35,
                    BROKER_ATTACK_PROCESSES="7",
                    BROKER_ATTACK_MAX_DURATION_S="1",
                    BROKER_WITNESS_HONOR_REJECT="1",
                    BROKER_SAME_WITNESS_CYCLE="1",
                    FAKE_WITNESS_TX_PORT="2801",
                    FAKE_ATTACK_KILL_DELAY_S="1",
                    FAKE_SAME_WITNESS_RECOVERY_DELAY_S="3",
                    FAKE_PING_TX=tx,
                    FAKE_PING_RX=rx,
                    FAKE_PING_LOSS=loss,
                )
                self.assertNotEqual(result.returncode, 0)
                verdict = self.result(run_id)
                self.assertEqual(verdict["reason"], "same_witness_recovery_missing")
                self.assertFalse(
                    verdict["same_witness_cycle"]["recovery"]["service_ok"]
                )

    def test_same_witness_cycle_rejects_attacker_activity_after_boundary(self):
        for run_id, env_name, result_name in (
            (
                "bw-same-attacker-late-attempt",
                "FAKE_ATTACK_POST_BOUNDARY_PORT",
                "post_boundary_attempts",
            ),
            (
                "bw-same-attacker-late-msg3",
                "FAKE_ATTACK_POST_BOUNDARY_MSG3_PORT",
                "post_boundary_msg3_tx",
            ),
        ):
            with self.subTest(run_id=run_id):
                result = self.run_script(
                    "attack",
                    run_id,
                    duration=35,
                    BROKER_ATTACK_PROCESSES="7",
                    BROKER_ATTACK_MAX_DURATION_S="1",
                    BROKER_WITNESS_HONOR_REJECT="1",
                    BROKER_SAME_WITNESS_CYCLE="1",
                    FAKE_WITNESS_TX_PORT="2801",
                    FAKE_ATTACK_KILL_DELAY_S="1",
                    FAKE_SAME_WITNESS_RECOVERY_DELAY_S="3",
                    FAKE_PING_TX="20",
                    **{env_name: "2101"},
                )
                self.assertNotEqual(result.returncode, 0)
                verdict = self.result(run_id)
                self.assertEqual(verdict["reason"], "attacker_activity_after_boundary")
                self.assertGreater(
                    verdict["same_witness_cycle"]["attackers"][result_name], 0
                )

    def test_same_witness_cycle_flag_is_strictly_scoped(self):
        cases = (
            ("control", "7", "1", "", "bw-same-control"),
            ("attack", "6", "1", "", "bw-same-six"),
            ("attack", "7", "0", "", "bw-seven-no-cycle"),
            ("attack", "7", "1", "3000", "bw-same-separate-recovery"),
            ("attack", "7", "2", "", "bw-same-invalid-flag"),
        )
        for mode, processes, flag, recovery_delay, run_id in cases:
            with self.subTest(run_id=run_id):
                result = self.run_script(
                    mode,
                    run_id,
                    BROKER_ATTACK_PROCESSES=processes,
                    BROKER_SAME_WITNESS_CYCLE=flag,
                    BROKER_RECOVERY_WITNESS_DELAY_MS=recovery_delay,
                    BROKER_ATTACK_MAX_DURATION_S="1",
                    BROKER_WITNESS_HONOR_REJECT="1",
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.runs / run_id).exists())

        for run_id, max_duration, honor_reject in (
            ("bw-same-no-kill-switch", "0", "1"),
            ("bw-same-no-retry", "1", "0"),
        ):
            with self.subTest(run_id=run_id):
                result = self.run_script(
                    "attack",
                    run_id,
                    BROKER_ATTACK_PROCESSES="7",
                    BROKER_SAME_WITNESS_CYCLE="1",
                    BROKER_ATTACK_MAX_DURATION_S=max_duration,
                    BROKER_WITNESS_HONOR_REJECT=honor_reject,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.runs / run_id).exists())

        result = self.run_script(
            "attack",
            "bw-same-duration-too-short",
            duration=34,
            BROKER_ATTACK_PROCESSES="7",
            BROKER_SAME_WITNESS_CYCLE="1",
            BROKER_ATTACK_MAX_DURATION_S="1",
            BROKER_WITNESS_HONOR_REJECT="1",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires -d >= 35 seconds", result.stderr)
        self.assertFalse((self.runs / "bw-same-duration-too-short").exists())

    def test_attack_assigns_four_attackers_and_no_attach_is_valid_outcome(self):
        result = self.run_script(
            "attack",
            "bw-attack",
            FAKE_WITNESS_OK="0",
            BROKER_ATTACK_MSG4_WAIT="0",
            BROKER_ATTACK_MAX_DURATION_S="30",
            BROKER_ATTACK_START_DELAY_MS="1000",
            BROKER_ATTACK_START_STRIDE_MS="100",
            BROKER_ATTACK_PHASE_MS="75",
            BROKER_ATTACK_UES_PER_PROCESS="2",
            BROKER_WITNESS_HONOR_REJECT="1",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        rows = [line.split("|") for line in self.trace.read_text().splitlines()]
        roles = {row[0].rsplit(":", 1)[1]: row for row in rows}
        for index, port in enumerate(("2101", "2201", "2301", "2401")):
            self.assertEqual(roles[port][1:3], ["2", str(1000 + index * 100)])
            self.assertEqual(roles[port][4:7], ["30", "0", "0"])
            self.assertEqual(roles[port][7:9], ["2", "2"])
            self.assertEqual(roles[port][9:11], ["1", "10"])
            self.assertEqual(roles[port][11], "75")
        self.assertEqual(roles["2501"][1], "1")
        self.assertEqual(roles["2501"][4:7], ["0", "1", "1"])
        self.assertEqual(roles["2501"][7:9], ["1", "1"])
        self.assertEqual(roles["2501"][9:11], ["0", "1000"])
        self.assertEqual(roles["2501"][11], "0")
        verdict = self.result("bw-attack")
        self.assertTrue(verdict["valid"])
        self.assertGreater(verdict["attacker_attempts"], 0)
        self.assertEqual(verdict["load_ue_attempts"], verdict["attacker_attempts"])
        self.assertFalse(verdict["witness"]["attached"])
        run = json.loads((self.runs / "bw-attack" / "run.json").read_text())
        self.assertEqual(
            run["roles"],
            {
                "attacker": {"processes": 4, "ues_per_process": 2, "msg4_wait": 0, "max_duration_s": 30, "start_delay_ms": 1000, "start_stride_ms": 100, "phase_ms": 75, "honor_reject": 0},
                "control_load": {"processes": 4, "ues_per_process": 2, "msg4_wait": 1, "max_duration_s": 0, "phase_ms": 0, "honor_reject": 0},
                "witness": {"processes": 1, "ues_per_process": 1, "msg4_wait": 1, "max_duration_s": 0, "phase_ms": 0, "honor_reject": 1},
            },
        )

    def test_attack_prelaunches_recovery_on_a_separate_endpoint(self):
        result = self.run_script(
            "attack",
            "bw-recovery-witness",
            duration=5,
            BROKER_ATTACK_MSG4_WAIT="0",
            BROKER_ATTACK_MAX_DURATION_S="1",
            BROKER_ATTACK_START_DELAY_MS="1000",
            BROKER_ATTACK_START_STRIDE_MS="100",
            BROKER_RECOVERY_WITNESS_DELAY_MS="3000",
            BROKER_WITNESS_HONOR_REJECT="1",
            FAKE_PRIMARY_WITNESS_OK="0",
            FAKE_RECOVERY_WITNESS_OK="1",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        rows = [line.split("|") for line in self.trace.read_text().splitlines()]
        ports = [row[0].rsplit(":", 1)[1] for row in rows]
        self.assertEqual(
            set(ports), {"2101", "2201", "2301", "2401", "2501", "2601"}
        )
        primary = next(row for row in rows if row[0].endswith(":2501"))
        recovery = next(row for row in rows if row[0].endswith(":2601"))
        self.assertEqual(primary[1:3], ["1", "0"])
        self.assertEqual(recovery[1:3], ["1", "3000"])
        self.assertEqual(recovery[4:12], ["0", "1", "1", "1", "1", "0", "1000", "0"])
        self.assertTrue(recovery[3].endswith("-recovery"))

        run = json.loads((self.runs / "bw-recovery-witness" / "run.json").read_text())
        self.assertEqual(run["topology"]["witness_processes"], 2)
        self.assertEqual(run["topology"]["witness_ues"], 2)
        self.assertEqual(run["topology"]["ue_processes"], 6)
        self.assertEqual(run["topology"]["planned_ue_process_starts"], 6)
        self.assertEqual(
            run["roles"]["recovery_witness"],
            {
                "processes": 1,
                "ues_per_process": 1,
                "msg4_wait": 1,
                "max_duration_s": 0,
                "delay_ms": 3000,
                "phase_ms": 0,
                "honor_reject": 1,
                "prelaunched": True,
                "endpoint_index": 6,
            },
        )

        verdict = self.result("bw-recovery-witness")
        self.assertEqual(verdict["sync_ues"], 6)
        self.assertEqual(verdict["topology"]["ue_processes"], 6)
        self.assertEqual(verdict["topology"]["ue_process_starts"], 6)
        self.assertFalse(verdict["witness"]["attached"])
        self.assertFalse(verdict["witness"]["ping_ok"])
        self.assertFalse(verdict["witness"]["service_ok"])
        self.assertTrue(verdict["recovery_witness"]["prelaunched"])
        self.assertEqual(verdict["recovery_witness"]["endpoint_index"], 6)
        self.assertTrue(verdict["recovery_witness"]["started"])
        self.assertTrue(verdict["recovery_witness"]["sync_ready"])
        self.assertEqual(verdict["recovery_witness"]["pre_attack_attempts"], 0)
        self.assertEqual(verdict["recovery_witness"]["pre_phase_attempts"], 0)
        self.assertTrue(verdict["recovery_witness"]["attached"])
        self.assertTrue(verdict["recovery_witness"]["ping_ok"])
        self.assertTrue(verdict["recovery_witness"]["ping_isolated"])
        self.assertTrue(verdict["recovery_witness"]["service_ok"])
        self.assertFalse((self.runs / "bw-recovery-witness" / "witness_ping.txt").exists())
        self.assertTrue((self.runs / "bw-recovery-witness" / "recovery_witness_ping.txt").is_file())
        self.assertEqual(len(verdict["teardown"]["ue_exit_statuses"]), 6)

    def test_attack_window_is_frozen_before_post_attack_primary_success(self):
        result = self.run_script(
            "attack",
            "bw-recovery-freeze",
            duration=7,
            BROKER_ATTACK_MAX_DURATION_S="1",
            BROKER_ATTACK_START_DELAY_MS="1000",
            BROKER_ATTACK_START_STRIDE_MS="100",
            BROKER_RECOVERY_WITNESS_DELAY_MS="5000",
            FAKE_PRIMARY_WITNESS_OK="0",
            FAKE_PRIMARY_POST_ATTACK_DELAY_S="3",
            FAKE_RECOVERY_WITNESS_OK="1",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        verdict = self.result("bw-recovery-freeze")
        self.assertFalse(verdict["witness"]["service_ok"])
        attack_window = verdict["witness"]["attack_window"]
        self.assertTrue(attack_window["frozen"])
        self.assertEqual(
            attack_window["boundary"], "all_attacker_kill_switches_observed"
        )
        self.assertFalse(attack_window["service_ok"])
        self.assertEqual(attack_window["rrc_setup_complete"], 0)
        self.assertEqual(attack_window["registration_accept"], 0)
        self.assertEqual(attack_window["pdu_accept"], 0)
        self.assertEqual(attack_window["ping_received"], 0)
        post_boundary = verdict["witness"]["post_boundary_activity"]
        self.assertTrue(post_boundary["observed"])
        self.assertEqual(post_boundary["registration_accept"], 1)
        self.assertEqual(post_boundary["pdu_accept"], 1)
        self.assertFalse(verdict["recovery_witness"]["ping_isolated"])
        self.assertFalse(verdict["recovery_witness"]["service_ok"])

    def test_recovery_missing_startup_sync_is_an_infrastructure_failure(self):
        run_id = "bw-recovery-no-sync"
        result = self.run_script(
            "attack",
            run_id,
            duration=5,
            BROKER_ATTACK_MAX_DURATION_S="1",
            BROKER_ATTACK_START_DELAY_MS="1000",
            BROKER_ATTACK_START_STRIDE_MS="100",
            BROKER_RECOVERY_WITNESS_DELAY_MS="3000",
            BROKER_SYNC_TIMEOUT_S="1",
            FAKE_PRIMARY_WITNESS_OK="0",
            FAKE_RECOVERY_WITNESS_OK="1",
            FAKE_NO_SYNC_RUN=f"u6-{run_id}-recovery",
        )
        self.assertNotEqual(result.returncode, 0)
        verdict = self.result(run_id)
        self.assertFalse(verdict["valid"])
        self.assertEqual(verdict["reason"], "infrastructure_failure")
        self.assertFalse(verdict["startup"]["sync_ready"])
        self.assertFalse(verdict["recovery_witness"]["started"])
        self.assertFalse(verdict["recovery_witness"]["sync_ready"])
        self.assertEqual(len(verdict["teardown"]["ue_exit_statuses"]), 6)

    def test_recovery_attempt_during_attack_is_an_infrastructure_failure(self):
        run_id = "bw-recovery-early-attempt"
        result = self.run_script(
            "attack",
            run_id,
            duration=5,
            BROKER_ATTACK_MAX_DURATION_S="1",
            BROKER_ATTACK_START_DELAY_MS="1000",
            BROKER_ATTACK_START_STRIDE_MS="100",
            BROKER_RECOVERY_WITNESS_DELAY_MS="3000",
            FAKE_RECOVERY_EARLY_ATTEMPT="1",
        )
        self.assertNotEqual(result.returncode, 0)
        verdict = self.result(run_id)
        self.assertFalse(verdict["valid"])
        self.assertEqual(verdict["reason"], "infrastructure_failure")
        self.assertGreater(verdict["recovery_witness"]["pre_attack_attempts"], 0)

    def test_recovery_attempt_during_settle_is_an_infrastructure_failure(self):
        run_id = "bw-recovery-settle-attempt"
        result = self.run_script(
            "attack",
            run_id,
            duration=7,
            BROKER_ATTACK_MAX_DURATION_S="1",
            BROKER_ATTACK_START_DELAY_MS="1000",
            BROKER_ATTACK_START_STRIDE_MS="100",
            BROKER_RECOVERY_WITNESS_DELAY_MS="5000",
            FAKE_RECOVERY_SETTLE_ATTEMPT_DELAY_S="2",
        )
        self.assertNotEqual(result.returncode, 0)
        verdict = self.result(run_id)
        self.assertFalse(verdict["valid"])
        self.assertEqual(verdict["reason"], "infrastructure_failure")
        self.assertEqual(verdict["recovery_witness"]["pre_attack_attempts"], 0)
        self.assertGreater(verdict["recovery_witness"]["pre_phase_attempts"], 0)

    def test_recovery_requires_every_attacker_quiet_stop_marker(self):
        result = self.run_script(
            "attack",
            "bw-recovery-not-quiet",
            duration=5,
            BROKER_ATTACK_MAX_DURATION_S="1",
            BROKER_ATTACK_START_DELAY_MS="1000",
            BROKER_ATTACK_START_STRIDE_MS="100",
            BROKER_RECOVERY_WITNESS_DELAY_MS="3000",
            FAKE_NO_KILL_SWITCH_PORT="2401",
        )
        self.assertNotEqual(result.returncode, 0)
        verdict = self.result("bw-recovery-not-quiet")
        self.assertFalse(verdict["valid"])
        self.assertFalse(verdict["recovery_witness"]["started"])
        self.assertFalse(verdict["recovery_witness"]["attackers_quiet"])
        self.assertEqual(verdict["topology"]["ue_process_starts"], 6)
        self.assertEqual(len(self.trace.read_text().splitlines()), 6)

    def test_recovery_witness_requires_attack_mode_and_post_attack_delay(self):
        cases = (
            (
                "control",
                "bw-recovery-control",
                {
                    "BROKER_ATTACK_MAX_DURATION_S": "1",
                    "BROKER_RECOVERY_WITNESS_DELAY_MS": "3000",
                },
            ),
            (
                "attack",
                "bw-recovery-one-attacker",
                {
                    "BROKER_ATTACK_PROCESSES": "1",
                    "BROKER_ATTACK_MAX_DURATION_S": "1",
                    "BROKER_RECOVERY_WITNESS_DELAY_MS": "3000",
                },
            ),
            (
                "attack",
                "bw-recovery-no-stop",
                {"BROKER_RECOVERY_WITNESS_DELAY_MS": "3000"},
            ),
            (
                "attack",
                "bw-recovery-too-early",
                {
                    "BROKER_ATTACK_MAX_DURATION_S": "1",
                    "BROKER_ATTACK_START_DELAY_MS": "1000",
                    "BROKER_ATTACK_START_STRIDE_MS": "100",
                    "BROKER_RECOVERY_WITNESS_DELAY_MS": "2300",
                },
            ),
        )
        for mode, run_id, overrides in cases:
            with self.subTest(run_id=run_id):
                result = self.run_script(mode, run_id, **overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.runs / run_id).exists())

    def test_recovery_rejects_a_broker_without_the_recovery_endpoint(self):
        broker5 = self.root / "broker5.py"
        broker5.write_text("tcp://127.0.0.1:2501 tcp://127.0.0.1:2500\n")
        result = self.run_script(
            "attack",
            "bw-recovery-six-endpoints",
            duration=5,
            BROKER_PY=str(broker5),
            BROKER_ATTACK_MAX_DURATION_S="1",
            BROKER_RECOVERY_WITNESS_DELAY_MS="3000",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("broker does not expose UE 6 ports 2601/2600", result.stderr)
        self.assertFalse((self.runs / "bw-recovery-six-endpoints").exists())

    def test_six_attack_process_recovery_uses_eighth_endpoint(self):
        result = self.run_script(
            "attack",
            "bw-recovery-eight-endpoint",
            duration=5,
            BROKER_ATTACK_PROCESSES="6",
            BROKER_ATTACK_MAX_DURATION_S="1",
            BROKER_ATTACK_START_DELAY_MS="1000",
            BROKER_RECOVERY_WITNESS_DELAY_MS="3000",
            FAKE_WITNESS_TX_PORT="2701",
            FAKE_RECOVERY_WITNESS_TX_PORT="2801",
            FAKE_PRIMARY_WITNESS_OK="0",
            FAKE_RECOVERY_WITNESS_OK="1",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        rows = [line.split("|") for line in self.trace.read_text().splitlines()]
        self.assertEqual(
            {row[0].rsplit(":", 1)[1] for row in rows},
            {"2101", "2201", "2301", "2401", "2501", "2601", "2701", "2801"},
        )
        verdict = self.result("bw-recovery-eight-endpoint")
        self.assertEqual(verdict["sync_ues"], 8)
        self.assertEqual(verdict["topology"]["ue_processes"], 8)
        self.assertEqual(verdict["topology"]["ue_process_starts"], 8)
        self.assertEqual(verdict["recovery_witness"]["endpoint_index"], 8)
        self.assertEqual(verdict["recovery_witness"]["pre_attack_attempts"], 0)
        self.assertEqual(verdict["recovery_witness"]["pre_phase_attempts"], 0)
        self.assertTrue(verdict["recovery_witness"]["ping_isolated"])
        self.assertTrue(verdict["recovery_witness"]["service_ok"])

    def test_role_knobs_are_validated_before_run_creation(self):
        for index, (name, value) in enumerate(
            (
                ("BROKER_ATTACK_MSG4_WAIT", "2"),
                ("BROKER_ATTACK_MAX_DURATION_S", "-1"),
                ("BROKER_ATTACK_MAX_DURATION_S", "86401"),
                ("BROKER_ATTACK_START_DELAY_MS", "-1"),
                ("BROKER_ATTACK_START_STRIDE_MS", "x"),
                ("BROKER_ATTACK_PHASE_MS", "-1"),
                ("BROKER_ATTACK_PHASE_MS", "5001"),
                ("BROKER_ATTACK_PHASE_MS", "bad"),
                ("BROKER_ATTACK_UES_PER_PROCESS", "0"),
                ("BROKER_ATTACK_UES_PER_PROCESS", "17"),
                ("BROKER_ATTACK_PROCESSES", "0"),
                ("BROKER_ATTACK_PROCESSES", "5"),
                ("BROKER_ATTACK_PROCESSES", "8"),
                ("BROKER_ATTACK_PROCESSES", "17"),
                ("BROKER_WITNESS_HONOR_REJECT", "yes"),
            ),
            1,
        ):
            with self.subTest(name=name, value=value):
                run_id = f"bw-invalid-role-{index}"
                result = self.run_script(run_id=run_id, **{name: value})
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.runs / run_id).exists())

    def test_existing_run_is_never_overwritten(self):
        existing = self.runs / "bw-existing"
        existing.mkdir(parents=True)
        marker = existing / "keep"
        marker.write_text("original\n")
        result = self.run_script(run_id="bw-existing")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), "original\n")

    def test_non_zmq_device_is_rejected_before_run_creation_or_process_start(self):
        result = self.run_script(run_id="bw-ota-unsafe", DEVICE="usrpb210")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("broker witness is ZMQ-only", result.stderr)
        self.assertFalse((self.runs / "bw-ota-unsafe").exists())
        self.assertFalse(self.trace.exists())

    def test_background_gnb_child_cannot_inherit_the_run_lock_fd(self):
        pidfile = self.root / "gnb-child.pid"
        fd_state = self.root / "gnb-child.fd-state"
        restart = (
            f"if {{ true >&9; }} 2>/dev/null; then echo open; else echo closed; fi "
            f"> {shlex.quote(str(fd_state))}; "
            f"sleep 30 & echo $! > {shlex.quote(str(pidfile))}"
        )
        first = self.run_script(run_id="bw-lock-1", GNB_RESTART_CMD=restart)
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        self.assertEqual(fd_state.read_text().strip(), "closed")
        os.kill(int(pidfile.read_text()), 15)

    def test_every_long_lived_child_boundary_closes_the_run_lock_fd(self):
        source = SCRIPT.read_text()
        required = (
            '"$SETSID_BIN" "$@" 9>&-',
            '"$@" 9>&-',
            'bash -c "$GNB_STOP_CMD" 9>&-',
            'bash -c "$GNB_RESTART_CMD" 9>&-',
            'bash -c "$GNB_READY_CMD" 9>&-',
            '9>&- >"$PING_FILE"',
        )
        for fragment in required:
            self.assertIn(fragment, source)

    def test_owned_gnb_is_stopped_on_success_and_failure(self):
        source = SCRIPT.read_text()
        self.assertIn("cleanup()", source)

        successful_trace = self.root / "gnb-success.trace"
        stop = f"echo stop >> {shlex.quote(str(successful_trace))}"
        result = self.run_script(run_id="bw-gnb-cleanup", GNB_STOP_CMD=stop)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(successful_trace.read_text().splitlines(), ["stop", "stop"])

        failed_trace = self.root / "gnb-failed-ready.trace"
        stop = f"echo stop >> {shlex.quote(str(failed_trace))}"
        result = self.run_script(
            run_id="bw-gnb-ready-fail", GNB_STOP_CMD=stop,
            GNB_READY_CMD="false", GNB_READY_TIMEOUT_S="1",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(failed_trace.read_text().splitlines(), ["stop", "stop"])

    def test_normal_pool_uses_the_normal_configuration_gnb_lifecycle(self):
        source = SCRIPT.read_text()
        block = source.split("if (( BROKER_NORMAL_POOL_QUALIFICATION )); then", 1)[1].split("fi", 1)[0]
        for name in ("GNB_CONFIG", "GNB_STOP_CMD", "GNB_RESTART_CMD", "GNB_READY_CMD"):
            self.assertIn(f"NORMAL_UE_{name}", block)
        self.assertIn("NORMAL_UE_ATTACK_BIN", block)

    def test_harness_launches_ue_endpoints_before_the_broker(self):
        source = SCRIPT.read_text()
        launch_ues = source.index('echo "== launching $BROKER_ATTACK_PROCESSES')
        start_broker = source.index('echo "== starting the broker after all $TOTAL_UE_PROCESSES')
        self.assertLess(launch_ues, start_broker)

    def test_one_attack_process_topology_uses_second_port_as_witness(self):
        broker2 = self.root / "broker2.py"
        broker2.write_text("tcp://127.0.0.1:2201 tcp://127.0.0.1:2200\n")
        result = self.run_script(
            run_id="bw-two-process",
            BROKER_ATTACK_PROCESSES="1",
            BROKER_ATTACK_UES_PER_PROCESS="6",
            BROKER_PY=str(broker2),
            FAKE_WITNESS_TX_PORT="2201",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        rows = [line.split("|") for line in self.trace.read_text().splitlines()]
        self.assertEqual(
            {row[0].rsplit(":", 1)[1] for row in rows},
            {"2101", "2201"},
        )
        verdict = self.result("bw-two-process")
        self.assertEqual(verdict["sync_ues"], 2)
        self.assertEqual(verdict["topology"], {
            "attack_or_quiet_processes": 1,
            "attack_or_quiet_ues": 6,
            "witness_processes": 1,
            "witness_ues": 1,
            "ue_processes": 2,
            "ue_process_starts": 2,
        })
        self.assertEqual(len(verdict["teardown"]["ue_exit_statuses"]), 2)

    def test_two_ue_flowgraph_has_only_required_endpoints(self):
        source = BROKER2.read_text()
        for port in ("2000", "2001", "2100", "2101", "2200", "2201"):
            self.assertIn(f"tcp://127.0.0.1:{port}", source)
        self.assertIn("blocks.throttle", source)
        self.assertIn("(ue1_ul, 0), (uplink, 0)", source)
        self.assertIn("(ue2_ul, 0), (uplink, 1)", source)
        reset = source.split("def reset_witness_uplink", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("signal.SIGUSR1", source)
        self.assertIn("RSS_BROKER_WITNESS_UPLINK_RESET port=2201", source)
        self.assertIn("zeromq.req_source", reset)
        self.assertNotIn("zeromq.rep_sink", reset)

    def test_five_ue_flowgraph_resets_only_the_witness_uplink(self):
        source = BROKER5.read_text()
        reset = source.split("def reset_witness_uplink", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("signal.SIGUSR1", source)
        self.assertIn("RSS_BROKER_WITNESS_UPLINK_RESET port=2501", source)
        self.assertIn("self.zeromq_req_source_3", reset)
        self.assertIn("self.blocks_mul_ul5", reset)
        self.assertIn("zeromq.req_source", reset)
        self.assertNotIn("zeromq.rep_sink", reset)

    def test_six_attack_process_topology_uses_seventh_port_as_witness(self):
        broker7 = self.root / "broker7.py"
        broker7.write_text("tcp://127.0.0.1:2701 tcp://127.0.0.1:2700\n")
        result = self.run_script(
            run_id="bw-seven-process",
            BROKER_ATTACK_PROCESSES="6",
            BROKER_PY=str(broker7),
            FAKE_WITNESS_TX_PORT="2701",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        rows = [line.split("|") for line in self.trace.read_text().splitlines()]
        self.assertEqual(
            {row[0].rsplit(":", 1)[1] for row in rows},
            {"2101", "2201", "2301", "2401", "2501", "2601", "2701"},
        )
        verdict = self.result("bw-seven-process")
        self.assertEqual(verdict["sync_ues"], 7)
        self.assertEqual(verdict["topology"]["ue_processes"], 7)
        self.assertEqual(len(verdict["teardown"]["ue_exit_statuses"]), 7)

    def test_seven_ue_flowgraph_adds_only_the_two_required_endpoints(self):
        source = BROKER7.read_text()
        for fragment in (
            "tcp://127.0.0.1:2601",
            "tcp://127.0.0.1:2600",
            "tcp://127.0.0.1:2701",
            "tcp://127.0.0.1:2700",
            "(self.blocks_add_xx_0, 5)",
            "(self.blocks_add_xx_0, 6)",
        ):
            self.assertIn(fragment, source)

    def test_eight_ue_flowgraph_adds_only_the_recovery_endpoint(self):
        source = BROKER8.read_text()
        for fragment in (
            "from multi_ue_7ue import main, multi_ue_7ue",
            "tcp://127.0.0.1:2801",
            "tcp://127.0.0.1:2800",
            "(self.blocks_add_xx_0, 7)",
        ):
            self.assertIn(fragment, source)

    def test_broker_or_ue_early_exit_is_invalid(self):
        broker = self.run_script("attack", "bw-broker-exit", FAKE_BROKER_EXIT="1")
        self.assertNotEqual(broker.returncode, 0)
        self.assertFalse(self.result("bw-broker-exit")["valid"])

        ue = self.run_script("attack", "bw-ue-exit", FAKE_UE_EXIT_PORT="2101")
        self.assertNotEqual(ue.returncode, 0)
        self.assertFalse(self.result("bw-ue-exit")["valid"])

    def test_missing_sync_stops_before_the_observation_window(self):
        started = time.monotonic()
        result = self.run_script(
            "attack",
            "bw-sync-timeout",
            duration=10,
            BROKER_SYNC_TIMEOUT_S="1",
            FAKE_NO_SYNC_PORT="2101",
        )
        elapsed = time.monotonic() - started
        self.assertNotEqual(result.returncode, 0)
        self.assertLess(elapsed, 7, result.stderr + result.stdout)
        verdict = self.result("bw-sync-timeout")
        self.assertFalse(verdict["valid"])
        self.assertEqual(verdict["reason"], "infrastructure_failure")
        self.assertEqual(verdict["sync_ues"], 4)
        self.assertFalse(verdict["startup"]["sync_ready"])
        self.assertTrue(verdict["startup"]["sync_timeout"])

    def test_teardown_sigsegv_is_recorded_without_reclassifying_observation(self):
        result = self.run_script(
            run_id="bw-teardown-segv", FAKE_BROKER_STOP_STATUS="139"
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        verdict = self.result("bw-teardown-segv")
        self.assertTrue(verdict["valid"])
        self.assertEqual(verdict["teardown"]["broker_exit_status"], 139)
        self.assertTrue(verdict["teardown"]["broker_sigsegv"])

    def test_ue_teardown_crash_marker_does_not_pollute_observation_crashes(self):
        result = self.run_script(
            run_id="bw-ue-teardown-segv", FAKE_UE_TEARDOWN_CRASH_PORT="2101"
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        verdict = self.result("bw-ue-teardown-segv")
        self.assertTrue(verdict["valid"])
        self.assertEqual(verdict["crash_markers"], 0)
        self.assertEqual(verdict["teardown"]["ue_sigsegv_count"], 1)
        self.assertIn(
            "Segmentation fault",
            (self.runs / "bw-ue-teardown-segv" / "ue1.log").read_text(),
        )

    def test_control_without_service_fails_and_unrelated_process_survives(self):
        sentinel = subprocess.Popen([shutil.which("sleep"), "30"])
        try:
            result = self.run_script(run_id="bw-no-service", FAKE_WITNESS_OK="0")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(self.result("bw-no-service")["valid"])
            self.assertIsNone(sentinel.poll())
        finally:
            sentinel.terminate()
            sentinel.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
