import os
import subprocess
import unittest
from pathlib import Path

from tools.verify_live_e2e import SEND

ROOT = Path(__file__).resolve().parents[1]
RUNNERS = {
    "p5": ROOT / "tools" / "p5-live-e2e",
    "uplink": ROOT / "reproducers" / "uplink-dos" / "bin" / "uplink-credential-flood-run",
    "nas": ROOT / "reproducers" / "nas-counter-desynchronization" / "bin" / "nas-counter-desync-run",
}
FOLLOW_GUARDS = ("if (( follow )); then", "if (( CU_DASHBOARD_FOLLOW )); then")


def body(text, header):
    return text.split(header, 1)[1].split("\n}\n", 1)[0]


def judge_totals(text):
    sends = [m.groupdict() for line in text.splitlines() if (m := SEND.search(line))]
    return (sum(int(row["accepted"]) for row in sends),
            sum(int(row["rejected"]) for row in sends))


def follow_default_line(path):
    lines = [line for line in path.read_text().splitlines()
             if line.startswith("CU_DASHBOARD_FOLLOW=${CU_DASHBOARD_FOLLOW:-")]
    assert len(lines) == 1, path
    return lines[0]


def effective_follow(path, value):
    env = {key: item for key, item in os.environ.items() if key != "CU_DASHBOARD_FOLLOW"}
    if value is not None:
        env["CU_DASHBOARD_FOLLOW"] = value
    script = follow_default_line(path) + '\nprintf %s "$CU_DASHBOARD_FOLLOW"'
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True,
                            text=True, check=True)
    return result.stdout


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


    def test_default_is_live_follow_and_toggle_is_validated(self):
        for name, path in RUNNERS.items():
            with self.subTest(runner=name):
                text = path.read_text()
                self.assertTrue(follow_default_line(path).endswith(":-1}"))
                self.assertIn('[[ $CU_DASHBOARD_FOLLOW == 0 || $CU_DASHBOARD_FOLLOW == 1 ]]', text)
                # 미설정이면 1(실행 중 실시간 전송), 0으로 주면 예전 한 번 전송 경로.
                self.assertEqual(effective_follow(path, None), "1")
                self.assertEqual(effective_follow(path, "0"), "0")
                self.assertEqual(effective_follow(path, "1"), "1")


    def test_follow_path_runs_as_same_user_with_same_config_and_only_two_gates(self):
        for name, path in RUNNERS.items():
            with self.subTest(runner=name):
                text = path.read_text()
                # 켜고 끄는 지점은 관측 시작과 종료 두 곳뿐이다.
                self.assertEqual(text.count('--config "$out/sender.json"'), 2)
                self.assertIn('setsid sudo -u "$owner" python3 '
                              '"$platform/detection/tools/dashboard_sender.py"', text)
                if name != "p5":
                    start = text.index('--config "$out/sender.json"')
                    guard = text.rindex("if (( ", 0, start)
                    self.assertTrue(text.startswith(FOLLOW_GUARDS, guard), text[guard:guard + 40])


    def test_zero_keeps_the_end_of_run_once_path(self):
        for name, path in RUNNERS.items():
            with self.subTest(runner=name):
                stop = body(path.read_text(), "stop_live() {")
                # follow=0이면 전송기를 띄우지 않고, 종료 시 같은 설정으로 한 번만 보낸다.
                self.assertIn('if (( follow )) && [[ -f $out/sender.pid ]]; then', stop)
                self.assertIn('fi\n'
                              'set +e\n'
                              'sudo -u "$owner" python3 "$platform/detection/tools/dashboard_sender.py" '
                              '--config "$out/sender.json" --once', stop)


    def test_p5_starts_follow_without_baseline_wait(self):
        text = RUNNERS["p5"].read_text()
        # 기본 1이 LIVE_E2E_WAIT_FOR_BASELINE=0 경로를 거부하지 않는다.
        self.assertNotIn("LIVE_E2E_WAIT_FOR_BASELINE=1", text)
        self.assertFalse([line for line in text.splitlines()
                          if "CU_DASHBOARD_FOLLOW" in line and "WAIT_FOR_BASELINE" in line])
        # baseline 대기 여부와 무관하게, 재기동 직후 또는 start_live 직후 같은 지점에서 띄운다.
        self.assertRegex(text, r"fi\nif \(\( CU_DASHBOARD_FOLLOW \)\); then\n"
                               r"  start_follow_sender\nfi\n"
                               r"\(\( PRE_CHILD_S == 0 \)\)")
        follow = body(text, "start_follow_sender() {")
        self.assertIn('grep -q \'"type":"hello"\' "$out/detector-input.jsonl"', follow)
        self.assertIn('--config "$out/sender.json" >>"$out/sender.stdout" '
                      '2>>"$out/sender.log"', follow)
        self.assertIn('echo $! >"$out/sender.pid"', follow)
        self.assertNotIn("--once", follow)


    def test_follow_sender_starts_when_observation_starts(self):
        text = RUNNERS["p5"].read_text()
        reset = body(text, "reset_detector_after_baseline() {")
        # 재기동은 detector 입력만 새로 만들고, 전송기 시작은 공통 지점 한 곳에서 한다.
        self.assertNotIn("if (( follow )); then", reset)
        self.assertLess(text.index("  reset_detector_after_baseline\n"),
                        text.index("  start_follow_sender\n"))
        self.assertLess(text.index("  start_follow_sender\n"),
                        text.index('sleep "$PRE_CHILD_S"'))
        self.assertIn("follow=$4", body(text, "stop_live() {"))


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
