import errno
import os
from pathlib import Path
import pty
import re
import select
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("timeout"), "GNU timeout is required")
class RunInterruptTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="run-interrupt-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = (ROOT / "tools/ctl.sh").read_text()
        self.function = re.search(
            r"^run_same_cell_phase\(\) \{\n.*?^\}", source, re.M | re.S
        ).group(0)
        self.child = self.root / "child.py"
        self.child.write_text('''import os, signal, subprocess, sys, time
from pathlib import Path
root = Path(sys.argv[1])
grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
(root / "grandchild.pid").write_text(str(grandchild.pid))
(root / "child.pid").write_text(str(os.getpid()))
def stop(*unused):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    print("FIXTURE_CLEANING", flush=True)
    os.killpg(grandchild.pid, signal.SIGTERM)
    grandchild.wait(timeout=2)
    time.sleep(.3)
    (root / "cleaned").touch()
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
print("FIXTURE_READY", flush=True)
while True:
    signal.pause()
''')
        self.harness = self.root / "phase.sh"
        self.harness.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n" + self.function
            + '\nrun_same_cell_phase "$@"\n'
        )

    def command(self):
        return ["timeout", "--signal=TERM", "--kill-after=2s", "30s",
                sys.executable, str(self.child), str(self.root)]

    def kill_fixture(self):
        for name in ("child.pid", "grandchild.pid"):
            path = self.root / name
            if path.exists():
                try:
                    os.kill(int(path.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_exit_status_and_deadline_are_preserved(self):
        for command, expected in ((["sh", "-c", "exit 7"], 7),
                                  (["timeout", ".1s", "sleep", "10"], 124)):
            with self.subTest(command=command):
                result = subprocess.run(["bash", str(self.harness), *command],
                                        capture_output=True, text=True, timeout=3)
                self.assertEqual(result.returncode, expected, result.stderr)

    def test_term_to_controller_reaches_timeout_group_cleanup(self):
        process = subprocess.Popen(["bash", str(self.harness), *self.command()],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), "FIXTURE_READY")
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=4)
            self.assertEqual(process.returncode, 143, stderr)
            self.assertIn("FIXTURE_CLEANING", stdout)
            self.assertTrue((self.root / "cleaned").exists())
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            self.kill_fixture()

    def test_terminal_ctrl_c_exits_ui_after_cleanup_without_extra_prompts(self):
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
        controller.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + self.function
                              + "\nrun_same_cell_phase " + shlex.join(self.command()) + "\n")
        controller.chmod(0o755)
        pid, fd = pty.fork()
        if pid == 0:
            env = dict(os.environ, TERM="xterm", COLUMNS="80", LINES="24")
            env.pop("NO_COLOR", None)
            os.execve(str(self.root / "run.sh"), ["run.sh", "--no-anim"], env)
        data = bytearray()
        cursor = 0
        ended = False

        def until(text):
            nonlocal cursor
            marker = text.encode()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                at = data.find(marker, cursor)
                if at >= 0:
                    cursor = at + len(marker)
                    return
                if select.select([fd], [], [], .1)[0]:
                    data.extend(os.read(fd, 65536))
            self.fail(f"missing terminal output: {text}\n{data.decode(errors='replace')}")

        try:
            for title, key in (("환경 설정", b"1"), ("공격 선택", b"1"), ("작업 선택", b"3")):
                until(title)
                until("q 나감")
                os.write(fd, key)
            until("FIXTURE_READY")
            child_pid = int((self.root / "child.pid").read_text())
            self.assertNotEqual(os.getpgid(child_pid), os.getpgid(pid))
            started = time.monotonic()
            os.write(fd, b"\x03")
            until("FIXTURE_CLEANING")
            os.write(fd, b"\x03")
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                waited, status = os.waitpid(pid, os.WNOHANG)
                if waited:
                    ended = True
                    self.assertEqual(os.waitstatus_to_exitcode(status), 130)
                    break
                if select.select([fd], [], [], .1)[0]:
                    try:
                        data.extend(os.read(fd, 65536))
                    except OSError as error:
                        if error.errno != errno.EIO:
                            raise
            self.assertTrue(ended, "Ctrl-C did not terminate the UI")
            self.assertLess(time.monotonic() - started, 4)
            self.assertTrue((self.root / "cleaned").exists())
            self.assertFalse((Path('/proc') / str(child_pid)).exists())
            text = data.decode(errors="replace")
            self.assertIn("중단 요청을 받았습니다", text)
            self.assertNotIn("ENABLE 입력", text)
            self.assertNotIn("RUN_ID [", text)
        finally:
            if not ended:
                os.killpg(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            os.close(fd)
            self.kill_fixture()


if __name__ == "__main__":
    unittest.main()
