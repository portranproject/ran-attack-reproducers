"""Local file guards only; no OAI build, radio, or gNB is invoked."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


BIN = Path(__file__).resolve().parents[1] / "bin"
GIT = shutil.which("git")
BASH = shutil.which("bash")


class DataSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stubs = self.root / "stubs"
        self.stubs.mkdir()
        self.action = self.root / "unexpected-action"
        for name in ("ue", "cmake", "timeout", "pkill", "pgrep", "taskset", "gnb"):
            self.stub(name, f"touch {shlex.quote(str(self.action))}\nexit 99\n")
        self.env = {
            "PATH": str(self.stubs) + os.pathsep + os.defpath,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "LC_ALL": "C",
            "RSS_CONF": str(self.root / "absent.conf"),
            "ENABLE": "0",
            "UE_BIN": str(self.stubs / "ue"),
            "LOGDIR": str(self.root / "runs"),
            "GNB_RESTART_CMD": shlex.quote(str(self.stubs / "gnb")),
        }

    def stub(self, name, body):
        path = self.stubs / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)

    def run_script(self, name, *args):
        result = subprocess.run(
            [BASH, str(BIN / name), *args],
            env=self.env, cwd=self.root, text=True, capture_output=True, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.action.exists(), result.stdout + result.stderr)
        return result

    def git(self, *args):
        return subprocess.check_output(
            [GIT, "-C", str(self.repo), *args], env=self.env, text=True,
            stderr=subprocess.STDOUT,
        ).strip()

    def make_repo(self):
        self.repo = self.root / "oai"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Local test")
        self.git("config", "user.email", "test@example.invalid")
        (self.repo / ".gitignore").write_text("cmake_targets/\n")
        (self.repo / "source.txt").write_text("original\n")
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
        self.build = self.repo / "cmake_targets/ran_build/build"
        self.build.mkdir(parents=True)
        for name in ("nr-uesoftmodem", "liboai_zmqdevif.so"):
            (self.build / name).write_text("original artifact\n")
        patch = self.root / "invalid.patch"
        patch.write_text("Deliberately invalid: tests must stop before applying.\n")
        self.env.update(OAI=str(self.repo), PATCH=str(patch), BRANCH="new-test-branch")

    def test_build_applies_the_incremental_patch_stack_in_order(self):
        content = (BIN / "rss-build").read_text()
        curated = content.index('git -C "$OAI" apply "$PATCH"')
        stale_rnti = content.index('git -C "$OAI" apply "$DCI_FIX"')
        ack_rnti = content.index('git -C "$OAI" apply "$ACK_RNTI_FIX"')
        self.assertLess(curated, stale_rnti)
        self.assertLess(stale_rnti, ack_rnti)

    def test_build_preserves_staged_unstaged_and_untracked_changes(self):
        self.make_repo()
        for state in ("unstaged", "staged", "untracked"):
            with self.subTest(state=state):
                source = self.repo / "source.txt"
                source.write_text("local work\n")
                if state == "staged":
                    self.git("add", "source.txt")
                elif state == "untracked":
                    source.write_text("original\n")
                    (self.repo / "notes.txt").write_text("untracked work\n")
                before = self.git("status", "--porcelain", "--untracked-files=all")
                branch = self.git("symbolic-ref", "HEAD")
                result = self.run_script("rss-build")
                self.assertIn("review and preserve", result.stderr)
                self.assertEqual(before, self.git("status", "--porcelain", "--untracked-files=all"))
                self.assertEqual(branch, self.git("symbolic-ref", "HEAD"))
                self.assertEqual(source.read_text(), "original\n" if state == "untracked" else "local work\n")
                if state == "staged":
                    self.assertEqual(self.git("show", ":source.txt"), "local work")
                    self.git("reset", "-q", "HEAD", "--", "source.txt")
                if state == "untracked":
                    self.assertEqual((self.repo / "notes.txt").read_text(), "untracked work\n")
                self.assertFalse(list(self.build.glob("*.orig")))
                source.write_text("original\n")

    def test_build_stops_when_git_status_fails(self):
        self.make_repo()
        branch = self.git("symbolic-ref", "HEAD")
        self.stub("git", 'if [ "$3" = status ]; then exit 97; fi\n'
                  f'exec {shlex.quote(GIT)} "$@"\n')
        result = self.run_script("rss-build")
        self.assertIn("cannot check local changes", result.stderr)
        self.assertFalse(list(self.build.glob("*.orig")))
        self.assertEqual(branch, self.git("symbolic-ref", "HEAD"))
        self.assertEqual((self.repo / "source.txt").read_text(), "original\n")

    def test_build_accepts_a_clean_git_worktree(self):
        self.make_repo()
        worktree = self.root / "oai-worktree"
        subprocess.check_call(
            [GIT, "-C", str(self.repo), "worktree", "add", "-q", "--detach",
             str(worktree), "HEAD"],
            env=self.env,
        )
        build = worktree / "cmake_targets/ran_build/build"
        build.mkdir(parents=True)
        for name in ("nr-uesoftmodem", "liboai_zmqdevif.so"):
            (build / name).write_text("original artifact\n")
        self.env["OAI"] = str(worktree)
        result = self.run_script("rss-build")
        self.assertIn("== tree state", result.stdout)
        self.assertNotIn("not an OAI git tree", result.stderr)

    def test_run_rejects_existing_directory_file_and_symlinks(self):
        logs = Path(self.env["LOGDIR"])
        logs.mkdir()
        saved = logs / "saved"
        saved.mkdir()
        (saved / "run.json").write_text("original metadata\n")
        (saved / "ue.log").write_text("original log\n")
        (logs / "file").write_text("original file\n")
        (logs / "linked").symlink_to(saved, target_is_directory=True)
        (logs / "dangling").symlink_to(self.root / "absent", target_is_directory=True)
        for run_id in ("saved", "file", "linked", "dangling"):
            with self.subTest(run_id=run_id):
                result = self.run_script("rss-run", "-n", run_id)
                self.assertIn("existing results are never overwritten", result.stderr)
        self.assertEqual((saved / "run.json").read_text(), "original metadata\n")
        self.assertEqual((saved / "ue.log").read_text(), "original log\n")
        self.assertEqual((logs / "file").read_text(), "original file\n")
        self.assertTrue((logs / "linked").is_symlink())
        self.assertTrue((logs / "dangling").is_symlink())
        self.assertFalse((self.root / "absent").exists())

    def test_run_rejects_unsafe_ids_before_creating_parent(self):
        for run_id in (".", "..", "../escape", "a/b", "/tmp/run", "-run",
                       "a b", 'a"b', "a\nb", "a\\b"):
            with self.subTest(run_id=run_id):
                result = self.run_script("rss-run", "-n", run_id)
                self.assertIn("run_id must start", result.stderr)
                self.assertFalse(Path(self.env["LOGDIR"]).exists())

    def test_probe_propagates_runner_validation_failure(self):
        result = self.run_script("rss-probe", "-n", "bad-ack", "-A", "2")
        self.assertIn("rss-run failed", result.stderr)
        self.assertTrue(Path(self.env["LOGDIR"]).is_dir())

    def test_ack_withholding_cannot_claim_a_completed_attacker(self):
        result = self.run_script("rss-run", "-A", "0", "-c", "1")
        self.assertIn("cannot be combined", result.stderr)

    def test_invalid_clock_evidence_is_rejected_before_artifacts(self):
        self.env["CLOCK_EVIDENCE_SHA256"] = "not-a-sha256"
        result = self.run_script("rss-run", "-n", "bad-clock")
        self.assertIn("must be a lowercase SHA-256", result.stderr)
        self.assertFalse(Path(self.env["LOGDIR"]).exists())

    def test_run_rejects_non_zmq_before_creating_artifacts_or_running_commands(self):
        self.env["DEVICE"] = "usrpb210"
        result = self.run_script("rss-run", "-n", "ota-unsafe")
        self.assertIn("runner is ZMQ-only", result.stderr)
        self.assertFalse(Path(self.env["LOGDIR"]).exists())

    def test_run_rejects_runner_owned_ue_extra_before_actions(self):
        for index, extra in enumerate(("--device.name usrpb210",
                                       "--device.name=usrpb210",
                                       "--rss.max_duration_s 0"), 1):
            with self.subTest(extra=extra):
                self.env["UE_EXTRA"] = extra
                result = self.run_script("rss-run", "-n", f"extra-unsafe-{index}")
                self.assertIn("must not override runner-owned option", result.stderr)
                self.assertFalse(Path(self.env["LOGDIR"]).exists())

    def test_run_still_accepts_tuning_ue_extra(self):
        self.env["UE_EXTRA"] = "--log_config.global_log_level error --num-dl-actors 0"
        self.env["UE_BIN"] = str(self.root / "missing-ue")
        result = self.run_script("rss-run", "-n", "extra-tuning")
        self.assertIn("UE binary not found", result.stderr)
        self.assertNotIn("runner-owned option", result.stderr)
        self.assertFalse(Path(self.env["LOGDIR"]).exists())

    def test_doctor_blocks_non_zmq_instead_of_claiming_readiness(self):
        self.env["DEVICE"] = "usrpb210"
        result = self.run_script("rss-doctor")
        self.assertIn("current build and runner are ZMQ-only", result.stdout)
        self.assertIn("[FAIL]", result.stdout)

    def test_doctor_blocks_runner_owned_ue_extra(self):
        self.env["UE_EXTRA"] = "--device.name usrpb210"
        result = self.run_script("rss-doctor")
        self.assertIn("UE_EXTRA overrides runner-owned option", result.stdout)
        self.assertIn("[FAIL]", result.stdout)

    def test_doctor_blocks_direct_milenage_dump_binary(self):
        Path(self.env["UE_BIN"]).write_text("milenage output ik:\n")
        result = self.run_script("rss-doctor")
        self.assertIn("direct Milenage authentication dumps", result.stdout)
        self.assertIn("[FAIL]", result.stdout)

    def test_doctor_accepts_dev_null_as_an_explicit_empty_conf(self):
        self.env["RSS_CONF"] = os.devnull
        result = self.run_script("rss-doctor")
        self.assertIn("conf: /dev/null", result.stdout)
        self.assertNotIn("no conf file", result.stdout)


if __name__ == "__main__":
    unittest.main()
