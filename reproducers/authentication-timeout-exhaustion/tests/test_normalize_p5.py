import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from analysis.normalize_p5 import normalize, parse_amf, parse_cu, realtime_ns


def fingerprint(imsi):
    return hashlib.sha256(imsi.encode()).hexdigest()


class NormalizeP5Test(unittest.TestCase):
    def fixture(self, mode="attack"):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        imsies = ("001010000000001", "001010000000002")
        profiles = {
            "schema": "auth-timeout.profiles.v1", "attacker_count": 2,
            "profiles": [
                {"role": "attacker", "subscriber_fingerprint": fingerprint(imsi), "config_sha256": str(index) * 64}
                for index, imsi in enumerate(imsies, 1)
            ] + [{"role": "witness", "subscriber_fingerprint": "f" * 64, "config_sha256": "3" * 64}],
        }
        (root / "profiles.manifest.json").write_text(json.dumps(profiles))
        (root / "run.json").write_text(json.dumps({
            "schema": "auth-timeout.run.v1", "run_id": "r1", "mode": mode,
            "attacker_count": 2,
        }))
        cu_lines, amf_lines, logs = [], [], []
        for index, imsi in enumerate(imsies, 1):
            ue, ran, amf = index + 10, index + 20, index + 30
            second = index
            cu_lines.extend([
                f"2026-11-09T00:00:0{second}.000001 [RRC     ] [D] ue={ue} c-rnti=0x460{index}: Rx SRB1 DCCH UL rrcSetupComplete (33 B)",
                f"2026-11-09T00:00:0{second}.000002 [NGAP    ] [D] ue={ue} ran_ue={ran}: NGAP UE context created",
                f"2026-11-09T00:00:0{second}.000003 [NGAP    ] [I] Tx PDU ue={ue} ran_ue={ran}: InitialUEMessage",
                f"2026-11-09T00:00:0{second}.000004 [NGAP    ] [D] ue={ue} ran_ue={ran}: Setting AMF-UE-NGAP-ID={amf}",
                f"2026-11-09T00:00:{30 + second}.000002 [NGAP    ] [D] ue={ue} ran_ue={ran} amf_ue={amf}: Removing NGAP UE context",
            ])
            msin = imsi[5:]
            suci = f"suci-0-001-01-0-0-0-{msin}"
            amf_lines.extend([
                f"2026-11-09T00:00:0{second}.000002Z [amf] INFO: InitialUEMessage",
                f"2026-11-09T00:00:0{second}.000003Z [amf] INFO:     RAN_UE_NGAP_ID[{ran}] AMF_UE_NGAP_ID[{amf}]",
                f"2026-11-09T00:00:0{second}.000004Z [amf] INFO: [{suci}]    SUCI (../src/amf/gmm-handler.c:183)",
                f"2026-11-09T00:00:0{second}.000005Z [amf] DEBUG: [{suci}] Authentication request",
            ])
            if mode == "control":
                amf_lines.append(f"2026-11-09T00:00:0{second}.100000Z [amf] DEBUG: [{suci}] Authentication response")
            amf_lines.extend([
                f"2026-11-09T00:00:{30 + second}.000000Z [amf] DEBUG: UEContextReleaseCommand",
                f"2026-11-09T00:00:{30 + second}.000001Z [amf] DEBUG:     RAN_UE_NGAP_ID[{ran}] AMF_UE_NGAP_ID[{amf}]",
            ])
            log = root / f"attacker-{index}.log"
            marker = "authentication_request_withheld" if mode == "attack" else "authentication_response_submitted"
            log.write_text(f"AUTH_TIMEOUT_EXHAUSTION event={marker} ue=0 response_submitted={'false' if mode == 'attack' else 'true'}\n")
            logs.append(log)
        (root / "cu.log").write_text("\n".join(cu_lines) + "\n")
        (root / "amf.log").write_text("\n".join(amf_lines) + "\n")
        (root / "service.jsonl").write_text("".join(
            json.dumps({"phase": "impact", "realtime_ns": 2_000_000_000_000_000_000 + attempt}) + "\n"
            for attempt in range(1, 6)
        ))
        return temporary, root, logs

    def test_attack_logs_exact_join(self):
        temporary, root, logs = self.fixture()
        self.addCleanup(temporary.cleanup)
        truth, contexts = normalize(root, logs)
        self.assertEqual(len(truth), 2)
        self.assertEqual(len(contexts), 2)
        self.assertTrue(all(row["rrc_setup_complete"] and row["initial_ue_message"] for row in contexts))
        self.assertTrue(all(row["authentication_request_count"] == 1 for row in contexts))
        self.assertTrue(all(row["authentication_response_count"] == 0 for row in contexts))

    def test_control_requires_submitted_marker_and_amf_response(self):
        temporary, root, logs = self.fixture("control")
        self.addCleanup(temporary.cleanup)
        truth, contexts = normalize(root, logs)
        self.assertTrue(all(row["response_submitted"] for row in truth))
        self.assertTrue(all(row["authentication_response_count"] == 1 for row in contexts))

    def test_multiple_uicc_markers_share_one_process_log(self):
        temporary, root, logs = self.fixture()
        self.addCleanup(temporary.cleanup)
        profiles = json.loads((root / "profiles.manifest.json").read_text())
        for ue_id, row in enumerate(profiles["profiles"][:2]):
            row.update(process_index=0, ue_id=ue_id)
        profiles["attacker_process_count"] = 1
        (root / "profiles.manifest.json").write_text(json.dumps(profiles))
        run = json.loads((root / "run.json").read_text())
        run["attacker_process_count"] = 1
        (root / "run.json").write_text(json.dumps(run))
        logs[0].write_text(
            "AUTH_TIMEOUT_EXHAUSTION event=authentication_request_withheld ue=0 response_submitted=false\n"
            "AUTH_TIMEOUT_EXHAUSTION event=authentication_request_withheld ue=1 response_submitted=false\n"
        )
        truth, contexts = normalize(root, logs[:1])
        self.assertEqual(len(truth), 2)
        self.assertEqual(len(contexts), 2)

    def test_missing_cu_binding_fails_closed(self):
        temporary, root, logs = self.fixture()
        self.addCleanup(temporary.cleanup)
        lines = (root / "cu.log").read_text().splitlines()
        (root / "cu.log").write_text("\n".join(line for line in lines if "AMF-UE-NGAP-ID=31" not in line) + "\n")
        with self.assertRaises(ValueError):
            normalize(root, logs)

    def test_parsers_ignore_unrelated_subscriber(self):
        self.assertEqual(parse_cu("unrelated\n"), {})
        self.assertEqual(parse_amf("unrelated\n"), [])

    def test_timestamp_keeps_nanoseconds(self):
        value = realtime_ns("2026-11-09T00:00:01.000000123Z event")
        self.assertEqual(value % 1_000_000_000, 123)


if __name__ == "__main__":
    unittest.main()
