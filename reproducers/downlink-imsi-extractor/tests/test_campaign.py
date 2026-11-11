import json
import tempfile
import unittest
from pathlib import Path

from analysis.verify_campaign import verify
from analysis.verify_run import verify as verify_run, write_manifest
from test_verify_run import make_run


class CampaignTest(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        for index in range(1, 4):
            for mode in ("control", "emulation"):
                run_id = f"c1-{mode}-{index}"
                child = root / run_id
                child.mkdir()
                make_run(child, mode, run_id)
                (child / "verdict.json").write_text(json.dumps(verify_run(child)))
                write_manifest(child)
        return temporary, root

    def test_three_matched_sets_pass(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        result = verify(root, "c1")
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["children"]), 6)

    def test_sealed_child_mutation_fails(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        with (root / "c1-emulation-2" / "ue.log").open("a") as output:
            output.write("changed\n")
        with self.assertRaisesRegex(ValueError, "봉인 후"):
            verify(root, "c1")

    def test_pair_configuration_mismatch_fails(self):
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        child = root / "c1-emulation-1"
        run = json.loads((child / "run.json").read_text())
        run["ue_binary_sha256"] = "f" * 64
        (child / "run.json").write_text(json.dumps(run))
        (child / "evidence_manifest.json").unlink()
        write_manifest(child)
        with self.assertRaisesRegex(ValueError, "matched"):
            verify(root, "c1")


if __name__ == "__main__":
    unittest.main()
