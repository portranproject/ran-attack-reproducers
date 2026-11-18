import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "reproducers" / "authentication-timeout-exhaustion"


class BuildContractTest(unittest.TestCase):
    def test_patch_stack_is_parseable(self):
        patches = [
            MODULE / "patch" / "ru-sharing-w38.patch",
            ROOT / "workloads" / "normal-ue" / "patch" / "normal-multi-ru.patch",
            MODULE / "patch" / "auth-timeout-ue-w38.patch",
            MODULE / "patch" / "same-cell-ra-gate-w38.patch",
        ]
        for patch in patches:
            result = subprocess.run(
                ["git", "apply", "--numstat", str(patch)],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_clean_build_and_runtime_use_the_same_oai_tree(self):
        build = (MODULE / "bin" / "auth-timeout-build").read_text()
        config = (MODULE / "conf" / "auth-stall-cell.conf.example").read_text()
        self.assertIn("GIT_INDEX_FILE", build)
        self.assertIn("/root/OAI-auth-timeout-w38/", config)
        self.assertNotIn("/root/OAI-auth-multi-ru-e2e/", config)


if __name__ == "__main__":
    unittest.main()
