import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "references" / "manifest.json").read_text(encoding="utf-8"))
CTL = ROOT / "references" / "bin" / "reference-ctl"


def load_bridge():
    path = ROOT / "reproducers" / "rrc-signaling-storm" / "reference" / "bin" / "oai-rfsim-zmq-bridge"
    loader = importlib.machinery.SourceFileLoader("rfsim_bridge", str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


class ReferenceManifestTest(unittest.TestCase):
    def test_schema_and_unique_ids(self):
        self.assertEqual(MANIFEST["schema"], "ran-reproducer.references.v1")
        ids = [item["id"] for item in MANIFEST["references"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("ref-rrc-storm", ids)

    def test_reference_paths_exist(self):
        for item in MANIFEST["references"]:
            self.assertTrue((ROOT / item["build"]).is_file(), item["id"])
            self.assertTrue((ROOT / item["bridge"]).is_file(), item["id"])
            if item.get("runner"):
                self.assertTrue((ROOT / item["runner"]).is_file(), item["id"])

    def test_rules_match_module_catalog(self):
        for item in MANIFEST["references"]:
            catalog = json.loads((ROOT / "reproducers" / item["module"] / "reproducer.json")
                                 .read_text(encoding="utf-8"))
            rules = set(catalog.get("rule_ids") or catalog.get("detection", {}).get("rule_ids") or [])
            for rule in item["rule_ids"]:
                self.assertTrue(rule in rules or not rules, f"{item['id']}: {rule} != {sorted(rules)}")

    def test_only_public_implementations_are_listed(self):
        sources = {item["source"]["repository"] for item in MANIFEST["references"]}
        self.assertEqual(sources, {"https://github.com/5gattacks/5g-rrc-storm",
                                   "https://github.com/5GSEC/OAI-5G"})
        missing = {row["source"] for row in MANIFEST["no_public_attack"]}
        self.assertIn("https://github.com/5GSEC/5G-Spector", missing)

    def test_rrc_storm_control_is_unpatched_build(self):
        item = next(item for item in MANIFEST["references"] if item["id"] == "ref-rrc-storm")
        self.assertNotEqual(item["binaries"]["attack"], item["binaries"]["control"])

    def test_blind_dos_is_honest_about_rfsim_gate(self):
        item = next(item for item in MANIFEST["references"] if item["id"] == "ref-blind-dos")
        self.assertIn("IS_SOFTMODEM_RFSIM", item["status_detail"] + item["attach"])


class ReferenceCtlTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        profile = Path(self.temp.name) / "p1.json"
        profile.write_text(json.dumps({
            "schema": "ran-reproducer.profile.v1",
            "id": "p1",
            "backend": "p5",
            "configured": False,
            "run_root": str(Path(self.temp.name) / "runs"),
        }), encoding="utf-8")
        self.env = dict(__import__("os").environ, RAN_REPRO_PROFILE_DIR=self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_list(self):
        result = subprocess.run([sys.executable, str(CTL), "list"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ref-rrc-storm", result.stdout)
        self.assertIn("공개 공격 구현 없음", result.stdout)

    def test_missing_profile(self):
        result = subprocess.run([sys.executable, str(CTL), "doctor", "ref-rrc-storm",
                                 "--profile", "no-such-profile"], capture_output=True, text=True,
                                env=self.env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("profile이 없습니다", result.stderr)

    def test_attack_requires_enable(self):
        result = subprocess.run([sys.executable, str(CTL), "run", "ref-rrc-storm",
                                 "--profile", "p1", "--mode", "attack"], capture_output=True, text=True,
                                env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--enable", result.stderr)

    def test_blind_dos_has_no_runner(self):
        result = subprocess.run([sys.executable, str(CTL), "run", "ref-blind-dos",
                                 "--profile", "p1", "--mode", "control", "--enable"],
                                capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("runner가 없습니다", result.stderr)


@unittest.skipUnless(__import__("importlib").util.find_spec("numpy"), "numpy 없음")
class BridgeConversionTest(unittest.TestCase):
    def test_c16_cf_roundtrip(self):
        bridge = load_bridge()
        payload = (b"\x01\x00\xff\x7f\x00\x80" * 4)
        converted = bridge.c16_to_cf(payload)
        self.assertEqual(len(converted), 4 * 4 * 2)
        back = bridge.cf_to_c16(converted)
        self.assertEqual(len(back), len(payload))


if __name__ == "__main__":
    unittest.main()
