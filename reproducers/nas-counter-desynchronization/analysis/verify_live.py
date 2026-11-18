#!/usr/bin/env python3
"""L3-06 UE→RAN→계측→production 탐지 실행을 독립 차원으로 판정한다."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


ALERT = re.compile(r"^ALERT (?P<action>\S+) rule=(?P<rule>\S+) cell=(?P<cell>\d+) t=(?P<t>\d+)(?P<rest>.*)$")
SEND = re.compile(r"\bsend file=(?P<file>\S+).*\bstatus=(?P<status>\d+) accepted=(?P<accepted>\d+) rejected=(?P<rejected>\d+)")
DETECTOR_COMMIT = "766f5569d0ddb425c14bf210a31c38ac60eceef9"


def regular(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"필수 일반 파일이 아닙니다: {path}")
    return path


def sha256(path: Path) -> str:
    return hashlib.sha256(regular(path).read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(regular(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 객체가 아닙니다: {path}")
    return value


def load_jsonl(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in regular(path).read_text(encoding="utf-8").splitlines() if line]
    if not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"JSONL이 비었거나 객체가 아닙니다: {path}")
    return rows


def parse_alerts(path: Path) -> list[dict]:
    alerts = []
    for line in regular(path).read_text(encoding="utf-8", errors="replace").splitlines():
        match = ALERT.match(line)
        if match:
            row = match.groupdict()
            row.update({"schema": "ran-reproducer.detector.v1", "cell": int(row["cell"]),
                        "t": int(row["t"]), "raw": line})
            alerts.append(row)
    return alerts


def context(row: dict) -> tuple:
    return row.get("cell_id"), row.get("du_ue_id"), row.get("cu_ue_id"), row.get("crnti")


def unsolicited_rejects(events: list[dict]) -> list[dict]:
    seen_commands: set[tuple] = set()
    rejects = []
    for row in sorted(events, key=lambda value: (value.get("t_ms", 0), value.get("seq", 0))):
        key = context(row)
        if row.get("msg") == "SecurityModeCommand":
            seen_commands.add(key)
        elif row.get("msg") == "SecurityModeReject" and key not in seen_commands:
            rejects.append(row)
    return rejects


def session_started_at(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{8}T\d{6}Z", value):
        raise ValueError("telemetry hello session 시각이 잘못됐습니다")
    return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def verify(root: Path, mode: str, run_id: str, binary: Path, ue_config: Path, uecap: Path, patch: Path) -> dict:
    if root.is_symlink() or not root.is_dir() or mode not in {"control", "emulation"}:
        raise ValueError("실행 디렉터리 또는 mode가 잘못됐습니다")
    observations = root / "observations.jsonl"
    telemetry = root / "live/telemetry.jsonl"
    if sha256(observations) != sha256(telemetry):
        raise ValueError("계측 원문과 탐지 엔진 입력 기록이 다릅니다")

    rows = load_jsonl(observations)
    hello = [row for row in rows if row.get("type") == "hello"]
    gaps = [row for row in rows if row.get("type") == "gap"]
    kpm = [row for row in rows if row.get("type") == "kpm2"]
    events = [row for row in rows if row.get("type") == "ue_evt"]
    rejects = [row for row in events if row.get("msg") == "SecurityModeReject"]
    unsolicited = unsolicited_rejects(events)
    commands_before_reject = len(rejects) - len(unsolicited)
    auth_responses = [row for row in events if row.get("msg") == "AuthenticationResponse"]

    profile_id = os.environ.get("RAN_REPRO_PROFILE_ID", "p5")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", profile_id) is None:
        raise ValueError("profile id가 잘못됐습니다")
    alerts = parse_alerts(root / "live/detector.stdout")
    raises = [row for row in alerts if row["action"] == "RAISE" and row["rule"] == "L3-06"]
    ue_log = regular(root / "ue.log").read_text(encoding="utf-8", errors="replace")
    reject_markers = ue_log.count("NAS_COUNTER_DESYNC event=unsolicited_security_mode_reject")
    control_markers = ue_log.count("NAS_COUNTER_DESYNC event=authentication_response_submitted")
    crashes = len(re.findall(r"Segmentation fault|Assertion|Caught signal|core dumped", ue_log))
    status = int(regular(root / "ue.exit").read_text().strip())
    service = load_json(root / "service.json")

    components = load_json(root / "live/components.json")
    sender_status = int(regular(root / "live/sender.exit").read_text().strip())
    sends = [match.groupdict() for line in regular(root / "live/sender.log").read_text(encoding="utf-8", errors="replace").splitlines()
             if (match := SEND.search(line))]
    dashboard_accepted = sum(int(row["accepted"]) for row in sends)
    dashboard_rejected = sum(int(row["rejected"]) for row in sends)
    evidence_delivered = any(row["file"].endswith("/evidence.jsonl") and int(row["accepted"]) > 0 for row in sends)

    expected = 0 if mode == "control" else 1
    input_ok = (len(hello) == 1 and hello[0].get("period_ms") == 100 and hello[0].get("ue_evt") is True
                and [row.get("seq") for row in rows] == list(range(1, len(rows) + 1)) and not gaps and bool(kpm))
    mechanism_ok = (len(rejects) == expected and len(unsolicited) == expected and commands_before_reject == 0
                    and reject_markers == expected and control_markers >= (1 if mode == "control" else 0))
    detector_ok = len(raises) == expected
    process_ok = status == 0 and crashes == 0
    control_service_ok = mode != "control" or all(service.get(key) is True for key in ("registration_ok", "pdu_session_ok", "ping_ok"))
    delivery_ok = sender_status == 0 and dashboard_accepted > 0 and dashboard_rejected == 0 and (mode == "control" or evidence_delivered)

    for name, values in (("detector", components.get("detector")), ("telemetry", components.get("telemetry"))):
        if not isinstance(values, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(values.get("binary_sha256", ""))):
            raise ValueError(f"{name} 구성요소 해시가 없습니다")
    if components["detector"].get("commit") != DETECTOR_COMMIT:
        raise ValueError("검증된 production detector 커밋이 아닙니다")
    if not re.fullmatch(r"[0-9a-f]{64}", str(components.get("dashboard", {}).get("sender_sha256", ""))):
        raise ValueError("dashboard sender 해시가 없습니다")

    checks = {
        "hello_period_100ms": len(hello) == 1 and hello[0].get("period_ms") == 100,
        "sequence_contiguous": [row.get("seq") for row in rows] == list(range(1, len(rows) + 1)),
        "gap_count": len(gaps), "kpm2_count": len(kpm), "authentication_response_count": len(auth_responses),
        "security_mode_reject_count": len(rejects), "unsolicited_security_mode_reject_count": len(unsolicited),
        "security_mode_command_before_reject_count": commands_before_reject,
        "ue_reject_marker_count": reject_markers, "ue_control_marker_count": control_markers,
        "ue_exit_status": status, "crash_count": crashes, "l3_06_raise_count": len(raises),
        "dashboard_sender_exit_status": sender_status, "dashboard_accepted_lines": dashboard_accepted,
        "dashboard_rejected_lines": dashboard_rejected, "dashboard_alert_evidence_delivered": evidence_delivered,
    }
    passed = mechanism_ok and input_ok and detector_ok and process_ok and control_service_ok and delivery_ok
    run = {
        "schema": "ran-reproducer.run.v1", "run_id": run_id, "scenario_id": "nas-counter-desynchronization",
        "rule_ids": ["L3-06"], "mode": mode, "profile": profile_id, "reproduction_level": "protocol-result-emulation",
        "started_at": session_started_at(hello[0].get("session")), "period_ms": 100,
        "source": {"ue_binary_sha256": sha256(binary), "ue_config_sha256": sha256(ue_config),
                   "uecap_sha256": sha256(uecap), "ue_patch_sha256": sha256(patch),
                   "detector": components["detector"], "telemetry": components["telemetry"]},
        "logical_ues": 1, "clock": {"source": "realtime", "detector_and_telemetry_same_host": True},
        "claims": {"live_protocol_path_observed": True, "invalid_smc_cause_emulated": mode == "emulation",
                   "invalid_smc_received_observed": False, "mitm_observed": False,
                   "nas_counter_wrap_observed": False, "service_denial_observed": False},
    }
    (root / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    oracle = {"schema": "ran-reproducer.oracle.v1", "run_id": run_id, "mode": mode,
              "service": service, "checks": checks}
    (root / "oracle.jsonl").write_text(json.dumps(oracle, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    with (root / "detector.jsonl").open("w", encoding="utf-8") as output:
        for row in alerts:
            output.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    verdict = {
        "schema": "ran-reproducer.verdict.v1", "run_id": run_id, "passed": bool(passed),
        "expected_rule": "L3-06", "observed_alerts": len(raises),
        "dimensions": {"mechanism": "pass" if mechanism_ok else "fail",
                       "detection_input": "pass" if input_ok else "fail",
                       "detector_result": "pass" if detector_ok and delivery_ok else "fail",
                       "service_impact": "not_observed"},
    }
    (root / "verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "report.md").write_text(
        f"# {run_id}\n\n- 모드: `{mode}`\n- UE→ZMQ→DU/CU→TeleRAN→production detector: `true`\n"
        f"- SecurityModeReject/선행 SecurityModeCommand: `{len(rejects)}/{commands_before_reject}`\n"
        f"- L3-06 RAISE: `{len(raises)}`\n- 대시보드 수락/거절: `{dashboard_accepted}/{dashboard_rejected}`\n"
        f"- 판정: `{'pass' if passed else 'fail'}`\n"
        "- MITM·실제 invalid SMC 수신·NAS 카운터 랩어라운드·서비스 거부는 주장하지 않음\n", encoding="utf-8")
    files = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "evidence_manifest.json"):
        files[str(path.relative_to(root))] = {"size": path.stat().st_size, "sha256": sha256(path)}
    (root / "evidence_manifest.json").write_text(
        json.dumps({"schema": "ran-reproducer.evidence.v1", "run_id": run_id, "files": files},
                   sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return verdict


def main() -> int:
    if len(sys.argv) != 8:
        print("usage: verify_live.py RUN_DIR MODE RUN_ID OAI_BIN UE_CFG UECAP PATCH", file=sys.stderr)
        return 2
    try:
        verdict = verify(Path(sys.argv[1]), sys.argv[2], sys.argv[3], *(Path(value) for value in sys.argv[4:]))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"L3-06 live 판정 실패: {error}", file=sys.stderr)
        return 2
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
