#!/usr/bin/env python3
"""단일 control 또는 pre-security capability injection 실행을 판정·봉인한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


INJECTED = "UE_CAPABILITY_INJECTION event=pre_security_information_injected"
NORMAL = "UE_CAPABILITY_INJECTION event=normal_information_submitted"
MESSAGES = {"RRCSetupComplete", "SecurityModeCommand", "SecurityModeComplete", "UECapabilityEnquiry", "UECapabilityInformation"}


def regular(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"필수 일반 파일이 아닙니다: {path.name}")
    return path


def load_object(path: Path) -> dict:
    value = json.loads(regular(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 객체가 아닙니다: {path.name}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(regular(path).read_bytes()).hexdigest()


def load_observations(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in regular(path).read_text(encoding="utf-8").splitlines() if line]
    required = {"schema", "order", "source", "direction", "message", "gnb_cu_ue_f1ap_id", "gnb_du_ue_f1ap_id", "realtime_ns", "rrc_security_before"}
    if not rows:
        raise ValueError("F1 관측이 비었습니다")
    for row in rows:
        if not isinstance(row, dict) or set(row) != required or row["schema"] != "ue-capability.observation.v1":
            raise ValueError("관측 스키마가 잘못됐습니다")
        if row["source"] != "f1ap" or row["message"] not in MESSAGES or row["direction"] not in {"uplink", "downlink"}:
            raise ValueError("관측 메시지 값이 잘못됐습니다")
        if row["rrc_security_before"] not in {"OFF", "ON"}:
            raise ValueError("RRC 보안 상태가 잘못됐습니다")
        if any(type(row[key]) is not int or row[key] < 0 for key in ("order", "gnb_cu_ue_f1ap_id", "gnb_du_ue_f1ap_id", "realtime_ns")):
            raise ValueError("관측 순서·ID·시각이 잘못됐습니다")
    if [row["order"] for row in rows] != list(range(len(rows))) or any(a["realtime_ns"] > b["realtime_ns"] for a, b in zip(rows, rows[1:])):
        raise ValueError("관측이 시간순이 아닙니다")
    if len({(row["gnb_cu_ue_f1ap_id"], row["gnb_du_ue_f1ap_id"]) for row in rows}) != 1:
        raise ValueError("관측이 같은 F1 UE context에 exact join되지 않았습니다")
    return rows


def verify(run_dir: Path) -> dict:
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise ValueError("실행 디렉터리가 없거나 심볼릭 링크입니다")
    run = load_object(run_dir / "run.json")
    process = load_object(run_dir / "process.json")
    service = load_object(run_dir / "service.json")
    oracle = load_object(run_dir / "oracle.json")
    rows = load_observations(run_dir / "observations.jsonl")
    ue_log = regular(run_dir / "ue.log").read_text(encoding="utf-8", errors="replace")
    pcap = regular(run_dir / "f1.pcap")

    mode = run.get("mode")
    enabled = mode == "emulation"
    if run.get("schema") != "ue-capability.run.v1" or mode not in {"control", "emulation"}:
        raise ValueError("run 스키마 또는 mode가 잘못됐습니다")
    limits = {
        "pre_security_information_injection_emulated": enabled,
        "mitm_relay_observed": False,
        "capability_content_modified": False,
        "capability_downgrade_accepted": False,
    }
    if any(run.get(key) is not value for key, value in limits.items()):
        raise ValueError("에뮬레이션 주장 경계가 잘못됐습니다")
    if process.get("schema") != "ue-capability.process.v1" or service.get("schema") != "ue-capability.service.v1" or oracle.get("schema") != "ue-capability.oracle.v1":
        raise ValueError("process/service/oracle 스키마가 잘못됐습니다")
    service_values = [service.get(key) for key in ("registration_ok", "pdu_session_ok", "ping_ok")]
    if any(type(value) is not bool for value in service_values):
        raise ValueError("서비스 판정은 boolean이어야 합니다")

    names = [row["message"] for row in rows]
    counts = {name: names.count(name) for name in MESSAGES}
    setup_at = names.index("RRCSetupComplete") if "RRCSetupComplete" in names else -1
    first_info = names.index("UECapabilityInformation") if "UECapabilityInformation" in names else -1
    first_enquiry = names.index("UECapabilityEnquiry") if "UECapabilityEnquiry" in names else -1
    first_smc = names.index("SecurityModeCommand") if "SecurityModeCommand" in names else len(names)
    info_row = rows[first_info] if first_info >= 0 else {}
    pre_security = setup_at >= 0 and first_info > setup_at and first_info < first_smc and info_row.get("direction") == "uplink" and info_row.get("rrc_security_before") == "OFF"
    unsolicited = pre_security and (first_enquiry < 0 or first_enquiry > first_info)
    injected_markers = ue_log.count(INJECTED)
    normal_markers = ue_log.count(NORMAL)
    if oracle.get("injected_marker_count") != injected_markers or oracle.get("normal_marker_count") != normal_markers:
        raise ValueError("UE oracle와 원문 로그가 다릅니다")

    pcap_ok = pcap.stat().st_size > 24 and run.get("f1_pcap_sha256") == sha256(pcap)
    crash_free = process.get("crash_count") == 0 and process.get("forced_kill_count") == 0
    anomalous_control_message = any(row["message"] == "UECapabilityInformation" and row["rrc_security_before"] == "OFF" for row in rows)
    if mode == "control":
        control_healthy = not anomalous_control_message and injected_markers == 0 and all(service_values)
        mechanism = False
        passed = control_healthy and pcap_ok and crash_free
    else:
        control_healthy = False
        mechanism = unsolicited and injected_markers == 1
        passed = mechanism and pcap_ok and crash_free

    return {
        "schema": "ue-capability.verdict.v1",
        "run_id": run.get("run_id"),
        "mode": mode,
        "passed": passed,
        "control_healthy": control_healthy,
        "pre_security_injection_observed": enabled and mechanism,
        "unsolicited_information_observed": enabled and unsolicited,
        "service_effect_observed": enabled and not all(service_values),
        "mitm_relay_observed": False,
        "capability_content_modified": False,
        "capability_downgrade_accepted": False,
        "checks": {
            "rrc_setup_complete_count": counts["RRCSetupComplete"],
            "security_mode_command_count": counts["SecurityModeCommand"],
            "security_mode_complete_count": counts["SecurityModeComplete"],
            "ue_capability_enquiry_count": counts["UECapabilityEnquiry"],
            "ue_capability_information_count": counts["UECapabilityInformation"],
            "injected_marker_count": injected_markers,
            "normal_marker_count": normal_markers,
            "f1_pcap_nonempty_and_matched": pcap_ok,
            "crash_free": crash_free,
            "registration_ok": service_values[0],
            "pdu_session_ok": service_values[1],
            "ping_ok": service_values[2],
        },
    }


def write_manifest(run_dir: Path) -> None:
    output = run_dir / "evidence_manifest.json"
    if output.exists() or output.is_symlink():
        raise ValueError("기존 evidence manifest는 덮어쓰지 않습니다")
    names = ("run.json", "ue.log", "cu.log", "f1.pcap", "observations.jsonl", "oracle.json", "service.json", "process.json", "verdict.json")
    files = {name: {"size": regular(run_dir / name).stat().st_size, "sha256": sha256(run_dir / name)} for name in names}
    output.write_text(json.dumps({"schema": "ue-capability.evidence.v1", "files": files}, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    try:
        root = args.run_dir.resolve()
        verdict = verify(root)
        output = root / "verdict.json"
        if output.exists() or output.is_symlink():
            raise ValueError("기존 verdict는 덮어쓰지 않습니다")
        output.write_text(json.dumps(verdict, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_manifest(root)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"ue-capability 판정 실패: {error}", file=sys.stderr)
        return 2
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
