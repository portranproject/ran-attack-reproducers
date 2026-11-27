import json
import os
import pathlib
import re
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SAME_CELL = ROOT / "workloads/normal-ue/bin/same-cell-run"
PHASE = ROOT / "reproducers/blind-dos/bin/blind-p5-phase"
BROKER = ROOT / "reproducers/rrc-signaling-storm/bin/rss-broker-witness"
CTL = ROOT / "tools" / "ctl.sh"


def function_text(path, name):
    source = path.read_text()
    match = re.search(rf"^{name}\(\) \{{\n.*?^\}}$", source, re.S | re.M)
    if not match:
        raise AssertionError(f"{name} not found in {path}")
    return match.group(0)


class NormalUeHoldTests(unittest.TestCase):
    def test_runners_default_to_no_hold_and_campaigns_set_it(self):
        same = SAME_CELL.read_text()
        broker = BROKER.read_text()
        self.assertIn("SAME_CELL_NORMAL_PRE_HOLD_S=${SAME_CELL_NORMAL_PRE_HOLD_S:-0}", same)
        self.assertIn("SAME_CELL_NORMAL_POST_HOLD_S=${SAME_CELL_NORMAL_POST_HOLD_S:-0}", same)
        self.assertIn("BROKER_NORMAL_PRE_HOLD_S=${BROKER_NORMAL_PRE_HOLD_S:-0}", broker)
        self.assertIn("BROKER_NORMAL_POST_HOLD_S=${BROKER_NORMAL_POST_HOLD_S:-0}", broker)
        campaign = CTL.read_text().split("same_cell_campaign()", 1)[1].split(
            "list_attacks()", 1)[0]
        for line in (
            "export SAME_CELL_NORMAL_PRE_HOLD_S=${SAME_CELL_NORMAL_PRE_HOLD_S:-30}",
            "export SAME_CELL_NORMAL_POST_HOLD_S=${SAME_CELL_NORMAL_POST_HOLD_S:-90}",
            "export BROKER_NORMAL_PRE_HOLD_S=${BROKER_NORMAL_PRE_HOLD_S:-30}",
            "export BROKER_NORMAL_POST_HOLD_S=${BROKER_NORMAL_POST_HOLD_S:-90}",
        ):
            self.assertIn(line, campaign)

    def test_zero_hold_keeps_the_previous_behavior(self):
        for path, name in ((SAME_CELL, "normal_hold"), (BROKER, "normal_hold")):
            body = function_text(path, name)
            self.assertIn("(( seconds > 0 )) || return 0", body)
            with tempfile.TemporaryDirectory() as directory:
                output = pathlib.Path(directory)
                result = subprocess.run(
                    ["bash", "-c", self.hold_harness(path, 0, output)], text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse((output / "normal-hold.tsv").exists())
                result = subprocess.run(
                    ["bash", "-c", self.hold_harness(path, 3, output)], text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                rows = (output / "normal-hold.tsv").read_text().splitlines()
                self.assertEqual(len(rows), 3)
                self.assertTrue(all(row.endswith("\t5") for row in rows), rows)

    def hold_harness(self, path, seconds, output):
        body = function_text(path, "normal_hold")
        prelude = f"""
set -euo pipefail
SECONDS=0
DEADLINE=1000
COUNT=5
NORMAL_PID=1
BROKER_PID=1
RUN_OUT={output}
OUT={output}
health() {{ echo 5; }}
normal_pool_health() {{ echo 5; }}
is_running() {{ return 0; }}
all_active_ues_running() {{ return 0; }}
sleep() {{ SECONDS=$((SECONDS + 1)); }}
date() {{ echo 1700000000000000000; }}
{body}
normal_hold {seconds} pre
"""
        return prelude

    def test_same_cell_holds_surround_the_detector_window(self):
        source = SAME_CELL.read_text()
        run = source.split("if [[ $ACTION == run ]]; then", 1)[1].split(
            "if [[ $ACTION == start ]]; then", 1)[0]
        observation = 'until [[ -f $OBSERVATION_READY_FILE'
        pre = 'normal_hold "$SAME_CELL_NORMAL_PRE_HOLD_S" pre'
        ready = "marker_publish normal.ready"
        release = "marker_publish attack.release"
        post = 'normal_hold "$SAME_CELL_NORMAL_POST_HOLD_S" post'
        recovery = "NORMAL_HEALTH_BEFORE_TEARDOWN=true"
        self.assertLess(run.index(observation), run.index(pre))
        self.assertLess(run.index(pre), run.index(ready))
        self.assertLess(run.index(recovery), run.index(post))
        self.assertLess(run.index(post), run.index(release))

    def test_broker_holds_stay_inside_the_runner_deadline(self):
        source = BROKER.read_text()
        pre = 'normal_hold "$BROKER_NORMAL_PRE_HOLD_S" pre'
        attack = "if select_persistent_attack warmup"
        post = 'normal_hold "$BROKER_NORMAL_POST_HOLD_S" post'
        teardown = 'is_running "$BROKER_PID" || BROKER_EARLY_EXIT=1'
        self.assertLess(source.index(pre), source.index(attack))
        self.assertLess(source.index(post), source.index(teardown))
        body = function_text(BROKER, "normal_hold")
        self.assertIn('(( deadline <= DEADLINE - 10 )) || deadline=$((DEADLINE - 10))', body)
        self.assertIn("BROKER_NORMAL_PRE_HOLD_S + BROKER_NORMAL_ATTACK_DURATION_S", source)
        self.assertIn("NORMAL_RECOVERY_DEADLINE_S + BROKER_NORMAL_POST_HOLD_S)", source)

    def test_ready_timeout_covers_both_holds(self):
        source = SAME_CELL.read_text()
        self.assertIn(
            "SAME_CELL_READY_TIMEOUT_S=$((SAME_CELL_HEALTH_TIMEOUT_S + 30 "
            "+ SAME_CELL_NORMAL_PRE_HOLD_S + SAME_CELL_NORMAL_POST_HOLD_S))",
            source,
        )

    def test_blind_attacker_gate_covers_both_holds(self):
        source = SAME_CELL.read_text()
        match = re.search(r"^\s*export SAME_CELL_ATTACKER_GATE_TIMEOUT_S=.*$", source, re.M)
        self.assertIsNotNone(match)
        for pre, post, expected in ((0, 0, 240), (30, 90, 360)):
            script = (
                "set -euo pipefail\n"
                f"SAME_CELL_NORMAL_PRE_HOLD_S={pre}\n"
                f"SAME_CELL_NORMAL_POST_HOLD_S={post}\n"
                f"{match.group(0)}\n"
                'printf %s "$SAME_CELL_ATTACKER_GATE_TIMEOUT_S"'
            )
            result = subprocess.run(
                ["bash", "-c", script], text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, str(expected))
        self.assertIn(
            "ATTACKER_GATE_TIMEOUT_S=${SAME_CELL_ATTACKER_GATE_TIMEOUT_S:-${ATTACKER_GATE_TIMEOUT_S:-240}}",
            PHASE.read_text(),
        )

    def test_normal_ue_stop_escalates_and_staggers(self):
        body = function_text(SAME_CELL, "stop_normal_ue")
        self.assertLess(body.index("kill -INT"), body.index("kill -TERM"))
        self.assertLess(body.index("kill -TERM"), body.index("kill -KILL"))
        self.assertEqual(body.count("kill -INT"), 1)
        self.assertEqual(body.count("{1..50}"), 2)

        source = BROKER.read_text()
        stop = function_text(BROKER, "stop_children")
        self.assertIn("gap=$NORMAL_UE_STOP_GAP_S", stop)
        self.assertIn('targets+=("$i")', stop)
        self.assertLess(stop.index('targets+=("$i")'), stop.index('targets+=("$BROKER_INDEX")'))
        self.assertLess(stop.index("kill -INT"), stop.index("kill -TERM"))
        self.assertLess(stop.index("kill -TERM"), stop.index("kill -KILL"))
        self.assertIn("NORMAL_UE_STOP_GAP_S=${NORMAL_UE_STOP_GAP_S:-3}", source)
        self.assertIn("sleep 0.2", stop)
        self.assertNotIn("sleep 0.2\n  for i in \"${UE_CHILD_INDEXES[@]}\"; do", stop)

    def test_broker_stop_staggers_targets_by_default_gap(self):
        source = BROKER.read_text()
        default = re.search(r"^NORMAL_UE_STOP_GAP_S=\$\{NORMAL_UE_STOP_GAP_S:-[0-9]+\}$",
                            source, re.M)
        self.assertIsNotNone(default)
        script = (
            "set -uo pipefail\n"
            "PING_PID=\nSTOPPED=0\n"
            "PIDS=(101 102 103)\nGROUPED=(0 0 0)\nCHILD_REAPED=()\n"
            "UE_CHILD_INDEXES=(0 1)\nBROKER_INDEX=2\n"
            "declare -A INTED=()\n"
            "is_running() { [[ -z ${INTED[$1]:-} ]]; }\n"
            "kill() { local signal=$1; local target=${@: -1};"
            " case $signal in -INT) INTED[${target#-}]=1; echo \"INT ${target#-}\";;"
            " *) echo \"SIG $signal\";; esac; }\n"
            "sleep() { echo \"SLEEP $1\"; }\n"
            "wait() { return 0; }\n"
            + default.group(0) + "\n"
            + function_text(BROKER, "stop_children") + "\n"
            "stop_children\n"
        )
        env = {key: value for key, value in os.environ.items()
               if key != "NORMAL_UE_STOP_GAP_S"}
        result = subprocess.run(["bash", "-c", script], text=True, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [line.split() for line in result.stdout.splitlines()]
        self.assertEqual([row[1] for row in rows if row[0] == "INT"],
                         ["101", "102", "103"])
        self.assertEqual([row[1] for row in rows if row[0] == "SLEEP"],
                         ["3", "3", "3"])
        self.assertNotIn("SIG", result.stdout)

    def test_hour_guard_waits_only_when_the_run_could_cross_the_hour(self):
        ctl = CTL.read_text()
        self.assertIn("SAME_CELL_HOUR_GUARD=${SAME_CELL_HOUR_GUARD:-1}", ctl)
        self.assertIn("SAME_CELL_HOUR_GUARD_MARGIN_S=${SAME_CELL_HOUR_GUARD_MARGIN_S:-360}", ctl)
        verify = (ROOT / "tools/verify_live_e2e.py").read_text()
        self.assertIn("HOUR_GUARD_WAIT_STARTED_AT", verify)

        short = self.guard_harness(480, 300, 1)
        self.assertIn("SLEEP 310", short.stdout)
        self.assertIn("START=2026-11-19T09:00:00Z", short.stdout)
        self.assertIn("END=2026-11-19T09:00:00Z", short.stdout)
        self.assertIn("WAITED=310", short.stdout)
        self.assertIn("대기 시작", short.stderr)
        self.assertIn("대기 끝", short.stderr)

        long = self.guard_harness(480, 600, 1)
        self.assertNotIn("SLEEP", long.stdout)
        self.assertIn("WAITED=\n", long.stdout)

        disabled = self.guard_harness(480, 300, 0)
        self.assertNotIn("SLEEP", disabled.stdout)
        self.assertIn("WAITED=\n", disabled.stdout)

    def guard_harness(self, expected, remaining, enabled):
        epoch = 1_700_000_000 - (1_700_000_000 % 3600) + (3600 - remaining)
        script = (
            "set -euo pipefail\n"
            f"SAME_CELL_HOUR_GUARD={enabled}\n"
            f"EPOCH={epoch}\n"
            'date() { if [[ "$*" == "+%s" ]]; then echo "$EPOCH"; '
            'else echo "2026-11-19T09:00:00Z"; fi; }\n'
            'sleep() { echo "SLEEP $1"; }\n'
            + function_text(CTL, "hour_guard_wait") + "\n"
            "HOUR_GUARD_WAIT_STARTED_AT=\n"
            "HOUR_GUARD_WAIT_ENDED_AT=\n"
            "HOUR_GUARD_WAIT_S=\n"
            f"hour_guard_wait {expected}\n"
            'echo "START=${HOUR_GUARD_WAIT_STARTED_AT:-} '
            'END=${HOUR_GUARD_WAIT_ENDED_AT:-} WAITED=${HOUR_GUARD_WAIT_S:-}"\n'
        )
        return subprocess.run(["bash", "-c", script], text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_rrc_broker_deadline_follows_hold_settings(self):
        base = ["bash", str(CTL), "same-cell", "run", "rrc-storm", "--profile", "p5",
                "--mode", "attack", "--run-id", "deadline-1", "--enable", "--dry-run"]
        default = subprocess.run(base, text=True, capture_output=True, env=dict(os.environ))
        self.assertEqual(default.returncode, 0, default.stderr)
        self.assertIn(" -d 240", default.stdout)
        shifted_env = dict(os.environ, BROKER_NORMAL_PRE_HOLD_S="45", BROKER_NORMAL_POST_HOLD_S="120")
        shifted = subprocess.run(base, text=True, capture_output=True, env=shifted_env)
        self.assertEqual(shifted.returncode, 0, shifted.stderr)
        self.assertIn(" -d 405", shifted.stdout)
        self.assertNotIn(" -d 240", shifted.stdout)

    def test_campaign_dry_run_carries_the_holds_to_every_runner(self):
        result = subprocess.run(
            ["bash", str(CTL), "same-cell", "campaign", "l3-live", "--campaign-id", "holds",
             "--sets", "3", "--count", "5", "--enable", "--dry-run"],
            text=True, capture_output=True, env=dict(os.environ),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        rrc = [line for line in result.stdout.splitlines() if "rss-broker-witness" in line]
        self.assertEqual(len(rrc), 6)
        for line in rrc:
            self.assertIn("BROKER_NORMAL_PRE_HOLD_S=30", line)
            self.assertIn("BROKER_NORMAL_POST_HOLD_S=90", line)
            self.assertIn("NORMAL_UE_STOP_GAP_S=3", line)
            self.assertIn(" -d 360", line)
        normal = [line for line in result.stdout.splitlines() if "blind-run" in line]
        self.assertTrue(normal, result.stdout)
        for line in normal:
            self.assertIn("SAME_CELL_NORMAL_PRE_HOLD_S=30", line)
            self.assertIn("SAME_CELL_NORMAL_POST_HOLD_S=90", line)

    def test_normal_hold_evidence_is_copied_and_sealed(self):
        wrapper = (ROOT / "tools/p5-live-e2e").read_text()
        self.assertGreaterEqual(wrapper.count("same-cell-normal-hold.tsv"), 2)
        match = re.search(r"^embed_self_live_evidence\(\) \{\n.*?^PY\n^\}$",
                          SAME_CELL.read_text(), re.S | re.M)
        self.assertIsNotNone(match)
        body = match.group(0)
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            child, out = base / "child", base / "run"
            child.mkdir()
            out.mkdir()
            (child / "run.json").write_text('{"schema":"x"}\n')
            (child / "oracle.jsonl").write_text('{"schema":"o"}\n')
            (child / "verdict.json").write_text('{"passed":true}\n')
            (child / "report.md").write_text("# r\n")
            (child / "evidence_manifest.json").write_text(
                '{"schema":"ran-reproducer.evidence.v1","run_id":"r","files":{}}\n')
            (out / "run.json").write_text('{"schema":"same-cell.run.v3"}\n')
            (out / "session.json").write_text('{"schema":"same-cell.session.v2"}\n')
            (out / "broker.log").write_text("log\n")
            (out / "normal-hold.tsv").write_text(
                "1700000000000000000\tpre\t5\n1700000000000000001\tpost\t5\n")
            rows = [{"phase": phase, "ue": ue, "ping_ok": True}
                    for phase in ("before", "after") for ue in range(1, 6)]
            (out / "normal-health.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows))
            script = (
                "set -euo pipefail\n"
                f"CHILD_OUTPUT={child}\nRUN_OUT={out}\n"
                + body + "\nembed_self_live_evidence\n"
            )
            result = subprocess.run(
                ["bash", "-c", script], text=True, capture_output=True,
                env=dict(os.environ, HOUR_GUARD_WAIT_STARTED_AT="2026-11-19T09:00:00Z",
                         HOUR_GUARD_WAIT_ENDED_AT="2026-11-19T09:05:10Z",
                         HOUR_GUARD_WAIT_S="310"))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((child / "same-cell-normal-hold.tsv").is_file())
            manifest = json.loads((child / "evidence_manifest.json").read_text())
            self.assertIn("same-cell-normal-hold.tsv", manifest["files"])
            run = json.loads((child / "run.json").read_text())
            self.assertEqual(run["same_cell"]["hour_guard"]["waited_s"], 310)

if __name__ == "__main__":
    unittest.main()
