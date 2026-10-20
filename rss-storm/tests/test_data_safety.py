"""Local file guards only; no OAI build, radio, or gNB is invoked."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


BIN = Path(__file__).resolve().parents[1] / "bin"
PUCCH_FIX = BIN.parent / "patch" / "oai-pucch-null-fix.patch"
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

    def make_pucch_repo(self, already_fixed=False):
        self.make_repo()
        scheduler = self.repo / "openair2/LAYER2/NR_MAC_UE/nr_ue_scheduler.c"
        scheduler.parent.mkdir(parents=True)
        scheduler.write_text(
            "  if (num_res == 1 && pucch[0].n_sr > 0 && pucch[0].sr_payload == 0)\n"
            "    return;\n\n"
            "  if (num_res > 1)\n"
            "    multiplex_pucch_resource(mac, pucch, num_res);\n\n"
            "  for (int j = 0; j < num_res; j++) {\n"
            "    if (pucch[j].n_harq + pucch[j].n_sr + pucch[j].csi_payload.p1_bits != 0) {\n"
        )
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "scheduler fixture")
        if already_fixed:
            self.git("apply", str(PUCCH_FIX))
            self.git("add", ".")
            self.git("-c", "commit.gpgsign=false", "commit", "-qm", "PUCCH fix")
        patch = self.root / "rss-fixture.patch"
        patch.write_text("--- a/source.txt\n+++ b/source.txt\n@@ -1 +1 @@\n-original\n+patched\n")
        self.env["PATCH"] = str(patch)
        self.stub("cmake", "exit 77\n")
        return scheduler

    def test_build_applies_pucch_fix_before_rss_patch(self):
        scheduler = self.make_pucch_repo()
        result = self.run_script("rss-build")
        self.assertIn("applying official OAI PUCCH crash fix", result.stdout)
        self.assertIn("common_harq", scheduler.read_text())
        self.assertEqual((self.repo / "source.txt").read_text(), "patched\n")

    def test_build_reuses_existing_pucch_fix(self):
        scheduler = self.make_pucch_repo(already_fixed=True)
        result = self.run_script("rss-build")
        self.assertIn("PUCCH crash fix already applied", result.stdout)
        self.assertEqual(scheduler.read_text().count("int common_harq"), 1)
        self.assertEqual((self.repo / "source.txt").read_text(), "patched\n")

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


if __name__ == "__main__":
    unittest.main()
