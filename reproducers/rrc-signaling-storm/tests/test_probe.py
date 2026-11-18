"""Offline checks for the normal-UE probe: the summary and the runner knobs."""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "analysis" / "probe_summary.py"
RUNNER = ROOT / "bin" / "rss-run"
PROBE = ROOT / "bin" / "rss-probe"
LAB_SUITE = ROOT / "bin" / "rss-lab-suite"
PATCH = ROOT / "patch" / "rss-ue-curated.patch"
ACK_RNTI_PATCH = ROOT / "patch" / "oai-msg4-ack-rnti.patch"
EVIDENCE = ROOT / "analysis" / "evidence_manifest.py"


def probe_event(ue, seq, t_ns, event, **extra):
    record = {"type": "event", "run_id": "t", "ue": ue, "seq": seq,
              "t_ns": t_ns, "air_ms": 0, "event": event}
    record.update(extra)
    return json.dumps(record) + "\n"


class ProbeSummaryTests(unittest.TestCase):
    def summarise(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "attempts.jsonl"
            path.write_text(content)
            return subprocess.run(
                [sys.executable, str(SUMMARY), str(path)],
                capture_output=True, text=True, check=False,
            )

    def test_attempts_without_a_connection_are_reported_as_denial(self):
        result = self.summarise(
            probe_event(0, 0, 1_000_000_000, "probe_attempt", **{"try": 1})
            + probe_event(0, 1, 3_000_000_000, "probe_attempt", **{"try": 2})
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("probe attempts      2", result.stdout)
        self.assertIn("probe connected     no", result.stdout)
        self.assertIn("the normal UE never connected", result.stdout)

    def test_connected_reports_the_try_count_and_latency(self):
        result = self.summarise(
            probe_event(0, 0, 1_000_000_000, "probe_attempt", **{"try": 1})
            + probe_event(0, 1, 6_100_000_000, "probe_connected", tries=1, ms=5102)
        )
        self.assertIn("probe connected     yes   tries=1  5102 ms", result.stdout)
        self.assertIn("stayed connected", result.stdout)

    def test_a_run_without_probe_events_says_so(self):
        result = self.summarise(
            probe_event(1, 0, 1_000_000_000, "attempt_start")
        )
        self.assertIn("no probe events", result.stdout)


class RunnerProbeKnobTests(unittest.TestCase):
    def test_connected_probe_keeps_loss_detection_armed(self):
        source = PATCH.read_text()
        branch = source.split(
            "if (ordinary_probe && rrc->nrRrcState == RRC_STATE_CONNECTED_NR)", 1
        )[1].split("if (rss_probe_done[pu])", 1)[0]
        self.assertIn("nr_timer_setup(t, 10, 10);", branch)
        self.assertIn("nr_timer_start(t);", branch)

    def verify_evidence(self, require_matched=False):
        command = [sys.executable, str(EVIDENCE), "verify", str(self.run_dir)]
        if require_matched:
            command.append("--require-matched")
        return subprocess.run(command, text=True, capture_output=True, check=False)

    def run_with(self, *options, env_overrides=None, expect_success=True):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        temp = pathlib.Path(self.tmp.name)
        runs = temp / "runs"
        runs.mkdir()
        ue = temp / "fake-ue"
        args_file = temp / "ue.args"
        ue.write_text(
            "#!/bin/sh\n"
            "[ -z \"${RSS_TEST_TRACE:-}\" ] || printf '%s\\n' ue >> \"$RSS_TEST_TRACE\"\n"
            ": > \"$RSS_TEST_ARGS\"\n"
            "for arg in \"$@\"; do printf '%s\\n' \"$arg\" >> \"$RSS_TEST_ARGS\"; done\n"
            "log_file=\n"
            "run_id=\n"
            "while [ \"$#\" -gt 0 ]; do\n"
            "  if [ \"$1\" = --rss.log_file ]; then log_file=$2; shift 2;\n"
            "  elif [ \"$1\" = --rss.run_id ]; then run_id=$2; shift 2; else shift; fi\n"
            "done\n"
            "printf '%s\\n' '[RSS] fake UE'\n"
            "if [ \"${RSS_TEST_SECRET_LOG:-0}\" = 1 ]; then "
            "printf 'UICC simulation: IMSI=%015d, Ki=%032d, OPc=%032d\\n' 0 0 0; fi\n"
            "printf '{\"type\":\"event\",\"run_id\":\"%s\",\"ue\":0,\"seq\":1,\"t_ns\":1,\"event\":\"attempt_start\"}\\n' \"$run_id\" > \"$log_file\"\n"
            "if [ \"${RSS_TEST_OMIT_MSG3:-0}\" != 1 ]; then "
            "printf '{\"type\":\"event\",\"run_id\":\"%s\",\"ue\":0,\"seq\":1,\"t_ns\":2,\"event\":\"msg3_tx\",\"tc_rnti\":\"0x4601\",\"frame\":100,\"slot\":2}\\n' \"$run_id\" >> \"$log_file\"; fi\n"
            "if [ \"${RSS_TEST_MIXED_PROBE:-0}\" = 1 ]; then\n"
            "  printf '{\"type\":\"event\",\"run_id\":\"%s\",\"ue\":0,\"seq\":1,\"t_ns\":3,\"event\":\"msg4_rx\"}\\n' \"$run_id\" >> \"$log_file\"\n"
            "  printf '{\"type\":\"event\",\"run_id\":\"%s\",\"ue\":1,\"seq\":1,\"t_ns\":4,\"event\":\"attempt_start\"}\\n' \"$run_id\" >> \"$log_file\"\n"
            "  printf '{\"type\":\"event\",\"run_id\":\"%s\",\"ue\":1,\"seq\":1,\"t_ns\":5,\"event\":\"msg3_tx\",\"tc_rnti\":\"0x4602\",\"frame\":101,\"slot\":2}\\n' \"$run_id\" >> \"$log_file\"\n"
            "fi\n"
            "if [ -n \"${RSS_TEST_DU_LOG:-}\" ]; then\n"
            "  printf '{\"type\":\"event\",\"run_id\":\"%s\",\"ue\":0,\"seq\":1,\"t_ns\":2,\"event\":\"msg4_rx\",\"msg5_action\":\"skipped\",\"tc_rnti\":\"0x4601\"}\\n' \"$run_id\" >> \"$log_file\"\n"
            "  printf '{\"type\":\"event\",\"run_id\":\"%s\",\"ue\":0,\"seq\":1,\"t_ns\":3,\"event\":\"msg4_ack_scheduled\",\"tc_rnti\":\"0x4601\",\"frame\":321,\"slot\":7,\"source\":\"ra_pucch\"}\\n' \"$run_id\" >> \"$log_file\"\n"
            "  if [ \"${RSS_TEST_DU_ROTATE:-0}\" = 1 ]; then\n"
            "    mv \"$RSS_TEST_DU_LOG\" \"$RSS_TEST_DU_LOG.old\"\n"
            "    : > \"$RSS_TEST_DU_LOG\"\n"
            "  else\n"
            "    printf 'Sector#0: UCI.indication slot=321.7 PUCCH format 0/1 format=0 rnti=17921 HARQ: harq_ack=%s\\n' \"${RSS_TEST_DU_OUTCOME:-ack}\" >> \"$RSS_TEST_DU_LOG\"\n"
            "  fi\n"
            "fi\n"
            "if [ \"${RSS_TEST_TWO_INT:-0}\" = 1 ]; then "
            "exec python3 -c 'import os,signal,time; n=[0]; "
            "signal.signal(signal.SIGINT, lambda *_: "
            "(n.__setitem__(0,n[0]+1), os._exit(0) if n[0] > 1 else "
            "print(\"[NR_MAC] Received detach indication\", flush=True))); "
            "time.sleep(20)'; fi\n"
        )
        ue.chmod(0o755)
        env = dict(
            os.environ,
            RSS_CONF=str(temp / "absent.conf"),
            LOGDIR=str(runs), OAI="/nonexistent", UE_BIN=str(ue),
            UE_CFG="/dev/null", UECAP="/dev/null",
            GNB_RESTART_CMD="", GNB_STOP_CMD="", GNB_READY_CMD="",
            RSS_TEST_ARGS=str(args_file),
        )
        env.update(env_overrides or {})
        result = subprocess.run(
            ["bash", str(RUNNER), "-e", "1", "-d", "1", *options],
            env=env, text=True, capture_output=True, timeout=30,
        )
        self.run_stdout = result.stdout
        if expect_success:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stderr + result.stdout)
        run_file = next(runs.glob("*/run.json"))
        self.run_dir = run_file.parent
        run = json.loads(run_file.read_text())
        self.ue_args = args_file.read_text().splitlines()
        return run

    def test_run_manifest_records_schema_clock_and_stop_status(self):
        run = self.run_with()
        self.assertEqual(run["schema_version"], "rss.run.v1")
        self.assertEqual(run["scenario"], "A")
        self.assertIn("scenario=RRCSetupComplete-omission attack=1", self.run_stdout)
        self.assertEqual(run["knobs"]["phase_ms"], 0)
        self.assertEqual(run["clock_sync"], {
            "method": "unmeasured", "offset_ns": None,
            "uncertainty_ns": None, "evidence_sha256": None,
        })
        self.assertEqual(run["software"]["ue_commit"], "unknown")
        for key in ("ue_binary_sha256", "rss_patch_sha256", "runner_sha256",
                    "label_exporter_sha256", "du_capture_sha256",
                    "log_redactor_sha256", "artifact_scanner_sha256"):
            self.assertRegex(run["software"][key], r"^[0-9a-f]{64}$")
        self.assertIsInstance(run["t_start_ns"], int)
        stopped = json.loads((self.run_dir / "run_stop.json").read_text())
        self.assertEqual(stopped["schema_version"], "rss.run-stop.v1")
        self.assertEqual(stopped["run_id"], run["run_id"])
        self.assertEqual(stopped["exit_status"], 0)
        self.assertTrue(stopped["valid"])
        self.assertEqual(stopped["stop_reason"], "clean_exit")
        self.assertEqual(stopped["label_export"], "ok")
        self.assertEqual(stopped["sensitive_artifact_scan"], "ok")
        self.assertEqual(stopped["evidence_manifest_schema"],
                         "rss.evidence-manifest.v1")
        self.assertEqual(stopped["du_ack_join"], "not_requested")
        self.assertIsNone(stopped["du_log_sha256"])
        self.assertFalse(run["orchestration"]["du_log_capture_requested"])
        self.assertIsNone(run["orchestration"]["du_sector_id"])
        self.assertIsInstance(stopped["t_stop_ns"], int)
        redaction = json.loads((self.run_dir / "ue_redaction.json").read_text())
        self.assertEqual(redaction["status"], "clean")
        self.assertEqual(redaction["redacted_lines"], 0)
        self.assertEqual(self.run_dir.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.run_dir / "ue.log").stat().st_mode & 0o777, 0o600)
        labels = [json.loads(line) for line in
                  (self.run_dir / "ground_truth.jsonl").read_text().splitlines()]
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels[0]["attempt_id"], f"{run['run_id']}:0:1")
        self.assertIsNone(labels[0]["canonical_a"])
        manifest = json.loads((self.run_dir / "evidence_manifest.json").read_text())
        self.assertEqual(manifest["run_id"], run["run_id"])
        self.assertIn("run_stop.json", {item["path"] for item in manifest["files"]})
        verified = self.verify_evidence()
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_duration_uses_watchdog_marked_sigkill(self):
        self.run_with(env_overrides={"RSS_TEST_TWO_INT": "1"})
        stopped = json.loads((self.run_dir / "run_stop.json").read_text())
        self.assertEqual(stopped["exit_status"], 137)
        self.assertEqual(stopped["stop_reason"], "duration_limit_sigkill")
        self.assertFalse(stopped["duration_all_detached"])
        self.assertTrue(stopped["duration_forced_kill"])
        self.assertTrue(stopped["valid"])

    def test_sensitive_ue_output_is_redacted_and_invalidated_before_sealing(self):
        self.run_with(
            env_overrides={"RSS_TEST_SECRET_LOG": "1"}, expect_success=False,
        )
        log = (self.run_dir / "ue.log").read_text()
        self.assertIn("[REDACTED subscriber/auth material]", log)
        self.assertNotIn("0" * 32, log)
        redaction = json.loads((self.run_dir / "ue_redaction.json").read_text())
        self.assertEqual(redaction["status"], "redacted")
        self.assertEqual(redaction["redacted_lines"], 1)
        stopped = json.loads((self.run_dir / "run_stop.json").read_text())
        self.assertFalse(stopped["valid"])
        self.assertEqual(stopped["stop_reason"], "sensitive_ue_log_redacted")
        self.assertEqual(stopped["sensitive_artifact_scan"], "ok")
        verified = self.verify_evidence()
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_sensitive_non_ue_artifact_prevents_evidence_seal(self):
        with tempfile.TemporaryDirectory() as directory:
            stop = pathlib.Path(directory) / "stop"
            stop.write_text(
                "#!/bin/sh\n"
                "printf 'IMSI=%015d, Ki=%032d, OPc=%032d\\n' 0 0 0\n"
            )
            stop.chmod(0o755)
            self.run_with(
                env_overrides={"GNB_STOP_CMD": str(stop)}, expect_success=False,
            )
        stopped = json.loads((self.run_dir / "run_stop.json").read_text())
        self.assertFalse(stopped["valid"])
        self.assertEqual(stopped["stop_reason"], "sensitive_artifact_scan_failed")
        self.assertEqual(stopped["sensitive_artifact_scan"], "failed")
        self.assertFalse((self.run_dir / "evidence_manifest.json").exists())
        diagnostic = (self.run_dir / "sensitive_artifact_check.err").read_text()
        self.assertIn("gnb_stop.txt", diagnostic)
        self.assertIn("imsi,ki,opc", diagnostic)
        self.assertNotIn("0" * 32, diagnostic)

    def test_run_scoped_du_ack_promotes_the_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            du_log = pathlib.Path(directory) / "odu.log"
            du_log.write_text("boot before this run\n")
            run = self.run_with(env_overrides={
                "ODU_LOG": str(du_log),
                "ODU_SECTOR_ID": "0",
                "RSS_TEST_DU_LOG": str(du_log),
            })
        self.assertTrue(run["orchestration"]["du_log_capture_requested"])
        self.assertEqual(run["orchestration"]["du_sector_id"], 0)
        stopped = json.loads((self.run_dir / "run_stop.json").read_text())
        self.assertEqual(stopped["du_ack_join"], "matched")
        self.assertRegex(stopped["du_log_sha256"], r"^[0-9a-f]{64}$")
        captured = (self.run_dir / "odu.log").read_text()
        self.assertNotIn("boot before this run", captured)
        self.assertIn("UCI.indication slot=321.7", captured)
        manifest = json.loads((self.run_dir / "du_log_slice.json").read_text())
        self.assertEqual(manifest["sha256"], stopped["du_log_sha256"])
        labels = [json.loads(line) for line in
                  (self.run_dir / "ground_truth.jsonl").read_text().splitlines()]
        self.assertIs(labels[0]["canonical_a"], True)
        self.assertEqual(labels[0]["canonical_a_evidence"],
                         "ue_scheduler+ocudu_fapi")
        evidence = labels[0]["du_ack_evidence"]
        self.assertEqual(evidence["log_sha256"], stopped["du_log_sha256"])
        self.assertEqual(evidence["sector_id"], 0)
        verified = self.verify_evidence(require_matched=True)
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_evidence_verifier_rejects_tamper_and_missing_artifact(self):
        for mode in ("tamper", "missing"):
            with self.subTest(mode=mode):
                self.run_with()
                if mode == "tamper":
                    with (self.run_dir / "ue.log").open("a") as handle:
                        handle.write("changed after seal\n")
                else:
                    (self.run_dir / "ground_truth.jsonl").unlink()
                verified = self.verify_evidence()
                self.assertNotEqual(verified.returncode, 0)

    def test_evidence_seal_and_verify_apply_the_current_sensitive_policy(self):
        secret = "milenage output ik:" + "".join(
            f"{index:02x} " for index in range(16)) + "\n"

        self.run_with()
        artifact = self.run_dir / "ground_truth.jsonl"
        artifact.write_text(secret)
        manifest_path = self.run_dir / "evidence_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        entry = next(item for item in manifest["files"] if item["path"] == artifact.name)
        entry["size"] = artifact.stat().st_size
        entry["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        verified = self.verify_evidence()
        self.assertNotEqual(verified.returncode, 0)
        self.assertIn("current sensitive artifact scan failed", verified.stderr)
        self.assertNotIn("00 01 02 03", verified.stderr)

        self.run_with()
        artifact = self.run_dir / "ground_truth.jsonl"
        artifact.write_text(secret)
        (self.run_dir / "evidence_manifest.json").unlink()
        sealed = subprocess.run(
            [sys.executable, str(EVIDENCE), "seal", str(self.run_dir)],
            text=True, capture_output=True, check=False,
        )
        self.assertNotEqual(sealed.returncode, 0)
        self.assertFalse((self.run_dir / "evidence_manifest.json").exists())
        self.assertIn("current sensitive artifact scan failed", sealed.stderr)
        self.assertNotIn("00 01 02 03", sealed.stderr)

    def test_evidence_seal_rejects_cross_file_run_id_mismatch(self):
        self.run_with()
        (self.run_dir / "evidence_manifest.json").unlink()
        stopped = json.loads((self.run_dir / "run_stop.json").read_text())
        stopped["run_id"] = "different-run"
        (self.run_dir / "run_stop.json").write_text(json.dumps(stopped))
        result = subprocess.run(
            [sys.executable, str(EVIDENCE), "seal", str(self.run_dir)],
            text=True, capture_output=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("run_id do not match", result.stderr)

    def test_matched_verifier_requires_sealed_raw_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            du_log = pathlib.Path(directory) / "odu.log"
            du_log.write_text("boot before this run\n")
            self.run_with(env_overrides={
                "ODU_LOG": str(du_log), "ODU_SECTOR_ID": "0",
                "RSS_TEST_DU_LOG": str(du_log),
            })
        (self.run_dir / "evidence_manifest.json").unlink()
        (self.run_dir / "attempts.jsonl").unlink()
        sealed = subprocess.run(
            [sys.executable, str(EVIDENCE), "seal", str(self.run_dir)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(sealed.returncode, 0, sealed.stderr)
        verified = self.verify_evidence(require_matched=True)
        self.assertNotEqual(verified.returncode, 0)
        self.assertIn("sealed attempts.jsonl", verified.stderr)

    def test_matched_verifier_replays_labels_from_raw_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            du_log = pathlib.Path(directory) / "odu.log"
            du_log.write_text("boot before this run\n")
            self.run_with(env_overrides={
                "ODU_LOG": str(du_log), "ODU_SECTOR_ID": "0",
                "RSS_TEST_DU_LOG": str(du_log),
            })
        (self.run_dir / "evidence_manifest.json").unlink()
        label_path = self.run_dir / "ground_truth.jsonl"
        row = json.loads(label_path.read_text())
        row["event_count"] = 999
        label_path.write_text(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        sealed = subprocess.run(
            [sys.executable, str(EVIDENCE), "seal", str(self.run_dir)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(sealed.returncode, 0, sealed.stderr)
        verified = self.verify_evidence(require_matched=True)
        self.assertNotEqual(verified.returncode, 0)
        self.assertIn("replayed raw evidence", verified.stderr)

    def test_captured_dtx_reports_no_match_and_keeps_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            du_log = pathlib.Path(directory) / "odu.log"
            du_log.write_text("boot before this run\n")
            self.run_with(env_overrides={
                "ODU_LOG": str(du_log),
                "ODU_SECTOR_ID": "0",
                "RSS_TEST_DU_LOG": str(du_log),
                "RSS_TEST_DU_OUTCOME": "dtx",
            })
        stopped = json.loads((self.run_dir / "run_stop.json").read_text())
        self.assertEqual(stopped["du_ack_join"], "no_match")
        labels = [json.loads(line) for line in
                  (self.run_dir / "ground_truth.jsonl").read_text().splitlines()]
        self.assertIs(labels[0]["canonical_a_ue"], True)
        self.assertIsNone(labels[0]["canonical_a"])

    def test_du_log_rotation_leaves_the_candidate_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            du_log = pathlib.Path(directory) / "odu.log"
            du_log.write_text("boot before this run\n")
            self.run_with(env_overrides={
                "ODU_LOG": str(du_log),
                "ODU_SECTOR_ID": "0",
                "RSS_TEST_DU_LOG": str(du_log),
                "RSS_TEST_DU_ROTATE": "1",
            })
        stopped = json.loads((self.run_dir / "run_stop.json").read_text())
        self.assertEqual(stopped["du_ack_join"], "capture_finish_failed")
        self.assertIsNone(stopped["du_log_sha256"])
        labels = [json.loads(line) for line in
                  (self.run_dir / "ground_truth.jsonl").read_text().splitlines()]
        self.assertIs(labels[0]["canonical_a_ue"], True)
        self.assertIsNone(labels[0]["canonical_a"])

    def test_measured_clock_basis_is_recorded(self):
        digest = "a" * 64
        run = self.run_with(env_overrides={
            "CLOCK_SYNC_METHOD": "ptp", "CLOCK_OFFSET_NS": "-1200",
            "CLOCK_UNCERTAINTY_NS": "300", "CLOCK_EVIDENCE_SHA256": digest,
        })
        self.assertEqual(run["clock_sync"], {
            "method": "ptp", "offset_ns": -1200,
            "uncertainty_ns": 300, "evidence_sha256": digest,
        })

    def test_probe_instances_remain_in_the_radio_batch(self):
        run = self.run_with("-u", "3", "-p", "1")
        self.assertEqual(run["knobs"]["probe_ues"], 1)
        self.assertEqual(run["radio"]["share_nue"], 3)

    def test_no_probe_keeps_every_instance_in_the_batch(self):
        run = self.run_with("-u", "3")
        self.assertEqual(run["knobs"]["probe_ues"], 0)
        self.assertEqual(run["radio"]["share_nue"], 3)

    def test_partial_radio_batch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = pathlib.Path(directory)
            ue = temp / "fake-ue"
            ue.write_text("#!/bin/sh\nexit 0\n")
            ue.chmod(0o755)
            env = dict(
                os.environ,
                RSS_CONF=str(temp / "absent.conf"), LOGDIR=str(temp / "runs"),
                OAI="/nonexistent", UE_BIN=str(ue), UE_CFG="/dev/null",
                UECAP="/dev/null", GNB_RESTART_CMD="", GNB_STOP_CMD="",
                GNB_READY_CMD="", RSS_SHARE_NUE="1",
            )
            result = subprocess.run(
                ["bash", str(RUNNER), "-e", "1", "-u", "2", "-p", "1", "-d", "1"],
                env=env, text=True, capture_output=True, timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must equal NUM_UES", result.stderr)

    def test_msg4_ack_is_recorded_and_passed_to_the_ue(self):
        run = self.run_with("-A", "0")
        self.assertEqual(run["knobs"]["msg4_ack"], 0)
        self.assertEqual(run["scenario"], "A_no_ack")
        self.assertIn("scenario=RRCSetup-HARQ-ACK-withholding attack=1",
                      self.run_stdout)
        i = self.ue_args.index("--rss.msg4_ack")
        self.assertEqual(self.ue_args[i + 1], "0")

    def test_msg3_restart_variant_has_its_own_scenario(self):
        run = self.run_with("-M", "0")
        self.assertEqual(run["scenario"], "A_early")
        self.assertIn("scenario=post-RRCSetupRequest-abort attack=1",
                      self.run_stdout)
        labels = [json.loads(line) for line in
                  (self.run_dir / "ground_truth.jsonl").read_text().splitlines()]
        self.assertIs(labels[0]["canonical_msg3_ue"], True)
        self.assertIsNone(labels[0]["canonical_msg3_only"])

    def test_msg3_restart_rejects_unimplemented_occupancy_control(self):
        result = subprocess.run(
            ["bash", str(RUNNER), "-e", "1", "-M", "0", "-o", "1"],
            env=dict(os.environ, RSS_CONF="/nonexistent"),
            text=True, capture_output=True, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gNB-observed lifetime control", result.stderr)

    def test_msg3_restart_fails_without_mac_confirmed_transmission(self):
        self.run_with(
            "-M", "0", env_overrides={"RSS_TEST_OMIT_MSG3": "1"},
            expect_success=False,
        )
        stopped = json.loads((self.run_dir / "run_stop.json").read_text())
        self.assertFalse(stopped["valid"])
        self.assertEqual(stopped["stop_reason"], "zero_msg3_tx")

    def test_probe_msg4_does_not_invalidate_msg3_only_attacker(self):
        self.run_with(
            "-u", "2", "-p", "1", "-M", "0",
            env_overrides={"RSS_TEST_MIXED_PROBE": "1"},
        )
        stopped = json.loads((self.run_dir / "run_stop.json").read_text())
        self.assertTrue(stopped["valid"])
        labels = [json.loads(line) for line in
                  (self.run_dir / "ground_truth.jsonl").read_text().splitlines()]
        self.assertTrue(any(row["ue"] == 1 and row["canonical_msg3_ue"]
                            for row in labels))

    def test_run_does_not_kill_an_unrelated_ue_process(self):
        self.assertNotIn("pkill", RUNNER.read_text())
        process = subprocess.Popen([shutil.which("sleep"), "30"])
        try:
            self.assertIsNone(process.poll())
            self.run_with()
            self.assertIsNone(process.poll())
        finally:
            process.terminate()
            process.wait(timeout=5)

    def test_probe_mode_and_pacing_are_recorded_and_passed(self):
        run = self.run_with(
            "-u", "3", "-p", "1",
            env_overrides={"PROBE_RA_ONLY": "1", "PROBE_INTERVAL_MS": "1500"},
        )
        self.assertEqual(run["knobs"]["probe_ra_only"], 1)
        self.assertEqual(run["knobs"]["probe_interval_ms"], 1500)
        for knob, value in (("--rss.probe_ra_only", "1"),
                            ("--rss.probe_interval_ms", "1500")):
            i = self.ue_args.index(knob)
            self.assertEqual(self.ue_args[i + 1], value)

    def test_phase_is_recorded_and_passed_to_the_ue(self):
        run = self.run_with("-u", "4", env_overrides={"PHASE_MS": "75"})
        self.assertEqual(run["knobs"]["phase_ms"], 75)
        i = self.ue_args.index("--rss.phase_ms")
        self.assertEqual(self.ue_args[i + 1], "75")

    def test_phase_rejects_values_outside_0_to_5000(self):
        for value in ("-1", "5001", "bad"):
            with self.subTest(value=value):
                result = subprocess.run(
                    ["bash", str(RUNNER), "-e", "1"],
                    env=dict(os.environ, RSS_CONF="/nonexistent", PHASE_MS=value),
                    text=True, capture_output=True, timeout=10,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("PHASE_MS must be 0..5000", result.stderr)

    def test_attack_without_banner_or_attempts_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(
                os.environ,
                RSS_CONF=str(pathlib.Path(directory) / "absent.conf"),
                LOGDIR=str(pathlib.Path(directory) / "runs"),
                OAI="/nonexistent", UE_BIN=shutil.which("true"),
                UE_CFG="/dev/null", UECAP="/dev/null",
                GNB_RESTART_CMD="", GNB_STOP_CMD="",
            )
            result = subprocess.run(
                ["bash", str(RUNNER), "-e", "1", "-d", "1"],
                env=env, text=True, capture_output=True, timeout=30,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("zero attempts", result.stdout)

    def test_baseline_without_attempt_log_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = pathlib.Path(directory) / "runs"
            env = dict(
                os.environ,
                RSS_CONF=str(pathlib.Path(directory) / "absent.conf"),
                LOGDIR=str(runs), OAI="/nonexistent", UE_BIN=shutil.which("true"),
                UE_CFG="/dev/null", UECAP="/dev/null",
                GNB_RESTART_CMD="", GNB_STOP_CMD="", GNB_READY_CMD="",
            )
            result = subprocess.run(
                ["bash", str(RUNNER), "-e", "0", "-d", "1", "-n", "baseline"],
                env=env, text=True, capture_output=True, timeout=30,
            )
            stopped = json.loads(next(runs.glob("*/run_stop.json")).read_text())
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(stopped["valid"])
        self.assertEqual(stopped["stop_reason"], "clean_exit")
        self.assertEqual(stopped["label_export"], "no_events")

    def test_gnb_stop_settle_restart_order_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = pathlib.Path(directory)
            trace = temp / "trace"
            stubs = temp / "stubs"
            stubs.mkdir()
            for name, line in (("stop", "stop"), ("restart", "restart")):
                script = stubs / name
                script.write_text(f"#!/bin/sh\nprintf '%s\\n' {line} >> \"$TRACE\"\n")
                script.chmod(0o755)
            sleep = stubs / "sleep"
            sleep.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = 4 ]; then printf 'sleep:%s\\n' \"$1\" >> \"$TRACE\"; exit 0; fi\n"
                "exec /bin/sleep \"$@\"\n"
            )
            sleep.chmod(0o755)
            self.run_with(
                env_overrides={
                    "TRACE": str(trace),
                    "PATH": str(stubs) + os.pathsep + os.environ["PATH"],
                    "GNB_STOP_CMD": str(stubs / "stop"),
                    "GNB_RESTART_CMD": str(stubs / "restart"),
                    "GNB_SETTLE_S": "4",
                },
            )
            self.assertEqual(trace.read_text().splitlines(), ["stop", "sleep:4", "restart"])

    def test_gnb_readiness_is_checked_before_the_ue_starts(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = pathlib.Path(directory)
            trace = temp / "trace"
            ready = temp / "ready"
            ready.write_text(
                "#!/bin/sh\nprintf '%s\\n' ready >> \"$RSS_TEST_TRACE\"\n"
            )
            ready.chmod(0o755)
            run = self.run_with(
                env_overrides={
                    "RSS_TEST_TRACE": str(trace),
                    "GNB_READY_CMD": str(ready),
                },
            )
            self.assertTrue(run["orchestration"]["gnb_ready_check"])
            self.assertEqual(trace.read_text().splitlines(), ["ready", "ue"])

    def test_failed_gnb_readiness_prevents_ue_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = pathlib.Path(directory)
            ue_marker = temp / "ue-started"
            ue = temp / "fake-ue"
            ue.write_text(f"#!/bin/sh\ntouch {ue_marker}\n")
            ue.chmod(0o755)
            env = dict(
                os.environ,
                RSS_CONF=str(temp / "absent.conf"),
                LOGDIR=str(temp / "runs"), OAI="/nonexistent", UE_BIN=str(ue),
                UE_CFG="/dev/null", UECAP="/dev/null",
                GNB_RESTART_CMD="", GNB_STOP_CMD="", GNB_READY_CMD="false",
                GNB_READY_TIMEOUT_S="1", GNB_READY_INTERVAL_S="1",
                GNB_READY_PROBE_TIMEOUT_S="1",
            )
            result = subprocess.run(
                ["bash", str(RUNNER), "-e", "1", "-d", "1"],
                env=env, text=True, capture_output=True, timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("UE was not launched", result.stdout)
            self.assertFalse(ue_marker.exists())


class CuratedPatchContractTests(unittest.TestCase):
    def test_msg4_ack_uses_the_rnti_saved_in_the_scheduled_pucch(self):
        content = ACK_RNTI_PATCH.read_text()
        self.assertIn("-                   mac->ra.t_crnti,", content)
        self.assertIn("+                   ra_pucch->pucch_pdu.rnti,", content)
        self.assertLess(
            content.index("+                   ra_pucch->pucch_pdu.rnti,"),
            content.index("free_and_zero(mac->ra.ra_pucch);"),
        )

    def test_delayed_ra_only_probe_uses_probe_scheduler_and_msg3_retry(self):
        content = PATCH.read_text()
        self.assertIn(
            "const bool attack_ue = !nr_rss_is_probe(ue) || nr_rss_probe_ra_only();",
            content,
        )
        self.assertIn("if (!polled && !probe && !tac->rss_msg3_tx_confirmed)", content)
        self.assertIn(
            "if (probe) {\n+    const int pu = ue >= 0 && ue < RSS_MAX_UE ? ue : 0;",
            content,
        )
        self.assertIn(
            "if (ordinary_probe && rrc->nrRrcState == RRC_STATE_CONNECTED_NR)",
            content,
        )

    def test_curated_patch_contains_only_the_supported_feature_family(self):
        content = PATCH.read_text()
        for marker in ("probe_ues", "probe_delay_ms", "probe_ra_only",
                       "probe_interval_ms", "phase_ms", "RSS_SHARE_NUE",
                       "rss_reject_reset_skipped", "msg4_ack_withheld",
                       "msg4_ack_scheduled", "msg5_action", "msg5_submitted",
                       "!nr_rss_is_probe(ue)"):
            self.assertIn(marker, content)
        self.assertIn(
            "if (!nr_rss_enabled()) {\n"
            "+    NR_UE_MAC_reset_cause_t cause = REJECT;",
            content,
        )
        self.assertNotIn(
            "if (!(nr_rss_enabled() && nr_rss_is_probe((int)rrc->ue_id))) {",
            content,
        )
        self.assertNotIn("rss_phase_applied", content)
        self.assertIn(
            "if (nr_rss_enabled() && !nr_rss_is_probe(ue))\n"
            "+    d += ue * cfg->phase_ms;",
            content,
        )
        self.assertIn("int common_harq = -1;", content)
        self.assertIn(
            "if (!nr_rss_honor_reject())\n"
            "+             nr_rss_arm_retry(rrc, 0);",
            content,
        )
        self.assertNotIn(
            "if (!nr_rss_honor_reject())\n"
            "+             nr_rss_arm_retry(rrc, 10);",
            content,
        )
        additions = "\n".join(
            line[1:] for line in content.splitlines()
            if line.startswith("+") and not line.startswith("+++"))
        self.assertIn('LOG_I(SIM, "UICC simulation configured\\n");', additions)
        self.assertNotIn('UICC simulation: IMSI=%s', additions)
        self.assertNotIn("log_dump(SIM,uicc->", additions)
        deletions = "\n".join(
            line[1:] for line in content.splitlines()
            if line.startswith("-") and not line.startswith("---"))
        for label in ("opc:", "amf:", "key:", "sqn:", "rand:",
                      "milenage output ik:", "milenage output ck:",
                      "milenage output res:", "milenage output autn:"):
            self.assertIn(f'"{label}"', deletions)
        self.assertNotIn(r'\"actual_reach\":\"msg5_skip\"', content)
        self.assertIn("static atomic_uint_fast64_t rss_attack_msg3_t0_ns;", content)
        self.assertIn(
            "config_sib1->can_start_ra = !rrc->is_NTN_UE && "
            "!nr_rss_probe_withheld((int)rrc->ue_id);",
            content,
        )
        self.assertIn("if (t0 == 0)\n+    return true;", content)
        for rejected in ("ra_depth", "evict_ues", "anas_ues",
                         "harvest_ues", "RSS_PHASE_STAGGER", "RSS_RO_"):
            self.assertNotIn(rejected, content)

    def test_max_duration_quiet_stops_without_disabling_interception(self):
        content = PATCH.read_text()
        self.assertIn(
            "bool nr_rss_enabled(void)\n+{\n+  return rss_get_cfg()->enable != 0;\n+}",
            content,
        )
        poll = content.index("+static void rss_poll(NR_UE_RRC_INST_t *rrc)")
        killed = content.index("+  if (!nr_rss_enabled() || rss_killed)\n+    return;", poll)
        expiry = content.index("+  if (cfg->max_duration_s > 0", killed)
        msg3_retry = content.index("+  if (!nr_rss_wait_for_msg4() && rss_take_msg3_tx(ue))", expiry)
        probe_retry = content.index("+    handle_t300_expiry(rrc);", msg3_retry)
        self.assertLess(killed, expiry)
        self.assertLess(expiry, msg3_retry)
        self.assertLess(expiry, probe_retry)
        self.assertIn(
            "if (t300_expired && !(nr_rss_enabled() && rss_killed))",
            content,
        )
        self.assertIn("attack scheduling stopped; interception remains active", content)
        self.assertNotIn("normal attach resumes", content)

    def test_ra_only_phase_reaches_both_probe_schedulers(self):
        content = PATCH.read_text()
        self.assertIn("static uint64_t rss_probe_delay_ms(int ue, int base_ms)", content)
        self.assertIn(
            "const uint64_t delay_ms = rss_probe_delay_ms(ue, rss_get_cfg()->probe_delay_ms);",
            content,
        )
        self.assertIn(
            "rss_probe_next_ns[pu] = now + rss_probe_delay_ms(ue, cfg->probe_interval_ms) * 1000000ULL;",
            content,
        )
        self.assertNotIn(
            "if (nr_rss_enabled() && (!nr_rss_is_probe(ue) || nr_rss_probe_ra_only()))",
            content,
        )

    def test_rss_options_are_registered_before_unknown_option_validation(self):
        content = PATCH.read_text()
        self.assertIn("void nr_rss_config_init(void);", content)
        self.assertIn(
            "void nr_rss_config_init(void)\n+{\n"
            "+  const rss_cfg_t *cfg = rss_get_cfg();\n"
            "+  if (cfg->enable && cfg->probe_ues > 0 && cfg->probe_ues >= NB_UE_INST)\n"
            "+    atomic_store_explicit(&rss_attack_msg3_t0_ns, rss_now_ns(), memory_order_release);\n+}",
            content,
        )
        common = content.index("get_common_options(uniqCfg);")
        eager = content.index("nr_rss_config_init();", common)
        clear = content.index("CONFIG_CLEARRTFLAG(CONFIG_NOEXITONHELP);", eager)
        self.assertLess(common, eager)
        self.assertLess(eager, clear)

    def test_jsonl_writer_serializes_mac_and_rrc_threads(self):
        content = PATCH.read_text()
        self.assertIn("static pthread_mutex_t rss_log_mutex = PTHREAD_MUTEX_INITIALIZER;", content)
        lock = content.index("pthread_mutex_lock(&rss_log_mutex);")
        write = content.index('fprintf(rss_log_fd,', lock)
        unlock = content.index("pthread_mutex_unlock(&rss_log_mutex);", write)
        self.assertLess(lock, write)
        self.assertLess(write, unlock)

class ProbeMetricContractTests(unittest.TestCase):
    def test_harq_outcomes_are_separate_from_the_conres_diagnostic(self):
        content = PROBE.read_text()
        self.assertIn('"conres_event_logged"', content)
        self.assertNotIn('"conres_ce_acked"', content)
        for outcome in ("ack", "dtx", "nack"):
            self.assertIn(f"HARQ: harq_ack={outcome}", content)
            self.assertIn(f'"harq_ack_{outcome}"', content)
        self.assertIn('"dl_harq_maxretx_discard"', content)

    def test_lab_suite_surfaces_harq_metrics_not_the_ambiguous_old_key(self):
        content = LAB_SUITE.read_text()
        self.assertIn("harq_ack_", content)
        self.assertIn("dl_harq_maxretx_discard", content)
        self.assertNotIn("conres_ce_acked", content)


if __name__ == "__main__":
    unittest.main()
