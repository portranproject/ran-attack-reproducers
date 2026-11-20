import unittest
from pathlib import Path

from tools.verify_live_e2e import SEND

ROOT = Path(__file__).resolve().parents[1]
RUNNERS = {
    "p5": ROOT / "tools" / "p5-live-e2e",
    "uplink": ROOT / "reproducers" / "uplink-dos" / "bin" / "uplink-credential-flood-run",
    "nas": ROOT / "reproducers" / "nas-counter-desynchronization" / "bin" / "nas-counter-desync-run",
}


def body(text, header):
    return text.split(header, 1)[1].split("\n}\n", 1)[0]


def judge_totals(text):
    sends = [m.groupdict() for line in text.splitlines() if (m := SEND.search(line))]
    return (sum(int(row["accepted"]) for row in sends),
            sum(int(row["rejected"]) for row in sends))


class DashboardFollowTest(unittest.TestCase):
    def test_judge_sums_follow_and_once_phases_without_double_counting_resumed_lines(self):
        follow = ("send file=/tmp/evidence.jsonl status=200 accepted=3 rejected=0\n"
                  "send file=/tmp/detector-input.jsonl status=200 accepted=5 rejected=0\n")
        once = ("send file=/tmp/evidence.jsonl status=200 accepted=2 rejected=0\n"
                "send file=/tmp/detector-input.jsonl status=200 accepted=4 rejected=0\n")
        # 상태 파일이 끊긴 위치를 남기므로 두 구간의 줄은 겹치지 않고 합계가 한 번씩 센다.
        self.assertEqual(judge_totals(follow + once), (14, 0))
        # 겹친 줄이 남으면 판정 합계는 두 번 센다. 대시보드 중복 제거는 이 합계를 고치지 않는다.
        self.assertEqual(judge_totals(follow + follow), (16, 0))


    def test_toggle_defaults_to_off_and_is_validated(self):
        for name, path in RUNNERS.items():
            with self.subTest(runner=name):
                text = path.read_text()
                self.assertIn("CU_DASHBOARD_FOLLOW=${CU_DASHBOARD_FOLLOW:-0}\n", text)
                self.assertIn('[[ $CU_DASHBOARD_FOLLOW == 0 || $CU_DASHBOARD_FOLLOW == 1 ]]', text)

    def test_follow_path_runs_as_same_user_with_same_config_and_only_two_gates(self):
        for name, path in RUNNERS.items():
            with self.subTest(runner=name):
                text = path.read_text()
                # 켜고 끄는 지점은 관측 시작과 종료 두 곳뿐이다.
                self.assertEqual(text.count("if (( follow ))"), 2)
                self.assertIn('setsid sudo -u "$owner" python3 '
                              '"$platform/detection/tools/dashboard_sender.py"', text)
                self.assertEqual(text.count('--config "$out/sender.json"'), 2)

    def test_follow_sender_starts_when_observation_starts(self):
        text = RUNNERS["p5"].read_text()
        reset = body(text, "reset_detector_after_baseline() {")
        self.assertIn('"$CU_DASHBOARD_FOLLOW" <<\'REMOTE\'', reset)
        self.assertIn("follow=$4", reset)
        self.assertLess(reset.index("telemetry reconnect hello timeout"),
                        reset.index("if (( follow )); then"))
        self.assertLess(reset.index('chown -R "$owner:$owner" "$out"'),
                        reset.index("if (( follow )); then"))
        start = reset[reset.index("if (( follow )); then"):]
        self.assertIn('--config "$out/sender.json" >>"$out/sender.stdout" 2>>"$out/sender.log"', start)
        self.assertIn('echo $! >"$out/sender.pid"', start)
        self.assertNotIn("--once", start)
        # 웜업 구간을 건너뛰는 지점에서만 켤 수 있다.
        self.assertIn("LIVE_E2E_WAIT_FOR_BASELINE=1", text)

    def test_follow_sender_starts_at_end_of_start_live_for_l3_runners(self):
        for name in ("uplink", "nas"):
            with self.subTest(runner=name):
                text = RUNNERS[name].read_text()
                start = body(text, "start_live() {")
                self.assertIn('"$CU_DASHBOARD_FOLLOW" <<\'REMOTE\'', start)
                self.assertIn("follow=${10}", start)
                self.assertLess(start.index('echo $! >"$out/telemetry.pid"'),
                                start.index("if (( follow )); then"))
                self.assertIn('--config "$out/sender.json" >>"$out/sender.stdout" 2>>"$out/sender.log"', start)
                self.assertIn('echo $! >"$out/sender.pid"', start)
                self.assertNotIn("--once", start)

    def test_stop_live_terminates_engines_then_sender_then_runs_once_appending(self):
        for name, path in RUNNERS.items():
            with self.subTest(runner=name):
                stop = body(path.read_text(), "stop_live() {")
                self.assertIn('"$CU_DASHBOARD_FOLLOW" <<\'REMOTE\'', stop)
                self.assertIn("follow=$4", stop)
                loop = stop.index("for role in telemetry detector; do")
                term = stop.index('kill -TERM -- "-$spid"')
                once = stop.index('--once')
                self.assertLess(loop, term)
                self.assertLess(term, once)
                self.assertLess(stop.index('for _ in {1..100}; do kill -0 "$spid"'), once)
                self.assertIn('>>"$out/sender.stdout" 2>>"$out/sender.log"', stop)
                self.assertNotIn('-KILL -- "-$spid"', stop)
                self.assertIn('echo $? >"$out/sender.exit"', stop)

    def test_stop_live_skips_sender_when_pid_file_is_missing(self):
        for name, path in RUNNERS.items():
            with self.subTest(runner=name):
                stop = body(path.read_text(), "stop_live() {")
                self.assertIn('if (( follow )) && [[ -f $out/sender.pid ]]; then', stop)


if __name__ == "__main__":
    unittest.main()
