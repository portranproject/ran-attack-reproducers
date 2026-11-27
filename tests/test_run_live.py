import errno
import fcntl
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import struct
import subprocess
import tempfile
import termios
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
BASH_MAJOR = int(subprocess.run([BASH, "-c", "echo ${BASH_VERSINFO[0]}"],
                                capture_output=True, text=True).stdout or 0) if BASH else 0

FAKE_CTL = """#!/usr/bin/env bash
trap 'echo "FAKE_CLEANING" >&2; sleep .5; echo FAKE_CLEANED; exit 130' INT
echo LIVE_LINE_A
sleep .6
echo LIVE_LINE_B >&2
sleep .6
printf 'LIVE_PART'; sleep .3; echo '_JOINED'
[ -n "${FAKE_WAIT:-}" ] && { echo FAKE_READY; while :; do sleep .1; done; }
exit 3
"""


@unittest.skipUnless(BASH_MAJOR >= 5, "live split screen needs bash 5")
class RunLiveTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="run-live-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        tools = self.root / "tools"
        tools.mkdir()
        shutil.copy2(ROOT / "run.sh", self.root / "run.sh")
        (tools / "reproctl.py").write_text(
            "import os, sys\n"
            "if sys.argv[1] == 'catalog':\n"
            f"    os.execv(sys.executable, [sys.executable, {str(ROOT / 'tools/reproctl.py')!r}, *sys.argv[1:]])\n"
            "elif sys.argv[1] == 'local-profile': print('lab')\n"
            "elif sys.argv[1] == 'env': print('RAN_REPRO_PROFILE_ID=lab')\n"
        )
        controller = tools / "ctl.sh"
        controller.write_text(FAKE_CTL)
        controller.chmod(0o755)

    def start(self, **env):
        pid, fd = pty.fork()
        if pid == 0:
            fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack("HHHH", 36, 110, 0, 0))
            values = dict(os.environ, TERM="xterm-256color", **env)
            values.pop("NO_COLOR", None)
            os.execve(str(self.root / "run.sh"), ["run.sh"], values)
        self.addCleanup(self.stop, pid, fd)
        self.pid, self.fd, self.data, self.cursor = pid, fd, bytearray(), 0
        return pid, fd

    def stop(self, pid, fd):
        try:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        except (ProcessLookupError, ChildProcessError):
            pass
        os.close(fd)

    def pump(self, timeout=.1):
        if select.select([self.fd], [], [], timeout)[0]:
            try:
                self.data.extend(os.read(self.fd, 65536))
            except OSError as error:
                if error.errno != errno.EIO:
                    raise
                return False
        return True

    def until(self, text, timeout=8):
        marker = text.encode()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            at = self.data.find(marker, self.cursor)
            if at >= 0:
                self.cursor = at + len(marker)
                return
            if not self.pump():
                break
        self.fail(f"missing terminal output: {text}\n{self.data.decode(errors='replace')[-3000:]}")

    def open_active_run(self):
        for title, key in (("환경 설정", b"1"), ("공격 선택", b"1"), ("작업 선택", b"3")):
            self.until(title)
            self.until("q 나감")
            os.write(self.fd, key)

    def test_motion_keeps_drawing_while_ctl_output_streams(self):
        self.start()
        self.open_active_run()
        self.until("실행 로그")
        start = self.cursor
        self.until("LIVE_LINE_A")
        self.until("LIVE_LINE_B")
        self.until("LIVE_PART_JOINED")
        self.until("종료 코드 3")
        live = self.data[start:self.cursor].decode(errors="replace")
        # 로그가 흐르는 동안 모션 프레임(머리 줄)이 여러 번 다시 그려짐
        self.assertGreaterEqual(live.count("실행 중 · Ctrl-C 중단"), 10)
        # 로그 영역은 모션 아래 줄부터 화면 끝까지
        self.assertIn("\x1b[24;36r", self.data.decode(errors="replace"))
        self.assertIn("\x1b[r", live)
        self.until("메뉴로 돌아감")

    def test_ctrl_c_shows_cleanup_output_then_exits(self):
        self.start(FAKE_WAIT="1")
        self.open_active_run()
        self.until("FAKE_READY")
        os.write(self.fd, b"\x03")
        self.until("FAKE_CLEANING")
        self.until("FAKE_CLEANED")
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            waited, status = os.waitpid(self.pid, os.WNOHANG)
            if waited:
                self.assertEqual(os.waitstatus_to_exitcode(status), 130)
                return
            self.pump()
        self.fail("Ctrl-C did not end the UI after cleanup")


if __name__ == "__main__":
    unittest.main()
